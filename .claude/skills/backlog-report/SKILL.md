---
name: backlog-report
description: Generate an old open Support tickets backlog report — grouped by CX Lead, with ticket links, stage, cohort, customer, and age. Configurable date cutoff. Uses DevRev REST API. Output to CLI only.
---

# Backlog Report — Old Open Support Tickets

CLI-only report. Do NOT post to Slack.

---

## Parameters

The user can customize the date cutoff when invoking this skill.

| Parameter | Default | Example |
|-----------|---------|---------|
| `cutoff_date` | `2026-04-01` | "before 1st March 2026", "before January 2026" |

**How to detect:** When the user says "backlog report before 1st March 2026" or "old tickets before February", extract the date and convert to ISO format for the API: `YYYY-MM-DDT00:00:00Z`. Adjust for IST (subtract 5:30h) if needed, or use `YYYY-03-31T18:30:00Z` for "before 1st April".

If no date is specified, use **2026-04-01** (i.e., `2026-03-31T18:30:00Z` in UTC).

---

## Source of Truth

### API Endpoint
```
POST https://api.devrev.ai/works.list
Header: Authorization: Bearer <PAT>
Header: Content-Type: application/json
```

PAT is stored as environment variable `DEVREV_TOKEN`. If not set, extract from `.claude/settings.local.json`.

### Request Body
```json
{
  "type": ["ticket"],
  "ticket": {"subtype": ["Support"]},
  "stage": {
    "name": [
      "queued",
      "Reopen",
      "work_in_progress",
      "awaiting_product_assist",
      "awaiting_development",
      "in_development",
      "Reassigned to Customer Support",
      "awaiting_customer_response"
    ]
  },
  "created_date": {
    "type": "range",
    "before": "<cutoff_date_utc>"
  },
  "limit": 100
}
```

### Pagination
If response contains `next_cursor`, send another request with `"cursor": "<next_cursor>"` added to the body. Continue until `next_cursor` is empty or `works` array is empty.

### JSON Parsing
Use `json.loads(response, strict=False)` — DevRev responses contain control characters that break strict JSON parsing.

### Why REST API, not hybrid_search
`hybrid_search` is semantic — it cannot filter by subtype, created_date, or stage. In testing it found 0 out of 42 matching tickets. The REST API `works.list` returns exact structured results.

---

## Execution Steps

### Step 1: Determine Cutoff Date

Parse the user's request for a date. Convert to UTC ISO format.

Examples:
- "before 1st April 2026" → `2026-03-31T18:30:00Z`
- "before March 2026" → `2026-02-28T18:30:00Z`
- "before 1st January 2026" → `2025-12-31T18:30:00Z`
- No date specified → `2026-03-31T18:30:00Z` (default)

### Step 2: Fetch Tickets via REST API

Save response to `/tmp/backlog_report_data.json`.

Use bash with curl:
```bash
export DEVREV_TOKEN="<token>"
curl -s -X POST "https://api.devrev.ai/works.list" \
  -H "Authorization: Bearer $DEVREV_TOKEN" \
  -H "Content-Type: application/json" \
  -d '<request_body>' > /tmp/backlog_report_data.json
```

### Step 3: Process and Generate Report

Use Python to parse the JSON and generate the report. The script must:

1. **Load the JSON** with `strict=False`
2. **Resolve CX Lead names** from `tnt__assignee` DON IDs using the mapping table below
3. **Group tickets by CX Lead** (sorted by count descending)
4. **Calculate age** for each ticket: `(today - created_date).days`
5. **Output the report** in the format defined below

---

## CX Lead Name Resolution

The `tnt__assignee` field returns a DON ID. Extract `devu/XXXX` suffix and map:

| DON suffix | Name | Email |
|------------|------|-------|
| devu/1327 | Gangesh Pandey | gangesh.pandey@shipsy.io |
| devu/2573 | Saurabh Singh | saurabh.singh@shipsy.io |
| devu/901 | Sachin Shivhare | sachin.shivhare@shipsy.io |
| devu/2585 | Laxmi Rajput | laxmi.rajput@shipsy.io |
| devu/1088 | Deepanshu Marwari | deepanshu.marwari@shipsy.io |
| devu/2580 | Vikas Pandey | vikas.pandey@shipsy.io |
| devu/2976 | Srijan Srivastava | srijan.srivastava@shipsy.io |
| devu/1246 | Vinod Kumar Gunda | vinod.kumargunda@shipsy.io |
| devu/3000 | Kaustuv Choudhary | kaustuv.choudhary@shipsy.io |
| devu/1314 | Vidushi Wanchoo | vidushi.wanchoo@shipsy.io |
| devu/2636 | Asif Khan | asif.khan@shipsy.io |
| devu/2978 | Medha Saxena | medha.saxena@shipsy.io |
| devu/1090 | Madhav Kapoor | madhav.kapoor@shipsy.io |
| devu/2934 | Abhishek Bhandari | abhishek.bhandari@shipsy.io |
| devu/3007 | Bhavyank Sarolia | bhavyank.sarolia@shipsy.io |
| devu/2744 | Omi Vaish | omi.vaish@shipsy.io |
| devu/2647 | Pakhi Vashishth | pakhi.vashishth@shipsy.io |
| devu/3063 | Tejal Shirsat | tejal.shirsat@shipsy.io |
| devu/2676 | Sumit Kumar Gupta | sumit.gupta@shipsy.io |
| devu/3091 | Gaurav Singh | gaurav.singh@shipsy.io |
| devu/2949 | Akshit Goyal | akshit.goyal@shipsy.io |
| devu/2626 | Shajiya Shaik | shajiya.shaik@shipsy.io |
| devu/1222 | Sachin Shivhare | sachin.shivhare@shipsy.io |

