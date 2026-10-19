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

## 2026-10-07 — Extraction is not repeatable: two runs on identical input differ (Person B)

- **What:** Ran extraction twice on the same 12 images, same model (`gemini-3.5-flash`), same prompt,
  temperature 0.2. Run 1 returned 6 traits, run 2 returned 5. One trait (exposed cyclone chambers)
  appeared only in run 1; the other traits came back with reworded names and slightly different
  evidence sets (e.g. the colour trait cited in 10 images, then 9). Confidence stayed at 0.85–0.95
  for every trait in both runs.
- **Why it matters:** The result is a proposal, not a measurement. The designer must be able to edit,
  remove and add traits (already in the design), and the seen-in count is a more useful signal of
  reliability than the model's own confidence. Traits that recur across runs are stronger candidates.
- **Next:** try repeated runs and keep track of which traits recur (script only for now; a change to
  the endpoint would multiply API calls and needs the team's agreement).

## 2026-10-07 — Repeated extraction: evidence is stable, names and weaker traits are not (Person B)

- **What:** Ran extraction 4 times on the same 12 images (`gemini-3.5-flash`), matching traits across runs
  by the images they cite (`try_extract --runs 4`). Three traits came back in all 4 runs with
  (nearly) identical evidence images each time: a perforation pattern (6 images, identical in all runs),
  saturated accent colours on grey (9 images), and transparent cyclone chambers (4 images).
  A red-controls trait came back in 3 of 4. A hollow-ring trait that appeared in both earlier runs
  appeared in only 1 of 4 here. Trait names changed in nearly every run.
- **Caveat:** matching by evidence overlap can merge two different traits that cite the same images
  (red controls and cyclone clusters share 4 images and were partly merged in the summary).
- **Takeaway for the design:** the evidence images are a more reliable identity for a trait than its
  name; a trait seen in every run is a stronger candidate than one seen once. A possible later feature
  is to run extraction 3 times and show "found in 3/3 runs" next to each trait; it costs 3x the
  API calls, so it needs the team's agreement.

## 2026-10-07 — The interface only shows what the API returned (Person C)

- **What:** Milestone 1 replaced all hard-coded mockup data with the three API calls. Where the
  mockup showed things the contract does not provide, the interface now leaves them out instead of
  inventing them: no image captions (shows id, source type and domain instead), no hand-placed pins
  on the design, no sketched variant per direction (only `image_url` when the API sends one), no
  do/don't rules (none returned yet — proposed in contract-changes.md).
- **Why:** "the AI measures and suggests, the designer decides" only works if what the designer
  sees is what the AI actually produced. Departures whose traits all have importance 0 are shown
  greyed out, as agreed with B.

## 2026-10-07 — Interface: failures stay visible (milestone 2)
- **What:** API errors are shown inline in the step with a retry button, and empty AI/search results are treated as an error with advice. The overall fit explains how many traits were left out or low confidence.
- **Why:** The core principle is that the AI must report honestly when it cannot judge. A toast disappears and an empty screen looks like a bug; designers need to see what failed and why.

## 2026-10-19 — Interface: designs are shrunk in the browser before comparison (milestone 4)
- **What:** Uploaded designs are limited to 15 MB and downscaled to at most 1600 px (JPEG) before being sent to `/api/compare` as a data URL.
- **Why:** Vision models do not need full-resolution files, and a small payload keeps the comparison fast and avoids request-size errors. The designer still sees their original-looking image in the preview.

## 2026-10-07 — Comparison: the model judges, the code decides everything else (Person B)

- **What:** `POST /api/compare` sends the design image and each trait's name and description to the
  vision model in one request and asks for a score (0-100 with written anchors), a status and a one-
  sentence note per trait. In code: a trait the model skipped, or marked not assessable, or scored
  without a number, becomes `not_assessable` with a null score (never 0); `low_confidence` is set
  from the package, not by the model; unknown trait ids are ignored. Overall fit and the signature
  rule come from `scoring.py`. Matches (score >= 70) and departures (< 50, plus traits that could
  not be judged) are taken from the model's per-trait notes, with no second model call.
- **Why:** The model never sees the importance values, so it cannot bend scores towards what the
  designer cares about; the weighting stays visible and editable in one place. One request for all
  traits (instead of one per trait) keeps us inside the free-tier quota and fails less often when the
  model is busy. Scores for traits whose feature is not visible are reported as not assessable so the
  designer sees what is missing instead of a made-up number.
- **Known limits:** reference images are not used yet (the request has no way to carry them; contract
  change agreed, not yet applied); scores will vary between runs like extraction does (to be measured
  with `try_compare --runs`); directions stay empty in live mode until milestone 5.

## 2026-10-13 — First comparison of hand-drawn sketches against a brand's traits (Person B)

- **What:** Compared three pencil sketches of new product ideas (made by the designer, in the style of one
  real brand, kept local) against five traits extracted from 12 of that brand's product screenshots,
  with `gemini-3.5-flash-lite`. One run each, about a minute per run including retries when the model
  was busy. Overall fit came out at 41, 50 and 58.
- **Observed (good):** the two colour and material traits, which carry the highest importance (95 and 90),
  were reported as not assessable on all three sketches ("needs colour"), with no invented score. The notes
  were concrete ("square grid instead of circular perforations"). A square mesh scored 30 on a
  circular-perforation trait, vertical slots scored 90.
- **Observed (weak):** the transparent-enclosure trait was handled inconsistently: scored 5 and 10 ("opaque,
  monochrome pencil") on two sketches, which a pencil drawing cannot show either way, and 85 on a third
  because internal parts were outlined. The slots-versus-circles score of 90 looks generous.
- **Consequence:** with the two heaviest traits not assessable, the overall fit describes only the traits
  that could be judged (here about 56% of the total importance on the first sketch), so the number must be
  shown together with that coverage. Traits that could not be judged are listed under departures, which
  reads as "departs from the brand"; the interface should show them as a separate group using the trait status.
- **Next:** repeat one sketch several times to see how much scores move, tighten the prompt on traits about
  material or transparency (judge them only when the drawing shows a clear cue), and try the larger model.

## 2026-10-14 — Stricter compare prompt, and the fit is shown with its coverage (Person B)

- **What:** Two prompt rules were added to `prompts/compare_traits.md`: colour, material, finish and
  transparency are judged only when the drawing shows a clear cue (otherwise `not_assessable`, and the
  absence of a feature in a monochrome sketch is never read as proof it is missing); and a different form
  from the one a trait names (slots or squares instead of round holes) counts as a deviation. A new
  function `scoring.coverage` gives the share of the total importance that could be judged, and the test
  page shows it next to the fit and puts "could not be judged" in its own group.
- **Result (same three sketches, same model, one run each):** overall fit 41 / 50 / 58 became
  54 / 45 (52 in a later batch) / 46. Transparency went from scores of 5, 10 and 85 to "not assessable" on all
  three; the slot pattern went from 90 to 30. The fit now rests on 39% of the total importance on every sketch,
  because the three traits about colour, material and transparency (the heaviest ones) cannot be judged from
  pencil. Three repeated runs of one sketch gave identical scores (30 / 75, fit 52), but the same trait scored
  60 in the earlier separate run, so the spread over separate runs is at least 15 points.
- **Caveat:** the stricter rule may be too strict: one sketch outlines the parts inside its head, which the
  first prompt read as a see-through enclosure (85) and the second as not assessable. Whether that counts as a
  clear cue is a judgement the designer should be able to make.
- **Why:** The fit of 41 to 58 looked comparable between sketches but rested on different, partly unjustified
  scores. Showing how much of the importance was judged, and refusing to score what a pencil outline cannot
  show, keeps the number honest. For sketches the tool should tell the designer what to add (colour fills,
  material notes, see-through parts) so that the heaviest traits can be judged.

## 2026-10-18 — Directions: a second request, chosen by code, worded by the model (Person B)

- **What:** After the per-trait judgements, code picks the traits with the biggest gap (importance x (100 - score);
  importance 0 and traits that could not be judged never count) and a second model request words up to 3
  concrete directions for them, each tied to trait ids. The model sees each trait's name, description, score and
  observation, never the importance. Code drops directions that name no trait we sent, orders them by gap and
  numbers them. If the directions request fails, the scores are still returned (with no directions).
- **Why:** The ranking stays traceable to the designer's own importance values, and a failed suggestion step does
  not throw away a successful comparison. It costs one extra request per comparison. A direction is only ever
  tied to a trait that was actually judged, so a pencil sketch gets no direction about colour it could not be
  judged on.
- **Seen on real sketches:** two or three concrete, drawable suggestions per sketch (for example "replace the
  slots with a dense pattern of small round holes"); none for traits that were not assessable.

## 2026-10-18 — Image detail: low gives the same traits as high on this test (Person B)

- **What:** Added the optional `VISION_IMAGE_DETAIL` setting (low, medium, high; sent to Gemini as mediaResolution).
  Ran extraction on the same 12 product screenshots (one real brand, kept local) at each level, twice each, and
  matched the traits by the images they cite. The five core traits came back in both runs at low detail, as they
  did at high; the only trait that differed between levels was a stray one that appeared twice at medium and
  never at high or low. Every run found 5 traits and took 5 to 7 seconds.
- **Why it matters:** low detail costs about a quarter of the image tokens (264 instead of 1,100 per image in an
  earlier measurement), so repeated runs and the reference images in the compare step get cheaper without an
  obvious loss for this kind of material. Caveat: one brand, one image set, two runs per level, and fine
  detail (very small holes) may need medium or high on other material. The default stays unset (Google's default).

## 2026-10-18 — Reference images in the compare step (Person B)

- **What:** With the agreed `reference_images` field the compare request carries the images the traits cite. Per
  trait up to 3 of its evidence images (most relevant first), at most 12 distinct per request, are downloaded
  into memory and shown to the model next to the design; the model judges the image labelled "design" only.
  A reference that cannot be downloaded is skipped, and without the field the step works as before.
- **Result on three sketches (single runs, same model):** scores moved by 5 to 15 points compared with the run
  without references (toaster fit 52 became 64; fly swatter 54 became 52), which is within the run-to-run
  noise we measured earlier, so there is no evidence yet that the references make the scores more accurate.
  The honest gain is inspectability: the same pictures the designer sees as evidence are the ones the AI used.
- **A warning sign:** on the third sketch the perforation trait became "not assessable", leaving only one judged
  trait, and the overall fit showed 92 based on 19% of the total importance. A high fit resting on a small share
  of the importance is misleading, so screens should show a warning when coverage is low (for example below 50%)
  and tell the designer what to add.

## 2026-10-18 — Cost controls: cheap defaults, a ceiling per request, a spending limit (Person B)

- **What:** The Gemini connection now (1) defaults to low image detail and minimal thinking (both can be changed in
  .env, or set to "default" to leave the choice to Google), (2) caps every request at 8,192 output tokens, thinking
  included, (3) records the tokens Google reports for each request and an estimated cost in `usage_ledger.jsonl`
  (kept out of git), and (4) refuses further requests once the recorded spend reaches `VISION_BUDGET_USD`.
  The try scripts print a one-line summary of tokens and cost per run.
- **Measured (one sketch comparison, one real request):** on Flash-Lite thinking was already 0, and low image detail
  cut the input from 2,139 to 1,303 tokens. On the larger Flash model the default used 1,229 thinking tokens
  (billed as output, about 1.7 cents in total); thinking set to minimal removed them and brought the request to about
  0.5 cents. With the new defaults: extraction on 12 screenshots 4,010 tokens in and 733 out, about 0.3 cents; a
  comparison including directions about 0.2 cents on Flash-Lite and 0.8 cents on Flash.
- **Why:** A $5 prepaid budget should cover thousands of Flash-Lite comparisons or several hundred on Flash, and a
  bug or a loop must not be able to spend it. The limit counts only what this code records, as an estimate with
  Google's published prices (checked 2026-10-13), so it complements the spending cap in Google AI Studio rather
  than replacing it.
- **Side result for the report:** on the same sketch the larger Flash model scored the perforation trait 60 where
  Flash-Lite scored 30 (overall fit 67 against 52, both based on 39% of the importance), so the choice of model
  moves the numbers more than the settings above do.

## 2026-10-19 — Interface: the fit is always shown with its coverage (Person C)
- **What:** The overall fit is shown as "based on N% of the importance", with a warning under 50%. Traits that could not be judged are listed separately instead of as empty score rows.
- **Why:** A fit of 45 from 39% of the importance means something different from 45 from 100%. The designer should not read a confident-looking number that rests on a few traits. The 50% warning threshold is our own choice for the demo.

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

## 2026-10-18 — Setting up billing moved the project to prepaid with no credit (Person B)

- **What:** While adding a payment method in Google AI Studio (the card was refused), the project behind our key was
  switched to the prepaid tier. From then on every request answers 402 "Your prepayment credits are depleted" even
  though the free tier had worked an hour earlier. The Gemini connection now maps a 402 to a clear message
  (`vision_no_credit`) instead of a generic "try again".
- **Why it matters:** starting the billing set-up is not harmless: the free allowance is replaced by the prepaid balance,
  so the project is unusable until credit is bought. Before changing billing on a project that is in use, keep a second
  key from a project that stays on the free tier.

## 2026-10-19 — Sourcing flags only AI, fan-made, poor-quality and user-generated images (decided in the integration session; Person A to review)

- **What:** The review flags in `backend/sourcing/flagging.py` no longer depend on whether the image's source website
  matches the brand name or the supplied official site. An image is flagged (and starts unselected) only when its
  metadata suggests it is small or low quality (reported side under 512 px), AI-generated (words such as
  "AI generated", Midjourney, DALL-E in the title, alt text or URL), fan-made or unofficial (fan art, fan-made,
  mock-up, parody, concept art), or user-generated or marketplace content (social networks, image boards, art
  communities, second-hand marketplaces such as eBay). A plain "render" or "CGI" is not flagged any more.
- **Why:** On a live search, 27 of 30 results were flagged because most image search results are retailers and
  magazines, so only 3 images started selected and the extraction rested on 3 images. Retailers, press and the
  brand's own pages are normal sources of reference images; the real risks are fake, fan-made and amateur pictures.
  After the change, 23 of 30 start selected; the 7 flagged were small images and eBay listings.
- **Trade-off:** images of a different company with a similar name (for example a tool maker with the same name as a
  car brand) are no longer flagged by their domain. The relevance estimate still uses the brand words, and the
  designer reviews the images before extraction. Person A can add a lighter signal for this if it becomes a problem.

## 2026-10-19 — The fictional example brand is now called Acme (decided in the integration session)

- **What:** The made-up brand used in the fixtures, the mock mode, the interface, the tests and the docs was renamed to
  "Acme" (with "Acme Tools BV" for the different-company example and `acme-auto.example` for its website). It is a
  plain search-and-replace over 21 files owned by all three of us; no behaviour changed and all tests still pass
  (A 37, B 143).
- **Why:** The earlier invented name looked odd in demos and screenshots. "Acme" is the usual placeholder name, a
  single word like before, so the tests and the brand-word matching behave the same. It is not a real brand, so the
  rule against real brand names in committed files still holds.

## 2026-10-19 — A design can be compared from up to 4 views (Person B, requested in the integration session)

- **What:** `POST /api/compare` takes an optional `additional_design_images` (up to 3) next to `design_image`. The model sees all
  views labelled "design", "design_2", ... and is told they are different views of one design: for each trait it uses the view
  that shows it best, and a trait is "not assessable" only when no view shows it. The directions request sees every view too.
  More than 4 images in total is refused with a clear message. The interface (Person C's file) and the developer page both let
  the designer add up to 3 more views, and a refused extra image no longer triggers a new comparison.
- **Why:** earlier results kept saying "needs a side view to judge". With a front, side and back view more traits can be judged,
  which raises coverage without any change to the scoring.
- **Cost:** each extra view adds about 264 input tokens at low image detail, so four views cost roughly a quarter of a cent more
  than one. A real test with two views gave a comparison and directions for about 0.2 cents.
- **Note:** this is a contract change (`docs/contract-changes.md`) and touches Person C's `frontend/index.html`; both need the team's
  review.

## 2026-10-19 — Three agreed contract fields are built: skipped images, do/don't rules, coverage (Person B)

- **What:** After the team meeting the three open proposals were applied. `POST /api/dna/extract` also returns `skipped_images`
  (every selected image that was not analysed, with the reason: could not be downloaded, wrong file type, too large, or beyond the 20
  most relevant) and `do_dont` (up to 6 design rules; the model is asked to draw each only from the traits it found, and
  incomplete pairs are dropped in code). `POST /api/compare` also returns `coverage`, computed by the same function as before.
  Contract, fixtures and tests are updated together.
- **Why:** The designer should know what the traits are based on (a trait seen in 3 images is weaker when 4 more images were never
  analysed), the House Style Package had an empty "do/don't" section no endpoint filled, and the fit should always be read together
  with how much of the importance could be judged, computed once instead of in every screen.
- **Seen on real images:** 12 screenshots gave 3 do/don't pairs, each matching a found trait; two images that could not be
  downloaded were reported with their reasons while the other 12 still produced traits.
