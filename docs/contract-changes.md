# Contract-change proposals — what, why, who is affected

## Proposal (Person B, 2026-10-07): tell the designer which images were skipped

- **What:** add an optional `skipped_images: [{ "id": "img_07", "reason": "could not be downloaded" }]`
  to the response of `POST /api/dna/extract`.
- **Why:** extraction skips images it cannot download. Today that is only written to the server
  log, so the designer sees "seen in 3 images" without knowing 4 of their 13 were never analysed.
- **Who is affected:** B returns it, C displays it. Optional field, so nothing breaks without it.
