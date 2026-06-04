#!/usr/bin/env python3
"""F.R.I.D.A.Y Impact Report — fetches DevRev data, computes Friday AI metrics.
Outputs JSON data file for the interactive dashboard.

Usage:
  python3 scripts/friday_report.py --days 30
  python3 scripts/friday_report.py --days 7
  python3 scripts/friday_report.py --from 2026-04-01 --to 2026-05-31
  python3 scripts/friday_report.py --days 7 --dry-run

Requires: DEVREV_TOKEN env var or .devrev_token file
"""

import json, os, sys, datetime, math, subprocess, argparse, time
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import median

# ═══ CONFIG ═══
def _load_token():
    t = os.environ.get("DEVREV_TOKEN", "").strip()
    if t:
        return t
    token_path = os.path.join(os.path.dirname(__file__), "..", ".devrev_token")
    try:
        with open(token_path) as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

TOKEN = _load_token()
API = "https://api.devrev.ai"
BASE_DIR = os.path.join(os.path.dirname(__file__), "..")

WMS_PODS = {"WMS Inbound", "WMS Outbound"}
EXCL_COHORTS = {"WMS", "Roadmap"}

ALIASES = {
    "reliance (ril)":"Reliance","ril":"Reliance","reliance":"Reliance","reliancehyperlocal":"Reliance",
    "ril-tira":"Reliance","1p jiomart reliance":"Reliance","reliance - 3p":"Reliance",
    "qwik logistics":"Reliance","rcpldemo":"Reliance",
    "dtdc":"DTDC","dtdc.in":"DTDC",
    "aramex global":"Aramex","aramex vw":"Aramex","aramex move":"Aramex",
    "aramex same day delivery":"Aramex","aramex ro":"Aramex","aramex oceania":"Aramex",
    "aramex freight":"Aramex","aramex":"Aramex","aramex sdd":"Aramex",
    "flipkart":"Flipkart","fkfooddemo":"Flipkart","fk food":"Flipkart","flipkartdropship":"Flipkart",
    "rozana":"Rozana","rozanaondemand":"Rozana",
    "wellness forever":"Wellness Forever","wellness forever (tms)":"Wellness Forever",
    "[wms] wellness forever":"Wellness Forever",
    "milkbasket":"Milkbasket","kama ayurveda":"Kama Ayurveda",
    "movin":"Movin","movin1demo":"Movin",
    "apollo247":"Apollo247","spencers":"Spencers",
    "hnk-br1-primary":"Heineken","hnk-br1-secondary":"Heineken","hnk-br1-support":"Heineken",
    "myntra":"Myntra","myntrahl":"Myntra","myntrahldemo":"Myntra",
    "swiggy":"Swiggy","swiggytms":"Swiggy",
    "proconnect":"Proconnect","proconnect account":"Proconnect",
    "wakefit":"Wakefit","wakefitdemo":"Wakefit",
    "box account":"Box","box":"Box",
    "expeditorsdemo":"Expeditors","expeditors":"Expeditors",
    "nxlogistics":"NX Logistics","caratlane":"CaratLane","sbt":"SBT",
    "healthkart":"Healthkart","zajel":"Zajel",
    "teleport":"Teleport","jeebly":"Jeebly","jeebly account":"Jeebly",
    "chronodiali":"Chronodiali","gmggroup":"GMG Group","gmggroup account":"GMG Group",
    "sugarcosmetics":"Sugar Cosmetics","visl":"VISL",
}

# ═══ HELPERS ═══
def norm(raw):
    if not raw or raw == "Unknown": return "Unknown"
    n = raw.strip()
    if n.endswith(" - Default Workspace"): n = n[:-20]
    if n.endswith(" Account"): n = n[:-8]
    return ALIASES.get(n.lower().strip(), n)

def apicall(endpoint, payload, _retries=3):
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(payload, f); f.flush(); tmppath = f.name
    try:
        for attempt in range(_retries):
            r = subprocess.run(["curl", "-s", "--compressed", "--retry", "1",
                "--max-time", "90", "-X", "POST", f"{API}/{endpoint}",
                "-H", f"Authorization: Bearer {TOKEN}",
                "-H", "Content-Type: application/json",
                "-d", f"@{tmppath}"], capture_output=True, text=True, timeout=120)
            if not r.stdout.strip():
                if attempt < _retries - 1: time.sleep(1); continue
                raise RuntimeError(f"curl returned empty (rc={r.returncode})")
            try:
                return json.loads(r.stdout, strict=False)
            except json.JSONDecodeError:
                if attempt < _retries - 1: time.sleep(1); continue
                raise
    finally:
        os.unlink(tmppath)

