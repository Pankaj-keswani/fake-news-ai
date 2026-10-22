"""Evidence gathering: Google News (incl. fact-check articles), Wikipedia, Google Fact Check API."""
import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests

import config

log = logging.getLogger(__name__)

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
BOT_UA = "FakeNewsDetector/2.0 (fact-checking web app; python-requests)"

# --------------------------------------------------------------------- source types
FACT_CHECKERS = {
    "factcheck.pib.gov.in", "pib.gov.in", "altnews.in", "boomlive.in", "factly.in", "vishvasnews.com",
    "newschecker.in", "factcrescendo.com", "factcheck.afp.com", "thequint.com", "newsmeter.in",
    "thelogicalindian.com", "snopes.com", "politifact.com", "fullfact.org", "factcheck.org",
    "newsmobile.in", "digiteye.in", "dfrac.org", "telugupost.com",
}
OFFICIAL = {"rbi.org.in", "gov.in", "nic.in", "who.int", "un.org", "mohfw.gov.in", "eci.gov.in", "isro.gov.in"}
WIRE = {"reuters.com", "apnews.com", "ptinews.com", "afp.com", "aninews.in", "ians.in"}
MAJOR = {
    "thehindu.com", "indianexpress.com", "hindustantimes.com", "ndtv.com", "timesofindia.indiatimes.com",
    "indiatimes.com", "livemint.com", "business-standard.com", "indiatoday.in", "theprint.in",
    "scroll.in", "news18.com", "abplive.com", "aajtak.in", "zeenews.india.com", "deccanherald.com",
    "telegraphindia.com", "moneycontrol.com", "wionews.com", "bbc.com", "bbc.co.uk", "cnn.com",
    "nytimes.com", "theguardian.com", "washingtonpost.com", "aljazeera.com", "bhaskar.com",
    "jagran.com", "amarujala.com", "livehindustan.com", "financialexpress.com", "thehindubusinessline.com",
    "tribuneindia.com", "outlookindia.com", "firstpost.com", "republicworld.com", "dnaindia.com",
    "newindianexpress.com", "economictimes.com", "cnbctv18.com", "variety.com", "hollywoodreporter.com",
    "deadline.com", "espncricinfo.com", "lokmat.com", "manoramaonline.com", "mathrubhumi.com",
}
_FACTCHECK_TITLE = re.compile(
    r"fact[\s-]?check|fake news|is fake|misleading|false claim|viral claim|debunk|hoax|"
    r"फैक्ट चेक|फर्जी|भ्रामक|झूठा दावा",
    re.IGNORECASE,
)


def _domain(url: str) -> str:
    try:
        host = urllib.parse.urlparse(url).hostname or ""
    except ValueError:
        return ""
    return host.lower().removeprefix("www.")


def _matches(domain: str, group: set) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in group)


def classify_source(site_url: str, title: str = "") -> str:
    """'factcheck' | 'official' | 'wire' | 'major' | 'other'"""
    d = _domain(site_url)
    if _matches(d, FACT_CHECKERS):
        return "factcheck"
    tier = "other"
    if _matches(d, OFFICIAL):
        tier = "official"
    elif _matches(d, WIRE):
        tier = "wire"
    elif _matches(d, MAJOR):
        tier = "major"
    # a fact-check story from an established outlet counts as a fact-check
    if tier != "other" and title and _FACTCHECK_TITLE.search(title):
        return "factcheck"
    return tier


def _iso_date(rfc822: str) -> str:
    try:
        return parsedate_to_datetime(rfc822).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return ""


