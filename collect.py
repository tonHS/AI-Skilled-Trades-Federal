#!/usr/bin/env python3
"""Collect federal mentions of artificial intelligence and skilled trades.

Sources (English only):
  - House of Commons debates and committee transcripts (OpenParliament API)
  - House committee meeting notices (ourcommons.ca), for studies that are scheduled
  - Bills in the current session (LEGISinfo JSON)
  - Senate debates and Senate committee meetings and transcripts (sencanada.ca)
  - Canada Gazette Part I and Part II (RSS feed -> issue pages)

Writes data/hits.json: one record per item (a debate topic, a committee meeting,
a bill stage, a Senate section, a Gazette notice). Each record carries the
matched terms, a text excerpt and a link. Deciding what is "material" and
writing the summary happens in a separate triage step (see README.md).

Usage: python3 collect.py --since 2026-10-01
"""
import argparse, datetime as dt, hashlib, html, json, os, re, sys, time
import urllib.request, urllib.error, urllib.parse

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
CACHE = os.path.join(ROOT, "cache")
SESSION = "45-1"           # current Parliament-session; update after a prorogation or election
UA = "federal-policy-tracker/1.0 (personal research script)"

# ---------------------------------------------------------------- keywords
AI_TERMS = [
    (r"artificial intelligence", re.I),
    (r"\bAI\b", 0),  # case-sensitive: avoids "ai" in other words
    (r"machine learning", re.I),
    (r"large language models?", re.I),
    (r"\bdeepfakes?\b", re.I),
    (r"automated decision[- ]making", re.I),
    (r"algorithmic", re.I),
    (r"\bdata cent(?:re|er)s?\b", re.I),
    (r"sovereign (?:compute|cloud)", re.I),
    (r"compute capacity", re.I),
    (r"\bchatbots?\b", re.I),
]
TRADES_TERMS = [
    (r"skilled trades?", re.I),
    (r"\btrades(?:people|person|men|women|workers)\b", re.I),
    (r"\b(?:pre-)?apprentice(?:s|ship|ships)?\b", re.I),
    (r"Red Seal", 0),
    (r"\bjourney(?:person|persons|man|men)\b", re.I),
    (r"Union Training and Innovation Program", re.I),
    (r"labour mobility (?:tax )?deduction", re.I),
    (r"\b(?:electricians?|welders?|pipefitters?|millwrights?|ironworkers?|boilermakers?|plumbers?|carpenters?|steamfitters?)\b", re.I),
    (r"\bbuilding trades\b", re.I),
]
TOPICS = {"ai": [(re.compile(p, f), p) for p, f in AI_TERMS],
          "trades": [(re.compile(p, f), p) for p, f in TRADES_TERMS]}


def match(text):
    """Return {topic: {term: count}} for the text."""
    out = {}
    for topic, pats in TOPICS.items():
        found = {}
        for rx, label in pats:
            n = len(rx.findall(text))
            if n:
                m = rx.search(text).group(0)
                found[m if len(m) < 40 else label] = found.get(m, 0) + n
        if found:
            out[topic] = found
    return out


def excerpt(text, width=700):
    """Excerpt around the densest cluster of matches."""
    spans = []
    for pats in TOPICS.values():
        for rx, _ in pats:
            spans += [m.start() for m in rx.finditer(text)]
    if not spans:
        return text[:width]
    spans.sort()
    best, bestn = spans[0], 0
    for s in spans:
        n = sum(1 for t in spans if s <= t < s + width)
        if n > bestn:
            best, bestn = s, n
    start = max(0, best - 150)
    return ("…" if start else "") + text[start:start + width].strip() + "…"


