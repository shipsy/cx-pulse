# Support Ticket Status Redesign — Suggestions
For discussion: Gaurav, Pushkar, Dhruv

## Starting point

The proposal gets the hard parts right. The core principle — status describes the work, owner describes who holds it — is exactly where every mature support system has landed (ITIL v4, ServiceNow, Zendesk, Jira SM all converge here). The three field-level changes (Resolution Type, severity-gated RCA, Pending On person-picker) are genuinely strong additions. These notes are suggestions on top of that foundation.

---

## Suggestion 1 — Add an entry state

The proposal starts at "Investigating." Every major platform has a pre-work state for tickets that have arrived but nobody has looked at yet:

| Platform | Entry State |
|----------|------------|
| ServiceNow | New |
| Zendesk | New |
| Jira SM | Open |
| Freshdesk | Open |
| Current DevRev | Queued |

Without it, we can't measure First Response SLA (time from creation to first agent action) or distinguish "nobody has seen this" from "actively working." Suggest keeping **New** or **Queued** as the first status.

---

## Suggestion 2 — Consider merging Investigating + Fix In Progress

The split makes intuitive sense, but most platforms use a single active-work status:

| Platform | Active work statuses |
|----------|---------------------|
| ServiceNow | In Progress (one) |
| Zendesk | Open (one) |
| JSM | In Progress (one) |
| Freshdesk | Open (one) |

The concern: agents often investigate and fix simultaneously. If they don't bother updating mid-ticket, the data becomes unreliable and we've added cognitive overhead for no signal.

A possible middle path: single **In Progress** status with an optional `work_phase` dropdown (Investigating / Implementing / Testing). Agents who want to signal where they are can; it's not mandatory. We get the data option without forcing the behaviour.

If the team feels strongly about the split — totally workable, just worth knowing the data quality will be approximate.

---

## Suggestion 3 — Define the Reopen lifecycle

The proposal doesn't mention how reopens work. The current system has "Reopen" as a status. Industry consensus leans toward making reopen a **transition**, not a status:

- Zendesk: customer reply on a Solved ticket moves it back to Open. A `reopen_count` field tracks it.
- ServiceNow: ticket goes back to In Progress with a `reopened` flag.

Suggestion: when a customer responds to a Resolved ticket, transition it back to In Progress (or Investigating). Increment a `reopen_count` field. Start a fresh SLA clock for the reopened segment. This keeps the workflow clean and gives us reopen rate as a quality metric (industry target: <10%).

---

## Suggestion 4 — Make the two-step close explicit

The proposal has "Resolved" under the Closed group but doesn't mention a separate locked terminal state. Nearly every platform uses a two-step pattern:

| Platform | Pattern | Auto-close timer |
|----------|---------|-----------------|
| ServiceNow | Resolved → Closed | 3–5 business days |
| Zendesk | Solved → Closed | 4–28 days |
| Freshdesk | Resolved → Closed | 48 hours |

Why it matters: the customer gets a grace window to say "not fixed." After the timer, the record locks and can't be edited — protecting SLA data integrity. Reopens during the grace period go back to In Progress.

Suggestion: keep **Resolved** as agent-set, add **Closed** as an auto-transition after ~5 business days. Agents never manually pick "Closed" — it happens on its own.

This also answers the "Accepted" open question: if Accepted meant "customer confirmed," the auto-close timer handles it. Silence = consent is the industry default.

---

## Suggestion 5 — Specify SLA clock behaviour per status

The proposal doesn't define which statuses pause, run, or stop the SLA clock. This is worth settling upfront. A possible mapping:

| Status | Resolution SLA | Rationale |
|--------|---------------|-----------|
| New / Queued | Running | We own triage |
| In Progress | Running | We're working |
| In Verification | Running | Still our responsibility |
| Awaiting Customer | **Paused** | Customer owns the delay |
| Awaiting Internal Input | **Running** | Still within our org |
| Blocked – External | **Paused** | Genuinely outside our control |
| Resolved | Stopped | Resolution delivered |

The debatable one is Awaiting Internal Input. Pausing SLA there is tempting, but keeping it running creates accountability — the support agent stays motivated to chase engineering rather than park and forget. We can still measure internal wait time separately through the Pending On field without affecting SLA.

