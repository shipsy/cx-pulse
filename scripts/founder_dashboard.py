#!/usr/bin/env python3
"""
CX Pulse — Founder Dashboard
One-page executive summary. Reads in 30 seconds.
"""

import json, os, sys, datetime, urllib.request, statistics
from collections import defaultdict, Counter

TOKEN = os.environ.get("DEVREV_TOKEN", "")
API = "https://api.devrev.ai"
NOW_UTC = datetime.datetime.utcnow()
TODAY_UTC = NOW_UTC.date()
IST_OFFSET = datetime.timedelta(hours=5, minutes=30)
NOW_IST = NOW_UTC + IST_OFFSET
TODAY_IST = NOW_IST.date()
SEVEN_DAYS_AGO = (NOW_UTC - datetime.timedelta(days=7)).isoformat() + "Z"

# ── Account consolidation ──
ACCOUNT_ALIASES = {
    "reliance (ril)":"Reliance","ril":"Reliance","reliance":"Reliance",
    "reliancehyperlocal":"Reliance","ril-tira":"Reliance",
    "1p jiomart reliance":"Reliance","reliance - 3p":"Reliance",
    "qwik logistics":"Reliance","rcpldemo":"Reliance",
    "dtdc":"DTDC","dtdc.in":"DTDC",
    "aramex global":"Aramex","aramex vw":"Aramex","aramex move":"Aramex",
    "aramex same day delivery":"Aramex","aramex ro":"Aramex",
    "aramex oceania":"Aramex","aramex freight":"Aramex","aramex":"Aramex",
    "aramex sdd":"Aramex",
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
}

def normalize_account(raw):
    if not raw or raw == "Unknown":
        return "Unknown"
    n = raw.strip()
    if n.endswith(" - Default Workspace"):
        n = n[:-20]
    if n.endswith(" Account"):
        n = n[:-8]
    return ACCOUNT_ALIASES.get(n.lower().strip(), n)

EXCLUDE_COHORTS = {"WMS", "Roadmap"}

# ── API helper ──
def apicall(endpoint, payload):
    d = json.dumps(payload).encode()
    r = urllib.request.Request(
        f"{API}/{endpoint}", data=d,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode(), strict=False)

def fetch_all_tickets(stage_filter=None, max_pages=150):
    """Paginate through works.list to get all tickets."""
    all_tickets = []
    cursor = None
    payload_base = {"type": ["ticket"], "limit": 100}
    if stage_filter:
        payload_base["stage"] = {"name": stage_filter}
    for page in range(max_pages):
        payload = dict(payload_base)
        if cursor:
            payload["cursor"] = cursor
        try:
            resp = apicall("works.list", payload)
        except Exception as e:
            print(f"  [warn] API error on page {page+1}: {e}", file=sys.stderr)
            break
        works = resp.get("works", [])
        all_tickets.extend(works)
        cursor = resp.get("next_cursor")
        if not cursor or not works:
            break
    return all_tickets


def extract_ticket(t):
    """Extract relevant fields from a raw ticket dict."""
    cf = t.get("custom_fields", {})
    cohort = cf.get("tnt__customer_cohort_dropdown", "") or "TBD"
    account_raw = (t.get("rev_org") or t.get("account") or {}).get("display_name", "Unknown")
    account = normalize_account(account_raw)
    severity = (t.get("severity") or "medium").lower()
    sentiment_obj = t.get("sentiment") or {}
    sentiment = sentiment_obj.get("label", "")
    stage_name = (t.get("stage") or {}).get("name", "unknown")
    needs_response = t.get("needs_response", False)
    created = t.get("created_date", "")
    closed = t.get("actual_close_date", "")
    display_id = t.get("display_id", "")
    subtype = t.get("subtype", "")
    assignee = cf.get("tnt__assignee", "")

    # SLA extraction
    sla = t.get("sla_summary", {})
    tracker = sla.get("sla_tracker", {})
    mts = tracker.get("metric_target_summaries", [])
    fr_status = None
    rt_status = None
    for m in mts:
        name = (m.get("metric_definition") or {}).get("name", "")
        if "First" in name:
            fr_status = m.get("status")  # hit, miss, in_progress
        elif "Resolution" in name:
            rt_status = m.get("status")

    # Owner
    owners = t.get("owned_by", [])
    owner_name = owners[0].get("full_name", owners[0].get("display_name", "?")) if owners else "Unassigned"

    # Age in days
    age_days = 0
    if created:
        try:
            cd = datetime.datetime.fromisoformat(created.replace("Z", "+00:00")).replace(tzinfo=None)
            age_days = (NOW_UTC - cd).days
        except:
            pass

    # TAT in hours (for resolved)
    tat_hours = None
    if created and closed:
        try:
            cd = datetime.datetime.fromisoformat(created.replace("Z", "+00:00")).replace(tzinfo=None)
            cl = datetime.datetime.fromisoformat(closed.replace("Z", "+00:00")).replace(tzinfo=None)
            tat_hours = (cl - cd).total_seconds() / 3600
        except:
            pass

    return {
        "id": display_id,
        "cohort": cohort,
        "account": account,
        "severity": severity,
        "sentiment": sentiment,
        "stage": stage_name,
        "needs_response": needs_response,
        "fr_status": fr_status,
        "rt_status": rt_status,
        "owner": owner_name,
        "age_days": age_days,
        "created": created,
        "closed": closed,
        "tat_hours": tat_hours,
        "subtype": subtype,
        "assignee": assignee,
    }


