# Status

Update your own section at the end of every session (done / in progress / blocked / needs from others).
If you need something from another folder, add a note under that owner's "Needs from others".

## Shared (skeleton)

- **Done:** project skeleton — contracts, Vorden fixtures, mock routers for all three endpoints,
  mockup copied to `frontend/index.html`.
- **Note:** `frontend/index.html` is still the static mockup with its data hard-coded; it does not
  call the API yet.

## A — Sourcing (`/backend/sourcing/`)

- **Done:** Milestone 1 — SerpAPI live image search using existing httpx; mock path preserved. One request per search, up to 30 candidates, and clear configuration/provider errors. Five unittest checks pass; a live search returned 30 candidates with HTTP 200.
- **In progress:** Milestone 1 ready for review on `sourcing/serpapi`.
- **Blocked:**
- **Needs from others:**
- **Run the tests:** `python -m unittest backend.sourcing.test_search`

## B — AI core (`/backend/ai_core/`)

- **Done:** Milestone 1 (branch `ai-core/scoring`) — scoring rules as pure functions in
  `backend/ai_core/scoring.py` (overall fit, gap ranking, signature-trait rule), with unit tests
  in `backend/ai_core/tests/`. Mock `/api/compare` now computes overall fit, departures and
  direction order from the package in the request, so changing an importance changes the result.
  The per-trait scores themselves are still the Vorden sample data.
- **In progress:** nothing — next is milestone 2 (trait extraction behind `MOCK_MODE=0`).
- **Blocked:** milestone 2 needs to know which vision provider we have API keys for.
- **Needs from others:**
- **Run the tests:** `python -m unittest discover -s backend/ai_core/tests -t .`

## C — Interface (`/frontend/`)

- **Done:**
- **In progress:**
- **Blocked:**
- **Needs from others:**
