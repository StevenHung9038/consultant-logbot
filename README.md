# Consultant Work-Log Bot

A 100% local chatbot that records a consultant's day-to-day work and turns it into
**impact-focused summaries** on demand (daily, weekly, monthly, or the entire placement).
It runs entirely on your machine using a local LLM — no cloud, no API keys, no data leaving
the computer.

It also ships an **agent-skills** system: portable, open-format **skills**
(`SKILL.md` + optional scripts) that extend what the assistant can do, and **agents**
(`AGENT.md`) that act as entry points with their own persona, entry-point keywords, model,
and skill set. Both can be created, imported, edited, or deleted yourself.

---

## Features

- **Log your day** — describe your work in chat (e.g. *"Today I ran a UAT session and wrote the test report."*); it is saved locally with the date.
- **Delete / edit mis-typed logs** — fix or remove any entry from the History tab.
- **Full history** — browse, search, and filter every past entry (all time / today / this week / this month).
- **Summaries** — ask for a **daily**, **weekly**, **monthly**, or **entire-placement** summary and get a structured, impact-focused write-up (Highlights / Impact / Skills & Growth).
- **Agent skills** — built-in skills drive the core workflows; add your own capability packages with instructions and scripts, then run them from chat.
- **Agents & entry points** — route messages to different personas via entry-point keywords, or pick one explicitly in chat. Each agent chooses its own skills and model.
- **Importable packages** — bring in an existing skill or agent as a single `SKILL.md` / `AGENT.md` file or a `.zip` bundle, and attach scripts.
- **Inline transparency** — every reply shows which agent handled it and which skills were used.
- **Local LLM** — powered by [Ollama](https://ollama.com) (`llama3.2:3b` by default). Private and free.

---

## How it works

```
                       ┌──────────────────────────────────────────────────┐
   Browser (UI)        │  Chat · History · Skills · Agents (single page)  │
        │              └──────────────────────────────────────────────────┘
        ▼                              │  HTTP/JSON
   FastAPI backend ────────────────────┤
        │                              │
        │  agent selection             │  data (local files)
        │  + intent routing            ├──▶  data/worklog.json             (work-log entries)
        ├── agent   ─ (entry points) ──┼──▶  data/skills/<slug>/SKILL.md  (+ scripts/)
        ├── log     ───────────────────┼──▶  data/agents/<slug>/AGENT.md  (persona + entry points)
        ├── summary ───────────────────┘
        └── skill
        │
        ▼
   Ollama  ──  llama3.2:3b  (intent classification, summaries, skill execution)
```

- **Agent selection** — an explicit agent (from the chat picker) wins; otherwise the message is
  matched against each agent's **entry points** (longest match), falling back to the default agent.
- **Intent routing** — each chat message is classified by the local LLM as `log`, `summary`,
  or `other`, optionally invoking a skill. A deterministic keyword guard keeps
  daily/weekly/monthly/placement summarisation reliable on a small model.
- **Storage** — plain JSON/Markdown files on disk; human-readable and portable.
- **Summaries** — matching entries are selected by date window and passed to the LLM with an
  impact-focused prompt, using the active agent's persona.

---

## Prerequisites

- **Python 3.12+**
- **Ollama** with the `llama3.2:3b` model (~2 GB):
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh   # standard install
  ollama pull llama3.2:3b
  ```
  No sudo? Extract the portable tarball to `~/ollama-dist/bin/ollama` and `run.sh` will find it.
- **RAM**: ~2 GB free for the model; the whole stack fits comfortably in 4 GB+.
- **uv** (optional) — `run.sh` installs it automatically if missing.

---

## Setup & run

```bash
git clone https://github.com/StevenHung9038/consultant-logbot.git
cd consultant-logbot
./run.sh
```

`run.sh` will:

1. Start the Ollama server if it isn't already running.
2. Pull `llama3.2:3b` if missing.
3. Create a Python virtual environment (`.venv`) and install dependencies.
4. Serve the app at **http://localhost:8010**.

Change the port with `PORT=9000 ./run.sh`.

---

## Usage

### Chat tab
Type what you did and it's logged. Ask questions like:
- *"Today I facilitated a workshop with 15 staff and drafted the data-migration plan."* → saved to your log.
- *"Give me a weekly summary of my work this week."* → impact summary.
- *"Summarise the impact of my entire placement."*

Use the sidebar for one-click **Daily / Weekly / Monthly / Full placement** summaries and **Log my day**.

Each reply is tagged with the **agent** that handled it and the **skills** it used, so you can
see exactly what ran. Use the **Agent** picker in the chat header to force a specific agent, or
leave it on **Auto** to route by entry-point keywords.

### History tab
All entries grouped by date. **Search** the text and **filter** by time range. Each entry can be **edited** or **deleted**.

### Skills tab
Manage portable skill packages. Each skill is stored as `data/skills/<slug>/SKILL.md`:

```markdown
---
name: weekly-client-report
description: Draft a concise weekly client status report from the work log.
triggers: weekly report, client update
builtin: false
---

# Weekly Client Report
## Steps
1. Review the week's entries.
2. Write a short client-facing status: progress, risks, next steps.
```

- **Built-in skills** (seeded on first run, cannot be deleted):
  - `log-today` — asks you what you worked on today, then records it.
  - `summarize-placement` — daily / weekly / monthly / entire-placement summaries.
- **Custom skills** can be added, edited, and deleted.
- **Import** an existing package as a single `.md` file or a `.zip` bundle (the `.zip` may
  include a `scripts/` folder; nested top-level directories are handled automatically).
- Attach scripts with **＋ script**, which are stored under `scripts/…` and referenced by the skill.
- Click **Run** on any skill to execute it in chat.

### Agents tab
Manage entry-point agents. Each agent is stored as `data/agents/<slug>/AGENT.md`:

```markdown
---
name: Client Reporter
description: Impact-focused reporting assistant.
model: llama3.2:3b
entry_points: client report, status update
skills: summarize-placement
builtin: false
---

You are a polished reporting assistant. Always lead with measurable impact...
```

- **Entry points** are keywords that route a chat message to this agent automatically.
- **Skills** restricts the agent to a subset of installed skills.
- **Model** overrides the default LLM for this agent.
- The markdown body is the agent's **persona / system prompt**.
- **Built-in** `worklog-assistant` (default, cannot be deleted) plus a deletable demo
  `client-reporter`. **Import** an existing agent as `.md` or `.zip`.

---

## REST API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Web UI |
| `GET` | `/api/health` | LLM status |
| `GET` | `/api/entries?range=all\|daily\|weekly\|monthly&q=` | List / search log entries |
| `GET` | `/api/stats` | Entry / day / skill / agent counts |
| `POST` | `/api/log` | Add an entry (`{text, date?, consultant?, tags?}`) |
| `PUT` | `/api/entries/{id}` | Update an entry |
| `DELETE` | `/api/entries/{id}` | Delete an entry |
| `GET` | `/api/skills` | List skills |
| `POST` | `/api/skills` | Create a skill |
| `POST` | `/api/skills/import` | Import a skill (`.md` / `.zip`, multipart `file`) |
| `PUT` | `/api/skills/{slug}` | Update a skill |
| `DELETE` | `/api/skills/{slug}` | Delete a skill (built-ins return `409`) |
| `POST` | `/api/skills/{slug}/scripts` | Upload a script (multipart `file`) |
| `POST` | `/api/skills/{slug}/run` | Run a skill |
| `GET` | `/api/agents` | List agents |
| `POST` | `/api/agents` | Create an agent |
| `POST` | `/api/agents/import` | Import an agent (`.md` / `.zip`, multipart `file`) |
| `PUT` | `/api/agents/{slug}` | Update an agent |
| `DELETE` | `/api/agents/{slug}` | Delete an agent (default returns `409`) |
| `POST` | `/api/chat` | Chat (`{message, skill?, agent?}`) |

Example:

```bash
curl -X POST localhost:8010/api/chat -H 'Content-Type: application/json' \
  -d '{"message":"Today I reviewed the data-quality checklist and fixed 3 issues."}'

curl -X POST localhost:8010/api/chat -H 'Content-Type: application/json' \
  -d '{"message":"Give me a monthly summary."}'

curl -X POST localhost:8010/api/chat -H 'Content-Type: application/json' \
  -d '{"message":"hello","agent":"client-reporter"}'
```

---

## Project structure

```
consultant-logbot/
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── config.py      # paths & settings (env-overridable)
│       ├── models.py      # pydantic schemas
│       ├── logstore.py    # work-log JSON storage + date-range queries
│       ├── skillstore.py  # SKILL.md package storage (open format)
│       ├── agentstore.py  # AGENT.md packages + entry-point routing
│       ├── llm.py         # Ollama client: routing, summaries, skill runner
│       └── main.py        # FastAPI app & endpoints
├── ui/
│   └── index.html         # single-page UI (Chat / History / Skills / Agents)
├── data/                  # created at runtime (git-ignored)
│   ├── worklog.json
│   ├── skills/<slug>/SKILL.md
│   └── agents/<slug>/AGENT.md
├── run.sh                 # one-command bootstrap
└── README.md
```

---

## Configuration (environment variables)

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_MODEL` | `llama3.2:3b` | Ollama generation model |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `CONSULTANT_NAME` | `Consultant` | Name shown in the assistant greeting |
| `PORT` | `8010` | Web server port |
| `OLLAMA_MODELS` | `$HOME/ollama-models` | Where Ollama stores models |

---

## Data & privacy

- All work-log entries are stored locally in `data/worklog.json`.
- Skills live in `data/skills/`; agents live in `data/agents/`.
- Nothing is sent to any external service — inference is done by your local Ollama.
- `data/` is git-ignored, so your personal logs are never committed.

---

## Known limitations

- When Ollama is stopped, `/api/chat` returns HTTP 500 (the UI shows an error) rather than degrading gracefully.
- Weekly/monthly summaries cover the **current** calendar period only (no "last week/month" yet).
- Custom skill **scripts are stored and referenced but not executed** (by design, for safety).
- The first LLM call after start is slow due to model warm-up on CPU.

---

## License

Provided as-is for internal/demo use.
