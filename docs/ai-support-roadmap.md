# AI Support Agents — Roadmap & Strategy

**Date:** June 1, 2026
**Owner:** Gaurav Singh (Lead - AI Applied Engineer, CX)
**Status:** Active

---

## Executive Summary

Shipsy's AI support infrastructure has two pillars:
1. **CX Pulse** — fleet-level daily visibility, metrics, proactive alerting (LIVE)
2. **Friday / Shipra** — per-ticket AI investigation and resolution (32% coverage, scaling)

This roadmap covers the next phase: **deep, organization-specific AI support agents** that move Friday from shallow symptom description (current 0.9x impact) to root-cause diagnosis with actionable resolution (target 2x+ speedup).

Three organization-specific agents are planned: **Aramex** (in progress), **WMS** (tools ready), **Exim** (to build).

---

## Where We Are Today

### Friday Agent — 30-Day Metrics (May 2-Jun 1, 2026)

| Metric | Value | Assessment |
|--------|-------|------------|
| Total support tickets | 1,204 | Baseline |
| Friday coverage | 32.1% (387/1,204) | Low — 2 of 3 tickets get no AI analysis |
| RCA + First Response draft | 78 (6.5%) | Only 1 in 15 tickets gets customer-ready draft |
| RCA only (no FR draft) | 309 | Analysis exists but not actionable enough |
| Median RCA time | 378s (~6 min) | Acceptable speed |
| Resolution speedup | **0.9x** | Not accelerating resolution |

### Why 0.9x — The Data Gap Problem

Friday currently has access to:
- DevRev ticket metadata (title, body, customer, stage, SLA)
- Timeline comments

Friday does **NOT** have access to:
- **Production logs (BigQuery)** — event traces, error patterns, transaction sequences
- **EU region Elastic logs** — Aramex and EU customers route through EU infra, completely invisible
- **Rider analytics** — delivery execution data, GPS traces, route deviations, SLA breaches at delivery level

Without these, Friday's RCA describes the *symptom* from ticket text but cannot diagnose the *cause*. The support person still investigates manually — hence no resolution speedup.

### CX Pulse — Operational Metrics (LIVE)

| Routine | Status | Schedule |
|---------|--------|----------|
| CX Daily Dashboard | LIVE | 9 AM IST daily |
| Morning Brief | LIVE (superseded by Dashboard) | — |
| Evening Wrap-up | LIVE | 6 PM IST daily |
| Sentinel | LIVE | Every 2 hours |
| CX Monthly Report | LIVE | 1st of month, 9 AM IST |
| Auto-Allocation | Architecture complete | Phase 2 |

---

## Phase 1: Fix Friday's Blind Spots (Current Sprint)

**Goal:** Give Friday the data it needs to go from symptom → root cause.
**Target:** Move resolution speedup from 0.9x to 2x+.

### 1A. EU Elastic Logs

| Item | Detail |
|------|--------|
| **What** | Connect Friday to EU-region Elasticsearch cluster |
| **Why** | Aramex (Tier 2 strategic) and other EU customers route through EU infrastructure. Friday is completely blind to their logs — cannot trace errors, check API responses, or diagnose integration failures |
| **Impact** | Unblocks Aramex investigation quality. Currently Aramex has 23+ day avg resolution — worst performer |
| **Dependency** | EU Elastic endpoint, read credentials, index patterns |
| **Deliverable** | Elastic MCP tool or direct query integration in Shipra |

### 1B. BigQuery Production Logs

| Item | Detail |
|------|--------|
| **What** | Give Friday read access to BigQuery production event logs |
| **Why** | BigQuery contains transaction traces, error events, API call logs. Friday can correlate a ticket's reported issue with what actually happened in the system — e.g., "shipment booking failed because carrier API returned 503 at 14:32 UTC" |
| **Impact** | Transforms RCA from "customer says X" to "system shows Y happened because Z" |
| **Dependency** | BigQuery project ID, service account with read access, relevant table/dataset names |
| **Deliverable** | BigQuery query tool integrated into Friday's toolset |

### 1C. Rider Analytics

