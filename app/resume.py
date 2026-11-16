"""
Reads the text out of an uploaded resume (PDF, Word .docx, or plain text).
The text is only ever held in the visitor's session; nothing is written to disk.
"""

import io
import re
import zipfile
from xml.etree import ElementTree

MAX_RESUME_BYTES = 5 * 1024 * 1024
MAX_RESUME_CHARS = 8000   # enough for a 2-3 page resume; keeps prompts a sensible size
MAX_PDF_PAGES = 10
_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class ResumeError(ValueError):
    """A problem with the uploaded resume, with a message suitable for the visitor."""


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ResumeError("This PDF is password-protected. Remove the password, or paste your resume text instead.")
        pages = [page.extract_text() or "" for page in reader.pages[:MAX_PDF_PAGES]]
    except ResumeError:
        raise
    except Exception:
        raise ResumeError("This PDF could not be read. Try a different file, or paste your resume text instead.")
    return "\n".join(pages)


def _docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > 20 * 1024 * 1024:
                raise ResumeError("This Word file is too large to read.")
            root = ElementTree.fromstring(archive.read(info))
    except ResumeError:
        raise
    except Exception:
        raise ResumeError("This Word file could not be read. Save it as .docx or PDF, or paste your resume text instead.")
    paragraphs = []
    for para in root.iter(f"{_WORD_NS}p"):
        text = "".join(node.text or "" for node in para.iter(f"{_WORD_NS}t"))
        if text.strip():
            paragraphs.append(text)
    return "\n".join(paragraphs)


def tidy_resume_text(text: str) -> str:
    """Collapse whitespace and trim to the size limit."""
    text = (text or "").replace("\x00", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return text[:MAX_RESUME_CHARS]


def extract_resume_text(filename: str, data: bytes) -> str:
    """Return the resume's text. Raises ResumeError with a visitor-friendly message on failure."""
    if len(data) > MAX_RESUME_BYTES:
        raise ResumeError("That file is larger than 5 MB. Upload a smaller file, or paste your resume text instead.")
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        text = _pdf_text(data)
    elif name.endswith(".docx"):
        text = _docx_text(data)
    elif name.endswith((".txt", ".md")):
        text = data.decode("utf-8", errors="replace")
    else:
        raise ResumeError("Please upload a PDF, a Word .docx file or a .txt file.")

    text = tidy_resume_text(text)
    if len(text) < 80:
        raise ResumeError(
            "Almost no text could be read from that file. If it is a scanned image, "
            "paste your resume text instead."
        )
    return text
