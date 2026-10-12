import re
import socket
import ipaddress
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from langchain_community.document_loaders import WebBaseLoader


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


def scrape_website(url: str) -> str:
    """
    Extracts text content from a URL using WebBaseLoader with fallback to requests + BeautifulSoup.
    Validates URL safety, applies a 15-second timeout, and trims text to 12,000 characters.
    """
    if not is_safe_url(url):
        raise ValueError(f"URL '{url}' is invalid or blocked for security reasons (private/local IP or unsupported scheme).")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    scraped_text = ""

    # Attempt 1: LangChain WebBaseLoader
    try:
        loader = WebBaseLoader(
            web_paths=(url,),
            header_template=headers,
        )
        docs = loader.load()
        if docs and docs[0].page_content.strip():
            scraped_text = clean_text(docs[0].page_content)
    except Exception:
        pass

    # Attempt 2: requests + BeautifulSoup fallback
    if not scraped_text:
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove scripts and style elements
            for element in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                element.decompose()

            raw_text = soup.get_text(separator=" ")
            scraped_text = clean_text(raw_text)
        except Exception as e:
            raise RuntimeError(f"Failed to scrape webpage at {url}: {str(e)}")

    # Trim to 12,000 characters (item 9)
    if len(scraped_text) > 12000:
        scraped_text = scraped_text[:12000]

    return scraped_text
