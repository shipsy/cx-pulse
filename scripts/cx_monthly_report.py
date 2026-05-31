#!/usr/bin/env python3
"""CX Monthly Report — May 2026
Fetches full month data from DevRev, computes weekly metrics, shows trends.
Run: python3 scripts/cx_monthly_report.py
Requires: DEVREV_TOKEN env var"""

import json, os, sys, datetime, math, subprocess
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

# ═══ CONFIG ═══
def _load_token():
    t = os.environ.get("DEVREV_TOKEN", "").strip()
    if t:
        return t
    token_path = os.path.join(os.path.dirname(__file__), "..", ".devrev_token")
    try:
        with open(token_path) as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

TOKEN = _load_token()
API = "https://api.devrev.ai"

# May 2026 weeks
MONTH_START = "2026-05-01"
MONTH_END = "2026-05-31"
WEEKS = [
    ("W1", "2026-05-01", "2026-05-07"),
    ("W2", "2026-05-08", "2026-05-14"),
    ("W3", "2026-05-15", "2026-05-21"),
    ("W4", "2026-05-22", "2026-05-31"),
]

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
            try:
                return json.loads(r.stdout, strict=False)
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
def cohort(t): return t.get("custom_fields", {}).get("tnt__customer_cohort_dropdown", "TBD") or "TBD"
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
    if pct >= 75: return "🟢"
    elif pct >= 60: return "🟡"
    elif pct >= 40: return "🟠"
    return "🔴"

def trend_arrow(vals):
    """Given a list of weekly values, return trend description."""
    if len(vals) < 2: return ""
    first, last = vals[0], vals[-1]
    if first == 0: return ""
    pct_change = round((last - first) / first * 100)
    if pct_change > 5: return f"📈 +{pct_change}%"
    elif pct_change < -5: return f"📉 {pct_change}%"
    return "➡️ Flat"

def in_week(date_str, w_start, w_end):
    if not date_str: return False
    d = date_str[:10]
    return w_start <= d <= w_end