# ---------------------------------------------------------------- fetching
def fetch(url, cache=True, accept=None, tries=3):
    key = hashlib.sha1(url.encode()).hexdigest()
    path = os.path.join(CACHE, key)
    if cache and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    headers = {"User-Agent": UA}
    if accept:
        headers["Accept"] = accept
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=40) as r:
                body = r.read().decode("utf-8", errors="replace")
            if cache:
                os.makedirs(CACHE, exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(body)
            time.sleep(0.3)
            return body
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if i == tries - 1:
                log(f"  ! {e.code} {url}")
                return None
        except Exception as e:  # network hiccup
            if i == tries - 1:
                log(f"  ! {e} {url}")
                return None
        time.sleep(2 * (i + 1))


def op_json(path, cache=False):
    url = path if path.startswith("http") else "https://api.openparliament.ca" + path
    body = fetch(url, cache=cache, accept="application/json")
    return json.loads(body) if body else None


def strip_tags(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>", "\n", s, flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\n\s*\n+", "\n", s)).strip()


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def rec(id_, source, date, title, url, text, extra=None):
    m = match(text)
    if not m:
        return None
    r = {"id": id_, "source": source, "date": date, "title": title, "url": url,
         "topics": sorted(m), "terms": m, "excerpt": excerpt(text)}
    if extra:
        r.update(extra)
    return r


# ---------------------------------------------------------------- House debates
def house_debates(since):
    log("House debates…")
    groups = {}
    nxt = f"/speeches/?time__gte={since}&limit=500"
    while nxt:
        d = op_json(nxt)
        if not d:
            break
        for s in d["objects"]:
            if not s["document_url"].startswith("/debates/"):
                continue
            h1 = (s.get("h1") or {}).get("en") or ""
            h2 = (s.get("h2") or {}).get("en") or ""
            k = (s["document_url"], h1, h2)
            g = groups.setdefault(k, {"date": s["time"][:10], "speeches": []})
            g["speeches"].append(s)
        nxt = d["pagination"]["next_url"]
    out = []
    for (doc, h1, h2), g in groups.items():
        texts, speakers, first_url = [], [], None
        for s in sorted(g["speeches"], key=lambda s: s["time"]):
            t = strip_tags(s["content"]["en"])
            if match(t):
                texts.append(f"{s['attribution']['en']}: {t}")
                speakers.append(s["attribution"]["en"])
                first_url = first_url or s["url"]
        if not texts:
            continue
        title = " — ".join(x for x in (h1, h2) if x) or "House debate"
        r = rec("house:" + doc + h1 + h2, "House debates", g["date"], title,
                "https://openparliament.ca" + first_url, "\n".join(texts),
                {"speakers": sorted(set(speakers))[:8], "n_speeches": len(texts)})
        if r:
            out.append(r)
    log(f"  {len(out)} topic hits")
    return out


# ---------------------------------------------------------------- House committees
COMMITTEE_NAMES = {}


def committee_name(slug_url):
    if slug_url not in COMMITTEE_NAMES:
        d = op_json(slug_url, cache=True)
        COMMITTEE_NAMES[slug_url] = d["name"]["en"] if d else slug_url.strip("/").split("/")[-1]
    return COMMITTEE_NAMES[slug_url]


def house_committees(since):
    log("House committees…")
    out = []
    off = 0
    meetings = []
    while True:
        d = op_json(f"/committees/meetings/?limit=100&offset={off}")
        if not d or not d["objects"]:
            break
        meetings += d["objects"]
        if d["objects"][-1]["date"] < since:
            break
        off += 100
    meetings = [m for m in meetings if m["date"] >= since]
    for m in meetings:
        name = committee_name(m["committee_url"])
        detail = op_json(m["url"], cache=m["has_evidence"])
        if not detail:
            continue
        # Notice of meeting: what the committee is studying, and witnesses
        notice = detail.get("notice_url")
        if notice:
            body = fetch(notice, cache=m["date"] < str(dt.date.today()))
            if body:
                main = re.search(r"<main.*?</main>", body, re.S)
                t = strip_tags(main.group(0) if main else body)
                r = rec(f"notice:{m['url']}", "Committee notice", m["date"],
                        f"{name} — meeting {m['number']} (notice)", notice, t,
                        {"committee": name, "upcoming": m["date"] > str(dt.date.today())})
                if r:
                    out.append(r)
        if not m["has_evidence"]:
            continue
        texts, first_url, speakers = [], None, []
        nxt = "/speeches/?document=" + urllib.parse.quote(m["url"], safe="") + "&limit=500"
        while nxt:
            d = op_json(nxt, cache=True)
            if not d:
                break
            for s in d["objects"]:
                t = strip_tags(s["content"]["en"])
                if match(t):
                    texts.append(f"{s['attribution']['en']}: {t}")
                    speakers.append(s["attribution"]["en"])
                    first_url = first_url or s["url"]
            nxt = d["pagination"]["next_url"]
        if texts:
            r = rec(f"cttee:{m['url']}", "Committee evidence", m["date"],
                    f"{name} — meeting {m['number']}",
                    "https://openparliament.ca" + (first_url or m["url"]), "\n".join(texts),
                    {"committee": name, "speakers": sorted(set(speakers))[:8], "n_speeches": len(texts)})
            if r:
                out.append(r)
    log(f"  {len(out)} meeting hits from {len(meetings)} meetings")
    return out


