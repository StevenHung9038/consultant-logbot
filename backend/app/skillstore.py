"""Agent skills stored as portable, open-format packages.

Each skill is a directory under ``data/skills/<slug>/`` containing a ``SKILL.md``
file (YAML-ish frontmatter + markdown instructions) and an optional ``scripts/``
folder. This mirrors the open agent-skill format used by tools like opencode.
"""

import re
import shutil
import threading
from datetime import datetime
from pathlib import Path

from .config import SKILLS_DIR

_lock = threading.Lock()

BUILTIN_SKILLS = {
    "log-today": {
        "name": "log-today",
        "description": "Ask the consultant what work they completed today, then record it to the local work log.",
        "triggers": ["log my work", "log today", "add a log", "record my day", "what should i log"],
        "instructions": (
            "# Log today's work\n\n"
            "## When to use\n"
            "When the user wants to record the work they did today (or a given day).\n\n"
            "## Instructions\n"
            "1. Greet the user and ask: \"What did you work on today?\"\n"
            "2. When they reply, capture their full description of the work and its impact.\n"
            "3. Save it to the local work log with today's date.\n"
            "4. Confirm what was saved and invite them to add more or request a summary."
        ),
    },
    "summarize-placement": {
        "name": "summarize-placement",
        "description": "Summarise the consultant's impact for a daily, weekly, monthly, or entire-placement period.",
        "triggers": ["summary", "summarise", "summarize", "recap", "report", "daily", "weekly",
                     "monthly", "entire placement"],
        "instructions": (
            "# Summarise placement impact\n\n"
            "## When to use\n"
            "When the user asks for a recap of logged work over a period.\n\n"
            "## Instructions\n"
            "1. Determine the period: daily (today), weekly (this week), monthly (this month), "
            "or entire placement (all entries).\n"
            "2. Query the local work log for entries inside that period.\n"
            "3. Write an impact-focused summary: Highlights, Impact, Skills & Growth.\n"
            "4. If no entries exist for the period, say so plainly."
        ),
    },
}

_BUILTIN_SLUGS = set(BUILTIN_SKILLS)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return slug or "skill"


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


def _serialize(name: str, description: str, triggers: list[str], builtin: bool,
               instructions: str) -> str:
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"triggers: {', '.join(triggers)}\n"
        f"builtin: {'true' if builtin else 'false'}\n"
        "---\n\n"
        f"{instructions.strip()}\n"
    )


def _write_skill(slug: str, name: str, description: str, triggers: list[str],
                 builtin: bool, instructions: str) -> None:
    skill_dir = SKILLS_DIR / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        _serialize(name, description, triggers, builtin, instructions), encoding="utf-8"
    )


def _seed_builtins() -> None:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    for slug, spec in BUILTIN_SKILLS.items():
        path = SKILLS_DIR / slug / "SKILL.md"
        if not path.exists():
            _write_skill(slug, spec["name"], spec["description"], spec["triggers"],
                         True, spec["instructions"])


def _read_skill(slug: str) -> dict | None:
    skill_dir = SKILLS_DIR / slug
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        return None
    meta, body = _parse(md.read_text(encoding="utf-8"))
    scripts_dir = skill_dir / "scripts"
    scripts = sorted(p.name for p in scripts_dir.glob("*") if p.is_file()) if scripts_dir.is_dir() else []
    triggers = [t.strip() for t in meta.get("triggers", "").split(",") if t.strip()]
    return {
        "slug": slug,
        "name": meta.get("name") or slug,
        "description": meta.get("description", ""),
        "triggers": triggers,
        "builtin": meta.get("builtin", "false").strip().lower() == "true" or slug in _BUILTIN_SLUGS,
        "instructions": body.strip(),
        "scripts": scripts,
        "path": str(skill_dir),
    }


def list_skills() -> list[dict]:
    with _lock:
        _seed_builtins()
        skills = []
        for entry in SKILLS_DIR.iterdir() if SKILLS_DIR.exists() else []:
            if entry.is_dir():
                skill = _read_skill(entry.name)
                if skill:
                    skills.append(skill)
    return sorted(skills, key=lambda s: (not s["builtin"], s["name"].lower()))


def get_skill(slug: str) -> dict | None:
    with _lock:
        _seed_builtins()
        return _read_skill(slug)


def create_skill(name: str, description: str = "", triggers: list[str] | None = None,
                 instructions: str = "", script_name: str | None = None,
                 script_content: str | None = None) -> dict:
    slug = _slugify(name)
    with _lock:
        _seed_builtins()
        base = slug
        i = 2
        while (SKILLS_DIR / slug).exists():
            slug = f"{base}-{i}"
            i += 1
        _write_skill(slug, name.strip(), description.strip(), triggers or [], False,
                     instructions or f"# {name.strip()}\n\nDescribe what this skill should do.")
        if script_name and script_content is not None:
            scripts_dir = SKILLS_DIR / slug / "scripts"
            scripts_dir.mkdir(exist_ok=True)
            safe = re.sub(r"[^A-Za-z0-9._-]", "_", script_name.strip()) or "script.sh"
            (scripts_dir / safe).write_text(script_content, encoding="utf-8")
        return _read_skill(slug)


def update_skill(slug: str, name: str | None = None, description: str | None = None,
                 triggers: list[str] | None = None, instructions: str | None = None) -> dict | None:
    with _lock:
        current = _read_skill(slug)
        if current is None:
            return None
        _write_skill(
            slug,
            (name or current["name"]).strip(),
            description if description is not None else current["description"],
            triggers if triggers is not None else current["triggers"],
            current["builtin"],
            instructions if instructions is not None else current["instructions"],
        )
        return _read_skill(slug)


def delete_skill(slug: str) -> str:
    """Returns 'deleted', 'builtin' (protected), or 'missing'."""
    with _lock:
        if slug in _BUILTIN_SLUGS:
            return "builtin"
        skill_dir = SKILLS_DIR / slug
        if not (skill_dir / "SKILL.md").is_file():
            return "missing"
        shutil.rmtree(skill_dir)
        return "deleted"
