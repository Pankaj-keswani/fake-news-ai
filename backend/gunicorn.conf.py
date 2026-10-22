# Production server settings (Linux / Docker / Render / Railway).
# One worker process with threads, so the in-memory cache and rate limits are shared
# by every request. Scale with more threads, not more workers.
import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = 1
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "8"))
timeout = 120          # a full check can take ~10-40 s
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")
forwarded_allow_ips = "*"
