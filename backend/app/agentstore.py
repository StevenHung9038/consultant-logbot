"""Agents stored as portable, open-format packages.

Each agent is a directory under ``data/agents/<slug>/`` containing an
``AGENT.md`` file: frontmatter (name, description, model, skills, entry_points,
builtin) plus a markdown body that acts as the agent's system prompt / persona.

Entry points are the keywords that route a chat message to the agent.
"""

import io
import re
import shutil
import threading
import zipfile
from pathlib import Path

from .config import AGENTS_DIR, LLM_MODEL

_lock = threading.Lock()

DEFAULT_AGENT = "worklog-assistant"

BUILTIN_AGENTS = {
    DEFAULT_AGENT: {
        "name": "Work-Log Assistant",
        "description": "Default agent: records the consultant's daily work and produces impact summaries.",
        "model": LLM_MODEL,
        "skills": ["log-today", "summarize-placement"],
        "entry_points": ["log", "summary", "work", "today", "help"],
        "builtin": True,
        "body": (
            "You are a professional work-log assistant for a consultant on placement.\n"
            "Help the user record the work they did and turn it into impact-focused summaries.\n"
            "Be concise, accurate and encouraging. Never invent facts that are not in the work log."
        ),
    },
}

# Seeded once when the agents directory is first created; freely editable/deletable.
DEMO_AGENTS = {
    "client-reporter": {
        "name": "Client Reporter",
        "description": "Turns the work log into polished, client-facing status updates.",
        "model": LLM_MODEL,
        "skills": ["summarize-placement"],
        "entry_points": ["client report", "status update", "report"],
        "builtin": False,
        "body": (
            "You are a client-facing reporting assistant. Transform the consultant's work log\n"
            "into clear, professional status updates for clients. Avoid internal jargon and\n"
            "focus on outcomes, progress, risks and next steps."
        ),
    },
}


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return slug or "agent"


def _parse(text: str) -> tuple[dict, str]:
    meta: dict[str, str] = {}
    body = text
    if text.lstrip().startswith("---"):
        stripped = text.lstrip()
        end = stripped.find("\n---", 3)
        if end != -1:
            fm = stripped[3:end]
            body = stripped[end + 4:].lstrip("\n")
            for line in fm.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip().lower()] = val.strip()
    return meta, body


def _serialize(agent: dict) -> str:
    return (
        "---\n"
        f"name: {agent['name']}\n"
        f"description: {agent['description']}\n"
        f"model: {agent['model']}\n"
        f"skills: {', '.join(agent['skills'])}\n"
        f"entry_points: {', '.join(agent['entry_points'])}\n"
        f"builtin: {'true' if agent['builtin'] else 'false'}\n"
        "---\n\n"
        f"{agent['body'].strip()}\n"
    )


def _write(slug: str, agent: dict) -> None:
    d = AGENTS_DIR / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "AGENT.md").write_text(_serialize(agent), encoding="utf-8")


def _read(slug: str) -> dict | None:
    md = AGENTS_DIR / slug / "AGENT.md"
    if not md.is_file():
        return None
    meta, body = _parse(md.read_text(encoding="utf-8"))
    skills = [s.strip() for s in meta.get("skills", "").split(",") if s.strip()]
    entries = [e.strip() for e in meta.get("entry_points", "").split(",") if e.strip()]
    builtin = meta.get("builtin", "false").strip().lower() == "true" or slug == DEFAULT_AGENT
    return {
        "slug": slug,
        "name": meta.get("name") or slug,
        "description": meta.get("description", ""),
        "model": meta.get("model") or LLM_MODEL,
        "skills": skills,
        "entry_points": entries,
        "builtin": builtin,
        "body": body.strip(),
        "path": str(AGENTS_DIR / slug),
    }


def _ensure() -> None:
    first_time = not AGENTS_DIR.exists()
    AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    # The default agent always exists (recreated if removed).
    default_path = AGENTS_DIR / DEFAULT_AGENT / "AGENT.md"
    if not default_path.exists():
        _write(DEFAULT_AGENT, dict(BUILTIN_AGENTS[DEFAULT_AGENT], slug=DEFAULT_AGENT))
    if first_time:
        for slug, spec in DEMO_AGENTS.items():
            if not (AGENTS_DIR / slug / "AGENT.md").exists():
                _write(slug, dict(spec, slug=slug))