| Item | Detail |
|------|--------|
| **What** | Connect Friday to rider analytics data — delivery execution, GPS traces, route performance, SLA at delivery level |
| **Why** | For Aramex and last-mile delivery accounts, many tickets are about delivery failures, missed SLAs, route deviations. Without rider-level data, Friday can only see "delivery failed" but not why |
| **Impact** | Directly enables Aramex resolution — their top issues involve delivery execution |
| **Dependency** | Rider analytics API/data source, access credentials |
| **Deliverable** | Rider analytics query tool in Shipra |

---

## Phase 2: Aramex Deep-Dive Agent (In Progress)

**Goal:** Bring Aramex resolution TAT from 23 days to <5 days.
**Status:** Skill docs created (PR in Shipra repo). Data sources from Phase 1 needed.

### Aramex Context

- **Cohort:** 2-Aramex (Tier 2 Strategic)
- **Sub-accounts:** Aramex Global, Aramex VW, Aramex Move, Aramex SDD, Aramex Freight, Aramex Oceania, Aramex RO
- **Team:** Srijan (Brahmos pod), Abhishek (WB pod), Laxmi (general)
- **DevRev Group:** aramex projects (group-251)
- **Complexity:** Aramex uses ServiceNow internally — tickets flow INC→ServiceNow→DevRev, creating multi-hop delays

### Top Recurring Issue Categories (from DevRev data)

| Category | Example Tickets | Pattern |
|----------|----------------|---------|
| Integration failures | TKT-98332 (ServiceNow iPaaS) | Cross-system middleware breaks, ServiceNow ↔ DevRev sync |
| Service configuration | TKT-73633 (Click & Collect 6.7.0) | Backend agent setup, scan event responses, code pattern issues |
| Territory optimization | TKT-62929 (Alexandria Cars) | Route planning, zone assignment, capacity modeling |
| Booking/carrier errors | TKT-42429 (Socket Timeout) | Aramex API timeouts, shipment booking failures — **blocker severity** |
| Label & package issues | TKT-45107, TKT-4727 | Package qty discrepancies, label printing failures |

### What the Aramex Agent Needs

1. **Phase 1 data sources** — EU Elastic, BigQuery, Rider Analytics (Aramex is EU-routed)
2. **Aramex org knowledge** — account structure, ServiceNow integration flow, pod-specific routing
3. **Skill templates** — pre-built investigation paths for top 5 issue categories
4. **Aramex-specific tools** — query Aramex carrier API status, check territory config, validate integration mappings

### Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Avg resolution TAT | 23+ days | <5 days |
| Friday coverage on Aramex tickets | ~32% | >90% |
| First Response SLA hit rate | Low | >75% |
| Tickets requiring human investigation | ~100% | <40% |

---

## Phase 3: WMS Support Agent (Pipeline — Tools Ready)

**Goal:** Dedicated WMS AI support agent with deep warehouse operations knowledge.
**Status:** 23 tools created. Organization doc complete. Agent build pending.

### WMS Context

- **Cohort:** WMS
- **Key accounts:** Rozana, Milkbasket, Kimbal, JGH, Wellness Forever, Sathya/Wondersoft, Stockone
- **Team:** Bhavyank Sarolia (Inbound + Outbound), Tulja Rathod, Shajiya Shaik
- **DevRev Group:** WMS (group-289)

### Top Recurring Issue Categories (from DevRev data)

| Category | Example Tickets | Pattern |
|----------|----------------|---------|
| PO/STO duplication | TKT-67096, TKT-92142 | Purchase orders appearing in multiple locations, duplicate line numbers |
| Data sync failures | TKT-76879 (WMS vs MB SKU sync) | Discrepancies between WMS and external systems |
| Outbound errors | TKT-83978 (Invoice failed) | Recurring outbound processing failures, temporary fixes only |
| Report issues | TKT-91057 (Outward gate pass) | Missing data in reports, data discrepancies |
| Customer frustration | TKT-91768 (Kimbal), TKT-91057 | Recurring unresolved issues, tickets closed without resolution |

### What's Already Built

