# AI & Skilled Trades Federal Tracker — update instructions for Claude

This repo publishes a public GitHub Pages site (https://tonhs.github.io/AI-Skilled-Trades-Federal/)
listing key federal developments on artificial intelligence and the skilled trades: bills,
regulations, House and Senate debates, and House and Senate committees, each with a 1–2 line
summary and a link to the source. A private copy is also published on claude.ai
(https://claude.ai/artifact/2Lix9wPGTAcpqMVGi5yDWY).

When Kate asks to "refresh the federal tracker" (or similar), follow the routine below.

## Files

- `collect.py` — pulls new items from every source into `data/hits.json` (English only, no API key).
- `data/hits.json` — every item found: source, date, title, link, matched terms, excerpt.
- `data/triage.json` — Claude's judgement on each item (see the rules below). This is the content to edit.
- `data/bills.json` — written by `collect.py`: every bill in the session whose text matches.
- `data/bill_notes.json` — which bills are on watch, with a note, a one-liner and an importance score.
- `data/regs_extra.json` (optional) — regulatory items found outside the Gazette, added by hand.
- `template.html` — page design and rendering code. Do not edit for routine updates.
- `build.py` — writes `index.html` (GitHub Pages) and `tracker.html` (claude.ai artifact) from the data.
- `.nojekyll` — keeps GitHub Pages from processing the site. Leave it.
- `tools/` — one-off triage scripts from the first build, kept as a record.
- `cache/` — downloaded pages; not committed (see `.gitignore`).

## Update routine

1. **Collect:** `python3 collect.py --since <last Updated date minus 7 days>`. The page's "Updated"
   date is in `index.html`. The 7-day overlap catches committee transcripts posted late; items
   already in `hits.json` keep their triage.
2. **Triage** every item in `data/hits.json` that has no entry in `data/triage.json`, using the
   rules below. Open the link when the excerpt is not enough. Update `data/bill_notes.json` for any
   bill whose stage changed, and add newly relevant bills.
3. **Build:** `python3 build.py`, and check the counts it prints. If possible, open `index.html`
   and confirm the page renders.
4. **Show Kate a short summary** of the new key developments (title, one line, link), bill stage
   changes and any regulations added, before committing. Then commit with a message like
   `Update tracker to YYYY-MM-DD: <main changes>` and push to `main`. Pages republishes in a minute
   or two. Republish `tracker.html` to the claude.ai link too, only after Kate's OK.

## Triage rules

Each entry in `triage.json` is
`{"material", "kind", "importance" 1-5, "summary", "short", "reg", "stage"}`.

An item is a **key development** (`"material": true`) when it is one of these:
- a bill stage (introduced, reading, committee, clause-by-clause, report, Royal Assent);
- a government announcement or new figure (program, funding, strategy, start date), including one first stated in Question Period or debate;
- a committee meeting held for a study that is about AI or the trades (one item per meeting with evidence; for in-camera draft-report meetings, keep only the latest notice);
- a Senate motion or order on an AI or trades study, or a pointed Senate question on Canada's position;
- a petition, or a sharp opposition line that introduces a new fact;
- a Gazette notice or regulation that actually concerns AI or the trades (set `"reg": true` and a `"stage"` such as "Proposed (Gazette I)" or "In force (Gazette II)").

Everything else is a passing mention (`"material": false, "kind": "Passing mention"`): a word dropped in a speech, a witness aside, a notice duplicating a meeting that has its transcript.

Importance: 5 = law, money or a bill moving; 4 = new program or funding; 3 = committee report or a
notable witness or allegation; 2 = an ordinary study meeting or exchange; 1 = study continuing.
The top 3 in each section come from this score. `summary` is 1–2 sentences saying only what the
source says; `short` is the one-liner for the top-3 bullets (leave it empty below importance 3).

## Sources

- House debates and committee transcripts: api.openparliament.ca
- House committee notices: ourcommons.ca (linked from each meeting)
- Bills: LEGISinfo JSON plus the full first-reading text from parl.ca
- Senate debates, and Senate committee meetings (topic, witnesses, transcripts): sencanada.ca
- Canada Gazette Parts I and II: RSS feeds, then each issue's pages

Not covered yet: ministers' news releases.
Edit `SESSION` in `collect.py` after a prorogation or election.
