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
