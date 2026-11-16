import html as _html
import json
import re
import socket
import ipaddress
import requests
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urljoin, urlparse
from bs4 import BeautifulSoup

MAX_TEXT_CHARS = 12000
MAX_RESPONSE_BYTES = 3 * 1024 * 1024
MAX_REDIRECTS = 5
REQUEST_TIMEOUT = 15
# Below this much text, the page almost certainly builds its content with JavaScript.
MIN_USEFUL_CHARS = 200

PASTE_HINT = "Switch to 'Paste Job Description Directly' and paste the posting text instead."

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


class ScrapeError(RuntimeError):
    """A scraping failure with a message that is safe and useful to show to the visitor."""


def is_safe_url(url: str) -> bool:
    """
    Validates that a URL is a safe public HTTP or HTTPS URL.
    Rejects private IPs, loopbacks (127.0.0.1, localhost), link-local (169.254.x.x),
    private ranges (192.168.x.x, 10.x.x.x, 172.16-31.x.x), and non-http schemes (ftp, etc.).
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    # Scheme must strictly be http or https
    if parsed.scheme.lower() not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    hostname_lower = hostname.lower()
    # Reject explicit localhost or common local names
    if hostname_lower in ("localhost", "local", "broadcasthost"):
        return False

    # Check if host is directly an IP or resolves to private/loopback IP
    try:
        ip_obj = ipaddress.ip_address(hostname)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
            return False
    except ValueError:
        # Not an IP string directly, resolve hostname
        try:
            resolved_ips = socket.gethostbyname_ex(hostname)[2]
            for ip_str in resolved_ips:
                ip_obj = ipaddress.ip_address(ip_str)
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
                    return False
        except Exception:
            # If resolution fails, do not allow unsafe URL
            return False

    return True


def clean_text(text: str) -> str:
    """
    Cleans raw text by removing HTML tags, URLs, special characters, and excessive whitespaces.
    """
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]*?>", " ", text)
    # Remove URL links
    text = re.sub(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", " ", text)
    # Remove non-ascii or special punctuation keeping meaningful text
    text = re.sub(r"[^\w\s.,;:!?'\"/\-()&]", " ", text)
    # Remove multiple spaces/newlines
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _html_to_text(fragment: str) -> str:
    """Visible text of an HTML fragment (which may itself be HTML-escaped)."""
    if not fragment:
        return ""
    fragment = str(fragment)
    if "&lt;" in fragment and "<" not in fragment:
        fragment = _html.unescape(fragment)
    return BeautifulSoup(fragment, "html.parser").get_text(separator=" ")


# ----------------------------------------------------------------------
# Fetching (every redirect hop is re-checked, so a public URL cannot bounce
# the server to a private address)
# ----------------------------------------------------------------------
def _fetch(url: str, accept: str = "text/html,application/xhtml+xml,*/*;q=0.8") -> requests.Response:
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        if not is_safe_url(current):
            raise ScrapeError(
                "That link is not allowed: only public http(s) web pages can be read. " + PASTE_HINT
            )
        try:
            resp = requests.get(
                current,
                headers={**_HEADERS, "Accept": accept},
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False,
                stream=True,
            )
        except requests.Timeout:
            raise ScrapeError("The site took too long to respond. Try again, or: " + PASTE_HINT)
        except requests.RequestException:
            raise ScrapeError("Could not connect to that site. Check the link, or: " + PASTE_HINT)

        if resp.is_redirect or resp.is_permanent_redirect:
            location = resp.headers.get("Location")
            resp.close()
            if not location:
                break
            current = urljoin(current, location)
            continue

        body = resp.raw.read(MAX_RESPONSE_BYTES + 1, decode_content=True)
        resp.close()
        resp._content = body[:MAX_RESPONSE_BYTES]
        resp._content_consumed = True
        return resp
    raise ScrapeError("That link redirects too many times. " + PASTE_HINT)


def _raise_for_status(resp: requests.Response) -> None:
    code = resp.status_code
    if code < 400:
        return
    if code in (401, 403, 429) or code == 999:
        raise ScrapeError(
            f"This site blocks automated readers (HTTP {code}), so the posting could not be fetched. " + PASTE_HINT
        )
    if code in (404, 410):
        raise ScrapeError(
            f"That job posting was not found (HTTP {code}). It may have been filled or removed. "
            "Check the link, or: " + PASTE_HINT
        )
    raise ScrapeError(f"The site returned an error (HTTP {code}). Try again later, or: " + PASTE_HINT)


# ----------------------------------------------------------------------
# Job boards with public JSON APIs
# ----------------------------------------------------------------------
def job_board_api(url: str) -> Optional[Tuple[str, str]]:
    """
    If the URL is a single posting on Greenhouse, Lever or Workday, return
    (board_name, api_url) for that board's public JSON endpoint.
    """
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return None
    host = (parsed.hostname or "").lower()
    parts = [p for p in parsed.path.split("/") if p]

    # Greenhouse: boards.greenhouse.io/{board}/jobs/{id}, job-boards[.eu].greenhouse.io/{board}/jobs/{id}
    if host.endswith("greenhouse.io"):
        if len(parts) >= 3 and parts[1] == "jobs" and parts[2].isdigit():
            return "Greenhouse", f"https://boards-api.greenhouse.io/v1/boards/{parts[0]}/jobs/{parts[2]}"
        query = parse_qs(parsed.query)
        board, token = query.get("for", [""])[0], query.get("token", [""])[0]
        if board and token.isdigit():  # embedded form: /embed/job_app?for={board}&token={id}
            return "Greenhouse", f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{token}"
        return None

    # Lever: jobs.lever.co/{company}/{posting-id}[/apply]
    if host in ("jobs.lever.co", "jobs.eu.lever.co"):
        if len(parts) >= 2 and re.fullmatch(r"[0-9a-fA-F-]{36}", parts[1]):
            api_host = "api.eu.lever.co" if ".eu." in host else "api.lever.co"
            return "Lever", f"https://{api_host}/v0/postings/{parts[0]}/{parts[1]}"
        return None

    # Workday: {tenant}.wd{N}.myworkdayjobs.com/[locale/]{site}/job/{...}
    if host.endswith(".myworkdayjobs.com") and "job" in parts:
        idx = parts.index("job")
        if idx >= 1 and idx < len(parts) - 1:
            tenant, site = host.split(".")[0], parts[idx - 1]
            rest = "/".join(parts[idx + 1:])
            return "Workday", f"https://{host}/wday/cxs/{tenant}/{site}/job/{rest}"
    return None


def _join_fields(pairs: List[Tuple[str, Any]]) -> str:
    return " ".join(f"{label}: {value}." for label, value in pairs if value)


def _text_from_board_json(board: str, data: Dict[str, Any]) -> str:
    if board == "Greenhouse":
        location = (data.get("location") or {}).get("name", "")
        company = data.get("company_name", "")
        head = _join_fields([("Job title", data.get("title")), ("Company", company), ("Location", location)])
        return f"{head} {_html_to_text(data.get('content', ''))}"

    if board == "Lever":
        cats = data.get("categories") or {}
        head = _join_fields([
            ("Job title", data.get("text")),
            ("Team", cats.get("team")),
            ("Location", cats.get("location")),
            ("Commitment", cats.get("commitment")),
        ])
        body = [data.get("descriptionPlain") or _html_to_text(data.get("description", ""))]
        for section in data.get("lists") or []:
            body.append(f"{section.get('text', '')}: {_html_to_text(section.get('content', ''))}")
        body.append(data.get("additionalPlain") or "")
        return f"{head} {' '.join(b for b in body if b)}"

    if board == "Workday":
        info = data.get("jobPostingInfo") or {}
        head = _join_fields([
            ("Job title", info.get("title")),
            ("Location", info.get("location")),
            ("Time type", info.get("timeType")),
        ])
        return f"{head} {_html_to_text(info.get('jobDescription', ''))}"
    return ""


def _scrape_job_board(board: str, api_url: str) -> str:
    resp = _fetch(api_url, accept="application/json")
    _raise_for_status(resp)
    try:
        data = resp.json()
    except ValueError:
        return ""
    return _text_from_board_json(board, data) if isinstance(data, dict) else ""


# Public Greenhouse boards used to find a posting that is live right now.
SAMPLE_BOARDS = ("stripe", "airbnb", "figma", "gitlab", "discord")
_SAMPLE_TITLE_WORDS = ("engineer", "developer")


def find_sample_job_url() -> Optional[str]:
    """
    A link to a job posting that exists today, for the "Use Sample URL" button.
    Postings come and go, so a fixed link would soon be dead. Returns None if none can be found.
    """
    for board in SAMPLE_BOARDS:
        try:
            resp = _fetch(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", accept="application/json")
            if resp.status_code != 200:
                continue
            jobs = [j for j in (resp.json().get("jobs") or []) if isinstance(j, dict) and j.get("id")]
        except Exception:
            continue
        if not jobs:
            continue
        technical = [j for j in jobs if any(w in str(j.get("title", "")).lower() for w in _SAMPLE_TITLE_WORDS)]
        job = (technical or jobs)[0]
        return f"https://boards.greenhouse.io/{board}/jobs/{job['id']}"
    return None


# ----------------------------------------------------------------------
# Generic pages
# ----------------------------------------------------------------------
def _find_job_posting(node: Any) -> Optional[Dict[str, Any]]:
    """Find a schema.org JobPosting object inside parsed JSON-LD."""
    if isinstance(node, list):
        for item in node:
            found = _find_job_posting(item)
            if found:
                return found
    elif isinstance(node, dict):
        kind = node.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "JobPosting" in kinds:
            return node
        if "@graph" in node:
            return _find_job_posting(node["@graph"])
    return None


def _text_from_json_ld(soup: BeautifulSoup) -> str:
    """Many career sites embed the posting as structured data, even when the page itself is built with JavaScript."""
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            posting = _find_job_posting(json.loads(tag.string or tag.get_text() or ""))
        except (ValueError, TypeError):
            continue
        if not posting:
            continue
        org = posting.get("hiringOrganization")
        company = org.get("name") if isinstance(org, dict) else org
        head = _join_fields([
            ("Job title", posting.get("title")),
            ("Company", company),
            ("Employment type", posting.get("employmentType")),
        ])
        extra = " ".join(
            _html_to_text(str(posting.get(key, "")))
            for key in ("description", "responsibilities", "qualifications", "skills", "experienceRequirements")
            if posting.get(key) and isinstance(posting.get(key), str)
        )
        if extra.strip():
            return f"{head} {extra}"
    return ""


def scrape_website(url: str) -> str:
    """
    Returns the text of a job posting or careers page, trimmed to 12,000 characters.

    Order of attempts:
    1. Greenhouse, Lever and Workday postings are read from the board's public JSON API.
    2. Structured data (schema.org JobPosting) embedded in the page.
    3. The page's visible text.

    Raises ScrapeError with a message suitable for showing to the visitor.
    """
    url = (url or "").strip()
    if not is_safe_url(url):
        raise ScrapeError(
            "That link is not allowed: only public http(s) web pages can be read. " + PASTE_HINT
        )

    text = ""
    board = job_board_api(url)
    if board:
        try:
            text = clean_text(_scrape_job_board(*board))
        except ScrapeError:
            text = ""  # fall through to reading the page itself

    if len(text) < MIN_USEFUL_CHARS:
        resp = _fetch(url)
        _raise_for_status(resp)
        content_type = resp.headers.get("Content-Type", "").lower()
        if content_type and not any(t in content_type for t in ("html", "xml", "text/plain")):
            raise ScrapeError("That link is not a web page (it looks like a file). " + PASTE_HINT)

        soup = BeautifulSoup(resp.content, "html.parser")
        text = clean_text(_text_from_json_ld(soup))
        if len(text) < MIN_USEFUL_CHARS:
            for element in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                element.decompose()
            text = clean_text(soup.get_text(separator=" "))

    if len(text) < MIN_USEFUL_CHARS:
        raise ScrapeError(
            "The page loaded, but it has almost no readable text. It probably builds its content "
            "with JavaScript, which this reader cannot run. " + PASTE_HINT
        )
    return text[:MAX_TEXT_CHARS]
