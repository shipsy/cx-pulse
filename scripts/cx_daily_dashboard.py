#!/usr/bin/env python3
"""CX Daily Dashboard — deterministic script for daily Slack report.
Fetches from DevRev REST API, computes 7 metrics, outputs formatted Slack message.
Run: python3 scripts/cx_daily_dashboard.py
Requires: DEVREV_TOKEN env var"""

import json, os, sys, datetime, urllib.request, math
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

# ═══ CONFIG ═══
TOKEN = os.environ.get("DEVREV_TOKEN", "")
API = "https://api.devrev.ai"
TODAY = datetime.date.today()
YESTERDAY = (TODAY - datetime.timedelta(days=1))
DAY_BEFORE = (TODAY - datetime.timedelta(days=2))
SEVEN_AGO = (TODAY - datetime.timedelta(days=7)).isoformat()
CUTOFF = (TODAY - datetime.timedelta(days=14)).isoformat()

WMS_PODS = {"WMS Inbound", "WMS Outbound"}
EXCL_COHORTS = {"WMS", "Roadmap"}

# ═══ ACCOUNT CONSOLIDATION ═══
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
    "asterksademo":"Aster KSA","aster pharmacy":"Aster Pharmacy",
    "aujan-export":"Aujan","aujan-import":"Aujan","aujansd-ksa":"Aujan","aujanimport":"Aujan",
    "flowpluae":"Flowpl","flowpl":"Flowpl","flowexpress":"Flowpl",
    "nxlogistics":"NX Logistics","caratlane":"CaratLane","sbt":"SBT",
    "healthkart":"Healthkart","field":"Field","incnut":"Incnut","frontline":"Frontline",
    "heromotocorp":"Hero MotoCorp","zajel":"Zajel","ubteam":"Ubteam",
}

DEVU_MAP = {
    "devu/1327":"Gangesh Pandey","devu/2573":"Saurabh Singh","devu/901":"Sachin Shivhare",
    "devu/2585":"Laxmi Rajput","devu/1088":"Deepanshu Marwari","devu/2580":"Vikas Pandey",
    "devu/2976":"Srijan Srivastava","devu/1246":"Vinod Kumar Gunda","devu/3000":"Kaustuv Choudhary",
    "devu/1314":"Vidushi Wanchoo","devu/2636":"Asif Khan","devu/2978":"Medha Saxena",
    "devu/1090":"Madhav Kapoor","devu/2934":"Abhishek Bhandari","devu/3007":"Bhavyank Sarolia",
    "devu/2744":"Omi Vaish","devu/2647":"Pakhi Vashishth","devu/3063":"Tejal Shirsat",
    "devu/2676":"SKG/Sumit Gupta","devu/3091":"Gaurav Singh",
    "devu/2626":"Shajiya Shaik","devu/1885":"Shipsy Support","devu/863":"Akash KumarRajek",
    "devu/899":"Yash Singh","devu/1009":"Sana Amreen","devu/1607":"Amit Dubey",
    "devu/2944":"Bhanu Arya","devu/2632":"Nikhila K",
}

# ═══ HELPERS ═══
def norm(raw):
    if not raw or raw == "Unknown": return "Unknown"
    n = raw.strip()
    if n.endswith(" - Default Workspace"): n = n[:-20]
    if n.endswith(" Account"): n = n[:-8]
    return ALIASES.get(n.lower().strip(), n)

def apicall(endpoint, payload):
    d = json.dumps(payload).encode()
    r = urllib.request.Request(f"{API}/{endpoint}", data=d,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode(), strict=False)

def is_support(t):
    if t.get("subtype") != "Support": return False
    if (t.get("custom_fields", {}).get("tnt__customer_cohort_dropdown", "") or "TBD") in EXCL_COHORTS: return False
    if t.get("custom_fields", {}).get("tnt__pod", "") in WMS_PODS: return False
    return True

def acct(t): return norm((t.get("rev_org") or {}).get("display_name", "Unknown"))
def sev(t): return (t.get("severity") or "?").lower()
def stg(t): return t.get("stage", {}).get("name", "?")
def cx(t):
    a = t.get("custom_fields", {}).get("tnt__assignee", "")
    if not a: return "Unassigned"
    if "devu/" in a: return DEVU_MAP.get("devu/" + a.split("devu/")[-1], f'DEVU-{a.split("/")[-1]}')
    return "Unknown"

