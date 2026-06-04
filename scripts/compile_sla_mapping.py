#!/usr/bin/env python3
"""
Compile the full 209-customer SLA + DevRev mapping into a readable .md file.
"""
import json
from pathlib import Path

OUTPUT_MD = Path(__file__).parent.parent / "docs" / "contractual-sla-master.md"
SLA_FILE = Path(__file__).parent.parent / "config" / "contractual-slas.json"

# ─── DevRev Account Mapping (from 3 batch searches) ─────────────────────

DEVREV_MAP = {
    # Batch 1
    "Aarti Industries": ("aarti Account", "ACC-es51m8cC"),
    "Al Sariyah (Sharaf DG)": ("Sharaf DG", "ACC-wCkZLVXd"),
    "Alkhayyat Investments (Binsina)": ("Alkhayyat", "ACC-ZmAsKIxN"),
    "Amal": ("Amal", "ACC-ymNZRRNv"),
    "Americana": ("americana Account", "ACC-18U0xpvEA"),
    "Aramex": ("Aramex", "ACC-G0tfv4Ge"),
    "argenX": ("Argenx", "ACC-oFmmC9y6"),
    "Arvind Limited": ("arvind Account", "ACC-cTyUXh5T"),
    "ASDA UK": ("Asda", "ACC-lYzn2A0l"),
    "Asendia Singapore": ("Asendia", "ACC-S96fnVXA"),
    "Aster Healthcare": ("Aster Pharmacy", "ACC-x2ktKQ5F"),
    "Aujan": ("aujanexport", "ACC-16L1sk6A2"),
    "Avery Dennison": ("avery Account", "ACC-1CQoAsLw1"),
    "BDO": ("bdo", "ACC-xLKYFRU1"),
    "Biryani By Kilo": ("biryanibykilo Account", "ACC-9HUQgSZq"),
    "Blink Technologies (Tradeling)": ("tradeling Account", "ACC-3zxgi3OV"),
    "Bluescale LLP": ("bluescale", "ACC-iac3QmPc"),
    "BRF Global": ("brfglobal Account", "ACC-15eTz3A7Q"),
    "Bunge Lodgers": ("bunge Account", "ACC-lMPGZelK"),
    "Caratlane": ("caratlane Account", "ACC-1s7j2wgc"),
    "Catalent": ("Catalent", "ACC-BS3K7xoN"),
    "CBL Global Foods": ("CBL Group", "ACC-18RYQjbQD"),
    "Connect India": ("Connect India Account", "ACC-Po7VsXYn"),
    "Contango & E7": ("contango", "ACC-12D1rqCou"),
    "Contrans": ("contrans Account", "ACC-QREhtTmg"),
    "Ctrl M Print Management": ("ctrlm Account", "ACC-110lCVeCL"),
    "Dealshare": ("Dealshare", "ACC-we41FNng"),
    "Decathalon": ("decathlon", "ACC-11nEqZem9"),
    "Desqaured (Box)": ("box Account", "ACC-6d3aY1sU"),
    "DHL": ("Dhl", "ACC-zcCEZvoQ"),
    "Dmart": ("dmart Account", "ACC-DElHbQI9"),
    "DPD Laser": ("DPD Laser (SA)", "ACC-Ppjgapw8"),
    "DTDC Express Ltd": ("DTDC", "ACC-u5JsHNO6"),
    "Duroshox": ("Duroshox", "ACC-ox5hN6QR"),
    "EFL (Eureka Forbes)": ("Eureka Forbes (EFL)", "ACC-vvyq2xOY"),
    "Expeditors International": ("Expeditors", "ACC-17OR9pzUN"),
    "Extra": ("extra Account", "ACC-1E7fOV8yI"),
    "Fashnear (Farmiso)": ("farmiso", "ACC-13QuvDQnP"),
    "Fashnear (Meesho)": ("Meesho", "ACC-1DPjntFAp"),
    # Batch 2
    "Flipkart": ("Flipkart", "ACC-cBf033gP"),
    "Floward": ("floward", "ACC-88Oi83FP"),
    "Flyjac": ("flyjac Account", "ACC-craNYFNT"),
    "Freshcartons (Rozana)": ("Rozana", "ACC-1BzCWHVKp"),
    "Frontline Logistics": ("frontline Account", "ACC-DcdeBdVb"),
    "Gujarat Fluorochemicals Ltd": ("GFL (Gujarat Fluorochemicals)", "ACC-YThYOnlj"),
    "Gulf Maritime General Trading & Contracting Co W.L.L  (Alkazemi)": ("GMTC Account", "ACC-AYFzE4o1"),
    "GWC": ("GWC", "ACC-VRlFflHQ"),
    "Haldiram Products Pvt. Ltd": ("haldirams Account", "ACC-15QJK85PN"),
    "HCCB": ("HCCB", "ACC-1GleDV4ha"),
    "Healthkart": ("healthkart", "ACC-vQdBcPlX"),
    "Heineken": ("heineken", "ACC-BvMwCgbz"),
    "Hellmann": ("hellmann", "ACC-19CFACCjj"),
    "Hotline Delivery (Kout)": ("KFG (Kout Food Group)", "ACC-5kdgCwnT"),
    "Iwexpress": ("iwexpress Account", "ACC-9LHfIA0E"),
    "Jeebly": ("Jeebly Account", "ACC-AMhkvISV"),
    "Jindal Worldwide": ("jindaltextiles Account", "ACC-QnLZcoaH"),
    "Kasha": ("Kasha", "ACC-6FALvkEQ"),
    "Kelloggs": ("Kelloggs Account", "ACC-18Nf9SwRb"),
    "Kimbal Technologies": ("Kimbal", "ACC-jnri8Dno"),
    "Kyosk": ("kyosk", "ACC-16ccvHZRW"),
    "Labaiik": ("labaiik Account", "ACC-3BlVNbEF"),
    "LATAM": ("latam", "ACC-q6b6gsS1"),
    "LATAM (LAN Cargo S.A.)": ("latam", "ACC-q6b6gsS1"),
    "Lighthouse": ("Lighthouse Learning", "ACC-H0G5NaVq"),
    "Loftafrica": ("[WMS] Loftafrica", "ACC-sqx2Ih38"),
    "Lulu Hypermarket": ("Lulu", "ACC-XRtHRBlW"),
    "Maldives Post": ("Maldives Post", "ACC-g2d7oiNl"),
    "Maruti Courier": ("maruti", "ACC-KiVDPYGD"),
    "Meatigo": ("meatigo", "ACC-pKnmqMSh"),
    "Mezzan": ("Mezzan", "ACC-JUJJCgac"),
    "MOVIN": ("Movin", "ACC-13BcNu6a1"),
    "Myntra": ("Myntra", "ACC-2x1qgkli"),
    "Nature_s Basket": ("naturesbasket", "ACC-HUD5DU08"),
    "Omantel": ("omantel Account", "ACC-iPaUeZyw"),
    "Omya": ("omya Account", "ACC-qpXbyMOc"),
    "Oriental Rubber": ("oriental Account", "ACC-gNAerzKw"),
    "Part 1 (Partnr)": ("Partnr", "ACC-RNOL9vCY"),
    "PayTM": ("Paytm", "ACC-4BRDKu0g"),
    "Pepperfry": ("Pepperfry", "ACC-BxZaVW1L"),
    "Perfetti Van Melle": ("perfettivanmelle Account", "ACC-4cBtFpy1"),
    "Pincode": ("Pincode by PhonePe", "ACC-PM0M2rJX"),
    # Batch 3
    "Pitchfork": ("pitchfork Account", "ACC-8szRCdsu"),
    "Plub": ("PLUB", "ACC-10MFHpNLt"),
    "POST Luxembourg (Inflow)": ("Lux Post", "ACC-PIPrqQV"),
    "Prakash Chemical": ("prakashchemicals", "ACC-DkEZEm42"),
    "Pro Connect (India)": ("proconnect Account", "ACC-FdQdQr3H"),
    "Puig": ("Puig", "ACC-7def1dez"),
    "Purplle": ("purplle Account", "ACC-16Xvdf24F"),
    "Qatarpost": ("Qatar Post (qpost)", "ACC-22rTAbb2"),
    "Quiqup": ("Quiqup UAE", "ACC-FswgQjhe"),
    "RIL": ("Reliance (RIL)", "ACC-y36IXmM4"),
    "Safexpress": ("Safexpress", "ACC-wxyJQCGl"),
    "Samsonite": ("samsonite", "ACC-p2ypFUj8"),
    "Sangeetha Mobiles Private Limited": ("sangeetha Account", "ACC-1EppULbJ6"),
    "Sathya Agencies": ("Sathya", "ACC-LQzaIyXt"),
    "Saudi Bulk Company (SBT)": ("SBT Account", "ACC-BiJi7X4d"),
    "Sela": ("sela.sa", "ACC-8lfRVMFN"),
    "SF Logistics Private Limited (Ibobscs)": ("ibobscs Account", "ACC-XRyHQwVe"),
    "SGA Security": ("sga", "ACC-WtyW42Bn"),
    "Shipyaari": ("Shipyaari", "ACC-mW4sob1j"),
    "Sirocco FZCO": ("sirocco Account", "ACC-soIC4HJR"),
    "SKIP Logistics": ("skipexpress Account", "ACC-bnSXgthq"),
    "Smiths News": ("Smiths News", "ACC-10vPAvm5V"),
    "Spencer": ("Spencers", "ACC-lFj4HNfY"),
    "SPL (TibbyGo)": ("TibbyGo (Infinite PL)", "ACC-LabyApj6"),
    "Starlinks": ("Starlinks (Connect)", "ACC-1CHNaIgjk"),
    "Sterling": ("Sterling Account", "ACC-17RQUhiAW"),
    "Swiggy": ("Swiggy", "ACC-14bkjdemh"),
    "Tata 1MG": ("1mg", "ACC-D3fTNluZ"),
    "Tata Motors": ("tatamotors Account", "ACC-GF2zF1eI"),
    "Tej Courier": ("Tejcouriers", "ACC-13M48rkqb"),
    "Teleport": ("Teleport", "ACC-1DIKg2Qlx"),
    "Thermo Fisher": ("Thermofisher", "ACC-mis1DHft"),
    "TibbyGo": ("TibbyGo (Infinite PL)", "ACC-LabyApj6"),
    "Truemeds": ("Truemeds", "ACC-pmA9AwIy"),
    "UBT": ("UBT", "ACC-Hmpi139c"),
    "Unibev": ("Unibev", "ACC-aXQsjMte"),
    "UPS Gulf": ("UPS", "ACC-1BgJ1VawB"),
    "Wacker Chemie": ("wacker Account", "ACC-D6VCSSM1"),
    "Wacker Metroark": ("Wacker", "ACC-BJbGr3Ru"),
    "Wakefit": ("wakefit.co", "ACC-15oNUsXpK"),
    "Warehouse Now": ("warehousenow", "ACC-d8jGxDb9"),
    "Wellness Forever": ("Wellness Forever (TMS)", "ACC-Z2zYm0vU"),
    "Welspun": ("welspunindia Account", "ACC-DpUvKLKD"),
    "XpressBees": ("Xpressbees", "ACC-13snlb4qU"),
    "Zajel": ("zajel", "ACC-sGhdsNvT"),
    "Zajil Express Company": ("Zajil Account", "ACC-KxMswNfE"),
    "Zypp": ("zypp Account", "ACC-una6Cy0Y"),
}

