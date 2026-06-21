---
name: cx-daily-dashboard
description: Daily CX Support Dashboard — 7-metric report posted to Slack at 9 AM IST. Uses Python script for deterministic execution. No AI interpretation of data.
---

# CX Daily Dashboard

Post the CX Support Daily Metrics to Slack every day at 9:00 AM IST.

---

## How to Execute

Run the Python script. It does everything — fetch, compute, format, output.

```bash
python3 scripts/cx_daily_dashboard.py
```

The script outputs the formatted Slack message to stdout. The trigger agent posts it to Slack using the Slack MCP tool `slack_send_message`.

---

## Filters (Applied to ALL metrics)

Every metric uses the SAME filter:

1. `subtype = "Support"` (strict — must be exactly "Support", not null)
2. Exclude cohorts: `tnt__customer_cohort_dropdown` in ("WMS", "Roadmap")
3. Exclude pods: `tnt__pod` in ("WMS Inbound", "WMS Outbound")
4. For resolved metrics: exclude `stage = "canceled"` (only count "resolved" + "Closed")

---

## Data Sources

### Open Tickets
```
POST https://api.devrev.ai/works.list
Body: {"type": ["ticket"], "state": ["open", "in_progress"], "limit": 100}
Paginate ALL pages (40-50 pages, ~4000 raw tickets -> ~230 support)
```

### Resolved/Closed Tickets (last 7 days)
```
POST https://api.devrev.ai/works.list
Body: {"type": ["ticket"], "state": ["resolved", "closed"], "limit": 100}
Smart stop: when modified_date < 14 days ago (~12 pages)
Client-side filter: actual_close_date >= 7 days ago, stage in (resolved, Closed)
```

### Previous Day Reconstruction (for Pulse Check trend)
```
open_yesterday = (tickets open now created <= yesterday)
               + (tickets closed after yesterday created <= yesterday)
```

### Authentication
DevRev PAT token stored in the script. Bearer token auth.

---

## 7 Metrics

### 1. PULSE CHECK
- Open Now: count of open support tickets (with filter)
- Previous day: reconstructed open count for yesterday (same filter)
- Blockers: severity = "blocker" (field: ticket.severity, plain string)
- Unanswered: needs_response = true AND stage in ("queued", "work_in_progress")
- Created yesterday: created_date = yesterday, excl canceled, with filter
- Resolved yesterday: actual_close_date = yesterday, stage = resolved/Closed, with filter

### 2. SLA ADHERENCE (Contract Basis)
- Uses contractual SLA policies (SLA-01 through SLA-25) with per-account, per-severity targets
- For each ticket: look up account's contractual FR/RT target in minutes for its severity
- FR hit = completed_in[0] (DevRev SLA-aware minutes) <= contractual FR target
- RT hit = completed_in[1] (DevRev SLA-aware minutes) <= contractual RT target
- If completed_in not available, falls back to DevRev hit/miss status
- Accounts without a contract use default SLA targets (P1: 15m FR/4h RT, P2: 1h/36h, P3: 2h/48h, P4: 4h/72h)
- SKIP accounts (internal/demo) excluded from SLA reporting entirely
- Hit% = hit / (hit + miss). Tickets with no evaluable data excluded from %
- Pool: open tickets + resolved last 7 days combined (excl SKIP accounts)
- Show top 12 accounts by pool size + "X more" rolled up
- Show pool breakdown: contractual / default / skip
- Color coding: >=75% green, 60-74% yellow, 40-59% orange, <40% red
- Period label: "(open + resolved 7d)"

### 3. RESOLUTION RATE
- Daily created vs resolved for last 7 days
- Created: created_date = that day, excl canceled, with filter
- Resolved: actual_close_date = that day, stage = resolved/Closed, with filter
- Net: created - resolved (positive = queue growing)
- Resolve ratio: total resolved / total created
- No canceled column

### 4. RESOLUTION TAT
- TAT = actual_close_date - created_date (wall-clock hours)
- Pool: resolved last 7 days, with filter
- P10 = 10th percentile (fastest 10%)
- P50 = 50th percentile (median)
- P90 = 90th percentile (slowest 10%)
- Breakdown by severity: blocker, high, medium, low

### 5. WHO RESOLVES
- Field: tnt__resolved_by (set by CX Lead when closing)
- Values: "Resolved by Support", "Resolved by Engineering", "Resolved by Product"
- % from tickets with data only
- Pool: resolved last 7 days

### 6. FRIDAY AI
- Source: Timeline API (timeline-entries.list) for tickets created yesterday
- Check for comments by author "Friday" with detailed RCA
- Coverage = tickets with Friday RCA / total created yesterday
- Time to RCA = trigger timestamp -> Friday response timestamp (from Slack channel)
- Show: tickets analyzed count, P50 time, avg time
- DO NOT show: skip rate, miss rate, organization breakdown

### 7. CX LEAD LOAD
- CX Lead = tnt__assignee field resolved to name via DEVU mapping
- Stage = current ticket stage
- Show top 12 CX Leads sorted by total tickets desc
- Columns: Tot, Que, WIP, AwC, AwD, AwP, InD, Rsg, Rop

---

## Account Consolidation Map

Strip " - Default Workspace" and " Account" suffixes first, then apply:

```
Reliance <- Reliance (RIL), RIL, Reliance, reliancehyperlocal, ril-tira,
            1P Jiomart Reliance, Reliance - 3P, QWIK Logistics, rcpldemo
DTDC <- DTDC, dtdc.in
Aramex <- Aramex Global, Aramex VW, Aramex Move, Aramex Same Day Delivery,
          Aramex RO, Aramex Oceania, Aramex Freight, Aramex, Aramex SDD
Flipkart <- Flipkart, fkfooddemo, FK Food, flipkartdropship
Rozana <- Rozana, rozanaondemand
Wellness Forever <- Wellness Forever, Wellness Forever (TMS), [WMS] Wellness Forever
Milkbasket <- Milkbasket
Kama Ayurveda <- Kama Ayurveda
Movin <- Movin, movin1demo
Apollo247 <- Apollo247
Spencers <- Spencers
Heineken <- HNK-BR1-Primary, HNK-BR1-Secondary, HNK-BR1-Support
Myntra <- Myntra, myntrahl, myntrahldemo
Swiggy <- Swiggy, swiggytms
Proconnect <- proconnect, proconnect Account
Wakefit <- wakefit, wakefitdemo
Box <- box Account, box
Expeditors <- expeditorsdemo, Expeditors
Aster KSA <- asterksademo
Aster Pharmacy <- Aster Pharmacy
Aujan <- aujan-export, aujan-import, aujansd-ksa, aujanimport
Flowpl <- flowpluae, flowpl, flowexpress
NX Logistics <- nxlogistics
CaratLane <- caratlane
SBT <- sbt
Healthkart <- healthkart
Field <- field
Incnut <- incnut
Frontline <- frontline
Hero MotoCorp <- heromotocorp
Zajel <- zajel
Ubteam <- ubteam
```

---

## CX Lead Name Mapping (DEVU)

```
devu/1327 -> Gangesh Pandey
devu/2573 -> Saurabh Singh
devu/901 -> Sachin Shivhare
devu/2585 -> Laxmi Rajput
devu/1088 -> Deepanshu Marwari
devu/2580 -> Vikas Pandey
devu/2976 -> Srijan Srivastava
devu/1246 -> Vinod Kumar Gunda
devu/3000 -> Kaustuv Choudhary
devu/1314 -> Vidushi Wanchoo
devu/2636 -> Asif Khan
devu/2978 -> Medha Saxena
devu/1090 -> Madhav Kapoor
devu/2934 -> Abhishek Bhandari
devu/3007 -> Bhavyank Sarolia
devu/2744 -> Omi Vaish
devu/2647 -> Pakhi Vashishth
devu/3063 -> Tejal Shirsat
devu/2676 -> SKG/Sumit Gupta
devu/3091 -> Gaurav Singh
devu/2626 -> Shajiya Shaik
devu/1885 -> Shipsy Support
devu/863 -> Akash KumarRajek
devu/899 -> Yash Singh
devu/1009 -> Sana Amreen
devu/1607 -> Amit Dubey
devu/2944 -> Bhanu Arya
devu/2632 -> Nikhila K
```

---

## Slack Message Format

EXACT format — do not change alignment, emojis, or structure:

```
📊 **CX Support — Daily Metrics** | {DD} {Mon} {YYYY}
_Data as of {yesterday DD Mon}_

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**1. PULSE CHECK**
\```
               {prev_date}    {today_date}   Change
Open              {prev}       {now}     {arrow}
Blockers          {prev}       {now}     {arrow} {emoji}
Unanswered        {prev}       {now}     {arrow} {emoji}

Yesterday:  +{created} created | -{resolved} resolved | net {net}
\```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**2. SLA ADHERENCE** _(open + resolved 7d)_
FR **{fr_pct}%** hit ({fr_hit}/{fr_total}) · RT **{rt_pct}%** hit ({rt_hit}/{rt_total})
\```
 #  Account            Pool   FR%    RT%
──  ─────────────────  ────  ─────  ─────
{rows with color emoji 🟢🟡🟠🔴}
    {remaining} more accts  {pool}  {fr%}  {rt%}

🟢 >=75%  🟡 60-74%  🟠 40-59%  🔴 <40%
\```

{...sections 3-7 in same pattern...}
```

Color coding for SLA:
- >= 75% -> 🟢
- 60-74% -> 🟡
- 40-59% -> 🟠
- < 40% -> 🔴

Pulse Check emojis:
- Decrease in blockers -> ✅
- Increase in unanswered -> ⚠️
- Decrease in open -> ✅

---

## Snapshot

File: `config/daily-snapshot.json`

```json
{
  "date": "YYYY-MM-DD",
  "total": 232,
  "blockers": 1,
  "unanswered": 34,
  "filter": "subtype=Support, excl WMS/Roadmap cohorts, excl WMS Inbound/Outbound pods, unanswered=queued+WIP only"
}
```

Saved after each run. Used for next day's Pulse Check trend.

---

## Rules

1. NEVER fabricate data. Only report what APIs return.
2. Use the Python script — do NOT try to compute metrics yourself.
3. The script outputs the Slack message to stdout. Post it as-is.
4. If the script fails, do NOT post a partial report. Report the error.
5. Post to the specified Slack channel only.
6. Do NOT add any extra sections, commentary, or insights.
7. Do NOT remove the "Powered by DevRev API" text (already removed per user).
