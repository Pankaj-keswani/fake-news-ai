# Fake News Detector

Paste a WhatsApp forward, a headline or a news link. The app finds the main claim, searches live
news, published fact-checks and Wikipedia, and an AI explains whether it looks **True**, **False**,
**Partly true** or **Unverifiable** — in English, Hindi or Hinglish — with the sources it used.

> ⚠️ AI can be wrong. The site shows this warning on every page and every result.

## Features

- Checks plain text **and links** (it reads the article on the page)
- Live evidence: Google News, fact-check articles (PIB, Alt News, BOOM, …), Hindi news, Wikipedia,
  plus the Google Fact Check API if you add a free key
- Source badges (fact-check / official / news agency / outlet) and which sources the AI relied on
- Claim-by-claim breakdown for messages with several claims
- Warning signs: AI-found red flags + offline detection of rumour patterns (“forward to everyone”,
  “media won't show this”, free-offer bait, ALL CAPS…)
- Replies in the user's language (English / हिन्दी / Hinglish)
- Share result on WhatsApp, copy, native share, 👍/👎 feedback
- History saved on the user's device, dark/light theme, voice input (English or Hindi)
- Production-ready: rate limiting, caching, security headers, link-safety (SSRF) checks,
  prompt-injection guard, AI model fallback, health check

## Run on your computer (Windows)

```bat
cd backend
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      &  REM first time only, then put your GROQ_API_KEY in .env
python app.py
```

Open **http://127.0.0.1:5000** — the backend now serves the website too.

## Deploy

You need a Groq API key (https://console.groq.com/keys). Never commit `backend/.env`; `.gitignore`
already excludes it.

### Vercel (free Hobby plan, no sleeping)
1. Push this folder to a GitHub repo.
2. On https://vercel.com click **Add New → Project** and import the repo. Leave every build setting
   at its default (Vercel detects Flask from `index.py` + `requirements.txt`).
3. Before clicking Deploy, open **Environment Variables** and add `GROQ_API_KEY`.
4. Deploy. Your site is live at `https://<project>.vercel.app`.

Notes: Hobby is for personal, non-commercial use. Each server instance keeps its own cache and
rate-limit counters, so limits are approximate on Vercel. Logs: Project → **Logs**.

### Render (free tier)
1. Push this folder to a GitHub repo.
2. On https://render.com choose **New → Blueprint** and pick the repo (it reads `render.yaml`).
3. Paste your `GROQ_API_KEY` when asked. Done — Render gives you an `https://….onrender.com` URL.

### Railway / Heroku-style hosts
Uses the `Procfile`. Set environment variables `GROQ_API_KEY` and `APP_ENV=production`.

### Docker / any VPS
```bash
docker build -t fake-news-detector .
docker run -p 8000:8000 -e GROQ_API_KEY=your_key fake-news-detector
```
Put it behind HTTPS (Nginx/Caddy/Cloudflare) for a public site.

### Frontend on a different domain (e.g. Vercel/Netlify)
Not required, but if you do it: set `ALLOWED_ORIGINS=https://your-frontend-domain` on the backend
and change `API_BASE` at the top of `frontend/script.js` to your backend URL. You'd also need to
add that URL to `connect-src` in the CSP in `backend/app.py`.

## Configuration (environment variables)

| Variable | Default | What it does |
|---|---|---|
| `GROQ_API_KEY` | — | **Required.** AI provider key |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Model that decides the verdict |
| `GROQ_FAST_MODEL` | `openai/gpt-oss-20b` | Reads the claim first; fallback if the main model is busy |
| `FACTCHECK_API_KEY` | — | Optional Google Fact Check Tools key for more published fact-checks |
| `APP_ENV` | `development` | Set `production` on the live server |
| `RATE_LIMIT` | `8 per minute;80 per day` | Checks allowed per visitor IP |
| `CACHE_TTL_SECONDS` | `21600` | How long identical checks are reused (memory only) |
| `MAX_TEXT_LENGTH` | `5000` | Longest message accepted |
| `TRUST_PROXY` | on in production | Use the real visitor IP behind Render/Nginx |
| `ALLOWED_ORIGINS` | — | Extra domains allowed to call the API |

## Costs and limits to know before going live

- Each check makes 2 AI calls (a small one and a large one). Watch your Groq usage dashboard;
  the free tier has per-minute and per-day limits, and the site will show "AI is busy" when hit.
- Google News RSS is a free public feed, not an official API — it may rate-limit heavy traffic.
- The cache and rate limits live in memory, so run **one** server process (the included gunicorn
  config does this) or move them to Redis if you scale out.

## Tests

```bash
cd backend
pip install pytest
python -m pytest -q    # offline tests, no API key needed
```

## API

`POST /api/analyze` `{"text": "..."}` → verdict JSON
`GET /api/health` → status
`POST /api/feedback` `{"helpful": true, "verdict": "False", "text": "..."}`
