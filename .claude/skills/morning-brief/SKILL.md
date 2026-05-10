---
name: morning-brief
description: Generate the daily Morning CX Brief — 6-section structured report with 5 action sub-sections. Uses DevRev REST API with pagination for complete data. Posts to C0A82U7MZ5F and C07BQD5776Y at 9 AM IST daily via routine.
---

# Morning Brief — CX Pulse

Post to TWO Slack channels:
- `C0A82U7MZ5F` — leadership group DM
- `C07BQD5776Y` — #customer-experience-product-support

---

## Source of Truth

### What we mirror
DevRev vista **vista-549 ("Support - open tickets")**.
Only tickets where `state = "open"` or `"in_progress"` (not closed/resolved/canceled).
Only tickets where `subtype = "Support"`.
Exclude cohorts: `WMS`, `Roadmap`.

### Why REST API, not hybrid_search
`hybrid_search` is semantic/text-based — it returns max 20 results per query and ranks by text relevance, not state. In production it found only 3-6 tickets out of 300+. The REST API `works.list` supports structured filters, pagination (100 per page), and returns ALL matching tickets.

### Authentication
```
POST https://api.devrev.ai/works.list
Header: Authorization: Bearer <PAT>
Header: Content-Type: application/json
```
PAT is stored as environment variable `DEVREV_TOKEN`. If not available, use the PAT from the project's secure config.

### Pagination
```
Page 1: { "type": ["ticket"], "state": ["open", "in_progress"], "limit": 100 }
Page N: { "type": ["ticket"], "state": ["open", "in_progress"], "limit": 100, "cursor": "<next_cursor>" }
```
Continue until `next_cursor` is empty or `works` array is empty.

### JSON Parsing
Use `json.loads(response, strict=False)` — DevRev responses contain control characters that break strict JSON parsing.

---

## Execution Steps

### Step 0: Load Yesterday's Snapshot

Read file: `config/daily-snapshot.json`

This file contains yesterday's metrics AND ticket IDs for accurate inflow/outflow.

```json
{
  "date": "2026-05-11",
  "total": 316,
  "blockers": 1,
  "aging30": 19,
  "unassigned": 9,
  "needs_response": 105,
  "ticket_ids": ["TKT-97414", "TKT-97412", ...]
}
```

**If file doesn't exist or date is >2 days old:** Skip trend, show "Trend: No baseline available".

**Inflow/Outflow calculation (using ticket IDs):**
```python
today_ids = set(all current ticket display_ids)
yesterday_ids = set(snapshot["ticket_ids"])

new_tickets = today_ids - yesterday_ids       # inflow — tickets that appeared today
resolved_tickets = yesterday_ids - today_ids   # outflow — tickets that disappeared (resolved/closed)

inflow_count = len(new_tickets)
outflow_count = len(resolved_tickets)
```

This gives EXACT numbers, not estimates based on total delta.

### Step 1: Read Roster

Google Sheet ID: `1v8lbH2yZCU7TAInUNO2tqx-HDGbCjPVtqZEWX94pApc`

**How to find today's column:**
- Read the sheet content
- The header row contains dates in format: `1 May`, `2 May`, ..., `11 May`, `12 May`
- Find the column index where the header matches today's date
- For each person row, read the value at that column index

**Status parsing:**
| Cell value contains | Status |
|---------------------|--------|
| `AM` or `PM` | ON DUTY — extract shift time (e.g., "10:30 AM-07:30 PM") |
| `WO` | Week Off |
| `PL` | Paid Leave |
| `6th day working` | ON DUTY (extra day) |
| `Half Day` | ON DUTY (half) |
| Empty | Skip |

**CX Lead Roster (the people who appear as tnt__assignee on tickets):**
Vidushi Wanchoo, Vinod Kumar Gunda, Madhav Kapoor, Deepanshu Marwari, Vikas Pandey, Asif Khan, Medha Saxena, Laxmi Rajput, Kaustuv Choudhary, Srijan Srivastava, Saurabh Singh, Gangesh Pandey

**Exclude:** Saatwika Sisodia (left the team). WMS team members.

### Step 2: Pull ALL Open Support Tickets

Use DevRev REST API with pagination (see Source of Truth above).

**Client-side filter after fetching:**
```python
for ticket in all_fetched_tickets:
    if ticket.subtype != "Support": skip
    cohort = ticket.custom_fields.tnt__customer_cohort_dropdown
    if cohort in ("WMS", "Roadmap"): skip
    # Keep this ticket
```

