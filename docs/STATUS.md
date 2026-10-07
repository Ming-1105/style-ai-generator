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

- **Done:** Milestone 1 (branch `ui/api-wiring`) — `frontend/index.html` no longer has hard-coded
  data. One `state` object (brand, candidates, traits, tone words, colors, package, compare result)
  and every screen renders from it. Brand → `POST /api/sources/search`, Sources →
  `POST /api/dna/extract` with the included images, Lock builds the `HouseStylePackage` client-side,
  Compare → `POST /api/compare`. Until upload exists, Compare sends a bundled sample sketch
  (`frontend/static/sample/design_sample.svg`) as a data URL. Departures whose traits all have
  importance 0 are greyed out (hide control comes in milestone 3). API errors show `error.message`
  in a toast. Re-running an earlier step locks the later ones again.
- **In progress:** next is milestone 2 (loading and error states, honest `null` / `low_confidence`
  display).
- **Blocked:**
- **Needs from others:** B — no endpoint returns `do_dont`; proposal in `docs/contract-changes.md`.
- **Request from B** (agreed with the designer on 2026-10-07; greying done, hide control still to do) —
  departures of traits whose importance is 0:
  - `/api/compare` keeps listing them. Each departure has `trait_ids`; look those up in the package
    you sent. If every linked trait has `importance` 0, show the departure **greyed out**.
  - Give the designer a control to **hide** (deselect) such departures, so the list can be reduced to
    what they care about. Nothing needs to be sent back to the backend for this.
  - The same trait never produces a direction and does not count towards `overall_fit`.
