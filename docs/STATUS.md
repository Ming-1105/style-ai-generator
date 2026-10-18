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

- **Done:**
  - Milestone 1 (merged): scoring rules (`scoring.py`): overall fit, gap ranking, signature-trait rule, coverage.
  - Milestone 2 (merged): trait extraction behind `MOCK_MODE=0`, Gemini connection (`VISION_PROVIDER=gemini`).
  - Milestone 3 (merged): design comparison behind `MOCK_MODE=0` (`compare.py`, prompt `prompts/compare_traits.md`).
  - Milestone 5 (branch `ai-core/directions`): up to 3 suggested directions from the biggest gaps (`directions.py`).
  - `VISION_IMAGE_DETAIL` setting (branch `ai-core/image-detail`): fewer tokens per image; low detail matched high on
    our test.
  - Reference images in compare (branch `ai-core/references`): reads the new optional `reference_images` field.
  - Cost controls (branch `ai-core/cost-controls`): cheap defaults (low image detail, minimal thinking), a per-request
    ceiling, a token/cost ledger and an optional spending limit (`VISION_BUDGET_USD`). A comparison costs about 0.2 cents
    on Flash-Lite.
  - Full-pipeline test page (branch `ai-core/pipeline-page`): `http://localhost:8000/api/dev/pipeline` walks brand and reference
    images, extraction, editing the traits, a design and the comparison on one screen, with the running cost. Developer tool.
  - Test page for the compare step: `http://localhost:8000/api/dev/compare` (developer tool, not the app's screen).
- **Open pull requests, to merge in this order:** `ai-core/compare-live`, `ai-core/directions`, `ai-core/image-detail`,
  `contract/reference-images` (shared files: AGENTS.md, contracts/models.py), `ai-core/references`, `ai-core/cost-controls`, `docs/timeline`,
  `chore/ignore-loose-notes`.
- **In progress:** nothing. Milestone 4 (image embeddings) needs a large new package and is skipped unless the
  team approves the dependency.
- **Blocked:** the Google project behind the API key was switched to the prepaid tier while setting up billing and now answers
  402 "prepayment credits are depleted" until $5 of credit is bought (or a key from a project still on the free tier is used).
  The code now explains this. Otherwise nothing on my side. A real end-to-end test needs Person A's search merged and Person C's screen connected.
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
