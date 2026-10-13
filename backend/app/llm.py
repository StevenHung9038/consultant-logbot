import json
import time
from datetime import date

from .config import LLM_MODEL, OLLAMA_BASE_URL

VALID_INTENTS = ("log", "summary", "other")
VALID_RANGES = ("daily", "weekly", "monthly", "all")

CLASSIFY_SYSTEM = (
    "You are the router for a consultant work-log assistant.\n"
    "Classify the user's message into JSON with exactly these keys:\n"
    '  "intent": "log" | "summary" | "other",\n'
    '  "skill": "" or a skill slug from the list below,\n'
    '  "range": "daily" | "weekly" | "monthly" | "all" | "",\n'
    '  "date": "YYYY-MM-DD" or "",\n'
    '  "text": "..."\n'
    "Rules:\n"
    '- "log" = the user is REPORTING work they did that should be saved.\n'
    '- "summary" = the user wants a recap/summary of logged work.\n'
    '- "other" = greetings, questions about the bot, or anything else.\n'
    '- "skill" = set it ONLY when the user explicitly asks to run/use a named skill.\n'
    '- "range" is only set for summaries: daily=today, weekly=this week, '
    'monthly=this month, all=entire placement. Otherwise "" .\n'
    '- "date" = a specific day the user mentions (YYYY-MM-DD), else "".\n'
    '- "text" = when intent is "log", the cleaned, first-person work description; '
    'otherwise "".\n'
    "Today is {today}.\n"
    "Available skills:\n{skills}"
)

SUMMARY_SYSTEM = (
    "You are a placement/consulting performance analyst. You receive a consultant's "
    "work-log entries for one period. Write a concise, professional summary focused on "
    "IMPACT and outcomes, using short markdown bullet sections:\n"
    "## Highlights\n## Impact\n## Skills & Growth\n"
    "Only use facts present in the entries. Never invent details. "
    "If the log is empty, state that no work was logged for the period."
)


def _client():
    import ollama

    return ollama.Client(host=OLLAMA_BASE_URL)


def chat(system_prompt: str, user_prompt: str, fmt: str | None = None,
         temperature: float = 0.2, max_retries: int = 3) -> str:
    client = _client()
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            kwargs = {}
            if fmt == "json":
                kwargs["format"] = "json"
            resp = client.chat(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                options={"temperature": temperature},
                **kwargs,
            )
            return resp["message"]["content"].strip()
        except Exception as err:
            last_err = err
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Ollama LLM request failed after {max_retries} attempts: {last_err}")


def explicit_range(message: str) -> str | None:
    low = message.lower()
    if any(k in low for k in ("daily", "today", "this day", "my day", "the day")):
        return "daily"
    if any(k in low for k in ("weekly", "this week")):
        return "weekly"
    if any(k in low for k in ("monthly", "this month")):
        return "monthly"
    if any(k in low for k in ("entire placement", "whole placement", "full placement",
                              "overall", "so far", "all my work", "placement")):
        return "all"
    return None


def _looks_like_summary(message: str) -> bool:
    low = message.lower()
    return any(w in low for w in ("summar", "recap", "what did i do", "report on", "overview"))


def _fallback_classify(message: str) -> dict:
    if _looks_like_summary(message):
        return {"intent": "summary", "skill": "", "range": explicit_range(message) or "all",
                "date": "", "text": ""}
    return {"intent": "other", "skill": "", "range": "", "date": "", "text": ""}


def classify(message: str, skills: list[dict] | None = None, persona: str | None = None) -> dict:
    today = date.today().isoformat()
    skills = skills or []
    menu = "\n".join(f"- {s['slug']}: {s.get('description', '')}".rstrip() for s in skills) or "(none)"
    system = CLASSIFY_SYSTEM.replace("{today}", today).replace("{skills}", menu)
    if persona:
        system = persona.strip() + "\n\n" + system
    valid_slugs = {s["slug"] for s in skills}
    try:
        raw = chat(system, message, fmt="json", temperature=0.0)
        data = json.loads(raw)
    except Exception:
        return _fallback_classify(message)

    if not isinstance(data, dict):
        return _fallback_classify(message)

    intent = str(data.get("intent", "")).strip().lower()
    if intent not in VALID_INTENTS:
        intent = "other"
    rng = str(data.get("range", "")).strip().lower()
    if rng not in VALID_RANGES:
        rng = ""
    dt = str(data.get("date", "")).strip()
    text = str(data.get("text", "")).strip()
    skill = str(data.get("skill", "")).strip().lower()
    if skill not in valid_slugs:
        skill = ""

    # Deterministic guard: clear summary wording always wins over a 3B model's guess.
    if _looks_like_summary(message):
        intent = "summary"
    if intent == "summary":
        rng = explicit_range(message) or rng or "all"
    return {"intent": intent, "skill": skill, "range": rng, "date": dt, "text": text}


def summarize(entries: list[dict], range_label: str, persona: str | None = None) -> str:
    if not entries:
        return (f"No work has been logged for the **{range_label}** period yet. "
                "Tell me what you worked on and I'll save it to your log.")
    blocks = []
    for e in entries:
        block = f"- {e['date']}: {e['text']}"
        if e.get("tags"):
            block += f"  (tags: {', '.join(e['tags'])})"
        blocks.append(block)

    system_prompt = SUMMARY_SYSTEM
    if persona:
        system_prompt = persona.strip() + "\n\n" + SUMMARY_SYSTEM

    user_prompt = (
        f"Period: {range_label}\n"
        f"Number of entries: {len(entries)}\n\n"
        "Entries:\n" + "\n".join(blocks) +
        "\n\nWrite the impact-focused summary now."
    )
    return chat(system_prompt, user_prompt, temperature=0.3)


def run_skill(skill: dict, user_message: str, worklog_context: str = "",
              persona: str | None = None) -> str:
    """Execute a skill by injecting its instructions (and agent persona) into the LLM."""
    system_prompt = (
        f"You are executing the agent skill '{skill['name']}'.\n"
        f"Skill description: {skill.get('description', '')}\n\n"
        "Follow the skill instructions below exactly. Stay focused on the task and the "
        "consultant's work log. Never invent facts.\n\n"
        "=== SKILL INSTRUCTIONS ===\n"
        f"{skill.get('instructions', '').strip()}\n"
        "=== END SKILL INSTRUCTIONS ==="
    )
    if persona:
        system_prompt = persona.strip() + "\n\n" + system_prompt
    if skill.get("scripts"):
        system_prompt += ("\n\nThis skill ships helper scripts: "
                          + ", ".join(skill["scripts"]) + ".")
    if worklog_context:
        system_prompt += "\n\nRelevant work-log context:\n" + worklog_context
    return chat(system_prompt, user_message or "Carry out this skill now.", temperature=0.3)