# ---------------------------------------------------------------- Bills
STAGES = [("PassedHouseFirstReadingDateTime", "First reading (House)"),
          ("PassedHouseSecondReadingDateTime", "Second reading (House)"),
          ("PassedHouseThirdReadingDateTime", "Third reading (House)"),
          ("PassedSenateFirstReadingDateTime", "First reading (Senate)"),
          ("PassedSenateSecondReadingDateTime", "Second reading (Senate)"),
          ("PassedSenateThirdReadingDateTime", "Third reading (Senate)"),
          ("ReceivedRoyalAssentDateTime", "Royal Assent")]


def bills(since):
    log("Bills…")
    body = fetch(f"https://www.parl.ca/legisinfo/en/bills/json?parlsession={SESSION}", cache=False)
    out, watch = [], []
    if not body:
        return out
    for b in json.loads(body):
        num = b["NumberCode"]
        head = " ".join(filter(None, [b.get("LongTitleEn"), b.get("ShortTitleEn"),
                                      strip_tags(b.get("ShortLegislativeSummaryEn") or "")]))
        # Full first-reading text (cached forever: the first-reading text never changes)
        full = fetch(f"https://www.parl.ca/DocumentViewer/en/{SESSION}/bill/{num}/first-reading") or ""
        main = re.search(r'<main class="publication".*?</main>', full, re.S)
        text = head + "\n" + strip_tags(main.group(0) if main else full)
        in_title = match(head)
        m = match(text)
        if not m:
            continue
        url = f"https://www.parl.ca/legisinfo/en/bill/{SESSION}/{num.lower()}"
        title = f"Bill {num}: {b.get('ShortTitleEn') or b['LongTitleEn']}"
        status = b.get("StatusNameEn") or ""
        extra = {"status": status, "bill": num, "government_bill": b.get("IsGovernmentBill"),
                 "in_title": bool(in_title), "long_title": b["LongTitleEn"],
                 "sponsor": (b.get("SponsorPersonName") or "").strip()}
        watch.append({"bill": num, "title": title, "url": url, "status": status,
                      "latest_event": b.get("LatestBillEventTypeNameEn"),
                      "latest_event_date": (b.get("LatestBillEventDateTime") or "")[:10],
                      "terms": m, "in_title": bool(in_title),
                      "government_bill": b.get("IsGovernmentBill"), "sponsor": extra["sponsor"]})
        events = [(b.get(f), s, f) for f, s in STAGES]
        ev = b.get("LatestBillEventTypeNameEn")
        if ev:
            cd = b.get("LatestBillEventCommitteeDetails") or {}
            cname = cd.get("CommitteeNameEn") if isinstance(cd, dict) else None
            events.append((b.get("LatestBillEventDateTime"), ev + (f" — {cname}" if cname else ""), "event:" + ev))
        for v, stage, key in events:
            if v and v[:10] >= since and not v.startswith("0001"):
                out.append(rec(f"bill:{num}:{key}", "Bills", v[:10], title, url, text,
                               dict(extra, stage=stage)))
    with open(os.path.join(DATA, "bills.json"), "w") as f:
        json.dump(watch, f, indent=1, ensure_ascii=False)
    log(f"  {len(watch)} relevant bills, {len(out)} stage events")
    return out


