# Brand DNA (style-ai-generator)

A design tool for the TU Delft IDE course "Generative AI and Design": a designer enters a brand,
reviews reference images found on the web, and locks the AI-extracted "Style DNA" traits into a
House Style Package. They then upload their own design and get per-trait similarity scores and
suggested design directions — the AI measures and suggests, the designer decides.

Working rules, the data contract and folder ownership are in [AGENTS.md](AGENTS.md). Read it first.

## Install

Requires Python 3.11 or newer. Run these from the repo folder.

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run in mock mode

Mock mode is the default (`MOCK_MODE=1` in `.env`, and also when no `.env` exists). Every endpoint
returns the fictional "Vorden" example data from `/fixtures`, so no API keys are needed.

```bash
uvicorn backend.main:app --reload
```

Then open <http://localhost:8000> for the app and <http://localhost:8000/docs> to try the API.

## Layout

| Path | What |
|---|---|
| `backend/main.py` | Creates the app and wires the routers together |
| `backend/sourcing/` | Person A — image search (`POST /api/sources/search`) |
| `backend/ai_core/` | Person B — trait extraction and scoring (`POST /api/dna/extract`, `POST /api/compare`) |
| `frontend/` | Person C — the app UI, served at `/` |
| `contracts/models.py` | Pydantic models for the data contract |
| `fixtures/` | Example responses used by mock mode |
| `docs/` | Status, decision log, contract-change proposals |
| `prompts/` | Kickoff prompts for each person's coding agent |