# Possible mismatches flagged by agents
FLAGGED = {
    "Maruti Courier": "maruti — may be different entity (courier vs auto)",
    "Oriental Rubber": "oriental Account — may be different entity",
    "Jindal Worldwide": "jindaltextiles — same group, different division",
    "Lighthouse": "Lighthouse Learning — verify same entity",
}


def fmt_time(minutes):
    if minutes is None:
        return "—"
    if minutes < 60:
        return f"{minutes}m"
    h = minutes / 60
    if h == int(h):
        return f"{int(h)}h"
    return f"{h:.1f}h"


def main():
    data = json.loads(SLA_FILE.read_text())

    lines = []
    lines.append("# Contractual SLA Master — All 209 Customers + DevRev Mapping")
    lines.append("")
    lines.append("Generated: 2026-06-02")
    lines.append(f"Source: `customer_support_slas.md` (contract extraction)")
    lines.append("")

    # Stats
    matched = sum(1 for c in data if c["customer_name"] in DEVREV_MAP)
    not_matched = len(data) - matched
    with_tiers = sum(1 for c in data if c.get("tiers"))
    with_credits = sum(1 for c in data if c.get("has_service_credits"))
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Count |")
    lines.append(f"|---|---|")
    lines.append(f"| Total customers | {len(data)} |")
    lines.append(f"| Mapped to DevRev account | {matched} |")
    lines.append(f"| Not mapped (no DevRev account found) | {not_matched} |")
    lines.append(f"| With structured SLA tiers | {with_tiers} |")
    lines.append(f"| With service credits/penalties | {with_credits} |")
    lines.append("")

    # Legend
    lines.append("## Legend")
    lines.append("")
    lines.append("- **Resp** = First Response time")
    lines.append("- **Res** = Max Resolution time (— = not committed in contract)")
    lines.append("- **Hrs** = Support hours for that tier")
    lines.append("- **Status**: OK = parsed, NONE = no SLA in contract, NO TIERS = narrative/missing tiers, INCOMPLETE = partial")
    lines.append("")

    # DevRev default
    lines.append("## DevRev Default SLA (sla-28)")
    lines.append("")
    lines.append("| Severity | First Response | Resolution | Schedule |")
    lines.append("|---|---|---|---|")
    lines.append("| Blocker | 15m | 4h | 24x7 |")
    lines.append("| High | 1h | 36h | Mon-Sat 10AM-8PM |")
    lines.append("| Medium | 2h | 48h | Mon-Fri 10AM-8PM |")
    lines.append("| Low | 4h | 72h | Mon-Fri 10AM-8PM |")
    lines.append("")

    # Main table
    lines.append("## Full Customer List")
    lines.append("")
    lines.append("| # | Customer | DevRev Account | Account ID | Status | Uptime | Credits | P1 Resp | P1 Res | P2 Resp | P2 Res | P3 Resp | P3 Res | P4 Resp | P4 Res |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")

    for i, c in enumerate(data, 1):
        name = c["customer_name"]
        devrev_name = "—"
        devrev_id = "—"
        if name in DEVREV_MAP:
            devrev_name, devrev_id = DEVREV_MAP[name]
        if name in FLAGGED:
            devrev_name += " (?)"

        status = c.get("status", "ok")
        if status == "none_found":
            status = "NONE"
        elif status == "incomplete":
            status = "INCOMPLETE"
        elif status == "no_tiers_parsed":
            status = "NO TIERS"
        else:
            status = "OK"

        uptime = f"{c['uptime_pct']}%" if c.get("uptime_pct") else "—"
        credits = "Yes" if c.get("has_service_credits") else "No"

        tiers = {t["priority"]: t for t in c.get("tiers", [])}

        def get_t(p):
            t = tiers.get(p, {})
            return fmt_time(t.get("response_time_minutes")), fmt_time(t.get("resolution_time_minutes"))

        p1r, p1x = get_t("P1")
        p2r, p2x = get_t("P2")
        p3r, p3x = get_t("P3")
        p4r, p4x = get_t("P4")

        lines.append(
            f"| {i} | {name} | {devrev_name} | {devrev_id} | {status} | {uptime} | {credits} "
            f"| {p1r} | {p1x} | {p2r} | {p2x} | {p3r} | {p3x} | {p4r} | {p4x} |"
        )

    lines.append("")

    # Not found list
    lines.append("## Customers Not Found in DevRev")
    lines.append("")
    not_found = [c["customer_name"] for c in data if c["customer_name"] not in DEVREV_MAP]
    for n in not_found:
        lines.append(f"- {n}")
    lines.append("")

    # Flagged possible mismatches
    lines.append("## Flagged Possible Mismatches (Review)")
    lines.append("")
    lines.append("| Contract Name | DevRev Match | Flag |")
    lines.append("|---|---|---|")
    for name, flag in FLAGGED.items():
        lines.append(f"| {name} | {flag.split(' — ')[0] if ' — ' in flag else flag} | {flag} |")
    lines.append("")

    # No SLA signal list (from bottom of source file)
    lines.append("## No SLA Signal in Contract (32 folders)")
    lines.append("")
    lines.append("These folders had readable contract text but no SLA keywords. Likely OF/addendum-only or genuinely no SLA.")
    lines.append("")
    no_signal = [
        "Adwar Logistics", "Almaya", "APM Cargo", "Arrow Foods", "Asian Paints", "Atul Limited",
        "Baladna", "Bayara", "Chiripoly Films Ltd", "Chrono Diali", "Dhaval Agri", "DPD Poland",
        "Easybox", "G4S", "Gulf Marketing Group", "Imerys", "Incresol",
        "Jubiliant Foodworks (Dominos)", "Junction 4 Pallets", "Kuehne Nagel Private Ltd",
        "Mitsui & Co", "Mynet express", "Polymedicure", "Power Lease", "Propelor",
        "Restaurant Brand Asia Limited (Burger King)", "Rishi Fibc Solutions Pvt. Ltd",
        "Saudi Ceramics", "Signode", "Sohobcom & Yemenpost", "Vashi Integrated Solutions Limited",
    ]
    for n in no_signal:
        lines.append(f"- {n}")

    OUTPUT_MD.write_text("\n".join(lines))
    print(f"Written to {OUTPUT_MD}")
    print(f"Total lines: {len(lines)}")
    print(f"Matched: {matched}/{len(data)}")


if __name__ == "__main__":
    main()
