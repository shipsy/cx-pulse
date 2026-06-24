#!/usr/bin/env python3
"""Aramex Weekly Support Report — Fetches tickets from DevRev for Aramex Move
and Aramex Oceania, computes weekly closure stats, outputs formatted Slack message.

Run: python3 scripts/routines/aramex_weekly_report.py
Requires: DEVREV_TOKEN env var or .devrev_token file

Accounts: Aramex Move (revo/Qnk3Lbim) + Aramex Oceania (revo/cErb8WTi)
Filter: subtype=Support, last 4 weeks
Closed = any stage NOT in the open stages set (includes resolved, closed, canceled).
"""

import json, os, sys, datetime, statistics, urllib.request

# ═══ CONFIG ═══
def _load_token():
    t = os.environ.get("DEVREV_TOKEN", "").strip()
    if t:
        return t
    token_path = os.path.join(os.path.dirname(__file__), "..", "..", ".devrev_token")
    try:
        with open(token_path) as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

TOKEN = _load_token()
API = "https://api.devrev.ai"

REVO_IDS = [
    "don:identity:dvrv-us-1:devo/xXjPo9nF:revo/Qnk3Lbim",  # Aramex Move
    "don:identity:dvrv-us-1:devo/xXjPo9nF:revo/cErb8WTi",  # Aramex Oceania
]

# Stages considered "open" — anything NOT in this set is treated as closed
OPEN_STAGES = {
    "queued", "reopen", "work_in_progress", "awaiting_product_assist",
    "awaiting_development", "in_development",
    "reassigned to customer support", "awaiting_customer_response",
}

# IST offset for date bucketing (matches DevRev org schedule)
IST_OFFSET = datetime.timedelta(hours=5, minutes=30)

NOW = datetime.datetime.utcnow() + IST_OFFSET  # current IST time
CUTOFF = NOW - datetime.timedelta(weeks=4)


