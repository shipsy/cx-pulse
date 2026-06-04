# DevRev SLA Exception Setup Guide

Per-customer SLA exceptions to configure in DevRev UI.
Path: **Settings > SLA > Support Ticket SLA Default > Exceptions**

## Severity Mapping (Contract → DevRev)

| Contract Priority | DevRev Severity | Description |
|---|---|---|
| P1 (Critical/Shutdown) | Blocker | Platform down, all users affected |
| P2 (High/Bugs) | High | Major bugs, business impact |
| P3 (Medium/Improvements) | Medium | Minor bugs, UI changes |
| P4 (Low/Queries) | Low | Training, general queries |

## Current DevRev Default SLA (sla-28)

| Severity | First Response | Resolution | Schedule |
|---|---|---|---|
| Blocker | 15m | 4h | 24x7 |
| High | 1h | 36h | Mon-Sat 10AM-8PM |
| Medium | 2h | 48h | Mon-Fri 10AM-8PM |
| Low | 4h | 72h | Mon-Fri 10AM-8PM |

---

## Tier 1 — Dedicated Enterprise

### DTDC (1-DTDC)

**Accounts:** DTDC (ACC-u5JsHNO6), dtdc.co (ACC-1ERdqDghw), dtdc.in (ACC-im2HyH1y)
**Uptime:** Not stated in contract
**Source:** Shipsy - DTDC MSA (Executed October 28, 2020), Annexure 1

| Severity | First Response | Resolution | Schedule | vs Default |
|---|---|---|---|---|
| Blocker | 15m | 2h | 24x7 | Same resp, TIGHTER res (2h vs 4h) |
| High | 1h | 18h | Mon-Sat 10AM-7PM | Same resp, TIGHTER res (18h vs 36h) |
| Medium | 2h | 36h | Mon-Fri 10AM-7PM | Same resp, TIGHTER res (36h vs 48h) |
| Low | 4h | 45h | Mon-Fri 10AM-7PM | Same resp, TIGHTER res (45h vs 72h) |

**Action:** Create exception. Condition: Account in [DTDC, dtdc.co, dtdc.in].
- Blocker: resp 15m, res **2h**, 24x7
- High: resp 1h, res **18h**, Mon-Sat 10AM-7PM
- Medium: resp 2h, res **36h**, Mon-Fri 10AM-7PM
- Low: resp 4h, res **45h**, Mon-Fri 10AM-7PM

### RIL / Reliance (1-Reliance)

**Accounts:** Reliance (RIL) (ACC-y36IXmM4), RIL (ACC-6wFfy2pw), Reliance (ACC-Wc8Rt9rz), Reliance Grocery (ACC-JKoyH2yi)
**Source:** RIL _ Shipsy - MSA.pdf

**NO TIERED SLA** — Contract is AMC-based. Only commitment: 24x7 support on critical platform/module failure. No P1/P2/P3 response/resolution times, no uptime %, no service credits.

**Action:** No exception needed — default SLA applies (and is actually stricter than the contract requires). Consider documenting that default SLA is the de facto standard for Reliance.

---

## Tier 2 — Strategic Accounts

### Aramex (2-Aramex) — DMCC MSA (Primary)

**Accounts:** Aramex (ACC-G0tfv4Ge), Aramex Global (ACC-cldfPBey), Aramex VW (ACC-x6aBsVOi), Aramex Oceania (ACC-YFdgDPLP), Aramex Freight (ACC-11duBDFNw), Aramex RO (ACC-mGbG1chd), Aramex Move (ACC-o0NpKw5T), aramex.com.au (ACC-1FBk68T7w), aramex.co.nz (ACC-3YvXMdkj)
**Uptime:** 99.4%
**Service Credits:** Yes — 0.5% (99.4-98%), 1% (98-97%), 3% (97-95%) of monthly recurring fee
**Source:** Aramex _ Shipsy MSA_.pdf (MSA Shipsy DMCC + Aramex Int. LLC, 11 Mar 2025)