# ---------------------------------------------------------------- Senate debates
def senate_debates(since):
    log("Senate debates…")
    out = []
    idx = fetch("https://sencanada.ca/en/in-the-chamber/debates/", cache=False) or ""
    m = re.search(r"/en/content/sen/chamber/(\d+)/debates/(\d+)db_(\d{4}-\d\d-\d\d)-e", idx)
    if not m:
        log("  ! could not find latest Senate sitting")
        return out
    parl, issue, date = m.group(1), int(m.group(2)), dt.date.fromisoformat(m.group(3))
    sittings = [(issue, date)]
    # Walk back issue by issue; each earlier issue is on an earlier date.
    while date.isoformat() > since and issue > 1:
        issue -= 1
        found = False
        for back in range(1, 60):
            d = date - dt.timedelta(days=back)
            if d.isoformat() < since:
                break
            url = f"https://sencanada.ca/en/content/sen/chamber/{parl}/debates/{issue:03d}db_{d}-e"
            page = fetch(url)  # the site answers 200 for missing sittings, so check the issue number
            if page and re.search(rf"Issue {issue}\s*<", page):
                sittings.append((issue, d)); date = d; found = True
                break
        if not found:
            break
    for issue, d in sittings:
        if d.isoformat() < since:
            continue
        url = f"https://sencanada.ca/en/content/sen/chamber/{parl}/debates/{issue:03d}db_{d}-e"
        body = fetch(url, cache=d < dt.date.today() - dt.timedelta(days=7))
        if not body:
            continue
        parts = re.split(r'(<h2 id="\d+"[^>]*>.*?</h2>)', body, flags=re.S)
        for i in range(1, len(parts) - 1, 2):
            head = strip_tags(parts[i])
            aid = re.search(r'id="(\d+)"', parts[i]).group(1)
            t = strip_tags(parts[i + 1])
            r = rec(f"senate:{issue}:{aid}", "Senate debates", d.isoformat(),
                    head or "Senate debate", f"{url}#{aid}", t)
            if r:
                out.append(r)
    log(f"  {len(out)} section hits from {len(sittings)} sittings")
    return out


# ---------------------------------------------------------------- Senate committees
def senate_committees(since):
    """Senate committee meetings: the study or bill and witnesses listed for each meeting
    (past and upcoming), plus the transcript ("evidence") once it is posted."""
    log("Senate committees…")
    out = []
    base = "https://sencanada.ca/umbraco/surface/CommitteesAjax/GetTablePartialView"
    rows = []
    for tab, order in (("PAST", "DATEDESC"), ("UPCOMING", "DATEASC")):
        q = urllib.parse.urlencode({"tableName": "Meetings", "committeeId": 0, "Lang": "en",
                                    "TabSelected": tab, "session": SESSION, "PageSize": 250,
                                    "SortOrder": order})
        body = fetch(f"{base}?{q}", cache=False) or ""
        rows += re.findall(r"<tr.*?</tr>", body, re.S)[1:]
    seen = set()
    for row in rows:
        dm = re.search(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{4})", strip_tags(row))
        notice = re.search(r'href="(/en/committees/[^"]+/noticeofmeeting/(\d+)/[^"]+)"', row)
        if not dm or not notice or notice.group(2) in seen:
            continue
        seen.add(notice.group(2))
        date = dt.datetime.strptime(" ".join(dm.groups()), "%b %d %Y").date().isoformat()
        if date < since:
            continue
        cells = [strip_tags(c) for c in re.findall(r"<td.*?</td>", row, re.S)]
        cells = [c for c in cells if c]
        committee = cells[1] if len(cells) > 1 else "Senate committee"
        text = strip_tags(row)
        # What the meeting is about, and who appears (meeting notice)
        r = rec(f"sen-notice:{notice.group(2)}", "Senate committee notice", date,
                f"Senate {committee} — {date} (notice)", "https://sencanada.ca" + notice.group(1), text,
                {"committee": committee, "upcoming": date > str(dt.date.today())})
        if r:
            out.append(r)
        ev = re.search(r'href="(/en/content/sen/committee/\d+/\w+/\d+ev-\d+-e)"', row)
        if ev:
            body = fetch("https://sencanada.ca" + ev.group(1)) or ""
            main = re.search(r'<main.*?</main>', body, re.S)
            t = strip_tags(main.group(0) if main else body)
            r = rec(f"sen-cttee:{ev.group(1)}", "Senate committee evidence", date,
                    f"Senate {committee} — {date}", "https://sencanada.ca" + ev.group(1), t,
                    {"committee": committee})
            if r:
                out.append(r)
    log(f"  {len(out)} hits from {len(seen)} meetings")
    return out


