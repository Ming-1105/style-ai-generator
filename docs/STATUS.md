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

- **Done:**
  - Milestone 1 (merged): scoring rules (`scoring.py`) — overall fit, gap ranking, signature-trait rule.
  - Milestone 2 (merged): trait extraction behind `MOCK_MODE=0` (`extract.py`, prompt in
    `prompts/extract_traits.md`), Gemini connection (`provider_gemini.py`, `VISION_PROVIDER=gemini`).
    Tried on real images; see the decision log for how repeatable it is.
- **In progress:** Milestone 3 (branch `ai-core/compare-live`): design comparison behind `MOCK_MODE=0`
  (`compare.py`, prompt in `prompts/compare_traits.md`). Built and tested with a fake model; not yet
  tried on a real design. For now the model sees the design image and the trait descriptions only.
  Live mode returns no directions until milestone 5.
- **Blocked:** reference images in compare wait for the contract change in `docs/contract-changes.md`
  ("send the reference images with `POST /api/compare`", agreed by the team). Someone needs to update
  `AGENTS.md` and `contracts/models.py` in one PR; B then reads the new field.
- **Needs from others:**
  - C: when `reference_images` is in the contract, send the candidates behind the traits' evidence ids
    with `/api/compare`. See also the note on importance-0 departures (greyed out + hide option).
  - A: `url` on each candidate must point at the image file itself, not the page it was found on.
- **Try it yourself:** `python -m backend.ai_core.try_extract` and `python -m backend.ai_core.try_compare`
  (read the top of each file). Tests: `python -m unittest discover -s backend/ai_core/tests -t .`

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
