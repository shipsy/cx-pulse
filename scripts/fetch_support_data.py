"""Shared data fetcher for CX Pulse reports. Used by both founder_dashboard.py and morning_brief_cli.py."""

import json, urllib.request, datetime
from collections import Counter

EXCLUDE_COHORTS = {"WMS", "Roadmap"}

ACCOUNT_ALIASES = {
    "reliance (ril)":"Reliance","ril":"Reliance","reliance":"Reliance",
    "reliancehyperlocal":"Reliance","ril-tira":"Reliance",
    "1p jiomart reliance":"Reliance","reliance - 3p":"Reliance",
    "qwik logistics":"Reliance","rcpldemo":"Reliance",
    "dtdc":"DTDC","dtdc.in":"DTDC",
    "aramex global":"Aramex","aramex vw":"Aramex","aramex move":"Aramex",
    "aramex same day delivery":"Aramex","aramex ro":"Aramex",
    "aramex oceania":"Aramex","aramex freight":"Aramex","aramex":"Aramex","aramex sdd":"Aramex",
    "flipkart":"Flipkart","fkfooddemo":"Flipkart",
    "rozana":"Rozana","rozanaondemand":"Rozana",
    "wellness forever":"Wellness Forever","wellness forever (tms)":"Wellness Forever",
    "[wms] wellness forever":"Wellness Forever",
    "milkbasket":"Milkbasket","kama ayurveda":"Kama Ayurveda",
    "movin":"Movin","movin1demo":"Movin","movindemo":"Movin",
    "apollo247":"Apollo247","spencers":"Spencers",
    "hnk-br1-primary":"Heineken","hnk-br1-secondary":"Heineken",
    "myntra":"Myntra","myntrahl":"Myntra",
    "swiggy":"Swiggy","swiggytms":"Swiggy",
    "proconnect":"Proconnect","proconnect account":"Proconnect",
    "wakefit":"Wakefit","wakefitdemo":"Wakefit",
    "box account":"Box","box":"Box",
    "expeditorsdemo":"Expeditors","expeditors":"Expeditors",
    "nxlogistics":"NX Logistics","caratlane":"CaratLane","sbt":"SBT",
    "healthkart":"Healthkart","field":"Field","incnut":"Incnut",
    "frontline":"Frontline","[wms] shipsy":"[WMS] Shipsy",
}

def normalize_account(raw):
    if not raw or raw == "Unknown": return "Unknown"
    n = raw.strip()
    if n.endswith(" - Default Workspace"): n = n[:-20]
    if n.endswith(" Account"): n = n[:-8]
    return ACCOUNT_ALIASES.get(n.lower().strip(), n)


def apicall(token, endpoint, payload):
    d = json.dumps(payload).encode()
    r = urllib.request.Request(
        f"https://api.devrev.ai/{endpoint}", data=d,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode(), strict=False)


def fetch_all_support(token, today_str, seven_ago_str, stderr=None):
    """Fetch all data needed for reports. Returns dict with all computed data."""
    import sys
    log = stderr or sys.stderr
    cutoff = (datetime.date.fromisoformat(seven_ago_str) - datetime.timedelta(days=7)).isoformat()

    # 1. ALL open tickets (state filter, full pagination)
    print("  Fetching open tickets...", file=log)
    raw_open = []; cur = None
    while True:
        p = {"type": ["ticket"], "state": ["open", "in_progress"], "limit": 100}
        if cur: p["cursor"] = cur
        r = apicall(token, "works.list", p)
        w = r.get("works", []); raw_open.extend(w); cur = r.get("next_cursor", "")
        if not w or not cur: break
    open_tix = [t for t in raw_open if t.get("subtype") == "Support"
                and (t.get("custom_fields", {}).get("tnt__customer_cohort_dropdown", "") or "TBD") not in EXCLUDE_COHORTS]
    print(f"    {len(raw_open)} raw -> {len(open_tix)} support", file=log)

    # 2. Recent resolved/closed/canceled (smart stop at modified_date < cutoff)
    print("  Fetching resolved/closed tickets...", file=log)
    raw_closed = []; cur = None; pg = 0
    while True:
        pg += 1
        p = {"type": ["ticket"], "state": ["resolved", "closed"], "limit": 100}
        if cur: p["cursor"] = cur
        r = apicall(token, "works.list", p)
        w = r.get("works", []); raw_closed.extend(w); cur = r.get("next_cursor", "")
        if not w or not cur: break
        last_mod = w[-1].get("modified_date", "")[:10]
        if last_mod and last_mod < cutoff: break
        if pg > 200: break
    closed_support = [t for t in raw_closed if t.get("subtype") == "Support"
                      and (t.get("custom_fields", {}).get("tnt__customer_cohort_dropdown", "") or "TBD") not in EXCLUDE_COHORTS]
    print(f"    {len(raw_closed)} raw in {pg} pages -> {len(closed_support)} support", file=log)

    # Split by stage
    resolved_all = [t for t in closed_support if t.get("stage", {}).get("name", "").lower() in ("resolved", "closed")]
    canceled_all = [t for t in closed_support if t.get("stage", {}).get("name", "") == "canceled"]

    # Time-based filters
    resolved_7d = [t for t in resolved_all if t.get("actual_close_date", "")[:10] >= seven_ago_str]
    resolved_today = [t for t in resolved_all if t.get("actual_close_date", "")[:10] == today_str]
    canceled_today = [t for t in canceled_all if t.get("actual_close_date", "")[:10] == today_str]

    # Created today (across all states)
    created_open = [t for t in open_tix if t.get("created_date", "")[:10] == today_str]
    created_closed = [t for t in closed_support if t.get("created_date", "")[:10] == today_str]
    created_today_total = len(created_open) + len(created_closed)

    # Metrics
    blockers = [t for t in open_tix if (t.get("severity") or "").lower() == "blocker"]
    unanswered = [t for t in open_tix if t.get("needs_response") == True]
    unassigned = [t for t in open_tix if not t.get("custom_fields", {}).get("tnt__assignee")]

    return {
        "open_tix": open_tix,
        "resolved_7d": resolved_7d,
        "resolved_today": resolved_today,
        "canceled_today": canceled_today,
        "closed_support": closed_support,
        "blockers": blockers,
        "unanswered": unanswered,
        "unassigned": unassigned,
        "created_today_total": created_today_total,
        "created_open": created_open,
        "created_closed": created_closed,
    }