def is_support(t):
    if t.get("subtype") != "Support": return False
    cohort = t.get("custom_fields", {}).get("tnt__customer_cohort_dropdown", "") or "TBD"
    if cohort in EXCL_COHORTS: return False
    if t.get("custom_fields", {}).get("tnt__pod", "") in WMS_PODS: return False
    return True

def acct(t): return norm((t.get("rev_org") or {}).get("display_name", "Unknown"))
def cohort(t): return t.get("custom_fields", {}).get("tnt__customer_cohort_dropdown", "TBD") or "TBD"
def sev(t): return (t.get("severity") or "?").lower()
def stg(t): return t.get("stage", {}).get("name", "?")

def parse_dt(s):
    if not s: return None
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except:
        return None


# ═══ FRIDAY TIMELINE CHECK (expanded) ═══
def check_friday_detail(ticket):
    """Check if Friday AI analyzed this ticket. Returns dict with details."""
    tid = ticket.get("display_id", "?")
    result = {
        "ticket": tid,
        "has_rca": False,
        "has_fr_draft": False,
        "rca_timestamp": None,
        "rca_seconds": None,
        "rca_snippet": "",
    }
    try:
        r = apicall("timeline-entries.list", {"object": ticket["id"], "limit": 50})
        ticket_created = parse_dt(ticket.get("created_date", ""))
        for e in r.get("timeline_entries", []):
            if e.get("type") != "timeline_comment": continue
            author = (e.get("created_by") or {}).get("display_name", "")
            author_id = (e.get("created_by") or {}).get("id", "")
            # Friday = DEVU-2940 or display_name contains "friday"
            if "friday" not in author.lower() and "devu/2940" not in author_id:
                continue
            result["has_rca"] = True
            comment_dt = parse_dt(e.get("created_date", ""))
            result["rca_timestamp"] = e.get("created_date", "")
            if ticket_created and comment_dt:
                result["rca_seconds"] = int((comment_dt - ticket_created).total_seconds())
            body = e.get("body", "") or ""
            if len(body) > 300:
                result["rca_snippet"] = body[:300]
            else:
                result["rca_snippet"] = body
            # Check for FR draft markers
            if "suggested first response" in body.lower() or "customer-facing" in body.lower() or "draft response" in body.lower():
                result["has_fr_draft"] = True
            break  # take the first Friday comment
    except Exception as ex:
        print(f"  Warning: timeline check failed for {tid}: {ex}", file=sys.stderr)
    return result


