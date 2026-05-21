#!/usr/bin/env python3
"""Morning Brief CLI — full CX Pulse report with resolved/created today + account consolidation."""

import json, os, sys, datetime, urllib.request, math
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

TOKEN = os.environ.get("DEVREV_TOKEN", "")
API = "https://api.devrev.ai"
TODAY = datetime.date.today()
TODAY_STR = TODAY.isoformat()
NOW = datetime.datetime.now()
SEVEN_DAYS_AGO = (TODAY - datetime.timedelta(days=7)).isoformat()

# ── CX Lead name resolution ──
DEVU_MAP = {
    "devu/1327": "Gangesh Pandey", "devu/2573": "Saurabh Singh", "devu/901": "Sachin Shivhare",
    "devu/2585": "Laxmi Rajput", "devu/1088": "Deepanshu Marwari", "devu/2580": "Vikas Pandey",
    "devu/2976": "Srijan Srivastava", "devu/1246": "Vinod Kumar Gunda", "devu/3000": "Kaustuv Choudhary",
    "devu/1314": "Vidushi Wanchoo", "devu/2636": "Asif Khan", "devu/2978": "Medha Saxena",
    "devu/1090": "Madhav Kapoor", "devu/2934": "Abhishek Bhandari", "devu/3007": "Bhavyank Sarolia",
    "devu/2744": "Omi Vaish", "devu/2647": "Pakhi Vashishth", "devu/3063": "Tejal Shirsat",
    "devu/2676": "SKG/Sumit Gupta", "devu/3091": "Gaurav Singh",
    "devu/2626": "Shajiya Shaik", "devu/1885": "Shipsy Support", "devu/863": "Akash KumarRajek",
    "devu/899": "Yash Singh", "devu/1009": "Sana Amreen", "devu/1607": "Amit Dubey",
    "devu/2944": "Bhanu Arya", "devu/2632": "Nikhila K",
}

# ── Account consolidation ──
# Explicit alias → parent mapping (lowercased keys)
ACCOUNT_ALIASES = {
    # Reliance group
    "reliance (ril)": "Reliance", "ril": "Reliance", "reliance": "Reliance",
    "reliancehyperlocal": "Reliance", "ril-tira": "Reliance",
    "1p jiomart reliance": "Reliance", "reliance - 3p": "Reliance",
    "qwik logistics": "Reliance", "rcpldemo": "Reliance",
    # DTDC
    "dtdc": "DTDC", "dtdc.in": "DTDC",
    # Aramex group
    "aramex global": "Aramex", "aramex vw": "Aramex", "aramex move": "Aramex",
    "aramex same day delivery": "Aramex", "aramex ro": "Aramex",
    "aramex oceania": "Aramex", "aramex freight": "Aramex", "aramex": "Aramex",
    "aramex sdd": "Aramex",
    # Flipkart
    "flipkart": "Flipkart", "fkfooddemo": "Flipkart",
    # Rozana
    "rozana": "Rozana", "rozanaondemand": "Rozana",
    # Wellness Forever
    "wellness forever": "Wellness Forever", "wellness forever (tms)": "Wellness Forever",
    "[wms] wellness forever": "Wellness Forever",
    # Milkbasket
    "milkbasket": "Milkbasket",
    # Kama Ayurveda
    "kama ayurveda": "Kama Ayurveda",
    # Movin
    "movin": "Movin", "movin1demo": "Movin", "movindemo": "Movin",
    # Apollo247
    "apollo247": "Apollo247",
    # Spencers
    "spencers": "Spencers",
    # Heineken
    "hnk-br1-primary": "Heineken", "hnk-br1-secondary": "Heineken",
    # Myntra
    "myntra": "Myntra", "myntrahl": "Myntra",
    # Swiggy
    "swiggy": "Swiggy", "swiggytms": "Swiggy",
    # Proconnect
    "proconnect": "Proconnect", "proconnect account": "Proconnect",
    # Wakefit
    "wakefit": "Wakefit", "wakefitdemo": "Wakefit",
    # Box
    "box account": "Box", "box": "Box",
    # Others with demo suffix
    "expeditorsdemo": "Expeditors", "expeditors": "Expeditors",
    "asterksademo": "Aster KSA", "desquareddemo": "DeSquared",
    "teleportdemo": "Teleport", "latamdemo": "LATAM",
    "movin1demo": "Movin",
    # Healthkart
    "healthkart": "Healthkart",
    # Field
    "field": "Field",
    # Incnut
    "incnut": "Incnut",
    # nxlogistics
    "nxlogistics": "NX Logistics",
    # Caratlane
    "caratlane": "CaratLane",
    # SBT
    "sbt": "SBT",
    # iwexpress
    "iwexpress": "IW Express",
    # frontline
    "frontline": "Frontline",
    # [WMS] Shipsy
    "[wms] shipsy": "[WMS] Shipsy",
}

def normalize_account(raw_name):
    if not raw_name or raw_name == "Unknown":
        return "Unknown"
    name = raw_name.strip()
    # Step 1: Strip " - Default Workspace"
    if name.endswith(" - Default Workspace"):
        name = name[:-len(" - Default Workspace")]
    # Step 2: Strip " Account" suffix
    if name.endswith(" Account"):
        name = name[:-len(" Account")]
    # Step 3: Check alias map (case-insensitive)
    key = name.lower().strip()
    if key in ACCOUNT_ALIASES:
        return ACCOUNT_ALIASES[key]
    # Step 4: Return cleaned name
    return name

