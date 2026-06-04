#!/usr/bin/env python3
"""
Parse customer_support_slas.md into structured JSON.
Extracts per-customer SLA terms: severity tiers, response/resolution times,
support hours, uptime %, and service credits.
"""

import json
import re
import sys
from pathlib import Path

INPUT_FILE = Path(__file__).parent.parent.parent / "customer_support_slas.md"
OUTPUT_FILE = Path(__file__).parent.parent / "config" / "contractual-slas-raw.json"

# If input file path passed as arg, use it
if len(sys.argv) > 1:
    INPUT_FILE = Path(sys.argv[1])


def parse_time_to_minutes(time_str: str) -> int | None:
    """Convert a time string like '15 min', '4 hrs', '2 hours', '48 hrs / 2 working days' to minutes."""
    if not time_str:
        return None
    time_str = time_str.strip().lower()

    # Handle "as per pm process" or similar non-numeric
    if not any(c.isdigit() for c in time_str):
        return None

    # Try hours first: "4 hrs", "4 hours", "4 hr", "4h"
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:hrs?|hours?|h\b)', time_str)
    if m:
        return int(float(m.group(1)) * 60)

    # Try minutes: "15 min", "15 mins", "15 minutes", "15m", "30 min"
    m = re.search(r'(\d+)\s*(?:mins?|minutes?|m\b)', time_str)
    if m:
        return int(m.group(1))

    # Try days: "2 working days", "5 working days"
    m = re.search(r'(\d+)\s*(?:working\s+)?days?', time_str)
    if m:
        return int(m.group(1)) * 24 * 60  # Convert to minutes (calendar)

    # Try bare number followed by context (e.g., "48 hrs / 2 working days" — already caught above)
    m = re.search(r'(\d+)', time_str)
    if m:
        # If it's a large number, probably hours
        val = int(m.group(1))
        if val >= 24:
            return val * 60  # Assume hours
        return val * 60  # Default assume hours

    return None


def parse_support_hours(text: str) -> str | None:
    """Extract support hours from a tier line."""
    text = text.lower()

    if '24x7' in text or '24*7' in text or '24/7' in text:
        return '24x7'
    if '16x6' in text or '16*6' in text:
        return '16x6'
    if '8x5' in text or '8*5' in text:
        return '8x5'

    # Mon-Fri patterns
    if re.search(r'mon[- ]?fri', text):
        m = re.search(r'(\d{1,2})\s*(?:am|:00\s*am)\s*[-–to]+\s*(\d{1,2})\s*(?:pm|:00\s*pm)', text)
        if m:
            return f"Mon-Fri {m.group(1)}AM-{m.group(2)}PM"
        return '8x5'

    # Mon-Sat patterns
    if re.search(r'mon[- ]?sat', text):
        return 'Mon-Sat'

    # Sun-Thu patterns (Middle East)
    if re.search(r'sun[- ]?thu', text):
        return 'Sun-Thu 8x5'

    return None


def extract_uptime(block: str) -> float | None:
    """Extract uptime percentage from a block."""
    # First try lines starting with "Uptime:" (most precise)
    for line in block.split('\n'):
        stripped = line.strip()
        if stripped.lower().startswith('uptime:') or stripped.lower().startswith('availability'):
            m = re.search(r'(\d{2,3}(?:\.\d+)?)\s*%', stripped)
            if m:
                val = float(m.group(1))
                if 90 <= val <= 100:
                    return val
    # Fallback: find % near uptime/availability keywords, but skip Source: lines
    for line in block.split('\n'):
        lower_line = line.strip().lower()
        if lower_line.startswith('source:'):
            continue
        if any(kw in lower_line for kw in ['uptime', 'availability', 'available']):
            m = re.search(r'(\d{2,3}(?:\.\d+)?)\s*%', line)
            if m:
                val = float(m.group(1))
                if 90 <= val <= 100:
                    return val
    return None


