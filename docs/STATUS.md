# Status

Update your own section at the end of every session (done / in progress / blocked / needs from others).
If you need something from another folder, add a note under that owner's "Needs from others".

## Shared (skeleton)

- **Done:** project skeleton — contracts, Acme fixtures, mock routers for all three endpoints,
  mockup copied to `frontend/index.html`.
- **Note:** `frontend/index.html` is still the static mockup with its data hard-coded; it does not
  call the API yet.

- **Timeline (everyone):** each of us keeps a CSV of our own events in `docs/timeline/` (`A.csv`, `B.csv`, `C.csv`,
  same format, see `docs/timeline/FORMAT.md`). `docs/timeline/PROMPT.md` is a prompt to give your coding agent to
  write yours after the fact. `python -m http.server 8080 --directory docs/timeline` shows the master flowchart.
  B.csv is done as the example; A and C still to add.

- **Integration (2026-10-19, one PC, branch `integration/a-b-c`):** A's `sourcing/serpapi` (PR #3), B's `ai-core/pipeline-page`
  and C's merged UI were combined on top of `main`; the only conflict was the shared decision log (both sides appended),
  resolved by keeping every entry. Results: A's 34 tests and B's 143 tests pass; in mock mode every endpoint, the frontend
  and the pipeline page work, and C's UI runs Brand -> Sources -> Style DNA -> Lock -> Compare with the fit shown with its
  coverage, the "could not be judged" group and 3 directions. Live (SerpApi + Gemini, key checked): search 30 candidates in
  7 s, extraction and comparison worked through the combined code in about 26 s for about 0.3 cents. Findings: (1) A flags
  27 of 30 results (domain does not match the brand or official site), so only 3 start selected and extraction rests on 3
  images unless the designer ticks more or enters the official website; (2) the images A pre-selects can be downloaded by B;
  (3) the contract proposals `skipped_images` and `coverage` in `docs/contract-changes.md` still need a team decision.

## A — Sourcing (`/backend/sourcing/`)

