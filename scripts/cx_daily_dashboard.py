#!/usr/bin/env python3
"""CX Daily Dashboard — deterministic script for daily Slack report.
Fetches from DevRev REST API, computes 8 metrics, outputs formatted Slack message.
Run: python3 scripts/cx_daily_dashboard.py [--dry-run]
  --dry-run: output report but do NOT update snapshot (safe for testing)
Requires: DEVREV_TOKEN env var"""

import json, os, sys, datetime, math, subprocess

DRY_RUN = "--dry-run" in sys.argv
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
TODAY = datetime.date.today()
YESTERDAY = (TODAY - datetime.timedelta(days=1))
DAY_BEFORE = (TODAY - datetime.timedelta(days=2))
SEVEN_AGO = (TODAY - datetime.timedelta(days=7)).isoformat()
CUTOFF = (TODAY - datetime.timedelta(days=14)).isoformat()

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
    "techmahindra":"Reliance",
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

# ═══ CONTRACTUAL SLA POLICIES ═══
# Key: normalized raw DevRev account (lowercase, stripped suffixes).
# Value: [[P1_fr, P1_rt], [P2_fr, P2_rt], [P3_fr, P3_rt], [P4_fr, P4_rt]] in minutes.
# None = no target for that tier/metric.
# Source: "Account to SLA Assignment" (cx-pulse-dashboard, SLA-01 through SLA-25).
CONTRACTUAL_SLA = {
    "ancdelivers": [[15,60],[120,360],[240,720],[480,960]],
    "apollo247": [[15,120],[240,2880],[240,7200],[None,None]],
    "apollopharmalogistics": [[15,120],[240,2880],[240,7200],[None,None]],
    "aramex global": [[240,None],[480,None],[960,None],[None,None]],
    "aramex move": [[60,240],[120,480],[240,1440],[720,2880]],
    "aster pharmacy": [[15,20],[30,1440],[120,5760],[720,None]],
    "asterksa": [[60,None],[480,None],[960,None],[1440,None]],
    "aujanexport": [[15,60],[120,360],[240,720],[480,960]],
    "aujanimport": [[15,60],[120,360],[240,720],[480,960]],
    "avery": [[60,720],[60,1440],[240,2880],[1440,7200]],
    "box": [[15,120],[240,2880],[240,7200],[None,None]],
    "caratlane": [[None,None],[None,None],[240,7200],[None,None]],
    "catalent": [[30,60],[240,480],[360,1440],[600,2160]],
    "dtdc": [[15,120],[60,1080],[120,2160],[240,2700]],
    "extra": [[240,None],[480,None],[960,None],[None,None]],
    "flipkart": [[30,60],[240,480],[360,1440],[600,2160]],
    "flow express": [[15,120],[240,2880],[240,7200],[None,None]],
    "floward": [[240,None],[480,None],[960,None],[1440,None]],
    "flowpl": [[15,120],[240,2880],[240,7200],[None,None]],
    "gmggroup": [[15,120],[240,2880],[240,7200],[None,None]],
    "gwc": [[60,None],[480,None],[960,None],[1440,None]],
    "heineken-br1": [[60,240],[240,960],[360,None],[None,None]],
    "instamart": [[120,None],[480,None],[960,None],[1440,None]],
    "iwexpress": [[15,120],[240,2880],[240,7200],[None,None]],
    "jeebly": [[60,None],[480,None],[960,None],[1440,None]],
    "kfg kout": [[15,60],[30,120],[60,180],[120,1440]],
    "meatigo": [[15,120],[240,2880],[240,7200],[None,None]],
    "movin": [[30,60],[120,360],[240,720],[480,960]],
    "movin1demo": [[30,60],[120,360],[240,720],[480,960]],
    "myntra": [[30,60],[240,480],[360,1440],[600,2160]],
    "myntrahl": [[30,60],[240,480],[360,1440],[600,2160]],
    "omantel": [[15,120],[240,2880],[240,7200],[None,None]],
    "partnr": [[240,None],[480,None],[960,None],[1440,None]],
    "proconnect": [[240,None],[480,None],[960,None],[1440,None]],
    "qatar post": [[45,60],[360,720],[540,2160],[720,3600]],
    "rozana": [[240,None],[480,None],[960,None],[None,None]],
    "sbt": [[15,120],[240,2880],[240,7200],[None,None]],
    "scootsy": [[120,None],[480,None],[960,None],[1440,None]],
    "smiths news": [[15,60],[15,240],[240,480],[480,960]],
    "spencers": [[60,None],[480,None],[960,None],[1440,None]],
    "spencersdemo": [[60,None],[480,None],[960,None],[1440,None]],
    "starlinks": [[240,None],[480,None],[960,None],[None,None]],
    "swiggytms": [[120,None],[480,None],[960,None],[1440,None]],
    "teleport my": [[60,240],[480,960],[960,2880],[1440,4320]],
    "teleportdemo": [[60,240],[480,960],[960,2880],[1440,4320]],
    "tibbygo": [[60,None],[120,None],[240,None],[480,None]],
    "ubteam": [[60,240],[480,1080],[960,None],[1440,None]],
    "wakefit": [[120,None],[480,None],[960,None],[None,None]],
    "wellness forever": [[15,120],[240,2880],[240,7200],[None,None]],
}

