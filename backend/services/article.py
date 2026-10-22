"""Safely download a news article from a link the user pasted and pull out its text."""
import ipaddress
import re
import socket
import urllib.parse

import requests
from bs4 import BeautifulSoup

from services.sources import BROWSER_UA

MAX_BYTES = 1_500_000
MAX_REDIRECTS = 4
MAX_TEXT = 4000


class ArticleError(Exception):
    """Raised with a user-friendly message when a link can't be read."""


def _is_public(host: str) -> bool:
    """Block localhost / private network addresses (SSRF protection for a public server)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
                or ip.is_reserved or ip.is_unspecified):
            return False
    return True


def _check_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ArticleError("Only normal http/https links can be checked.")
    if parsed.port not in (None, 80, 443):
        raise ArticleError("This link uses an unusual port and can't be opened.")
    if not _is_public(parsed.hostname):
        raise ArticleError("This link points to a private or unknown address.")
    return url


def fetch_article(url: str) -> dict:
    """Returns {"url", "title", "site", "published", "text"} or raises ArticleError."""
    current = url
    resp = None
    try:
        for _ in range(MAX_REDIRECTS + 1):
            _check_url(current)
            resp = requests.get(current, headers={"User-Agent": BROWSER_UA, "Accept": "text/html"},
                                timeout=(5, 10), allow_redirects=False, stream=True)
            if resp.is_redirect and resp.headers.get("Location"):
                current = urllib.parse.urljoin(current, resp.headers["Location"])
                resp.close()
                continue
            break
        else:
            raise ArticleError("The link redirects too many times.")

        if resp.status_code >= 400:
            raise ArticleError(f"The website refused the request (HTTP {resp.status_code}).")
        ctype = resp.headers.get("Content-Type", "")
        if "html" not in ctype.lower():
            raise ArticleError("This link isn't a web page (it may be an image, video or PDF).")

        chunks, size = [], 0
        for chunk in resp.iter_content(64 * 1024):
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_BYTES:
                break
        html = b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")
    except requests.RequestException:
        raise ArticleError("Couldn't open that link. The site may be down or blocking automated access.")
    finally:
        if resp is not None:
            resp.close()

    soup = BeautifulSoup(html, "html.parser")

    def meta(*names):
        for n in names:
            tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
            if tag and tag.get("content"):
                return tag["content"].strip()
        return ""

    title = meta("og:title", "twitter:title") or (soup.title.get_text(strip=True) if soup.title else "")
    description = meta("og:description", "description", "twitter:description")
    published = meta("article:published_time", "datePublished", "pubdate")[:10]
    site = meta("og:site_name") or (urllib.parse.urlparse(current).hostname or "").removeprefix("www.")

    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form", "iframe"]):
        tag.decompose()
    container = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs = []
    for p in container.find_all(["p", "h2"]):
        txt = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
        if len(txt) >= 40:
            paragraphs.append(txt)
    body = " ".join(paragraphs)

    text = "\n".join(x for x in (title, description, body) if x)[:MAX_TEXT].strip()
    if len(text) < 60:
        raise ArticleError("Couldn't find readable article text on that page. Paste the text instead.")
    return {"url": current, "title": title, "site": site, "published": published, "text": text}