**Fields to extract per ticket:**

| Field | JSON Path | Purpose |
|-------|-----------|---------|
| display_id | `ticket.display_id` | Ticket number (TKT-XXXXX) |
| don_id | `ticket.id` | Internal ID for API calls (timeline, etc.) |
| title | `ticket.title` | Description |
| cohort | `ticket.custom_fields.tnt__customer_cohort_dropdown` | Customer tier/segment |
| pod | `ticket.custom_fields.tnt__pod` | Sub-team |
| CX Lead | `ticket.custom_fields.tnt__assignee` | Designated support person (DON ID) |
| severity | `ticket.severity_v2.label` | Blocker / High / Medium / Low |
| stage | `ticket.stage.name` | Current workflow stage |
| state | `ticket.state` | open / in_progress |
| owner | `ticket.owned_by[0].display_name` | Current ticket owner |
| account | `ticket.rev_org.display_name` | Customer account name |
| needs_response | `ticket.needs_response` | Boolean — customer waiting for reply |
| created_date | `ticket.created_date` | For age calculation |
| modified_date | `ticket.modified_date` | For staleness calculation |

### Step 3: Build Sections 1-5

Process all tickets into the data structures needed for each section. See Section Definitions below for exact logic.

### Step 4: Build Section 6a-6d

Process tickets into the four action sub-sections. See Section Definitions below.

### Step 5: Build Section 6e — RCA Analysis

This requires timeline API calls. See RCA Classification section below for full methodology.

**API for each ticket (>2 days old):**
```
POST https://api.devrev.ai/timeline-entries.list
Header: Authorization: Bearer <PAT>
Body: { "object": "<ticket_don_id>", "limit": 20 }
```

Run in parallel (10-15 concurrent threads) to complete in ~2 minutes for 280 tickets.

### Step 6: Save Today's Snapshot

Write to `config/daily-snapshot.json`:
```json
{
  "date": "YYYY-MM-DD",
  "total": <count>,
  "blockers": <count>,
  "aging30": <count>,
  "unassigned": <count>,
  "needs_response": <count>,
  "ticket_ids": ["TKT-XXXXX", "TKT-YYYYY", ...]
}
```

This becomes tomorrow's baseline. The `ticket_ids` array enables exact inflow/outflow calculation.

### Step 7: Format and Post to Slack

Post to BOTH channels: `C0A82U7MZ5F` and `C07BQD5776Y`.
Use the output format template defined below.
All ticket IDs must be clickable: `<https://app.devrev.ai/shipsy/works/TKT-XXXXX|TKT-XXXXX>`

---

## Section Definitions

### TREND (Header)

**Purpose:** At a glance — is the queue improving or worsening?

**Calculation:**
```python
# Load yesterday's snapshot
yesterday = load("config/daily-snapshot.json")

# Calculate deltas
delta_total = today_total - yesterday["total"]
delta_blockers = today_blockers - yesterday["blockers"]
delta_aging = today_aging30 - yesterday["aging30"]
delta_unassigned = today_unassigned - yesterday["unassigned"]
delta_nr = today_needs_response - yesterday["needs_response"]

# Inflow/Outflow from ticket ID comparison
today_ids = set(all_ticket_display_ids)
yesterday_ids = set(yesterday["ticket_ids"])
inflow = len(today_ids - yesterday_ids)
outflow = len(yesterday_ids - today_ids)

# Arrow formatting
def arrow(delta):
    if delta > 0: return f"▲{delta}" + (" ⚠️" if delta > 5 else "")
    elif delta < 0: return f"▼{abs(delta)}" + (" ✅" if abs(delta) > 3 else "")
    else: return "—"
```

**Metrics in trend:**
| Metric | Source |
|--------|--------|
| Total Open | `count(support_tickets)` |
| Blockers | `count(severity_v2.label == "blocker")` |
| Aging 30d+ | `count(age >= 30 AND severity in ["blocker", "high"])` |
| Unassigned | `count(tnt__assignee is null)` |
| Unanswered | `count(needs_response == true)` |
| Inflow | `len(today_ids - yesterday_ids)` |
| Outflow | `len(yesterday_ids - today_ids)` |

---

### Section 1: CX Lead x Stage Matrix

**Purpose:** Who has how many tickets in which stage. Shows workload and where tickets are stuck.

