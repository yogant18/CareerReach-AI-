"""
Small helpers for working with a generated email: splitting out the subject,
building "open in mail app" links, and recording thumbs up/down feedback.
"""

import json
import os
import re
import threading
import time
from typing import Dict, Tuple
from urllib.parse import quote

_SUBJECT_RE = re.compile(r"^\s*subject\s*:\s*(.*)$", re.IGNORECASE)

# Compose links carry the whole email in the URL; very long ones get cut off by browsers.
MAX_LINK_BODY_CHARS = 6000


def split_subject(email_text: str) -> Tuple[str, str]:
    """Split an email into (subject, body). The subject is the first 'Subject:' line, if any."""
    lines = (email_text or "").strip().splitlines()
    for i, line in enumerate(lines[:3]):
        match = _SUBJECT_RE.match(line)
        if match:
            body = "\n".join(lines[:i] + lines[i + 1:]).strip()
            return match.group(1).strip(), body
    return "", (email_text or "").strip()


def replace_subject(email_text: str, new_subject: str) -> str:
    """Return the email with its subject line replaced (or added at the top)."""
    _, body = split_subject(email_text)
    return f"Subject: {new_subject.strip()}\n\n{body}"


def compose_links(subject: str, body: str) -> Dict[str, str]:
    """Links that open a new message, pre-filled, in Gmail, Outlook on the web, or the default mail app."""
    body = body[:MAX_LINK_BODY_CHARS]
    s, b = quote(subject, safe=""), quote(body.replace("\n", "\r\n"), safe="")
    return {
        "gmail": f"https://mail.google.com/mail/?view=cm&fs=1&su={s}&body={b}",
        "outlook": f"https://outlook.office.com/mail/deeplink/compose?subject={s}&body={b}",
        "mailto": f"mailto:?subject={s}&body={b}",
    }


_feedback_lock = threading.Lock()


def record_feedback(path: str, entry: dict) -> None:
    """
    Append one feedback entry as a JSON line and echo it to the server log.
    Only settings and the rating are recorded, never the email text.
    """
    row = {"ts": int(time.time()), **entry}
    line = json.dumps(row, ensure_ascii=False)
    print(f"FEEDBACK {line}", flush=True)
    try:
        with _feedback_lock, open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass  # feedback must never break the app
