from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import agentstore, llm, logstore, skillstore
from .config import CONSULTANT_NAME, UI_DIR, WORKLOG_FILE
from .models import (
    Agent,
    AgentCreate,
    AgentUpdate,
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
        "agents": len(agentstore.list_agents()),
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
    return skillstore.create_skill(req.name, req.description, req.triggers, req.instructions,
                                   req.script_name, req.script_content)


@app.post("/api/skills/import", response_model=Skill)
def import_skill(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file")
    try:
        return skillstore.import_upload(file.filename, file.file.read())
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Import failed: {err}")


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


@app.post("/api/skills/{slug}/scripts", response_model=Skill)
def upload_script(slug: str, file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file")
    updated = skillstore.add_script(slug, file.filename, file.file.read())
    if updated is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return updated


@app.post("/api/skills/{slug}/run", response_model=ChatResponse)
def run_skill(slug: str, req: SkillRunRequest) -> ChatResponse:
    skill = skillstore.get_skill(slug)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return _execute_skill(skill, req.message, agentstore.default_agent())


# ------------------------------------------------------------------ agents ----

@app.get("/api/agents", response_model=list[Agent])
def get_agents() -> list[dict]:
    return agentstore.list_agents()


@app.post("/api/agents", response_model=Agent)
def create_agent(req: AgentCreate) -> dict:
    return agentstore.create_agent(req.name, req.description, req.model, req.skills,
                                   req.entry_points, req.body)


@app.post("/api/agents/import", response_model=Agent)
def import_agent(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file")
    try:
        return agentstore.import_upload(file.filename, file.file.read())
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Import failed: {err}")


@app.put("/api/agents/{slug}", response_model=Agent)
def edit_agent(slug: str, req: AgentUpdate) -> dict:
    updated = agentstore.update_agent(slug, req.name, req.description, req.model,
                                       req.skills, req.entry_points, req.body)
    if updated is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return updated


@app.delete("/api/agents/{slug}", response_model=DeleteResponse)
def remove_agent(slug: str) -> DeleteResponse:
    outcome = agentstore.delete_agent(slug)
    if outcome == "builtin":
        raise HTTPException(status_code=409, detail="The default agent cannot be deleted.")
    if outcome == "missing":
        raise HTTPException(status_code=404, detail="Agent not found")
    return DeleteResponse(ok=True, deleted=1)


# ------------------------------------------------------------ skill runner ----

def _execute_skill(skill: dict, message: str, agent: dict | None) -> ChatResponse:
    slug = skill["slug"]
    persona = agent["body"] if agent else None
    meta = {"agent": agent["slug"], "agent_name": agent["name"]} if agent else {}

    if slug == "log-today":
        reply = (
            "Sure — let's log your day.\n\n"
            "**What did you work on today?** Describe the tasks, who was involved, and any "
            "impact or results. Reply in your next message and I'll save it to your log."
        )
        return ChatResponse(reply=reply, intent="skill", skill=slug, skills_used=[slug], **meta)

    if slug == "summarize-placement":
        rng = llm.explicit_range(message) or "all"
        entries = logstore.query(rng)
        reply = llm.summarize(entries, RANGE_LABELS.get(rng, rng), persona)
        return ChatResponse(reply=reply, intent="summary", skill=slug, range=rng,
                            skills_used=[slug], **meta)

    recent = logstore.query("all")[-20:]
    context = "\n".join(f"- {e['date']}: {e['text']}" for e in recent)
    reply = llm.run_skill(skill, message, context, persona)
    return ChatResponse(reply=reply, intent="skill", skill=slug, skills_used=[slug], **meta)


# -------------------------------------------------------------------- chat ----

@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    agent = agentstore.select_agent(req.message, req.agent)
    all_skills = {s["slug"]: s for s in skillstore.list_skills()}
    agent_skills = [all_skills[s] for s in agent["skills"] if s in all_skills]

    result = llm.classify(req.message, agent_skills, agent["body"])
    skill_slug = req.skill or result.get("skill")
    if skill_slug and skill_slug in all_skills:
        return _execute_skill(all_skills[skill_slug], req.message, agent)

    meta = {"agent": agent["slug"], "agent_name": agent["name"]}
    intent = result["intent"]

    if intent == "log":
        text = result["text"] or req.message
        entry = logstore.add_entry(text, result.get("date") or None)
        used = ["log-today"] if "log-today" in agent["skills"] else []
        reply = (f"Logged your work for **{entry['date']}**:\n\n> {entry['text']}\n\n"
                 "Anything else for today, or want a summary?")
        return ChatResponse(reply=reply, intent="log", skills_used=used,
                            entries_logged=1, entry_ids=[entry["id"]], **meta)

    if intent == "summary":
        rng = result["range"] or "all"
        ref = logstore.parse_date(result.get("date"))
        entries = logstore.query(rng, ref)
        reply = llm.summarize(entries, RANGE_LABELS.get(rng, rng), agent["body"])
        used = ["summarize-placement"] if "summarize-placement" in agent["skills"] else []
        return ChatResponse(reply=reply, intent="summary", range=rng, skills_used=used, **meta)

    skill_list = ", ".join(agent["skills"]) or "none"
    reply = (
        f"Hi! I'm **{agent['name']}**, your work-log assistant for **{CONSULTANT_NAME}**.\n\n"
        f"Here's what I can do:\n"
        "- **Log work** — e.g. *\"Today I facilitated a workshop with 15 staff.\"*\n"
        "- **Summarise impact** — ask for a *daily*, *weekly*, *monthly*, or "
        "*entire-placement* summary.\n"
        "- **Skills** — open the **Skills** tab to run or add capability packages.\n"
        "- **Agents** — open the **Agents** tab to customise entry points and personas.\n\n"
        f"This agent can use these skills: *{skill_list}*. "
        "Everything runs locally on your machine."
    )
    return ChatResponse(reply=reply, intent="other", **meta)
