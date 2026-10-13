from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import llm, logstore, skillstore
from .config import CONSULTANT_NAME, UI_DIR, WORKLOG_FILE
from .models import (
    ChatRequest,
    ChatResponse,
    DeleteResponse,
    Entry,
    LogRequest,
    LogUpdate,
    Skill,
    SkillCreate,
    SkillRunRequest,
    SkillUpdate,
)

app = FastAPI(title="Consultant Work-Log Bot")

UI_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(UI_DIR)), name="static")

RANGE_LABELS = {
    "daily": "daily (today)",
    "weekly": "weekly (this week)",
    "monthly": "monthly (this month)",
    "all": "entire placement",
}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(UI_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    import ollama

    client = ollama.Client(host=llm.OLLAMA_BASE_URL)
    try:
        tags = client.list().get("models", [])
        names = [m.get("model") or m.get("name") for m in tags]
        return {"ok": True, "model": llm.LLM_MODEL, "available": names}
    except Exception as err:
        return {"ok": False, "model": llm.LLM_MODEL, "error": str(err)}


# ---------------------------------------------------------------- work log ----

@app.get("/api/entries", response_model=list[Entry])
def entries(range: str = "all", q: str | None = None) -> list[dict]:
    if range not in logstore.RANGES:
        range = "all"
    return logstore.query(range, q=q)


@app.get("/api/stats")
def stats() -> dict:
    all_items = logstore.all_entries()
    days = {e["date"] for e in all_items}
    return {
        "total": len(all_items),
        "days": len(days),
        "skills": len(skillstore.list_skills()),
        "file": str(WORKLOG_FILE),
    }


@app.post("/api/log", response_model=ChatResponse)
def log(req: LogRequest) -> ChatResponse:
    entry = logstore.add_entry(req.text, req.date, req.consultant, req.tags)
    reply = (f"Saved to your log for **{entry['date']}**:\n\n> {entry['text']}\n\n"
             "Ask me for a daily, weekly, monthly, or full-placement summary anytime.")
    return ChatResponse(reply=reply, intent="log", entries_logged=1, entry_ids=[entry["id"]])


@app.put("/api/entries/{entry_id}", response_model=Entry)
def update_entry(entry_id: str, req: LogUpdate) -> dict:
    updated = logstore.update_entry(entry_id, req.text, req.date, req.tags)
    if updated is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return updated


@app.delete("/api/entries/{entry_id}", response_model=DeleteResponse)
def delete_entry(entry_id: str) -> DeleteResponse:
    ok = logstore.delete_entry(entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Entry not found")
    return DeleteResponse(ok=True, deleted=1)


# ------------------------------------------------------------------ skills ----

@app.get("/api/skills", response_model=list[Skill])
def get_skills() -> list[dict]:
    return skillstore.list_skills()


@app.post("/api/skills", response_model=Skill)
def create_skill(req: SkillCreate) -> dict:
    return skillstore.create_skill(
        req.name, req.description, req.triggers, req.instructions,
        req.script_name, req.script_content,
    )


@app.put("/api/skills/{slug}", response_model=Skill)
def edit_skill(slug: str, req: SkillUpdate) -> dict:
    updated = skillstore.update_skill(slug, req.name, req.description, req.triggers, req.instructions)
    if updated is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return updated


@app.delete("/api/skills/{slug}", response_model=DeleteResponse)
def remove_skill(slug: str) -> DeleteResponse:
    outcome = skillstore.delete_skill(slug)
    if outcome == "builtin":
        raise HTTPException(status_code=409, detail="Built-in skills cannot be deleted.")
    if outcome == "missing":
        raise HTTPException(status_code=404, detail="Skill not found")
    return DeleteResponse(ok=True, deleted=1)


@app.post("/api/skills/{slug}/run", response_model=ChatResponse)
def run_skill(slug: str, req: SkillRunRequest) -> ChatResponse:
    skill = skillstore.get_skill(slug)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return _execute_skill(skill, req.message)


# ------------------------------------------------------------ skill runner ----

def _execute_skill(skill: dict, message: str) -> ChatResponse:
    slug = skill["slug"]

    if slug == "log-today":
        reply = (
            "Sure — let's log your day.\n\n"
            "**What did you work on today?** Describe the tasks, who was involved, and any "
            "impact or results. Reply in your next message and I'll save it to your log."
        )
        return ChatResponse(reply=reply, intent="skill", skill=slug)

    if slug == "summarize-placement":
        rng = llm.explicit_range(message) or "all"
        entries = logstore.query(rng)
        reply = llm.summarize(entries, RANGE_LABELS.get(rng, rng))
        return ChatResponse(reply=reply, intent="summary", skill=slug, range=rng)

    recent = logstore.query("all")[-20:]
    context = "\n".join(f"- {e['date']}: {e['text']}" for e in recent)
    reply = llm.run_skill(skill, message, context)
    return ChatResponse(reply=reply, intent="skill", skill=slug)


# -------------------------------------------------------------------- chat ----

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    skills = skillstore.list_skills()
    result = llm.classify(req.message, skills)

    skill_slug = req.skill or result.get("skill")
    if skill_slug:
        skill = skillstore.get_skill(skill_slug)
        if skill:
            return _execute_skill(skill, req.message)

    intent = result["intent"]

    if intent == "log":
        text = result["text"] or req.message
        entry = logstore.add_entry(text, result.get("date") or None)
        reply = (f"Logged your work for **{entry['date']}**:\n\n> {entry['text']}\n\n"
                 "Anything else for today, or want a summary?")
        return ChatResponse(reply=reply, intent="log", entries_logged=1, entry_ids=[entry["id"]])

    if intent == "summary":
        rng = result["range"] or "all"
        ref = logstore.parse_date(result.get("date"))
        entries = logstore.query(rng, ref)
        reply = llm.summarize(entries, RANGE_LABELS.get(rng, rng))
        return ChatResponse(reply=reply, intent="summary", range=rng)

    reply = (
        f"Hi! I'm your work-log assistant for **{CONSULTANT_NAME}**.\n\n"
        "Here's what I can do:\n"
        "- **Log work** — e.g. *\"Today I facilitated a workshop with 15 staff and drafted "
        "the data migration plan.\"*\n"
        "- **Summarise impact** — ask for a *daily*, *weekly*, *monthly*, or "
        "*entire-placement* summary.\n"
        "- **Skills** — open the **Skills** tab to run built-in skills or add your own "
        "capability packages.\n\n"
        "Everything is saved locally and summarised by your local LLM, so nothing leaves this machine."
    )
    return ChatResponse(reply=reply, intent="other")