# Default SLA targets (fallback for accounts without a contractual policy)
DEFAULT_SLA_TARGETS = {
    "blocker": [15, 240],    # 15m FR, 4h RT
    "high":    [60, 2160],   # 1h FR, 36h RT
    "medium":  [120, 2880],  # 2h FR, 48h RT
    "low":     [240, 4320],  # 4h FR, 72h RT
}

SLA_TIER = {"blocker": 0, "high": 1, "medium": 2, "low": 3}

# Accounts with no tiered contract — use default SLA targets
SLA_NO_TIERS = {
    "ajslogisticsprod","burgerking","burjeelpharmacy","chronodiali","expeditors",
    "expeditors.com","expeditorsdemo","healthkart","jio","rcpl","reliance",
    "reliance ril","reliancehyperlocal","reliancepbg","ril","ril-tira","zajel",
}

# Internal/demo/no-contract accounts — excluded from SLA reporting
SLA_SKIP = {
    "eximdemo","fk food","jayashree","mbrf","nxlogistics",
    "service-now","shipsy","shipsy.ai","shipsyflamingo","test","visl","xhawi.com",
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
        json.dump(payload, f)
        f.flush()
        tmppath = f.name
    try:
        for attempt in range(_retries):
            r = subprocess.run(["curl", "-s", "--compressed", "--retry", "1",
                "--max-time", "90", "-X", "POST", f"{API}/{endpoint}",
                "-H", f"Authorization: Bearer {TOKEN}",
                "-H", "Content-Type: application/json",
                "-d", f"@{tmppath}"], capture_output=True, text=True, timeout=120)
            if not r.stdout.strip():
                if attempt < _retries - 1:
                    time.sleep(1)
                    continue
                raise RuntimeError(f"curl returned empty (rc={r.returncode})")
            try:
                return json.loads(r.stdout, strict=False)
            except json.JSONDecodeError:
                if attempt < _retries - 1:
                    time.sleep(1)
                    continue
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
    if pct >= 75: return "🟢"
    elif pct >= 60: return "🟡"
    elif pct >= 40: return "🟠"
    return "🔴"

def arrow(prev, now):
    d = now - prev
    if d > 0: return f"▲ {d:>2}"
    elif d < 0: return f"▼ {abs(d):>2}"
    return f"= {0:>2}"

def arrow_emoji(prev, now, lower_is_good=True):
    d = now - prev
    if d == 0: return ""
    if lower_is_good:
        return " ✅" if d < 0 else " ⚠️"
    return " ✅" if d > 0 else " ⚠️"

def sla_raw_key(t):
    """Normalize raw DevRev account name for contractual SLA lookup."""
    n = ((t.get("rev_org") or {}).get("display_name", "") or "").strip().lower()
    if n.endswith(" - default workspace"): n = n[:-20].strip()
    if n.endswith(" account"): n = n[:-8].strip()
    return n

def contractual_targets(t):
    """Get [fr_target_min, rt_target_min] for a ticket based on its account + severity."""
    key = sla_raw_key(t)
    severity = sev(t)
    tier_idx = SLA_TIER.get(severity)
    if tier_idx is None:
        return [None, None]
    policy = CONTRACTUAL_SLA.get(key)
    explicit = policy[tier_idx] if policy and tier_idx < len(policy) else [None, None]
    fallback = DEFAULT_SLA_TARGETS.get(severity, [None, None])
    return [
        explicit[0] if explicit[0] is not None else fallback[0],
        explicit[1] if explicit[1] is not None else fallback[1],
    ]

def contractual_eval(t):
    """Evaluate a ticket against contractual SLA. Returns {fr: hit/miss/None, rt: hit/miss/None, category}."""
    key = sla_raw_key(t)
    if key in SLA_SKIP:
        return {"fr": None, "rt": None, "category": "skip"}
    category = "contractual" if key in CONTRACTUAL_SLA else ("no_tiers" if key in SLA_NO_TIERS else "default")
    targets = contractual_targets(t)
    # Extract completed_in from SLA tracker
    tr = t.get("sla_summary", {}).get("sla_tracker", {})
    c0 = None  # FR completed_in (minutes)
    c1 = None  # RT completed_in (minutes)
    st0 = ""   # FR DevRev status
    st1 = ""   # RT DevRev status
    for m in tr.get("metric_target_summaries", []):
        nm = m.get("metric_definition", {}).get("name", "")
        if "First" in nm:
            ci = m.get("completed_in")
            if ci is not None: c0 = ci
            st0 = m.get("status", "")
        elif "Resolution" in nm:
            ci = m.get("completed_in")
            if ci is not None: c1 = ci
            st1 = m.get("status", "")
    fr_result = None
    if targets[0] is not None:
        if c0 is not None and c0 > 0:
            fr_result = "hit" if c0 <= targets[0] else "miss"
        elif st0 in ("hit", "miss"):
            fr_result = st0
    rt_result = None
    if targets[1] is not None:
        if c1 is not None and c1 > 0:
            rt_result = "hit" if c1 <= targets[1] else "miss"
        elif st1 in ("hit", "miss"):
            rt_result = st1
    return {"fr": fr_result, "rt": rt_result, "category": category}

def check_friday(ticket):
    """Check Friday AI activity on this ticket. Returns dict with detailed info."""
    result = {"analyzed": False, "has_rca": False, "has_fr": False, "latency_min": None}
    try:
        r = apicall("timeline-entries.list", {"object": ticket["id"], "limit": 30})
        created = ticket.get("created_date", "")
        for e in r.get("timeline_entries", []):
            if e.get("type") != "timeline_comment": continue
            author = (e.get("created_by") or {}).get("display_name", "")
            if "friday" not in author.lower(): continue
            result["analyzed"] = True
            body = e.get("body", "")
            if "Root Cause Analysis" in body or "Auto-Investigation" in body:
                result["has_rca"] = True
            if e.get("visibility") == "external":
                result["has_fr"] = True
                if created and e.get("created_date"):
                    try:
                        t1 = datetime.datetime.fromisoformat(created.replace("Z", "+00:00")).replace(tzinfo=None)
                        t2 = datetime.datetime.fromisoformat(e["created_date"].replace("Z", "+00:00")).replace(tzinfo=None)
                        mins = (t2 - t1).total_seconds() / 60
                        if mins >= 0 and (result["latency_min"] is None or mins < result["latency_min"]):
                            result["latency_min"] = round(mins)
                    except: pass
        return result
    except:
        return result


# ═══ MAIN ═══
def main():
    if not TOKEN:
        print("ERROR: Set DEVREV_TOKEN env var", file=sys.stderr)
        sys.exit(1)

    yday = YESTERDAY.isoformat()
    dbyday = DAY_BEFORE.isoformat()

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
    print(f"  Open: {len(tix)}", file=sys.stderr)

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
        if pg > 200: break
    csup = [t for t in res if is_support(t)]
    print(f"  Closed: {len(csup)} in {pg} pages", file=sys.stderr)

    # ═══ COMPUTED DATA ═══
    total = len(tix)
    blockers = [t for t in tix if sev(t) == "blocker"]
    unanswered = [t for t in tix if t.get("needs_response") == True and stg(t) in ("queued", "work_in_progress")]

    # Resolved 7d (excl canceled)
    resolved_7d = [t for t in csup if t.get("actual_close_date", "")[:10] >= SEVEN_AGO
                   and stg(t).lower() in ("resolved", "closed")]

    # Previous day reconstruction
    open_before_yday = [t for t in tix if t.get("created_date", "")[:10] <= yday]
    closed_after_yday = [t for t in csup if t.get("actual_close_date", "")[:10] > yday
                         and t.get("created_date", "")[:10] <= yday]
    open_yday = len(open_before_yday) + len(closed_after_yday)

    prev_blockers = len([t for t in tix if sev(t) == "blocker" and t.get("created_date", "")[:10] <= yday]) + \
                    len([t for t in csup if sev(t) == "blocker" and t.get("actual_close_date", "")[:10] > yday
                         and t.get("created_date", "")[:10] <= yday])
    # Approximate — can't reconstruct exact previous unanswered
    prev_unanswered = len(unanswered)  # Will use snapshot if available

    # Load snapshot for better previous day data
    snap = None
    snap_raw = {}
    stored_rates = {}
    snap_path = os.path.join(os.path.dirname(__file__), "..", "config", "daily-snapshot.json")
    try:
        with open(snap_path) as f:
            snap_raw = json.load(f)
        stored_rates = snap_raw.get("daily_rates", {})
        snap_date = snap_raw.get("date", "")
        snap_age = (TODAY - datetime.date.fromisoformat(snap_date)).days if snap_date else 999

        if snap_date == yday:
            # Ideal: snapshot is exactly yesterday
            snap = snap_raw
        elif snap_date == TODAY.isoformat():
            # Already ran today — use prior_total stored from earlier run
            if "prior_total" in snap_raw:
                snap = {"total": snap_raw["prior_total"],
                        "blockers": snap_raw.get("prior_blockers", prev_blockers),
                        "unanswered": snap_raw.get("prior_unanswered", len(unanswered)),
                        "blocker_ids": snap_raw.get("prior_blocker_ids", [])}
        elif 0 < snap_age <= 3:
            # Stale but usable — snapshot is 2-3 days old
            snap = snap_raw
            print(f"  Warning: snapshot {snap_age}d old, prior-day values are approximate", file=sys.stderr)
    except:
        pass

    prev_blocker_ids = set()
    if snap:
        open_yday = snap.get("total", open_yday)
        prev_blockers_val = snap.get("blockers", prev_blockers)
        prev_unanswered_val = snap.get("unanswered", len(unanswered))
        prev_blocker_ids = set(snap.get("blocker_ids", []))
    else:
        prev_blockers_val = prev_blockers
        prev_unanswered_val = len(unanswered)
        print("  Warning: no usable snapshot, prior-day values are reconstructed", file=sys.stderr)

    # Blocker breakdown: persisting / closed / downgraded / new / escalated
    current_blocker_ids = set(t.get("display_id", "") for t in blockers)
    blockers_persisting = current_blocker_ids & prev_blocker_ids

    # Tickets that LEFT the blocker list — why?
    no_longer_blocker = prev_blocker_ids - current_blocker_ids
    closed_ids = set(t.get("display_id", "") for t in csup)
    open_ids = set(t.get("display_id", "") for t in tix)
    blockers_closed = set(did for did in no_longer_blocker if did in closed_ids)
    blockers_downgraded = set(did for did in no_longer_blocker if did in open_ids)  # still open, just not blocker
    blockers_other = no_longer_blocker - blockers_closed - blockers_downgraded  # reclassified out of filter

    # Tickets that JOINED the blocker list — how?
    new_blocker_ids = current_blocker_ids - prev_blocker_ids
    blockers_created = set()  # truly new tickets
    blockers_escalated = set()  # existing tickets escalated to blocker
    for did in new_blocker_ids:
        t = next((t for t in blockers if t.get("display_id") == did), None)
        if t and t.get("created_date", "")[:10] == TODAY.isoformat():
            blockers_created.add(did)  # created today as blocker
        else:
            blockers_escalated.add(did)  # existed before, severity raised to blocker

    # Created/Resolved yesterday (deduped)
    seen = set(); created_yday = []
    for t in list(tix) + list(csup):
        did = t.get("display_id", "")
        if did in seen: continue
        seen.add(did)
        if t.get("created_date", "")[:10] != yday: continue
        if not is_support(t): continue
        if stg(t) == "canceled": continue
        created_yday.append(t)

    resolved_yday = [t for t in csup if t.get("actual_close_date", "")[:10] == yday
                     and stg(t).lower() in ("resolved", "closed")]

    # Canceled yesterday (left open but NOT counted as resolved)
    canceled_yday = [t for t in csup if t.get("actual_close_date", "")[:10] == yday
                     and stg(t) == "canceled" and is_support(t)]

    # Reopened yesterday (currently open, stage=Reopen, modified yesterday)
    reopened_yday = [t for t in tix if stg(t).lower() == "reopen"
                     and t.get("modified_date", "")[:10] == yday]

    # Reconciliation
    if snap:
        expected_open = open_yday + len(created_yday) - len(resolved_yday) - len(canceled_yday) + len(reopened_yday)
        reclass_delta = total - expected_open  # tickets entering/leaving support filter
    else:
        expected_open = None
        reclass_delta = 0

    # ═══ SLA (Contractual) ═══
    sla_all = {"fr_h": 0, "fr_m": 0, "rt_h": 0, "rt_m": 0}
    sla_acct = defaultdict(lambda: {"fr_h": 0, "fr_m": 0, "rt_h": 0, "rt_m": 0, "n": 0, "category": ""})
    sla_cats = Counter()  # contractual / no_tiers / default / skip
    for t in tix + resolved_7d:
        a = acct(t)
        ev = contractual_eval(t)
        sla_cats[ev["category"]] += 1
        if ev["category"] == "skip":
            continue
        has = False
        if ev["fr"] == "hit": sla_all["fr_h"] += 1; sla_acct[a]["fr_h"] += 1; has = True
        elif ev["fr"] == "miss": sla_all["fr_m"] += 1; sla_acct[a]["fr_m"] += 1; has = True
        if ev["rt"] == "hit": sla_all["rt_h"] += 1; sla_acct[a]["rt_h"] += 1; has = True
        elif ev["rt"] == "miss": sla_all["rt_m"] += 1; sla_acct[a]["rt_m"] += 1; has = True
        if has:
            sla_acct[a]["n"] += 1
            if not sla_acct[a]["category"]: sla_acct[a]["category"] = ev["category"]
    fr_t = sla_all["fr_h"] + sla_all["fr_m"]
    rt_t = sla_all["rt_h"] + sla_all["rt_m"]
    print(f"  SLA: {sla_cats['contractual']} contractual, {sla_cats['no_tiers']} no-tiers, "
          f"{sla_cats['default']} default, {sla_cats['skip']} skip", file=sys.stderr)

    # ═══ RESOLUTION RATE (daily, last 7 days) ═══
    daily_rates = []
    daily_rates_save = {}
    for i in range(7, 0, -1):
        d = (TODAY - datetime.timedelta(days=i)).isoformat()
        if d in stored_rates:
            c, r = stored_rates[d]
        else:
            cr = [t for t in seen_all_dedup(tix, csup) if t.get("created_date", "")[:10] == d and stg(t) != "canceled"]
            rv = [t for t in csup if t.get("actual_close_date", "")[:10] == d and stg(t).lower() in ("resolved", "closed")]
            c, r = len(cr), len(rv)
        daily_rates.append((d, c, r))
        daily_rates_save[d] = [c, r]

    # ═══ TAT (SLA-aware from DevRev's completed_in) ═══
    tat_all = []; tat_sev = defaultdict(list)
    tat_wallclock_fallback = 0
    for t in resolved_7d:
        # Try SLA-aware time first (completed_in minutes from Resolution time metric)
        sla_tat_min = None
        tr = t.get("sla_summary", {}).get("sla_tracker", {})
        for m in tr.get("metric_target_summaries", []):
            nm = m.get("metric_definition", {}).get("name", "")
            if "Resolution" in nm and m.get("completed_in") is not None:
                sla_tat_min = m["completed_in"]
                break
        if sla_tat_min is not None and sla_tat_min > 0:
            h = sla_tat_min / 60  # convert minutes to hours
            tat_all.append(h); tat_sev[sev(t)].append(h)
        elif sla_tat_min == 0:
            continue  # skip: SLA was paused entire duration (no actual support time)
        else:
            # Fallback: wall clock (less accurate — includes customer wait + off-hours)
            cr = t.get("created_date", ""); cl = t.get("actual_close_date", "")
            if cr and cl:
                try:
                    c1 = datetime.datetime.fromisoformat(cr.replace("Z", "+00:00")).replace(tzinfo=None)
                    c2 = datetime.datetime.fromisoformat(cl.replace("Z", "+00:00")).replace(tzinfo=None)
                    h = (c2 - c1).total_seconds() / 3600
                    if h >= 0: tat_all.append(h); tat_sev[sev(t)].append(h); tat_wallclock_fallback += 1
                except: pass
    tat_all.sort()
    if tat_wallclock_fallback:
        print(f"  TAT: {len(tat_all) - tat_wallclock_fallback} SLA-aware + {tat_wallclock_fallback} wall-clock fallback", file=sys.stderr)

    # ═══ WHO RESOLVES ═══
    rb = Counter(t.get("custom_fields", {}).get("tnt__resolved_by", "") for t in resolved_7d
                 if t.get("custom_fields", {}).get("tnt__resolved_by"))
    rb_total = sum(rb.values())

    # ═══ FRIDAY AI ═══
    print("Checking Friday AI coverage...", file=sys.stderr)
    friday_results = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = {pool.submit(check_friday, t): t for t in created_yday}
        for f in as_completed(futs):
            friday_results.append(f.result())
    friday_count = sum(1 for r in friday_results if r["analyzed"])
    friday_rca = sum(1 for r in friday_results if r["has_rca"])
    friday_fr = sum(1 for r in friday_results if r["has_fr"])
    friday_latencies = [r["latency_min"] for r in friday_results if r["latency_min"] is not None]
    friday_latencies.sort()
    friday_coverage = round(friday_count / len(created_yday) * 100) if created_yday else 0
    friday_p50_lat = pctl(friday_latencies, 50) if friday_latencies else None
    friday_avg_lat = round(sum(friday_latencies) / len(friday_latencies)) if friday_latencies else None
    print(f"  Friday: {friday_count}/{len(created_yday)} analyzed, {friday_rca} RCA, {friday_fr} FR sent", file=sys.stderr)

    # ═══ CX LEAD LOAD ═══
    mx = defaultdict(Counter)
    for t in tix: mx[cx(t)][stg(t)] += 1

    # ═══ FORMAT OUTPUT ═══
    yday_str = YESTERDAY.strftime("%d %b")
    dbyday_str = DAY_BEFORE.strftime("%d %b")
    today_str = TODAY.strftime("%d %b %Y")
    net_yday = len(created_yday) - len(resolved_yday)

    msg = []
    msg.append(f"📊 **CX Support — Daily Metrics** | {today_str}")
    msg.append(f"_Data as of {yday_str}_")
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append("**1. PULSE CHECK**")
    msg.append("```")
    msg.append(f"               {dbyday_str:>8}  {yday_str:>8}    Change")
    msg.append(f"Open           {open_yday:>8}  {total:>8}     {arrow(open_yday, total)}")
    # Blocker emoji: based on what actually happened, not just count
    if prev_blocker_ids:
        if len(blockers_closed) > 0 and len(blockers_persisting) == 0:
            bl_emoji = " ✅"  # all old blockers cleared
        elif len(blockers_persisting) == len(prev_blocker_ids) and len(new_blocker_ids) > 0:
            bl_emoji = " 🔴"  # all old persist + new ones added
        elif len(blockers_persisting) == len(prev_blocker_ids) and len(new_blocker_ids) == 0:
            bl_emoji = " ⚠️"  # all old persist, no new but nothing fixed
        elif len(blockers_closed) > 0:
            bl_emoji = " 🟡"  # some progress but still have blockers
        else:
            bl_emoji = " ⚠️"
    else:
        bl_emoji = " ✅" if len(blockers) < prev_blockers_val else (" ⚠️" if len(blockers) > prev_blockers_val else "")

    bl_arrow = arrow(prev_blockers_val, len(blockers))
    msg.append(f"Blockers       {prev_blockers_val:>8}  {len(blockers):>8}     {bl_arrow}{bl_emoji}")
    if prev_blocker_ids:
        parts = []
        parts.append(f"{len(blockers_persisting)} persisting")
        if blockers_closed: parts.append(f"{len(blockers_closed)} closed")
        if blockers_downgraded: parts.append(f"{len(blockers_downgraded)} downgraded")
        if blockers_created: parts.append(f"{len(blockers_created)} new")
        if blockers_escalated: parts.append(f"{len(blockers_escalated)} escalated")
        msg.append(f"  → {' · '.join(parts)}")
    un_arrow = arrow(prev_unanswered_val, len(unanswered))
    un_emoji = " ✅" if len(unanswered) < prev_unanswered_val else (" ⚠️" if len(unanswered) > prev_unanswered_val else "")
    msg.append(f"Unanswered     {prev_unanswered_val:>8}  {len(unanswered):>8}     {un_arrow}{un_emoji}")
    net_sign = "+" if net_yday >= 0 else ""
    msg.append(f"\nYesterday:  +{len(created_yday)} created | -{len(resolved_yday)} resolved | net {net_sign}{net_yday}")
    msg.append("```")

    # SLA (Contractual)
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    fr_pct = round(sla_all["fr_h"] / fr_t * 100) if fr_t else 0
    rt_pct = round(sla_all["rt_h"] / rt_t * 100) if rt_t else 0
    msg.append(f"**2. SLA ADHERENCE (Contract Basis)** _(open + resolved 7d)_")
    msg.append(f"FR **{fr_pct}%** hit ({sla_all['fr_h']}/{fr_t}) · RT **{rt_pct}%** hit ({sla_all['rt_h']}/{rt_t})")
    cat_parts = []
    if sla_cats["contractual"]: cat_parts.append(f"{sla_cats['contractual']} contractual")
    if sla_cats["no_tiers"] + sla_cats["default"]: cat_parts.append(f"{sla_cats['no_tiers'] + sla_cats['default']} default")
    if sla_cats["skip"]: cat_parts.append(f"{sla_cats['skip']} skip")
    msg.append(f"_Pool: {' · '.join(cat_parts)}_")
    msg.append("```")
    msg.append(f" #  {'Account':<18}  {'Pool':>4}   {'FR%':>5}   {'RT%':>5}")
    msg.append(f"──  {'─'*18}  {'─'*4}  {'─'*6}  {'─'*6}")
    sorted_sla = sorted(sla_acct.items(), key=lambda x: x[1]["n"], reverse=True)
    # Show top 12 accounts with 3+ tickets, roll up the rest
    shown = []
    rest = []
    for a, d in sorted_sla:
        if len(shown) < 12 and d["n"] >= 3:
            shown.append((a, d))
        else:
            rest.append((a, d))
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

    # Resolution Rate
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append("**3. RESOLUTION RATE** _(last 7 days)_")
    msg.append("```")
    msg.append(f"{'Date':>8}  {'Created':>8}  {'Resolved':>8}    {'Net':>5}")
    msg.append("─" * 37)
    tc = 0; tr2 = 0
    for d, c, r in daily_rates:
        tc += c; tr2 += r
        net = c - r
        dn = "▲" if net > 0 else ("▼" if net < 0 else "=")
        emoji = " ✅" if net < 0 else ""
        dname = datetime.date.fromisoformat(d).strftime("%d %b")
        msg.append(f"{dname:>8}  {c:>8}  {r:>8}   {dn} {abs(net):>3}{emoji}")
    msg.append("─" * 37)
    tnet = tc - tr2
    tdn = "▲" if tnet > 0 else ("▼" if tnet < 0 else "=")
    msg.append(f"{'TOTAL':>8}  {tc:>8}  {tr2:>8}   {tdn} {abs(tnet):>3}")
    msg.append("")
    rr = round(tr2 / tc * 100) if tc else 0
    msg.append(f"Resolve ratio: {tr2}/{tc} = {rr}%")
    msg.append("```")

    # TAT
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append(f"**4. RESOLUTION TAT** _(resolved last 7d)_")
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

    # Who Resolves
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append(f"**5. WHO RESOLVES** _(resolved last 7d)_")
    msg.append("```")
    for k, c in rb.most_common():
        icon = {"Resolved by Support": "🛠️", "Resolved by Product": "📦", "Resolved by Engineering": "⚙️"}.get(k, "")
        name = k.replace("Resolved by ", "")
        msg.append(f"{icon}  {name:<16}  {c:>4}   ({round(c/rb_total*100)}%)")
    msg.append("```")

    # Friday AI
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append(f"**6. FRIDAY AI** _({yday_str})_")
    msg.append("```")
    msg.append(f"🤖  Tickets created:    {len(created_yday)}")
    msg.append(f"📊  Friday analyzed:    {friday_count}/{len(created_yday)}  ({friday_coverage}%)")
    msg.append(f"🔍  RCA generated:      {friday_rca}")
    msg.append(f"💬  First response sent: {friday_fr}")
    if friday_p50_lat is not None:
        avg_str = f"{friday_avg_lat}m" if friday_avg_lat else "-"
        p50_str = f"{friday_p50_lat:.0f}m" if friday_p50_lat else "-"
        msg.append(f"⚡  Response time:      P50 {p50_str} · Avg {avg_str}")
    msg.append("```")

    # CX Lead Load
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append(f"**7. CX LEAD LOAD** _(current open)_")
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

    # Aging Tickets
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append("**8. AGING TICKETS** _(open, by age)_")

    def ticket_age(t):
        try: return (TODAY - datetime.date.fromisoformat(t.get("created_date", TODAY.isoformat())[:10])).days
        except: return 0

    tix_7 = [t for t in tix if ticket_age(t) >= 7]
    tix_15 = [t for t in tix if ticket_age(t) >= 15]
    tix_30 = [t for t in tix if ticket_age(t) >= 30]

    msg.append("```")
    msg.append(f"{'Age':<14} {'Count':>5}    {'% of Open':>9}")
    msg.append("─" * 34)
    msg.append(f"{'7+ days':<14} {len(tix_7):>5}    {round(len(tix_7)/total*100):>8}%")
    msg.append(f"{'15+ days':<14} {len(tix_15):>5}    {round(len(tix_15)/total*100):>8}%")
    msg.append(f"{'30+ days':<14} {len(tix_30):>5}    {round(len(tix_30)/total*100):>8}%")
    msg.append("```")

    # 30+ holders — OUTSIDE code block so Slack renders @mentions
    aging_lead = Counter(cx(t) for t in tix_30)
    top3 = [(n, c) for n, c in aging_lead.most_common(4) if n != "Unassigned"][:3]
    def slack_tag(name):
        sid = SLACK_ID.get(name)
        return f"<@{sid}>" if sid else name
    holders = " · ".join(f"{slack_tag(n)} ({c})" for n, c in top3)
    unassigned_30 = aging_lead.get("Unassigned", 0)
    if unassigned_30:
        holders += f" · {unassigned_30} unassigned"
    msg.append(f"30+ holders: {holders}")

    # 30+ stuck in
    stage_short = {"awaiting_customer_response": "AwCust", "awaiting_development": "AwDev",
                   "awaiting_product_assist": "AwProd", "work_in_progress": "WIP",
                   "queued": "Queued", "in_development": "InDev",
                   "Reassigned to Customer Support": "Reassigned", "Reopen": "Reopen"}
    aging_stages = Counter(stage_short.get(stg(t), stg(t)[:12]) for t in tix_30)
    stuck = " · ".join(f"{s} ({c})" for s, c in aging_stages.most_common(3))
    msg.append(f"30+ stuck in: {stuck}")

    # Output
    output = "\n".join(msg)
    print(output)

    # Save snapshot — only on real runs, not dry-run/testing
    if DRY_RUN:
        print("DRY RUN — snapshot NOT updated", file=sys.stderr)
        return output
    is_rerun = snap_raw.get("date", "") == TODAY.isoformat()
    prior_total = snap_raw.get("total", total) if not is_rerun else snap_raw.get("prior_total", total)
    prior_blockers = snap_raw.get("blockers", len(blockers)) if not is_rerun else snap_raw.get("prior_blockers", len(blockers))
    prior_unanswered = snap_raw.get("unanswered", len(unanswered)) if not is_rerun else snap_raw.get("prior_unanswered", len(unanswered))
    prior_blocker_ids_save = list(snap_raw.get("blocker_ids", [])) if not is_rerun else snap_raw.get("prior_blocker_ids", [])
    new_snap = {
        "date": TODAY.isoformat(),
        "total": total,
        "blockers": len(blockers),
        "blocker_ids": list(current_blocker_ids),
        "unanswered": len(unanswered),
        "prior_total": prior_total,
        "prior_blockers": prior_blockers,
        "prior_unanswered": prior_unanswered,
        "prior_blocker_ids": prior_blocker_ids_save,
        "daily_rates": daily_rates_save,
        "filter": "subtype=Support, excl WMS/Roadmap cohorts, excl WMS Inbound/Outbound pods, unanswered=queued+WIP only"
    }
    try:
        with open(snap_path, "w") as f:
            json.dump(new_snap, f, indent=2)
        print(f"Snapshot saved: {new_snap}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: could not save snapshot: {e}", file=sys.stderr)

    return output


def seen_all_dedup(tix, csup):
    """Dedup tickets across open and closed."""
    seen = set(); result = []
    for t in list(tix) + list(csup):
        did = t.get("display_id", "")
        if did in seen: continue
        seen.add(did)
        if is_support(t): result.append(t)
    return result


if __name__ == "__main__":
    main()