def extract_service_credits(block: str) -> tuple[bool, str | None]:
    """Check if service credits/penalties exist."""
    lower = block.lower()

    # Check for explicit "none"
    none_patterns = [
        r'service credits?\s*/?\s*penalties?\s*:\s*none',
        r'service credits?\s*/?\s*penalties?\s*:\s*NONE',
        r'penalties?\s*:\s*none',
        r'no fixed service[- ]credit',
    ]
    for pat in none_patterns:
        if re.search(pat, lower):
            # But check if there's still some penalty language
            if any(kw in lower for kw in ['liquidated damages', 'penalty band', '% of monthly']):
                break
            return False, None

    # Check for positive credit indicators
    credit_indicators = [
        'service credit', 'penalty band', 'liquidated damages',
        '% of monthly', 'credit equivalent', 'monthly billing',
        'monthly recurring fee', 'penalty matrix'
    ]
    for indicator in credit_indicators:
        if indicator in lower:
            # Extract the summary
            for line in block.split('\n'):
                if indicator in line.lower():
                    return True, line.strip()
            return True, "Service credits present (see details)"

    return False, None


def parse_tier_line(line: str) -> dict | None:
    """Parse a single tier line like '- P1 (platform shutdown): response 15 min, resolution 2 hrs, support 24*7'."""
    line = line.strip()
    if not line.startswith('-'):
        return None

    result = {}

    # Extract priority label
    # Patterns: "P1", "Shutdown (P1)", "P1 Critical", "Emergency (P1)", "P1 Shutdown"
    priority_match = re.search(r'\b[Pp]([1-4])\b', line)
    if not priority_match:
        # Try S1/S2/S3/S4 labels (e.g. Aster Healthcare)
        s_match = re.search(r'\b[Ss]([1-4])\b', line)
        if s_match:
            result['priority'] = f"P{s_match.group(1)}"
            # For S-labels, try "<=X min/hr" response pattern
            resp_alt = re.search(r'<=?\s*(\d+(?:\.\d+)?\s*(?:min(?:s|utes?)?|hrs?|hours?|business\s+hours?))', line)
            if resp_alt:
                result['_alt_response'] = resp_alt.group(1)
    if not priority_match and 'priority' not in result:
        # Try descriptive labels
        label_map = {
            'shutdown': 'P1', 'critical': 'P1', 'emergency': 'P1', 'urgent': 'P1', 'blocker': 'P1',
            'bugs': 'P2', 'high': 'P2', 'major': 'P2',
            'improvement': 'P3', 'medium': 'P3', 'minor': 'P3',
            'low': 'P4', 'training': 'P4', 'general': 'P4', 'cosmetic': 'P4',
        }
        lower_line = line.lower()
        for keyword, priority in label_map.items():
            if keyword in lower_line:
                result['priority'] = priority
                break
        if 'priority' not in result:
            return None
    else:
        result['priority'] = f"P{priority_match.group(1)}"

    # Extract response time
    resp_match = re.search(
        r'[Rr]esponse\s+(\d+(?:\.\d+)?\s*(?:min(?:s|utes?)?|hrs?|hours?|h\b|m\b))',
        line
    )
    if resp_match:
        result['response_time_minutes'] = parse_time_to_minutes(resp_match.group(1))
    else:
        # Try "first response" pattern
        resp_match = re.search(
            r'first\s+response\s+(\d+(?:\.\d+)?\s*(?:min(?:s|utes?)?|hrs?|hours?|h\b|m\b))',
            line
        )
        if resp_match:
            result['response_time_minutes'] = parse_time_to_minutes(resp_match.group(1))
        elif '_alt_response' in result:
            # S-label style: "<=15 min"
            result['response_time_minutes'] = parse_time_to_minutes(result.pop('_alt_response'))

    # Clean up temp key
    result.pop('_alt_response', None)

    # Extract resolution time
    # Handles: "resolution 2 hrs", "max resolution 2 hrs", "resolution up to 18 hr"
    res_match = re.search(
        r'(?:max\s+)?[Rr]esolution\s+(?:up\s+to\s+)?(\d+(?:\.\d+)?\s*(?:min(?:s|utes?)?|hrs?|hours?|h\b|m\b|working\s+days?))',
        line
    )
    if res_match:
        result['resolution_time_minutes'] = parse_time_to_minutes(res_match.group(1))
    else:
        result['resolution_time_minutes'] = None

    # Extract support hours
    result['support_hours'] = parse_support_hours(line)

    return result


