---
name: morning-brief
description: Generate the daily Morning CX Brief — mirrors vista-549 (Support - open tickets), 6-section structured report. Posts to C0A82U7MZ5F and C07BQD5776Y at 8 AM IST daily.
---

# Morning Brief — CX Pulse

Post to TWO channels: C0A82U7MZ5F (leadership DM) and C07BQD5776Y (#customer-experience-product-support).

## Source of Truth

Mirrors **vista-549 ("Support - open tickets")** in DevRev.
Only tickets where state = "open" or "in_progress" (not closed/resolved/canceled).

## Execution Steps

### Step 1: Read Roster
Google Sheet `1v8lbH2yZCU7TAInUNO2tqx-HDGbCjPVtqZEWX94pApc`. Today's column.
ON DUTY (name + shift) vs OFF (WO/PL). Exclude WMS team.

### Step 2: Pull ALL Open Support Tickets

Run multiple searches to maximize coverage:
```
hybrid_search namespace=ticket query="support tickets currently open queued not resolved" limit=50
hybrid_search namespace=ticket query="support tickets in progress awaiting response" limit=50
hybrid_search namespace=ticket query="support tickets awaiting development not closed" limit=50
hybrid_search namespace=ticket query="support tickets reopened reopen" limit=50
hybrid_search namespace=ticket query="unassigned support tickets open" limit=50
hybrid_search namespace=ticket query="support tickets frustrated unhappy sentiment open" limit=50
```

For EACH unique ticket, `get_ticket`. FILTER: only keep state = "open" or "in_progress".

Extract per ticket:
- `display_id` — clickable link
- `title`
- `tnt__customer_cohort_dropdown` — cohort
- `tnt__pod` — pod
- `tnt__assignee` — CX Lead (the designated support person)
- `severity_v2.label` — Blocker / High / Medium / Low
- `stage.name` — Queued / In Progress / Awaiting Customer Response / Awaiting Development / Reopen / Awaiting Product Assist
- `state` — must be "open" or "in_progress"
- `owned_by[0].display_name` — current owner
- `account.display_name` — customer
- `rev_org.display_name` — org
- `sentiment.label`
- `sla_summary` — hit/miss per metric
- `needs_response`
- `created_date` — for age calculation (today - created_date = age in days)

### Step 3: Scan Slack Channels (last 24h)
- `C07BQD5776Y` — frustrated alerts
- `C0AU4MT6MUK` — escalations
- `C09P8BC41PW` — Aramex WhatsApp
- `C0ACT5ER2E6` — ChronoDiali WhatsApp
- `C09L2ARTF4J` — Flipkart WhatsApp
- `C09EDETE468` — Reliance WhatsApp
- `C081FG99KKL` — Starlinks external
- `C081GJ2M0LW` — Qatar Post external
- `C07UZFTU7C4` — Movin

### Step 4: Format & Post to BOTH channels

```
*CX Pulse — Morning Brief* | {{day}}, {{date}}
_Source: vista-549 · {{total}} open tickets_

*{{total}} open* · *{{blockers}} blockers* · *{{frustrated}} frustrated* · *{{sla_breached}} SLA breached* · *{{unassigned}} unassigned*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

:pushpin: *Headlines*
{{one-liner biggest risk today}}
On Duty: {{count}}/{{total team}} {{weekend note if applicable}}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

:busts_in_silhouette: *1. CX Lead Wise* (tnt__assignee)

```
CX Lead              | Open | Blocker | Frust | SLA Miss | On Duty?
---------------------|------|---------|-------|----------|----------
{{assignee name}}    | {{n}}| {{n}}   | {{n}} | {{n}}    | Yes/No/WO
Unassigned           | {{n}}| {{n}}   | {{n}} | {{n}}    | —
...
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

:gear: *2. POD Wise*

```
Pod              | Open | Blocker | Frust | SLA Miss
-----------------|------|---------|-------|----------
On Demand        | {{n}}| {{n}}   | {{n}} | {{n}}
MCM              | {{n}}| {{n}}   | {{n}} | {{n}}
Alpha            | {{n}}| {{n}}   | {{n}} | {{n}}
Brahmos          | {{n}}| {{n}}   | {{n}} | {{n}}
Finance          | {{n}}| {{n}}   | {{n}} | {{n}}
...
(not set)        | {{n}}| {{n}}   | {{n}} | {{n}}
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

:office: *3. Top 10 Accounts*

```
Account              | Open | Frust | SLA   | Key Issue
---------------------|------|-------|-------|-----------------------------
{{account}}          | {{n}}| {{n}} | {{s}} | {{one-liner}}
...
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

:red_circle: *4. Blockers* ({{count}} total)

• TKT-XXXXX | {{Account}} | {{title}} | CX Lead: {{assignee or UNASSIGNED}} | Age: {{days}}d
• ...
(If 0 blockers: "No blockers :large_green_square:")
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

:hourglass_flowing_sand: *5. Age Wise* (pending tickets)

```
Age              | Count | % of Total
-----------------|-------|------------
0-7 days         | {{n}} | {{%}}
7-14 days        | {{n}} | {{%}}
14-30 days       | {{n}} | {{%}}
30+ days         | {{n}} | {{%}}  ← needs attention
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

:bar_chart: *6. Status Wise*

```
Stage                         | Count
------------------------------|------
Queued                        | {{n}}
In Progress                   | {{n}}
Awaiting Customer Response    | {{n}}
Awaiting Development          | {{n}}
Awaiting Product Assist       | {{n}}
Reopen                        | {{n}}
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

:satellite: *Channel Signals* (last 24h)

```
Source                           | Signals | Key Issue
---------------------------------|---------|------------------
{{channel}}                      | {{cnt}} | {{summary or Silent}}
...
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

:busts_in_silhouette: *Today's Team*

```
ON DUTY
{{Name}}     {{bars}}  {{count}} open   {{shift}}

OFF TODAY (with open tickets)
{{Name}}     {{bars}}  {{count}} open   WO/PL
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

:bulb: *Notable*
• {{insight 1}}
• {{insight 2}}

:dart: *Actions*
1. *{{Person}}* → {{ticket}}: {{what and why}}
...

_Morning Baseline — evening report will track RESOLVED vs STILL OPEN for each ticket above_
```

## Age Calculation
```
age_days = (today - created_date).days
Bucket:
  0-7 days   = recent
  7-14 days  = aging
  14-30 days = old
  30+ days   = critical — flag these
```

## Rules

1. NEVER fabricate data.
2. Clickable links: `<https://app.devrev.ai/shipsy/works/TKT-XXXXX|TKT-XXXXX>`
3. Only state = "open" or "in_progress". Never include closed.
4. CX Lead = `tnt__assignee` field. If empty, show "Unassigned".
5. Cross-reference roster — flag CX Lead as "WO" or "PL" if off today.
6. Keep under 4500 characters.
7. 3PL (4A+5A) — always highlight if overwhelmed.
8. Exclude WMS team.
9. Blockers section: list EVERY blocker with full details. This is critical.
10. 30+ days tickets in Age Wise section = flag as needing attention.
11. Actions: 3-5 items, each with person + ticket + reason.
