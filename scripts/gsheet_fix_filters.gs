/**
 * PATCH: Fix filters on CX Dashboard tab.
 * Run: fixFilters()
 *
 * What it fixes:
 * 1. All formulas now respect dropdown filters (CX Lead, Account, Cohort, Severity)
 * 2. "Open" correctly excludes resolved/canceled/Closed
 * 3. When dropdown = "All", formula matches everything
 * 4. When dropdown = specific value, formula filters to that value
 */

function fixFilters() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const dash = ss.getSheetByName("CX Dashboard");
  if (!dash) { SpreadsheetApp.getUi().alert("CX Dashboard tab not found"); return; }

  // Find raw data tab
  let rawName = null;
  for (const sheet of ss.getSheets()) {
    if (String(sheet.getRange("A1").getValue()).trim() === "Title") {
      const lastCol = sheet.getLastColumn();
      const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
      if (headers.some(h => String(h).trim() === "Items")) {
        rawName = sheet.getName(); break;
      }
    }
  }
  if (!rawName) { SpreadsheetApp.getUi().alert("Raw data tab not found"); return; }

  // Auto-detect columns
  const raw = ss.getSheetByName(rawName);
  const lastCol = raw.getLastColumn();
  const lastRow = raw.getLastRow();
  const headers = raw.getRange(1, 1, 1, lastCol).getValues()[0];
  const COL = {};
  for (let i = 0; i < headers.length; i++) {
    COL[String(headers[i]).trim()] = i + 1;
  }

  function cl(name) {
    const n = COL[name];
    if (!n) return "ZZ";
    if (n <= 26) return String.fromCharCode(64 + n);
    return String.fromCharCode(64 + Math.ceil(n / 26) - 1) + String.fromCharCode(64 + ((n - 1) % 26) + 1);
  }

  const R = rawName;
  const LR = lastRow;
  const C = {
    subtype: cl("Subtype"), stage: cl("Stage"), severity: cl("Severity.label"),
    cxLead: cl("CX Lead"), account: cl("Account"), cohort: cl("Customer Cohort"),
    pod: cl("POD"), created: cl("Created date"), closed: cl("Close date"),
    metricStatus0: cl("Metric Status[0]"), metricStatus1: cl("Metric Status[1]"),
    completedIn1: cl("Completed In[1]"), resolvedBy: cl("Resolved By"),
    items: cl("Items"),
  };

  // ═══ THE FIX: Base filter includes all dropdowns ═══
  // When dropdown = "All", use "*" (matches everything)
  // When dropdown = specific value, match exactly
  //
  // Filter cells: G3=CX Lead, J3=Account, M3=Cohort, P3=Severity
  //
  // COUNTIFS format:
  //   column, IF($G$3="All","*",$G$3)

  const subF = `'${R}'!${C.subtype}2:${C.subtype}${LR},"Support"`;
  const leadF = `'${R}'!${C.cxLead}2:${C.cxLead}${LR},IF($G$3="All","*",$G$3)`;
  const acctF = `'${R}'!${C.account}2:${C.account}${LR},IF($J$3="All","*",$J$3)`;
  const cohortF = `'${R}'!${C.cohort}2:${C.cohort}${LR},IF($M$3="All","*",$M$3)`;
  const sevF = `'${R}'!${C.severity}2:${C.severity}${LR},IF($P$3="All","*",$P$3)`;
  const base = `${subF},${leadF},${acctF},${cohortF},${sevF}`;

  // Open filter (not resolved, not canceled, not Closed)
  const stgNR = `'${R}'!${C.stage}2:${C.stage}${LR},"<>resolved"`;
  const stgNC = `'${R}'!${C.stage}2:${C.stage}${LR},"<>canceled"`;
  const stgNCl = `'${R}'!${C.stage}2:${C.stage}${LR},"<>Closed"`;
  const openF = `${stgNR},${stgNC},${stgNCl}`;

  // ═══ UPDATE KPI CARDS ═══

  // Card 1: Open (A6)
  dash.getRange("A6").setFormula(`=COUNTIFS(${base},${openF})`);

  // Card 2: Blockers (C6)
  dash.getRange("C6").setFormula(`=COUNTIFS(${base},${openF},'${R}'!${C.severity}2:${C.severity}${LR},"Blocker")`);

  // Card 3: Created in range (E6)
  dash.getRange("E6").setFormula(`=COUNTIFS(${base},'${R}'!${C.created}2:${C.created}${LR},">="&$B$3,'${R}'!${C.created}2:${C.created}${LR},"<="&$D$3,${stgNC})`);

  // Card 4: Resolved in range (G6)
  dash.getRange("G6").setFormula(`=COUNTIFS(${base},'${R}'!${C.closed}2:${C.closed}${LR},">="&$B$3,'${R}'!${C.closed}2:${C.closed}${LR},"<="&$D$3,${stgNC})`);

  // Card 5: FR % (I6)
  dash.getRange("I6").setFormula(
    `=IFERROR(ROUND(COUNTIFS(${base},'${R}'!${C.metricStatus0}2:${C.metricStatus0}${LR},"hit")/COUNTIFS(${base},'${R}'!${C.metricStatus0}2:${C.metricStatus0}${LR},"<>",'${R}'!${C.metricStatus0}2:${C.metricStatus0}${LR},"<>in_progress")*100,0)&"%","N/A")`
  );

  // Card 6: RT % (K6)
  dash.getRange("K6").setFormula(
    `=IFERROR(ROUND(COUNTIFS(${base},'${R}'!${C.metricStatus1}2:${C.metricStatus1}${LR},"hit")/COUNTIFS(${base},'${R}'!${C.metricStatus1}2:${C.metricStatus1}${LR},"<>",'${R}'!${C.metricStatus1}2:${C.metricStatus1}${LR},"<>in_progress")*100,0)&"%","N/A")`
  );

  // Card 8: Resolve Ratio (O6)
  dash.getRange("O6").setFormula(`=IFERROR(ROUND(G6/E6*100,0)&"%","N/A")`);

  SpreadsheetApp.getUi().alert(
    "Filters fixed!\n\n" +
    "KPI cards now respond to all 4 dropdowns:\n" +
    "- G3: CX Lead\n" +
    "- J3: Account\n" +
    "- M3: Cohort\n" +
    "- P3: Severity\n\n" +
    "Set any dropdown to 'All' to see everything,\n" +
    "or select a specific value to filter.\n\n" +
    "Note: Chart data ranges also need updating.\n" +
    "Run fixChartData() next to update chart source formulas."
  );
}