| Severity | First Response | Resolution | Schedule | vs Default |
|---|---|---|---|---|
| Blocker | 1h | 4h | 24x7 | LOOSER resp (1h vs 15m), same res |
| High | 2h | 8h | 24x7 | LOOSER resp (2h vs 1h), TIGHTER res (8h vs 36h), WIDER hours (24x7 vs Mon-Sat) |
| Medium | 4h | 24h | 16x6 | LOOSER resp (4h vs 2h), TIGHTER res (24h vs 48h) |
| Low | 12h | 48h | 16x6 | LOOSER resp (12h vs 4h), TIGHTER res (48h vs 72h) |

**Action:** Create exception. Condition: Account in [all 9 Aramex accounts].
- Blocker: resp **1h**, res 4h, 24x7
- High: resp **2h**, res **8h**, **24x7**
- Medium: resp **4h**, res **24h**, 16x6 (7AM-11PM Dubai)
- Low: resp **12h**, res **48h**, 16x6

**Note:** Aramex KSA POC has a DIFFERENT, weaker SLA (P1 4h / P2 8h / P3 16h, all 8x5, no resolution times). If KSA tickets are on the same accounts, the primary DMCC SLA should apply.

### Heineken (2-HNK)

**Accounts:** heineken (ACC-BvMwCgbz), heineken.com.br (ACC-C4800jMY), heineken-br1 (ACC-5zvP8D4)
**Uptime:** 99.9%
**Service Credits:** Termination right (no % credit), penalty if >10% downtime (2x monthly recurring fee)
**Source:** Heineken _ Shipsy - MSA.pdf + SoW/SCM SLA schedule

| Severity | First Response | Resolution | Schedule | vs Default |
|---|---|---|---|---|
| Blocker | 1h | 4h | 24x7 | LOOSER resp (1h vs 15m), same res |
| High | 4h | 16h | 8x5 Mon-Fri | LOOSER resp (4h vs 1h), TIGHTER res (16h vs 36h), NARROWER hours |
| Low* | 6h | — | 8x5 Mon-Fri | LOOSER resp (6h vs 4h), no resolution committed |

*3-tier contract: P3 maps to DevRev Low (no Medium tier).

**Action:** Create exception. Condition: Account in [heineken, heineken.com.br, heineken-br1].
- Blocker: resp **1h**, res 4h, 24x7
- High: resp **4h**, res **16h**, Mon-Fri 8x5
- Low: resp **6h**, res **none committed** (use default 72h or leave blank), Mon-Fri 8x5
- Medium: No contractual tier — use default (2h / 48h) or skip

---

## Strategic Accounts (Custom SLAs)

### Flipkart (3A-On Demand) — Platinum Addendum

**Accounts:** Flipkart (ACC-cBf033gP), flipkart.in (ACC-OPPE2slK), Flipkart DH Offload (ACC-jdKQCOIt)
**Uptime:** 99.6%
**Service Credits:** None
**Source:** Addendum No. 3 (Platinum tier)

| Severity | First Response | Resolution | Schedule | vs Default |
|---|---|---|---|---|
| Blocker | 30m | 1h | 24x7 | LOOSER resp (30m vs 15m), TIGHTER res (1h vs 4h) |
| High | 4h (biz) | 8h (biz) | 16x6 | LOOSER resp (4h vs 1h), TIGHTER res (8h vs 36h) |
| Medium | 6h (biz) | 24h (biz) | 8x5 | LOOSER resp (6h vs 2h), TIGHTER res (24h vs 48h) |
| Low | 10h (biz) | 36h (biz) | 8x5 | LOOSER resp (10h vs 4h), TIGHTER res (36h vs 72h) |

**Action:** Create exception. Condition: Account in [Flipkart, flipkart.in, Flipkart DH Offload].
- Blocker: resp **30m**, res **1h**, 24x7
- High: resp **4h**, res **8h**, 16x6
- Medium: resp **6h**, res **24h**, Mon-Fri 8x5
- Low: resp **10h**, res **36h**, Mon-Fri 8x5

### ASDA UK

**Accounts:** Asda (ACC-lYzn2A0l)
**Uptime:** 99.9% (quarterly measurement)
**Service Credits:** Yes — <99.9% = 1 week of charges, <98.5% = 1 month of charges (quarterly)
**Source:** Asda Shipsy Order (Final Clean).pdf, Appendix 4 + 6

