#!/usr/bin/env python3
"""Dashboard Preflight Check — validates token, API, snapshot before dashboard runs.
Run: python3 scripts/dashboard_preflight.py
Exit 0 = safe to run dashboard. Exit 1 = something broken, do NOT run dashboard."""

import json, os, sys, datetime, urllib.request, base64

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


def check_token():
    if not TOKEN:
        return False, "DEVREV_TOKEN env var not set"
    try:
        d = json.dumps({"type": ["ticket"], "limit": 1}).encode()
        r = urllib.request.Request(f"{API}/works.list", data=d,
            headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
        with urllib.request.urlopen(r, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        if "works" in data:
            return True, "API auth OK"
        return False, "API returned unexpected response"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "TOKEN EXPIRED or INVALID (HTTP 401) — generate new PAT in DevRev"
        return False, f"API error HTTP {e.code}"
    except Exception as e:
        return False, f"API unreachable: {e}"


def check_token_expiry():
    try:
        parts = TOKEN.split(".")
        if len(parts) != 3:
            return True, "Not a JWT, skipping expiry check"
        padding = "=" * (4 - len(parts[1]) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(parts[1] + padding))
        exp = decoded.get("exp", 0)
        days_left = (exp - datetime.datetime.now().timestamp()) / 86400
        if days_left < 0:
            return False, f"Token EXPIRED {abs(int(days_left))} days ago"
        if days_left < 7:
            return False, f"Token expires in {int(days_left)} days — RENEW NOW"
        if days_left < 30:
            return True, f"Token expires in {int(days_left)} days — renew soon"
        return True, f"Token valid for {int(days_left)} more days"
    except Exception:
        return True, "Could not parse JWT expiry"


def check_snapshot():
    snap_path = os.path.join(os.path.dirname(__file__), "..", "config", "daily-snapshot.json")
    try:
        with open(snap_path) as f:
            snap = json.load(f)
        date = snap.get("date", "")
        if not date:
            return False, "Snapshot has no date field"
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        if date == yesterday:
            has_rates = "daily_rates" in snap
            return True, f"Snapshot current ({date}), rates={'yes' if has_rates else 'NO — daily counts will be reconstructed'}"
        days_old = (datetime.date.today() - datetime.date.fromisoformat(date)).days
        if days_old <= 2:
            return True, f"Snapshot {days_old}d old ({date}) — pulse will use reconstruction for gap days"
        return False, f"Snapshot stale ({date}, {days_old}d old) — pulse data will be inaccurate"
    except FileNotFoundError:
        return False, "Snapshot file missing — first run, pulse previous-day will use reconstruction"
    except Exception as e:
        return False, f"Snapshot corrupted: {e}"


def main():
    checks = [
        ("Token valid", check_token),
        ("Token expiry", check_token_expiry),
        ("Snapshot file", check_snapshot),
    ]

    all_ok = True
    blockers = []
    print("Dashboard Preflight Check", file=sys.stderr)
    print("-" * 40, file=sys.stderr)
    for name, fn in checks:
        ok, msg = fn()
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False
            blockers.append(f"{name}: {msg}")
        print(f"  {status}  {name}: {msg}", file=sys.stderr)
    print("-" * 40, file=sys.stderr)

    if all_ok:
        print("All checks passed", file=sys.stderr)
        return 0
    else:
        # Print blockers to stdout so the trigger agent can relay them
        print("PREFLIGHT_FAILED: " + " | ".join(blockers))
        return 1


if __name__ == "__main__":
    sys.exit(main())