**Calculation:**
```python
matrix = defaultdict(Counter)
for ticket in support_tickets:
    cx_lead = resolve_assignee_name(ticket)
    stage = ticket.stage.name
    matrix[cx_lead][stage] += 1
```

**Column order:**
```
queued | work_in_progress | awaiting_customer_response | awaiting_development |
awaiting_product_assist | in_development | Reassigned to Customer Support | Reopen
```

**Sort:** By total tickets descending.
**Show:** Top 12 CX Leads (covers all active ones).

---

### Section 2: Blockers

**Purpose:** Every blocker-severity ticket listed with full details.

**Filter:** `severity_v2.label == "blocker"` (case-insensitive)

**Display per blocker:** Ticket ID (clickable), Account, Title (50 chars), CX Lead, Owner, Age in days, Stage.

**If 0 blockers:** Show "No blockers ✅"

---

### Section 3: Aging 30+ Days Tickets

**Purpose:** High-severity tickets open for more than 30 days.

**Filter:**
```python
aged = [t for t in support_tickets
        if age(t) >= 30
        and severity(t).lower() in ("blocker", "high")]
```

**Display:** Group by CX Lead → count + key accounts (top 3 accounts per CX Lead).
**Sort:** By count descending.

---

### Section 4: Top Accounts

**Purpose:** Which customer accounts have the most open tickets, and what stages they're in.

**Calculation:**
```python
accounts = Counter(ticket.rev_org.display_name for ticket in support_tickets)
top_10 = accounts.most_common(10)

# For each account, also compute stage breakdown
acc_stages = defaultdict(Counter)
for ticket in support_tickets:
    acc_stages[ticket.rev_org.display_name][ticket.stage.name] += 1
```

**Columns:** Account | Open count | Status Breakdown (top 4 stages with counts)

**Stage abbreviations for display:**
| Full stage name | Abbreviation |
|-----------------|-------------|
| queued | Queued |
| work_in_progress | WIP |
| awaiting_customer_response | AwCust |
| awaiting_development | AwDev |
| awaiting_product_assist | AwProd |
| in_development | InDev |
| Reassigned to Customer Support | Reassigned |
| Reopen | Reopen |
| TKT Backlog | Backlog |

---

### Section 5: Today's Team

**Purpose:** Who's on duty, who's off, and how many tickets each person has.

**Data source:** Google Sheet roster (Step 1) + ticket counts from Section 1.

**Display:**
```
🟢 ON DUTY — name, shift time, open ticket count
🔴 OFF TODAY — name, reason (WO/PL), open ticket count (only if > 0)
```

**Sort ON DUTY:** By open ticket count descending.
**Flag:** ⚠️ next to OFF members with >30 tickets.

---

### Section 6a: Customer Unanswered

**What it measures:** Tickets where the customer sent a message and we haven't responded.

**Field:** `needs_response` (boolean)
- DevRev sets this to `true` automatically when a customer sends a message
- Resets to `false` when an agent replies
- This is DevRev-native behavior, we don't control it

**Calculation:**
```python
unanswered = [t for t in support_tickets if t.needs_response == True]

# Group by CX Lead
nr_by_cx = defaultdict(lambda: {"total": 0, "accounts": defaultdict(list)})
for t in unanswered:
    cx = resolve_assignee_name(t)
    account = t.rev_org.display_name
    nr_by_cx[cx]["total"] += 1
    nr_by_cx[cx]["accounts"][account].append(t.display_id)
```

**Columns:** CX Lead | Unanswered count | % of their tickets | Top Accounts (count)
**Sort:** By unanswered count descending.

---

### Section 6b: Not Triaged

**What it measures:** Tickets that nobody has picked up, triaged, or started working on.

**Stages included (3 stages that mean "not actively being worked"):**
```python
not_triaged_stages = [
    "queued",                          # Never touched — initial intake
    "TKT Backlog",                     # Parked — deliberately shelved
    "Reassigned to Customer Support"   # Bounced back from dev/product, in limbo
]
```

**Why these 3:**
- `queued`: Ticket entered the system, nobody picked it up.
- `TKT Backlog`: Someone looked at it and parked it. Rot silently.
- `Reassigned to Customer Support`: Another team sent it back. Neither team owns it.

**Calculation:**
```python
not_triaged = [t for t in support_tickets if t.stage.name in not_triaged_stages]

# Group by CX Lead
nt_by_cx = defaultdict(lambda: {"count": 0, "tickets": []})
for t in not_triaged:
    cx = resolve_assignee_name(t)
    nt_by_cx[cx]["count"] += 1
    nt_by_cx[cx]["tickets"].append({
        "id": t.display_id,
        "account": t.rev_org.display_name,
        "age": age(t),
        "stage": t.stage.name
    })
```