---

## Suggestion 6 — Expand Resolution Type slightly

The proposal has Permanent Fix vs Workaround. Suggest adding a few more values — the difference between "we fixed a bug" and "we taught the customer how to use the feature" matters for Product:

| Resolution Type | Meaning |
|----------------|---------|
| Permanent Fix | Root cause eliminated |
| Workaround | Service restored, root cause remains → linked Problem required |
| Configuration Change | Ops/admin change, not code |
| Customer Education | Not a defect; user needed guidance |
| Cannot Reproduce | Could not replicate |
| Duplicate | Same as another ticket → link required |
| By Design | Working as intended |
| Third-Party Resolution | Fixed by vendor/partner |

High "Customer Education" volumes on a feature = UX gap signal. High "Configuration Change" = operational fragility. These feed different improvement loops.

Similarly, for **Closed – No Action**, a `closure_reason` sub-field (By Design / Duplicate / Info Only / Self-Resolved / No Response) would capture why no action was needed without adding more statuses.

---

## Suggestion 7 — A few guard rails

Three operational controls worth building in from day one:

1. **Blocked – External**: make `vendor_name` required (not optional). Set a max pause: SLA resumes after 5 business days regardless. Agent must follow up every 48 hours.

2. **Awaiting Internal Input**: auto-escalate if ticket sits in Pending On for >48 business hours without activity. Stale internal waits are the #1 SLA killer.

3. **Awaiting Customer**: auto-nudge the agent after 3 business days. Customers forget; the agent's job is to chase.

---

## Suggested final model

Incorporating the above, this is what the status list could look like:

| # | Status | Group | SLA | Owner |
|---|--------|-------|-----|-------|
| 1 | **New** | Open | Running | Queue / unassigned |
| 2 | **In Progress** | Active | Running | Assigned agent |
| 3 | **In Verification** | Active | Running | Support agent validates fix |
| 4 | **Awaiting Customer** | Waiting | Paused | Customer has next action |
| 5 | **Awaiting Internal Input** | Waiting | Running | Pending On person |
| 6 | **Blocked – External** | Waiting | Paused | Vendor/partner |
| 7 | **Resolved** | Closed | Stopped | Grace period (auto-closes) |
| 8 | **Closed** | Terminal | Stopped | Auto from Resolved, 5 days |
| 9 | **Closed – No Action** | Terminal | Stopped | Valid but no fix needed |
| 10 | **Canceled** | Terminal | Stopped | Withdrawn / error |

Agents interact with statuses 1–7. Statuses 8–10 are terminal. The effective agent workflow is **7 statuses** — right at the industry sweet spot.

If the team prefers keeping Investigating + Fix In Progress as separate statuses (from the original proposal), the count goes to 11 with 8 agent-managed. Still reasonable.

---

## Mapping: current → new

| Current (12 statuses) | Maps to |
|-----------------------|---------|
| Queued | New |
| Reopen | In Progress (+ set `reopen_count`) |
| Work In Progress | In Progress |
| In Development | In Progress |
| Awaiting Development | Awaiting Internal Input |
| Awaiting Product Assist | Awaiting Internal Input |
| Awaiting Customer Response | Awaiting Customer |
| Reassigned to Customer Support | In Verification |
| Resolved | Resolved |
| Accepted | Resolved |
| Canceled | Canceled |
| Closed | Closed |

---

## What this unlocks

| Metric | How | Not possible today |
|--------|-----|--------------------|
| Internal bottleneck heatmap | `pending_on` across Awaiting Internal Input tickets | No structured data on who blocks whom |
| Workaround debt | Resolved + resolution_type = Workaround, no linked Problem | No permanence tracking |
| Vendor exposure | Time in Blocked – External by vendor | No vendor-wait visibility |
| Resolution quality | Reopen rate by agent, cohort, pod | Reopen is a status, not a measurable event |
| Closure composition | resolution_type distribution | Only free-text `tnt__resolution` today |
| RCA coverage | % of Sev-1 with root_cause filled | No severity-gated enforcement |

---

These are just suggestions building on a solid proposal. Happy to discuss any of these in more detail.
