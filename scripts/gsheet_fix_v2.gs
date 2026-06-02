/**
 * FIX v2 — Rewrites all KPI + chart formulas without wildcard bug.
 * Run: fixAll()
 *
 * Fix approach: Instead of "*" wildcard (breaks on empty cells),
 * uses IF() to switch between filtered and unfiltered COUNTIFS.
 *
 * Also adds closed ticket metrics alongside open.
 */

function fixAll() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const dash = ss.getSheetByName("CX Dashboard");
  if (!dash) { SpreadsheetApp.getUi().alert("CX Dashboard not found"); return; }

  // Find raw data
  let rawName = null, raw = null;
  for (const sheet of ss.getSheets()) {
    if (String(sheet.getRange("A1").getValue()).trim() === "Title") {
      const lc = sheet.getLastColumn();
      const h = sheet.getRange(1, 1, 1, lc).getValues()[0];
      if (h.some(x => String(x).trim() === "Items")) { raw = sheet; rawName = sheet.getName(); break; }
    }
  }
  if (!raw) { SpreadsheetApp.getUi().alert("Raw data not found"); return; }

  const LR = raw.getLastRow();
  const headers = raw.getRange(1, 1, 1, raw.getLastColumn()).getValues()[0];
  const COL = {};
  for (let i = 0; i < headers.length; i++) COL[String(headers[i]).trim()] = i + 1;

  function cl(name) {
    const n = COL[name]; if (!n) return "ZZ";
    if (n <= 26) return String.fromCharCode(64 + n);
    return String.fromCharCode(64 + Math.ceil(n / 26) - 1) + String.fromCharCode(64 + ((n - 1) % 26) + 1);
  }

  const R = rawName;
  const c = {
    sub: cl("Subtype"), stg: cl("Stage"), sev: cl("Severity.label"),
    lead: cl("CX Lead"), acct: cl("Account"), coh: cl("Customer Cohort"),
    pod: cl("POD"), crd: cl("Created date"), cls: cl("Close date"),
    ms0: cl("Metric Status[0]"), ms1: cl("Metric Status[1]"),
    ci1: cl("Completed In[1]"), rb: cl("Resolved By"),
    sent: cl("Sentiment.label"), items: cl("Items"),
  };

  Logger.log("Columns: " + JSON.stringify(c));

  // ═══ HELPER: Build COUNTIFS string without wildcard ═══
  // For each dropdown, we add criteria ONLY when not "All"
  // This avoids the "*" bug entirely

  // Range refs
  const subR = `'${R}'!${c.sub}2:${c.sub}${LR}`;
  const stgR = `'${R}'!${c.stg}2:${c.stg}${LR}`;
  const sevR = `'${R}'!${c.sev}2:${c.sev}${LR}`;
  const leadR = `'${R}'!${c.lead}2:${c.lead}${LR}`;
  const acctR = `'${R}'!${c.acct}2:${c.acct}${LR}`;
  const cohR = `'${R}'!${c.coh}2:${c.coh}${LR}`;
  const crdR = `'${R}'!${c.crd}2:${c.crd}${LR}`;
  const clsR = `'${R}'!${c.cls}2:${c.cls}${LR}`;
  const ms0R = `'${R}'!${c.ms0}2:${c.ms0}${LR}`;
  const ms1R = `'${R}'!${c.ms1}2:${c.ms1}${LR}`;
  const ci1R = `'${R}'!${c.ci1}2:${c.ci1}${LR}`;
  const rbR = `'${R}'!${c.rb}2:${c.rb}${LR}`;

  // SUMPRODUCT approach — handles empty cells correctly
  // SUMPRODUCT((condition1)*(condition2)*...)
  // For "All" dropdown: condition = 1 (always true)
  // For specific value: condition = (column = value)

  function sp(extraConditions) {
    // Base: subtype = "Support"
    let parts = [`(${subR}="Support")`];

    // Dropdown filters — only apply when not "All"
    parts.push(`IF($G$3="All",1,(${leadR}=$G$3))`);
    parts.push(`IF($J$3="All",1,(${acctR}=$J$3))`);
    parts.push(`IF($M$3="All",1,(${cohR}=$M$3))`);
    parts.push(`IF($P$3="All",1,(${sevR}=$P$3))`);

    // Extra conditions
    if (extraConditions) {
      for (const ec of extraConditions) parts.push(ec);
    }

    return `SUMPRODUCT(${parts.join("*")})`;
  }

  // ═══ KPI CARDS ═══

  // Card 1: Open Tickets (not resolved/canceled/Closed)
  dash.getRange("A6").setFormula(`=${sp([
    `(${stgR}<>"resolved")`,
    `(${stgR}<>"canceled")`,
    `(${stgR}<>"Closed")`
  ])}`);

  // Card 2: Blockers (open + severity=Blocker)
  dash.getRange("C6").setFormula(`=${sp([
    `(${stgR}<>"resolved")`,
    `(${stgR}<>"canceled")`,
    `(${stgR}<>"Closed")`,
    `(${sevR}="Blocker")`
  ])}`);

  // Card 3: Created in date range (excl canceled)
  dash.getRange("E6").setFormula(`=${sp([
    `(${crdR}>=B3)`,
    `(${crdR}<=D3)`,
    `(${stgR}<>"canceled")`
  ])}`);

  // Card 4: Resolved in date range (only resolved/Closed stage)
  dash.getRange("G6").setFormula(`=${sp([
    `(${clsR}>=B3)`,
    `(${clsR}<=D3)`,
    `((${stgR}="resolved")+(${stgR}="Closed"))`
  ])}`);

  // Card 5: FR Hit %
  const frHit = sp([`(${ms0R}="hit")`]);
  const frTotal = sp([`(${ms0R}<>"")`, `(${ms0R}<>"in_progress")`]);
  dash.getRange("I6").setFormula(`=IFERROR(ROUND(${frHit}/${frTotal}*100,0)&"%","N/A")`);

  // Card 6: RT Hit %
  const rtHit = sp([`(${ms1R}="hit")`]);
  const rtTotal = sp([`(${ms1R}<>"")`, `(${ms1R}<>"in_progress")`]);
  dash.getRange("K6").setFormula(`=IFERROR(ROUND(${rtHit}/${rtTotal}*100,0)&"%","N/A")`);

  // Card 7: TAT P50 — using PERCENTILE on FILTER
  dash.getRange("M6").setFormula(
    `=IFERROR(LET(v,FILTER(${ci1R},${subR}="Support",${ci1R}>0,${clsR}>=B3,${clsR}<=D3),` +
    `p,PERCENTILE(v,0.5),` +
    `IF(p<60,ROUND(p,0)&"m",IF(p<1440,ROUND(p/60,1)&"h",ROUND(p/1440,1)&"d"))),"N/A")`
  );

  // Card 8: Resolve Ratio
  dash.getRange("O6").setFormula(`=IFERROR(ROUND(G6/E6*100,0)&"%","N/A")`);

  Logger.log("KPI cards updated");

  // ═══ HELPER DATA FOR CHARTS (Row 202+) ═══
  const DR = 202;

  // Aging (open tickets)
  const ageBuckets = [7,15,30,60,90];
  for (let i = 0; i < ageBuckets.length; i++) {
    dash.getRange("B"+(DR+1+i)).setFormula(`=${sp([
      `(${stgR}<>"resolved")`,`(${stgR}<>"canceled")`,`(${stgR}<>"Closed")`,
      `(${crdR}<=TODAY()-${ageBuckets[i]})`
    ])}`);
  }

  // Stage (open tickets)
  const stages = ["queued","work_in_progress","awaiting_customer_response","awaiting_development",
    "awaiting_product_assist","in_development","Reassigned to Customer Support","Reopen"];
  for (let i = 0; i < stages.length; i++) {
    dash.getRange("E"+(DR+1+i)).setFormula(`=${sp([`(${stgR}="${stages[i]}")`])}`);
  }

  // Severity (open tickets)
  const sevs = ["Blocker","High","Medium","Low"];
  for (let i = 0; i < sevs.length; i++) {
    dash.getRange("H"+(DR+1+i)).setFormula(`=${sp([
      `(${stgR}<>"resolved")`,`(${stgR}<>"canceled")`,`(${stgR}<>"Closed")`,
      `(${sevR}="${sevs[i]}")`
    ])}`);
  }

  // Who Resolves (date range)
  const resolvers = ["Resolved by Support","Resolved by Engineering","Resolved by Product"];
  for (let i = 0; i < resolvers.length; i++) {
    dash.getRange("K"+(DR+1+i)).setFormula(`=${sp([
      `(${rbR}="${resolvers[i]}")`,
      `(${clsR}>=B3)`,`(${clsR}<=D3)`
    ])}`);
  }

  // CX Lead (open tickets)
  for (let i = 0; i < 15; i++) {
    const row = DR + 9 + i;
    const name = dash.getRange("A"+row).getValue();
    if (!name) break;
    dash.getRange("B"+row).setFormula(`=${sp([
      `(${stgR}<>"resolved")`,`(${stgR}<>"canceled")`,`(${stgR}<>"Closed")`,
      `(${leadR}="${name}")`
    ])}`);
  }

  // Accounts (open tickets)
  for (let i = 0; i < 15; i++) {
    const row = DR + 9 + i;
    const name = dash.getRange("D"+row).getValue();
    if (!name) break;
    dash.getRange("E"+row).setFormula(`=${sp([
      `(${stgR}<>"resolved")`,`(${stgR}<>"canceled")`,`(${stgR}<>"Closed")`,
      `(${acctR}="${name}")`
    ])}`);
  }

  // Weekly resolution (created vs resolved per week)
  for (let i = 0; i < 14; i++) {
    const row = DR + 9 + 16 + i; // offset past CX Lead rows
    const wkCell = dash.getRange("G"+row).getValue();
    if (!wkCell) break;
    // Created in week
    dash.getRange("H"+row).setFormula(`=${sp([
      `(${crdR}>=G${row})`,`(${crdR}<G${row}+7)`,`(${stgR}<>"canceled")`
    ])}`);
    // Resolved in week
    dash.getRange("I"+row).setFormula(`=${sp([
      `(${clsR}>=G${row})`,`(${clsR}<G${row}+7)`,
      `((${stgR}="resolved")+(${stgR}="Closed"))`
    ])}`);
  }

  Logger.log("Chart data updated");

  // ═══ CX LEAD DETAIL TABLE ═══
  // Find the CX Lead Detail section
  const allValues = dash.getRange("A1:A" + dash.getLastRow()).getValues();
  let leadDetailStart = 0;
  for (let i = 0; i < allValues.length; i++) {
    if (String(allValues[i][0]).indexOf("CX LEAD DETAIL") !== -1) {
      leadDetailStart = i + 4; // skip header rows
      break;
    }
  }

  if (leadDetailStart > 0) {
    const stgCols = stages;
    for (let i = 0; i < 15; i++) {
      const row = leadDetailStart + i;
      const name = dash.getRange("A"+row).getValue();
      if (!name) break;

      // Total open
      dash.getRange("B"+row).setFormula(`=${sp([
        `(${stgR}<>"resolved")`,`(${stgR}<>"canceled")`,`(${stgR}<>"Closed")`,
        `(${leadR}="${name}")`
      ])}`).setFontWeight("bold");

      // Per stage
      for (let s = 0; s < stgCols.length; s++) {
        dash.getRange(row, s+3).setFormula(`=SUMPRODUCT((${subR}="Support")*(${leadR}="${name}")*(${stgR}="${stgCols[s]}"))`);
      }

      // Avg Age
      dash.getRange("K"+row).setFormula(
        `=IFERROR(ROUND(SUMPRODUCT((${subR}="Support")*(${leadR}="${name}")*(${stgR}<>"resolved")*(${stgR}<>"canceled")*(${stgR}<>"Closed")*(TODAY()-${crdR}))/SUMPRODUCT((${subR}="Support")*(${leadR}="${name}")*(${stgR}<>"resolved")*(${stgR}<>"canceled")*(${stgR}<>"Closed")*1),1),"-")`
      );

      // 7+, 15+, 30+ days
      for (const [col, days] of [["L",7],["M",15],["N",30]]) {
        dash.getRange(col+row).setFormula(`=SUMPRODUCT((${subR}="Support")*(${leadR}="${name}")*(${stgR}<>"resolved")*(${stgR}<>"canceled")*(${stgR}<>"Closed")*(${crdR}<=TODAY()-${days}))`);
      }
    }
    Logger.log("CX Lead detail updated");
  }

  SpreadsheetApp.getUi().alert(
    "All formulas fixed!\n\n" +
    "Changes:\n" +
    "1. Replaced COUNTIFS+wildcard with SUMPRODUCT (handles empty cells)\n" +
    "2. All 4 dropdowns now work (CX Lead, Account, Cohort, Severity)\n" +
    "3. Date range filter controls Created/Resolved/TAT/Who Resolves\n" +
    "4. CX Lead Load shows correct counts\n\n" +
    "Try changing a dropdown — all numbers + charts should update."
  );
}
