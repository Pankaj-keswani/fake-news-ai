"""
AI Fake News Detector — web server.

Local:       python app.py            -> http://127.0.0.1:5000
Production:  gunicorn -c gunicorn.conf.py app:app
"""
import hashlib
import logging

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

import config
from services.analyzer import analyze_news

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")

app = Flask(__name__, static_folder=None)
app.json.ensure_ascii = False  # keep Hindi readable in JSON
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # reject huge request bodies

if config.TRUST_PROXY:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# The frontend is served by this same server, so CORS is only needed for a separately hosted frontend.
if config.ALLOWED_ORIGINS:
    CORS(app, resources={r"/api/*": {"origins": config.ALLOWED_ORIGINS}, r"/analyze": {"origins": config.ALLOWED_ORIGINS}})
elif not config.IS_PRODUCTION:
    CORS(app)  # local development: allow opening index.html directly from disk

limiter = Limiter(get_remote_address, app=app, storage_uri="memory://", default_limits=[],
                  headers_enabled=True)


# ------------------------------------------------------------------ security headers
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
       "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
       "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(), microphone=(self)")
    if resp.mimetype == "text/html":
        resp.headers.setdefault("Content-Security-Policy", CSP)
    if config.IS_PRODUCTION:
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return resp


# ------------------------------------------------------------------ frontend
@app.get("/")
def index():
    return send_from_directory(config.FRONTEND_DIR, "index.html", max_age=0)


@app.get("/<path:filename>")
def static_files(filename):
    if filename.startswith("api/"):
        return jsonify({"error": "Not found"}), 404
    return send_from_directory(config.FRONTEND_DIR, filename, max_age=3600)


# ------------------------------------------------------------------ API
def _bad_request(message, status=400):
    return jsonify({"error": message}), status


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "ai_configured": bool(config.GROQ_API_KEY),
                    "model": config.GROQ_MODEL, "max_text_length": config.MAX_TEXT_LENGTH})


@app.post("/api/analyze")
@app.post("/analyze")  # old URL, kept for compatibility
@limiter.limit(config.RATE_LIMIT)
def analyze():
    data = request.get_json(silent=True)
    text = data.get("text") if isinstance(data, dict) else None
    if not isinstance(text, str) or not text.strip():
        return _bad_request("Please type or paste a message to check.")
    text = text.strip()
    if len(text) < 4:
        return _bad_request("That's too short to check. Paste the full message or headline.")
    if len(text) > config.MAX_TEXT_LENGTH:
        return _bad_request(f"That's too long. Keep it under {config.MAX_TEXT_LENGTH} characters.", 413)

    try:
        result = analyze_news(text)
    except Exception:
        log.exception("Analysis crashed")
        return jsonify({"error": "Something went wrong on the server while checking this. Please try again."}), 500
    if result.get("error"):
        return jsonify(result), (422 if result.get("error_kind") == "input" else 503)
    return jsonify(result)


@app.post("/api/feedback")
@limiter.limit("20 per minute")
def feedback():
    """Thumbs up/down. Only a hash of the message is logged, never the message itself."""
    data = request.get_json(silent=True) or {}
    helpful = data.get("helpful")
    if not isinstance(helpful, bool):
        return _bad_request("'helpful' must be true or false")
    text = str(data.get("text", ""))[: config.MAX_TEXT_LENGTH]
    log.info("feedback helpful=%s verdict=%s msg=%s", helpful, str(data.get("verdict", ""))[:20],
             hashlib.sha256(text.encode("utf-8")).hexdigest()[:12])
    return jsonify({"ok": True})


# ------------------------------------------------------------------ errors
@app.errorhandler(429)
def too_many(e):
    return jsonify({"error": "You're checking messages too quickly. Wait a minute and try again."}), 429


@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "That request is too large."}), 413


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    return send_from_directory(config.FRONTEND_DIR, "index.html", max_age=0), 404


@app.errorhandler(405)
def not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405


if __name__ == "__main__":
    if not config.GROQ_API_KEY:
        log.warning("GROQ_API_KEY is not set — add it to backend/.env")
    log.info("Open http://127.0.0.1:%s in your browser", config.PORT)
    app.run(host="127.0.0.1", port=config.PORT, debug=config.DEBUG)
