# Prompt: write your part of the project timeline

Give this to your coding agent (Claude Code or Codex) **after the fact**, in a session inside this repo,
once you have pulled `main` and the timeline folder is there. The agent rebuilds your timeline from the
history, so it comes out in the same shape as everyone else's and can be merged into the master timeline.

Before you start, know your letter (A = Sourcing, B = AI core, C = Interface) and your GitHub username.

---

Copy everything below this line:

```text
You are helping me write my part of the shared project timeline. I am Person <A/B/C> (<role>), my GitHub
username is <username>. The team will merge the three timelines into a master timeline and show it to our
teachers, so the format must be exactly the same for everyone.

1. Read docs/timeline/FORMAT.md completely, and look at docs/timeline/B.csv as a worked example of the style.
   Read AGENTS.md and docs/STATUS.md and docs/decision-log.md too.

2. Reconstruct the story of MY work from the evidence, not from memory:
   - `git log --all --date=format:"%Y-%m-%d %H:%M" --format="%h | %ad | %an | %s"` (my commits and my
     branches), the merged pull requests (`git log --merges`, or the GitHub pull request list), my section
     of docs/STATUS.md, the decisions I logged in docs/decision-log.md and docs/contract-changes.md, and
     anything you remember from our earlier sessions.
   - Include what really happened: milestones, decisions (with the alternatives we rejected and why),
     problems and how we dealt with them, and experiments, including dead ends and negative results.
     The honest story matters more than a clean one.
   - Do NOT invent events, dates, numbers or reasons. If something is not in the history and you are not
     sure, ask me. If you only know the time of the commit that records an event, use that time and say
     "(time approximate)" at the end of `what`.

3. Write docs/timeline/<MY LETTER>.csv exactly in the format of FORMAT.md: header line
   `id,datetime,person,type,title,what,why,links,after`, ids like <MY LETTER>-001, newest at the bottom,
   `person` = my letter on every row, one row per event (merge tiny commits into one row), titles of at most
   60 characters that state the point, plain English a teacher can follow. Use `after` to show what an event
   depends on, also across people (for example A-004 or C-002) when I tell you the dependency is real.
   Write the file with a CSV library or quote fields properly.

4. NO real brand names, logos or scraped content anywhere in the file. Write "a real brand" or "the test
   brand" instead. If you are not sure whether a name is a real brand, leave it out.

5. Run `python docs/timeline/check_timeline.py` and fix every error. Then run it again with
   `--ban "<the real brand names we tested with>"` to prove none slipped in (do not write those names into
   any file, only pass them on the command line).

6. Show me the rows in a table and let me correct them BEFORE you commit.

7. Then, on a new branch `docs/timeline-<letter>`, commit ONLY docs/timeline/<MY LETTER>.csv (touch no other
   file), push it, and tell me how to open a pull request to main. I am new to git, so explain each step
   briefly. Do not push anything until I say so.
```

---

After all three CSVs are on `main`, open the master timeline with
`python -m http.server 8080 --directory docs/timeline` and <http://localhost:8080>.
For later events, ask the agent the same thing again with: "Add everything since the last row of my
timeline file, same rules."
