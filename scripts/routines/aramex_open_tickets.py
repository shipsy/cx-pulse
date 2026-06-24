#!/usr/bin/env python3
"""Aramex Open Tickets Report — Fetches open support tickets from DevRev for
Aramex Move and Aramex Oceania, outputs stage summary + ticket details.

Run: python3 scripts/routines/aramex_open_tickets.py
Requires: DEVREV_TOKEN env var or .devrev_token file

Accounts: Aramex Move (revo/Qnk3Lbim) + Aramex Oceania (revo/cErb8WTi)
Filter: subtype=Support, open stages only.
"""

import json, os, sys, urllib.request
from collections import defaultdict

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

OPEN_STAGES = {
    "queued", "reopen", "work_in_progress", "awaiting_product_assist",
    "awaiting_development", "in_development",
    "reassigned to customer support", "awaiting_customer_response",
}


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


def get_stage(t):
    return t.get("stage", {}).get("name", "Unknown")


def get_owner(t):
    owners = t.get("owned_by", [])
    if not owners:
        return "Unassigned"
    o = owners[0]
    return o.get("full_name", "") or o.get("display_name", "Unassigned")


def get_severity(t):
    return (t.get("severity") or "Unknown").capitalize()


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

    # Filter open only
    open_tickets = [t for t in all_tickets
                    if t.get("stage", {}).get("name", "").lower() in OPEN_STAGES]

    print(f"  Open: {len(open_tickets)}", file=sys.stderr)

    # Build rows
    rows = []
    for t in open_tickets:
        rows.append({
            "id": t.get("display_id", ""),
            "title": t.get("title", "")[:55],
            "stage": get_stage(t),
            "severity": get_severity(t),
            "owner": get_owner(t),
        })

    # Stage counts
    counts = defaultdict(int)
    for r in rows:
        counts[r["stage"]] += 1
    counts = dict(sorted(counts.items(), key=lambda x: -x[1]))

    # Format Slack message
    msg = []
    msg.append("*Daily Ticket Status Report* — `subtype: Support` | Open Tickets")
    msg.append("")
    msg.append("*View 1 — Stage Summary*")
    msg.append("```")
    msg.append(f"{'Stage':<35} {'Count':>5}")
    msg.append("-" * 41)
    for stage, count in counts.items():
        msg.append(f"{stage:<35} {count:>5}")
    msg.append("-" * 41)
    msg.append(f"{'TOTAL':<35} {len(rows):>5}")
    msg.append("```")
    msg.append("")
    msg.append("*View 2 — Ticket Details*")
    msg.append("```")
    msg.append(f"{'Ticket':<12} {'Severity':<10} {'Stage':<30} {'Owner'}")
    msg.append("-" * 75)
    for r in rows:
        msg.append(f"{r['id']:<12} {r['severity']:<10} {r['stage']:<30} {r['owner']}")
    msg.append("```")
    msg.append("")
    msg.append("_Source: DevRev REST API. Accounts: Aramex Move + Aramex Oceania._")

    output = "\n".join(msg)
    print(output)
    return output


if __name__ == "__main__":
    main()