def parse_customer_block(block: str) -> dict:
    """Parse a single customer SLA block."""
    lines = block.strip().split('\n')

    # Extract customer name
    name_match = re.search(r'=== CUSTOMER:\s*(.+?)\s*===', block)
    customer_name = name_match.group(1) if name_match else "UNKNOWN"

    result = {
        'customer_name': customer_name,
        'uptime_pct': None,
        'tiers': [],
        'has_service_credits': False,
        'service_credits_summary': None,
        'notes': [],
        'status': 'ok',  # ok, none_found, incomplete
    }

    # Check for NONE FOUND
    if 'NONE FOUND' in block:
        result['status'] = 'none_found'
        return result

    # Check for INCOMPLETE
    if 'INCOMPLETE' in block:
        result['status'] = 'incomplete'

    # Extract uptime
    result['uptime_pct'] = extract_uptime(block)

    # Extract service credits
    has_credits, credits_summary = extract_service_credits(block)
    result['has_service_credits'] = has_credits
    result['service_credits_summary'] = credits_summary

    # Extract tiers — find lines starting with "- " that contain priority/response info
    tier_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('- ') and any(kw in stripped.lower() for kw in [
            'response', 'resolution', 'p1', 'p2', 'p3', 'p4',
            'shutdown', 'critical', 'bugs', 'improvement', 'emergency',
            'high', 'medium', 'low', 'training', 'urgent'
        ]):
            tier_lines.append(stripped)

    # Parse each tier line
    seen_priorities = set()
    for tl in tier_lines:
        parsed = parse_tier_line(tl)
        if parsed and parsed.get('priority') and parsed['priority'] not in seen_priorities:
            seen_priorities.add(parsed['priority'])
            result['tiers'].append(parsed)

    # Sort tiers by priority
    priority_order = {'P1': 1, 'P2': 2, 'P3': 3, 'P4': 4}
    result['tiers'].sort(key=lambda t: priority_order.get(t.get('priority', 'P9'), 9))

    # Extract notes (OCR flags, special observations)
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith('note:') or '[ocr unclear]' in stripped.lower():
            result['notes'].append(stripped)

    if not result['notes']:
        result['notes'] = None

    # If no tiers found but block isn't NONE FOUND, flag it
    if not result['tiers'] and result['status'] == 'ok':
        result['status'] = 'no_tiers_parsed'

    return result


def main():
    # Read input
    if not INPUT_FILE.exists():
        print(f"ERROR: Input file not found: {INPUT_FILE}")
        sys.exit(1)

    text = INPUT_FILE.read_text(encoding='utf-8')

    # Split into customer blocks using the delimiter
    blocks = re.split(r'(?=^=== CUSTOMER:)', text, flags=re.MULTILINE)

    customers = []
    for block in blocks:
        if '=== CUSTOMER:' not in block:
            continue
        parsed = parse_customer_block(block)
        customers.append(parsed)

    # Summary stats
    total = len(customers)
    ok = sum(1 for c in customers if c['status'] == 'ok')
    none_found = sum(1 for c in customers if c['status'] == 'none_found')
    incomplete = sum(1 for c in customers if c['status'] == 'incomplete')
    no_tiers = sum(1 for c in customers if c['status'] == 'no_tiers_parsed')
    with_credits = sum(1 for c in customers if c['has_service_credits'])

    print(f"Parsed {total} customer blocks:")
    print(f"  OK (tiers extracted): {ok}")
    print(f"  NONE FOUND:          {none_found}")
    print(f"  INCOMPLETE:          {incomplete}")
    print(f"  No tiers parsed:     {no_tiers}")
    print(f"  With service credits: {with_credits}")

    # Show tier count distribution
    tier_counts = {}
    for c in customers:
        n = len(c['tiers'])
        tier_counts[n] = tier_counts.get(n, 0) + 1
    print(f"\nTier count distribution:")
    for n in sorted(tier_counts.keys()):
        print(f"  {n} tiers: {tier_counts[n]} customers")

    # Show customers with no_tiers_parsed for debugging
    if no_tiers > 0:
        print(f"\nCustomers with no tiers parsed:")
        for c in customers:
            if c['status'] == 'no_tiers_parsed':
                print(f"  - {c['customer_name']}")

    # Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(customers, f, indent=2, ensure_ascii=False)

    print(f"\nOutput written to: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