- 23 tools covering warehouse operations
- Organization doc with WMS domain knowledge
- Tool categories: inbound (GRN, putaway, ASN), outbound (picking, packing, dispatch), inventory (stock, cycle count, reconciliation)

### Remaining Work

1. Wire 23 tools into a cohesive agent
2. Connect to WMS-specific data sources (WMS database, inventory APIs)
3. Build skill templates for top 5 recurring issue types
4. Test against historical tickets for accuracy

### Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Friday coverage on WMS tickets | Excluded from current metrics | >80% |
| Avg resolution TAT | TBD (need baseline) | <24h for P1 issues |
| Repeat ticket rate | High (Kimbal, Rozana) | <20% |

---

## Phase 4: Exim Support Agent (To Build)

**Goal:** From-scratch AI support agent for Exim (international trade/logistics) product.
**Status:** Not started. This section serves as the detailed plan for leadership.

### Exim Context

- **Cohort:** Exim
- **Product:** International freight forwarding — import/export bookings, customs, documentation, tracking
- **Key accounts:** Motherson Group, Ubteam, Bunge, Expeditors, Aujan (import/export/SD-KSA), Flowpl (UAE/Express), Aster (KSA/Pharmacy)
- **Current support:** No dedicated AI agent, tickets handled manually

### Top Recurring Issue Categories (from DevRev data)

| Category | Example Tickets | Pattern |
|----------|----------------|---------|
| Tracking errors | TKT-2858, TKT-174 (Motherson) | EXIM shipment tracking failures, status not updating |
| Booking/report failures | TKT-98630 (Ubteam) | EXIM module reports showing "No results!", booking data not displaying |
| E-way bill issues | TKT-93795 (Expeditors) | Recurring errors when booking with e-way bills, incorrect updates |
| Excel upload problems | TKT-40519 (Bunge) | Dropdown column issues, data not populating correctly on upload |
| International portal issues | TKT-53225 (DTDC INTL) | Customer portal validation failures for international shipments |

### Build Plan

#### Step 1: Exim Data Analysis (Week 1)
- Pull all Exim cohort tickets from DevRev (historical + open)
- Classify into issue categories with frequency counts
- Identify top 10 recurring issues by volume
- Map accounts → issue patterns → resolution paths
- Output: **Exim Issue Taxonomy** document

#### Step 2: Organization Doc (Week 1-2)
- Document Exim product architecture: modules, workflows, integrations
- Map customer accounts with their specific configurations
- Document customs/regulatory workflows by country
- Catalog common misconfigurations and their fixes
- Output: **Exim Organization Knowledge Base**

#### Step 3: Tool Development (Week 2-3)
Target tool categories:

| Category | Tools | Purpose |
|----------|-------|---------|
| Shipment tracking | Track shipment status, check carrier integration status, verify tracking events | Diagnose tracking failures |
| Booking & documentation | Validate booking data, check document compliance, verify e-way bill config | Resolve booking errors |
| Customs & compliance | Check customs status, validate HS codes, verify regulatory requirements by country | Handle customs-related tickets |
| Configuration audit | Check account config, validate carrier mappings, verify portal settings | Diagnose config issues |
| Data & reporting | Query shipment reports, check data pipeline status, validate Excel templates | Resolve report/upload issues |

Estimated: **15-20 tools** (based on WMS precedent of 23 tools)

#### Step 4: Skill Templates (Week 3)
Build pre-built investigation paths for top recurring issues:
- "Shipment tracking not updating" → check carrier API → check event pipeline → check mapping
- "Booking report empty" → check filters → check data pipeline → check account permissions
- "E-way bill error" → validate bill format → check GST config → check carrier e-way integration
- "Excel upload failing" → validate template version → check dropdown config → check data format
- "Portal login/access issue" → check user permissions → check domain config → check SSL

#### Step 5: Agent Integration & Testing (Week 3-4)
- Wire tools + org knowledge + skills into agent
- Test against 50 historical Exim tickets
- Measure: RCA accuracy, investigation completeness, suggested resolution quality
- Iterate based on test results

### Dependencies

