# Status

Update your own section at the end of every session (done / in progress / blocked / needs from others).
If you need something from another folder, add a note under that owner's "Needs from others".

## Shared (skeleton)

- **Done:** project skeleton — contracts, Vorden fixtures, mock routers for all three endpoints,
  mockup copied to `frontend/index.html`.
- **Note:** `frontend/index.html` is still the static mockup with its data hard-coded; it does not
  call the API yet.

## A — Sourcing (`/backend/sourcing/`)

- **Done:**
- **In progress:**
- **Blocked:**
- **Needs from others:**

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
