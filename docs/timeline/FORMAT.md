# Project timeline — the shared format

Each of us keeps **one CSV file with our own events**: `A.csv`, `B.csv`, `C.csv` (the letter of your role).
The web page in this folder merges them into the **master timeline** and draws the flowchart. Nobody edits
anyone else's file, so there are no merge conflicts.

## See the master timeline

From the repo root:

```bash
python -m http.server 8080 --directory docs/timeline
```

Open <http://localhost:8080>. The page re-reads the files every few seconds, so when a CSV changes the
flowchart updates by itself. (Opening `index.html` by double-click does not work: browsers block it from
reading the CSV files. If the repo is published with GitHub Pages, the same page works there for teachers.)

## Columns (exactly these nine, in this order, with this header line)

```
id,datetime,person,type,title,what,why,links,after
```

| Column | Meaning |
|---|---|
| `id` | Your letter, a dash, and a 3-digit number: `B-001`, `B-002`, … Unique, never reused. |
| `datetime` | When it happened, `YYYY-MM-DD HH:MM` (24 h, local time). Take it from `git log` when the event is a commit. If you only know the time of the commit that records it, use that and end `what` with "(time approximate)". |
| `person` | Who did it: `A`, `B` or `C`. Must equal the letter of the file it is in. |
| `type` | `milestone`, `decision`, `problem` or `experiment` (see below). |
| `title` | Max 60 characters. This is the label in the flowchart: say the point, not the topic. |
| `what` | 1–3 plain sentences: what happened. Facts and numbers, no hype. |
| `why` | Why it matters. For a decision: the reasoning and the alternatives rejected. For a problem: how it was solved or worked around. For an experiment: what it showed. May be empty for a milestone. |
| `links` | Where to look: commit hashes, pull request URLs, repo paths such as `docs/decision-log.md`, separated by `;`. |
| `after` | Ids of the earlier events this one follows from or depends on, separated by `;`. Can point at other people's ids (e.g. `A-004`). Leave empty if it simply follows your previous row. |

Quote any field that contains a comma or a line break with double quotes (a spreadsheet program or Python's
`csv` module does this for you).

## The four types

- **milestone**: something that now works or is merged (a pipeline, a screen, a merged pull request).
- **decision**: we chose between options. Always give the reasoning and say what was rejected.
- **problem**: something broke, blocked us or surprised us, and what we did about it. Keep these; they are
  the honest story of how development really went.
- **experiment**: we tried something to find out. Say what was tried and what it showed, including
  results that were negative.

## Rules

1. **No real brand names, logos or scraped content.** Write "a real brand" or "the test brand". Fictional
   brand names are fine. (`AGENTS.md` forbids real brand names in committed files.)
2. **Never invent an event or a date.** If you are unsure, ask your human, or leave the event out.
3. **Newest rows at the bottom**, in time order. One row per event, not per commit: merge small commits.
4. Write in plain English that a teacher who has not seen the code can follow.

## Check your file

```bash
python docs/timeline/check_timeline.py
```

It checks every CSV in this folder (header, ids, dates, types, links between files) and exits with an error
if something is wrong. To make sure no brand name slipped in, pass the names at run time, e.g.
`python docs/timeline/check_timeline.py --ban "Some Brand,Other Brand"` (do not write them into any file).

## Examples (from `B.csv`)

```
B-001,2026-10-05 15:12,B,milestone,Repo skeleton built,"Created the shared skeleton ...","Lets all three of us start in parallel ...",fa07dfb,
B-005,2026-10-07 09:57,B,decision,Weighing is done in code never by the model,"The model only judges single traits; ...","Anyone can trace a number back ...",docs/decision-log.md,B-004
B-014,2026-10-07 11:04,B,problem,Chosen model was closed to new accounts (404),"The first default model answered 404 ...","Model names change often ...",951c06a,B-013
```
