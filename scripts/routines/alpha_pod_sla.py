#!/usr/bin/env python3
"""Alpha Pod — Daily Support SLA Tracker.

Fetches Alpha pod's open Support tickets that are pending on Product or
Engineering from DevRev, computes ageing + SLA breach status, and prints a
Slack-ready markdown message (table + SLA-01-DTDC policy brief) to stdout.

Scope matches DevRev Vista vista-549 ("Support - open tickets"):
subtype=Support, non-WMS pods — here narrowed to tnt__pod == "Alpha".

  Product    = stage awaiting_product_assist
  Engineering = stages awaiting_development + in_development

Run: python3 scripts/routines/alpha_pod_sla.py
Requires: DEVREV_TOKEN_VINOD env var or .devrev_token file at repo root.
Target Slack channel: C07NJDX8AD8 (#alpha-pod-support-issues)
"""

import json, os, sys, urllib.request, datetime
from collections import defaultdict

# ═══ CONFIG ═══
def _load_token():
    t = os.environ.get("DEVREV_TOKEN_VINOD", "").strip()
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
POD = "Alpha"
TODAY = datetime.datetime.now(datetime.timezone.utc)

# Bucket -> stage names (lowercased match on stage.name)
PRODUCT_STAGES = ["awaiting_product_assist"]
ENGINEERING_STAGES = ["awaiting_development", "in_development"]

# Severity -> Priority label
SEV_PRIORITY = {"blocker": "P1", "high": "P2", "medium": "P3", "low": "P4"}

# Raw stage name -> display status (unmapped stages fall back to Title Case)
STATUS_DISPLAY = {
    "in_development": "Pending for release",
    "awaiting_development": "Awaiting Development",
    "awaiting_product_assist": "Awaiting Product",
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
        except Exception:
            if attempt < _retries - 1:
                time.sleep(1)
                continue
            raise


def fetch_by_stage(stage_names):
    """All tickets currently in any of the given stages (server-side filter)."""
    out, cursor = [], None
    while True:
        payload = {"type": ["ticket"], "stage": {"name": stage_names}, "limit": 100}
        if cursor:
            payload["cursor"] = cursor
        r = apicall("works.list", payload)
        out.extend(r.get("works", []))
        cursor = r.get("next_cursor", "")
        if not cursor:
            break
    return out


def age_days(iso):
    try:
        return (TODAY - datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))).days
    except Exception:
        return None


def sla_status_due(t):
    """Return (status_label, due_date_str) from the ticket's SLA summary."""
    ss = t.get("sla_summary") or {}
    overall = ss.get("stage")  # running / breached / warning / completed / paused
    due = None
    for m in ss.get("sla_tracker", {}).get("metric_target_summaries", []):
        if m.get("metric_definition", {}).get("name") == "Resolution time":
            due = m.get("target_time")
    if overall == "breached":
        label = "🔴 Breached"
    elif overall == "running":
        label = "🟢 Running"
    elif overall == "warning":
        label = "🟡 Warning"
    elif overall:
        label = overall.capitalize()
    else:
        label = "—"
    return label, (due[:10] if due else "—")


def collect(stage_names, bucket):
    rows = []
    for t in fetch_by_stage(stage_names):
        cf = t.get("custom_fields") or {}
        if cf.get("tnt__pod") != POD or t.get("subtype") != "Support":
            continue
        sev_raw = (t.get("severity") or "low").lower()
        priority = SEV_PRIORITY.get(sev_raw, "P4")
        stage_name = (t.get("stage") or {}).get("name", "")
        status = STATUS_DISPLAY.get(stage_name, stage_name.replace("_", " ").title() or "—")
        sla, due = sla_status_due(t)
        rows.append({
            "id": t.get("display_id", ""),
            "title": (t.get("title") or "").strip()[:50],
            "priority": priority,
            "age": age_days(t.get("created_date")),
            "bucket": bucket,
            "status": status,
            "sla": sla,
            "due": due,
        })
    return rows


def build_message(rows):
    d = TODAY.strftime("%d %b %Y")
    if not rows:
        return (f"✅ *Alpha Pod — Daily Support SLA Tracker* ({d})\n\n"
                f"No open Alpha tickets pending on Product or Engineering today. 🎉")
    prod = sum(1 for r in rows if r["bucket"] == "Product")
    eng = len(rows) - prod
    breached = sum(1 for r in rows if "Breached" in r["sla"])
    # priority (P1 first) then ageing (oldest first)
    rows = sorted(rows, key=lambda r: (int(r["priority"][1]), -(r["age"] if r["age"] is not None else -1)))
    L = []
    L.append(f":rotating_light: *Alpha Pod — Daily Support SLA Tracker* "
             f"_(Vista: Support - open tickets, as of {d})_")
    L.append("")
    L.append("*SLA policy — SLA-01-DTDC* _(business time within coverage window; timers "
             "pause outside window & during Awaiting Customer Response)_")
    L.append("| Priority | First Response | Resolution | Coverage |")
    L.append("|---|---|---|---|")
    L.append("| P1 – Blocker | 15 min | 2h | 24×7 |")
    L.append("| P2 – High | 1h | 18h | Mon–Sat, 10AM–8PM IST |")
    L.append("| P3 – Medium | 2h | 36h | Mon–Fri, 10AM–8PM IST |")
    L.append("| P4 – Low | 4h | 45h | Mon–Fri, 10AM–8PM IST |")
    L.append("")
    summary = f"*Summary:* Pending on Engineering = *{eng}*"
    if prod:
        summary += f" · Product = *{prod}*"
    summary += f" · SLA breached = *{breached} / {len(rows)}* — sorted by priority, then ageing"
    L.append(summary)
    L.append("")
    L.append("| Ticket | Title | Priority | Age | Status | SLA Status | SLA Due |")
    L.append("|---|---|---|---|---|---|---|")
    for r in rows:
        L.append(f"| {r['id']} | {r['title']} | {r['priority']} | {r['age']}d | "
                 f"{r['status']} | {r['sla']} | {r['due']} |")
    L.append("")
    L.append("_Please prioritise the breached tickets to improve SLA adherence._")
    return "\n".join(L)


def main():
    if not TOKEN:
        print("ERROR: Set DEVREV_TOKEN_VINOD env var or create .devrev_token file", file=sys.stderr)
        sys.exit(1)
    print("Fetching Alpha pod Product/Engineering tickets...", file=sys.stderr)
    rows = collect(PRODUCT_STAGES, "Product") + collect(ENGINEERING_STAGES, "Engineering")
    rows.sort(key=lambda r: (r["age"] if r["age"] is not None else -1), reverse=True)
    print(f"  Product: {sum(1 for r in rows if r['bucket']=='Product')} | "
          f"Engineering: {sum(1 for r in rows if r['bucket']=='Engineering')}", file=sys.stderr)
    output = build_message(rows)
    print(output)
    return output


if __name__ == "__main__":
    main()
