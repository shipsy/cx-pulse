#!/usr/bin/env python3
"""CX Weekly Report — consolidated Mon-Sun with contractual SLA basis.
Run: python3 scripts/cx_weekly_report.py [--week YYYY-MM-DD]
  --week: Monday of the target week (default: most recent Monday)
Requires: DEVREV_TOKEN env var or .devrev_token file"""

import json, os, sys, datetime, math, subprocess
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from sla_lookup import load_sla_config, check_ticket_sla, lookup

# ═══ CONFIG ═══
def _load_token():
    t = os.environ.get("DEVREV_TOKEN", "").strip()
    if t: return t
    token_path = os.path.join(os.path.dirname(__file__), "..", ".devrev_token")
    try:
        with open(token_path) as f: return f.read().strip()
    except FileNotFoundError: return ""

TOKEN = _load_token()
API = "https://api.devrev.ai"
TODAY = datetime.date.today()

# Parse --week argument
WEEK_MON = None
for i, a in enumerate(sys.argv):
    if a == "--week" and i + 1 < len(sys.argv):
        WEEK_MON = datetime.date.fromisoformat(sys.argv[i + 1])
if not WEEK_MON:
    # Default: most recent completed Mon-Sun (if today is Mon, use last week)
    days_since_mon = TODAY.weekday()  # 0=Mon
    if days_since_mon == 0:
        WEEK_MON = TODAY - datetime.timedelta(days=7)
    else:
        WEEK_MON = TODAY - datetime.timedelta(days=days_since_mon)

WEEK_SUN = WEEK_MON + datetime.timedelta(days=6)
WEEK_START = WEEK_MON.isoformat()
WEEK_END = WEEK_SUN.isoformat()
# For resolved lookups, go a few days before week start
CUTOFF = (WEEK_MON - datetime.timedelta(days=7)).isoformat()

WMS_PODS = {"WMS Inbound", "WMS Outbound"}
EXCL_COHORTS = {"WMS", "Roadmap"}

# ═══ ACCOUNT CONSOLIDATION ═══
ALIASES = {
    "reliance (ril)":"Reliance","ril":"Reliance","reliance":"Reliance","reliancehyperlocal":"Reliance",
    "ril-tira":"Reliance","1p jiomart reliance":"Reliance","reliance - 3p":"Reliance",
    "qwik logistics":"Reliance","rcpldemo":"Reliance",
    "dtdc":"DTDC","dtdc.in":"DTDC",
    "aramex global":"Aramex","aramex vw":"Aramex","aramex move":"Aramex",
    "aramex same day delivery":"Aramex","aramex ro":"Aramex","aramex oceania":"Aramex",
    "aramex freight":"Aramex","aramex":"Aramex","aramex sdd":"Aramex",
    "flipkart":"Flipkart","fkfooddemo":"Flipkart","fk food":"Flipkart","flipkartdropship":"Flipkart",
    "rozana":"Rozana","rozanaondemand":"Rozana",
    "wellness forever":"Wellness Forever","wellness forever (tms)":"Wellness Forever",
    "[wms] wellness forever":"Wellness Forever",
    "milkbasket":"Milkbasket","kama ayurveda":"Kama Ayurveda",
    "movin":"Movin","movin1demo":"Movin",
    "apollo247":"Apollo247","spencers":"Spencers",
    "hnk-br1-primary":"Heineken","hnk-br1-secondary":"Heineken","hnk-br1-support":"Heineken",
    "myntra":"Myntra","myntrahl":"Myntra","myntrahldemo":"Myntra",
    "swiggy":"Swiggy","swiggytms":"Swiggy",
    "proconnect":"Proconnect","proconnect account":"Proconnect",
    "wakefit":"Wakefit","wakefitdemo":"Wakefit",
    "box account":"Box","box":"Box",
    "expeditorsdemo":"Expeditors","expeditors":"Expeditors",
    "asterksademo":"Aster KSA","aster pharmacy":"Aster Pharmacy",
    "aujan-export":"Aujan","aujan-import":"Aujan","aujansd-ksa":"Aujan","aujanimport":"Aujan",
    "flowpluae":"Flowpl","flowpl":"Flowpl","flowexpress":"Flowpl",
    "nxlogistics":"NX Logistics","caratlane":"CaratLane","sbt":"SBT",
    "healthkart":"Healthkart","field":"Field","incnut":"Incnut","frontline":"Frontline",
    "heromotocorp":"Hero MotoCorp","zajel":"Zajel","ubteam":"Ubteam",
}

