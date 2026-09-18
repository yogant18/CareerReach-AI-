import re
import requests
from bs4 import BeautifulSoup
from langchain_community.document_loaders import WebBaseLoader


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
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    # Attempt 1: LangChain WebBaseLoader
    try:
        loader = WebBaseLoader(
            web_paths=(url,),
            header_template=headers,
        )
        docs = loader.load()
        if docs and docs[0].page_content.strip():
            return clean_text(docs[0].page_content)
    except Exception as e:
        pass

    # Attempt 2: requests + BeautifulSoup fallback
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove scripts and style elements
        for element in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            element.decompose()

        text = soup.get_text(separator=" ")
        return clean_text(text)
    except Exception as e:
        raise RuntimeError(f"Failed to scrape webpage at {url}: {str(e)}")
