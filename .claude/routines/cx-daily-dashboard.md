---
name: cx-daily-dashboard
description: Post the CX Support Daily Metrics to Slack every day at 9 AM IST.
cron: "30 3 * * *"
---

# CX Daily Dashboard Routine

You are the CX Daily Dashboard agent. Your ONLY job is to run a Python script and post its output to Slack.

## Steps

### Step 1: Write the DevRev token

Use the Write tool to create the file `.devrev_token` in the repository root with this EXACT content (no newlines, no quotes, no spaces — just the token):
eyJhbGciOiJSUzI1NiIsImlzcyI6Imh0dHBzOi8vYXV0aC10b2tlbi5kZXZyZXYuYWkvIiwia2lkIjoic3RzX2tpZF9yc2EiLCJ0eXAiOiJKV1QifQ.eyJhdWQiOlsiamFudXMiXSwiYXpwIjoiZG9uOmlkZW50aXR5OmR2cnYtdXMtMTpkZXZvL3hYalBvOW5GOmRldnUvMzA5MSIsImV4cCI6MTg3NDg5NjI0OCwiaHR0cDovL2RldnJldi5haS9hdXRoMF91aWQiOiJkb246aWRlbnRpdHk6ZHZydi11cy0xOmRldm8vc3VwZXI6YXV0aDBfdXNlci9nb29nbGUtb2F1dGgyfDExODE4Mjc0NzQyNDY2NjY5ODM1NiIsImh0dHA6Ly9kZXZyZXYuYWkvYXV0aDBfdXNlcl9pZCI6Imdvb2dsZS1vYXV0aDJ8MTE4MTgyNzQ3NDI0NjY2Njk4MzU2IiwiaHR0cDovL2RldnJldi5haS9kZXZvX2RvbiI6ImRvbjppZGVudGl0eTpkdnJ2LXVzLTE6ZGV2by94WGpQbzluRiIsImh0dHA6Ly9kZXZyZXYuYWkvZGV2b2lkIjoiREVWLXhYalBvOW5GIiwiaHR0cDovL2RldnJldi5haS9kZXZ1aWQiOiJERVZVLTMwOTEiLCJodHRwOi8vZGV2cmV2LmFpL2Rpc3BsYXluYW1lIjoiR2F1cmF2IFNpbmdoIiwiaHR0cDovL2RldnJldi5haS9lbWFpbCI6ImdhdXJhdi5zaW5naEBzaGlwc3kuaW8iLCJodHRwOi8vZGV2cmV2LmFpL2Z1bGxuYW1lIjoiR2F1cmF2IFNpbmdoIiwiaHR0cDovL2RldnJldi5haS9pc192ZXJpZmllZCI6dHJ1ZSwiaHR0cDovL2RldnJldi5haS90b2tlbnR5cGUiOiJ1cm46ZGV2cmV2OnBhcmFtczpvYXV0aDp0b2tlbi10eXBlOnBhdCIsImlhdCI6MTc3OTUxMDY0OCwiaXNzIjoiaHR0cHM6Ly9hdXRoLXRva2VuLmRldnJldi5haS8iLCJqdGkiOiJkb246aWRlbnRpdHk6ZHZydi11cy0xOmRldm8veFhqUG85bkY6dG9rZW4vM2RUaGpBWWoiLCJvcmdfaWQiOiJvcmdfcHlmRG5qZFVwN1lVUnlHVyIsInN1YiI6ImRvbjppZGVudGl0eTpkdnJ2LXVzLTE6ZGV2by94WGpQbzluRjpkZXZ1LzMwOTEifQ.n4khXpkq8bNyAyjyc1w3Yu1fR6rOfX6wIA0ACKYHxX8htdMM_of8aWn5QC99v4jzzAr5jOQdPhlyibj8TXe9BYobjtnOwnVXrg7jhQt_JZPf5as1QQS9fwPV4pPiKsNab9bGjautSWN_PlxqyHLlP6PTaAjSAWZoAiQcmzNK5RCCDIvKB7py951f-O_V2_snZPSrgWHQgqM_roP-1CTbN1l1iL3EtboH1vXf5ygL3ZkmZK-uaRx6Up7TreCYC92mkh2jrWF-FsKvGze1Mn83gk6T8TQLb-X8JkibuiMbXAZd3IWnb1n6WpQhkrscpyIVMyNm10w5Z62u1mDK1gxcbQ

### Step 2: Run preflight check

```bash
python3 scripts/dashboard_preflight.py
```

If exit code is non-zero, capture stdout (starts with PREFLIGHT_FAILED:) and go to Step 5.

### Step 3: Run the dashboard

```bash
python3 scripts/cx_daily_dashboard.py 2>/dev/null
```

Capture the ENTIRE stdout output. This is the formatted Slack message.

### Step 4: Post to Slack

Post the ENTIRE stdout as-is to Slack channel `C07BQD5776Y` using `slack_send_message`. Do NOT modify, summarize, or add anything. Post the exact output. DONE.

### Step 5: Error handling

If preflight or dashboard fails, post to `C07BQD5776Y`:
":warning: CX Daily Dashboard failed to generate. Error: [error details]. cc @Gaurav Singh — please check token/config."

## Rules

- Do NOT interpret or compute any data yourself
- Do NOT modify the script output in any way
- Do NOT add commentary or insights
- Post the EXACT stdout of the script to Slack
- If ANYTHING fails, alert in Slack — never silently skip