- **Done:** Milestone 1 — SerpAPI live image search using existing httpx; mock path preserved. One request per search, up to 30 candidates, and clear configuration/provider errors. Five unittest checks pass; a live search returned 30 candidates with HTTP 200.
- **In progress:** Milestones 1–5 ready for review and integration on `sourcing/serpapi` (PR #3). Added keyword categories and weighted text relevance from title/alt/URL and official source. Review flags and inclusion are preserved. Thirty-four tests pass; live endpoint returned 49 candidates with categories and relevance scores.
- **Blocked:**
- **Needs from others:**
- **Run the tests:** `python -m unittest backend.sourcing.test_search backend.sourcing.test_website backend.sourcing.test_filtering backend.sourcing.test_flagging backend.sourcing.test_classification`
- **Changed in the integration session (2026-10-19), please review:** flagging no longer looks at whether the source domain matches
  the brand; it flags only small, AI-generated, fan-made and user-generated/marketplace images (see the decision log). Tests updated
  (37 pass). 23 of 30 live results now start selected instead of 3.

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
  - Several views of the design (branch `ai-core/design-views`): optional `additional_design_images` (up to 3) on `/api/compare`;
    all views go to the model as one design. Contract change, see `docs/contract-changes.md`.
  - Agreed contract fields (branch `contract/agreed-fields`): `/api/dna/extract` returns `skipped_images` (selected images that could not be
    analysed, with the reason) and `do_dont` (rules drawn from the traits); `/api/compare` returns `coverage`. In `AGENTS.md`,
    `contracts/models.py` and the fixtures.
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

- **Needs from C (agreed in the team meeting, 2026-10-19):** `/api/dna/extract` now returns `do_dont` (use it for the package's do/don't
  rules instead of `[]`) and `skipped_images` (show something like "2 images could not be analysed: img_13 (could not be downloaded)"
  next to the extraction result). `/api/compare` now returns `coverage` (already used when present). The fixtures contain an example of
  each, so mock mode shows them.

- **Changed by B at the designer's request (2026-10-19), confirmed by the team:** `frontend/index.html` now lets the designer add up to 3 more views of
  the design (step 4 and the Compare screen) and sends them as `additional_design_images`; first image stays `design_image`. A refused
  extra image does not re-run the comparison. See the decision log.

- **Done:** Milestone 1 (branch `ui/api-wiring`) — `frontend/index.html` no longer has hard-coded
  data. One `state` object (brand, candidates, traits, tone words, colors, package, compare result)
  and every screen renders from it. Brand → `POST /api/sources/search`, Sources →
  `POST /api/dna/extract` with the included images, Lock builds the `HouseStylePackage` client-side,
  Compare → `POST /api/compare`. Until upload exists, Compare sends a bundled sample sketch
  (`frontend/static/sample/design_sample.svg`) as a data URL. Departures whose traits all have
  importance 0 are greyed out (hide control comes in milestone 3). API errors show `error.message`
  in a toast. Re-running an earlier step locks the later ones again.
- **Done (milestone 2):** loading state on all three API calls (spinner + seconds counter). Errors now
  stay in the step as an inline box with `error.message` and a "Try again" button (they used to be a
  toast that vanished). Empty results (0 candidates, 0 traits) are shown as a clear message instead of
  an empty screen. Honest display: `confidence: null` shows "not rated", and the overall fit shows a
  note when traits were left out (`not_assessable`) or scored with low confidence. Broken images hide
  instead of showing the browser's broken icon.
- **Done (milestone 3):** greyed-out departures (all linked traits importance 0) have a Hide button;
  hidden ones leave the list and a "N hidden — show" toggle brings them back. Frontend only, nothing
  sent to the backend. Resets when sources, DNA, package or compare change.
- **Done (milestone 4):** design upload. Step 4 has a drop/click area for the designer's own image
  (PNG/JPG/WebP/GIF, max 15 MB, preview shown); "Replace design" on the Compare screen uploads and
  re-compares at once. Images over 1600 px on the long side are shrunk to JPEG in the browser before
  being sent as a data URL in `design_image`. Wrong file types and unreadable images give a clear
  message. With no upload, the bundled sample sketch is still used and labelled as such.
- **Done (after merging main):** Compare now sends `reference_images` (the evidence images of the traits, each once), as B's contract change requires.
- **Done (milestone 5, branch `ui/coverage-display`):** Compare shows the overall fit with its coverage
  ("Based on 92% of the importance (5 of 6 traits could be judged)") and a warning when coverage is under
  50%. Uses the API's `coverage` field if it is ever sent, otherwise the same formula as
  `scoring.coverage`. Traits that could not be judged are their own group, "Could not be judged", with
  the AI's note, and no longer appear among the score bars. Requests from B on 2026-10-14 are done.
- **In progress:** nothing planned yet.
- **Blocked:**
- **Needs from others:** B — no endpoint returns `do_dont`; proposal in `docs/contract-changes.md`.
- **Request from B** (agreed with the designer on 2026-10-07; greying and hide control done) —
  departures of traits whose importance is 0:
  - `/api/compare` keeps listing them. Each departure has `trait_ids`; look those up in the package
    you sent. If every linked trait has `importance` 0, show the departure **greyed out**.
  - Give the designer a control to **hide** (deselect) such departures, so the list can be reduced to
    what they care about. Nothing needs to be sent back to the backend for this.
  - The same trait never produces a direction and does not count towards `overall_fit`.
  - From B, 2026-10-14: show `overall_fit` together with how much of the importance could be judged ("based on
    39% of the importance"; formula in `scoring.coverage`, contract proposal in `docs/contract-changes.md`), and show
    traits with status `not_assessable` as their own group ("could not be judged"), not under "departs from the
    brand". The test page in `backend/ai_core/devtools/` does both and can serve as the example.