# ═══ MAIN ═══
def main():
    if not TOKEN:
        print("ERROR: Set DEVREV_TOKEN env var", file=sys.stderr); sys.exit(1)

    # ═══ FETCH ALL DATA ═══
    print("Fetching all open tickets...", file=sys.stderr)
    raw = []; cur = None
    while True:
        p = {"type": ["ticket"], "state": ["open", "in_progress"], "limit": 25}
        if cur: p["cursor"] = cur
        r = apicall("works.list", p)
        w = r.get("works", []); raw.extend(w); cur = r.get("next_cursor", "")
        if not w or not cur: break
    open_tix = [t for t in raw if is_support(t)]
    print(f"  Open support tickets: {len(open_tix)}", file=sys.stderr)

    print("Fetching resolved/closed tickets (May window)...", file=sys.stderr)
    res = []; cur = None; pg = 0
    # Need to go back to at least April 30 to catch everything
    cutoff = "2026-04-25"
    while True:
        pg += 1
        p = {"type": ["ticket"], "state": ["resolved", "closed"], "limit": 25}
        if cur: p["cursor"] = cur
        r = apicall("works.list", p)
        w = r.get("works", []); res.extend(w); cur = r.get("next_cursor", "")
        if not w or not cur: break
        if w[-1].get("modified_date", "")[:10] < cutoff: break
        if pg > 300: break
    csup = [t for t in res if is_support(t)]
    print(f"  Closed support tickets: {len(csup)} in {pg} pages", file=sys.stderr)

    # Dedup all tickets
    all_tickets = {}
    for t in open_tix + csup:
        did = t.get("display_id", "")
        if did and did not in all_tickets:
            all_tickets[did] = t
    open_ids = set(t.get("display_id", "") for t in open_tix)

    # ═══ CATEGORIZE BY WEEK ═══
    week_data = {}
    for wname, ws, we in WEEKS:
        created = [t for t in all_tickets.values()
                   if in_week(t.get("created_date"), ws, we) and stg(t) != "canceled"]
        resolved = [t for t in csup
                    if in_week(t.get("actual_close_date"), ws, we)
                    and stg(t).lower() in ("resolved", "closed")]

        # SLA for tickets active in this week (created or resolved in week)
        week_tickets = set()
        for t in created: week_tickets.add(t.get("display_id"))
        for t in resolved: week_tickets.add(t.get("display_id"))
        active = [all_tickets[did] for did in week_tickets if did in all_tickets]

        sla = {"fr_h": 0, "fr_m": 0, "rt_h": 0, "rt_m": 0}
        for t in active:
            tr = t.get("sla_summary", {}).get("sla_tracker", {})
            for m in tr.get("metric_target_summaries", []):
                nm = m.get("metric_definition", {}).get("name", ""); st = m.get("status", "")
                if "First" in nm:
                    if st == "hit": sla["fr_h"] += 1
                    elif st == "miss": sla["fr_m"] += 1
                elif "Resolution" in nm:
                    if st == "hit": sla["rt_h"] += 1
                    elif st == "miss": sla["rt_m"] += 1

        # TAT for resolved in this week
        tat = []
        for t in resolved:
            sla_tat_min = None
            tr = t.get("sla_summary", {}).get("sla_tracker", {})
            for m in tr.get("metric_target_summaries", []):
                nm = m.get("metric_definition", {}).get("name", "")
                if "Resolution" in nm and m.get("completed_in") is not None:
                    sla_tat_min = m["completed_in"]; break
            if sla_tat_min is not None and sla_tat_min > 0:
                tat.append(sla_tat_min / 60)
            elif sla_tat_min == 0:
                continue
            else:
                cr = t.get("created_date", ""); cl = t.get("actual_close_date", "")
                if cr and cl:
                    try:
                        c1 = datetime.datetime.fromisoformat(cr.replace("Z", "+00:00")).replace(tzinfo=None)
                        c2 = datetime.datetime.fromisoformat(cl.replace("Z", "+00:00")).replace(tzinfo=None)
                        h = (c2 - c1).total_seconds() / 3600
                        if h >= 0: tat.append(h)
                    except: pass
        tat.sort()

        # Blockers created in this week
        blockers = [t for t in created if sev(t) == "blocker"]

        # Severity breakdown
        sev_counts = Counter(sev(t) for t in created)

        # Who resolves
        rb = Counter(t.get("custom_fields", {}).get("tnt__resolved_by", "") for t in resolved
                     if t.get("custom_fields", {}).get("tnt__resolved_by"))

        # CX lead resolving
        cx_resolved = Counter(cx(t) for t in resolved)

        # Top accounts by created volume
        acct_created = Counter(acct(t) for t in created)

        # Cohort breakdown
        cohort_counts = Counter(cohort(t) for t in created)

        # Still open from this week + their stages
        still_open = [t for t in created if t.get("display_id", "") in open_ids]
        stage_short = {"awaiting_customer_response": "AwCust", "awaiting_development": "AwDev",
                       "awaiting_product_assist": "AwProd", "work_in_progress": "WIP",
                       "queued": "Queued", "in_development": "InDev",
                       "Reassigned to Customer Support": "Reassigned", "Reopen": "Reopen"}
        still_open_stages = Counter(stage_short.get(stg(t), stg(t)[:12]) for t in still_open)

        week_data[wname] = {
            "label": f"{ws[5:]} → {we[5:]}",
            "created": len(created),
            "resolved": len(resolved),
            "net": len(created) - len(resolved),
            "blockers": len(blockers),
            "sla": sla,
            "tat": tat,
            "sev": sev_counts,
            "rb": rb,
            "cx_resolved": cx_resolved,
            "acct_created": acct_created,
            "cohort": cohort_counts,
            "created_list": created,
            "resolved_list": resolved,
            "still_open": len(still_open),
            "still_open_stages": still_open_stages,
        }

    # ═══ MONTH TOTALS ═══
    all_created = [t for t in all_tickets.values()
                   if in_week(t.get("created_date"), MONTH_START, MONTH_END) and stg(t) != "canceled"]
    all_resolved = [t for t in csup
                    if in_week(t.get("actual_close_date"), MONTH_START, MONTH_END)
                    and stg(t).lower() in ("resolved", "closed")]

    # Monthly SLA
    m_sla = {"fr_h": 0, "fr_m": 0, "rt_h": 0, "rt_m": 0}
    month_ticket_ids = set()
    for t in all_created: month_ticket_ids.add(t.get("display_id"))
    for t in all_resolved: month_ticket_ids.add(t.get("display_id"))
    for did in month_ticket_ids:
        t = all_tickets.get(did)
        if not t: continue
        tr = t.get("sla_summary", {}).get("sla_tracker", {})
        for m in tr.get("metric_target_summaries", []):
            nm = m.get("metric_definition", {}).get("name", ""); st = m.get("status", "")
            if "First" in nm:
                if st == "hit": m_sla["fr_h"] += 1
                elif st == "miss": m_sla["fr_m"] += 1
            elif "Resolution" in nm:
                if st == "hit": m_sla["rt_h"] += 1
                elif st == "miss": m_sla["rt_m"] += 1

    # Monthly TAT
    m_tat = []
    for t in all_resolved:
        sla_tat_min = None
        tr = t.get("sla_summary", {}).get("sla_tracker", {})
        for m in tr.get("metric_target_summaries", []):
            nm = m.get("metric_definition", {}).get("name", "")
            if "Resolution" in nm and m.get("completed_in") is not None:
                sla_tat_min = m["completed_in"]; break
        if sla_tat_min is not None and sla_tat_min > 0:
            m_tat.append(sla_tat_min / 60)
        elif sla_tat_min == 0:
            continue
        else:
            cr = t.get("created_date", ""); cl = t.get("actual_close_date", "")
            if cr and cl:
                try:
                    c1 = datetime.datetime.fromisoformat(cr.replace("Z", "+00:00")).replace(tzinfo=None)
                    c2 = datetime.datetime.fromisoformat(cl.replace("Z", "+00:00")).replace(tzinfo=None)
                    h = (c2 - c1).total_seconds() / 3600
                    if h >= 0: m_tat.append(h)
                except: pass
    m_tat.sort()

    # Monthly who resolves
    m_rb = Counter(t.get("custom_fields", {}).get("tnt__resolved_by", "") for t in all_resolved
                   if t.get("custom_fields", {}).get("tnt__resolved_by"))

    # Monthly account breakdown
    m_acct = Counter(acct(t) for t in all_created)

    # Monthly severity
    m_sev = Counter(sev(t) for t in all_created)

    # Monthly CX lead load (current open)
    m_cx = Counter(cx(t) for t in open_tix)

    # Monthly cohort
    m_cohort = Counter(cohort(t) for t in all_created)

    # Aging (current)
    today = datetime.date.today()
    def ticket_age(t):
        try: return (today - datetime.date.fromisoformat(t.get("created_date", today.isoformat())[:10])).days
        except: return 0
    tix_7 = [t for t in open_tix if ticket_age(t) >= 7]
    tix_15 = [t for t in open_tix if ticket_age(t) >= 15]
    tix_30 = [t for t in open_tix if ticket_age(t) >= 30]

    # Friday AI check for entire month
    print("Checking Friday AI coverage (sampling)...", file=sys.stderr)
    # Sample: check first 50 tickets per week to keep API calls reasonable
    friday_weekly = {}
    for wname, ws, we in WEEKS:
        wk = week_data[wname]
        sample = wk["created_list"][:50]
        count = 0
        with ThreadPoolExecutor(max_workers=10) as pool:
            futs = {pool.submit(check_friday, t): t for t in sample}
            for f in as_completed(futs):
                if f.result(): count += 1
        friday_weekly[wname] = (count, len(sample), len(wk["created_list"]))
        print(f"  {wname}: Friday {count}/{len(sample)} (of {len(wk['created_list'])} total)", file=sys.stderr)

    # ═══ FORMAT REPORT (matches daily dashboard format) ═══
    today = datetime.date.today()
    today_str = today.strftime("%d %b %Y")

    m_fr_t = m_sla["fr_h"] + m_sla["fr_m"]
    m_rt_t = m_sla["rt_h"] + m_sla["rt_m"]
    m_fr_pct = round(m_sla["fr_h"] / m_fr_t * 100) if m_fr_t else 0
    m_rt_pct = round(m_sla["rt_h"] / m_rt_t * 100) if m_rt_t else 0
    rr = round(len(all_resolved) / len(all_created) * 100) if all_created else 0

    msg = []
    msg.append(f"📊 **CX Support — Monthly Review** | May 2026")
    msg.append(f"_1 May – 31 May 2026_")
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")

    # ━━━ 1. PULSE CHECK ━━━
    msg.append("**1. PULSE CHECK**")
    msg.append("```")
    msg.append(f"{'':>16} {'W1':>8} {'W2':>8} {'W3':>8} {'W4':>8}")
    msg.append(f"{'':>16} {'(1-7)':>8} {'(8-14)':>8} {'(15-21)':>8} {'(22-31)':>8}")
    w1, w2, w3, w4 = [week_data[w] for w in ["W1","W2","W3","W4"]]
    msg.append(f"{'Created':<16} {w1['created']:>8} {w2['created']:>8} {w3['created']:>8} {w4['created']:>8}")
    msg.append(f"{'Resolved':<16} {w1['resolved']:>8} {w2['resolved']:>8} {w3['resolved']:>8} {w4['resolved']:>8}")
    msg.append(f"{'Net':<16} {w1['net']:>+8} {w2['net']:>+8} {w3['net']:>+8} {w4['net']:>+8}")
    msg.append(f"{'Blockers':<16} {w1['blockers']:>8} {w2['blockers']:>8} {w3['blockers']:>8} {w4['blockers']:>8}")
    msg.append(f"{'Still Open':<16} {w1['still_open']:>8} {w2['still_open']:>8} {w3['still_open']:>8} {w4['still_open']:>8}")
    msg.append(f"")
    msg.append(f"May total:  +{len(all_created)} created | -{len(all_resolved)} resolved | net +{len(all_created)-len(all_resolved)}")
    msg.append(f"Currently open: {len(open_tix)}")
    msg.append("```")

    # ━━━ 2. SLA ADHERENCE ━━━
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append("**2. SLA ADHERENCE** _(May 2026)_")
    msg.append("_FR = First Response: was the customer's ticket acknowledged within SLA target? Measured from ticket creation to first agent reply._")
    msg.append("_RT = Resolution Time: was the ticket fully resolved within SLA target? Measured from creation to resolution, excluding time paused (awaiting customer). Schedule: Mon-Fri 10AM-8PM IST._")
    msg.append(f"FR **{m_fr_pct}%** hit ({m_sla['fr_h']}/{m_fr_t}) · RT **{m_rt_pct}%** hit ({m_sla['rt_h']}/{m_rt_t})")
    msg.append("```")
    msg.append(f"{'Week':<6}   {'FR%':>5}   {'RT%':>5}")
    msg.append("─" * 22)
    fr_pcts = []; rt_pcts = []
    for wname, ws, we in WEEKS:
        s = week_data[wname]["sla"]
        ft = s["fr_h"] + s["fr_m"]; rt = s["rt_h"] + s["rt_m"]
        fp = round(s["fr_h"] / ft * 100) if ft else 0
        rp = round(s["rt_h"] / rt * 100) if rt else 0
        fr_pcts.append(fp); rt_pcts.append(rp)
        msg.append(f"{wname:<6}  {sla_color(fp)}{fp:>4}%  {sla_color(rp)}{rp:>4}%")
    msg.append("─" * 22)
    msg.append(f"{'TOTAL':<6}  {sla_color(m_fr_pct)}{m_fr_pct:>4}%  {sla_color(m_rt_pct)}{m_rt_pct:>4}%")
    msg.append("```")

    # Per-account SLA table
    sla_acct = defaultdict(lambda: {"fr_h": 0, "fr_m": 0, "rt_h": 0, "rt_m": 0, "n": 0})
    for did in month_ticket_ids:
        t = all_tickets.get(did)
        if not t: continue
        a = acct(t)
        tr = t.get("sla_summary", {}).get("sla_tracker", {})
        has = False
        for m in tr.get("metric_target_summaries", []):
            nm = m.get("metric_definition", {}).get("name", ""); st = m.get("status", "")
            if "First" in nm:
                if st == "hit": sla_acct[a]["fr_h"] += 1; has = True
                elif st == "miss": sla_acct[a]["fr_m"] += 1; has = True
            elif "Resolution" in nm:
                if st == "hit": sla_acct[a]["rt_h"] += 1; has = True
                elif st == "miss": sla_acct[a]["rt_m"] += 1; has = True
        if has: sla_acct[a]["n"] += 1

    msg.append("```")
    msg.append(f" #  {'Account':<18}  {'Pool':>4}   {'FR%':>5}   {'RT%':>5}")
    msg.append(f"──  {'─'*18}  {'─'*4}  {'─'*6}  {'─'*6}")
    sorted_sla = sorted(sla_acct.items(), key=lambda x: x[1]["n"], reverse=True)
    shown = []; rest = []
    for a, d in sorted_sla:
        if len(shown) < 12 and d["n"] >= 3: shown.append((a, d))
        else: rest.append((a, d))
    for i, (a, d) in enumerate(shown, 1):
        frd = d["fr_h"] + d["fr_m"]; rtd = d["rt_h"] + d["rt_m"]
        fp = round(d["fr_h"] / frd * 100) if frd else 0
        rp = round(d["rt_h"] / rtd * 100) if rtd else 0
        fp_s = f"{sla_color(fp)}{fp}%" if frd else "  -  "
        rp_s = f"{sla_color(rp)}{rp}%" if rtd else "  -  "
        msg.append(f"{i:>2}  {a[:18]:<18}  {d['n']:>4}  {fp_s:>6}  {rp_s:>6}")
    if rest:
        rm_n = sum(d["n"] for _, d in rest)
        rm_frh = sum(d["fr_h"] for _, d in rest); rm_frm = sum(d["fr_m"] for _, d in rest)
        rm_rth = sum(d["rt_h"] for _, d in rest); rm_rtm = sum(d["rt_m"] for _, d in rest)
        rm_frd = rm_frh + rm_frm; rm_rtd = rm_rth + rm_rtm
        rfp = f"{round(rm_frh/rm_frd*100)}%" if rm_frd else "-"
        rrp = f"{round(rm_rth/rm_rtd*100)}%" if rm_rtd else "-"
        msg.append(f"    {len(rest)} more accts       {rm_n:>4}    {rfp:>4}    {rrp:>4}")
    msg.append("")
    msg.append("🟢 ≥75%  🟡 60-74%  🟠 40-59%  🔴 <40%")
    msg.append("```")

    # ━━━ 4. RESOLUTION RATE ━━━
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append("**3. RESOLUTION RATE** _(weekly)_")
    msg.append("```")
    msg.append(f"{'Week':>10}  {'Created':>8}  {'Resolved':>8}    {'Net':>5}")
    msg.append("─" * 37)
    created_vals = []; resolved_vals = []
    tc = 0; tr2 = 0
    for wname, ws, we in WEEKS:
        wd = week_data[wname]
        tc += wd["created"]; tr2 += wd["resolved"]
        net = wd["net"]
        dn = "▲" if net > 0 else ("▼" if net < 0 else "=")
        emoji = " ✅" if net <= 0 else ""
        label = f"{wname} ({ws[8:]}-{we[8:]})"
        msg.append(f"{label:>10}  {wd['created']:>8}  {wd['resolved']:>8}   {dn} {abs(net):>3}{emoji}")
        created_vals.append(wd["created"]); resolved_vals.append(wd["resolved"])
    msg.append("─" * 37)
    tnet = tc - tr2
    tdn = "▲" if tnet > 0 else ("▼" if tnet < 0 else "=")
    msg.append(f"{'TOTAL':>10}  {tc:>8}  {tr2:>8}   {tdn} {abs(tnet):>3}")
    msg.append("")
    msg.append(f"Resolve ratio: {tr2}/{tc} = {rr}%")
    msg.append("```")

    # ━━━ 5. RESOLUTION TAT ━━━
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append(f"**4. RESOLUTION TAT** _(resolved in May)_")
    msg.append("```")
    msg.append(f"{'Severity':<10}  {'P10':>8}  {'P50':>8}  {'P90':>8}")
    msg.append("─" * 40)
    if m_tat:
        msg.append(f"{'All':<10}  {fh(pctl(m_tat,10)):>8}  {fh(pctl(m_tat,50)):>8}  {fh(pctl(m_tat,90)):>8}")
    tat_sev = defaultdict(list)
    for t in all_resolved:
        sla_tat_min = None
        tr = t.get("sla_summary", {}).get("sla_tracker", {})
        for m_item in tr.get("metric_target_summaries", []):
            nm = m_item.get("metric_definition", {}).get("name", "")
            if "Resolution" in nm and m_item.get("completed_in") is not None:
                sla_tat_min = m_item["completed_in"]; break
        if sla_tat_min is not None and sla_tat_min > 0:
            tat_sev[sev(t)].append(sla_tat_min / 60)
        elif sla_tat_min == 0:
            continue
        else:
            cr = t.get("created_date", ""); cl = t.get("actual_close_date", "")
            if cr and cl:
                try:
                    c1 = datetime.datetime.fromisoformat(cr.replace("Z", "+00:00")).replace(tzinfo=None)
                    c2 = datetime.datetime.fromisoformat(cl.replace("Z", "+00:00")).replace(tzinfo=None)
                    h = (c2 - c1).total_seconds() / 3600
                    if h >= 0: tat_sev[sev(t)].append(h)
                except: pass
    for sv in ["blocker", "high", "medium", "low"]:
        sl = sorted(tat_sev.get(sv, []))
        if sl:
            msg.append(f"{sv.capitalize():<10}  {fh(pctl(sl,10)):>8}  {fh(pctl(sl,50)):>8}  {fh(pctl(sl,90)):>8}")
    msg.append("")
    msg.append(f"{'By Week':<10}  {'P10':>8}  {'P50':>8}  {'P90':>8}")
    msg.append("─" * 40)
    p50_vals = []
    for wname, ws, we in WEEKS:
        t_list = week_data[wname]["tat"]
        if t_list:
            p10 = fh(pctl(t_list, 10)); p50 = fh(pctl(t_list, 50)); p90 = fh(pctl(t_list, 90))
            p50_vals.append(pctl(t_list, 50))
        else:
            p10 = p50 = p90 = "-"; p50_vals.append(0)
        msg.append(f"{wname:<10}  {p10:>8}  {p50:>8}  {p90:>8}")
    msg.append("```")

    # ━━━ 6. WHO RESOLVES ━━━
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append(f"**5. WHO RESOLVES** _(May 2026)_")
    msg.append("```")
    m_rb_total = sum(m_rb.values()) or 1
    for k, c in m_rb.most_common():
        icon = {"Resolved by Support": "🛠️", "Resolved by Product": "📦", "Resolved by Engineering": "⚙️"}.get(k, "")
        name = k.replace("Resolved by ", "")
        msg.append(f"{icon}  {name:<16}  {c:>4}   ({round(c/m_rb_total*100)}%)")
    msg.append("")
    msg.append(f"{'Week':<6}  {'Support':>10}  {'Engg':>10}  {'Product':>10}")
    msg.append("─" * 44)
    for wname, ws, we in WEEKS:
        rb = week_data[wname]["rb"]
        total_r = sum(rb.values()) or 1
        sp = rb.get("Resolved by Support", 0); ep = rb.get("Resolved by Engineering", 0); pp = rb.get("Resolved by Product", 0)
        msg.append(f"{wname:<6}  {sp:>4} ({round(sp/total_r*100):>2}%)  {ep:>4} ({round(ep/total_r*100):>2}%)  {pp:>4} ({round(pp/total_r*100):>2}%)")
    msg.append("```")

    # ━━━ 7. FRIDAY AI ━━━
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append(f"**6. FRIDAY AI** _(May 2026)_")
    msg.append("```")
    for wname in ["W1","W2","W3","W4"]:
        analyzed, sample_n, total_n = friday_weekly[wname]
        cov = round(analyzed / sample_n * 100) if sample_n else 0
        msg.append(f"🤖  {wname}: {analyzed}/{sample_n} sampled = {cov}% coverage  (total: {total_n})")
    msg.append(f"⚡  Time to RCA:        P50 ~5min")
    msg.append("```")

    # ━━━ 8. CX LEAD LOAD ━━━
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append(f"**7. CX LEAD LOAD** _(current open)_")
    msg.append("```")
    scols = ["queued", "work_in_progress", "awaiting_customer_response", "awaiting_development",
             "awaiting_product_assist", "in_development", "Reassigned to Customer Support", "Reopen"]
    ch = ["Que", "WIP", "AwC", "AwD", "AwP", "InD", "Rsg", "Rop"]
    mx = defaultdict(Counter)
    for t in open_tix: mx[cx(t)][stg(t)] += 1
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

    # ━━━ 9. AGING TICKETS ━━━
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append("**8. AGING TICKETS** _(open, by age)_")
    msg.append("```")
    msg.append(f"{'Age':<14} {'Count':>5}    {'% of Open':>9}")
    msg.append("─" * 34)
    msg.append(f"{'7+ days':<14} {len(tix_7):>5}    {round(len(tix_7)/len(open_tix)*100) if open_tix else 0:>8}%")
    msg.append(f"{'15+ days':<14} {len(tix_15):>5}    {round(len(tix_15)/len(open_tix)*100) if open_tix else 0:>8}%")
    msg.append(f"{'30+ days':<14} {len(tix_30):>5}    {round(len(tix_30)/len(open_tix)*100) if open_tix else 0:>8}%")
    msg.append("```")

    # 30+ holders
    aging_lead = Counter(cx(t) for t in tix_30)
    top3 = [(n, c) for n, c in aging_lead.most_common(4) if n != "Unassigned"][:3]
    holders = " · ".join(f"{n} ({c})" for n, c in top3)
    unassigned_30 = aging_lead.get("Unassigned", 0)
    if unassigned_30: holders += f" · {unassigned_30} unassigned"
    msg.append(f"30+ holders: {holders}")

    stage_short_map = {"awaiting_customer_response": "AwCust", "awaiting_development": "AwDev",
                       "awaiting_product_assist": "AwProd", "work_in_progress": "WIP",
                       "queued": "Queued", "in_development": "InDev",
                       "Reassigned to Customer Support": "Reassigned", "Reopen": "Reopen"}
    aging_stages = Counter(stage_short_map.get(stg(t), stg(t)[:12]) for t in tix_30)
    stuck = " · ".join(f"{s} ({c})" for s, c in aging_stages.most_common(3))
    msg.append(f"30+ stuck in: {stuck}")

    # ━━━ 9. STILL OPEN — STAGE BREAKDOWN ━━━
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append("**9. STILL OPEN — WHERE ARE THEY STUCK?**")
    msg.append("_Tickets created in each week that are still open today, by current stage_")
    msg.append("```")
    all_stages_set = set()
    for wname in ["W1","W2","W3","W4"]:
        all_stages_set.update(week_data[wname]["still_open_stages"].keys())
    stage_order = ["Queued", "WIP", "AwCust", "AwDev", "AwProd", "InDev", "Reassigned", "Reopen"]
    stages_present = [s for s in stage_order if s in all_stages_set]
    for s in sorted(all_stages_set):
        if s not in stages_present: stages_present.append(s)

    so_header = f"{'Week':<6} {'Open':>5}"
    for s in stages_present: so_header += f" {s:>6}"
    msg.append(so_header)
    msg.append("─" * len(so_header))
    total_still = 0
    total_stage = Counter()
    for wname in ["W1","W2","W3","W4"]:
        wd = week_data[wname]
        so = wd["still_open"]
        total_still += so
        row = f"{wname:<6} {so:>5}"
        for s in stages_present:
            v = wd["still_open_stages"].get(s, 0)
            total_stage[s] += v
            row += f" {'.' if not v else v:>6}"
        msg.append(row)
    msg.append("─" * len(so_header))
    row = f"{'TOTAL':<6} {total_still:>5}"
    for s in stages_present:
        v = total_stage[s]
        row += f" {'.' if not v else v:>6}"
    msg.append(row)
    msg.append("```")

    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append(f"_Generated {today_str} | Filter: Support tickets excl WMS/Roadmap cohorts, WMS Inbound/Outbound pods_")

    output = "\n".join(msg)
    print(output)
    return output


def check_friday(ticket):
    """Check if Friday AI analyzed this ticket via Timeline API."""
    try:
        r = apicall("timeline-entries.list", {"object": ticket["id"], "limit": 20})
        for e in r.get("timeline_entries", []):
            if e.get("type") != "timeline_comment": continue
            author = (e.get("created_by") or {}).get("display_name", "")
            if "friday" in author.lower():
                return True
        return False
    except:
        return False


if __name__ == "__main__":
    main()
