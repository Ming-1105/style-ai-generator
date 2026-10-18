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
  - Milestone 1 (merged): scoring rules (`scoring.py`): overall fit, gap ranking, signature-trait rule, coverage.
  - Milestone 2 (merged): trait extraction behind `MOCK_MODE=0`, Gemini connection (`VISION_PROVIDER=gemini`).
  - Milestone 3 (merged): design comparison behind `MOCK_MODE=0` (`compare.py`, prompt `prompts/compare_traits.md`).
  - Milestone 5 (branch `ai-core/directions`): up to 3 suggested directions from the biggest gaps (`directions.py`).
  - `VISION_IMAGE_DETAIL` setting (branch `ai-core/image-detail`): fewer tokens per image; low detail matched high on
    our test.
  - Reference images in compare (branch `ai-core/references`): reads the new optional `reference_images` field.
  - Test page for the compare step: `http://localhost:8000/api/dev/compare` (developer tool, not the app's screen).
- **Open pull requests, to merge in this order:** `ai-core/compare-live`, `ai-core/directions`, `ai-core/image-detail`,
  `contract/reference-images` (shared files: AGENTS.md, contracts/models.py), `ai-core/references`, `docs/timeline`,
  `chore/ignore-loose-notes`.
- **In progress:** nothing. Milestone 4 (image embeddings) needs a large new package and is skipped unless the
  team approves the dependency.
- **Blocked:** nothing on my side. A real end-to-end test needs Person A's search merged and Person C's screen connected.
- **Needs from others:**
  - C: send `reference_images` (the candidates cited by the traits' `evidence_image_ids`) with `/api/compare`; show
    `overall_fit` together with how much of the importance could be judged and warn when that share is low; show traits
    that could not be judged as their own group; greyed-out/hide option for importance-0 departures (see below).
  - A: `url` on each candidate must point at the image file itself, not the page it was found on.
- **Try it yourself:** `python -m backend.ai_core.try_extract` and `python -m backend.ai_core.try_compare` (read the top
  of each file; `--detail`, `--runs`, `--references` options). Tests: `python -m unittest discover -s backend/ai_core/tests -t .`

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
  - From B, 2026-10-14: show `overall_fit` together with how much of the importance could be judged ("based on
    39% of the importance"; formula in `scoring.coverage`, contract proposal in `docs/contract-changes.md`), and show
    traits with status `not_assessable` as their own group ("could not be judged"), not under "departs from the
    brand". The test page in `backend/ai_core/devtools/` does both and can serve as the example.