| Severity | First Response | Resolution | Schedule | vs Default |
|---|---|---|---|---|
| Blocker | 1h | — | 24x7 | LOOSER resp (1h vs 15m), no resolution committed |
| High | 4h | — | Business Days | LOOSER resp (4h vs 1h), NARROWER hours |
| Low* | 8h | — | 8x5 | LOOSER resp (8h vs 4h) |

*3-tier contract: P3 maps to DevRev Low.

**Action:** Create exception. Condition: Account in [Asda].
- Blocker: resp **1h**, no res commitment, 24x7
- High: resp **4h**, no res commitment, Business Days 9AM-5PM
- Low: resp **8h**, no res commitment, 8x5
- Medium: No contractual tier — use default or skip

### Zepto (3A-On Demand) — SLA & Penalty Addendum

**Accounts:** NOT FOUND in DevRev — needs account creation or mapping
**Uptime:** 99.9% (with penalty bands)
**Service Credits:** Yes — 3-tier penalty matrix (uptime + support SLA + API latency), 3-10% of monthly billing
**Source:** Zepto.pdf + SLA & Penalty Addendum (Aug 2022, supersedes base)

| Severity | First Response | Resolution | Schedule | vs Default |
|---|---|---|---|---|
| Blocker | 15m | 4h | 24x7 | SAME as default |
| High | 1h | 36h | Mon-Sat 10AM-8PM | SAME as default |
| Medium | 2h | 48h | Mon-Fri 10AM-8PM | SAME as default |
| Low | 4h | 72h | Mon-Fri 10AM-8PM | SAME as default |

**Action:** Zepto's contractual SLA matches the DevRev default almost exactly. No exception needed unless DevRev default changes.

**Note:** Despite matching the default, Zepto has financial penalties (3-10% monthly) tied to SLA performance >=85%. Track closely.

### ANC Delivers — Platinum Dedicated

**Accounts:** NOT FOUND in DevRev — needs account creation or mapping
**Uptime:** 99.6%
**Service Credits:** Liquidated damages for data breach/excessive downtime (sum TBC), +10% KPI bonus
**Source:** ANC Delivers _ Shipsy - OF.pdf, Annexure A + Appendix V

| Severity | First Response | Resolution | Schedule | vs Default |
|---|---|---|---|---|
| Blocker | 15m | 1h | 24x7 | Same resp, TIGHTER res (1h vs 4h) |
| High | 2h | 6h | 24x7 | LOOSER resp (2h vs 1h), TIGHTER res (6h vs 36h), WIDER hours |
| Medium | 4h | 12h | 24x7 | LOOSER resp (4h vs 2h), TIGHTER res (12h vs 48h), WIDER hours |
| Low | 8h | 16h | 24x7 | LOOSER resp (8h vs 4h), TIGHTER res (16h vs 72h), WIDER hours |

**Action:** Once ANC account exists in DevRev, create exception:
- Blocker: resp 15m, res **1h**, 24x7
- High: resp **2h**, res **6h**, **24x7**
- Medium: resp **4h**, res **12h**, **24x7**
- Low: resp **8h**, res **16h**, **24x7**

---

## Summary: Which Customers Need Exceptions?

| Customer | Exception Needed? | Key Difference from Default |
|---|---|---|
| DTDC | YES | Tighter resolution times across all tiers |
| RIL | NO | AMC-based, default is already stricter |
| Aramex | YES | Custom response times + 24x7 for High, service credits |
| Heineken | YES | Custom response times, 3-tier only |
| Flipkart | YES | Platinum: 30m P1 response, very tight resolution |
| ASDA | YES | Response-only SLA, service credits |
| Zepto | NO* | Matches default, but has financial penalties |
| ANC | YES* | Tightest resolution times (1h P1), all 24x7 |

*Zepto: monitor via CX Pulse (penalty tracking). ANC: needs DevRev account first.

## Next Steps

1. Create exceptions for DTDC, Aramex, Heineken, Flipkart, ASDA in DevRev UI
2. Create DevRev accounts for Zepto and ANC Delivers
3. Add ANC exception after account creation
4. Set up CX Pulse contractual SLA comparison (config/contractual-slas.json) for penalty-bearing customers