**Columns:** CX Lead | Count | Top tickets (ID, account, stage — top 3 oldest)
**Sort:** By count descending.

---

### Section 6c: No Human Activity 5+ Days (Stale)

**What it measures:** Tickets with no updates for 5+ days, with a breakdown of which stages they're stuck in.

**Field:** `modified_date`

**Calculation:**
```python
for ticket in support_tickets:
    days_since_modified = (today - ticket.modified_date).days
    if days_since_modified >= 5:
        mark_as_stale(ticket)

# Group by CX Lead with stage breakdown
stale_by_cx = defaultdict(lambda: {"count": 0, "stages": Counter()})
for t in stale_tickets:
    cx = resolve_assignee_name(t)
    stale_by_cx[cx]["count"] += 1
    stale_by_cx[cx]["stages"][t.stage.name] += 1
```

**Why 5 days:** Weekend = 2 days natural gap. 5 days = 3+ working days with zero touch.

**Columns:** CX Lead | Stale count | Stuck In (stage breakdown — top 3 stages)
**Sort:** By stale count descending.

**Note on modified_date:** This field gets updated by bots/automations too. A ticket may show as "recently modified" even if no human has looked at it. `modified_date` is a conservative proxy — if even `modified_date` is stale, the ticket is definitely abandoned.

---

### Section 6d: Follow-up Needed (Awaiting Customer)

**What it measures:** Tickets where we asked the customer something, they haven't responded, and we haven't followed up.

**Filter:** `stage.name == "awaiting_customer_response"` AND modified_date exceeds tier threshold.

**Tier-based thresholds:**
```python
tier1_cohorts = {"1-Reliance", "1-DTDC"}          # 3 days
tier2_cohorts = {"2-Aramex", "2-HNK"}             # 5 days
# Everything else                                  # 7 days

for ticket in awaiting_customer_tickets:
    cohort = ticket.custom_fields.tnt__customer_cohort_dropdown
    if cohort in tier1_cohorts:
        threshold = 3
    elif cohort in tier2_cohorts:
        threshold = 5
    else:
        threshold = 7

    days_silent = (today - ticket.modified_date).days
    if days_silent >= threshold:
        flag_for_followup(ticket)
```

**Why tier-based:**
- Tier 1 (Reliance, DTDC) = dedicated enterprise. 3 days silence is too long.
- Tier 2 (Aramex, HNK) = strategic accounts. 5 days.
- Others = 7 days is reasonable.

**Columns:** Ticket ID (clickable) | Account | CX Lead (with @) | Days Silent | Tier
**Sort:** By days silent descending.

---

### Section 6e: Missing RCA Analysis

**What it measures:** Tickets older than 2 days where no human has written a proper analysis/investigation. Excludes automated workflows and AI-generated content.

**Age filter:** Only check tickets where `age >= 2 days`. Newer tickets haven't had time for analysis.

**API:** For each qualifying ticket, call `timeline-entries.list`:
```
POST https://api.devrev.ai/timeline-entries.list
Body: { "object": "<ticket.id>", "limit": 20 }
```

Run in parallel (10-15 threads) for speed. ~280 tickets takes ~2 minutes.

**Classification of each timeline comment:**

First, filter to only `type == "timeline_comment"` entries.

Then classify each comment body:

**EXCLUDE — these are NOT human analysis (system/bot/AI):**

| Pattern | What it is |
|---------|-----------|
| `[Auto-Investigation]` anywhere in body | Automated workflow that runs at ticket creation |
| Body starts with `**Problem Statement:**` | Shipsy AI auto-generated initial analysis |
| `Stage has been changed` anywhere in body | Stage change bot notification |
| `This ticket was mentioned in Slack` anywhere in body | Slack integration bot |
| `Thank you for contacting us!` anywhere in body | Auto-acknowledgment email template |
| `Auto-assigned` anywhere in body | Auto-assignment bot |
| `This ticket has been open for` anywhere in body | Reminder bot (aging notification) |
| `Both background agents have completed` anywhere in body | AI agent system completion message |
| `projectx agent` anywhere in body | AI agent reference |

**EXCLUDE — trivial replies (not RCA, just acknowledgments):**
Body (lowercase, first 20 chars) starts with: `checking`, `noted`, `ok`, `done`, `resolved`, `hi `, `hello`, `thanks`, `sure`