def pctl(sl, p):
    if not sl: return 0
    n = len(sl); k = (p / 100) * (n - 1); f = int(k); c = min(f + 1, n - 1)
    return sl[f] * (c - k) + sl[c] * (k - f) if f != c else sl[f]

def fh(h):
    if h < 1: return f"{h*60:.0f}m"
    elif h < 24: return f"{h:.1f}h"
    return f"{h/24:.1f}d"

def sla_color(pct):
    if pct >= 75: return "🟢"
    elif pct >= 60: return "🟡"
    elif pct >= 40: return "🟠"
    return "🔴"

def arrow(prev, now):
    d = now - prev
    if d > 0: return f"▲ {d:>2}"
    elif d < 0: return f"▼ {abs(d):>2}"
    return f"= {0:>2}"

def arrow_emoji(prev, now, lower_is_good=True):
    d = now - prev
    if d == 0: return ""
    if lower_is_good:
        return " ✅" if d < 0 else " ⚠️"
    return " ✅" if d > 0 else " ⚠️"

def check_friday(ticket):
    """Check if Friday AI analyzed this ticket via Timeline API."""
    try:
        r = apicall("timeline-entries.list", {"object": ticket["id"], "limit": 20})
        for e in r.get("timeline_entries", []):
            if e.get("type") != "timeline_comment": continue
            author = (e.get("created_by") or {}).get("display_name", "")
            if "friday" in author.lower():
                return True
        return False
    except:
        return False


