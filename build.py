#!/usr/bin/env python3
"""Build tracker.html from data/hits.json, data/triage.json and data/bills.json.

triage.json maps an item id to:
  {"material": true|false, "kind": "...", "summary": "1-2 sentences",
   "short": "one line for the top-3 bullets", "importance": 1-5,
   "reg": true if it belongs under Regulations on watch, "stage": "Proposed (Gazette I)"}
bill_notes.json maps a bill number to {"watch", "note", "short", "importance", "topics"}.
Items with no triage entry are shown under "Not yet reviewed".
"""
import datetime as dt, json, os

ROOT = os.path.dirname(os.path.abspath(__file__))
D = lambda f: os.path.join(ROOT, "data", f)


def load(f, default):
    try:
        with open(D(f)) as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default


hits = load("hits.json", {})
triage = load("triage.json", {})
bills = load("bills.json", [])
bill_notes = load("bill_notes.json", {})

items = []
for id_, h in hits.items():
    t = triage.get(id_)
    items.append({
        "id": id_, "date": h["date"], "source": h["source"], "title": h["title"],
        "url": h["url"], "topics": h["topics"],
        "material": t["material"] if t else None,
        "importance": (t or {}).get("importance", 0),   # 1-5, drives the top-3 bullets
        "reg": bool((t or {}).get("reg")),               # shown under Regulations on watch
        "stage": (t or {}).get("stage", ""),             # e.g. "Proposed (Gazette I)", "In force (Gazette II)"
        "short": (t or {}).get("short", ""),             # one-line version for the top-3 bullets
        "kind": (t or {}).get("kind", ""),
        "summary": (t or {}).get("summary") or "",
        "excerpt": "" if t else h["excerpt"][:400],
        "new": h.get("first_seen") == dt.date.today().isoformat(),
    })
items.sort(key=lambda x: (x["date"], x["source"]), reverse=True)

for b in bills:
    n = bill_notes.get(b["bill"], {})
    b["note"] = n.get("note", "")
    b["topics_tag"] = n.get("topics") or sorted(b["terms"])
    b["watch"] = n.get("watch", b["in_title"])
    b["importance"] = n.get("importance", 0)
    b["short"] = n.get("short", "")

# Regulatory items found outside the Gazette (consultations, guidance) can be added by hand
for r in load("regs_extra.json", []):
    r.setdefault("source", "Regulatory"); r.setdefault("material", True); r["reg"] = True
    r.setdefault("excerpt", ""); r.setdefault("new", False); r.setdefault("kind", "")
    items.append(r)
items.sort(key=lambda x: (x["date"], x["source"]), reverse=True)

payload = {"updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "items": items,
           "bills": [b for b in bills if b["watch"]]}

tpl = open(os.path.join(ROOT, "template.html")).read()
out = tpl.replace("/*__DATA__*/null", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"))
# tracker.html: page body for the claude.ai artifact (the artifact host adds <html>/<head>/<body>)
with open(os.path.join(ROOT, "tracker.html"), "w") as f:
    f.write(out)

# index.html: standalone page for GitHub Pages. Everything before the page wrapper goes in <head>.
head, sep, body = out.partition('<div class="wrap">')
standalone = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
              '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
              '<meta name="description" content="Key federal developments on artificial intelligence and the '
              'skilled trades in Canada: bills, regulations, debates and committees, with links to sources.">\n'
              + head.strip() + '\n<style>body{margin:0}</style>\n</head>\n<body>\n' + sep + body + '\n</body>\n</html>\n')
with open(os.path.join(ROOT, "index.html"), "w") as f:
    f.write(standalone)
m = sum(1 for i in items if i["material"])
u = sum(1 for i in items if i["material"] is None)
print(f"tracker.html: {len(items)} items ({m} material, {u} unreviewed), {len(payload['bills'])} bills on watch")