**HUMAN RCA criteria (a comment counts as human analysis if ALL are true):**
1. Not matched by any EXCLUDE pattern above
2. Not matched by any trivial reply pattern above
3. Body length >= 80 characters (substantive content, not a one-liner)

**Classification per ticket:**
```python
for ticket in tickets_over_2_days:
    comments = fetch_timeline_comments(ticket)
    found_ai = False
    found_human_rca = False

    for comment in comments:
        body = comment.body
        if starts_with_problem_statement(body):
            found_ai = True
            continue
        if is_excluded(body):
            continue
        if is_trivial(body):
            continue
        if len(body.strip()) >= 80:
            found_human_rca = True
            break  # at least one human RCA found, enough

    if found_human_rca:
        result = "human_rca"       # Good — human analyzed this ticket
    elif found_ai:
        result = "ai_only"         # Bad — only AI looked at it, no human follow-up
    else:
        result = "no_analysis"     # Worst — nobody looked at it at all
```

**Display:**
```
CX Lead | Missing | No Analysis | AI-Only
```
Plus a list of the oldest tickets without human RCA (top 8).

**Sort:** By missing count descending.

---

## CX Lead Name Resolution

The `tnt__assignee` field returns a DON ID (e.g., `don:identity:dvrv-us-1:devo/xXjPo9nF:devu/1327`).
Extract the `devu/XXXX` suffix and map:

| DON suffix | Name |
|------------|------|
| devu/1327 | Gangesh Pandey |
| devu/2573 | Saurabh Singh |
| devu/901 | Sachin Shivhare |
| devu/2585 | Laxmi Rajput |
| devu/1088 | Deepanshu Marwari |
| devu/2580 | Vikas Pandey |
| devu/2976 | Srijan Srivastava |
| devu/1246 | Vinod Kumar Gunda |
| devu/3000 | Kaustuv Choudhary |
| devu/1314 | Vidushi Wanchoo |
| devu/2636 | Asif Khan |
| devu/2978 | Medha Saxena |
| devu/1090 | Madhav Kapoor |
| devu/2934 | Abhishek Bhandari |
| devu/3007 | Bhavyank Sarolia |
| devu/2744 | Omi Vaish |
| devu/2647 | Pakhi Vashishth |
| devu/3063 | Tejal Shirsat |
| devu/2676 | SKG/Sumit Gupta |
| devu/3091 | Gaurav Singh |

**If DON ID not in this table:** Try resolving via `GET https://api.devrev.ai/dev-users.get?id=<don_id>`. Extract `full_name` or `display_name`. Cache the result.

**If resolution fails:** Show as `DEVU-{number}`.
**If `tnt__assignee` is null/empty:** Show as `Unassigned`.

---

## Cohort Tier Mapping (for Section 6d thresholds)

| Tier | Cohorts | Follow-up Threshold |
|------|---------|---------------------|
| Tier 1 | `1-Reliance`, `1-DTDC` | 3 days |
| Tier 2 | `2-Aramex`, `2-HNK` | 5 days |
| Tier 3+ | `3A-On Demand`, `3B-S (On Demand)`, `4A-B2C Shipper`, `4A-B2C LSP`, `4B-S (B2C Shipper)`, `4B-S (B2C LSP)`, `5A-B2B LSP`, `5A-B2B Shipper`, `5B-S (B2B LSP)`, `5B-S (B2B Shipper)`, `Exim`, `Platform`, `AI`, `TBD` | 7 days |

See `.claude/rules/cohort-mapping.md` for full cohort details.

---

## Output Format

```
🎫 *CX Pulse — Morning Brief* | {{day}}, {{date}}
_Source: vista-549 · {{total}} open support tickets_

```📊 Trend: {{yesterday_day}} {{yesterday_date}} → {{today_day}} {{today_date}}
🎫 Total Open:     {{y_total}} → {{t_total}}  {{arrow}}
🔴 Blockers:       {{y_block}} → {{t_block}}  {{arrow}}
🟠 Aging 30d+:     {{y_aged}}  → {{t_aged}}   {{arrow}}
⚪ Unassigned:     {{y_unas}}  → {{t_unas}}   {{arrow}}
⚠️ Unanswered:    {{y_nr}}    → {{t_nr}}     {{arrow}}
📥 Inflow: +{{inflow}} new | 📤 Outflow: -{{outflow}} resolved```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👥 *1. CX Lead × Stage*
```{{matrix table}}```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 *2. Blockers* ({{count}})
```{{blocker table or "No blockers ✅"}}```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🟠 *3. Aging 30+ Days Tickets* ({{count}})
```{{aged table}}```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏢 *4. Top Accounts*
```{{account table with status breakdown}}```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🧑‍💼 *5. Today's Team*
```🟢 ON DUTY ({{count}})
{{name, shift, open tickets}}