DEVU_MAP = {
    "devu/1327":"Gangesh Pandey","devu/2573":"Saurabh Singh","devu/901":"Sachin Shivhare",
    "devu/2585":"Laxmi Rajput","devu/1088":"Deepanshu Marwari","devu/2580":"Vikas Pandey",
    "devu/2976":"Srijan Srivastava","devu/1246":"Vinod Kumar Gunda","devu/3000":"Kaustuv Choudhary",
    "devu/1314":"Vidushi Wanchoo","devu/2636":"Asif Khan","devu/2978":"Medha Saxena",
    "devu/1090":"Madhav Kapoor","devu/2934":"Abhishek Bhandari","devu/3007":"Bhavyank Sarolia",
    "devu/2744":"Omi Vaish","devu/2647":"Pakhi Vashishth","devu/3063":"Tejal Shirsat",
    "devu/2676":"SKG/Sumit Gupta","devu/3091":"Gaurav Singh",
    "devu/2626":"Shajiya Shaik","devu/1885":"Shipsy Support","devu/863":"Akash KumarRajek",
    "devu/899":"Yash Singh","devu/1009":"Sana Amreen","devu/1607":"Amit Dubey",
    "devu/2944":"Bhanu Arya","devu/2632":"Nikhila K",
}

SLACK_ID = {
    "Saurabh Singh": "U06L4JBDUG7", "Gangesh Pandey": "U03CAJNJ3M5",
    "Vinod Kumar Gunda": "U037KN084FJ", "Laxmi Rajput": "U06PWHWSDV3",
    "Kaustuv Choudhary": "U09BY1QA9D2", "Vidushi Wanchoo": "U032GDTAN6B",
    "Madhav Kapoor": "U02KSF1754L", "Vikas Pandey": "U06MM6U5WHK",
    "Abhishek Bhandari": "U08LNRWDBNE", "Asif Khan": "U069SEPA8M8",
    "Srijan Srivastava": "U096P90QQAE", "Tejal Shirsat": "U09JLRSCV51",
    "Deepanshu Marwari": "U02J2QN6SSX",
}

# ═══ HELPERS ═══
def norm(raw):
    if not raw or raw == "Unknown": return "Unknown"
    n = raw.strip()
    if n.endswith(" - Default Workspace"): n = n[:-20]
    if n.endswith(" Account"): n = n[:-8]
    return ALIASES.get(n.lower().strip(), n)

def apicall(endpoint, payload, _retries=3):
    import tempfile, time
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(payload, f); f.flush(); tmppath = f.name
    try:
        for attempt in range(_retries):
            r = subprocess.run(["curl", "-s", "--compressed", "--retry", "1",
                "--max-time", "90", "-X", "POST", f"{API}/{endpoint}",
                "-H", f"Authorization: Bearer {TOKEN}",
                "-H", "Content-Type: application/json",
                "-d", f"@{tmppath}"], capture_output=True, text=True, timeout=120)
            if not r.stdout.strip():
                if attempt < _retries - 1: time.sleep(1); continue
                raise RuntimeError(f"curl returned empty (rc={r.returncode})")
            try: return json.loads(r.stdout, strict=False)
            except json.JSONDecodeError:
                if attempt < _retries - 1: time.sleep(1); continue
                raise
    finally:
        os.unlink(tmppath)

def is_support(t):
    if t.get("subtype") != "Support": return False
    if (t.get("custom_fields", {}).get("tnt__customer_cohort_dropdown", "") or "TBD") in EXCL_COHORTS: return False
    if t.get("custom_fields", {}).get("tnt__pod", "") in WMS_PODS: return False
    return True

def acct(t): return norm((t.get("rev_org") or {}).get("display_name", "Unknown"))
def sev(t): return (t.get("severity") or "?").lower()
def stg(t): return t.get("stage", {}).get("name", "?")
def cx(t):
    a = t.get("custom_fields", {}).get("tnt__assignee", "")
    if not a: return "Unassigned"
    if "devu/" in a: return DEVU_MAP.get("devu/" + a.split("devu/")[-1], f'DEVU-{a.split("/")[-1]}')
    return "Unknown"