def fmt_pct(num, den):
    if den == 0:
        return "N/A"
    return f"{num*100/den:.0f}%"


def fmt_hours(h):
    if h is None:
        return "N/A"
    if h < 1:
        return f"{h*60:.0f}m"
    if h < 24:
        return f"{h:.1f}h"
    return f"{h/24:.1f}d"


def sentiment_icon(label):
    m = {"Happy": ":)", "Neutral": ":|", "Unhappy": ":(", "Frustrated": ">:("}
    return m.get(label, "?")


def main():
    if not TOKEN:
        print("ERROR: Set DEVREV_TOKEN environment variable", file=sys.stderr)
        sys.exit(1)

    # ── 1. Fetch ALL open tickets (state filter, full pagination) ──
    print("Fetching open tickets...", file=sys.stderr)
    raw_open = []
    cur = None
    while True:
        pl = {"type": ["ticket"], "state": ["open", "in_progress"], "limit": 100}
        if cur: pl["cursor"] = cur
        resp = apicall("works.list", pl)
        raw_open.extend(resp.get("works", []))
        cur = resp.get("next_cursor")
        if not cur or not resp.get("works"): break
    print(f"  Raw open tickets: {len(raw_open)}", file=sys.stderr)

    # ── 2. Fetch ALL resolved + Closed tickets (full pagination) ──
    print("Fetching resolved tickets...", file=sys.stderr)
    raw_resolved = fetch_all_tickets(stage_filter=["resolved", "Closed"])
    print(f"  Raw resolved/Closed: {len(raw_resolved)}", file=sys.stderr)

    # ── 3. Fetch canceled tickets (recent, for Created Today count) ──
    print("Fetching canceled tickets (recent)...", file=sys.stderr)
    raw_canceled = []
    cur = None
    for _ in range(10):  # ~1000 recent canceled, enough for today
        pl = {"type": ["ticket"], "stage": {"name": ["canceled"]}, "limit": 100}
        if cur: pl["cursor"] = cur
        resp = apicall("works.list", pl)
        raw_canceled.extend(resp.get("works", []))
        cur = resp.get("next_cursor")
        if not cur or not resp.get("works"): break
    print(f"  Raw canceled: {len(raw_canceled)}", file=sys.stderr)

    # ── 3. Filter: only Support subtype, exclude WMS/Roadmap cohorts ──
    def is_support(t):
        if t.get("subtype") != "Support":
            return False
        cohort = (t.get("custom_fields") or {}).get("tnt__customer_cohort_dropdown", "") or ""
        if cohort in EXCLUDE_COHORTS:
            return False
        return True

    open_tickets = [extract_ticket(t) for t in raw_open if is_support(t)]
    # For resolved: only those closed in last 7 days
    all_resolved = [extract_ticket(t) for t in raw_resolved if is_support(t)]
    # API already filters to resolved + Closed stages (no canceled)
    resolved_7d = [t for t in all_resolved if t["closed"] and t["closed"] >= SEVEN_DAYS_AGO]
    # API already filters to resolved + Closed stages (no canceled)
    today_str = TODAY_IST.isoformat()
    resolved_today = [t for t in all_resolved
                      if t["closed"] and t["closed"][:10] == today_str]
    # Canceled today (for Created Today count)
    canceled_support = [extract_ticket(t) for t in raw_canceled if is_support(t)]
    canceled_today = [t for t in canceled_support if t["closed"] and t["closed"][:10] == today_str]
    # Created today = open created today + resolved created today + canceled created today
    created_today_open = [t for t in open_tickets if t["created"] and t["created"][:10] == today_str]
    created_today_resolved = [t for t in resolved_today if t["created"] and t["created"][:10] == today_str]
    created_today_canceled = [t for t in canceled_today if t["created"] and t["created"][:10] == today_str]

    total_open = len(open_tickets)
    total_resolved_today = len(resolved_today)
    total_created_today = len(created_today_open) + len(created_today_resolved) + len(created_today_canceled)

    # ── HEADLINE NUMBERS ──
    resolution_rate_den = total_resolved_today + total_open
    resolution_rate = total_resolved_today * 100 / resolution_rate_den if resolution_rate_den else 0

    # ── SLA PERFORMANCE (open tickets) ──
    fr_hit = sum(1 for t in open_tickets if t["fr_status"] == "hit")
    fr_miss = sum(1 for t in open_tickets if t["fr_status"] == "miss")
    fr_total = fr_hit + fr_miss  # Only count decided ones
    fr_ip = sum(1 for t in open_tickets if t["fr_status"] == "in_progress")

    rt_hit = sum(1 for t in open_tickets if t["rt_status"] == "hit")
    rt_miss = sum(1 for t in open_tickets if t["rt_status"] == "miss")
    rt_total = rt_hit + rt_miss
    rt_ip = sum(1 for t in open_tickets if t["rt_status"] == "in_progress")

    # ── Account-wise aggregation ──
    acct_data = defaultdict(lambda: {"total": 0, "fr_hit": 0, "fr_decided": 0,
                                      "rt_hit": 0, "rt_decided": 0,
                                      "unanswered": 0, "sentiments": [],
                                      "sla_miss": 0, "blockers": 0})
    for t in open_tickets:
        a = t["account"]
        d = acct_data[a]
        d["total"] += 1
        if t["fr_status"] in ("hit", "miss"):
            d["fr_decided"] += 1
            if t["fr_status"] == "hit":
                d["fr_hit"] += 1
        if t["rt_status"] in ("hit", "miss"):
            d["rt_decided"] += 1
            if t["rt_status"] == "hit":
                d["rt_hit"] += 1
        if t["fr_status"] == "miss" or t["rt_status"] == "miss":
            d["sla_miss"] += 1
        if t["needs_response"]:
            d["unanswered"] += 1
        if t["sentiment"]:
            d["sentiments"].append(t["sentiment"])
        if t["severity"] == "blocker":
            d["blockers"] += 1

    # Sort accounts by ticket count desc
    sorted_accounts = sorted(acct_data.items(), key=lambda x: -x[1]["total"])

    # ── TAT percentiles (resolved last 7 days) ──
    tat_all = [t["tat_hours"] for t in resolved_7d if t["tat_hours"] is not None]
    tat_by_sev = defaultdict(list)
    for t in resolved_7d:
        if t["tat_hours"] is not None:
            tat_by_sev[t["severity"]].append(t["tat_hours"])

    def percentiles(vals):
        if not vals:
            return (None, None, None)
        s = sorted(vals)
        n = len(s)
        p10 = s[max(0, int(n * 0.10))]
        p50 = s[max(0, int(n * 0.50))]
        p90 = s[max(0, min(n - 1, int(n * 0.90)))]
        return (p10, p50, p90)

    # ── Sentiment distribution (open) ──
    sent_counts = Counter(t["sentiment"] for t in open_tickets)
    sent_happy = sent_counts.get("Happy", 0)
    sent_neutral = sent_counts.get("Neutral", 0)
    sent_unhappy = sent_counts.get("Unhappy", 0)
    sent_frustrated = sent_counts.get("Frustrated", 0)
    sent_nodata = sent_counts.get("", 0)

    # ── Red flags ──
    unanswered_total = sum(1 for t in open_tickets if t["needs_response"])
    stale_5d = sum(1 for t in open_tickets if t["age_days"] >= 5)
    stale_10d = sum(1 for t in open_tickets if t["age_days"] >= 10)
    blockers = [t for t in open_tickets if t["severity"] == "blocker"]
    high_sev = [t for t in open_tickets if t["severity"] == "high"]

    # Owner load
    owner_load = Counter(t["owner"] for t in open_tickets)

    # ── Dominant sentiment for an account ──
    def dominant_sentiment(sentiments):
        if not sentiments:
            return "N/A"
        c = Counter(sentiments)
        # Priority: Frustrated > Unhappy > Neutral > Happy
        for s in ["Frustrated", "Unhappy", "Neutral", "Happy"]:
            if c.get(s, 0) > 0:
                # If worst sentiment is >30% of total, show it
                if c[s] / len(sentiments) > 0.25:
                    return sentiment_icon(s)
        top = c.most_common(1)[0][0]
        return sentiment_icon(top)

    # ══════════════════════════════════════════════════
    # RENDER DASHBOARD
    # ══════════════════════════════════════════════════
    W = 58
    bar = "=" * W
    thin = "-" * W

    print()
    print(bar)
    print(f"  CX SUPPORT DASHBOARD | {TODAY_IST.strftime('%d %b %Y')}")
    print(bar)
    print()

    # ── TREND & THROUGHPUT ──
    # Load yesterday's snapshot for trend
    snap = None
    try:
        import os as _os
        snap_path = _os.path.join(_os.path.dirname(__file__), "..", "config", "daily-snapshot.json")
        with open(snap_path) as _f:
            snap = json.load(_f)
        snap_date = datetime.datetime.strptime(snap["date"], "%Y-%m-%d").date()
        if (TODAY_IST - snap_date).days > 2:
            snap = None
    except:
        snap = None

    today_ids = set(t["id"] for t in open_tickets)
    blocker_count = sum(1 for t in open_tickets if t.get("severity") == "blocker")
    unanswered_count = sum(1 for t in open_tickets if t.get("needs_response") == True)
    unassigned_count = sum(1 for t in open_tickets if not t.get("assignee"))

    print("  TREND & THROUGHPUT")
    if snap:
        yids = set(snap.get("ticket_ids", []))
        inflow = len(today_ids - yids)
        outflow = len(yids - today_ids)
        def _ar(d):
            if d > 0: return f"^{d}"
            elif d < 0: return f"v{abs(d)}"
            return "--"
        print(f"    Open:        {snap['total']} -> {total_open}  ({_ar(total_open - snap['total'])})")
        print(f"    Blockers:    {snap['blockers']} -> {blocker_count}  ({_ar(blocker_count - snap['blockers'])})")
        print(f"    Unanswered:  {snap['needs_response']} -> {unanswered_count}  ({_ar(unanswered_count - snap['needs_response'])})")
        print(f"    Unassigned:  {snap['unassigned']} -> {unassigned_count}  ({_ar(unassigned_count - snap['unassigned'])})")
        print(f"    Inflow: +{inflow} new | Outflow: -{outflow} resolved")
    else:
        print(f"    Open: {total_open} | Blockers: {blocker_count} | Unanswered: {unanswered_count}")
    print(f"    Created Today:     {total_created_today}  ({len(created_today_open)} open + {len(created_today_resolved)} resolved + {len(created_today_canceled)} canceled)")
    print(f"    Resolved Today:    {total_resolved_today}  (excl {len(canceled_today)} canceled)")
    print(f"    Canceled Today:    {len(canceled_today)}")
    print(f"    Resolved (7d):     {len(resolved_7d)}")
    print(f"    7d Resolution Rate:{resolution_rate:.0f}%")
    print()

    # ── SLA PERFORMANCE ──
    print("  SLA PERFORMANCE (open tickets)")
    if fr_total > 0:
        print(f"    First Response:    {fmt_pct(fr_hit, fr_total)} hit  ({fr_hit}/{fr_total} decided, {fr_ip} pending)")
    else:
        print(f"    First Response:    No decided tickets ({fr_ip} pending)")
    if rt_total > 0:
        print(f"    Resolution Time:   {fmt_pct(rt_hit, rt_total)} hit  ({rt_hit}/{rt_total} decided, {rt_ip} pending)")
    else:
        print(f"    Resolution Time:   No decided tickets ({rt_ip} pending)")
    print()

    # Account-wise SLA table (top 15 by ticket count)
    print("    Account-wise SLA (top accounts):")
    hdr = f"    {'Account':<22} {'Tkt':>4} {'FR Hit%':>8} {'Res Hit%':>9} {'Miss':>5}"
    print(hdr)
    print(f"    {'-'*50}")
    for acct_name, d in sorted_accounts[:15]:
        fr_pct = fmt_pct(d["fr_hit"], d["fr_decided"]) if d["fr_decided"] else "-"
        rt_pct = fmt_pct(d["rt_hit"], d["rt_decided"]) if d["rt_decided"] else "-"
        name_trunc = (acct_name[:20] + "..") if len(acct_name) > 22 else acct_name
        print(f"    {name_trunc:<22} {d['total']:>4} {fr_pct:>8} {rt_pct:>9} {d['sla_miss']:>5}")
    print()

    # ── TAT ──
    print(f"  RESOLUTION TAT (last 7 days, {len(tat_all)} resolved tickets)")
    tat_hdr = f"    {'':>16} {'P10':>8} {'P50':>8} {'P90':>8}"
    print(tat_hdr)
    print(f"    {'-'*42}")
    p10, p50, p90 = percentiles(tat_all)
    print(f"    {'All':<16} {fmt_hours(p10):>8} {fmt_hours(p50):>8} {fmt_hours(p90):>8}")
    for sev_name in ["blocker", "high", "medium", "low"]:
        vals = tat_by_sev.get(sev_name, [])
        if vals:
            p10, p50, p90 = percentiles(vals)
            print(f"    {sev_name.capitalize():<16} {fmt_hours(p10):>8} {fmt_hours(p50):>8} {fmt_hours(p90):>8}")
        else:
            print(f"    {sev_name.capitalize():<16} {'--':>8} {'--':>8} {'--':>8}")
    print()

    # ── SENTIMENT ──
    print("  CUSTOMER SENTIMENT (open tickets)")
    for label, cnt, icon in [
        ("Happy", sent_happy, ":)"),
        ("Neutral", sent_neutral, ":|"),
        ("Unhappy", sent_unhappy, ":("),
        ("Frustrated", sent_frustrated, ">:("),
        ("No data", sent_nodata, ""),
    ]:
        pct = f"({cnt*100/total_open:.0f}%)" if total_open else ""
        print(f"    {icon+' ' if icon else '  '}{label:<14} {cnt:>4} {pct}")
    print()

    # ── TOP ACCOUNTS HEALTH CHECK ──
    print("  TOP 10 ACCOUNTS -- HEALTH CHECK")
    hdr2 = f"    {'Account':<22} {'Open':>5} {'Unans':>6} {'Miss':>5} {'Mood':>5}"
    print(hdr2)
    print(f"    {'-'*46}")
    for acct_name, d in sorted_accounts[:10]:
        mood = dominant_sentiment(d["sentiments"])
        name_trunc = (acct_name[:20] + "..") if len(acct_name) > 22 else acct_name
        print(f"    {name_trunc:<22} {d['total']:>5} {d['unanswered']:>6} {d['sla_miss']:>5} {mood:>5}")
    print()

    # ── RED FLAGS ──
    print("  RED FLAGS")
    if blockers:
        print(f"    - {len(blockers)} BLOCKER tickets active")
        for b in blockers[:5]:
            print(f"      {b['id']}  {b['account']}  ({b['owner']})")
    if high_sev:
        print(f"    - {len(high_sev)} HIGH severity tickets open")
    print(f"    - {unanswered_total} tickets unanswered ({unanswered_total*100//max(total_open,1)}%)")
    print(f"    - {stale_5d} tickets stale 5+ days ({stale_5d*100//max(total_open,1)}%)")
    if stale_10d:
        print(f"    - {stale_10d} tickets stale 10+ days ({stale_10d*100//max(total_open,1)}%)")
    if sent_frustrated > 0:
        print(f"    - {sent_frustrated} tickets with FRUSTRATED sentiment")
    # Top loaded owners
    top_owners = owner_load.most_common(5)
    if top_owners:
        print(f"    - Top loaded owners:")
        for name, cnt in top_owners:
            print(f"      {name}: {cnt} open tickets")
    print()
    print(bar)
    print()


if __name__ == "__main__":
    main()
