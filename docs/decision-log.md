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
