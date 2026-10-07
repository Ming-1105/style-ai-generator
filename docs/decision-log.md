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

## 2026-10-07 — The vision model is interchangeable (Person B)

- **What:** All of `ai_core` talks to a "provider": one function that takes a prompt and images
  and returns the model's text. Which model is behind it is set by `VISION_PROVIDER` and lives
  only in `backend/ai_core/providers.py`. No provider is connected yet.
- **Why:** We have no API key yet and may switch model during the project. The prompt, the checks
  and the tests do not depend on the choice, so the report can compare models on equal terms.

## 2026-10-07 — The model proposes traits, the code checks them (Person B)

- **What:** For trait extraction the model returns name, description, evidence image ids,
  confidence and a suggested importance. In code we then: drop evidence ids for images we did
  not send, count `seen_count` from the remaining ids, set `low_confidence` below 0.6, and
  remove a trait that has no valid evidence left. An invalid answer is retried once; after that
  the designer gets an error instead of made-up traits.
- **Why:** A language model can miscount or cite an image that does not exist. Anything that can
  be counted or looked up should not rest on the model's word, so every trait the designer sees
  is linked to images that were really shown to the model.

## 2026-10-07 — Extraction prompt: images are the only evidence (Person B)

- **What:** `prompts/extract_traits.md` tells the model to report only what is visible in the
  supplied images, not what it knows about the brand from elsewhere; to need at least 2 images
  per trait; to describe the product, not the photograph; and to return fewer traits rather than
  pad the list. Brand keywords and values are given as context, explicitly not as evidence.
- **Why:** For a well-known brand the model could recite a textbook description that the
  designer cannot verify against their own reference set. Tying traits to the reviewed images
  keeps the designer's curation in step 2 meaningful.

## 2026-10-07 — Images are downloaded by us and sent as data (Person B)

- **What:** Extraction downloads each included image (max 20, most relevant first, jpg/png/gif/
  webp up to 5 MB) and sends the image data to the model. Images that fail to load are skipped
  and logged; with fewer than 2 usable images the request fails with a clear message.
- **Why:** Search results often point at images that block outside access or have disappeared,
  and we need to know exactly which images the model saw to validate its evidence. Images are
  held in memory for one request and never saved.

## 2026-10-07 — Departures stay when importance is 0; the interface greys them out (Person B)

- **What:** If the designer sets a trait's importance to 0, `/api/compare` still lists its departure.
  The trait no longer counts in overall fit and gets no direction. The interface shows such
  departures greyed out and lets the designer hide them.
- **Why:** The AI measures and the designer decides: "this doesn't matter to me" should not delete a
  factual observation, only stop it from steering the score and the suggestions.

## 2026-10-07 — First provider: Google Gemini, called over plain HTTPS (Person B)

- **What:** `backend/ai_core/provider_gemini.py` sends the prompt and images to Gemini's REST API
  with `httpx` and asks for JSON output (`responseMimeType: application/json`, temperature 0.2).
  Default model `gemini-2.5-flash`, overridable with the optional `VISION_MODEL` variable. The API
  key is sent in a header, never in the URL.
- **Why:** A free API key is available through Google AI Studio, and no new dependency is needed.
  Because the provider is interchangeable, we can compare other models later with the same prompt.

## 2026-10-07 — First real extraction test: which Gemini model works on the free tier (Person B)

- **What:** Tried extraction on 12 product screenshots of one real brand (kept local, not in the repo).
  On a free-tier key: `gemini-3.8-flash` was overloaded (503, then a timeout), `gemini-3.1-pro-preview`
  was rate-limited (429), `gemini-2.5-*` is closed to new accounts, and **`gemini-3.5-flash` worked**
  (6 traits in 24 s, all with valid evidence ids). Model is chosen with `VISION_MODEL` in `.env`.
- **Observed:** the model rated every trait 0.85–0.95 confident and suggested importance 75–95, so
  the confidence and importance numbers barely distinguish traits. Spot checks of 2 of 12 images
  found the cited evidence plausible. Worth handling in the interface: the designer sets importance,
  and the AI's confidence should not be read as an accuracy measure.
- **Why it matters:** availability of the preferred model varies by hour on a free key; the pinned
  model for the report must be one that actually responds, and the comparison against a Pro model
  needs a paid or higher-quota key.
