from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    skill: str | None = Field(default=None, max_length=120)
    agent: str | None = Field(default=None, max_length=120)


class LogRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    date: str | None = None
    consultant: str | None = None
    tags: list[str] = Field(default_factory=list)


class Entry(BaseModel):
    id: str
    date: str
    created_at: str
    consultant: str
    text: str
    tags: list[str] = Field(default_factory=list)


class LogUpdate(BaseModel):
    text: str | None = Field(default=None, max_length=4000)
    date: str | None = None
    tags: list[str] | None = None


class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    triggers: list[str] = Field(default_factory=list)
    instructions: str = Field(default="", max_length=8000)
    script_name: str | None = Field(default=None, max_length=100)
    script_content: str | None = Field(default=None, max_length=20000)


class SkillUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    triggers: list[str] | None = None
    instructions: str | None = Field(default=None, max_length=8000)


class Skill(BaseModel):
    slug: str
    name: str
    description: str = ""
    triggers: list[str] = Field(default_factory=list)
    builtin: bool = False
    instructions: str = ""
    scripts: list[str] = Field(default_factory=list)
    path: str = ""


class SkillRunRequest(BaseModel):
    message: str = Field(default="", max_length=4000)


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    model: str = Field(default="", max_length=80)
    skills: list[str] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)
    body: str = Field(default="", max_length=8000)


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=80)
    skills: list[str] | None = None
    entry_points: list[str] | None = None
    body: str | None = Field(default=None, max_length=8000)


class Agent(BaseModel):
    slug: str
    name: str
    description: str = ""
    model: str = ""
    skills: list[str] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)
    builtin: bool = False
    body: str = ""
    path: str = ""


class DeleteResponse(BaseModel):
    ok: bool
    deleted: int = 0


class ChatResponse(BaseModel):
    reply: str
    intent: str
    skill: str | None = None
    agent: str | None = None
    agent_name: str | None = None
    skills_used: list[str] = Field(default_factory=list)
    range: str | None = None
    entries_logged: int = 0
    entry_ids: list[str] = Field(default_factory=list)
