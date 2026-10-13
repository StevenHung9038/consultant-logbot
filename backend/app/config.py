import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
WORKLOG_FILE = DATA_DIR / "worklog.json"
SKILLS_DIR = DATA_DIR / "skills"
UI_DIR = BASE_DIR / "ui"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")
CONSULTANT_NAME = os.getenv("CONSULTANT_NAME", "Consultant")
