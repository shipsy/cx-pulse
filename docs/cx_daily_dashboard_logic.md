# CX Daily Dashboard — Complete Computation Logic

**Purpose**: This document describes every metric, formula, data source, and computation rule used in the daily CX Support Dashboard that posts to #customer-experience-product-support at 9:00 AM IST every day.

**Script**: `scripts/cx_daily_dashboard.py`
**Trigger**: Claude Code Remote Trigger `trig_011nXspqKLprxnYGqaEvsXm2` (9:00 AM IST, daily)
**Slack Channel**: `C07BQD5776Y` (#customer-experience-product-support)

**References**:
- Repo: `shipsy/cx-pulse`
- CX Pulse Dashboard (Vercel live)

---

## 1. Data Sources

### 1.1 DevRev REST API

All ticket data is fetched from `https://api.devrev.ai` using a DevRev Personal Access Token (PAT).

**Open Tickets**:
```
POST /works.list
Body: { "type": ["ticket"], "state": ["open", "in_progress"], "limit": 25 }
```
- Full pagination — follows `next_cursor` until exhausted
- Typical volume: ~40-50 pages, ~4000 raw tickets, ~230 after support filter

**Resolved/Closed Tickets**:
```
POST /works.list
Body: { "type": ["ticket"], "state": ["resolved", "closed"], "limit": 25 }
```
- Smart stop: pagination stops when `modified_date < 14 days ago`
- This avoids paginating through 80,000+ historical tickets
- Safety cap at 200 pages
- Client-side filter: `actual_close_date >= 7 days ago`

**Timeline API** (for Friday AI):
```
POST /timeline-entries.list
Body: { "object": "<ticket_don_id>", "limit": 20 }
```

### 1.2 Snapshot File

`config/daily-snapshot.json` — saved after each run, used for next-day trend comparison.

Contents:
- `date` — when snapshot was taken
- `total` — open ticket count at that time
- `blockers` — blocker count
- `blocker_ids` — list of specific blocker ticket IDs (for movement tracking)
- `unanswered` — unanswered count
- `prior_*` — previous day's values (for re-run protection)
- `daily_rates` — created/resolved counts per day (avoids recomputing history)

---

## 2. Global Filters

**Every single metric uses the same filter.** This ensures consistency across all numbers.

| Rule | Field | Logic |
|------|-------|-------|
| Support only | `subtype` | Must be exactly `"Support"` (strict match, null is excluded) |
| Exclude WMS cohorts | `custom_fields.tnt__customer_cohort_dropdown` | Exclude if value is `"WMS"` or `"Roadmap"` |
| Exclude WMS pods | `custom_fields.tnt__pod` | Exclude if value is `"WMS Inbound"` or `"WMS Outbound"` |
| Exclude canceled | `stage.name` | For resolved metrics only: must be `"resolved"` or `"Closed"`, not `"canceled"` |

**Implementation** (`is_support()` function):
```python
def is_support(t):
    if t.get("subtype") != "Support": return False
    cohort = t.get("custom_fields", {}).get("tnt__customer_cohort_dropdown", "") or "TBD"
    if cohort in {"WMS", "Roadmap"}: return False
    pod = t.get("custom_fields", {}).get("tnt__pod", "")
    if pod in {"WMS Inbound", "WMS Outbound"}: return False
    return True
```

---

## 3. Account Consolidation

DevRev has ~72 raw account names (workspaces). These are consolidated to ~36 display names to avoid fragmentation.

**Step 1**: Strip suffixes
- Remove ` - Default Workspace` from the end
- Remove ` Account` from the end

**Step 2**: Apply alias map (case-insensitive)

Key consolidations:
| Display Name | Raw DevRev Names |
|---|---|
| Reliance | Reliance (RIL), RIL, reliancehyperlocal, ril-tira, 1P Jiomart Reliance, Reliance - 3P, QWIK Logistics, rcpldemo, **Techmahindra** |
| DTDC | DTDC, dtdc.in |
| Aramex | Aramex Global, Aramex VW, Aramex Move, Aramex Same Day Delivery, Aramex RO, Aramex Oceania, Aramex Freight, Aramex SDD |
| Flipkart | Flipkart, fkfooddemo, FK Food, flipkartdropship |
| Heineken | HNK-BR1-Primary, HNK-BR1-Secondary, HNK-BR1-Support |
| Myntra | Myntra, myntrahl, myntrahldemo |
| Swiggy | Swiggy, swiggytms |

Full map: 66 raw names to 36 consolidated names (see `ALIASES` dict in script).

---

## 4. CX Lead Name Resolution

The `tnt__assignee` custom field stores a DevRev DON ID (e.g., `don:identity:dvrv-us-1:devo/xXjPo9nF:devu/1327`).

The script extracts the `devu/XXXX` portion and maps it to a human name:

| DEVU ID | Name |
|---|---|
| devu/1327 | Gangesh Pandey |
| devu/2573 | Saurabh Singh |
| devu/2585 | Laxmi Rajput |
| devu/1088 | Deepanshu Marwari |
| devu/2580 | Vikas Pandey |
| devu/2976 | Srijan Srivastava |
| devu/1246 | Vinod Kumar Gunda |
| devu/3000 | Kaustuv Choudhary |
| ... | (28 people total) |

If `tnt__assignee` is empty, the ticket is labeled "Unassigned".

---

## 5. The 8 Metrics — Detailed Computation

---

### Metric 1: PULSE CHECK

**Purpose**: Day-over-day snapshot of queue health.

#### 5.1.1 Open Now
- **What**: Count of all currently open support tickets
- **Calculation**: Count of tickets from the `state: ["open", "in_progress"]` fetch that pass `is_support()`
- **Formula**: `total = len(tix)`

#### 5.1.2 Previous Day Open
- **What**: How many tickets were open yesterday (for trend comparison)
- **Primary source**: Snapshot file (`config/daily-snapshot.json`) from yesterday's run
- **Fallback** (if no snapshot): Reconstruct from current data:
  ```
  open_yesterday = (tickets currently open, created on or before yesterday)
                 + (tickets closed after yesterday, created on or before yesterday)
  ```
- **Rationale for snapshot**: The reconstruction is approximate because it can't account for tickets that were reclassified (cohort/pod changed), so the snapshot gives exact numbers.

#### 5.1.3 Blockers
- **What**: Tickets with severity = "blocker" (case-insensitive)
- **Field**: `ticket.severity` (plain string, NOT `severity_v2`)
- **Previous day**: From snapshot (exact blocker IDs stored)

**Blocker Movement Breakdown** (tracks what happened to each blocker):
- **Persisting**: Blocker IDs present both yesterday and today
- **Closed**: Yesterday's blockers that are now in resolved/closed state
- **Downgraded**: Yesterday's blockers that are still open but no longer severity=blocker
- **New**: Today's blockers that were created today as blockers
- **Escalated**: Today's blockers that existed before today but were upgraded to blocker severity

#### 5.1.4 Unanswered
- **What**: Tickets waiting for a support agent to respond
- **Fields**: `needs_response == true` AND `stage.name` in `("queued", "work_in_progress")`
- **Important**: Does NOT include "awaiting_customer_response" — those are waiting on the customer, not the agent

#### 5.1.5 Created Yesterday
- **What**: New tickets created on the previous calendar day
- **Calculation**: Deduplicated across open + closed pools, `created_date[:10] == yesterday`, excluding canceled, passing `is_support()`
- **Why dedup**: A ticket may appear in both open and resolved fetches during state transitions

#### 5.1.6 Resolved Yesterday
- **What**: Tickets that reached "resolved" or "Closed" stage yesterday
- **Calculation**: `actual_close_date[:10] == yesterday` AND `stage.name` in `("resolved", "Closed")`
- **Excludes**: Canceled tickets (they are not "resolved")

#### 5.1.7 Net
- **Formula**: `net = created_yesterday - resolved_yesterday`
- Positive = queue growing, Negative = queue shrinking

#### 5.1.8 Trend Indicators
| Indicator | Meaning |
|---|---|
| `▲ N` | Value increased by N |
| `▼ N` | Value decreased by N |
| `= 0` | No change |
| `✅` | Good direction (blockers down, open down) |
| `⚠️` | Concerning direction (unanswered up, blockers up) |
| `🔴` | All old blockers persist AND new ones added |
| `🟡` | Some blocker progress but still have blockers |

---

### Metric 2: SLA ADHERENCE (Contract Basis)

**Purpose**: How well are we meeting **contractual** SLA targets for First Response and Resolution Time, measured against each account's specific contract.

**Pool**: All open tickets + all resolved tickets from the last 7 days (combined, deduplicated). SKIP accounts excluded.

**Per-Account Breakdown**:
- Top 12 accounts by pool size (minimum 3 tickets to show individually)
- Remaining accounts rolled up as "X more accts" with aggregate FR%/RT%
- Pool breakdown shown: how many tickets are contractual / default / skip

#### 5.2.1 Contractual SLA Logic

The SLA evaluation uses per-account, per-severity contractual targets (SLA-01 through SLA-25), sourced from Gaurav's curated sheets and implemented in the CX Pulse Dashboard.

**How it works**:

**Step 1 — Identify the account's SLA policy**:
Each raw DevRev account name is normalized (strip " - Default Workspace", strip " Account", lowercase) and looked up in a policy table.

Three categories:
| Category | Meaning | How SLA is computed |
|---|---|---|
| **Contractual** | Account has a specific SLA contract (SLA-01 through SLA-25) | Compare `completed_in` against per-severity contractual target |
| **NO-TIERS** | Account exists but has no tiered contract (e.g., Reliance, Expeditors, Healthkart, Zajel) | Falls back to the default SLA targets |
| **SKIP** | Internal/demo/no contract (e.g., Shipsy, nxlogistics, test, xhawi.com) | Excluded from SLA reporting entirely |

**Note**: Tech Mahindra is consolidated into **Reliance** (account alias). Hero MotoCorp is a real customer account and is included in SLA reporting (uses default targets).

**Step 2 — Map ticket severity to priority tier**:
```
blocker -> P1 (tier index 0)
high    -> P2 (tier index 1)
medium  -> P3 (tier index 2)
low     -> P4 (tier index 3)
```

**Step 3 — Look up targets**:
Each policy defines per-severity targets as `[FR_minutes, RT_minutes]`.

Example — DTDC (SLA-01-DTDC):
| Severity | FR Target | RT Target |
|---|---|---|
| P1 (blocker) | 15 min | 120 min (2h) |
| P2 (high) | 60 min (1h) | 1080 min (18h) |
| P3 (medium) | 120 min (2h) | 2160 min (36h) |
| P4 (low) | 240 min (4h) | 2700 min (45h) |

Example — Flipkart/Myntra (SLA-02):
| Severity | FR Target | RT Target |
|---|---|---|
| P1 | 30 min | 60 min (1h) |
| P2 | 240 min (4h) | 480 min (8h) |
| P3 | 360 min (6h) | 1440 min (24h) |
| P4 | 600 min (10h) | 2160 min (36h) |

`null` = no target defined for that severity/metric — ticket is not evaluable for that metric.

**Default SLA fallback** (for NO-TIERS accounts and unmapped accounts):
| Severity | FR Target | RT Target |
|---|---|---|
| blocker | 15 min | 240 min (4h) |
| high | 60 min (1h) | 2160 min (36h) |
| medium | 120 min (2h) | 2880 min (48h) |
| low | 240 min (4h) | 4320 min (72h) |

**Step 4 — Evaluate hit/miss**:

For First Response:
```
IF completed_in[0] (FR minutes from DevRev) is available AND > 0:
    FR_hit = completed_in[0] <= FR_target
ELSE IF DevRev status (hit/miss) is available:
    FR_hit = status   (fallback to DevRev's own evaluation)
ELSE:
    FR = null  (not evaluable)
```

For Resolution Time:
```
IF completed_in[1] (RT minutes from DevRev) is available AND > 0:
    RT_hit = completed_in[1] <= RT_target
ELSE IF DevRev status (hit/miss) is available:
    RT_hit = status   (fallback to DevRev's own evaluation)
ELSE:
    RT = null  (not evaluable)
```

**What is `completed_in`?**
- DevRev's SLA-aware elapsed time in **business-hours minutes**
- For the default schedule (Mon-Fri 10AM-8PM IST): it counts only minutes within business hours
- Customer wait time (ticket in "Awaiting Customer Response" stage) pauses the SLA clock
- Non-business hours are excluded
- Important caveat: accounts on 24x7 contracts will appear to have better numbers because DevRev still measures in its 8x5 schedule — the actual calendar-time may be longer

**Step 5 — Aggregate**:
```
FR% = FR_hits / (FR_hits + FR_misses) * 100
RT% = RT_hits / (RT_hits + RT_misses) * 100
```
Tickets where FR or RT is `null` (not evaluable) are excluded from the denominator.

#### 5.2.3 The 25 Contractual SLA Policies

| Policy ID | Customer | P1 FR | P1 RT | P2 FR | P2 RT | P3 FR | P3 RT | P4 FR | P4 RT | Schedule |
|---|---|---|---|---|---|---|---|---|---|---|
| SLA-01 | DTDC | 15m | 2h | 1h | 18h | 2h | 36h | 4h | 45h | P1 24x7, P2 Mon-Sat, P3 Mon-Fri |
| SLA-02 | Flipkart/Myntra | 30m | 1h | 4h | 8h | 6h | 24h | 10h | 36h | 24x7 |
| SLA-03 | Template-A (Apollo, Wellness Forever, Box, SBT, Flow, etc.) | 15m | 2h | 4h | 48h | 4h | 120h | - | - | P1 24x7, P2 16x6, P3 8x5 |
| SLA-04 | Template-B (Aramex Global, Starlinks, Rozana) | 4h | - | 8h | - | 16h | - | - | - | 8x5 all tiers |
| SLA-05 | MOVIN | 30m | 1h | 2h | 6h | 4h | 12h | 8h | 16h | 24x7 all tiers |
| SLA-06 | Heineken | 1h | 4h | 4h | 16h | 6h | - | - | - | P1 24x7, P2/P3 8x5 |
| SLA-07 | Aujan/ANC | 15m | 1h | 2h | 6h | 4h | 12h | 8h | 16h | P1 24x7, P2-P4 Wknd 16h |
| SLA-08 | Aramex Move | 1h | 4h | 2h | 8h | 4h | 24h | 12h | 48h | P1/P2 24x7, P3/P4 16x6 |
| SLA-09 | Template-C (Proconnect, Partnr) | 4h | - | 8h | - | 16h | - | 24h | - | P1 24x7, P2-P4 8x5 |
| SLA-10 | Swiggy | 2h | - | 8h | - | 16h | - | 24h | - | P1 24x7, P2-P4 8x5 |
| SLA-11 | UBT (Ubteam) | 1h | 4h | 8h | 18h | 16h | - | 24h | - | Std/Prem varies |
| SLA-12 | Wakefit | 2h | - | 8h | - | 16h | - | - | - | P1 12x7, P2/P3 8x5 |
| SLA-13 | TibbyGo | 1h | - | 2h | - | 4h | - | 8h | - | P1/P2 24x7, P3/P4 8x5 |
| SLA-14 | Jeebly/GWC | 1h | - | 8h | - | 16h | - | 24h | - | P1 24x7, P2-P4 8x5 |
| SLA-15 | Teleport | 1h | 4h | 8h | 16h | 16h | 48h | 24h | 72h | P1 24x7, P2-P4 8x5 |
| SLA-16 | Kout (KFG) | 5m | 45m | 30m | 90m | 1h | 3h | 2h | 24h | P1 24x7, P2 16x6, P3 8x5 |
| SLA-17 | Caratlane | - | - | - | - | 4h | 120h | - | - | P3 8x5 |
| SLA-18 | Aster HC (Pharmacy) | 15m | 20m | 30m | 24h | 2h | 96h | 12h | - | Custom CSM |
| SLA-19 | Spencer | 1h | - | 8h | - | 16h | - | 24h | - | P1 8x7, P2-P4 8x5 |
| SLA-20 | Avery Dennison | 1h | 12h | 1h | 24h | 4h | 48h | 24h | 120h | P1 24hr Mon-Sun varies |
| SLA-21 | Qatarpost | 45m | 1h | 6h | 12h | 9h | 36h | 12h | 60h | P1 8x7, P3/P4 8x5 |
| SLA-22 | Aster Arabia (KSA) | 1h | - | 8h | - | 16h | - | 24h | - | 8x5 all tiers |
| SLA-23 | Catalent | 30m | 1h | 4h | 8h | 6h | 24h | 10h | 36h | 8x5 + wknd P1/P2 |
| SLA-24 | Floward | 4h | - | 8h | - | 16h | - | 24h | - | Mon-Fri 8x5 all |
| SLA-25 | Smiths News | 15m | 1h | 15m | 4h | 4h | 8h | 8h | 16h | P1/P2 24x7, P3/P4 8x5 |

"-" = no contractual target defined for that tier/metric.

#### 5.2.4 Color Coding
| Color | Range |
|---|---|
| Green | >= 75% |
| Yellow | 60-74% |
| Orange | 40-59% |
| Red | < 40% |

---

### Metric 3: RESOLUTION RATE

**Purpose**: Daily created vs resolved trend over the last 7 days.

**For each of the past 7 calendar days**:
- **Created**: Tickets with `created_date == that day`, excluding canceled, deduplicated across open+closed pools, passing `is_support()`
- **Resolved**: Tickets with `actual_close_date == that day`, stage in `("resolved", "Closed")`
- **Net**: `created - resolved` (positive = queue growing)

**Optimization**: Previously computed daily rates are stored in the snapshot file to avoid recomputing historical days.

**Bottom line**:
```
Resolve Ratio = total_resolved_7d / total_created_7d * 100
```

---

### Metric 4: RESOLUTION TAT (Turn-Around Time)

**Purpose**: How long does it take to resolve tickets, measured in percentiles.

**Pool**: All tickets resolved in the last 7 days (passing `is_support()`, stage = resolved/Closed).

#### 5.4.1 TAT Measurement (SLA-aware preferred)

The script uses a two-tier approach for each ticket:

**Tier 1 — SLA-aware time (preferred)**:
```
completed_in = sla_summary.sla_tracker.metric_target_summaries[]
               where metric name contains "Resolution"
               -> completed_in field (in minutes)
```
- This is DevRev's business-hours elapsed time
- Excludes customer wait time (ticket in "Awaiting Customer Response" pauses clock)
- Excludes non-business hours (outside Mon-Fri 10AM-8PM IST)
- Convert to hours: `hours = completed_in / 60`
- If `completed_in == 0`: skip this ticket (SLA was paused the entire duration — no actual support time)

**Tier 2 — Wall-clock fallback** (if no SLA-aware time available):
```
hours = (actual_close_date - created_date) in hours
```
- Includes all calendar time (weekends, nights, customer wait)
- Less accurate but better than no data
- The script logs how many tickets used this fallback

#### 5.4.2 Percentile Calculation

**Formula** (linear interpolation):
```python
def percentile(sorted_list, p):
    n = len(sorted_list)
    k = (p / 100) * (n - 1)
    floor_k = int(k)
    ceil_k = min(floor_k + 1, n - 1)
    if floor_k == ceil_k:
        return sorted_list[floor_k]
    return sorted_list[floor_k] * (ceil_k - k) + sorted_list[ceil_k] * (k - floor_k)
```

This is the same formula used in both repos — standard linear interpolation percentile.

**Example**: For 100 resolved tickets with TAT values sorted ascending:
- P10 = value at position 9.9 (interpolated between 10th and 11th values)
- P50 = value at position 49.5 (interpolated between 50th and 51st values — the median)
- P90 = value at position 89.1 (interpolated between 90th and 91st values)

**What P10, P50, P90 mean**:
| Percentile | Meaning | What it tells you |
|---|---|---|
| **P10** | 10% of tickets were resolved faster than this | Best-case resolution speed |
| **P50** | 50% of tickets were resolved faster than this | Median — the "typical" resolution time |
| **P90** | 90% of tickets were resolved faster than this | Worst-case (tail) — only 10% took longer |

**Breakdown**: Computed separately for each severity level (blocker, high, medium, low) in addition to the overall "All" row.

#### 5.4.3 Display Format
```
< 1 hour  -> displayed as minutes (e.g., "45m")
1-24 hours -> displayed as hours (e.g., "4.2h")
> 24 hours -> displayed as days (e.g., "2.1d")
```

#### 5.4.4 CX Pulse Dashboard approach (for reference)
The Vercel dashboard uses `Completed In[1]` (Resolution Time metric, SLA-aware minutes) directly from the API response — same source, same field. It does NOT fall back to wall-clock. TAT is always in business-hours minutes and displayed via the same percentile function.

---

### Metric 5: WHO RESOLVES

**Purpose**: Breakdown of who actually resolves tickets — Support team, Engineering, or Product.

**Pool**: Resolved tickets from the last 7 days.

**Field**: `custom_fields.tnt__resolved_by`
- Set manually by the CX Lead when closing a ticket
- Values: `"Resolved by Support"`, `"Resolved by Engineering"`, `"Resolved by Product"`

**Calculation**:
```
For each value: count / total_with_data * 100
```
Only tickets where `tnt__resolved_by` is non-empty are counted in the denominator.

---

### Metric 6: FRIDAY AI

**Purpose**: How effectively is Friday AI analyzing new tickets and sending first responses to customers.

**Pool**: Tickets created yesterday (from the `created_yday` list).

#### 5.6.1 Data Collection

For each ticket created yesterday, the script calls the Timeline API:
```
POST /timeline-entries.list
Body: { "object": "<ticket_id>", "limit": 30 }
```

It scans all timeline entries of type `"timeline_comment"` where `created_by.display_name` contains "friday" (case-insensitive), and extracts:

| Signal | How detected | What it means |
|---|---|---|
| **Analyzed** | Any Friday comment exists | Friday triggered and ran on this ticket |
| **RCA generated** | Comment body contains "Root Cause Analysis" or "Auto-Investigation" | Friday produced an investigation |
| **First response sent** | Friday comment with `visibility = "external"` | Friday sent a customer-facing reply |
| **Response latency** | `friday_external_comment.created_date - ticket.created_date` | Time from ticket creation to Friday's first customer reply |

**Concurrency**: Uses `ThreadPoolExecutor` with 10 parallel workers to speed up the timeline API calls.

#### 5.6.2 Metrics Reported

| Metric | Formula | What it tells you |
|---|---|---|
| **Tickets created** | `len(created_yday)` | Total new support tickets yesterday |
| **Friday analyzed** | `analyzed_count / created_count * 100` | Coverage % — what fraction Friday ran on |
| **RCA generated** | Count of tickets where Friday produced an RCA | How many got an AI investigation |
| **First response sent** | Count of tickets where Friday sent an external (customer-facing) comment | Actual customer impact — not just internal analysis |
| **Response time P50** | Median of `(friday_external_comment_time - ticket_created_time)` in minutes | How fast Friday replies to customers |
| **Response time Avg** | Average of the same latency values | Mean response speed |

#### 5.6.3 Classification (from CX Pulse Dashboard)

The Vercel dashboard uses a five-state classification for deeper analysis:

| Outcome | Meaning |
|---|---|
| **RanFull** | Friday produced both RCA and a usable first response draft |
| **RanRCAOnly** | Friday produced RCA but no customer-facing first response |
| **Skipped** | Friday detected the ticket but skipped it (workspace not mapped) |
| **Failed** | Friday attempted investigation but encountered an error |
| **NeverTriggered** | No Friday comment at all — Friday did not run on this ticket |

The daily dashboard reports the simplified version (analyzed/RCA/FR sent) for quick daily visibility.

---

### Metric 7: CX LEAD LOAD

**Purpose**: Current workload distribution across CX Leads.

**Pool**: All currently open support tickets.

**Calculation**:
1. For each ticket, resolve `tnt__assignee` to a CX Lead name (via DEVU_MAP)
2. Cross-tabulate by current stage

**Stage columns**:
| Abbreviation | Stage Name |
|---|---|
| Que | queued |
| WIP | work_in_progress |
| AwC | awaiting_customer_response |
| AwD | awaiting_development |
| AwP | awaiting_product_assist |
| InD | in_development |
| Rsg | Reassigned to Customer Support |
| Rop | Reopen |

**Display**: Top 12 CX Leads sorted by total ticket count descending. Each row shows total + count in each stage.

---

### Metric 8: AGING TICKETS

**Purpose**: How many tickets have been open for extended periods.

**Pool**: All currently open support tickets.

**Age calculation**:
```
age_days = today - created_date (in calendar days)
```

**Buckets**:
| Bucket | Filter | What it means |
|---|---|---|
| 7+ days | `age >= 7` | Open for a week or more |
| 15+ days | `age >= 15` | Open for two weeks or more |
| 30+ days | `age >= 30` | Open for a month or more — needs attention |

**Additional details for 30+ day tickets**:
- **Top 3 holders**: CX Leads with the most 30+ day tickets (with Slack @mentions)
- **Unassigned count**: 30+ day tickets with no `tnt__assignee`
- **Stuck in**: Top 3 stages where 30+ day tickets are sitting

---

## 6. Snapshot System

After each successful run, the script saves a snapshot to `config/daily-snapshot.json`.

**Purpose**: Enable accurate day-over-day comparisons for the next day's Pulse Check.

**Re-run protection**: If the script runs twice on the same day, it preserves the `prior_*` values from the first run so the trend comparison remains valid.

**Staleness handling**:
- Snapshot from yesterday: ideal, used directly
- Snapshot from today (re-run): uses `prior_*` values
- Snapshot 2-3 days old: usable with warning
- Snapshot older than 3 days or missing: falls back to reconstruction from current data

**`--dry-run` flag**: Outputs the report but does NOT update the snapshot file. Safe for testing.

---

## 7. Key Differences Between Repos

| Aspect | Daily Slack Report | CX Pulse Dashboard (Vercel) |
|---|---|---|
| **SLA Method** | Contractual (per-account targets) | DevRev default + Contractual side by side |
| **SLA Policies** | 25 contractual policies + default fallback | Same 25 policies + default fallback |
| **TAT Source** | SLA-aware `completed_in` with wall-clock fallback | SLA-aware `completed_in` only (no fallback) |
| **FR Filter** | Counts all tickets | Skips tickets without `reported_by` |
| **Lookback** | 7 days for resolved | 120 days for resolved |
| **Account Mapping** | Same consolidation map + Tech Mahindra -> Reliance | Same consolidation map |
| **Refresh** | Once daily at 9 AM IST | ~Hourly (CDN + GitHub Actions) |
| **CSAT** | Not included | Included (from surveys.responses.list) |
| **Sentiment** | Not included | Included (from ticket.sentiment.label) |
| **Friday AI** | Coverage %, RCA count, FR sent count, response time P50/Avg | Full 5-state classification + latency |

---

## 8. DevRev Fields Reference

| Field Path | Type | Used In | Purpose |
|---|---|---|---|
| `subtype` | string | Global filter | Must be "Support" |
| `severity` | string | Pulse Check, TAT | blocker/high/medium/low |
| `stage.name` | string | All metrics | Current ticket stage |
| `created_date` | ISO datetime | Pulse Check, Resolution Rate | When ticket was created |
| `actual_close_date` | ISO datetime | Resolution Rate, TAT | When ticket was resolved |
| `modified_date` | ISO datetime | Pagination | Smart stop for resolved fetch |
| `needs_response` | boolean | Pulse Check | Customer waiting for agent reply |
| `rev_org.display_name` | string | SLA, Account | Raw account/workspace name |
| `custom_fields.tnt__customer_cohort_dropdown` | string | Global filter | Customer cohort (WMS/Roadmap excluded) |
| `custom_fields.tnt__pod` | string | Global filter | Pod (WMS Inbound/Outbound excluded) |
| `custom_fields.tnt__assignee` | DON ref | CX Lead Load | Assigned CX Lead |
| `custom_fields.tnt__resolved_by` | string | Who Resolves | Support/Engineering/Product |
| `sla_summary.sla_tracker.metric_target_summaries[]` | array | SLA, TAT | Per-metric SLA data |
| `.metric_definition.name` | string | SLA, TAT | "First Response" or "Resolution Time" |
| `.status` | string | SLA | "hit", "miss", or "in_progress" |
| `.completed_in` | number (minutes) | SLA (contractual), TAT | Business-hours elapsed time |
| `display_id` | string | All | Ticket ID (e.g., TKT-12345) |

---

## 9. Schedule & SLA Clock

DevRev's default SLA schedule: **Mon-Fri 10:00 AM - 8:00 PM IST** (org_schedule-13)

- SLA clock only ticks during these 10 hours per weekday
- Clock pauses when ticket enters "Awaiting Customer Response" stage
- Clock stops when ticket reaches "Resolved" or "Closed" stage
- `completed_in` reflects only the business-hours minutes the clock was running

For contractual SLA evaluation, the `completed_in` value from DevRev is used as the elapsed time, regardless of the contract's stated schedule. This means:
- 24x7 contracts measured against DevRev's 8x5 clock may show higher compliance than actual calendar-time performance
- Note: Times are DevRev business-schedule minutes (Mon-Fri 10-8 IST); accounts on 24x7 contracts will appear to have better numbers here than in calendar time

---

## 10. Data Integrity Rules

1. **Never fabricate data** — only report what DevRev APIs return
2. **Same filter everywhere** — every metric uses the identical `is_support()` filter
3. **Deduplication** — tickets are deduplicated by `display_id` across open and closed pools
4. **No partial reports** — if the script fails, no report is posted
5. **Snapshot verification** — prior-day values come from the snapshot, not reconstruction
6. **Ticket IDs as links** — all ticket IDs in Slack are clickable DevRev links

---

*Document generated from `shipsy/cx-pulse` codebase and CX Pulse Dashboard.*
*Last updated: 21 June 2026*
