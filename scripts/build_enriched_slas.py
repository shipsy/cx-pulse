#!/usr/bin/env python3
"""
Build enriched contractual-slas.json from raw parsed data + DevRev account mapping.
Adds DevRev account IDs, severity mapping, and manual fixes for Tier 1+2 edge cases.
"""

import json
from pathlib import Path

RAW_FILE = Path(__file__).parent.parent / "config" / "contractual-slas-raw.json"
OUTPUT_FILE = Path(__file__).parent.parent / "config" / "contractual-slas.json"

# ─── DevRev Account Mapping (Tier 1+2 + Strategic) ───────────────────────

DEVREV_ACCOUNTS = {
    # Tier 1 — Dedicated Enterprise
    "RIL": {
        "cohort": "1-Reliance",
        "devrev_accounts": [
            {"display_name": "Reliance (RIL)", "account_id": "ACC-y36IXmM4", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/y36IXmM4"},
            {"display_name": "RIL", "account_id": "ACC-6wFfy2pw", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/6wFfy2pw"},
            {"display_name": "Reliance", "account_id": "ACC-Wc8Rt9rz", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/Wc8Rt9rz"},
            {"display_name": "Reliance Grocery", "account_id": "ACC-JKoyH2yi", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/JKoyH2yi"},
        ],
    },
    "DTDC Express Ltd": {
        "cohort": "1-DTDC",
        "devrev_accounts": [
            {"display_name": "DTDC", "account_id": "ACC-u5JsHNO6", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/u5JsHNO6"},
            {"display_name": "dtdc.co", "account_id": "ACC-1ERdqDghw", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/1ERdqDghw"},
            {"display_name": "dtdc.in", "account_id": "ACC-im2HyH1y", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/im2HyH1y"},
        ],
    },

    # Tier 2 — Strategic Accounts
    "Aramex": {
        "cohort": "2-Aramex",
        "devrev_accounts": [
            {"display_name": "Aramex", "account_id": "ACC-G0tfv4Ge", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/G0tfv4Ge"},
            {"display_name": "Aramex Global", "account_id": "ACC-cldfPBey", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/cldfPBey"},
            {"display_name": "Aramex VW", "account_id": "ACC-x6aBsVOi", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/x6aBsVOi"},
            {"display_name": "Aramex Oceania", "account_id": "ACC-YFdgDPLP", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/YFdgDPLP"},
            {"display_name": "Aramex Freight", "account_id": "ACC-11duBDFNw", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/11duBDFNw"},
            {"display_name": "Aramex RO", "account_id": "ACC-mGbG1chd", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/mGbG1chd"},
            {"display_name": "Aramex Move", "account_id": "ACC-o0NpKw5T", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/o0NpKw5T"},
            {"display_name": "aramex.com.au", "account_id": "ACC-1FBk68T7w", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/1FBk68T7w"},
            {"display_name": "aramex.co.nz", "account_id": "ACC-3YvXMdkj", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/3YvXMdkj"},
        ],
        "sla_note": "DMCC MSA (primary). Aramex KSA has a weaker SLA (4hr/8hr/16hr, 8x5). Aramex India also has a separate weaker SLA.",
    },
    "Heineken": {
        "cohort": "2-HNK",
        "devrev_accounts": [
            {"display_name": "heineken", "account_id": "ACC-BvMwCgbz", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/BvMwCgbz"},
            {"display_name": "heineken.com.br", "account_id": "ACC-C4800jMY", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/C4800jMY"},
            {"display_name": "heineken-br1", "account_id": "ACC-5zvP8D4", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/5zvP8D4"},
        ],
    },

    # Strategic accounts
    "Flipkart": {
        "cohort": "3A-On Demand",
        "devrev_accounts": [
            {"display_name": "Flipkart", "account_id": "ACC-cBf033gP", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/cBf033gP"},
            {"display_name": "flipkart.in", "account_id": "ACC-OPPE2slK", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/OPPE2slK"},
            {"display_name": "Flipkart DH Offload", "account_id": "ACC-jdKQCOIt", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/jdKQCOIt"},
        ],
        "sla_note": "Multiple contracts: Platinum Addendum 3 (tighter) and Standard Addendum 5. Using Platinum values as primary.",
    },
    "ASDA UK": {
        "cohort": "other",
        "devrev_accounts": [
            {"display_name": "Asda", "account_id": "ACC-lYzn2A0l", "don_id": "don:identity:dvrv-us-1:devo/xXjPo9nF:account/lYzn2A0l"},
        ],
    },
    "Zepto": {
        "cohort": "3A-On Demand",
        "devrev_accounts": [],
        "sla_note": "NOT FOUND in DevRev accounts. Needs manual account creation or mapping.",
    },
    "ANC Delivers": {
        "cohort": "other",
        "devrev_accounts": [],
        "sla_note": "NOT FOUND in DevRev accounts. Platinum Dedicated tier. Needs manual account creation or mapping.",
    },
}

# ─── Manual SLA Fixes (edge cases the parser couldn't handle perfectly) ───

MANUAL_FIXES = {
    "Aramex": {
        "uptime_pct": 99.4,  # Parser might pick up 99.6% from sub-entity mentions
        "tiers": [
            {"priority": "P1", "response_time_minutes": 60,   "resolution_time_minutes": 240,  "support_hours": "24x7"},
            {"priority": "P2", "response_time_minutes": 120,  "resolution_time_minutes": 480,  "support_hours": "24x7"},
            {"priority": "P3", "response_time_minutes": 240,  "resolution_time_minutes": 1440, "support_hours": "16x6"},
            {"priority": "P4", "response_time_minutes": 720,  "resolution_time_minutes": 2880, "support_hours": "16x6"},
        ],
    },
    "Zepto": {
        "uptime_pct": 99.9,
        "tiers": [
            {"priority": "P1", "response_time_minutes": 15,  "resolution_time_minutes": 240,  "support_hours": "24x7"},
            {"priority": "P2", "response_time_minutes": 60,  "resolution_time_minutes": 2160, "support_hours": "Mon-Sat 10AM-8PM"},
            {"priority": "P3", "response_time_minutes": 120, "resolution_time_minutes": 2880, "support_hours": "Mon-Fri 10AM-8PM"},
            {"priority": "P4", "response_time_minutes": 240, "resolution_time_minutes": 4320, "support_hours": "Mon-Fri 10AM-8PM"},
        ],
        "has_service_credits": True,
        "service_credits_summary": "3-tier penalty: uptime (3-10%), support SLA (3-10%), API latency (3-10%) of monthly billing",
    },
    "Flipkart": {
        # Use Platinum Addendum 3 (the tighter/active SLA)
        "tiers": [
            {"priority": "P1", "response_time_minutes": 30,  "resolution_time_minutes": 60,   "support_hours": "24x7"},
            {"priority": "P2", "response_time_minutes": 240, "resolution_time_minutes": 480,  "support_hours": "16x6"},
            {"priority": "P3", "response_time_minutes": 360, "resolution_time_minutes": 1440, "support_hours": "8x5"},
            {"priority": "P4", "response_time_minutes": 600, "resolution_time_minutes": 2160, "support_hours": "8x5"},
        ],
    },
}

# ─── Contract Priority → DevRev Severity Mapping ─────────────────────────

SEVERITY_MAP = {
    "P1": "blocker",   # Critical/Shutdown → DevRev Blocker
    "P2": "high",      # Bugs/High → DevRev High
    "P3": "medium",    # Improvements/Medium → DevRev Medium
    "P4": "low",       # Training/Low → DevRev Low
}

# For 3-tier contracts, P3 maps to Low (no Medium)
SEVERITY_MAP_3TIER = {
    "P1": "blocker",
    "P2": "high",
    "P3": "low",
}


def enrich_customer(raw_entry: dict) -> dict:
    """Enrich a raw parsed customer entry with DevRev mapping and severity."""
    name = raw_entry["customer_name"]
    enriched = dict(raw_entry)

    # Apply manual fixes if available
    if name in MANUAL_FIXES:
        for key, val in MANUAL_FIXES[name].items():
            enriched[key] = val

    # Add DevRev account mapping
    if name in DEVREV_ACCOUNTS:
        mapping = DEVREV_ACCOUNTS[name]
        enriched["cohort"] = mapping["cohort"]
        enriched["devrev_accounts"] = mapping["devrev_accounts"]
        if "sla_note" in mapping:
            if enriched.get("notes"):
                enriched["notes"].append(mapping["sla_note"])
            else:
                enriched["notes"] = [mapping["sla_note"]]
    else:
        enriched["devrev_accounts"] = []
        enriched["cohort"] = None

    # Add severity mapping to each tier
    num_tiers = len(enriched.get("tiers", []))
    sev_map = SEVERITY_MAP_3TIER if num_tiers == 3 else SEVERITY_MAP

    for tier in enriched.get("tiers", []):
        priority = tier.get("priority", "")
        tier["devrev_severity"] = sev_map.get(priority)

    return enriched


def main():
    raw = json.loads(RAW_FILE.read_text())

    # Enrich all entries
    enriched = [enrich_customer(c) for c in raw]

    # Summary
    mapped = sum(1 for c in enriched if c.get("devrev_accounts"))
    print(f"Total customers: {len(enriched)}")
    print(f"With DevRev account mapping: {mapped}")
    print(f"Without mapping: {len(enriched) - mapped}")

    # Show Tier 1+2 summary
    print("\n--- Tier 1+2 + Strategic Summary ---")
    for name in DEVREV_ACCOUNTS:
        entry = next((c for c in enriched if c["customer_name"] == name), None)
        if entry:
            accts = len(entry.get("devrev_accounts", []))
            tiers = len(entry.get("tiers", []))
            print(f"  {name}: {tiers} tiers, {accts} DevRev accounts, uptime={entry.get('uptime_pct')}%")
            for t in entry.get("tiers", []):
                print(f"    {t['priority']} ({t.get('devrev_severity', '?')}): "
                      f"resp={t.get('response_time_minutes')}m, "
                      f"res={t.get('resolution_time_minutes')}m, "
                      f"hours={t.get('support_hours')}")

    # Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(enriched, indent=2, ensure_ascii=False))
    print(f"\nOutput: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