# ═══ MAIN ═══
def main():
    parser = argparse.ArgumentParser(description="F.R.I.D.A.Y Impact Report")
    parser.add_argument("--days", type=int, default=30, help="Number of days to analyze (default: 30)")
    parser.add_argument("--from-date", dest="from_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to-date", dest="to_date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Compute but don't save files")
    parser.add_argument("--skip-timeline", action="store_true", help="Skip timeline checks (fast mode, no Friday data)")
    args = parser.parse_args()

    if not TOKEN:
        print("ERROR: Set DEVREV_TOKEN env var or create .devrev_token file", file=sys.stderr)
        sys.exit(1)

    today = datetime.date.today()
    if args.from_date and args.to_date:
        date_from = datetime.date.fromisoformat(args.from_date)
        date_to = datetime.date.fromisoformat(args.to_date)
    else:
        date_to = today
        date_from = today - datetime.timedelta(days=args.days)

    days_count = (date_to - date_from).days
    from_iso = date_from.isoformat()
    to_iso = date_to.isoformat()
    print(f"F.R.I.D.A.Y Report: {from_iso} to {to_iso} ({days_count} days)", file=sys.stderr)

    # ═══ STEP 1: FETCH ALL TICKETS IN DATE RANGE ═══
    print("Step 1: Fetching tickets...", file=sys.stderr)

    # Fetch open/in_progress tickets
    raw_open = []; cur = None; pg = 0
    while True:
        pg += 1
        p = {"type": ["ticket"], "state": ["open", "in_progress"], "limit": 50}
        if cur: p["cursor"] = cur
        r = apicall("works.list", p)
        w = r.get("works", []); raw_open.extend(w); cur = r.get("next_cursor", "")
        if not w or not cur: break
        if pg > 300: break
    print(f"  Open/InProgress raw: {len(raw_open)} ({pg} pages)", file=sys.stderr)

    # Fetch resolved/closed tickets
    raw_closed = []; cur = None; pg = 0
    while True:
        pg += 1
        p = {"type": ["ticket"], "state": ["resolved", "closed"], "limit": 50}
        if cur: p["cursor"] = cur
        r = apicall("works.list", p)
        w = r.get("works", []); raw_closed.extend(w); cur = r.get("next_cursor", "")
        if not w or not cur: break
        # Stop if we've gone past our date range
        if w[-1].get("modified_date", "")[:10] < from_iso: break
        if pg > 500: break
    print(f"  Resolved/Closed raw: {len(raw_closed)} ({pg} pages)", file=sys.stderr)

    # Filter to support tickets created in date range
    all_raw = raw_open + raw_closed
    tickets_in_range = []
    seen_ids = set()
    for t in all_raw:
        did = t.get("display_id", "")
        if did in seen_ids: continue
        seen_ids.add(did)
        if not is_support(t): continue
        created = t.get("created_date", "")[:10]
        if created < from_iso or created > to_iso: continue
        if stg(t) == "canceled": continue
        tickets_in_range.append(t)

    total_tickets = len(tickets_in_range)
    print(f"  Support tickets in range: {total_tickets}", file=sys.stderr)

    # ═══ STEP 2: CHECK FRIDAY TIMELINE FOR EACH TICKET ═══
    friday_results = []
    if not args.skip_timeline:
        print(f"Step 2: Checking Friday comments ({total_tickets} tickets, 10 threads)...", file=sys.stderr)
        done = 0
        with ThreadPoolExecutor(max_workers=10) as pool:
            futs = {pool.submit(check_friday_detail, t): t for t in tickets_in_range}
            for f in as_completed(futs):
                friday_results.append((futs[f], f.result()))
                done += 1
                if done % 50 == 0:
                    print(f"  ... {done}/{total_tickets}", file=sys.stderr)
        print(f"  Timeline checks complete: {done}", file=sys.stderr)
    else:
        print("Step 2: SKIPPED (--skip-timeline)", file=sys.stderr)
        friday_results = [(t, {"ticket": t.get("display_id","?"), "has_rca": False, "has_fr_draft": False,
                                "rca_timestamp": None, "rca_seconds": None, "rca_snippet": ""})
                          for t in tickets_in_range]

    # ═══ STEP 3: COMPUTE METRICS ═══
    print("Step 3: Computing metrics...", file=sys.stderr)

    # Classify tickets
    with_rca = [(t, fr) for t, fr in friday_results if fr["has_rca"]]
    with_fr_draft = [(t, fr) for t, fr in friday_results if fr["has_fr_draft"]]
    without_friday = [(t, fr) for t, fr in friday_results if not fr["has_rca"]]

    friday_runs = len(with_rca)
    rca_count = friday_runs
    fr_draft_count = len(with_fr_draft)
    coverage_pct = round(friday_runs / total_tickets * 100, 1) if total_tickets > 0 else 0

    # Timing
    timing_samples = []
    for t, fr in with_rca:
        # Only include timing between 30s and 3600s (1 hour)
        # Shorter = likely timestamp noise, longer = retroactive analysis on old ticket
        if fr["rca_seconds"] is not None and 30 <= fr["rca_seconds"] <= 3600:
            timing_samples.append({"ticket": fr["ticket"], "seconds": fr["rca_seconds"]})

    timing_samples.sort(key=lambda x: x["seconds"])
    timing_seconds = [s["seconds"] for s in timing_samples]

    timing_stats = {}
    if timing_seconds:
        timing_stats = {
            "median_seconds": int(median(timing_seconds)),
            "avg_seconds": int(sum(timing_seconds) / len(timing_seconds)),
            "min_seconds": min(timing_seconds),
            "max_seconds": max(timing_seconds),
            "count": len(timing_seconds),
            "distribution": {
                "under_2m": len([s for s in timing_seconds if s < 120]),
                "2_5m": len([s for s in timing_seconds if 120 <= s < 300]),
                "5_10m": len([s for s in timing_seconds if 300 <= s < 600]),
                "10_15m": len([s for s in timing_seconds if 600 <= s < 900]),
                "over_15m": len([s for s in timing_seconds if s >= 900]),
            },
            "samples": timing_samples[:100],  # cap at 100 samples for JSON size
        }

    # Org breakdown
    org_counter = defaultdict(lambda: {"total": 0, "rca": 0, "rca_fr": 0, "no_friday": 0, "cohort": "TBD"})
    for t, fr in friday_results:
        org_name = acct(t)
        org_counter[org_name]["total"] += 1
        org_counter[org_name]["cohort"] = cohort(t)
        if fr["has_fr_draft"]:
            org_counter[org_name]["rca_fr"] += 1
        elif fr["has_rca"]:
            org_counter[org_name]["rca"] += 1
        else:
            org_counter[org_name]["no_friday"] += 1

    orgs_list = sorted(
        [{"org": k, "cohort": v["cohort"], "total": v["total"], "rca_fr": v["rca_fr"],
          "rca": v["rca"], "no_friday": v["no_friday"]}
         for k, v in org_counter.items()],
        key=lambda x: -x["total"]
    )

    # Daily breakdown
    daily_counter = defaultdict(lambda: {"total": 0, "rca": 0, "rca_fr": 0, "no_friday": 0})
    for t, fr in friday_results:
        day = t.get("created_date", "")[:10]
        daily_counter[day]["total"] += 1
        if fr["has_fr_draft"]:
            daily_counter[day]["rca_fr"] += 1
        elif fr["has_rca"]:
            daily_counter[day]["rca"] += 1
        else:
            daily_counter[day]["no_friday"] += 1

    daily_list = sorted(
        [{"date": k, **v} for k, v in daily_counter.items()],
        key=lambda x: x["date"]
    )

    # ═══ IMPACT: WITH FRIDAY vs WITHOUT ═══
    print("Step 4: Computing impact...", file=sys.stderr)

    def compute_resolution_stats(ticket_list):
        """Compute avg resolution hours and SLA hit rates for a list of tickets."""
        resolution_hours = []
        fr_hits = 0; fr_total = 0
        rt_hits = 0; rt_total = 0
        for t in ticket_list:
            # Resolution time
            cr = parse_dt(t.get("created_date", ""))
            cl = parse_dt(t.get("actual_close_date", ""))
            if cr and cl:
                h = (cl - cr).total_seconds() / 3600
                if 0 < h < 720:  # cap at 30 days
                    resolution_hours.append(h)
            # SLA from sla_tracker
            sla = t.get("sla_summary", {}); tr = sla.get("sla_tracker", {})
            for m in tr.get("metric_target_summaries", []):
                nm = m.get("metric_definition", {}).get("name", ""); st = m.get("status", "")
                if "First" in nm and st in ("hit", "miss"):
                    fr_total += 1
                    if st == "hit": fr_hits += 1
                elif "Resolution" in nm and st in ("hit", "miss"):
                    rt_total += 1
                    if st == "hit": rt_hits += 1
        avg_hours = round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else None
        med_hours = round(median(sorted(resolution_hours)), 1) if resolution_hours else None
        fr_pct = round(fr_hits / fr_total * 100, 1) if fr_total > 0 else None
        rt_pct = round(rt_hits / rt_total * 100, 1) if rt_total > 0 else None
        return {
            "count": len(ticket_list),
            "resolved_count": len(resolution_hours),
            "avg_resolution_hours": avg_hours,
            "median_resolution_hours": med_hours,
            "fr_sla_hit_pct": fr_pct,
            "rt_sla_hit_pct": rt_pct,
        }

    # Only compare resolved tickets
    resolved_with_friday = [t for t, fr in with_rca
                            if stg(t).lower() in ("resolved", "closed")]
    resolved_without_friday = [t for t, fr in without_friday
                               if stg(t).lower() in ("resolved", "closed")]

    impact_with = compute_resolution_stats(resolved_with_friday)
    impact_without = compute_resolution_stats(resolved_without_friday)

    # Compute improvement
    improvement = {}
    if impact_with["avg_resolution_hours"] and impact_without["avg_resolution_hours"]:
        if impact_with["avg_resolution_hours"] > 0:
            speedup = round(impact_without["avg_resolution_hours"] / impact_with["avg_resolution_hours"], 1)
            improvement["resolution_speedup"] = f"{speedup}x"
        else:
            improvement["resolution_speedup"] = "N/A"
    if impact_with["fr_sla_hit_pct"] is not None and impact_without["fr_sla_hit_pct"] is not None:
        delta = round(impact_with["fr_sla_hit_pct"] - impact_without["fr_sla_hit_pct"], 1)
        improvement["sla_improvement"] = f"+{delta}pp" if delta > 0 else f"{delta}pp"

    # ═══ STEP 4b: PER-TICKET SLA DATA (for client-side filtering) ═══
    print("Step 4b: Building per-ticket SLA data...", file=sys.stderr)

    # Determine friday-eligible orgs (orgs with at least one Friday run)
    friday_orgs = set()
    for t, fr in friday_results:
        if fr["has_rca"]:
            friday_orgs.add(acct(t))

    sla_tickets = []
    for t, fr in friday_results:
        # Determine bucket
        if fr["has_fr_draft"]:
            bucket = "success_with_fr"
        elif fr["has_rca"]:
            bucket = "success_no_fr"
        else:
            bucket = "no_run"

        # Extract SLA metrics
        fr_st = None; fr_c = None; res_st = None; res_c = None
        sla = t.get("sla_summary", {}); tr = sla.get("sla_tracker", {})
        for m in tr.get("metric_target_summaries", []):
            nm = m.get("metric_definition", {}).get("name", ""); st = m.get("status", "")
            completion = m.get("completed_in")
            if "First" in nm:
                if st in ("hit", "miss", "in_progress"):
                    fr_st = st
                    if completion is not None:
                        fr_c = round(completion)
            elif "Resolution" in nm:
                if st in ("hit", "miss", "in_progress"):
                    res_st = st
                    if completion is not None:
                        res_c = round(completion)

        org_name = acct(t)
        rb = t.get("custom_fields", {}).get("tnt__resolved_by", "") or ""
        severity = (t.get("severity") or "Medium").capitalize()

        sla_tickets.append({
            "tkt": t.get("display_id", "?"),
            "bucket": bucket,
            "sev": severity,
            "rb": rb,
            "fr_st": fr_st,
            "fr_c": fr_c,
            "res_st": res_st,
            "res_c": res_c,
            "org": org_name,
            "fe": org_name in friday_orgs,
        })

    # ═══ STEP 5: TRENDS ═══
    print("Step 5: Computing trends...", file=sys.stderr)

    # Weekly breakdown for trends
    weekly = defaultdict(lambda: {"total": 0, "friday": 0, "rca_fr": 0, "timing_sum": 0, "timing_count": 0})
    for t, fr in friday_results:
        created = t.get("created_date", "")[:10]
        try:
            d = datetime.date.fromisoformat(created)
            week = d.isocalendar()
            week_label = f"{week.year}-W{week.week:02d}"
        except:
            continue
        weekly[week_label]["total"] += 1
        if fr["has_rca"]:
            weekly[week_label]["friday"] += 1
        if fr["has_fr_draft"]:
            weekly[week_label]["rca_fr"] += 1
        if fr["rca_seconds"] and fr["rca_seconds"] > 0:
            weekly[week_label]["timing_sum"] += fr["rca_seconds"]
            weekly[week_label]["timing_count"] += 1

    trends = sorted([
        {
            "week": k,
            "total": v["total"],
            "friday_runs": v["friday"],
            "coverage_pct": round(v["friday"] / v["total"] * 100, 1) if v["total"] > 0 else 0,
            "rca_fr": v["rca_fr"],
            "avg_timing_sec": round(v["timing_sum"] / v["timing_count"]) if v["timing_count"] > 0 else None,
        }
        for k, v in weekly.items()
    ], key=lambda x: x["week"])

    # ═══ STEP 6: BUILD OUTPUT JSON ═══
    print("Step 6: Building output...", file=sys.stderr)

    report = {
        "generated_at": datetime.datetime.now().isoformat(),
        "period": {"from": from_iso, "to": to_iso, "days": days_count},
        "kpis": {
            "total_tickets": total_tickets,
            "friday_runs": friday_runs,
            "coverage_pct": coverage_pct,
            "rca_count": rca_count,
            "fr_draft_count": fr_draft_count,
            "rca_only_count": rca_count - fr_draft_count,
            "no_friday_count": len(without_friday),
        },
        "timing": timing_stats,
        "orgs": orgs_list,
        "daily": daily_list,
        "impact": {
            "with_friday": impact_with,
            "without_friday": impact_without,
            "improvement": improvement,
        },
        "sla_tickets": sla_tickets,
        "trends": trends,
    }

    # ═══ STEP 7: SAVE ═══
    if args.dry_run:
        print("\n--- DRY RUN: JSON output ---", file=sys.stderr)
        print(json.dumps(report, indent=2))
    else:
        # Save report data as JS module for dashboard
        data_path = os.path.join(BASE_DIR, "config", "friday-report-data.js")
        with open(data_path, "w") as f:
            f.write("// Auto-generated by friday_report.py — do not edit\n")
            f.write(f"// Generated: {report['generated_at']}\n")
            f.write(f"const REPORT_DATA = {json.dumps(report, indent=2)};\n")
        print(f"  Saved: {data_path}", file=sys.stderr)

        # Also save raw JSON
        json_path = os.path.join(BASE_DIR, "config", "friday-report-data.json")
        with open(json_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"  Saved: {json_path}", file=sys.stderr)

        # Append to trend history
        history_path = os.path.join(BASE_DIR, "config", "friday-trend-history.json")
        history = []
        try:
            with open(history_path) as f:
                history = json.load(f)
        except:
            pass

        history.append({
            "generated_at": report["generated_at"],
            "period": report["period"],
            "coverage_pct": coverage_pct,
            "friday_runs": friday_runs,
            "total_tickets": total_tickets,
            "rca_count": rca_count,
            "fr_draft_count": fr_draft_count,
            "avg_timing_sec": timing_stats.get("avg_seconds"),
            "median_timing_sec": timing_stats.get("median_seconds"),
            "impact_speedup": improvement.get("resolution_speedup"),
        })
        with open(history_path, "w") as f:
            json.dump(history, f, indent=2)
        print(f"  Saved: {history_path}", file=sys.stderr)

    # Print summary to stdout (for Slack posting via trigger)
    print(f"""F.R.I.D.A.Y Report | {from_iso} to {to_iso} ({days_count}d)

Coverage:   {coverage_pct}% ({friday_runs}/{total_tickets} tickets)
RCA + FR:   {fr_draft_count}
RCA Only:   {rca_count - fr_draft_count}
No Friday:  {len(without_friday)}""")

    if timing_stats:
        print(f"""
Timing (n={timing_stats['count']}):
  Median:  {timing_stats['median_seconds']}s ({timing_stats['median_seconds']/60:.1f} min)
  Average: {timing_stats['avg_seconds']}s ({timing_stats['avg_seconds']/60:.1f} min)
  Fastest: {timing_stats['min_seconds']}s
  Slowest: {timing_stats['max_seconds']}s""")

    if impact_with["avg_resolution_hours"] and impact_without["avg_resolution_hours"]:
        print(f"""
Impact:
  With Friday:    avg resolution {impact_with['avg_resolution_hours']}h | FR SLA {impact_with.get('fr_sla_hit_pct','?')}%
  Without Friday: avg resolution {impact_without['avg_resolution_hours']}h | FR SLA {impact_without.get('fr_sla_hit_pct','?')}%
  Speedup:        {improvement.get('resolution_speedup', '?')} faster with Friday""")

    top5 = [f"{o['org']} ({o['total']})" for o in orgs_list[:5]]
    print(f"\nTop orgs: {', '.join(top5)}")

    print(f"\nDone.", file=sys.stderr)


if __name__ == "__main__":
    main()