Also pull names from `owned_by[].full_name` and `owned_by[].email` in the response to resolve any IDs not in this table.

If DON ID is not in table and not resolvable: show `DEVU-{number}`.
If `tnt__assignee` is null/empty: show `Unassigned`.

---

## Stage Display Names

| API name | Display |
|----------|---------|
| queued | Queued |
| work_in_progress | Work In Progress |
| awaiting_customer_response | Awaiting Customer Response |
| awaiting_development | Awaiting Development |
| awaiting_product_assist | Awaiting Product Assist |
| in_development | In Development |
| Reopen | Reopen |
| Reassigned to Customer Support | Reassigned to CX Support |

---

## Output Format

Output directly to CLI. Do NOT post to Slack.

```
Old Open Support Tickets | {{day}}, {{date}}
Source: vista-1806 | {{total}} tickets | subtype=Support | created before {{cutoff_date_display}}

{{total}} open · {{breached}} SLA breached · {{queued}} queued (unactioned) · {{lead_count}} CX Leads
=======================================================================================================

For EACH CX Lead (sorted by ticket count descending):

========================================================================================================
  @{{CX Lead Name}}  ({{count}} tickets)  {{email}}
========================================================================================================
  #   Ticket       Link                                                   Age  Stage                        Cohort             Customer               Title
  --- ------------ ---------------------------------------------------- ----- ---------------------------- ------------------ ---------------------- -----
  1   TKT-XXXXX    https://app.devrev.ai/shipsy/works/TKT-XXXXX          XXXd {{stage}}                     {{cohort}}         {{customer}}           {{title}}
  ...

========================================================================================================
```

After all CX Lead sections, add summary:

```
Key Takeaways
  - Total: {{total}} tickets, {{breached}} SLA breached
  - Top cohort: {{top_cohort}} ({{top_cohort_count}} tickets, {{top_cohort_pct}}%)
  - {{queued}} tickets still in Queued — never actioned
  - Oldest ticket: {{max_age}} days old
  - Highest load: {{top_lead}} ({{top_lead_count}} tickets)

Actions Needed
  1. {{top_lead}} — {{count}} tickets. Triage queued ones immediately.
  2. {{top_cohort}} cluster — needs dedicated attention.
  3. {{queued}} queued tickets — assign owners or close if stale.
  4. 180+ day tickets — escalate or close.
```

---

## Fields to Extract Per Ticket

| Field | JSON Path | Purpose |
|-------|-----------|---------|
| display_id | `ticket.display_id` | Ticket number |
| title | `ticket.title` | Truncate to 50 chars |
| cohort | `ticket.custom_fields.tnt__customer_cohort_dropdown` | Cohort |
| CX Lead | `ticket.custom_fields.tnt__assignee` | DON ID → resolve to name |
| stage | `ticket.stage.name` | Current stage |
| state | `ticket.state` | open / in_progress |
| owner | `ticket.owned_by[0].full_name` | Current owner |
| account | `ticket.account.display_name` | Customer account |
| rev_org | `ticket.rev_org.display_name` | Customer org |
| created_date | `ticket.created_date` | For age: (today - created).days |
| sla_summary | `ticket.sla_summary.stage` | breached / paused / running |

Customer = `account.display_name` or `rev_org.display_name` (whichever is available), truncated to 20 chars.

---

## Rules

1. **NEVER fabricate data.** Only report what the API returns.
2. **Ticket links:** Full URL format: `https://app.devrev.ai/shipsy/works/TKT-XXXXX`
3. **CX Lead = `tnt__assignee` field.** Not `owned_by`.
4. **Tag CX Leads** with `@Name` and show email.
5. **CLI only.** Do not post to Slack unless explicitly asked.
6. **Use REST API** — NOT hybrid_search. hybrid_search cannot do structured filtering.
7. **JSON parsing:** Always use `strict=False`.
8. **Date is customizable.** Parse from user request, default to 2026-04-01.
9. **Sort** CX Leads by ticket count descending, tickets within each lead by created_date ascending (oldest first).
