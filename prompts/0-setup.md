# Kickoff prompt 0: repo setup (one person, once, before the others start)

Copy `AGENTS.md` and `CLAUDE.md` into an empty folder, open a session there, and paste the prompt below.
If you have it, also copy in the mockup HTML as `mockup.html`.

---

You are setting up the shared repository for a three-person student project. Read `AGENTS.md`
first. It is the contract everyone works from. Do not change its contents.

Create the skeleton so that all three people can start in parallel today:

1. `git init`, a Python `.gitignore` that also ignores `.env`, and a `README.md` with:
   what the tool is (2 sentences), how to install, and how to run in mock mode.
2. `requirements.txt` with only: fastapi, uvicorn, python-dotenv, httpx, pydantic.
3. `.env.example` with `MOCK_MODE=1` and empty placeholders for `IMAGE_SEARCH_PROVIDER`,
   `IMAGE_SEARCH_API_KEY`, `VISION_PROVIDER`, `VISION_API_KEY`.
4. `/contracts/models.py` with pydantic models that exactly match the data contract in
   AGENTS.md (ImageCandidate, Trait, Brand, HouseStylePackage, TraitScore, CompareResult, …).
5. `/fixtures/` with realistic example JSON for every endpoint, using the fictional brand
   "Vorden". If `mockup.html` exists, take the data from it (18 image candidates with 4 flagged,
   6 traits, the package, and a compare result with overall fit 61, one `not_assessable`
   trait and 3 directions). Image URLs can be placeholders such as `/static/placeholder/img_01.svg`.
6. `/backend/main.py` creating the FastAPI app, mounting `/frontend` as static files at `/`,
   and including the routers from `backend.sourcing` and `backend.ai_core`.
7. `/backend/sourcing/__init__.py` and `/backend/ai_core/__init__.py`, each with an `APIRouter`
   whose endpoints (from the API table) return the fixtures. This is the mock path the owners
   will build on.
8. `/frontend/index.html`: copy `mockup.html` if present, otherwise a minimal page that calls
   `/api/sources/search` and shows the result.
9. `/docs/STATUS.md` with a section per person (A Sourcing, B AI core, C Interface), plus empty
   `/docs/decision-log.md` and `/docs/contract-changes.md` with a one-line header each.

Then verify that `MOCK_MODE=1 uvicorn backend.main:app --reload` starts and that each endpoint
returns its fixture. Commit with the message "Project skeleton". Then tell me the exact steps to
push this to a new GitHub repo and invite my two teammates.