function fixChartData() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const dash = ss.getSheetByName("CX Dashboard");
  if (!dash) return;

  // Find raw data
  let rawName = null;
  for (const sheet of ss.getSheets()) {
    if (String(sheet.getRange("A1").getValue()).trim() === "Title") {
      const lastCol = sheet.getLastColumn();
      const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
      if (headers.some(h => String(h).trim() === "Items")) {
        rawName = sheet.getName(); break;
      }
    }
  }
  if (!rawName) return;

  const raw = ss.getSheetByName(rawName);
  const lastCol = raw.getLastColumn();
  const lastRow = raw.getLastRow();
  const headers = raw.getRange(1, 1, 1, lastCol).getValues()[0];
  const COL = {};
  for (let i = 0; i < headers.length; i++) COL[String(headers[i]).trim()] = i + 1;
  function cl(name) {
    const n = COL[name]; if (!n) return "ZZ";
    if (n <= 26) return String.fromCharCode(64 + n);
    return String.fromCharCode(64 + Math.ceil(n / 26) - 1) + String.fromCharCode(64 + ((n - 1) % 26) + 1);
  }

  const R = rawName, LR = lastRow;
  const C = {
    subtype: cl("Subtype"), stage: cl("Stage"), severity: cl("Severity.label"),
    cxLead: cl("CX Lead"), account: cl("Account"), cohort: cl("Customer Cohort"),
    created: cl("Created date"), closed: cl("Close date"),
    metricStatus0: cl("Metric Status[0]"), metricStatus1: cl("Metric Status[1]"),
    completedIn1: cl("Completed In[1]"), resolvedBy: cl("Resolved By"),
  };

  const subF = `'${R}'!${C.subtype}2:${C.subtype}${LR},"Support"`;
  const leadF = `'${R}'!${C.cxLead}2:${C.cxLead}${LR},IF($G$3="All","*",$G$3)`;
  const acctF = `'${R}'!${C.account}2:${C.account}${LR},IF($J$3="All","*",$J$3)`;
  const cohortF = `'${R}'!${C.cohort}2:${C.cohort}${LR},IF($M$3="All","*",$M$3)`;
  const sevF = `'${R}'!${C.severity}2:${C.severity}${LR},IF($P$3="All","*",$P$3)`;
  const base = `${subF},${leadF},${acctF},${cohortF},${sevF}`;
  const openF = `'${R}'!${C.stage}2:${C.stage}${LR},"<>resolved",'${R}'!${C.stage}2:${C.stage}${LR},"<>canceled",'${R}'!${C.stage}2:${C.stage}${LR},"<>Closed"`;

  // Update helper data ranges (Row 202+)
  const DR = 202;

  // Aging
  const ageBuckets = [7,15,30,60,90];
  for (let i = 0; i < ageBuckets.length; i++) {
    dash.getRange("B"+(DR+1+i)).setFormula(
      `=COUNTIFS(${base},${openF},'${R}'!${C.created}2:${C.created}${LR},"<="&TODAY()-${ageBuckets[i]})`
    );
  }

  // Stages
  const stages = ["queued","work_in_progress","awaiting_customer_response","awaiting_development",
    "awaiting_product_assist","in_development","Reassigned to Customer Support","Reopen"];
  for (let i = 0; i < stages.length; i++) {
    dash.getRange("E"+(DR+1+i)).setFormula(
      `=COUNTIFS(${base},'${R}'!${C.stage}2:${C.stage}${LR},"${stages[i]}")`
    );
  }

  // Severity
  const sevs = ["Blocker","High","Medium","Low"];
  for (let i = 0; i < sevs.length; i++) {
    dash.getRange("H"+(DR+1+i)).setFormula(
      `=COUNTIFS(${base},${openF},'${R}'!${C.severity}2:${C.severity}${LR},"${sevs[i]}")`
    );
  }

  // Who Resolves
  const resolvers = ["Resolved by Support","Resolved by Engineering","Resolved by Product"];
  for (let i = 0; i < resolvers.length; i++) {
    dash.getRange("K"+(DR+1+i)).setFormula(
      `=COUNTIFS(${base},'${R}'!${C.resolvedBy}2:${C.resolvedBy}${LR},"${resolvers[i]}",'${R}'!${C.closed}2:${C.closed}${LR},">="&$B$3,'${R}'!${C.closed}2:${C.closed}${LR},"<="&$D$3)`
    );
  }

  // CX Lead bars (update existing rows)
  const leadStart = DR + 9;
  for (let i = 0; i < 15; i++) {
    const row = leadStart + i;
    const name = dash.getRange("A"+row).getValue();
    if (!name) break;
    dash.getRange("B"+row).setFormula(
      `=COUNTIFS(${base},${openF},'${R}'!${C.cxLead}2:${C.cxLead}${LR},"${name}")`
    );
  }

  // Account bars
  const acctStart = DR + 9;
  for (let i = 0; i < 12; i++) {
    const row = acctStart + i;
    const name = dash.getRange("D"+row).getValue();
    if (!name) break;
    dash.getRange("E"+row).setFormula(
      `=COUNTIFS(${base},${openF},'${R}'!${C.account}2:${C.account}${LR},"${name}")`
    );
  }

  SpreadsheetApp.getUi().alert(
    "Chart data formulas updated!\n\n" +
    "All charts and tables now respond to filters.\n" +
    "Change any dropdown → data recalculates → charts update."
  );
}