def pctl(sl, p):
    if not sl: return 0
    n = len(sl); k = (p / 100) * (n - 1); f = int(k); c = min(f + 1, n - 1)
    return sl[f] * (c - k) + sl[c] * (k - f) if f != c else sl[f]

def fh(h):
    if h < 1: return f"{h*60:.0f}m"
    elif h < 24: return f"{h:.1f}h"
    return f"{h/24:.1f}d"

def sla_color(pct):
    if pct >= 75: return "\U0001f7e2"
    elif pct >= 60: return "\U0001f7e1"
    elif pct >= 40: return "\U0001f7e0"
    return "\U0001f534"

def fmin(m):
    """Format minutes as human-readable."""
    if m is None: return "-"
    if m < 60: return f"{int(m)}m"
    elif m < 1440: return f"{m/60:.0f}h"
    return f"{m/1440:.1f}d"

def check_friday(ticket):
    try:
        r = apicall("timeline-entries.list", {"object": ticket["id"], "limit": 20})
        for e in r.get("timeline_entries", []):
            if e.get("type") != "timeline_comment": continue
            author = (e.get("created_by") or {}).get("display_name", "")
            if "friday" in author.lower(): return True
        return False
    except: return False

# ═══ MAIN ═══
def main():
    if not TOKEN:
        print("ERROR: Set DEVREV_TOKEN env var", file=sys.stderr); sys.exit(1)

    print(f"Week: {WEEK_MON.strftime('%d %b')} (Mon) — {WEEK_SUN.strftime('%d %b')} (Sun)", file=sys.stderr)

    sla_cfg = load_sla_config()
    print(f"Contractual SLA loaded: {len(sla_cfg['mapping'])} accounts", file=sys.stderr)

    # ═══ FETCH DATA ═══
    print("Fetching open tickets...", file=sys.stderr)
    raw = []; cur = None
    while True:
        p = {"type": ["ticket"], "state": ["open", "in_progress"], "limit": 25}
        if cur: p["cursor"] = cur
        r = apicall("works.list", p)
        w = r.get("works", []); raw.extend(w); cur = r.get("next_cursor", "")
        if not w or not cur: break
    tix = [t for t in raw if is_support(t)]
    print(f"  Open support: {len(tix)}", file=sys.stderr)

    print("Fetching resolved/closed tickets...", file=sys.stderr)
    res = []; cur = None; pg = 0
    while True:
        pg += 1
        p = {"type": ["ticket"], "state": ["resolved", "closed"], "limit": 25}
        if cur: p["cursor"] = cur
        r = apicall("works.list", p)
        w = r.get("works", []); res.extend(w); cur = r.get("next_cursor", "")
        if not w or not cur: break
        if w[-1].get("modified_date", "")[:10] < CUTOFF: break
        if pg > 250: break
    csup = [t for t in res if is_support(t)]
    print(f"  Closed support: {len(csup)} in {pg} pages", file=sys.stderr)

    # ═══ WEEK SCOPED DATA ═══
    # All tickets created during the week (from both open and closed pools, deduped)
    seen_ids = set()
    all_tickets = []
    for t in list(tix) + list(csup):
        did = t.get("display_id", "")
        if did in seen_ids: continue
        seen_ids.add(did)
        if is_support(t): all_tickets.append(t)

    created_week = [t for t in all_tickets
                    if WEEK_START <= t.get("created_date", "")[:10] <= WEEK_END
                    and stg(t) != "canceled"]
    resolved_week = [t for t in csup
                     if WEEK_START <= (t.get("actual_close_date") or "")[:10] <= WEEK_END
                     and stg(t).lower() in ("resolved", "closed")]

    total_now = len(tix)

    # Reconstruct Monday opening: current open + resolved during week - created during week
    # (tickets open on Monday = currently open that existed before Monday + closed-during-week that existed before Monday)
    open_before_week = [t for t in tix if t.get("created_date", "")[:10] < WEEK_START]
    closed_during_week_existed_before = [t for t in resolved_week if t.get("created_date", "")[:10] < WEEK_START]
    monday_open = len(open_before_week) + len(closed_during_week_existed_before)

    blockers_now = [t for t in tix if sev(t) == "blocker"]
    unanswered_now = [t for t in tix if t.get("needs_response") == True and stg(t) in ("queued", "work_in_progress")]

    # ═══ SLA — CONTRACTUAL BASIS ═══
    print("Computing contractual SLA...", file=sys.stderr)
    sla_pool = list(tix) + list(resolved_week)
    csla_all = {"fr_h": 0, "fr_m": 0, "fr_na": 0, "rt_h": 0, "rt_m": 0, "rt_na": 0}
    csla_acct = defaultdict(lambda: {"fr_h": 0, "fr_m": 0, "rt_h": 0, "rt_m": 0, "n": 0,
                                      "policy": "", "c_fr": None, "c_rt": None})
    devsla_all = {"fr_h": 0, "fr_m": 0, "rt_h": 0, "rt_m": 0}
    sla_counts = {"contractual": 0, "no_tiers": 0, "skip": 0, "unknown": 0}

    for t in sla_pool:
        a = acct(t)
        # DevRev default SLA (for comparison)
        tr = t.get("sla_summary", {}).get("sla_tracker", {})
        for m in tr.get("metric_target_summaries", []):
            nm = m.get("metric_definition", {}).get("name", ""); st = m.get("status", "")
            if "First" in nm:
                if st == "hit": devsla_all["fr_h"] += 1
                elif st == "miss": devsla_all["fr_m"] += 1
            elif "Resolution" in nm:
                if st == "hit": devsla_all["rt_h"] += 1
                elif st == "miss": devsla_all["rt_m"] += 1

        # Contractual SLA check (uses sla_lookup module)
        raw_acct = (t.get("rev_org") or {}).get("display_name", "Unknown")
        # Strip common suffixes for matching
        raw_clean = raw_acct.strip()
        if raw_clean.endswith(" - Default Workspace"): raw_clean = raw_clean[:-20]
        if raw_clean.endswith(" Account"): raw_clean = raw_clean[:-8]
        res = check_ticket_sla(t, sla_cfg, consolidated_account_name=raw_clean)
        sla_counts[res["category"]] += 1

        if res["category"] != "contractual":
            csla_all["fr_na"] += 1
            csla_all["rt_na"] += 1
            continue

        has_sla = False
        if res["fr_hit"] is not None:
            if res["fr_hit"]: csla_all["fr_h"] += 1; csla_acct[a]["fr_h"] += 1
            else: csla_all["fr_m"] += 1; csla_acct[a]["fr_m"] += 1
            has_sla = True
        else:
            csla_all["fr_na"] += 1

        if res["rt_hit"] is not None:
            if res["rt_hit"]: csla_all["rt_h"] += 1; csla_acct[a]["rt_h"] += 1
            else: csla_all["rt_m"] += 1; csla_acct[a]["rt_m"] += 1
            has_sla = True
        else:
            csla_all["rt_na"] += 1

        if has_sla:
            csla_acct[a]["n"] += 1
        if not csla_acct[a]["policy"]:
            csla_acct[a]["policy"] = res.get("policy", "")
            csla_acct[a]["c_fr"] = res.get("fr_target")
            csla_acct[a]["c_rt"] = res.get("rt_target")

    # ═══ RESOLUTION RATE (daily, Mon-Sun) ═══
    daily_rates = []
    for i in range(7):
        d = (WEEK_MON + datetime.timedelta(days=i)).isoformat()
        cr = [t for t in all_tickets if t.get("created_date", "")[:10] == d and stg(t) != "canceled"]
        rv = [t for t in csup if (t.get("actual_close_date") or "")[:10] == d and stg(t).lower() in ("resolved", "closed")]
        daily_rates.append((d, len(cr), len(rv)))

    # ═══ TAT ═══
    tat_all = []; tat_sev = defaultdict(list)
    for t in resolved_week:
        sla_tat_min = None
        tr = t.get("sla_summary", {}).get("sla_tracker", {})
        for m in tr.get("metric_target_summaries", []):
            nm = m.get("metric_definition", {}).get("name", "")
            if "Resolution" in nm and m.get("completed_in") is not None:
                sla_tat_min = m["completed_in"]; break
        if sla_tat_min is not None and sla_tat_min > 0:
            h = sla_tat_min / 60
            tat_all.append(h); tat_sev[sev(t)].append(h)
        elif sla_tat_min == 0:
            continue
        else:
            cr = t.get("created_date", ""); cl = t.get("actual_close_date", "")
            if cr and cl:
                try:
                    c1 = datetime.datetime.fromisoformat(cr.replace("Z", "+00:00")).replace(tzinfo=None)
                    c2 = datetime.datetime.fromisoformat(cl.replace("Z", "+00:00")).replace(tzinfo=None)
                    h = (c2 - c1).total_seconds() / 3600
                    if h >= 0: tat_all.append(h); tat_sev[sev(t)].append(h)
                except: pass
    tat_all.sort()

    # ═══ WHO RESOLVES ═══
    rb = Counter(t.get("custom_fields", {}).get("tnt__resolved_by", "") for t in resolved_week
                 if t.get("custom_fields", {}).get("tnt__resolved_by"))
    rb_total = sum(rb.values())

    # ═══ FRIDAY AI ═══
    print("Checking Friday AI coverage...", file=sys.stderr)
    friday_count = 0
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = {pool.submit(check_friday, t): t for t in created_week}
        for f in as_completed(futs):
            if f.result(): friday_count += 1
    print(f"  Friday: {friday_count}/{len(created_week)}", file=sys.stderr)

    # ═══ CX LEAD LOAD ═══
    mx = defaultdict(Counter)
    for t in tix: mx[cx(t)][stg(t)] += 1

    # ═══ FORMAT OUTPUT ═══
    week_label = f"{WEEK_MON.strftime('%d %b')} — {WEEK_SUN.strftime('%d %b %Y')}"
    msg = []
    msg.append(f":bar_chart: *CX Support — Weekly Metrics* | {week_label}")
    msg.append(f"_Contractual SLA basis_")
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")

    # 1. PULSE CHECK
    msg.append("*1. PULSE CHECK*")
    msg.append("```")
    msg.append(f"{'':16} {'Mon Open':>8}  {'Now':>8}    {'Change':>6}")
    delta = total_now - monday_open
    arr = f"{'▲' if delta > 0 else '▼' if delta < 0 else '='} {abs(delta):>2}"
    msg.append(f"{'Open':<16} {monday_open:>8}  {total_now:>8}     {arr}")
    msg.append(f"{'Blockers':<16} {'':>8}  {len(blockers_now):>8}")
    msg.append(f"{'Unanswered':<16} {'':>8}  {len(unanswered_now):>8}")
    msg.append(f"")
    msg.append(f"Week totals:  +{len(created_week)} created | -{len(resolved_week)} resolved | net {'+' if len(created_week)-len(resolved_week) >= 0 else ''}{len(created_week)-len(resolved_week)}")
    msg.append("```")

    # 2. SLA ADHERENCE (CONTRACTUAL)
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")

    cfr_t = csla_all["fr_h"] + csla_all["fr_m"]
    crt_t = csla_all["rt_h"] + csla_all["rt_m"]
    cfr_pct = round(csla_all["fr_h"] / cfr_t * 100) if cfr_t else 0
    crt_pct = round(csla_all["rt_h"] / crt_t * 100) if crt_t else 0

    # DevRev default for comparison
    dfr_t = devsla_all["fr_h"] + devsla_all["fr_m"]
    drt_t = devsla_all["rt_h"] + devsla_all["rt_m"]
    dfr_pct = round(devsla_all["fr_h"] / dfr_t * 100) if dfr_t else 0
    drt_pct = round(devsla_all["rt_h"] / drt_t * 100) if drt_t else 0

    msg.append("*2. SLA ADHERENCE — CONTRACTUAL* _(open + resolved this week)_")
    msg.append(f"Contractual:  FR *{cfr_pct}%* hit ({csla_all['fr_h']}/{cfr_t}) · RT *{crt_pct}%* hit ({csla_all['rt_h']}/{crt_t})")
    msg.append(f"DevRev default: FR {dfr_pct}% ({devsla_all['fr_h']}/{dfr_t}) · RT {drt_pct}% ({devsla_all['rt_h']}/{drt_t})")
    msg.append(f"_{sla_counts['contractual']} contractual · {sla_counts['no_tiers']} no-tiers · {sla_counts['skip']} skip · {sla_counts['unknown']} unmapped_")
    msg.append("```")
    msg.append(f" #  {'Account':<16}  {'Pool':>4}  {'Policy':<10}  {'cFR%':>5}  {'Tgt':>5}  {'cRT%':>5}  {'Tgt':>5}")
    msg.append(f"──  {'─'*16}  {'─'*4}  {'─'*10}  {'─'*5}  {'─'*5}  {'─'*5}  {'─'*5}")

    sorted_csla = sorted(csla_acct.items(), key=lambda x: x[1]["n"], reverse=True)
    shown = []; rest = []
    for a, d in sorted_csla:
        if len(shown) < 12 and d["n"] >= 3: shown.append((a, d))
        else: rest.append((a, d))

    for i, (a, d) in enumerate(shown, 1):
        frd = d["fr_h"] + d["fr_m"]; rtd = d["rt_h"] + d["rt_m"]
        fp = round(d["fr_h"] / frd * 100) if frd else 0
        rp = round(d["rt_h"] / rtd * 100) if rtd else 0
        fp_s = f"{sla_color(fp)}{fp}%" if frd else "  -"
        rp_s = f"{sla_color(rp)}{rp}%" if rtd else "  -"
        cfr_s = fmin(d["c_fr"]) if d["c_fr"] else "  -"
        crt_s = fmin(d["c_rt"]) if d["c_rt"] else "  -"
        pol = (d.get("policy") or "")[:10]
        msg.append(f"{i:>2}  {a[:16]:<16}  {d['n']:>4}  {pol:<10}  {fp_s:>5}  {cfr_s:>5}  {rp_s:>5}  {crt_s:>5}")

    if rest:
        rm_n = sum(d["n"] for _, d in rest)
        rm_frh = sum(d["fr_h"] for _, d in rest); rm_frm = sum(d["fr_m"] for _, d in rest)
        rm_rth = sum(d["rt_h"] for _, d in rest); rm_rtm = sum(d["rt_m"] for _, d in rest)
        rm_frd = rm_frh + rm_frm; rm_rtd = rm_rth + rm_rtm
        rfp = f"{round(rm_frh/rm_frd*100)}%" if rm_frd else "-"
        rrp = f"{round(rm_rth/rm_rtd*100)}%" if rm_rtd else "-"
        msg.append(f"    {len(rest)} more accts     {rm_n:>4}  {rfp:>5}  {'':>6}  {rrp:>5}  {'':>6}")

    msg.append("")
    msg.append(f"{sla_color(75)} >=75%  {sla_color(60)} 60-74%  {sla_color(40)} 40-59%  {sla_color(0)} <40%")
    msg.append("```")

    # 3. RESOLUTION RATE
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append("*3. RESOLUTION RATE* _(Mon — Sun)_")
    msg.append("```")
    msg.append(f"{'Day':>10}  {'Created':>8}  {'Resolved':>8}    {'Net':>5}")
    msg.append("─" * 40)
    tc = 0; tr2 = 0
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for idx, (d, c, r) in enumerate(daily_rates):
        tc += c; tr2 += r
        net = c - r
        dn = "▲" if net > 0 else ("▼" if net < 0 else "=")
        emoji = " ✅" if net < 0 else ""
        dname = f"{day_names[idx]} {datetime.date.fromisoformat(d).strftime('%d')}"
        msg.append(f"{dname:>10}  {c:>8}  {r:>8}   {dn} {abs(net):>3}{emoji}")
    msg.append("─" * 40)
    tnet = tc - tr2
    tdn = "▲" if tnet > 0 else ("▼" if tnet < 0 else "=")
    msg.append(f"{'TOTAL':>10}  {tc:>8}  {tr2:>8}   {tdn} {abs(tnet):>3}")
    rr = round(tr2 / tc * 100) if tc else 0
    msg.append(f"\nResolve ratio: {tr2}/{tc} = {rr}%")
    msg.append("```")

    # 4. RESOLUTION TAT
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append("*4. RESOLUTION TAT* _(resolved this week)_")
    msg.append("```")
    msg.append(f"{'Severity':<10}  {'P10':>8}  {'P50':>8}  {'P90':>8}")
    msg.append("─" * 40)
    if tat_all:
        msg.append(f"{'All':<10}  {fh(pctl(tat_all,10)):>8}  {fh(pctl(tat_all,50)):>8}  {fh(pctl(tat_all,90)):>8}")
    for sv in ["blocker", "high", "medium", "low"]:
        sl = sorted(tat_sev.get(sv, []))
        if sl:
            msg.append(f"{sv.capitalize():<10}  {fh(pctl(sl,10)):>8}  {fh(pctl(sl,50)):>8}  {fh(pctl(sl,90)):>8}")
    msg.append("```")

    # 5. WHO RESOLVES
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append("*5. WHO RESOLVES* _(resolved this week)_")
    msg.append("```")
    if rb_total:
        for k, c in rb.most_common():
            icon = {"Resolved by Support": "🛠️", "Resolved by Product": "📦", "Resolved by Engineering": "⚙️"}.get(k, "")
            name = k.replace("Resolved by ", "")
            msg.append(f"{icon}  {name:<16}  {c:>4}   ({round(c/rb_total*100)}%)")
    else:
        msg.append("No resolved-by data this week")
    msg.append("```")

    # 6. FRIDAY AI
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append(f"*6. FRIDAY AI* _(week total)_")
    msg.append("```")
    msg.append(f"🤖  Tickets analyzed:  {friday_count} / {len(created_week)} created")
    coverage = round(friday_count / len(created_week) * 100) if created_week else 0
    msg.append(f"📊  Coverage:          {coverage}%")
    msg.append("```")

    # 7. CX LEAD LOAD
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append("*7. CX LEAD LOAD* _(current open)_")
    msg.append("```")
    scols = ["queued", "work_in_progress", "awaiting_customer_response", "awaiting_development",
             "awaiting_product_assist", "in_development", "Reassigned to Customer Support", "Reopen"]
    ch = ["Que", "WIP", "AwC", "AwD", "AwP", "InD", "Rsg", "Rop"]
    sl = sorted(mx.items(), key=lambda x: sum(x[1].values()), reverse=True)
    header = f"{'Lead':<18} {'Tot':>3}"
    for c in ch: header += f" {c:>3}"
    msg.append(header)
    msg.append("─" * len(header))
    for n, st in sl[:12]:
        name = n[:18] if len(n) > 18 else n
        row = f"{name:<18} {sum(st.values()):>3}"
        for s in scols:
            v = st.get(s, 0)
            row += f" {'.' if not v else v:>3}"
        msg.append(row)
    msg.append("```")

    # 8. AGING TICKETS
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append("*8. AGING TICKETS* _(open, by age)_")

    def ticket_age(t):
        try: return (TODAY - datetime.date.fromisoformat(t.get("created_date", TODAY.isoformat())[:10])).days
        except: return 0

    tix_7 = [t for t in tix if ticket_age(t) >= 7]
    tix_15 = [t for t in tix if ticket_age(t) >= 15]
    tix_30 = [t for t in tix if ticket_age(t) >= 30]

    msg.append("```")
    msg.append(f"{'Age':<14} {'Count':>5}    {'% of Open':>9}")
    msg.append("─" * 34)
    msg.append(f"{'7+ days':<14} {len(tix_7):>5}    {round(len(tix_7)/total_now*100) if total_now else 0:>8}%")
    msg.append(f"{'15+ days':<14} {len(tix_15):>5}    {round(len(tix_15)/total_now*100) if total_now else 0:>8}%")
    msg.append(f"{'30+ days':<14} {len(tix_30):>5}    {round(len(tix_30)/total_now*100) if total_now else 0:>8}%")
    msg.append("```")

    aging_lead = Counter(cx(t) for t in tix_30)
    top3 = [(n, c) for n, c in aging_lead.most_common(4) if n != "Unassigned"][:3]
    holders = " · ".join(f"{n} ({c})" for n, c in top3)
    unassigned_30 = aging_lead.get("Unassigned", 0)
    if unassigned_30: holders += f" · {unassigned_30} unassigned"
    msg.append(f"30+ holders: {holders}")

    output = "\n".join(msg)
    print(output)
    return output


if __name__ == "__main__":
    main()
