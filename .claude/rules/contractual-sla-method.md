# Contractual SLA Calculation Method

## Source of Truth
- `config/sla-policies.json` — 25 SLA policies (SLA-01 through SLA-25)
- `config/account-sla-mapping.json` — DevRev account → SLA policy → per-severity targets
- Curated from Gaurav's Google Sheets (June 2026)

## Account Categories
- **Contractual** (SLA-01 to SLA-25): check against contractual targets
- **NO-TIERS** (Reliance, Expeditors, etc.): no contractual tiers available → use DevRev default SLA
- **SKIP** (internal, demo, no contract): exclude from SLA reporting entirely
- **Unknown**: not in mapping → treat as unmapped, report count separately

## Measurement Method
- **First Response**: use `completed_in` from DevRev's `metric_target_summaries` (business-hours minutes). No FR timestamp is available in the API.
- **Resolution Time**: hybrid based on schedule:
  - 24x7 schedules → wall clock: `actual_close_date - created_date`
  - 8x5 schedules → `completed_in` from DevRev (business-hours minutes)

## Severity Mapping
- blocker → P1
- high → P2
- medium → P3
- low → P4

## Reusable Module
`scripts/sla_lookup.py` — import and use in any report script:
```python
from sla_lookup import load_sla_config, check_ticket_sla
sla_cfg = load_sla_config()
result = check_ticket_sla(ticket, sla_cfg)
# result: {category, fr_hit, rt_hit, fr_elapsed, rt_elapsed, fr_target, rt_target, policy}
```

## Display Format
Always show:
1. Contractual FR% and RT% as primary
2. DevRev default as comparison line
3. Counts: contractual / no-tiers / skip / unmapped
4. Per-account table with policy name, targets, and color-coded percentages

## Important Notes
- DevRev currently uses ONE generic SLA policy (sla-28 "Support Ticket SLA Default") for all tickets
- The contractual SLA policies have NOT yet been applied in DevRev per-account
- Until they are, we must compute contractual compliance ourselves using this module
- `completed_at` field does NOT exist in DevRev's metric_target_summaries
