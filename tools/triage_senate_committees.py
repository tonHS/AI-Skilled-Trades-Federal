"""Run from the repo root. One-off: triage of Senate committee items added 2026-11-24. Unlisted new items become passing mentions."""
import json
S = "sen-cttee:/en/content/sen/committee/451/"
M = {
 S+"soci/53ev-57899-e": ("Committee study", 4,
   "AI Minister Evan Solomon appears before the Senate Social Affairs committee's AI study. An ISED official says the 100,000 Red Seal placements complement the 90,000 placements in the AI for All strategy.",
   "AI Minister at Senate AI study; officials pair 100,000 Red Seal placements with 90,000 AI for All placements."),
 S+"soci/56ev-57945-e": ("Committee study", 2,
   "Senate Social Affairs AI study hears from CIGI's Global AI Risks Initiative and others, including on bringing AI into government consultations with civil society.", ""),
 S+"soci/57ev-57953-e": ("Committee study", 2,
   "Senate Social Affairs AI study hears from Nicolas Papernot, co-director of the Canadian AI Safety Institute research program at CIFAR, and other experts.", ""),
 "sen-notice:710268": ("Committee study", 1,
   "Senate Social Affairs AI study continues, with the Machine Intelligence Research Institute's CEO and Avi Goldfarb (Rotman) among witnesses.", ""),
 "sen-notice:710396": ("Committee study", 2,
   "Upcoming at the Senate Social Affairs AI study: the Canadian Labour Congress, Ajay Agrawal and Wendy Cukier, on AI and work.", ""),
 "sen-notice:710604": ("Committee study", 1,
   "Upcoming at the Senate Social Affairs AI study: Valerio De Stefano (Osgoode) and Karen Hughes (University of Alberta).", ""),
 "sen-notice:706881": ("Committee report", 3,
   "Senate Human Rights committee is drafting its report on AI's impact on human rights and economic security, including vulnerable groups and the right to work.",
   "Senate Human Rights committee drafting report on AI, human rights and the right to work."),
 "sen-notice:709480": ("Committee report", 3,
   "Senate Transport and Communications committee is drafting its report on the opportunities and challenges of AI in the ICT sector.",
   "Senate Transport committee drafting report on AI in the ICT sector."),
 S+"cscf/04ev-57929-e": ("Bill in committee", 2,
   "Canada's Building Trades Unions tell the Senate special committee on the Building Canada Strong Act that UTIP funding is expanding training centres, but apprentices also need work on projects.", ""),
 S+"ollo/28ev-57959-e": ("Committee study", 2,
   "Witnesses tell the Senate Official Languages committee that AI was trained on writers' uncompensated work and is undermining their income.", ""),
 S+"aefa/49ev-57950-e": ("Committee study", 2,
   "A witness at Senate Foreign Affairs notes that Cohere is merging with a German company to build a larger AI firm.", ""),
}
hits = json.load(open("data/hits.json")); tri = json.load(open("data/triage.json"))
assert all(k in hits for k in M), [k for k in M if k not in hits]
n = 0
for k in hits:
    if k in tri: continue
    if k in M:
        kind, imp, s, sh = M[k]; tri[k] = {"material": True, "kind": kind, "importance": imp, "summary": s, "short": sh}
    else:
        tri[k] = {"material": False, "kind": "Passing mention", "importance": 0, "summary": ""}
    n += 1
json.dump(tri, open("data/triage.json", "w"), indent=1, ensure_ascii=False)
print(n, "triaged,", len(M), "key")
