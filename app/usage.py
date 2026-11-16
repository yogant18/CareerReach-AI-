"""
Free-trial usage limits for the hosted app.

Visitors without their own Groq key get a small daily allowance on the
server key. Two limits apply:

* Per visitor: a rolling 24-hour window that starts at their first free use.
* All visitors combined: a cap per UTC calendar day, so a burst of traffic
  cannot exhaust the server's Groq quota.

Visitors are identified by a salted SHA-256 hash of their IP address, so no
raw IP is ever written to disk. Counts live in a small JSON file next to the
project; on hosts with ephemeral disks (e.g. Streamlit Community Cloud) they
reset when the app restarts, which only ever errs in the visitor's favour.
"""

import hashlib
import ipaddress
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

WINDOW_SECONDS = 24 * 60 * 60

# Kinds of free actions that are metered.
EMAIL = "emails"
CHAT = "chats"


def _int_setting(name: str, default: int, secrets=None) -> int:
    """Read an integer limit from Streamlit secrets or the environment."""
    raw = None
    try:
        if secrets is not None and name in secrets:
            raw = secrets[name]
    except Exception:
        raw = None
    if raw is None:
        raw = os.getenv(name)
    try:
        return max(0, int(raw)) if raw is not None else default
    except (TypeError, ValueError):
        return default


class UsageLimiter:
    def __init__(
        self,
        store_path: str,
        per_visitor: Dict[str, int],
        global_daily_cap: int,
        salt: str = "",
    ):
        self.store_path = store_path
        self.per_visitor = per_visitor
        self.global_daily_cap = global_daily_cap
        self.salt = salt
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------
    def _load(self) -> dict:
        try:
            with open(self.store_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                data.setdefault("visitors", {})
                data.setdefault("global", {})
                return data
        except (OSError, ValueError):
            pass
        return {"visitors": {}, "global": {}}

    def _save(self, data: dict) -> None:
        tmp = f"{self.store_path}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            os.replace(tmp, self.store_path)
        except OSError:
            # Failing to persist must never break the app.
            pass

    def _prune(self, data: dict, now: float) -> None:
        """Drop expired visitor windows and past global days."""
        data["visitors"] = {
            vid: rec for vid, rec in data["visitors"].items()
            if now - rec.get("start", 0) < WINDOW_SECONDS
        }
        today = _utc_day(now)
        data["global"] = {k: v for k, v in data["global"].items() if k == today}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def visitor_id(self, raw_identifier: str) -> str:
        digest = hashlib.sha256(f"{self.salt}|{raw_identifier}".encode("utf-8"))
        return digest.hexdigest()[:32]

    def status(self, visitor: str, kind: str) -> dict:
        """Remaining allowance for a visitor, without consuming anything."""
        with self._lock:
            data = self._load()
            return self._status(data, visitor, kind, time.time())

    def consume(self, visitor: str, kind: str) -> dict:
        """
        Use one free action if allowed. Returns the status after the attempt,
        with ``allowed`` telling the caller whether to proceed.
        """
        with self._lock:
            now = time.time()
            data = self._load()
            self._prune(data, now)
            st = self._status(data, visitor, kind, now)
            if not st["allowed"]:
                return st

            rec = data["visitors"].get(visitor)
            if rec is None:
                rec = {"start": now, EMAIL: 0, CHAT: 0}
                data["visitors"][visitor] = rec
            rec[kind] = rec.get(kind, 0) + 1

            day = _utc_day(now)
            data["global"][day] = data["global"].get(day, 0) + 1
            self._save(data)
            return self._status(data, visitor, kind, now, just_used=True)

    # ------------------------------------------------------------------
    def _status(self, data: dict, visitor: str, kind: str, now: float, just_used: bool = False) -> dict:
        limit = self.per_visitor.get(kind, 0)
        rec = data["visitors"].get(visitor)
        if rec and now - rec.get("start", 0) < WINDOW_SECONDS:
            used = rec.get(kind, 0)
            reset_at: Optional[float] = rec["start"] + WINDOW_SECONDS
        else:
            used = 0
            reset_at = None

        global_used = data["global"].get(_utc_day(now), 0)
        global_full = self.global_daily_cap > 0 and global_used >= self.global_daily_cap
        remaining = max(0, limit - used)

        if just_used:
            allowed = True
            reason = None
        elif global_full:
            allowed, reason = False, "global"
        elif remaining <= 0:
            allowed, reason = False, "visitor"
        else:
            allowed, reason = True, None

        return {
            "allowed": allowed,
            "reason": reason,
            "limit": limit,
            "used": min(used, limit),
            "remaining": remaining,
            "reset_at": reset_at,
            "global_reset_at": _next_utc_midnight(now),
        }


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _utc_day(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def _next_utc_midnight(ts: float) -> float:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    midnight = (dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.timestamp()


def format_wait(reset_at: Optional[float]) -> str:
    """'5h 12m' style countdown until a timestamp."""
    if not reset_at:
        return "24h"
    secs = max(0, int(reset_at - time.time()))
    hours, rem = divmod(secs, 3600)
    minutes = rem // 60
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{max(minutes, 1)}m"


def format_reset_time(reset_at: Optional[float]) -> str:
    """Absolute reset time in UTC, e.g. '17 Nov, 14:05 UTC'."""
    if not reset_at:
        return "24 hours after your first free use"
    dt = datetime.fromtimestamp(reset_at, tz=timezone.utc)
    return dt.strftime("%d %b, %H:%M UTC")


def client_identifier(headers, ip_address: Optional[str], fallback: str) -> str:
    """
    Best-effort client IP. Prefers the right-most public address in
    X-Forwarded-For (the one added by the nearest trusted proxy, which a client
    cannot forge), then Streamlit's own view of the IP, then a per-session id.
    """
    xff = ""
    try:
        xff = headers.get("X-Forwarded-For", "") if headers else ""
    except Exception:
        xff = ""
    for part in reversed([p.strip() for p in str(xff).split(",") if p.strip()]):
        try:
            if ipaddress.ip_address(part).is_global:
                return part
        except ValueError:
            continue
    if isinstance(ip_address, str):
        try:
            return str(ipaddress.ip_address(ip_address.strip()))
        except ValueError:
            pass
    return f"session:{fallback}"
