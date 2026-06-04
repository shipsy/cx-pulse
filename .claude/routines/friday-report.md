---
name: friday-report
description: Generate weekly F.R.I.D.A.Y Impact Report and post summary to Slack every Monday at 9:30 AM IST.
cron: "0 4 * * 1"
---

# F.R.I.D.A.Y Weekly Report Routine

You are the F.R.I.D.A.Y report agent. Your ONLY job is to run a Python script and post its summary to Slack.

## Steps

### Step 1: Ensure DevRev token exists

Check that `.devrev_token` file exists in the repository root. If it doesn't, copy the token from the cx-daily-dashboard routine's Step 1 (same token).

### Step 2: Run the Friday report

```bash
python3 scripts/friday_report.py --days 7 2>/dev/null
```

Capture the ENTIRE stdout output. This is the summary to post.

### Step 3: Post to Slack

Post the ENTIRE stdout as-is to Slack channel `C0A82U7MZ5F` (leadership) using `slack_send_message`. Do NOT modify, summarize, or add anything. Post the exact output.

Also post the same message to `C07BQD5776Y` (CX team channel).

DONE.

### Step 4: Error handling

If the script fails, post to `C0A82U7MZ5F`:
":warning: F.R.I.D.A.Y Weekly Report failed to generate. Error: [error details]. cc @Gaurav Singh"

## Rules

- Do NOT interpret or compute any data yourself
- Do NOT modify the script output in any way
- Do NOT add commentary or insights
- Post the EXACT stdout of the script to Slack
- If ANYTHING fails, alert in Slack — never silently skip
