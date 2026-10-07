# Status

Update your own section at the end of every session (done / in progress / blocked / needs from others).
If you need something from another folder, add a note under that owner's "Needs from others".

## Shared (skeleton)

- **Done:** project skeleton — contracts, Vorden fixtures, mock routers for all three endpoints,
  mockup copied to `frontend/index.html`.
- **Note:** `frontend/index.html` is still the static mockup with its data hard-coded; it does not
  call the API yet.

- **Timeline (everyone):** each of us keeps a CSV of our own events in `docs/timeline/` (`A.csv`, `B.csv`, `C.csv`,
  same format, see `docs/timeline/FORMAT.md`). `docs/timeline/PROMPT.md` is a prompt to give your coding agent to
  write yours after the fact. `python -m http.server 8080 --directory docs/timeline` shows the master flowchart.
  B.csv is done as the example; A and C still to add.

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
- **In progress:** Milestone 2 (branch `ai-core/extract`) — trait extraction behind `MOCK_MODE=0`.
  Done: the prompt (`backend/ai_core/prompts/extract_traits.md`), image download, the checks on
  the model's answer (evidence ids, `seen_count`, `low_confidence`), one retry, clear errors, and
  tests with a fake model. Gemini connection written (`provider_gemini.py`, registered as `VISION_PROVIDER=gemini`) and tested
  with faked web responses; not yet tried with a real key.
- **Blocked:** needs a Gemini API key from Google AI Studio (in a local `.env`) to try it on real images.
- **Needs from others:** A — extraction downloads each included image from its `url`, so `url`
  should point at the image file itself (jpg/png/gif/webp), not at the page it appears on.
- **Run the tests:** `python -m unittest discover -s backend/ai_core/tests -t .`

## C — Interface (`/frontend/`)

- **Done:**
- **In progress:**
- **Blocked:**
- **Needs from others:** from B (agreed with the designer on 2026-10-07) — departures of traits whose
  importance is 0:
  - `/api/compare` keeps listing them. Each departure has `trait_ids`; look those up in the package
    you sent. If every linked trait has `importance` 0, show the departure **greyed out**.
  - Give the designer a control to **hide** (deselect) such departures, so the list can be reduced to
    what they care about. Nothing needs to be sent back to the backend for this.
  - The same trait never produces a direction and does not count towards `overall_fit`.