# ── Constants ──
EXCLUDE_COHORTS = {"WMS", "Roadmap"}
NOT_TRIAGED = {"queued", "TKT Backlog", "Reassigned to Customer Support"}
ABBREV = {
    "queued": "Queued", "work_in_progress": "WIP", "awaiting_customer_response": "AwCust",
    "awaiting_development": "AwDev", "awaiting_product_assist": "AwProd",
    "in_development": "InDev", "Reassigned to Customer Support": "Reassigned",
    "Reopen": "Reopen", "TKT Backlog": "Backlog", "Need Product Sprint Planning": "NeedSprint",
    "scoping_in_progress": "Scoping", "dev_in_progress": "DevIP",
    "Need Governance": "NeedGov", "To be Initiated": "ToInit",
}
TIER1 = {"1-Reliance", "1-DTDC"}
TIER2 = {"2-Aramex", "2-HNK"}
ROSTER = {
    "Vidushi Wanchoo": ("10:30 AM-07:30 PM", "ON"), "Vinod Kumar Gunda": ("10:30 AM-07:30 PM", "ON"),
    "Madhav Kapoor": ("10:30 AM-07:30 PM", "ON"), "Deepanshu Marwari": ("12:00 PM-09:00 PM", "ON"),
    "Vikas Pandey": ("09:00 PM-06:00 AM", "ON"), "Asif Khan": ("WO", "OFF"),
    "Medha Saxena": ("08:30 AM-05:30 PM", "ON"), "Laxmi Rajput": ("08:30 AM-05:30 PM", "ON"),
    "Kaustuv Choudhary": ("10:30 AM-07:30 PM", "ON"), "Srijan Srivastava": ("10:30 AM-07:30 PM", "ON"),
    "Saurabh Singh": ("WO", "OFF"), "Gangesh Pandey": ("10:30 AM-07:30 PM", "ON"),
}

# ── Helpers ──
def apicall(endpoint, payload):
    d = json.dumps(payload).encode()
    r = urllib.request.Request(f"{API}/{endpoint}", data=d,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read().decode(), strict=False)

def cx(t):
    a = t.get("custom_fields", {}).get("tnt__assignee", "")
    if not a: return "Unassigned"
    if "devu/" in a: return DEVU_MAP.get("devu/" + a.split("devu/")[-1], f'DEVU-{a.split("/")[-1]}')
    return "Unknown"

def cohort(t): return t.get("custom_fields", {}).get("tnt__customer_cohort_dropdown", "") or "TBD"
def stage(t): return t.get("stage", {}).get("name", "?")
def sev(t): return (t.get("severity") or "?").lower()
def acct(t): return normalize_account((t.get("rev_org") or {}).get("display_name", "Unknown"))
def acct_raw(t): return (t.get("rev_org") or {}).get("display_name", "Unknown")
def age(t):
    c = t.get("created_date", "")
    if not c: return 0
    try: return (NOW - datetime.datetime.fromisoformat(c.replace("Z", "+00:00")).replace(tzinfo=None)).days
    except: return 0
def mod_age(t):
    m = t.get("modified_date", "")
    if not m: return 999
    try: return (NOW - datetime.datetime.fromisoformat(m.replace("Z", "+00:00")).replace(tzinfo=None)).days
    except: return 999
def owner(t):
    o = t.get("owned_by", [])
    return o[0].get("display_name", "?") if o else "?"

def timeline(tid):
    try: return apicall("timeline-entries.list", {"object": tid, "limit": 20}).get("timeline_entries", [])
    except: return []

def classify_rca(entries):
    ai = False; human = False
    EXCL = ["[Auto-Investigation]", "Stage has been changed", "This ticket was mentioned in Slack",
            "Thank you for contacting us!", "Auto-assigned", "This ticket has been open for",
            "Both background agents have completed", "projectx agent"]
    TRIV = ["checking", "noted", "ok", "done", "resolved", "hi ", "hello", "thanks", "sure"]
    for e in entries:
        if e.get("type") != "timeline_comment": continue
        b = e.get("body", "") or ""
        if b.strip().startswith("**Problem Statement:**"): ai = True; continue
        if any(p in b for p in EXCL): continue
        lo = b.strip().lower()[:20]
        if any(lo.startswith(x) for x in TRIV): continue
        if len(b.strip()) >= 80: human = True; break
    if human: return "human_rca"
    elif ai: return "ai_only"
    return "no_analysis"


# ── SLA helpers ──
def extract_sla_metrics(t):
    """Extract SLA hit/miss/in_progress for First Response and Resolution Time.
    Returns dict: {'first_response': 'hit'|'miss'|'in_progress'|None, 'resolution_time': 'hit'|'miss'|'in_progress'|None}
    """
    result = {"first_response": None, "resolution_time": None}
    sla = t.get("sla_summary", {})
    if not sla:
        return result
    tracker = sla.get("sla_tracker", {})
    if not tracker:
        return result
    mts = tracker.get("metric_target_summaries", [])
    for m in mts:
        name = m.get("metric_definition", {}).get("name", "")
        status = m.get("status", "")
        if "First" in name:
            result["first_response"] = status
        elif "Resolution" in name:
            result["resolution_time"] = status
    return result