| Dependency | Owner | Status |
|------------|-------|--------|
| Exim product architecture docs | Product/Eng team | Needed |
| Exim backend access (logs, configs) | Infra team | Needed |
| Customs/regulatory reference data | Domain expert | Needed |
| Carrier integration specs | Integration team | Needed |

### Success Metrics

| Metric | Baseline | Target |
|--------|----------|--------|
| Friday coverage on Exim tickets | 0% | >80% |
| Avg resolution TAT | TBD (need baseline) | <48h |
| RCA accuracy (validated by CX Lead) | N/A | >85% |
| Tickets auto-resolved without human | 0% | >30% |

---

## Phase 5: Founder OKR Alignment

These phases directly map to Dhruv's expected metrics:

| OKR Metric | Phase | How |
|------------|-------|-----|
| SLA Adherence (account-wise) | BUILT | CX Daily Dashboard — live |
| Resolution TAT (P10/P50/P90) | BUILT | CX Daily Dashboard — live |
| Human-free resolution % | Phase 1-4 | Once agents can resolve without human, track % |
| Skills for high-frequency issues | Phase 2-4 | Skill templates per org agent |
| Customer-wise automation efficiency | Phase 2-4 | Coverage + speedup per account |
| Support CSAT | Ongoing | Increase DevRev survey dispatch rate |

---

## Overall Timeline

```
June 2026
  Week 1-2: Phase 1 — EU Elastic + BigQuery + Rider Analytics integration
  Week 2-3: Phase 2 — Aramex agent goes live (skill docs ready, needs Phase 1 data)

July 2026
  Week 1-2: Phase 3 — WMS agent build (23 tools ready, wire + test)
  Week 1-2: Phase 4 Step 1-2 — Exim data analysis + org doc
  Week 3-4: Phase 4 Step 3-4 — Exim tool development + skills

August 2026
  Week 1:   Phase 4 Step 5 — Exim agent testing + launch
  Week 2-4: Phase 5 — Founder OKR metrics dashboard integration
```

---

## Architecture — How Org-Specific Agents Fit

```
Ticket arrives in DevRev
  |
  v
CX Pulse: Auto-Allocation (Phase 2)
  |-- Route to correct team based on cohort + pod
  |
  v
Friday/Shipra: AI Investigation
  |-- Generic Friday: DevRev data only (current)
  |-- Aramex Agent: + EU Elastic + BigQuery + Rider Analytics + Aramex org knowledge
  |-- WMS Agent: + WMS tools (23) + warehouse domain knowledge
  |-- Exim Agent: + Exim tools (15-20) + trade/customs knowledge
  |
  v
CX Lead receives: Ticket + AI RCA + Suggested resolution + Data evidence
  |
  v
CX Pulse: Track resolution, SLA, publish metrics
```

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| EU Elastic access delayed | Medium | High (blocks Aramex) | Escalate to infra team, document exact requirements |
| BigQuery query costs | Low | Medium | Read-only access, query limits, cache frequent patterns |
| Exim domain knowledge gaps | Medium | Medium | Partner with Exim product team early, use ticket data as ground truth |
| Agent accuracy < target | Medium | High | Test against historical tickets before launch, human-in-the-loop for first 2 weeks |
| WMS tool integration complexity | Low | Low | 23 tools already built, mostly wiring work |

---

## Appendix: Data Sources Summary

| Data Source | Current Status | Needed For |
|-------------|---------------|------------|
| DevRev API | LIVE | All agents |
| Slack (16+ channels) | LIVE | CX Pulse routines |
| Google Drive (roster) | LIVE | CX Pulse routines |
| EU Elastic | NOT CONNECTED | Aramex agent, EU customers |
| BigQuery | NOT CONNECTED | All org agents (production logs) |
| Rider Analytics | NOT CONNECTED | Aramex agent, last-mile accounts |
| WMS Database | NOT CONNECTED | WMS agent |
| Exim Backend | NOT CONNECTED | Exim agent |
| New Relic | CONFIGURED, not active | Sentinel enhancement |
| GitHub | CONFIGURED, not active | Deploy correlation |