# ---------------------------------------------------------------- Canada Gazette
def gazette(since):
    log("Canada Gazette…")
    out = []
    for part in ("p1", "p2"):
        rss = fetch(f"https://gazette.gc.ca/rss/{part}-eng.xml", cache=False) or ""
        issues = re.findall(r"<link>(https://gazette\.gc\.ca/rp-pr/%s/\d{4}/(\d{4}-\d\d-\d\d)[^<]*/index-eng\.html)</link>" % part, rss)
        for idx_url, date in issues:
            if date < since:
                continue
            idx = fetch(idx_url) or ""
            base = idx_url.rsplit("/", 1)[0] + "/"
            pages = sorted(set(re.findall(r'href="(?:\./)?([a-z0-9-]+-eng\.html)"', idx)) - {"index-eng.html"})
            for p in pages:
                body = fetch(base + p) or ""
                main = re.search(r'<main.*?</main>', body, re.S)
                body = main.group(0) if main else body
                h1 = strip_tags((re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S) or [None, ""])[1])
                # Split into notices at h2 headings with ids (Part I), else treat whole page as one item (Part II reg).
                parts = re.split(r'(<h2 id="[^"]+"[^>]*>.*?</h2>)', body, flags=re.S)
                if len(parts) > 1:
                    for i in range(1, len(parts) - 1, 2):
                        aid = re.search(r'id="([^"]+)"', parts[i]).group(1)
                        sub = re.search(r"<h3[^>]*>(.*?)</h3>", parts[i + 1], re.S)
                        head = strip_tags(parts[i]) + (" — " + strip_tags(sub.group(1)) if sub else "")
                        r = rec(f"gazette:{part}:{date}:{p}:{aid}", f"Canada Gazette {part.upper().replace('P', 'Part ')}",
                                date, head, f"{base}{p}#{aid}", strip_tags(parts[i + 1]))
                        if r:
                            out.append(r)
                else:
                    r = rec(f"gazette:{part}:{date}:{p}", f"Canada Gazette {part.upper().replace('P', 'Part ')}",
                            date, h1.split(":", 1)[-1].strip() or p, base + p, strip_tags(body))
                    if r:
                        out.append(r)
    log(f"  {len(out)} notice hits")
    return out


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=(dt.date.today() - dt.timedelta(days=14)).isoformat())
    ap.add_argument("--only", nargs="*", help="house committees bills senate senate_committees gazette")
    a = ap.parse_args()
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, "hits.json")
    existing = json.load(open(path)) if os.path.exists(path) else {}
    runners = {"house": house_debates, "committees": house_committees, "bills": bills,
               "senate": senate_debates, "senate_committees": senate_committees, "gazette": gazette}
    new = 0
    for name, fn in runners.items():
        if a.only and name not in a.only:
            continue
        try:
            for r in fn(a.since):
                if r["id"] not in existing:
                    r["first_seen"] = dt.date.today().isoformat()
                    new += 1
                else:
                    r["first_seen"] = existing[r["id"]].get("first_seen")
                existing[r["id"]] = r
        except Exception as e:
            log(f"  ! {name} failed: {e!r}")
    with open(path, "w") as f:
        json.dump(existing, f, indent=1, ensure_ascii=False)
    log(f"Done: {new} new items, {len(existing)} total -> {path}")


if __name__ == "__main__":
    main()