def parse_iso(s):
    """Parse ISO datetime string to naive datetime."""
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except:
        return None


def percentile(sorted_list, p):
    """Calculate the p-th percentile of a sorted list."""
    if not sorted_list:
        return 0
    n = len(sorted_list)
    k = (p / 100.0) * (n - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_list[int(k)]
    return sorted_list[f] * (c - k) + sorted_list[c] * (k - f)


def format_hours(h):
    """Format hours into a human-readable string."""
    if h < 1:
        return f"{h * 60:.0f}m"
    elif h < 24:
        return f"{h:.1f}h"
    else:
        return f"{h / 24:.1f}d"


def sentiment_label(t):
    """Extract sentiment label from ticket."""
    sent = t.get("sentiment")
    if isinstance(sent, dict):
        return sent.get("label", "None")
    return "None"


# ══════════════════════════════════════
# MAIN
# ══════════════════════════════════════
def main():
    if not TOKEN:
        print("ERROR: Set DEVREV_TOKEN env var", file=sys.stderr)
        sys.exit(1)

    # ── Fetch open tickets ──
    print("Fetching open tickets...", file=sys.stderr)
    raw = []; cur = None
    while True:
        p = {"type": ["ticket"], "state": ["open", "in_progress"], "limit": 100}
        if cur: p["cursor"] = cur
        r = apicall("works.list", p); w = r.get("works", []); raw.extend(w); cur = r.get("next_cursor", "")
        if not w or not cur: break
    tickets = [t for t in raw if t.get("subtype") == "Support" and cohort(t) not in EXCLUDE_COHORTS]
    print(f"  {len(raw)} raw -> {len(tickets)} support tickets", file=sys.stderr)

    # ── Fetch resolved+Closed tickets (full pagination, excludes canceled at API level) ──
    print("Fetching resolved+Closed tickets (full pagination)...", file=sys.stderr)
    resolved_raw = []; cur = None; pg = 0
    while True:
        pg += 1
        p = {"type": ["ticket"], "stage": {"name": ["resolved", "Closed"]}, "limit": 100}
        if cur: p["cursor"] = cur
        r = apicall("works.list", p); w = r.get("works", []); resolved_raw.extend(w); cur = r.get("next_cursor", "")
        if pg % 20 == 0: print(f"    Page {pg}: {len(resolved_raw)} raw", file=sys.stderr)
        if not w or not cur: break
    print(f"  {len(resolved_raw)} raw resolved+Closed in {pg} pages", file=sys.stderr)

    # Filter to Support, excl WMS/Roadmap, then split by date
    all_resolved_support = [t for t in resolved_raw
                            if t.get("subtype") == "Support"
                            and cohort(t) not in EXCLUDE_COHORTS]
    resolved_today = [t for t in all_resolved_support
                      if t.get("actual_close_date", "")[:10] == TODAY_STR]
    resolved_7d = [t for t in all_resolved_support
                   if t.get("actual_close_date", "")[:10] >= SEVEN_DAYS_AGO]
    print(f"  Support: {len(all_resolved_support)} total, {len(resolved_7d)} last 7d, {len(resolved_today)} today", file=sys.stderr)

    # ── Created today ──
    open_created_today = [t for t in tickets if t.get("created_date", "")[:10] == TODAY_STR]
    resolved_created_today = [t for t in resolved_today if t.get("created_date", "")[:10] == TODAY_STR]
    all_created_today = open_created_today + resolved_created_today

    # ── Resolved breakdown by stage ──
    resolved_stages = Counter(stage(t) for t in resolved_today)

    # ── RCA (parallel) ──
    t2d = [t for t in tickets if age(t) >= 2]
    print(f"Fetching RCA timelines for {len(t2d)} tickets...", file=sys.stderr)
    rca_map = {}
    with ThreadPoolExecutor(max_workers=15) as pool:
        futs = {pool.submit(timeline, t["id"]): t for t in t2d}
        for f in as_completed(futs):
            t = futs[f]; rca_map[t["display_id"]] = classify_rca(f.result())
    print("Done.", file=sys.stderr)

    # ── Snapshot ──
    snap = None
    try:
        with open(os.path.join(os.path.dirname(__file__), "..", "config", "daily-snapshot.json")) as f:
            snap = json.load(f)
        if (TODAY - datetime.date.fromisoformat(snap["date"])).days > 2: snap = None
    except: pass
    today_ids = set(t["display_id"] for t in tickets)

    # ── Computed metrics ──
    blockers = [t for t in tickets if sev(t) == "blocker"]
    aging30 = [t for t in tickets if age(t) >= 30 and sev(t) in ("blocker", "high")]
    unanswered = [t for t in tickets if t.get("needs_response") == True]
    unassigned_l = [t for t in tickets if cx(t) == "Unassigned"]
    not_triaged = [t for t in tickets if stage(t) in NOT_TRIAGED]
    stale = [t for t in tickets if mod_age(t) >= 5]
    awcust = [t for t in tickets if stage(t) == "awaiting_customer_response"]
    followup = []
    for t in awcust:
        co = cohort(t)
        th = 3 if co in TIER1 else (5 if co in TIER2 else 7)
        tier = "Tier1" if co in TIER1 else ("Tier2" if co in TIER2 else "Tier3+")
        ds = mod_age(t)
        if ds >= th: followup.append((t, ds, tier))
    followup.sort(key=lambda x: x[1], reverse=True)
    missing_rca = {did: r for did, r in rca_map.items() if r != "human_rca"}

    day = TODAY.strftime("%A"); ds = TODAY.strftime("%d %b %Y")
    total = len(tickets)

    # ══════════════════════════════════════
    # OUTPUT
    # ══════════════════════════════════════
    print()
    print(f"CX Pulse -- Morning Brief | {day}, {ds}")
    print(f"Source: vista-549 | {total} open support tickets")

    # ── TREND ──
    print()
    print("=" * 90)
    print("TREND")
    print("=" * 90)
    if snap:
        yd = datetime.date.fromisoformat(snap["date"])
        yids = set(snap.get("ticket_ids", []))
        inf = len(today_ids - yids); out = len(yids - today_ids)
        def ar(d):
            if d > 0: return f"^{d}"
            elif d < 0: return f"v{abs(d)}"
            return "--"
        print(f'  {"Metric":<20} {"Prev":>10} {"Today":>10} {"Delta":>10}')
        print(f"  {'-'*55}")
        print(f'  {"Total Open":<20} {snap["total"]:>10} {total:>10} {ar(total - snap["total"]):>10}')
        print(f'  {"Blockers":<20} {snap["blockers"]:>10} {len(blockers):>10} {ar(len(blockers) - snap["blockers"]):>10}')
        print(f'  {"Aging 30d+":<20} {snap["aging30"]:>10} {len(aging30):>10} {ar(len(aging30) - snap["aging30"]):>10}')
        print(f'  {"Unassigned":<20} {snap["unassigned"]:>10} {len(unassigned_l):>10} {ar(len(unassigned_l) - snap["unassigned"]):>10}')
        print(f'  {"Unanswered":<20} {snap["needs_response"]:>10} {len(unanswered):>10} {ar(len(unanswered) - snap["needs_response"]):>10}')
        print(f"  Inflow: +{inf} new (in open queue) | Outflow: -{out} left open queue")
    else:
        print("  No baseline available (snapshot expired)")

    # ── NEW: Created & Resolved Today ──
    print()
    print("=" * 90)
    print("TODAY'S THROUGHPUT")
    print("=" * 90)
    print(f"  Created Today:   {len(all_created_today)} tickets ({len(open_created_today)} still open, {len(resolved_created_today)} already closed)")
    print(f"  Resolved Today:  {len(resolved_today)} tickets closed")
    if resolved_stages:
        breakdown = ", ".join(f"{s}: {c}" for s, c in resolved_stages.most_common())
        print(f"     Breakdown: {breakdown}")
    print()
    # Created today by account
    created_accts = Counter(acct(t) for t in all_created_today)
    print(f"  Created by Account:")
    for a, c in created_accts.most_common(10):
        print(f"    {a:<30} {c:>3}")
    if len(created_accts) > 10:
        print(f"    ... and {len(created_accts) - 10} more accounts")
    print()
    # Resolved today by account
    resolved_accts = Counter(acct(t) for t in resolved_today)
    print(f"  Resolved by Account:")
    for a, c in resolved_accts.most_common(10):
        print(f"    {a:<30} {c:>3}")
    if len(resolved_accts) > 10:
        print(f"    ... and {len(resolved_accts) - 10} more accounts")

    # ── S1: CX LEAD x STAGE ──
    print()
    print("=" * 90)
    print("1. CX LEAD x STAGE MATRIX")
    print("=" * 90)
    mx = defaultdict(Counter)
    for t in tickets: mx[cx(t)][stage(t)] += 1
    scols = ["queued", "work_in_progress", "awaiting_customer_response", "awaiting_development",
             "awaiting_product_assist", "in_development", "Reassigned to Customer Support", "TKT Backlog", "Reopen"]
    ch = ["Que", "WIP", "AwCst", "AwDev", "AwPrd", "InDev", "Rsgn", "Bklg", "Ropn"]
    sl = sorted(mx.items(), key=lambda x: sum(x[1].values()), reverse=True)
    nw = max(len(n) for n, _ in sl) if sl else 10
    h = f'  {"CX Lead":<{nw}}  {"Tot":>4}'
    for c in ch: h += f"  {c:>5}"
    h += f'  {"Other":>5}'
    print(h); print(f"  {'-' * (len(h) - 2)}")
    for n, st in sl:
        other = sum(st[s] for s in st if s not in scols)
        r = f"  {n:<{nw}}  {sum(st.values()):>4}"
        for s in scols: v = st.get(s, 0); r += f"  {'.' if not v else v:>5}"
        r += f"  {'.' if not other else other:>5}"
        print(r)
    totals = Counter()
    for _, st in sl:
        for s, c in st.items(): totals[s] += c
    r = f'  {"TOTAL":<{nw}}  {sum(totals.values()):>4}'
    for s in scols: r += f"  {totals.get(s, 0):>5}"
    other_tot = sum(totals[s] for s in totals if s not in scols)
    r += f"  {other_tot:>5}"
    print(f"  {'-' * (len(h) - 2)}"); print(r)

    # ── S2: BLOCKERS ──
    print()
    print("=" * 90)
    print(f"2. BLOCKERS ({len(blockers)})")
    print("=" * 90)
    if not blockers:
        print("  No blockers")
    else:
        print(f'  {"Ticket":<12} {"Account":<25} {"CX Lead":<22} {"Owner":<18} {"Age":>5} {"Stage":<25}')
        print(f"  {'-' * 110}")
        for t in sorted(blockers, key=lambda t: age(t), reverse=True):
            print(f'  {t["display_id"]:<12} {acct(t)[:23]:<25} {cx(t):<22} {owner(t)[:16]:<18} {age(t):>4}d {stage(t):<25}')
            print(f'    -> {t.get("title", "")[:80]}')

    # ── S3: AGING 30d+ ──
    print()
    print("=" * 90)
    print(f"3. AGING 30+ DAYS -- HIGH/BLOCKER ({len(aging30)})")
    print("=" * 90)
    if not aging30:
        print("  No aging high/blocker tickets")
    else:
        print(f'  {"Ticket":<12} {"Account":<25} {"CX Lead":<22} {"Age":>5} {"Sev":<8} {"Stage":<25}')
        print(f"  {'-' * 100}")
        for t in sorted(aging30, key=lambda t: age(t), reverse=True):
            print(f'  {t["display_id"]:<12} {acct(t)[:23]:<25} {cx(t):<22} {age(t):>4}d {sev(t):<8} {stage(t):<25}')

    # ── S4: TOP ACCOUNTS (consolidated) ──
    print()
    print("=" * 90)
    print("4. TOP ACCOUNTS (consolidated)")
    print("=" * 90)
    ac = Counter(acct(t) for t in tickets)
    ast = defaultdict(Counter)
    for t in tickets: ast[acct(t)][stage(t)] += 1
    print(f'  {"Account":<30} {"Open":>5}  Stage Breakdown')
    print(f"  {'-' * 85}")
    for a, cnt in ac.most_common(15):
        bd = ", ".join(f"{ABBREV.get(s, s[:6])}:{c}" for s, c in ast[a].most_common(5))
        print(f"  {a[:28]:<30} {cnt:>5}  {bd}")

    # ── S5: TEAM ──
    print()
    print("=" * 90)
    print(f"5. TODAY'S TEAM -- {day}, {ds}")
    print("=" * 90)
    cx_counts = Counter(cx(t) for t in tickets)
    on = []; off = []
    for name, (shift, status) in ROSTER.items():
        ct = cx_counts.get(name, 0)
        if status == "ON": on.append((name, shift, ct))
        else: off.append((name, shift, ct))
    on.sort(key=lambda x: x[2], reverse=True)
    print(f"  ON DUTY")
    print(f'  {"Name":<24} {"Shift":<22} {"Tickets":>8}')
    print(f"  {'-' * 56}")
    for n, s, c in on: print(f"  {n:<24} {s:<22} {c:>8}")
    print()
    print(f"  OFF TODAY")
    print(f'  {"Name":<24} {"Reason":<22} {"Tickets":>8}')
    print(f"  {'-' * 56}")
    for n, s, c in off:
        flag = " !!" if c > 30 else ""
        print(f"  {n:<24} {s:<22} {c:>8}{flag}")

    # ── S6a: UNANSWERED ──
    print()
    print("=" * 90)
    print(f"6a. CUSTOMER UNANSWERED -- {len(unanswered)} tickets ({round(len(unanswered)/total*100)}%)")
    print("=" * 90)
    nr = defaultdict(lambda: {"t": 0, "a": Counter()})
    cxt = Counter(cx(t) for t in tickets)
    for t in unanswered: nr[cx(t)]["t"] += 1; nr[cx(t)]["a"][acct(t)] += 1
    print(f'  {"CX Lead":<22} {"Unans":>6} {"% Own":>6}  Top Accounts')
    print(f"  {'-' * 85}")
    for n, d in sorted(nr.items(), key=lambda x: x[1]["t"], reverse=True):
        p = round(d["t"] / cxt.get(n, 1) * 100)
        ta = ", ".join(f"{a}({c})" for a, c in d["a"].most_common(3))
        print(f'  {n:<22} {d["t"]:>6} {p:>5}%  {ta}')

    # ── S6b: NOT TRIAGED ──
    print()
    print("=" * 90)
    print(f"6b. NOT TRIAGED -- {len(not_triaged)} tickets")
    print("    (Queued + TKT Backlog + Reassigned to Customer Support)")
    print("=" * 90)
    print(f'  {"Ticket":<12} {"Account":<25} {"CX Lead":<22} {"Age":>5} {"Stage":<25}')
    print(f"  {'-' * 92}")
    for t in sorted(not_triaged, key=lambda t: age(t), reverse=True):
        print(f'  {t["display_id"]:<12} {acct(t)[:23]:<25} {cx(t):<22} {age(t):>4}d {stage(t):<25}')

    # ── S6c: STALE ──
    print()
    print("=" * 90)
    print(f"6c. NO ACTIVITY 5+ DAYS -- {len(stale)} tickets ({round(len(stale)/total*100)}%)")
    print("=" * 90)
    sb = defaultdict(lambda: {"c": 0, "s": Counter()})
    for t in stale: sb[cx(t)]["c"] += 1; sb[cx(t)]["s"][stage(t)] += 1
    print(f'  {"CX Lead":<22} {"Stale":>6}  Stuck In')
    print(f"  {'-' * 70}")
    for n, d in sorted(sb.items(), key=lambda x: x[1]["c"], reverse=True):
        st = ", ".join(f"{ABBREV.get(s, s[:8])}:{c}" for s, c in d["s"].most_common(4))
        print(f'  {n:<22} {d["c"]:>6}  {st}')

    # ── S6d: FOLLOW-UP ──
    print()
    print("=" * 90)
    print(f"6d. FOLLOW-UP NEEDED -- {len(followup)} tickets")
    print("    Tier 1 (Reliance/DTDC): 3d | Tier 2 (Aramex/HNK): 5d | Others: 7d")
    print("=" * 90)
    print(f'  {"Ticket":<12} {"Account":<25} {"CX Lead":<22} {"Silent":>7} {"Tier":<6} {"Cohort":<18}')
    print(f"  {'-' * 95}")
    for t, d, tier in followup:
        print(f'  {t["display_id"]:<12} {acct(t)[:23]:<25} {cx(t):<22} {d:>6}d {tier:<6} {cohort(t):<18}')

    # ── S6e: RCA ──
    print()
    print("=" * 90)
    pm = round(len(missing_rca) / len(t2d) * 100) if t2d else 0
    print(f"6e. MISSING RCA -- {len(missing_rca)} tickets ({pm}% of {len(t2d)} tickets >2d)")
    print("    Excluded: [Auto-Investigation], **Problem Statement:** (AI), bots, trivial replies")
    print("=" * 90)
    rb = defaultdict(lambda: {"m": 0, "n": 0, "a": 0})
    for did, r in missing_rca.items():
        t = next(t for t in tickets if t["display_id"] == did)
        rb[cx(t)]["m"] += 1
        if r == "no_analysis": rb[cx(t)]["n"] += 1
        else: rb[cx(t)]["a"] += 1
    print(f'  {"CX Lead":<22} {"Missing":>8} {"No Analysis":>12} {"AI-Only":>8}')
    print(f"  {'-' * 55}")
    for n, d in sorted(rb.items(), key=lambda x: x[1]["m"], reverse=True):
        print(f'  {n:<22} {d["m"]:>8} {d["n"]:>12} {d["a"]:>8}')
    print()
    print(f"  Oldest tickets without human RCA:")
    print(f'  {"Ticket":<12} {"Account":<25} {"CX Lead":<22} {"Age":>5} {"Class":<15}')
    print(f"  {'-' * 82}")
    rca_tickets = [(next(t for t in tickets if t["display_id"] == did), r) for did, r in missing_rca.items()]
    for t, r in sorted(rca_tickets, key=lambda x: age(x[0]), reverse=True)[:10]:
        print(f'  {t["display_id"]:<12} {acct(t)[:23]:<25} {cx(t):<22} {age(t):>4}d {r:<15}')

    # ══════════════════════════════════════
    # NEW SECTIONS 7-10
    # ══════════════════════════════════════

    # ── S7: SLA ADHERENCE (Account-Wise) ──
    print()
    print("=" * 90)
    print("7. SLA ADHERENCE (Account-Wise)")
    print("    Source: All open + resolved-last-7d tickets with SLA data")
    print("=" * 90)

    # Combine open + resolved_7d for SLA analysis
    all_for_sla = tickets + resolved_7d
    # Build per-account SLA stats
    sla_by_account = defaultdict(lambda: {"fr_hit": 0, "fr_miss": 0, "rt_hit": 0, "rt_miss": 0, "total": 0})
    sla_overall = {"fr_hit": 0, "fr_miss": 0, "rt_hit": 0, "rt_miss": 0}

    for t in all_for_sla:
        m = extract_sla_metrics(t)
        account_name = acct(t)
        fr = m["first_response"]
        rt = m["resolution_time"]
        has_sla = False
        if fr == "hit":
            sla_by_account[account_name]["fr_hit"] += 1; sla_overall["fr_hit"] += 1; has_sla = True
        elif fr == "miss":
            sla_by_account[account_name]["fr_miss"] += 1; sla_overall["fr_miss"] += 1; has_sla = True
        if rt == "hit":
            sla_by_account[account_name]["rt_hit"] += 1; sla_overall["rt_hit"] += 1; has_sla = True
        elif rt == "miss":
            sla_by_account[account_name]["rt_miss"] += 1; sla_overall["rt_miss"] += 1; has_sla = True
        if has_sla:
            sla_by_account[account_name]["total"] += 1

    # Priority accounts + any account with 5+ tickets
    priority_accounts = {"Reliance", "DTDC", "Aramex", "Heineken", "Flipkart",
                         "Wellness Forever", "Rozana", "Box", "Proconnect", "Movin"}
    show_accounts = set()
    for a, stats in sla_by_account.items():
        if a in priority_accounts or stats["total"] >= 5:
            show_accounts.add(a)
    # Also add priority accounts even if they have fewer tickets
    for a in priority_accounts:
        if a in sla_by_account:
            show_accounts.add(a)

    # Overall summary
    fr_total = sla_overall["fr_hit"] + sla_overall["fr_miss"]
    rt_total = sla_overall["rt_hit"] + sla_overall["rt_miss"]
    fr_pct = round(sla_overall["fr_hit"] / fr_total * 100) if fr_total else 0
    rt_pct = round(sla_overall["rt_hit"] / rt_total * 100) if rt_total else 0
    print(f"  OVERALL: First Response {sla_overall['fr_hit']}/{fr_total} ({fr_pct}% hit) | Resolution Time {sla_overall['rt_hit']}/{rt_total} ({rt_pct}% hit)")
    print()
    print(f'  {"Account":<25} {"Tkts":>5} {"FR Hit":>7} {"FR Miss":>8} {"FR %":>6} {"RT Hit":>7} {"RT Miss":>8} {"RT %":>6}')
    print(f"  {'-' * 75}")

    sorted_sla_accounts = sorted(show_accounts, key=lambda a: sla_by_account[a]["total"], reverse=True)
    for a in sorted_sla_accounts:
        s = sla_by_account[a]
        fr_t = s["fr_hit"] + s["fr_miss"]
        rt_t = s["rt_hit"] + s["rt_miss"]
        fr_p = f"{round(s['fr_hit'] / fr_t * 100)}%" if fr_t else "--"
        rt_p = f"{round(s['rt_hit'] / rt_t * 100)}%" if rt_t else "--"
        print(f'  {a[:23]:<25} {s["total"]:>5} {s["fr_hit"]:>7} {s["fr_miss"]:>8} {fr_p:>6} {s["rt_hit"]:>7} {s["rt_miss"]:>8} {rt_p:>6}')

    # Show accounts with SLA misses highlighted
    miss_accounts = [(a, sla_by_account[a]) for a in sla_by_account
                     if sla_by_account[a]["fr_miss"] > 0 or sla_by_account[a]["rt_miss"] > 0]
    if miss_accounts:
        print()
        print(f"  [!] Accounts with SLA misses:")
        for a, s in sorted(miss_accounts, key=lambda x: x[1]["fr_miss"] + x[1]["rt_miss"], reverse=True)[:10]:
            misses = []
            if s["fr_miss"]: misses.append(f"FR:{s['fr_miss']}")
            if s["rt_miss"]: misses.append(f"RT:{s['rt_miss']}")
            print(f"    {a:<25} {', '.join(misses)}")

    # ── S8: RESOLUTION TAT (P10/P50/P90) ──
    print()
    print("=" * 90)
    print("8. RESOLUTION TAT (Turn Around Time) -- Last 7 Days")
    print("    Calculated from created_date to actual_close_date")
    print("=" * 90)

    # Calculate TAT for resolved_7d tickets
    tat_all = []
    tat_by_sev = defaultdict(list)
    for t in resolved_7d:
        created = parse_iso(t.get("created_date", ""))
        closed = parse_iso(t.get("actual_close_date", ""))
        if created and closed:
            delta_hours = (closed - created).total_seconds() / 3600.0
            if delta_hours >= 0:
                tat_all.append(delta_hours)
                severity = sev(t)
                tat_by_sev[severity].append(delta_hours)

    if tat_all:
        tat_all.sort()
        p10 = percentile(tat_all, 10)
        p50 = percentile(tat_all, 50)
        p90 = percentile(tat_all, 90)
        avg = sum(tat_all) / len(tat_all)
        print(f"  Overall ({len(tat_all)} tickets):")
        print(f"    P10: {format_hours(p10):>8}   P50 (median): {format_hours(p50):>8}   P90: {format_hours(p90):>8}   Avg: {format_hours(avg):>8}")
        print()

        # Breakdown by severity
        print(f'  {"Severity":<12} {"Count":>6} {"P10":>10} {"P50":>10} {"P90":>10} {"Avg":>10}')
        print(f"  {'-' * 60}")
        for severity in ["blocker", "high", "medium", "low"]:
            sv = tat_by_sev.get(severity, [])
            if not sv:
                print(f'  {severity:<12} {0:>6} {"--":>10} {"--":>10} {"--":>10} {"--":>10}')
                continue
            sv.sort()
            sp10 = format_hours(percentile(sv, 10))
            sp50 = format_hours(percentile(sv, 50))
            sp90 = format_hours(percentile(sv, 90))
            savg = format_hours(sum(sv) / len(sv))
            print(f'  {severity:<12} {len(sv):>6} {sp10:>10} {sp50:>10} {sp90:>10} {savg:>10}')

        # Other severities not in the standard list
        other_sevs = [s for s in tat_by_sev if s not in ("blocker", "high", "medium", "low")]
        for severity in other_sevs:
            sv = tat_by_sev[severity]
            sv.sort()
            sp10 = format_hours(percentile(sv, 10))
            sp50 = format_hours(percentile(sv, 50))
            sp90 = format_hours(percentile(sv, 90))
            savg = format_hours(sum(sv) / len(sv))
            print(f'  {severity[:12]:<12} {len(sv):>6} {sp10:>10} {sp50:>10} {sp90:>10} {savg:>10}')
    else:
        print("  No resolved tickets with valid date ranges found in the last 7 days.")

    # ── S9: CUSTOMER SENTIMENT / CSAT ──
    print()
    print("=" * 90)
    print("9. CUSTOMER SENTIMENT / CSAT")
    print("    Based on DevRev sentiment field (no direct CSAT score available)")
    print("=" * 90)

    # Sentiment across all open tickets
    sent_open = Counter(sentiment_label(t) for t in tickets)
    sent_resolved = Counter(sentiment_label(t) for t in resolved_7d)

    # Sentiment order
    SENT_ORDER = ["Happy", "Neutral", "Unhappy", "Frustrated", "None"]

    print(f"  Open Tickets ({total}):")
    print(f'  {"Sentiment":<15} {"Count":>7} {"%":>6}  Bar')
    print(f"  {'-' * 55}")
    for s in SENT_ORDER:
        c = sent_open.get(s, 0)
        pct = round(c / total * 100) if total else 0
        bar = "#" * (pct // 2) if pct > 0 else ""
        print(f"  {s:<15} {c:>7} {pct:>5}%  {bar}")

    print()
    print(f"  Resolved Last 7 Days ({len(resolved_7d)}):")
    r7_total = len(resolved_7d)
    print(f'  {"Sentiment":<15} {"Count":>7} {"%":>6}  Bar')
    print(f"  {'-' * 55}")
    for s in SENT_ORDER:
        c = sent_resolved.get(s, 0)
        pct = round(c / r7_total * 100) if r7_total else 0
        bar = "#" * (pct // 2) if pct > 0 else ""
        print(f"  {s:<15} {c:>7} {pct:>5}%  {bar}")

    # Negative sentiment per account (Unhappy + Frustrated) on open tickets
    neg_by_acct = Counter()
    for t in tickets:
        sl = sentiment_label(t)
        if sl in ("Unhappy", "Frustrated"):
            neg_by_acct[acct(t)] += 1
    if neg_by_acct:
        print()
        print(f"  [!] Accounts with Unhappy/Frustrated tickets (open):")
        print(f'  {"Account":<30} {"Count":>6}')
        print(f"  {'-' * 38}")
        for a, c in neg_by_acct.most_common(15):
            print(f"  {a[:28]:<30} {c:>6}")

    # ── S10: RESOLUTION RATE ──
    print()
    print("=" * 90)
    print("10. RESOLUTION RATE")
    print("=" * 90)

    resolved_today_count = len(resolved_today)
    created_today_count = len(all_created_today)
    still_open = total

    # Resolved today / (Resolved today + Still open)
    if resolved_today_count + still_open > 0:
        resolution_rate = round(resolved_today_count / (resolved_today_count + still_open) * 100, 1)
    else:
        resolution_rate = 0.0

    # Resolved today vs Created today ratio
    if created_today_count > 0:
        resolve_create_ratio = round(resolved_today_count / created_today_count, 2)
    else:
        resolve_create_ratio = float('inf') if resolved_today_count > 0 else 0.0

    print(f"  Today's Resolution Rate:    {resolution_rate}%  (resolved today / [resolved today + still open])")
    print(f"  Resolved vs Created Today:  {resolved_today_count} resolved / {created_today_count} created = {resolve_create_ratio}x")
    if resolve_create_ratio < 1.0 and created_today_count > 0:
        print(f"    [!] Queue is growing: creating tickets faster than resolving")
    elif resolve_create_ratio >= 1.0 and created_today_count > 0:
        print(f"    Queue is shrinking or stable")

    # 7-day view
    created_7d_count = sum(1 for t in resolved_7d if t.get("created_date", "")[:10] >= SEVEN_DAYS_AGO)
    # For a 7-day resolution ratio, we compare resolved_7d count vs tickets created in last 7 days
    # that are either still open or resolved
    open_created_7d = sum(1 for t in tickets if t.get("created_date", "")[:10] >= SEVEN_DAYS_AGO)
    total_created_7d = open_created_7d + created_7d_count
    if total_created_7d > 0:
        rate_7d = round(len(resolved_7d) / total_created_7d * 100, 1)
    else:
        rate_7d = 0.0
    print()
    print(f"  7-Day View:")
    print(f"    Resolved (7d):  {len(resolved_7d)}")
    print(f"    Created  (7d):  {total_created_7d} ({open_created_7d} still open + {created_7d_count} already closed)")
    print(f"    Resolution Rate (7d): {rate_7d}%")

    # ── FULL TICKET TABLE ──
    print()
    print("=" * 90)
    print(f"APPENDIX: ALL {total} TICKETS")
    print("=" * 90)
    print(f'  {"#":>4} {"Ticket":<12} {"Sev":<8} {"Stage":<28} {"CX Lead":<22} {"Account":<25} {"Age":>5} {"NR":>3} {"Stale":>6} {"Cohort":<18}')
    print(f"  {'-' * 135}")
    for i, t in enumerate(sorted(tickets, key=lambda x: age(x), reverse=True), 1):
        nr_flag = "Y" if t.get("needs_response") else "."
        sd = mod_age(t)
        stale_s = f"{sd}d" if sd >= 5 else "."
        print(f'  {i:>4} {t["display_id"]:<12} {sev(t):<8} {stage(t):<28} {cx(t):<22} {acct(t)[:23]:<25} {age(t):>4}d {nr_flag:>3} {stale_s:>6} {cohort(t):<18}')

    print()
    print("=" * 90)
    print(f"END OF REPORT -- {total} open + {len(resolved_today)} resolved today + {len(all_created_today)} created today | {NOW.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 90)

if __name__ == "__main__":
    main()
