# Contract-change proposals — what, why, who is affected

## Proposal (Person B, 2026-10-07): tell the designer which images were skipped

- **What:** add an optional `skipped_images: [{ "id": "img_07", "reason": "could not be downloaded" }]`
  to the response of `POST /api/dna/extract`.
- **Why:** extraction skips images it cannot download. Today that is only written to the server
  log, so the designer sees "seen in 3 images" without knowing 4 of their 13 were never analysed.
- **Who is affected:** B returns it, C displays it. Optional field, so nothing breaks without it.

## Proposal (Person C, 2026-10-07): return do/don't rules from extraction

- **What:** add an optional `do_dont: [{ "do": "…", "dont": "…" }]` to the response of
  `POST /api/dna/extract`, next to `tone_words` and `colors`.
- **Why:** `HouseStylePackage.do_dont` exists and the House style screen has a "Form language"
  section for it, but no endpoint produces these rules. The frontend now builds the package from
  the API responses, so `do_dont` is always `[]` and the screen says "No do/don't rules yet".
  (Until then, C could let the designer type rules by hand — that needs no contract change.)
- **Who is affected:** B returns it, C displays it. Optional field, so nothing breaks without it.

## Proposal (Person B, 2026-10-07): send the reference images with `POST /api/compare`

- **Status:** agreed by the team and applied on 2026-10-18 (`AGENTS.md` API table, `contracts/models.py`).

- **What:** add one optional field to the request of `POST /api/compare`:

  ```jsonc
  { "package": HouseStylePackage,
    "design_image": "<data URL or https URL>",
    "reference_images": ImageCandidate[] }   // optional, default []
  ```

  `reference_images` holds the `ImageCandidate` objects (the same objects the sourcing step returned,
  with `id`, `url`, `source_domain`, …) of the images that are listed in the traits' `evidence_image_ids`.
  Each image appears once, even when several traits cite it. `contracts/models.py` gets
  `reference_images: list[ImageCandidate] = []` on `CompareRequest`, and the request body in the
  API table in `AGENTS.md` is updated to match. Nothing changes in the response.

- **Why:** the compare step should judge the design against the *pictures* that evidence each trait,
  not only against the trait's one-sentence description. But the package stores evidence as image IDs
  only, so the backend cannot look the pictures up: it has no database and, per `AGENTS.md`, must not
  keep scraped images. The interface still holds the candidates from the sourcing step, so it can send
  them along. Comparing against real references also makes the result easier for the designer to
  inspect: the same images that are shown as evidence on the Style DNA screen are the ones the AI used.

- **How B will use it:** for each trait, up to 3 of its evidence images (highest `relevance` first) are
  sent to the vision model together with the design, at most about 12 distinct images per request.
  Images are downloaded into memory for that one request and never saved (same loader as extraction).
  An image that cannot be downloaded is skipped and the trait is judged from its description plus the
  remaining images. Without `reference_images` the compare step works from the trait descriptions
  alone, so old requests keep working.

- **Who is affected:**
  - **C (Interface):** include the candidates whose IDs appear in any trait's `evidence_image_ids`
    when calling `/api/compare`. Optional, so the screen keeps working before this is done.
  - **B (AI core):** reads the new field. Until the team agrees, B builds the description-only version.
  - **A (Sourcing):** `url` on each candidate must point at the image file itself (jpg/png/gif/webp),
    not the page it was found on, because B downloads it from there. Same requirement as for extraction.
  - **Shared files:** `contracts/models.py`, `AGENTS.md` (API table). `fixtures/` do not change, because
    fixtures are responses and the response does not change.

- **Alternatives considered:**
  - *Put image URLs inside the package.* Rejected: the locked House Style Package would then carry
    scraped image links, and the same image would be repeated under several traits.
  - *Send the images per trait* (`{ trait_id: [images] }`). Rejected: an image that evidences three
    traits would be sent and downloaded three times.
  - *Keep the extraction images in the backend's memory.* Rejected: lost on every restart, and it stores
    scraped images, which `AGENTS.md` discourages.

- **Decision needed:** the team agrees on the field name `reference_images` and that C sends it.
  If agreed, one person updates `AGENTS.md`, `contracts/models.py` and this file in a single PR.

## Proposal (Person B, 2026-10-14): `coverage` on the compare result

- **What:** add an optional integer `coverage` (0-100, or `null`) to `CompareResult`: the share of the
  designer's total trait importance that could be judged (traits with status `ok` or `low_confidence`, weighed by
  importance, divided by the importance of all traits). `scoring.coverage` in `backend/ai_core/scoring.py`
  is the reference implementation.
- **Why:** `overall_fit` only describes the traits that could be assessed. A fit of 45 based on 39% of the
  importance (a pencil sketch with no colour) means something very different from a 45 based on 100%.
  Every screen should show the two together; computing it once in the backend keeps the three screens
  from drifting.
- **Who is affected:** B returns it, C displays it as "based on N% of the importance" (and can suggest what to
  add when it is low). Optional field, nothing breaks without it. Until agreed, a screen can compute it from
  `trait_scores` and the package's importance values with the same formula.

## Proposal (Person B, 2026-10-19): more than one design image in `POST /api/compare`

- **What:** add one optional field to the request: `additional_design_images: string[]` (data URLs or https URLs, at most 3).
  `design_image` stays the main view. B shows all of them to the model as views of the same design (labelled "design",
  "design_2", ...). `contracts/models.py` and the API table in `AGENTS.md` are updated. Nothing changes in the response.
- **Why:** one picture often hides traits (earlier results said "needs a side view to judge"). With a front, a side and a back
  view the AI can judge more traits, which raises coverage, and a trait counts as "not assessable" only when no view shows it.
- **Who is affected:** B reads it and sends all views to the model. C needs a way to add up to 4 images of the design and to send
  the first as `design_image` and the rest as `additional_design_images`. A is not affected. Optional field, so nothing breaks
  without it; more than 4 images in total is refused with a clear message (`too_many_design_images`).
- **Status:** confirmed by all three of us on 2026-10-19 and applied in `AGENTS.md` (API table and text) and
  `contracts/models.py` (pull request #12). No fixture changes: fixtures are responses and the response did not change.
