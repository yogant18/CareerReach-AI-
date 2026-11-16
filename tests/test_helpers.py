"""Tests for the small pure helpers: usage limits, email tools, skill matching, resume reading."""

import io
import json
import zipfile
from urllib.parse import parse_qs, unquote, urlparse

import pytest

from app.email_tools import compose_links, record_feedback, replace_subject, split_subject
from app.matching import skill_match
from app.resume import MAX_RESUME_CHARS, ResumeError, extract_resume_text
from app.usage import CHAT, EMAIL, UsageLimiter, client_identifier, format_wait
from conftest import SAMPLE_EMAIL


# ---------------- usage limits ----------------
def make_limiter(tmp_path, emails=3, chats=10, cap=0):
    return UsageLimiter(str(tmp_path / "usage.json"), {EMAIL: emails, CHAT: chats}, global_daily_cap=cap, salt="s")


def test_visitor_limit_blocks_after_allowance(tmp_path):
    limiter = make_limiter(tmp_path)
    visitor = limiter.visitor_id("1.2.3.4")
    assert [limiter.consume(visitor, EMAIL)["allowed"] for _ in range(4)] == [True, True, True, False]
    status = limiter.status(visitor, EMAIL)
    assert status["reason"] == "visitor" and status["remaining"] == 0 and status["reset_at"]


def test_visitors_are_independent_and_ids_are_hashed(tmp_path):
    limiter = make_limiter(tmp_path, emails=1)
    a, b = limiter.visitor_id("1.2.3.4"), limiter.visitor_id("5.6.7.8")
    assert a != b and "1.2.3.4" not in a
    assert limiter.consume(a, EMAIL)["allowed"] and limiter.consume(b, EMAIL)["allowed"]
    assert "1.2.3.4" not in (tmp_path / "usage.json").read_text()


def test_global_cap_applies_to_everyone(tmp_path):
    limiter = make_limiter(tmp_path, cap=2)
    a, b, c = (limiter.visitor_id(x) for x in "abc")
    assert limiter.consume(a, EMAIL)["allowed"] and limiter.consume(b, EMAIL)["allowed"]
    blocked = limiter.consume(c, EMAIL)
    assert not blocked["allowed"] and blocked["reason"] == "global"


def test_window_expires_after_24_hours(tmp_path):
    limiter = make_limiter(tmp_path, emails=1)
    visitor = limiter.visitor_id("x")
    limiter.consume(visitor, EMAIL)
    assert not limiter.consume(visitor, EMAIL)["allowed"]
    store = tmp_path / "usage.json"
    data = json.loads(store.read_text())
    data["visitors"][visitor]["start"] -= 24 * 3600 + 1
    store.write_text(json.dumps(data))
    assert limiter.consume(visitor, EMAIL)["allowed"]


def test_client_identifier_ignores_forged_and_private_addresses():
    headers = {"X-Forwarded-For": "9.9.9.9, 8.8.4.4, 10.0.0.1"}
    assert client_identifier(headers, "10.1.1.1", "sess") == "8.8.4.4"
    assert client_identifier({}, None, "abc") == "session:abc"
    assert client_identifier({}, "203.0.113.7", "abc") == "203.0.113.7"
    assert client_identifier({}, object(), "abc") == "session:abc"  # not a real address
    assert format_wait(None) == "24h"


# ---------------- email tools ----------------
def test_split_and_replace_subject():
    subject, body = split_subject(SAMPLE_EMAIL)
    assert subject == "Quick idea for your Python role" and body.startswith("Hi Priya,")
    assert split_subject("Hi there\nBody") == ("", "Hi there\nBody")
    assert replace_subject(SAMPLE_EMAIL, " New ").startswith("Subject: New\n\nHi Priya,")
    assert replace_subject("Hi\nBody", "S") == "Subject: S\n\nHi\nBody"


def test_compose_links_round_trip_special_characters():
    subject, body = split_subject(SAMPLE_EMAIL)
    links = compose_links(subject, body)
    gmail = parse_qs(urlparse(links["gmail"]).query)
    assert gmail["su"][0] == subject and gmail["body"][0].replace("\r\n", "\n") == body
    assert parse_qs(urlparse(links["outlook"]).query)["subject"][0] == subject
    assert links["mailto"].startswith("mailto:?subject=")
    assert unquote(links["mailto"].split("body=")[1]).replace("\r\n", "\n") == body


def test_record_feedback_appends_json_lines(tmp_path, capsys):
    path = tmp_path / "fb.jsonl"
    record_feedback(str(path), {"rating": "up"})
    record_feedback(str(path), {"rating": "down"})
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["rating"] for r in rows] == ["up", "down"] and "ts" in rows[0]


# ---------------- skill matching ----------------
def test_skill_match_counts_found_and_missing():
    resume = "Built REST APIs in Python and FastAPI, deployed on Amazon Web Services with Docker. Used Node.js and K8s."
    result = skill_match(["Python", "AWS", "Docker", "NodeJS", "Kubernetes", "Rust", "python"], resume)
    assert result["matched"] == ["Python", "AWS", "Docker", "NodeJS", "Kubernetes"]
    assert result["missing"] == ["Rust"] and result["total"] == 6 and result["score"] == 83


def test_skill_match_avoids_false_positives():
    # "go" as an English word must not match Golang; "Java" must not match "JavaScript"
    result = skill_match(["Golang", "Java", "C++", "C#"], "I go to work and write JavaScript, C++ and csharp.")
    assert result["matched"] == ["C++", "C#"] and result["missing"] == ["Golang", "Java"]
    assert skill_match(["Go"], "Services written in Golang")["score"] == 100
    assert skill_match([], "anything") == {"matched": [], "missing": [], "total": 0, "score": 0}


# ---------------- resume reading ----------------
def make_docx(paragraphs):
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("word/document.xml", f'<w:document xmlns:w="{ns}"><w:body>{body}</w:body></w:document>')
    return buf.getvalue()


def make_pdf(text):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})
    })
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


LONG_LINE = "Senior Python engineer with five years building data pipelines on AWS and leading a team of four."


def test_resume_from_txt_and_docx():
    assert "data pipelines" in extract_resume_text("cv.txt", LONG_LINE.encode())
    text = extract_resume_text("CV.DOCX", make_docx([LONG_LINE, "Skills: Python, SQL"]))
    assert "data pipelines" in text and "Skills: Python, SQL" in text


def test_resume_from_pdf():
    assert "data pipelines" in extract_resume_text("cv.pdf", make_pdf(LONG_LINE))


def test_resume_is_trimmed_to_limit():
    assert len(extract_resume_text("cv.txt", ("word " * 5000).encode())) <= MAX_RESUME_CHARS


@pytest.mark.parametrize("name,data", [
    ("cv.exe", b"x" * 200),                  # unsupported type
    ("cv.txt", b"too short"),                # no real content
    ("cv.pdf", b"this is not a pdf" * 20),   # corrupt
    ("cv.docx", b"this is not a zip" * 20),  # corrupt
    ("cv.txt", b"a" * (5 * 1024 * 1024 + 1)),  # too large
])
def test_resume_problems_raise_friendly_errors(name, data):
    with pytest.raises(ResumeError):
        extract_resume_text(name, data)