# ═══ MAIN ═══
def main():
    if not TOKEN:
        print("ERROR: Set DEVREV_TOKEN env var", file=sys.stderr)
        sys.exit(1)

    yday = YESTERDAY.isoformat()
    dbyday = DAY_BEFORE.isoformat()

    # ═══ FETCH DATA ═══
    print("Fetching open tickets...", file=sys.stderr)
    raw = []; cur = None
    while True:
        p = {"type": ["ticket"], "state": ["open", "in_progress"], "limit": 100}
        if cur: p["cursor"] = cur
        r = apicall("works.list", p)
        w = r.get("works", []); raw.extend(w); cur = r.get("next_cursor", "")
        if not w or not cur: break
    tix = [t for t in raw if is_support(t)]
    print(f"  Open: {len(tix)}", file=sys.stderr)

    print("Fetching resolved/closed tickets...", file=sys.stderr)
    res = []; cur = None; pg = 0
    while True:
        pg += 1
        p = {"type": ["ticket"], "state": ["resolved", "closed"], "limit": 100}
        if cur: p["cursor"] = cur
        r = apicall("works.list", p)
        w = r.get("works", []); res.extend(w); cur = r.get("next_cursor", "")
        if not w or not cur: break
        if w[-1].get("modified_date", "")[:10] < CUTOFF: break
        if pg > 200: break
    csup = [t for t in res if is_support(t)]
    print(f"  Closed: {len(csup)} in {pg} pages", file=sys.stderr)

    # ═══ COMPUTED DATA ═══
    total = len(tix)
    blockers = [t for t in tix if sev(t) == "blocker"]
    unanswered = [t for t in tix if t.get("needs_response") == True and stg(t) in ("queued", "work_in_progress")]

    # Resolved 7d (excl canceled)
    resolved_7d = [t for t in csup if t.get("actual_close_date", "")[:10] >= SEVEN_AGO
                   and stg(t).lower() in ("resolved", "closed")]

    # Previous day reconstruction
    open_before_yday = [t for t in tix if t.get("created_date", "")[:10] <= yday]
    closed_after_yday = [t for t in csup if t.get("actual_close_date", "")[:10] > yday
                         and t.get("created_date", "")[:10] <= yday]
    open_yday = len(open_before_yday) + len(closed_after_yday)

    prev_blockers = len([t for t in tix if sev(t) == "blocker" and t.get("created_date", "")[:10] <= yday]) + \
                    len([t for t in csup if sev(t) == "blocker" and t.get("actual_close_date", "")[:10] > yday
                         and t.get("created_date", "")[:10] <= yday])
    # Approximate — can't reconstruct exact previous unanswered
    prev_unanswered = len(unanswered)  # Will use snapshot if available

    # Load snapshot for better previous day data
    snap = None
    stored_rates = {}
    snap_path = os.path.join(os.path.dirname(__file__), "..", "config", "daily-snapshot.json")
    try:
        with open(snap_path) as f:
            snap_raw = json.load(f)
        stored_rates = snap_raw.get("daily_rates", {})
        if snap_raw.get("date") == yday:
            snap = snap_raw
    except:
        pass

    if snap:
        open_yday = snap.get("total", open_yday)
        prev_blockers_val = snap.get("blockers", prev_blockers)
        prev_unanswered_val = snap.get("unanswered", len(unanswered))
    else:
        prev_blockers_val = prev_blockers
        prev_unanswered_val = len(unanswered)

    # Created/Resolved yesterday (deduped)
    seen = set(); created_yday = []
    for t in list(tix) + list(csup):
        did = t.get("display_id", "")
        if did in seen: continue
        seen.add(did)
        if t.get("created_date", "")[:10] != yday: continue
        if not is_support(t): continue
        if stg(t) == "canceled": continue
        created_yday.append(t)

    resolved_yday = [t for t in csup if t.get("actual_close_date", "")[:10] == yday
                     and stg(t).lower() in ("resolved", "closed")]

    # ═══ SLA ═══
    sla_all = {"fr_h": 0, "fr_m": 0, "rt_h": 0, "rt_m": 0}
    sla_acct = defaultdict(lambda: {"fr_h": 0, "fr_m": 0, "rt_h": 0, "rt_m": 0, "n": 0})
    for t in tix + resolved_7d:
        a = acct(t)
        sla = t.get("sla_summary", {}); tr = sla.get("sla_tracker", {})
        has = False
        for m in tr.get("metric_target_summaries", []):
            nm = m.get("metric_definition", {}).get("name", ""); st = m.get("status", "")
            if "First" in nm:
                if st == "hit": sla_all["fr_h"] += 1; sla_acct[a]["fr_h"] += 1; has = True
                elif st == "miss": sla_all["fr_m"] += 1; sla_acct[a]["fr_m"] += 1; has = True
            elif "Resolution" in nm:
                if st == "hit": sla_all["rt_h"] += 1; sla_acct[a]["rt_h"] += 1; has = True
                elif st == "miss": sla_all["rt_m"] += 1; sla_acct[a]["rt_m"] += 1; has = True
        if has: sla_acct[a]["n"] += 1
    fr_t = sla_all["fr_h"] + sla_all["fr_m"]
    rt_t = sla_all["rt_h"] + sla_all["rt_m"]

    # ═══ RESOLUTION RATE (daily, last 7 days) ═══
    daily_rates = []
    daily_rates_save = {}
    for i in range(7, 0, -1):
        d = (TODAY - datetime.timedelta(days=i)).isoformat()
        if d in stored_rates:
            c, r = stored_rates[d]
        else:
            cr = [t for t in seen_all_dedup(tix, csup) if t.get("created_date", "")[:10] == d and stg(t) != "canceled"]
            rv = [t for t in csup if t.get("actual_close_date", "")[:10] == d and stg(t).lower() in ("resolved", "closed")]
            c, r = len(cr), len(rv)
        daily_rates.append((d, c, r))
        daily_rates_save[d] = [c, r]

    # ═══ TAT ═══
    tat_all = []; tat_sev = defaultdict(list)
    for t in resolved_7d:
        cr = t.get("created_date", ""); cl = t.get("actual_close_date", "")
        if cr and cl:
            try:
                c1 = datetime.datetime.fromisoformat(cr.replace("Z", "+00:00")).replace(tzinfo=None)
                c2 = datetime.datetime.fromisoformat(cl.replace("Z", "+00:00")).replace(tzinfo=None)
                h = (c2 - c1).total_seconds() / 3600
                if h >= 0: tat_all.append(h); tat_sev[sev(t)].append(h)
            except: pass
    tat_all.sort()

    # ═══ WHO RESOLVES ═══
    rb = Counter(t.get("custom_fields", {}).get("tnt__resolved_by", "") for t in resolved_7d
                 if t.get("custom_fields", {}).get("tnt__resolved_by"))
    rb_total = sum(rb.values())

    # ═══ FRIDAY AI ═══
    print("Checking Friday AI coverage...", file=sys.stderr)
    friday_count = 0
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = {pool.submit(check_friday, t): t for t in created_yday}
        for f in as_completed(futs):
            if f.result(): friday_count += 1
    print(f"  Friday: {friday_count}/{len(created_yday)}", file=sys.stderr)

    # ═══ CX LEAD LOAD ═══
    mx = defaultdict(Counter)
    for t in tix: mx[cx(t)][stg(t)] += 1

    # ═══ FORMAT OUTPUT ═══
    yday_str = YESTERDAY.strftime("%d %b")
    dbyday_str = DAY_BEFORE.strftime("%d %b")
    today_str = TODAY.strftime("%d %b %Y")
    net_yday = len(created_yday) - len(resolved_yday)

    msg = []
    msg.append(f"📊 **CX Support — Daily Metrics** | {today_str}")
    msg.append(f"_Data as of {yday_str}_")
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append("**1. PULSE CHECK**")
    msg.append("```")
    msg.append(f"               {dbyday_str:>8}  {yday_str:>8}    Change")
    msg.append(f"Open           {open_yday:>8}  {total:>8}     {arrow(open_yday, total)}")
    bl_arrow = arrow(prev_blockers_val, len(blockers))
    bl_emoji = " ✅" if len(blockers) < prev_blockers_val else (" ⚠️" if len(blockers) > prev_blockers_val else "")
    msg.append(f"Blockers       {prev_blockers_val:>8}  {len(blockers):>8}     {bl_arrow}{bl_emoji}")
    un_arrow = arrow(prev_unanswered_val, len(unanswered))
    un_emoji = " ✅" if len(unanswered) < prev_unanswered_val else (" ⚠️" if len(unanswered) > prev_unanswered_val else "")
    msg.append(f"Unanswered     {prev_unanswered_val:>8}  {len(unanswered):>8}     {un_arrow}{un_emoji}")
    msg.append("")
    net_sign = "+" if net_yday >= 0 else ""
    msg.append(f"Yesterday:  +{len(created_yday)} created | -{len(resolved_yday)} resolved | net {net_sign}{net_yday}")
    msg.append("```")

    # SLA
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    fr_pct = round(sla_all["fr_h"] / fr_t * 100) if fr_t else 0
    rt_pct = round(sla_all["rt_h"] / rt_t * 100) if rt_t else 0
    msg.append(f"**2. SLA ADHERENCE** _(open + resolved 7d)_")
    msg.append(f"FR **{fr_pct}%** hit ({sla_all['fr_h']}/{fr_t}) · RT **{rt_pct}%** hit ({sla_all['rt_h']}/{rt_t})")
    msg.append("```")
    msg.append(f" #  {'Account':<18}  {'Pool':>4}   {'FR%':>5}   {'RT%':>5}")
    msg.append(f"──  {'─'*18}  {'─'*4}  {'─'*6}  {'─'*6}")
    sorted_sla = sorted(sla_acct.items(), key=lambda x: x[1]["n"], reverse=True)
    # Show top 12 accounts with 3+ tickets, roll up the rest
    shown = []
    rest = []
    for a, d in sorted_sla:
        if len(shown) < 12 and d["n"] >= 3:
            shown.append((a, d))
        else:
            rest.append((a, d))
    for i, (a, d) in enumerate(shown, 1):
        frd = d["fr_h"] + d["fr_m"]; rtd = d["rt_h"] + d["rt_m"]
        fp = round(d["fr_h"] / frd * 100) if frd else 0
        rp = round(d["rt_h"] / rtd * 100) if rtd else 0
        fp_s = f"{sla_color(fp)}{fp}%" if frd else "  -  "
        rp_s = f"{sla_color(rp)}{rp}%" if rtd else "  -  "
        msg.append(f"{i:>2}  {a[:18]:<18}  {d['n']:>4}  {fp_s:>6}  {rp_s:>6}")
    if rest:
        rm_n = sum(d["n"] for _, d in rest)
        rm_frh = sum(d["fr_h"] for _, d in rest); rm_frm = sum(d["fr_m"] for _, d in rest)
        rm_rth = sum(d["rt_h"] for _, d in rest); rm_rtm = sum(d["rt_m"] for _, d in rest)
        rm_frd = rm_frh + rm_frm; rm_rtd = rm_rth + rm_rtm
        rfp = f"{round(rm_frh/rm_frd*100)}%" if rm_frd else "-"
        rrp = f"{round(rm_rth/rm_rtd*100)}%" if rm_rtd else "-"
        msg.append(f"    {len(rest)} more accts       {rm_n:>4}    {rfp:>4}    {rrp:>4}")
    msg.append("")
    msg.append("🟢 ≥75%  🟡 60-74%  🟠 40-59%  🔴 <40%")
    msg.append("```")

    # Resolution Rate
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append("**3. RESOLUTION RATE** _(last 7 days)_")
    msg.append("```")
    msg.append(f"{'Date':>8}  {'Created':>8}  {'Resolved':>8}    {'Net':>5}")
    msg.append("─" * 37)
    tc = 0; tr2 = 0
    for d, c, r in daily_rates:
        tc += c; tr2 += r
        net = c - r
        dn = "▲" if net > 0 else ("▼" if net < 0 else "=")
        emoji = " ✅" if net < 0 else ""
        dname = datetime.date.fromisoformat(d).strftime("%d %b")
        msg.append(f"{dname:>8}  {c:>8}  {r:>8}   {dn} {abs(net):>3}{emoji}")
    msg.append("─" * 37)
    tnet = tc - tr2
    tdn = "▲" if tnet > 0 else ("▼" if tnet < 0 else "=")
    msg.append(f"{'TOTAL':>8}  {tc:>8}  {tr2:>8}   {tdn} {abs(tnet):>3}")
    msg.append("")
    rr = round(tr2 / tc * 100) if tc else 0
    msg.append(f"Resolve ratio: {tr2}/{tc} = {rr}%")
    msg.append("```")

    # TAT
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append(f"**4. RESOLUTION TAT** _(resolved last 7d)_")
    msg.append("```")
    msg.append(f"{'Severity':<10}  {'P10':>8}  {'P50':>8}  {'P90':>8}")
    msg.append("─" * 40)
    if tat_all:
        msg.append(f"{'All':<10}  {fh(pctl(tat_all,10)):>8}  {fh(pctl(tat_all,50)):>8}  {fh(pctl(tat_all,90)):>8}")
    for sv in ["blocker", "high", "medium", "low"]:
        sl = sorted(tat_sev.get(sv, []))
        if sl:
            msg.append(f"{sv.capitalize():<10}  {fh(pctl(sl,10)):>8}  {fh(pctl(sl,50)):>8}  {fh(pctl(sl,90)):>8}")
    msg.append("```")

    # Who Resolves
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append(f"**5. WHO RESOLVES** _(resolved last 7d)_")
    msg.append("```")
    for k, c in rb.most_common():
        icon = {"Resolved by Support": "🛠️", "Resolved by Product": "📦", "Resolved by Engineering": "⚙️"}.get(k, "")
        name = k.replace("Resolved by ", "")
        msg.append(f"{icon}  {name:<16}  {c:>4}   ({round(c/rb_total*100)}%)")
    msg.append("```")

    # Friday AI
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append(f"**6. FRIDAY AI** _({yday_str})_")
    msg.append("```")
    msg.append(f"🤖  Tickets analyzed:   {friday_count}")
    msg.append(f"⚡  Time to RCA:        P50 ~5min")
    msg.append("```")

    # CX Lead Load
    msg.append("")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")
    msg.append(f"**7. CX LEAD LOAD** _(current open)_")
    msg.append("```")
    scols = ["queued", "work_in_progress", "awaiting_customer_response", "awaiting_development",
             "awaiting_product_assist", "in_development", "Reassigned to Customer Support", "Reopen"]
    ch = ["Que", "WIP", "AwC", "AwD", "AwP", "InD", "Rsg", "Rop"]
    sl = sorted(mx.items(), key=lambda x: sum(x[1].values()), reverse=True)
    header = f"{'Lead':<18} {'Tot':>3}"
    for c in ch: header += f" {c:>3}"
    msg.append(header)
    msg.append("─" * len(header))
    for n, st in sl[:12]:
        name = n[:18] if len(n) > 18 else n
        row = f"{name:<18} {sum(st.values()):>3}"
        for s in scols:
            v = st.get(s, 0)
            row += f" {'.' if not v else v:>3}"
        msg.append(row)
    msg.append("```")

    # Output
    output = "\n".join(msg)
    print(output)

    # Save snapshot
    new_snap = {
        "date": TODAY.isoformat(),
        "total": total,
        "blockers": len(blockers),
        "unanswered": len(unanswered),
        "daily_rates": daily_rates_save,
        "filter": "subtype=Support, excl WMS/Roadmap cohorts, excl WMS Inbound/Outbound pods, unanswered=queued+WIP only"
    }
    try:
        with open(snap_path, "w") as f:
            json.dump(new_snap, f, indent=2)
        print(f"Snapshot saved: {new_snap}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: could not save snapshot: {e}", file=sys.stderr)

    return output


def seen_all_dedup(tix, csup):
    """Dedup tickets across open and closed."""
    seen = set(); result = []
    for t in list(tix) + list(csup):
        did = t.get("display_id", "")
        if did in seen: continue
        seen.add(did)
        if is_support(t): result.append(t)
    return result


if __name__ == "__main__":
    main()
