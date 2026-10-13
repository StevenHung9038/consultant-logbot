# Consultant Work-Log Bot

A 100% local chatbot that records a consultant's day-to-day work and turns it into
**impact-focused summaries** on demand (daily, weekly, monthly, or the entire placement).
It runs entirely on your machine using a local LLM — no cloud, no API keys, no data leaving
the computer.

It also ships an **agent-skills** system: portable, open-format capability packages
(`SKILL.md` + optional scripts) that extend what the assistant can do, and which you can add,
edit, or delete yourself.

---

## Features

- **Log your day** — describe your work in chat (e.g. *"Today I ran a UAT session and wrote the test report."*); it is saved locally with the date.
- **Delete / edit mis-typed logs** — fix or remove any entry from the History tab.
- **Full history** — browse, search, and filter every past entry (all time / today / this week / this month).
- **Summaries** — ask for a **daily**, **weekly**, **monthly**, or **entire-placement** summary and get a structured, impact-focused write-up (Highlights / Impact / Skills & Growth).
- **Agent skills** — built-in skills drive the core workflows; add your own capability packages with instructions and scripts, then run them from chat.
- **Local LLM** — powered by [Ollama](https://ollama.com) (`llama3.2:3b` by default). Private and free.

---

## How it works

```
                       ┌────────────────────────────────────────────┐
   Browser (UI)        │  Chat · History · Skills  (single HTML page) │
        │              └────────────────────────────────────────────┘
        ▼                              │  HTTP/JSON
   FastAPI backend ────────────────────┤
        │                              │
        │  intent routing              │  data (local files)
        ├── log    ────────────────────┼──▶  data/worklog.json      (work-log entries)
        ├── summary ──────────────────┼──▶  data/skills/<slug>/SKILL.md (+ scripts/)
        └── skill  ───────────────────┘
        │
        ▼
   Ollama  ──  llama3.2:3b  (intent classification, summaries, skill execution)
```

- **Intent routing** — each chat message is classified by the local LLM as `log`, `summary`,
  or `other`, optionally invoking a skill. A deterministic keyword guard keeps
  daily/weekly/monthly/placement summarisation reliable on a small model.
- **Storage** — plain JSON/Markdown files on disk; human-readable and portable.
- **Summaries** — matching entries are selected by date window and passed to the LLM with an
  impact-focused prompt.

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
- **Custom skills** can be added, edited, and deleted. Optionally attach a script
  (`scripts/…`), which is stored and referenced by the skill.
- Click **Run** on any skill to execute it in chat.

---

## REST API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Web UI |
| `GET` | `/api/health` | LLM status |
| `GET` | `/api/entries?range=all\|daily\|weekly\|monthly&q=` | List / search log entries |
| `GET` | `/api/stats` | Entry / day / skill counts |
| `POST` | `/api/log` | Add an entry (`{text, date?, consultant?, tags?}`) |
| `PUT` | `/api/entries/{id}` | Update an entry |
| `DELETE` | `/api/entries/{id}` | Delete an entry |
| `GET` | `/api/skills` | List skills |
| `POST` | `/api/skills` | Create a skill |
| `PUT` | `/api/skills/{slug}` | Update a skill |
| `DELETE` | `/api/skills/{slug}` | Delete a skill (built-ins return `409`) |
| `POST` | `/api/skills/{slug}/run` | Run a skill |
| `POST` | `/api/chat` | Chat (`{message, skill?}`) |

Example:

```bash
curl -X POST localhost:8010/api/chat -H 'Content-Type: application/json' \
  -d '{"message":"Today I reviewed the data-quality checklist and fixed 3 issues."}'

curl -X POST localhost:8010/api/chat -H 'Content-Type: application/json' \
  -d '{"message":"Give me a monthly summary."}'
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
│       ├── llm.py         # Ollama client: routing, summaries, skill runner
│       └── main.py        # FastAPI app & endpoints
├── ui/
│   └── index.html         # single-page UI (Chat / History / Skills)
├── data/                  # created at runtime (git-ignored)
│   ├── worklog.json
│   └── skills/<slug>/SKILL.md
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
- Skills live in `data/skills/`.
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