🔴 OFF TODAY (with open tickets)
{{name, reason, open tickets}}```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 *6. Action Required*

*6a. ⚠️ Customer Unanswered — {{count}} tickets ({{pct}}%)*
```{{CX Lead | Unanswered | % of tickets | Top Accounts}}```
→ Action: Each CX Lead to clear unanswered queue as morning priority

*6b. 🕳️ Not Triaged — {{count}} tickets*
_Includes: Queued + TKT Backlog + Reassigned to Customer Support_
```{{CX Lead | Count | Top tickets}}```
→ Action: All not-triaged tickets >7d must be triaged or reassigned today

*6c. 💤 No Human Activity 5+ Days — {{count}} tickets ({{pct}}%)*
```{{CX Lead | Stale | Stuck In}}```
→ Action: Add update on all 5d+ tickets today

*6d. 📩 Follow-up Needed — {{count}} tickets*
_Tier 1 (Reliance/DTDC): 3d | Tier 2 (Aramex/HNK): 5d | Others: 7d_
```{{Ticket | Account | CX Lead | Days Silent | Tier}}```
→ Action: Send follow-up to customer

*6e. 🔍 Missing RCA Analysis — {{count}} tickets ({{pct}}% of tickets >2d old)*
_Excluded: [Auto-Investigation] workflow, **Problem Statement:** (Shipsy AI), stage-change bots, Slack bots, reminder bots._
```{{CX Lead | Missing | No Analysis | AI-Only}}```
_Oldest tickets without human RCA:_
```{{Ticket | Account | CX Lead | Age}}```
→ Action: CX Leads to add RCA/analysis on their missing tickets

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Daily Snapshot Schema

File: `config/daily-snapshot.json`

```json
{
  "date": "YYYY-MM-DD",
  "total": 316,
  "blockers": 1,
  "aging30": 19,
  "unassigned": 9,
  "needs_response": 105,
  "ticket_ids": [
    "TKT-97414",
    "TKT-97412",
    "..."
  ]
}
```

**Updated:** Every morning run, after generating the report but before posting.
**Used by:** Next day's run for trend calculation and exact inflow/outflow.
**ticket_ids:** Complete list of all support ticket display_ids at time of snapshot. This is the key to accurate inflow/outflow — compare today's ticket IDs with yesterday's to know exactly which tickets are new and which were resolved.

---

## Rules

1. **NEVER fabricate data.** Only report what APIs return. If an API call fails, say "data unavailable" — never guess.
2. **Clickable ticket links:** Format as `<https://app.devrev.ai/shipsy/works/TKT-XXXXX|TKT-XXXXX>` in Slack output.
3. **Only state = "open" or "in_progress".** Never include closed/resolved/canceled tickets.
4. **CX Lead = `tnt__assignee` field.** If empty, show "Unassigned".
5. **Cross-reference roster.** In Section 5, show duty status for each CX Lead.
6. **Exclude WMS and Roadmap cohorts.** These are tracked separately.
7. **Use REST API with pagination** — NOT hybrid_search. hybrid_search misses 99%+ of tickets.
8. **Save daily snapshot** after generating report (Step 6).
9. **RCA check is selective** — only for tickets >2 days old. Run timeline calls in parallel.
10. **Tier-based follow-up thresholds:** Tier 1 = 3 days, Tier 2 = 5 days, Others = 7 days.
11. **Not-triaged includes 3 stages:** queued + TKT Backlog + Reassigned to Customer Support.
12. **No target lines.** Do not add "Target: bring below X by EOD" or similar lines.
13. **No concentration risk lines.** Do not add clustering/concentration commentary below section tables.
14. **No insights section.** The brief has exactly 6 sections + 5 action sub-sections. No Section 7.
15. **JSON parsing:** Always use `strict=False` when parsing DevRev API responses.
16. **Age calculation:** `age_days = (today - created_date).days`
17. **Post to BOTH channels:** `C0A82U7MZ5F` and `C07BQD5776Y`. Every run, both channels.
