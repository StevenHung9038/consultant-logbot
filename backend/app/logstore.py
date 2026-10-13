import calendar
import json
import threading
import uuid
from datetime import date, datetime, timedelta

from .config import CONSULTANT_NAME, WORKLOG_FILE

_lock = threading.Lock()

RANGES = ("daily", "weekly", "monthly", "all")


def _ensure() -> None:
    WORKLOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not WORKLOG_FILE.exists():
        WORKLOG_FILE.write_text(json.dumps({"entries": []}, indent=2), encoding="utf-8")


def _load() -> list[dict]:
    _ensure()
    try:
        data = json.loads(WORKLOG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, list):
        return data
    return data.get("entries", [])


def _save(entries: list[dict]) -> None:
    entries = sorted(entries, key=lambda e: (e.get("date", ""), e.get("created_at", "")))
    tmp = WORKLOG_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"entries": entries}, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(WORKLOG_FILE)


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def add_entry(text: str, on_date: str | None = None, consultant: str | None = None,
              tags: list[str] | None = None) -> dict:
    day = parse_date(on_date) or date.today()
    now = datetime.now().replace(microsecond=0)
    entry = {
        "id": uuid.uuid4().hex[:12],
        "date": day.isoformat(),
        "created_at": now.isoformat(),
        "consultant": consultant or CONSULTANT_NAME,
        "text": text.strip(),
        "tags": tags or [],
    }
    with _lock:
        entries = _load()
        entries.append(entry)
        _save(entries)
    return entry


def all_entries() -> list[dict]:
    with _lock:
        return _load()


def get_entry(entry_id: str) -> dict | None:
    for e in _load():
        if e.get("id") == entry_id:
            return e
    return None


def delete_entry(entry_id: str) -> bool:
    with _lock:
        entries = _load()
        remaining = [e for e in entries if e.get("id") != entry_id]
        if len(remaining) == len(entries):
            return False
        _save(remaining)
    return True


def update_entry(entry_id: str, text: str | None = None, on_date: str | None = None,
                 tags: list[str] | None = None) -> dict | None:
    with _lock:
        entries = _load()
        target = None
        for e in entries:
            if e.get("id") == entry_id:
                target = e
                break
        if target is None:
            return None
        if text is not None:
            target["text"] = text.strip()
        if on_date:
            day = parse_date(on_date)
            if day:
                target["date"] = day.isoformat()
        if tags is not None:
            target["tags"] = tags
        _save(entries)
        return target


def range_bounds(range_key: str, ref: date | None = None) -> tuple[date | None, date | None]:
    ref = ref or date.today()
    if range_key == "daily":
        return ref, ref
    if range_key == "weekly":
        start = ref - timedelta(days=ref.weekday())
        return start, start + timedelta(days=6)
    if range_key == "monthly":
        start = ref.replace(day=1)
        last = calendar.monthrange(ref.year, ref.month)[1]
        return start, ref.replace(day=last)
    return None, None


def query(range_key: str, ref: date | None = None, q: str | None = None) -> list[dict]:
    start, end = range_bounds(range_key, ref)
    entries = _load()
    if start is not None and end is not None:
        entries = [e for e in entries if start.isoformat() <= e.get("date", "") <= end.isoformat()]
    if q:
        needle = q.strip().lower()
        entries = [e for e in entries if needle in e.get("text", "").lower()]
    return entries
