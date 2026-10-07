# Decision log — AI-related design decisions (date, what, why)

## 2026-10-07 — Scoring is computed in code, not by the model (Person B)

- **What:** The model will only supply a score, status and note per trait. Overall fit, the gap
  ranking that orders directions, and the signature-trait departure are computed by plain
  functions in `backend/ai_core/scoring.py`.
- **Why:** The designer can trace every derived number back to a trait score and the importance
  they set themselves, and changing an importance changes the result predictably. A model asked
  for an "overall fit" would give a number nobody can inspect.

## 2026-10-07 — A trait without a judgement is "not assessable", never 0 (Person B)

- **What:** If a trait in the package has no score (e.g. a trait the designer added by hand, or a
  view that doesn't show the feature), it gets `score: null`, `status: not_assessable` and is left
  out of overall fit. Overall fit is `null` when nothing could be assessed.
- **Why:** Counting it as 0 would lower the fit for something the AI simply could not see, which
  presents a gap in the evidence as a flaw in the design.

## 2026-10-07 — Search metadata without inferred visual relevance (Person A)

- **What:** Use SerpAPI google_images with existing httpx. Build one query from brand name, category, keywords and official; return up to 30 image URLs and source domains. No images are downloaded. Keep relevance=null and category=other until the later classification milestone.
- **Why:** One request limits allowance usage. Provider ranking is not a measured relevance score, and a search query does not prove an image is official. Preserve the working mock path and never commit the private .env file.

## 2026-10-07 — Respect website collection policy (Person A)

- **What:** Check robots.txt and read the exact supplied HTML page. Disallowed, inaccessible, redirected or rate-restricted pages return an actionable error; clear the website field for search only. Missing robots.txt (404) permits collection. No links or image resources are fetched and no JavaScript is run.
- **Why:** Keep collection inspectable within single-page scope without hiding failures. Support relative and lazy-loading image URLs using existing dependencies. Category and relevance remain unknown. No new dependencies.

## 2026-10-07 — URL dedupe and metadata-based size filtering (Person A)

- **What:** Deduplicate URLs across search and scrape candidates, normalizing hostname/default ports and removing fragments while preserving query parameters. Drop images with a known side below 128 pixels. Use SerpAPI original dimensions or HTML declared dimensions; retain unknown sizes. Return a clear error if no images remain.
- **Why:** Remove repeated evidence and small icons without new dependencies or downloading source images. HTML dimensions describe display size, not verified intrinsic resolution. Visually similar images at different URLs remain; perceptual hashing is not implemented.

## 2026-10-07 — Review clues, not authenticity verdicts (Person A)

- **What:** Flag reported image sides below 512px, source domains differing from the supplied official website (or brand tokens when no website is supplied), and explicit fan-art/unofficial/render/CGI words in title, alt text or URL. Keep flagged candidates visible with included=false and combine all reasons. Unknown dimensions cause no size flag.
- **Why:** Let the designer judge questionable evidence. Domain mismatches can be legitimate third-party coverage, and renders can be official. Reasons state this uncertainty. HTML dimensions reflect declared display size, not verified file resolution. No vision model or new dependency is used.

## 2026-10-07 — Keyword category and relevance estimates (Person A)

- **What:** Classify title/alt/URL tokens using ordered keyword dictionaries: logo, packaging, web, product, otherwise other. Relevance weights brand tokens 50%, category 20%, keyword groups 20%, official source 10%, renormalized for absent optional fields. Missing all text yields null; available text with no match yields 0. Preserve flags and inclusion.
- **Why:** An inspectable first version without vision costs. Scores are text match estimates, not probabilities or visual style scores. CDN hostnames are not category evidence; unrecognized product types remain other. Metadata cannot verify visible content. No new dependencies.