def apicall(endpoint, payload, _retries=3):
    import time
    for attempt in range(_retries):
        try:
            req = urllib.request.Request(
                f"{API}/{endpoint}",
                data=json.dumps(payload).encode(),
                headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except Exception as e:
            if attempt < _retries - 1:
                time.sleep(1)
                continue
            raise


def parse_date(s):
    """Parse ISO date string to IST datetime."""
    if not s:
        return None
    try:
        dt = datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
        return dt + IST_OFFSET  # convert UTC to IST
    except (ValueError, TypeError):
        return None


def get_week_start(dt):
    """Get Monday 00:00 of the week containing dt."""
    monday = dt - datetime.timedelta(days=dt.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def pctl(sorted_list, p):
    """Percentile with linear interpolation."""
    if not sorted_list:
        return None
    n = len(sorted_list)
    k = (p / 100) * (n - 1)
    f = int(k)
    c = min(f + 1, n - 1)
    if f == c:
        return sorted_list[f]
    return sorted_list[f] * (c - k) + sorted_list[c] * (k - f)


def fetch_all(revo_id):
    """Fetch all support tickets for a rev_org."""
    tickets = []
    cursor = None
    while True:
        payload = {
            "type": ["ticket"],
            "ticket": {"rev_org": [revo_id], "subtype": ["Support"]},
            "limit": 50,
        }
        if cursor:
            payload["cursor"] = cursor
        r = apicall("works.list", payload)
        tickets.extend(r.get("works", []))
        cursor = r.get("next_cursor", "")
        if not cursor:
            break
    return tickets


def main():
    if not TOKEN:
        print("ERROR: Set DEVREV_TOKEN env var or create .devrev_token file", file=sys.stderr)
        sys.exit(1)

    # Fetch tickets
    print("Fetching Aramex tickets...", file=sys.stderr)
    all_tickets = []
    for revo in REVO_IDS:
        tix = fetch_all(revo)
        print(f"  {revo.split('/')[-1]}: {len(tix)} tickets", file=sys.stderr)
        all_tickets.extend(tix)

    # Bucket by week
    from collections import defaultdict
    cohorts = defaultdict(list)

    for t in all_tickets:
        created = parse_date(t.get("created_date", ""))
        if not created or created < CUTOFF:
            continue

        stage_name = (t.get("stage", {}).get("name", "") or "").lower()

        wk = get_week_start(created)
        is_closed = stage_name not in OPEN_STAGES and stage_name != ""

        # Days to close: use actual_close_date (the real resolution timestamp)
        days_to_close = None
        if is_closed:
            closed_date = parse_date(t.get("actual_close_date", ""))
            if closed_date and created:
                days_to_close = max(0, (closed_date - created).total_seconds() / 86400)

        cohorts[wk].append({"is_closed": is_closed, "days": days_to_close})

    # Compute stats per week
    sorted_weeks = sorted(cohorts.keys())
    rows = []
    all_days = []
    total_created = total_closed = total_open = 0

    for wk in sorted_weeks:
        items = cohorts[wk]
        created = len(items)
        closed_items = [x for x in items if x["is_closed"]]
        open_items = [x for x in items if not x["is_closed"]]
        closed = len(closed_items)
        still_open = len(open_items)
        closure_pct = closed / created * 100 if created else 0

        days_list = sorted([x["days"] for x in closed_items if x["days"] is not None])
        all_days.extend(days_list)

        avg_d = sum(days_list) / len(days_list) if days_list else None
        p50 = pctl(days_list, 50)
        p90 = pctl(days_list, 90)

        total_created += created
        total_closed += closed
        total_open += still_open

        rows.append({
            "week": wk.strftime("%b %d"),
            "created": created,
            "closed": closed,
            "closure_pct": f"{closure_pct:.0f}%",
            "avg_d": f"{avg_d:.1f}" if avg_d is not None else "-",
            "p50": f"{p50:.1f}" if p50 is not None else "-",
            "p90": f"{p90:.1f}" if p90 is not None else "-",
            "still_open": still_open,
        })

    total_closure_pct = total_closed / total_created * 100 if total_created else 0
    all_days_sorted = sorted(all_days)
    avg_total = sum(all_days) / len(all_days) if all_days else None
    median_total = pctl(all_days_sorted, 50)
    p90_total = pctl(all_days_sorted, 90)

    # Format Slack message
    med_str = f"{median_total:.1f}" if median_total is not None else "-"
    avg_str = f"{avg_total:.1f}" if avg_total is not None else "-"
    p90_str = f"{p90_total:.1f}" if p90_total is not None else "-"

    msg = []
    msg.append(f"*Weekly Summary of Aramex Support Tickets — Closed/Resolved (last 4 weeks)*")
    msg.append(f"{total_created} total | {total_closed} closed ({total_closure_pct:.0f}%) | {total_open} still open | Median close: {med_str} days")
    msg.append("")
    msg.append("```")
    msg.append(f"{'Week of':<10} {'Created':>7} {'Closed':>7} {'Close%':>7} {'Avg(d)':>7} {'P50(d)':>7} {'P90(d)':>7} {'Open':>6}")
    msg.append("-" * 62)
    for r in rows:
        msg.append(f"{r['week']:<10} {r['created']:>7} {r['closed']:>7} {r['closure_pct']:>7} {r['avg_d']:>7} {r['p50']:>7} {r['p90']:>7} {r['still_open']:>6}")
    msg.append("-" * 62)
    msg.append(f"{'TOTAL':<10} {total_created:>7} {total_closed:>7} {total_closure_pct:.0f}%{'':<3} {avg_str:>7} {med_str:>7} {p90_str:>7} {total_open:>6}")
    msg.append("```")

    output = "\n".join(msg)
    print(output)

    # Also output as JSON for the trigger agent to parse
    print(json.dumps({
        "total_created": total_created,
        "total_closed": total_closed,
        "total_open": total_open,
        "total_closure_pct": f"{total_closure_pct:.0f}%",
        "median_close": med_str,
        "avg_total": avg_str,
        "p90_total": p90_str,
        "rows": rows,
        "channel": "C07ASBBQE20",
    }), file=sys.stderr)

    return output


if __name__ == "__main__":
    main()