def list_agents() -> list[dict]:
    with _lock:
        _ensure()
        agents = [_read(p.name) for p in AGENTS_DIR.iterdir() if p.is_dir()]
    return sorted([a for a in agents if a], key=lambda a: (not a["builtin"], a["name"].lower()))


def get_agent(slug: str) -> dict | None:
    with _lock:
        _ensure()
        return _read(slug)


def default_agent() -> dict:
    return get_agent(DEFAULT_AGENT)


def create_agent(name: str, description: str = "", model: str = "", skills: list[str] | None = None,
                 entry_points: list[str] | None = None, body: str = "") -> dict:
    slug = _slugify(name)
    with _lock:
        _ensure()
        base, i = slug, 2
        while (AGENTS_DIR / slug).exists():
            slug = f"{base}-{i}"
            i += 1
        agent = {
            "name": name.strip(),
            "description": description.strip(),
            "model": (model or LLM_MODEL).strip(),
            "skills": skills or [],
            "entry_points": entry_points or [],
            "builtin": False,
            "body": body or f"You are {name.strip()}.",
        }
        _write(slug, agent)
        return _read(slug)


def update_agent(slug: str, name: str | None = None, description: str | None = None,
                 model: str | None = None, skills: list[str] | None = None,
                 entry_points: list[str] | None = None, body: str | None = None) -> dict | None:
    with _lock:
        current = _read(slug)
        if current is None:
            return None
        merged = {
            "name": (name or current["name"]).strip(),
            "description": description if description is not None else current["description"],
            "model": (model or current["model"]).strip(),
            "skills": skills if skills is not None else current["skills"],
            "entry_points": entry_points if entry_points is not None else current["entry_points"],
            "builtin": current["builtin"],
            "body": body if body is not None else current["body"],
        }
        _write(slug, merged)
        return _read(slug)


def delete_agent(slug: str) -> str:
    with _lock:
        if slug == DEFAULT_AGENT:
            return "builtin"
        d = AGENTS_DIR / slug
        if not (d / "AGENT.md").is_file():
            return "missing"
        shutil.rmtree(d)
        return "deleted"


def import_upload(filename: str, content: bytes) -> dict:
    """Import an AGENT.md (or a .zip containing one). Returns the created agent."""
    if filename.lower().endswith(".zip"):
        text = _extract_md_from_zip(content, "AGENT.md")
    else:
        text = content.decode("utf-8", errors="replace")
    meta, body = _parse(text)
    name = meta.get("name") or Path(filename).stem
    skills = [s.strip() for s in meta.get("skills", "").split(",") if s.strip()]
    entries = [e.strip() for e in meta.get("entry_points", "").split(",") if e.strip()]
    return create_agent(name, meta.get("description", ""), meta.get("model", ""),
                        skills, entries, body)


def _extract_md_from_zip(content: bytes, marker: str) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        names = [n for n in zf.namelist() if n.endswith(marker)]
        if not names:
            raise ValueError(f"No {marker} found in archive")
        names.sort(key=len)
        return zf.read(names[0]).decode("utf-8", errors="replace")


def select_agent(message: str, requested: str | None = None) -> dict:
    """Pick the agent for a message: explicit slug > longest entry-point match > default."""
    with _lock:
        _ensure()
        if requested:
            chosen = _read(requested)
            if chosen:
                return chosen
        low = (message or "").lower()
        best, best_len = None, 0
        for p in AGENTS_DIR.iterdir() if AGENTS_DIR.exists() else []:
            if not p.is_dir():
                continue
            agent = _read(p.name)
            if not agent:
                continue
            for kw in agent["entry_points"]:
                if kw and kw.lower() in low and len(kw) > best_len:
                    best, best_len = agent, len(kw)
        return best or _read(DEFAULT_AGENT)
