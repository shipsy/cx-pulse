"""Contractual SLA lookup — shared module for all CX reports.

Source of truth: config/account-sla-mapping.json (from Gaurav's curated sheets)
Measurement:
  - FR: completed_in from DevRev (business-hours minutes) — no FR timestamp available
  - RT: wall clock (actual_close_date - created_date) for 24x7; completed_in for 8x5
"""

import json, os, datetime

_BASE = os.path.join(os.path.dirname(__file__), "..")
SEV_TO_P = {"blocker": "p1", "high": "p2", "medium": "p3", "low": "p4"}

# Schedule classification: does this severity run 24x7 for this account?
_24X7_KEYWORDS = ["24x7", "24/7", "24hr"]

def _is_24x7_schedule(schedule_str, severity):
    """Check if a given severity level runs on 24x7 schedule."""
    if not schedule_str:
        return False
    s = schedule_str.lower()
    p = SEV_TO_P.get(severity, "p3")
    # "24x7 all tiers" or "24x7" → all severities are 24x7
    if any(kw in s for kw in _24X7_KEYWORDS) and "all" in s:
        return True
    if s == "24x7":
        return True
    # "P1 24x7 P2 8x5" → only P1 is 24x7
    if p == "p1" and any(f"p1 {kw}" in s or f"p1/{kw}" in s for kw in ["24x7", "24/7", "24hr"]):
        return True
    if p == "p1" and any(kw in s for kw in _24X7_KEYWORDS) and "p2" not in s.split("24")[0]:
        # "24x7" appears and P1 is likely covered
        return True
    # "P1/P2 24x7" → P1 and P2 are 24x7
    if p in ("p1", "p2") and ("p1/p2 24x7" in s or "p1/p2 24/7" in s):
        return True
    return False


def load_sla_config():
    """Load account SLA mapping. Returns dict ready for lookup."""
    path = os.path.join(_BASE, "config", "account-sla-mapping.json")
    with open(path) as f:
        data = json.load(f)
    # Build lowercase lookup + extract special lists
    no_tiers = set(v.lower() for v in data.get("_NO_TIERS", []))
    skip = set(v.lower() for v in data.get("_SKIP", []))
    mapping = {}
    for k, v in data.items():
        if k.startswith("_"):
            continue
        mapping[k.lower()] = v
    return {"mapping": mapping, "no_tiers": no_tiers, "skip": skip}


def lookup(sla_config, devrev_account, severity):
    """Look up contractual SLA target for an account+severity.

    Returns dict with keys: fr_target, rt_target, policy, schedule, category
    category is one of: 'contractual', 'no_tiers', 'skip', 'unknown'
    """
    acct_lower = devrev_account.lower().strip()
    # Remove common suffixes
    for suffix in [" account", " - default workspace"]:
        if acct_lower.endswith(suffix):
            acct_lower = acct_lower[:-len(suffix)]

    if acct_lower in sla_config["skip"]:
        return {"category": "skip"}
    if acct_lower in sla_config["no_tiers"]:
        return {"category": "no_tiers"}

    entry = sla_config["mapping"].get(acct_lower)
    if not entry:
        return {"category": "unknown"}

    p = SEV_TO_P.get(severity, "p3")
    return {
        "category": "contractual",
        "policy": entry.get("policy", ""),
        "schedule": entry.get("schedule", ""),
        "fr_target": entry.get(f"{p}_fr"),
        "rt_target": entry.get(f"{p}_rt"),
        "is_24x7": _is_24x7_schedule(entry.get("schedule", ""), severity),
    }


def check_ticket_sla(ticket, sla_config, consolidated_account_name=None):
    """Check a ticket against contractual SLA.

    Args:
        ticket: DevRev ticket dict (from works.list)
        sla_config: from load_sla_config()
        consolidated_account_name: pre-computed account name (optional)

    Returns dict:
        category: contractual|no_tiers|skip|unknown
        fr_hit: True/False/None
        rt_hit: True/False/None
        fr_elapsed: minutes or None
        rt_elapsed: minutes or None
        fr_target: minutes or None
        rt_target: minutes or None
        policy: str or None
    """
    # Get account name from ticket
    if consolidated_account_name:
        acct = consolidated_account_name
    else:
        acct = (ticket.get("rev_org") or {}).get("display_name", "Unknown")

    severity = (ticket.get("severity") or "medium").lower()
    info = lookup(sla_config, acct, severity)

    result = {
        "category": info["category"],
        "fr_hit": None, "rt_hit": None,
        "fr_elapsed": None, "rt_elapsed": None,
        "fr_target": None, "rt_target": None,
        "policy": info.get("policy"),
    }

    if info["category"] != "contractual":
        return result

    result["fr_target"] = info["fr_target"]
    result["rt_target"] = info["rt_target"]

    # Extract FR and RT data from SLA tracker
    tr = ticket.get("sla_summary", {}).get("sla_tracker", {})
    fr_completed_in = None
    rt_completed_in = None
    for m in tr.get("metric_target_summaries", []):
        nm = m.get("metric_definition", {}).get("name", "")
        ci = m.get("completed_in")
        if "First" in nm and ci is not None:
            fr_completed_in = ci  # minutes (business hours)
        elif "Resolution" in nm and ci is not None:
            rt_completed_in = ci  # minutes (business hours)

    # FR check: always use completed_in (no FR timestamp available)
    if fr_completed_in is not None and info["fr_target"] is not None:
        result["fr_elapsed"] = fr_completed_in
        result["fr_hit"] = fr_completed_in <= info["fr_target"]

    # RT check: use wall clock for 24x7, completed_in for 8x5
    if info["rt_target"] is not None:
        if info.get("is_24x7"):
            # Wall clock: actual_close_date - created_date
            cr = ticket.get("created_date", "")
            cl = ticket.get("actual_close_date", "")
            if cr and cl:
                try:
                    t1 = datetime.datetime.fromisoformat(cr.replace("Z", "+00:00")).replace(tzinfo=None)
                    t2 = datetime.datetime.fromisoformat(cl.replace("Z", "+00:00")).replace(tzinfo=None)
                    wall_min = (t2 - t1).total_seconds() / 60
                    if wall_min >= 0:
                        result["rt_elapsed"] = round(wall_min)
                        result["rt_hit"] = wall_min <= info["rt_target"]
                except (ValueError, TypeError):
                    pass
        else:
            # Business hours: use completed_in
            if rt_completed_in is not None:
                result["rt_elapsed"] = rt_completed_in
                result["rt_hit"] = rt_completed_in <= info["rt_target"]

    return result