# --------------------------------------------------------------------- Google News
def google_news(query: str, lang: str = "en", max_results: int = 6) -> list:
    query = (query or "").strip()
    if not query:
        return []
    hl, ceid = ("hi", "IN:hi") if lang == "hi" else ("en-IN", "IN:en")
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": hl, "gl": "IN", "ceid": ceid}
    )
    try:
        r = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=8)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except (requests.RequestException, ET.ParseError) as exc:
        log.warning("Google News failed for %r: %s", query, exc)
        return []

    out = []
    for item in root.findall(".//item")[:max_results]:
        title = (item.findtext("title") or "").strip()
        src_el = item.find("source")
        src_name = (src_el.text or "").strip() if src_el is not None and src_el.text else ""
        src_url = src_el.get("url", "") if src_el is not None else ""
        # Google appends " - Publisher" to titles; strip it since we show the publisher separately
        if src_name and title.endswith(" - " + src_name):
            title = title[: -len(" - " + src_name)].strip()
        if not title:
            continue
        out.append({
            "title": title,
            "url": (item.findtext("link") or "").strip(),
            "source": src_name or _domain(src_url),
            "date": _iso_date(item.findtext("pubDate") or ""),
            "type": classify_source(src_url, title),
            "origin": "news",
        })
    return out


# --------------------------------------------------------------------- Wikipedia
def wikipedia(query: str, lang: str = "en") -> list:
    """Top matching article intro — gives background facts (birth/death dates, what something is)."""
    query = (query or "").strip()
    if not query:
        return []
    api = f"https://{lang}.wikipedia.org/w/api.php"
    headers = {"User-Agent": BOT_UA}
    try:
        r = requests.get(api, params={
            "action": "query", "list": "search", "srsearch": query, "srlimit": 1,
            "format": "json", "srprop": "",
        }, headers=headers, timeout=6)
        r.raise_for_status()
        hits = r.json().get("query", {}).get("search", [])
        if not hits:
            return []
        title = hits[0]["title"]
        r = requests.get(api, params={
            "action": "query", "prop": "extracts|info", "exintro": 1, "explaintext": 1,
            "exchars": 900, "titles": title, "format": "json", "inprop": "url", "redirects": 1,
        }, headers=headers, timeout=6)
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
        page = next(iter(pages.values()), {})
    except (requests.RequestException, ValueError, KeyError, StopIteration) as exc:
        log.warning("Wikipedia failed for %r: %s", query, exc)
        return []

    extract = re.sub(r"\s+", " ", page.get("extract") or "").strip()
    if not extract:
        return []
    return [{
        "title": f"{page.get('title', title)} — Wikipedia",
        "url": page.get("fullurl") or f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title)}",
        "source": "Wikipedia",
        "date": "",
        "type": "reference",
        "origin": "wikipedia",
        "snippet": extract,
    }]


# --------------------------------------------------------------------- Google Fact Check API
def factcheck_api(query: str, max_results: int = 4) -> list:
    """Published fact-checks (needs optional FACTCHECK_API_KEY)."""
    if not config.FACTCHECK_API_KEY or not (query or "").strip():
        return []
    try:
        r = requests.get(
            "https://factchecktools.googleapis.com/v1alpha1/claims:search",
            params={"query": query, "key": config.FACTCHECK_API_KEY, "pageSize": max_results},
            timeout=8,
        )
        r.raise_for_status()
        claims = r.json().get("claims", [])
    except (requests.RequestException, ValueError) as exc:
        log.warning("Fact Check API failed for %r: %s", query, exc)
        return []

    out = []
    for c in claims:
        for review in (c.get("claimReview") or [])[:1]:
            publisher = (review.get("publisher") or {}).get("name") or _domain(review.get("url", ""))
            rating = review.get("textualRating", "")
            out.append({
                "title": review.get("title") or c.get("text", ""),
                "url": review.get("url", ""),
                "source": publisher,
                "date": (review.get("reviewDate") or "")[:10],
                "type": "factcheck",
                "origin": "factcheck_api",
                "snippet": f"Claim: {c.get('text', '')[:200]} — Rating: {rating}",
            })
    return out[:max_results]


def dedupe(items: list, limit: int = 12) -> list:
    seen, out = set(), []
    for s in items:
        key = re.sub(r"\W+", "", (s.get("title") or "").lower())[:80]
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out[:limit]
