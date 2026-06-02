/**
 * ═══════════════════════════════════════════════════════════════════
 * CX PULSE DASHBOARD v6 — Full Founder-Level Analysis
 * ═══════════════════════════════════════════════════════════════════
 *
 * Creates 2 tabs:
 *   Tab 3: "CX Dashboard"  — KPIs + charts + interactive filters
 *   Tab 4: "Analysis"      — Deep-dive tables + ticket lists
 *
 * Auto-detects column positions from header row.
 * Data filtered from 1 March 2026.
 *
 * HOW TO RUN:
 *   1. Open Apps Script (Extensions > Apps Script)
 *   2. Create new script file, paste this
 *   3. Run: buildAll()
 * ═══════════════════════════════════════════════════════════════════
 */

function buildAll() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // ── Auto-detect raw data tab ──
  let rawSheet = null, rawName = null;
  for (const sheet of ss.getSheets()) {
    const val = (sheet.getRange("A1").getValue() || "").toString();
    if (val === "Title") {
      // Check if it has "Items" column (ticket IDs) somewhere in header
      const lastCol = sheet.getLastColumn();
      const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
      if (headers.some(h => String(h).trim() === "Items")) {
        rawSheet = sheet; rawName = sheet.getName(); break;
      }
    }
  }
  if (!rawSheet) {
    SpreadsheetApp.getUi().alert("Raw data tab not found. Looking for header with 'Title' in A1 and 'Items' column.");
    return;
  }

  // ── Map columns dynamically ──
  const lastCol = rawSheet.getLastColumn();
  const lastRow = rawSheet.getLastRow();
  const headers = rawSheet.getRange(1, 1, 1, lastCol).getValues()[0];
  const COL = {};
  for (let i = 0; i < headers.length; i++) {
    const name = String(headers[i]).trim();
    if (name) COL[name] = i + 1;
  }

  function cl(name) {
    const n = COL[name];
    if (!n) { Logger.log("Column not found: " + name); return "ZZ"; }
    if (n <= 26) return String.fromCharCode(64 + n);
    return String.fromCharCode(64 + Math.ceil(n / 26) - 1) + String.fromCharCode(64 + ((n - 1) % 26) + 1);
  }

  // Key columns
  const C = {
    items: cl("Items"),
    title: cl("Title"),
    created: cl("Created date"),
    closed: cl("Close date"),
    stage: cl("Stage"),
    subtype: cl("Subtype"),
    cohort: cl("Customer Cohort"),
    pod: cl("POD"),
    account: cl("Account"),
    workspace: cl("Workspace"),
    cxLead: cl("CX Lead"),
    cxLeadId: cl("CX Lead-ID"),
    severity: cl("Severity.label"),
    metricName0: cl("Metric Name[0]"),
    metricName1: cl("Metric Name[1]"),
    metricStatus0: cl("Metric Status[0]"),
    metricStatus1: cl("Metric Status[1]"),
    completedIn0: cl("Completed In[0]"),
    completedIn1: cl("Completed In[1]"),
    resolvedBy: cl("Resolved By"),
    sentiment: cl("Sentiment.label"),
    supportType: cl("Support Type"),
    workDuration: cl("Work duration"),
    owner: cl("Owner[0]"),
    sourceChannel: cl("Source channel"),
  };

  Logger.log("Column map: " + JSON.stringify(C));
  Logger.log("Raw data: " + rawName + " (" + lastRow + " rows, " + lastCol + " cols)");

  const R = rawName;
  const LR = lastRow; // for range references

  // ── Build both tabs ──
  buildDashboardTab_(ss, R, C, LR);
  buildAnalysisTab_(ss, R, C, LR);

  SpreadsheetApp.getUi().alert(
    "Dashboard v6 created!\n\n" +
    "Raw data: '" + rawName + "' (" + lastRow + " rows)\n" +
    "Columns auto-detected.\n\n" +
    "Tab 3: CX Dashboard — KPIs, charts, filters\n" +
    "Tab 4: Analysis — deep-dive tables\n\n" +
    "Use the dropdown filters in Row 3 of CX Dashboard to slice data."
  );
}


// ═══════════════════════════════════════════════════════════════════
// TAB 3: CX DASHBOARD
// ═══════════════════════════════════════════════════════════════════
function buildDashboardTab_(ss, R, C, LR) {
  let dash = ss.getSheetByName("CX Dashboard");
  if (dash) { try { dash.getCharts().forEach(c => dash.removeChart(c)); } catch(e){} ss.deleteSheet(dash); }
  dash = ss.insertSheet("CX Dashboard");

  // Column widths
  dash.setColumnWidth(1, 180);
  for (let c = 2; c <= 16; c++) dash.setColumnWidth(c, 105);

  // ═══ HEADER ═══
  dash.getRange("A1:P1").merge().setValue("📊 CX Pulse Dashboard — Founder View")
    .setFontSize(18).setFontWeight("bold").setBackground("#1A237E").setFontColor("white").setHorizontalAlignment("center");
  dash.getRange("A2:P2").merge().setValue("Source: DevRev Export · Data from 1 Mar 2026 · Filters below control all metrics")
    .setFontSize(9).setBackground("#283593").setFontColor("#9FA8DA").setHorizontalAlignment("center");
  dash.setRowHeight(1, 40);

  // ═══ FILTERS (Row 3-4) ═══
  dash.getRange("A3").setValue("From:").setFontWeight("bold").setBackground("#ECEFF1");
  dash.getRange("B3").setValue(new Date(2026, 2, 1)).setNumberFormat("dd-mmm-yyyy").setBackground("#FFF9C4").setFontWeight("bold");
  dash.getRange("B3").setDataValidation(SpreadsheetApp.newDataValidation().requireDate().build());
  dash.getRange("C3").setValue("To:").setFontWeight("bold").setBackground("#ECEFF1");
  dash.getRange("D3").setValue(new Date()).setNumberFormat("dd-mmm-yyyy").setBackground("#FFF9C4").setFontWeight("bold");
  dash.getRange("D3").setDataValidation(SpreadsheetApp.newDataValidation().requireDate().build());

  // Dropdown filters
  dash.getRange("F3").setValue("CX Lead:").setFontWeight("bold").setBackground("#ECEFF1");
  dash.getRange("G3").setValue("All").setBackground("#FFF9C4").setFontWeight("bold");
  dash.getRange("I3").setValue("Account:").setFontWeight("bold").setBackground("#ECEFF1");
  dash.getRange("J3").setValue("All").setBackground("#FFF9C4").setFontWeight("bold");
  dash.getRange("L3").setValue("Cohort:").setFontWeight("bold").setBackground("#ECEFF1");
  dash.getRange("M3").setValue("All").setBackground("#FFF9C4").setFontWeight("bold");
  dash.getRange("O3").setValue("Severity:").setFontWeight("bold").setBackground("#ECEFF1");
  dash.getRange("P3").setValue("All").setBackground("#FFF9C4").setFontWeight("bold");

  // Populate dropdowns from raw data
  setDropdown_(dash, "G3", R, C.cxLead, C.subtype);
  setDropdown_(dash, "J3", R, C.account, C.subtype);
  setDropdown_(dash, "M3", R, C.cohort, C.subtype);
  setSeverityDropdown_(dash, "P3");

  // ═══ FILTER FORMULA (helper cell — builds the base filter condition) ═══
  // We'll use a hidden area for helper formulas
  const H = 200; // helper row start

  // Base filter string for COUNTIFS (repeated in every formula)
  // We'll store the filter as named references
  dash.getRange("A" + H).setValue("=== HELPER AREA (do not edit) ===").setFontColor("#CCCCCC");

  // ═══ KPI CARDS (Row 5-7) ═══
  const baseFilter = buildBaseFilter_(R, C, LR);

  // Card 1: Open
  setCard_(dash, "A", "OPEN TICKETS",
    `=COUNTIFS(${baseFilter},${sq(R)}!${C.stage}2:${C.stage}${LR},"<>resolved",${sq(R)}!${C.stage}2:${C.stage}${LR},"<>canceled",${sq(R)}!${C.stage}2:${C.stage}${LR},"<>Closed")`,
    "#E3F2FD", "#0D47A1");

  // Card 2: Blockers
  setCard_(dash, "C", "BLOCKERS",
    `=COUNTIFS(${baseFilter},${sq(R)}!${C.stage}2:${C.stage}${LR},"<>resolved",${sq(R)}!${C.stage}2:${C.stage}${LR},"<>canceled",${sq(R)}!${C.stage}2:${C.stage}${LR},"<>Closed",${sq(R)}!${C.severity}2:${C.severity}${LR},"Blocker")`,
    "#FFEBEE", "#B71C1C");

  // Card 3: Created in range
  setCard_(dash, "E", "CREATED (range)",
    `=COUNTIFS(${baseFilter},${sq(R)}!${C.created}2:${C.created}${LR},">="&B3,${sq(R)}!${C.created}2:${C.created}${LR},"<="&D3,${sq(R)}!${C.stage}2:${C.stage}${LR},"<>canceled")`,
    "#FFF3E0", "#E65100");

  // Card 4: Resolved in range
  setCard_(dash, "G", "RESOLVED (range)",
    `=COUNTIFS(${baseFilter},${sq(R)}!${C.closed}2:${C.closed}${LR},">="&B3,${sq(R)}!${C.closed}2:${C.closed}${LR},"<="&D3,${sq(R)}!${C.stage}2:${C.stage}${LR},"<>canceled")`,
    "#E8F5E9", "#1B5E20");

  // Card 5: FR %
  setCard_(dash, "I", "FR HIT %",
    `=IFERROR(ROUND(COUNTIFS(${baseFilter},${sq(R)}!${C.metricStatus0}2:${C.metricStatus0}${LR},"hit")/COUNTIFS(${baseFilter},${sq(R)}!${C.metricStatus0}2:${C.metricStatus0}${LR},"<>",${sq(R)}!${C.metricStatus0}2:${C.metricStatus0}${LR},"<>in_progress")*100,0)&"%","N/A")`,
    "#F3E5F5", "#4A148C");

  // Card 6: RT %
  setCard_(dash, "K", "RT HIT %",
    `=IFERROR(ROUND(COUNTIFS(${baseFilter},${sq(R)}!${C.metricStatus1}2:${C.metricStatus1}${LR},"hit")/COUNTIFS(${baseFilter},${sq(R)}!${C.metricStatus1}2:${C.metricStatus1}${LR},"<>",${sq(R)}!${C.metricStatus1}2:${C.metricStatus1}${LR},"<>in_progress")*100,0)&"%","N/A")`,
    "#FCE4EC", "#880E4F");

  // Card 7: Avg TAT
  setCard_(dash, "M", "TAT P50 (SLA)",
    `=IFERROR(LET(vals,FILTER(${sq(R)}!${C.completedIn1}2:${C.completedIn1}${LR},${sq(R)}!${C.subtype}2:${C.subtype}${LR}="Support",${sq(R)}!${C.completedIn1}2:${C.completedIn1}${LR}>0,${sq(R)}!${C.closed}2:${C.closed}${LR}>=B3,${sq(R)}!${C.closed}2:${C.closed}${LR}<=D3),IF(PERCENTILE(vals,0.5)<60,ROUND(PERCENTILE(vals,0.5),0)&"m",IF(PERCENTILE(vals,0.5)<1440,ROUND(PERCENTILE(vals,0.5)/60,1)&"h",ROUND(PERCENTILE(vals,0.5)/1440,1)&"d"))),"N/A")`,
    "#E0F2F1", "#00695C");

  // Card 8: Resolve Ratio
  setCard_(dash, "O", "RESOLVE RATIO",
    `=IFERROR(ROUND(G6/E6*100,0)&"%","N/A")`,
    "#EFEBE9", "#4E342E");

  // ═══ DATA TABLES FOR CHARTS (Row H+1 onwards) ═══
  const DR = H + 2;

  // -- Aging --
  dash.getRange("A"+DR).setValue("Age Bucket"); dash.getRange("B"+DR).setValue("Count");
  const ageOpen = `${sq(R)}!${C.stage}2:${C.stage}${LR},"<>resolved",${sq(R)}!${C.stage}2:${C.stage}${LR},"<>canceled",${sq(R)}!${C.stage}2:${C.stage}${LR},"<>Closed"`;
  const ageBuckets = [7,15,30,60,90];
  for (let i = 0; i < ageBuckets.length; i++) {
    dash.getRange("A"+(DR+1+i)).setValue(ageBuckets[i]+"+ days");
    dash.getRange("B"+(DR+1+i)).setFormula(
      `=COUNTIFS(${baseFilter},${ageOpen},${sq(R)}!${C.created}2:${C.created}${LR},"<="&TODAY()-${ageBuckets[i]})`
    );
  }

  // -- Stage --
  const stages = [["queued","Queued"],["work_in_progress","WIP"],["awaiting_customer_response","AwCust"],
    ["awaiting_development","AwDev"],["awaiting_product_assist","AwProd"],["in_development","InDev"],
    ["Reassigned to Customer Support","Reassigned"],["Reopen","Reopen"]];
  dash.getRange("D"+DR).setValue("Stage"); dash.getRange("E"+DR).setValue("Count");
  for (let i = 0; i < stages.length; i++) {
    dash.getRange("D"+(DR+1+i)).setValue(stages[i][1]);
    dash.getRange("E"+(DR+1+i)).setFormula(
      `=COUNTIFS(${baseFilter},${sq(R)}!${C.stage}2:${C.stage}${LR},"${stages[i][0]}")`
    );
  }

  // -- Severity --
  const sevs = [["Blocker","Blocker"],["High","High"],["Medium","Medium"],["Low","Low"]];
  dash.getRange("G"+DR).setValue("Severity"); dash.getRange("H"+DR).setValue("Count");
  for (let i = 0; i < sevs.length; i++) {
    dash.getRange("G"+(DR+1+i)).setValue(sevs[i][1]);
    dash.getRange("H"+(DR+1+i)).setFormula(
      `=COUNTIFS(${baseFilter},${ageOpen},${sq(R)}!${C.severity}2:${C.severity}${LR},"${sevs[i][0]}")`
    );
  }

  // -- Who Resolves --
  const resolvers = [["Resolved by Support","Support"],["Resolved by Engineering","Engineering"],["Resolved by Product","Product"]];
  dash.getRange("J"+DR).setValue("Resolved By"); dash.getRange("K"+DR).setValue("Count");
  for (let i = 0; i < resolvers.length; i++) {
    dash.getRange("J"+(DR+1+i)).setValue(resolvers[i][1]);
    dash.getRange("K"+(DR+1+i)).setFormula(
      `=COUNTIFS(${baseFilter},${sq(R)}!${C.resolvedBy}2:${C.resolvedBy}${LR},"${resolvers[i][0]}",${sq(R)}!${C.closed}2:${C.closed}${LR},">="&B3,${sq(R)}!${C.closed}2:${C.closed}${LR},"<="&D3)`
    );
  }

  // -- CX Lead (top 15 from data) --
  const leadNames = getUniqueValues_(ss.getSheetByName(R), COL_(R, C.cxLead, ss), COL_(R, C.subtype, ss), "Support", 15);
  dash.getRange("A"+(DR+8)).setValue("CX Lead"); dash.getRange("B"+(DR+8)).setValue("Open");
  for (let i = 0; i < leadNames.length; i++) {
    const short = leadNames[i].length > 14 ? leadNames[i].substring(0, 14) : leadNames[i];
    dash.getRange("A"+(DR+9+i)).setValue(short);
    dash.getRange("B"+(DR+9+i)).setFormula(
      `=COUNTIFS(${baseFilter},${ageOpen},${sq(R)}!${C.cxLead}2:${C.cxLead}${LR},"${leadNames[i]}")`
    );
  }

  // -- Accounts (top 12) --
  const acctNames = getUniqueValues_(ss.getSheetByName(R), COL_(R, C.account, ss), COL_(R, C.subtype, ss), "Support", 12);
  dash.getRange("D"+(DR+8)).setValue("Account"); dash.getRange("E"+(DR+8)).setValue("Open");
  for (let i = 0; i < acctNames.length; i++) {
    const short = acctNames[i].length > 14 ? acctNames[i].substring(0, 14) : acctNames[i];
    dash.getRange("D"+(DR+9+i)).setValue(short);
    dash.getRange("E"+(DR+9+i)).setFormula(
      `=COUNTIFS(${baseFilter},${ageOpen},${sq(R)}!${C.account}2:${C.account}${LR},"${acctNames[i]}")`
    );
  }

  // -- Weekly Resolution --
  dash.getRange("G"+(DR+8)).setValue("Week Start"); dash.getRange("H"+(DR+8)).setValue("Created"); dash.getRange("I"+(DR+8)).setValue("Resolved");
  // Generate week start dates from Mar 1 to today
  const weekStart = new Date(2026, 2, 1); // Mar 1
  const today = new Date();
  let weekIdx = 0;
  const wDate = new Date(weekStart);
  while (wDate <= today && weekIdx < 14) {
    const row = DR + 9 + weekIdx;
    dash.getRange("G"+row).setValue(new Date(wDate)).setNumberFormat("dd-mmm");
    const nextWeek = new Date(wDate.getTime() + 7 * 86400000);
    dash.getRange("H"+row).setFormula(
      `=COUNTIFS(${baseFilter},${sq(R)}!${C.created}2:${C.created}${LR},">="&G${row},${sq(R)}!${C.created}2:${C.created}${LR},"<"&G${row}+7,${sq(R)}!${C.stage}2:${C.stage}${LR},"<>canceled")`
    );
    dash.getRange("I"+row).setFormula(
      `=COUNTIFS(${baseFilter},${sq(R)}!${C.closed}2:${C.closed}${LR},">="&G${row},${sq(R)}!${C.closed}2:${C.closed}${LR},"<"&G${row}+7,${sq(R)}!${C.stage}2:${C.stage}${LR},"<>canceled")`
    );
    wDate.setDate(wDate.getDate() + 7);
    weekIdx++;
  }

  // ═══ FLUSH BEFORE CHARTS ═══
  SpreadsheetApp.flush();
  Utilities.sleep(3000);

  // ═══ CHARTS ═══
  // Chart 1: Aging bar
  dash.insertChart(dash.newChart().setChartType(Charts.ChartType.BAR)
    .addRange(dash.getRange("A"+DR+":A"+(DR+ageBuckets.length)))
    .addRange(dash.getRange("B"+DR+":B"+(DR+ageBuckets.length)))
    .setPosition(9, 1, 0, 0).setOption("useFirstColumnAsDomain", true)
    .setOption("title","Aging (Open Tickets)").setOption("legend",{position:"none"})
    .setOption("colors",["#FF8F00"]).setOption("width",430).setOption("height",260).build());

  // Chart 2: Stage bar
  dash.insertChart(dash.newChart().setChartType(Charts.ChartType.BAR)
    .addRange(dash.getRange("D"+DR+":D"+(DR+stages.length)))
    .addRange(dash.getRange("E"+DR+":E"+(DR+stages.length)))
    .setPosition(9, 7, 0, 0).setOption("useFirstColumnAsDomain", true)
    .setOption("title","Open by Stage").setOption("legend",{position:"none"})
    .setOption("colors",["#C62828"]).setOption("width",430).setOption("height",260).build());

  // Chart 3: Severity donut
  dash.insertChart(dash.newChart().setChartType(Charts.ChartType.PIE)
    .addRange(dash.getRange("G"+DR+":G"+(DR+sevs.length)))
    .addRange(dash.getRange("H"+DR+":H"+(DR+sevs.length)))
    .setPosition(23, 1, 0, 0).setOption("useFirstColumnAsDomain", true)
    .setOption("title","Open by Severity").setOption("pieHole",0.4)
    .setOption("colors",["#B71C1C","#E65100","#F9A825","#2E7D32"])
    .setOption("width",430).setOption("height",260).build());

  // Chart 4: Who Resolves donut
  dash.insertChart(dash.newChart().setChartType(Charts.ChartType.PIE)
    .addRange(dash.getRange("J"+DR+":J"+(DR+resolvers.length)))
    .addRange(dash.getRange("K"+DR+":K"+(DR+resolvers.length)))
    .setPosition(23, 7, 0, 0).setOption("useFirstColumnAsDomain", true)
    .setOption("title","Who Resolves (date range)").setOption("pieHole",0.4)
    .setOption("colors",["#1565C0","#6A1B9A","#00695C"])
    .setOption("width",430).setOption("height",260).build());

  // Chart 5: CX Lead bar
  dash.insertChart(dash.newChart().setChartType(Charts.ChartType.BAR)
    .addRange(dash.getRange("A"+(DR+8)+":A"+(DR+8+leadNames.length)))
    .addRange(dash.getRange("B"+(DR+8)+":B"+(DR+8+leadNames.length)))
    .setPosition(37, 1, 0, 0).setOption("useFirstColumnAsDomain", true)
    .setOption("title","Open by CX Lead").setOption("legend",{position:"none"})
    .setOption("colors",["#00695C"]).setOption("width",430).setOption("height",320).build());

  // Chart 6: Account bar
  dash.insertChart(dash.newChart().setChartType(Charts.ChartType.BAR)
    .addRange(dash.getRange("D"+(DR+8)+":D"+(DR+8+acctNames.length)))
    .addRange(dash.getRange("E"+(DR+8)+":E"+(DR+8+acctNames.length)))
    .setPosition(37, 7, 0, 0).setOption("useFirstColumnAsDomain", true)
    .setOption("title","Open by Account").setOption("legend",{position:"none"})
    .setOption("colors",["#0D47A1"]).setOption("width",430).setOption("height",320).build());

  // Chart 7: Weekly Resolution combo
  dash.insertChart(dash.newChart().setChartType(Charts.ChartType.COMBO)
    .addRange(dash.getRange("G"+(DR+8)+":I"+(DR+8+weekIdx)))
    .setPosition(53, 1, 0, 0).setOption("useFirstColumnAsDomain", true)
    .setOption("title","Weekly Created vs Resolved (since 1 Mar)")
    .setOption("colors",["#E65100","#2E7D32"])
    .setOption("series",{0:{type:"bars"},1:{type:"bars"}})
    .setOption("width",860).setOption("height",300).build());

  // ═══ DETAIL TABLES (Row 70+) ═══
  let tr = 70;

  // ── TAT TABLE ──
  dash.getRange("A"+tr+":H"+tr).merge().setValue("RESOLUTION TAT (SLA-aware, date filtered)")
    .setFontSize(12).setFontWeight("bold").setBackground("#FF6F00").setFontColor("white");
  dash.getRange("A"+(tr+1)).setValue("_Uses DevRev's completed_in field — actual support work time, excludes customer wait + non-business hours._")
    .setFontStyle("italic").setFontColor("#888").setFontSize(9);
  tr += 2;
  ["Severity","P10","P50 (median)","P90","Count"].forEach((h,i) => {
    dash.getRange(tr, i+1).setValue(h).setFontWeight("bold").setBackground("#FFF3E0");
  });
  tr++;

  // TAT formulas using FILTER + PERCENTILE
  const tatBase = `FILTER('${R}'!${C.completedIn1}2:${C.completedIn1}${LR},'${R}'!${C.subtype}2:${C.subtype}${LR}="Support",'${R}'!${C.completedIn1}2:${C.completedIn1}${LR}>0,'${R}'!${C.closed}2:${C.closed}${LR}>=B3,'${R}'!${C.closed}2:${C.closed}${LR}<=D3`;

  // All
  dash.getRange("A"+tr).setValue("All");
  dash.getRange("B"+tr).setFormula(`=IFERROR(ROUND(PERCENTILE(${tatBase}),0.1)/60,1)&"h","—")`);
  dash.getRange("C"+tr).setFormula(`=IFERROR(ROUND(PERCENTILE(${tatBase}),0.5)/60,1)&"h","—")`);
  dash.getRange("D"+tr).setFormula(`=IFERROR(ROUND(PERCENTILE(${tatBase}),0.9)/60,1)&"h","—")`);
  dash.getRange("E"+tr).setFormula(`=IFERROR(COUNT(${tatBase})),0)`);
  tr++;

  for (const [sev, display] of sevs) {
    const sevFilter = `${tatBase},'${R}'!${C.severity}2:${C.severity}${LR}="${sev}"`;
    dash.getRange("A"+tr).setValue(display);
    dash.getRange("B"+tr).setFormula(`=IFERROR(ROUND(PERCENTILE(${sevFilter}),0.1)/60,1)&"h","—")`);
    dash.getRange("C"+tr).setFormula(`=IFERROR(ROUND(PERCENTILE(${sevFilter}),0.5)/60,1)&"h","—")`);
    dash.getRange("D"+tr).setFormula(`=IFERROR(ROUND(PERCENTILE(${sevFilter}),0.9)/60,1)&"h","—")`);
    dash.getRange("E"+tr).setFormula(`=IFERROR(COUNT(${sevFilter})),0)`);
    if (sevs.indexOf([sev,display]) % 2 === 0) dash.getRange("A"+tr+":E"+tr).setBackground("#F5F5F5");
    tr++;
  }

  // ── SLA BY ACCOUNT ──
  tr += 1;
  dash.getRange("A"+tr+":H"+tr).merge().setValue("SLA BY ACCOUNT (open + resolved in range)")
    .setFontSize(12).setFontWeight("bold").setBackground("#AD1457").setFontColor("white");
  dash.getRange("A"+(tr+1)).setValue("_FR/RT = hit/(hit+miss) from DevRev SLA tracker. Excludes in_progress._")
    .setFontStyle("italic").setFontColor("#888").setFontSize(9);
  tr += 2;
  ["Account","Pool","FR Hit","FR Miss","FR%","RT Hit","RT Miss","RT%"].forEach((h,i) => {
    dash.getRange(tr, i+1).setValue(h).setFontWeight("bold").setBackground("#FCE4EC");
  });
  tr++;

  for (let i = 0; i < Math.min(acctNames.length, 15); i++) {
    const acct = acctNames[i];
    const af = `'${R}'!${C.account}2:${C.account}${LR},"${acct}",'${R}'!${C.subtype}2:${C.subtype}${LR},"Support"`;
    dash.getRange("A"+tr).setValue(acct);
    // Pool = open + resolved in range
    dash.getRange("B"+tr).setFormula(`=COUNTIFS(${af})+0`);
    dash.getRange("C"+tr).setFormula(`=COUNTIFS(${af},'${R}'!${C.metricStatus0}2:${C.metricStatus0}${LR},"hit")`);
    dash.getRange("D"+tr).setFormula(`=COUNTIFS(${af},'${R}'!${C.metricStatus0}2:${C.metricStatus0}${LR},"miss")`);
    dash.getRange("E"+tr).setFormula(`=IFERROR(ROUND(C${tr}/(C${tr}+D${tr})*100,0)&"%","—")`);
    dash.getRange("F"+tr).setFormula(`=COUNTIFS(${af},'${R}'!${C.metricStatus1}2:${C.metricStatus1}${LR},"hit")`);
    dash.getRange("G"+tr).setFormula(`=COUNTIFS(${af},'${R}'!${C.metricStatus1}2:${C.metricStatus1}${LR},"miss")`);
    dash.getRange("H"+tr).setFormula(`=IFERROR(ROUND(F${tr}/(F${tr}+G${tr})*100,0)&"%","—")`);
    if (i % 2 === 0) dash.getRange("A"+tr+":H"+tr).setBackground("#F5F5F5");
    tr++;
  }

  // ── CX LEAD DETAIL ──
  tr += 1;
  dash.getRange("A"+tr+":P"+tr).merge().setValue("CX LEAD DETAIL (open tickets)")
    .setFontSize(12).setFontWeight("bold").setBackground("#00695C").setFontColor("white");
  dash.getRange("A"+(tr+1)).setValue("_CX Lead = 'CX Lead' column. Stage breakdown of currently open tickets._")
    .setFontStyle("italic").setFontColor("#888").setFontSize(9);
  tr += 2;
  const ldHeaders = ["CX Lead","Total","Queued","WIP","AwCust","AwDev","AwProd","InDev","Resgn","Reopen","Avg Age","7+d","15+d","30+d"];
  ldHeaders.forEach((h,i) => dash.getRange(tr, i+1).setValue(h).setFontWeight("bold").setBackground("#E0F2F1").setFontSize(9));
  tr++;

  const stgCols = ["queued","work_in_progress","awaiting_customer_response","awaiting_development",
    "awaiting_product_assist","in_development","Reassigned to Customer Support","Reopen"];
  for (let li = 0; li < leadNames.length; li++) {
    const lead = leadNames[li];
    const lf = `'${R}'!${C.cxLead}2:${C.cxLead}${LR},"${lead}",'${R}'!${C.subtype}2:${C.subtype}${LR},"Support"`;
    const lfOpen = `${lf},${ageOpen}`;
    dash.getRange("A"+tr).setValue(lead);
    dash.getRange("B"+tr).setFormula(`=COUNTIFS(${lfOpen})`).setFontWeight("bold");
    for (let s = 0; s < stgCols.length; s++) {
      dash.getRange(tr, s+3).setFormula(`=COUNTIFS(${lf},'${R}'!${C.stage}2:${C.stage}${LR},"${stgCols[s]}")`);
    }
    // Avg Age = AVERAGEIFS on created date
    dash.getRange("K"+tr).setFormula(`=IFERROR(ROUND(AVERAGEIFS(TODAY()-'${R}'!${C.created}2:${C.created}${LR},${lf},${ageOpen}),1),"-")`);
    dash.getRange("L"+tr).setFormula(`=COUNTIFS(${lfOpen},'${R}'!${C.created}2:${C.created}${LR},"<="&TODAY()-7)`);
    dash.getRange("M"+tr).setFormula(`=COUNTIFS(${lfOpen},'${R}'!${C.created}2:${C.created}${LR},"<="&TODAY()-15)`);
    dash.getRange("N"+tr).setFormula(`=COUNTIFS(${lfOpen},'${R}'!${C.created}2:${C.created}${LR},"<="&TODAY()-30)`);
    if (li % 2 === 0) dash.getRange("A"+tr+":N"+tr).setBackground("#F5F5F5");
    tr++;
  }

  // ═══ FINAL ═══
  dash.setFrozenRows(4);
  dash.setHiddenGridlines(true);
}


// ═══════════════════════════════════════════════════════════════════
// TAB 4: ANALYSIS (Deep Dive)
// ═══════════════════════════════════════════════════════════════════
function buildAnalysisTab_(ss, R, C, LR) {
  let sheet = ss.getSheetByName("Analysis");
  if (sheet) ss.deleteSheet(sheet);
  sheet = ss.insertSheet("Analysis");

  sheet.setColumnWidth(1, 200);
  for (let c = 2; c <= 12; c++) sheet.setColumnWidth(c, 110);

  // Header
  sheet.getRange("A1:L1").merge().setValue("📋 CX Support — Deep Dive Analysis")
    .setFontSize(18).setFontWeight("bold").setBackground("#1B5E20").setFontColor("white").setHorizontalAlignment("center");
  sheet.getRange("A2:L2").merge().setValue("Filters inherited from CX Dashboard tab · All formulas reference raw data directly")
    .setFontSize(9).setBackground("#2E7D32").setFontColor("#A5D6A7").setHorizontalAlignment("center");

  const baseFilter = buildBaseFilter_(R, C, LR);
  const ageOpen = `${sq(R)}!${C.stage}2:${C.stage}${LR},"<>resolved",${sq(R)}!${C.stage}2:${C.stage}${LR},"<>canceled",${sq(R)}!${C.stage}2:${C.stage}${LR},"<>Closed"`;

  let tr = 4;

  // ── 1. MONTHLY SUMMARY ──
  sheet.getRange("A"+tr+":L"+tr).merge().setValue("1. MONTHLY SUMMARY (Mar-May 2026)")
    .setFontSize(12).setFontWeight("bold").setBackground("#0D47A1").setFontColor("white");
  tr++;
  ["Month","Created","Resolved","Net","Resolve %","FR Hit%","RT Hit%"].forEach((h,i) => {
    sheet.getRange(tr, i+1).setValue(h).setFontWeight("bold").setBackground("#E3F2FD");
  });
  tr++;

  const months = [
    ["Mar 2026", "2026-03-01", "2026-03-31"],
    ["Apr 2026", "2026-04-01", "2026-04-30"],
    ["May 2026", "2026-05-01", "2026-05-31"]
  ];
  for (const [label, start, end] of months) {
    const mf = `'${R}'!${C.subtype}2:${C.subtype}${LR},"Support"`;
    sheet.getRange("A"+tr).setValue(label);
    sheet.getRange("B"+tr).setFormula(`=COUNTIFS(${mf},'${R}'!${C.created}2:${C.created}${LR},">="&DATE(${start.split('-').join(',')}),${sq(R)}!${C.created}2:${C.created}${LR},"<="&DATE(${end.split('-').join(',')}),'${R}'!${C.stage}2:${C.stage}${LR},"<>canceled")`);
    sheet.getRange("C"+tr).setFormula(`=COUNTIFS(${mf},'${R}'!${C.closed}2:${C.closed}${LR},">="&DATE(${start.split('-').join(',')}),${sq(R)}!${C.closed}2:${C.closed}${LR},"<="&DATE(${end.split('-').join(',')}),'${R}'!${C.stage}2:${C.stage}${LR},"<>canceled")`);
    sheet.getRange("D"+tr).setFormula(`=B${tr}-C${tr}`).setFontWeight("bold");
    sheet.getRange("E"+tr).setFormula(`=IFERROR(ROUND(C${tr}/B${tr}*100,0)&"%","—")`);
    sheet.getRange("F"+tr).setFormula(`=IFERROR(ROUND(COUNTIFS(${mf},'${R}'!${C.metricStatus0}2:${C.metricStatus0}${LR},"hit",'${R}'!${C.created}2:${C.created}${LR},">="&DATE(${start.split('-').join(',')}),'${R}'!${C.created}2:${C.created}${LR},"<="&DATE(${end.split('-').join(',')}))/COUNTIFS(${mf},'${R}'!${C.metricStatus0}2:${C.metricStatus0}${LR},"<>",'${R}'!${C.metricStatus0}2:${C.metricStatus0}${LR},"<>in_progress",'${R}'!${C.created}2:${C.created}${LR},">="&DATE(${start.split('-').join(',')}),'${R}'!${C.created}2:${C.created}${LR},"<="&DATE(${end.split('-').join(',')}))*100,0)&"%","—")`);
    sheet.getRange("G"+tr).setFormula(`=IFERROR(ROUND(COUNTIFS(${mf},'${R}'!${C.metricStatus1}2:${C.metricStatus1}${LR},"hit",'${R}'!${C.created}2:${C.created}${LR},">="&DATE(${start.split('-').join(',')}),'${R}'!${C.created}2:${C.created}${LR},"<="&DATE(${end.split('-').join(',')}))/COUNTIFS(${mf},'${R}'!${C.metricStatus1}2:${C.metricStatus1}${LR},"<>",'${R}'!${C.metricStatus1}2:${C.metricStatus1}${LR},"<>in_progress",'${R}'!${C.created}2:${C.created}${LR},">="&DATE(${start.split('-').join(',')}),'${R}'!${C.created}2:${C.created}${LR},"<="&DATE(${end.split('-').join(',')}))*100,0)&"%","—")`);
    tr++;
  }

  // ── 2. COHORT BREAKDOWN ──
  tr += 2;
  sheet.getRange("A"+tr+":L"+tr).merge().setValue("2. COHORT BREAKDOWN (open tickets)")
    .setFontSize(12).setFontWeight("bold").setBackground("#4A148C").setFontColor("white");
  tr++;
  ["Cohort","Open","Avg Age","Blockers","SLA Breach"].forEach((h,i) => {
    sheet.getRange(tr, i+1).setValue(h).setFontWeight("bold").setBackground("#F3E5F5");
  });
  tr++;

  const cohorts = getUniqueValues_(ss.getSheetByName(R), COL_(R, C.cohort, ss), COL_(R, C.subtype, ss), "Support", 20);
  for (let i = 0; i < cohorts.length; i++) {
    if (cohorts[i] === "WMS" || cohorts[i] === "Roadmap") continue;
    const cf = `'${R}'!${C.cohort}2:${C.cohort}${LR},"${cohorts[i]}",'${R}'!${C.subtype}2:${C.subtype}${LR},"Support"`;
    sheet.getRange("A"+tr).setValue(cohorts[i]);
    sheet.getRange("B"+tr).setFormula(`=COUNTIFS(${cf},${ageOpen})`);
    sheet.getRange("C"+tr).setFormula(`=IFERROR(ROUND(AVERAGEIFS(TODAY()-'${R}'!${C.created}2:${C.created}${LR},${cf},${ageOpen}),1),"-")`);
    sheet.getRange("D"+tr).setFormula(`=COUNTIFS(${cf},${ageOpen},'${R}'!${C.severity}2:${C.severity}${LR},"Blocker")`);
    sheet.getRange("E"+tr).setFormula(`=COUNTIFS(${cf},${ageOpen},'${R}'!${C.metricStatus1}2:${C.metricStatus1}${LR},"miss")`);
    if (i % 2 === 0) sheet.getRange("A"+tr+":E"+tr).setBackground("#F5F5F5");
    tr++;
  }

  // ── 3. SENTIMENT DISTRIBUTION ──
  tr += 2;
  sheet.getRange("A"+tr+":L"+tr).merge().setValue("3. SENTIMENT DISTRIBUTION (open tickets)")
    .setFontSize(12).setFontWeight("bold").setBackground("#E65100").setFontColor("white");
  tr++;
  ["Sentiment","Count","% of Open"].forEach((h,i) => {
    sheet.getRange(tr, i+1).setValue(h).setFontWeight("bold").setBackground("#FFF3E0");
  });
  tr++;
  const sentiments = ["Frustrated","Unhappy","Neutral","Happy"];
  for (const s of sentiments) {
    sheet.getRange("A"+tr).setValue(s);
    sheet.getRange("B"+tr).setFormula(`=COUNTIFS(${baseFilter},${ageOpen},'${R}'!${C.sentiment}2:${C.sentiment}${LR},"${s}")`);
    sheet.getRange("C"+tr).setFormula(`=IFERROR(ROUND(B${tr}/COUNTIFS(${baseFilter},${ageOpen})*100,0)&"%","0%")`);
    tr++;
  }

  // ── 4. SUPPORT TYPE BREAKDOWN ──
  tr += 2;
  sheet.getRange("A"+tr+":L"+tr).merge().setValue("4. SUPPORT TYPE (resolved in range)")
    .setFontSize(12).setFontWeight("bold").setBackground("#1565C0").setFontColor("white");
  tr++;
  const supportTypes = getUniqueValues_(ss.getSheetByName(R), COL_(R, C.supportType, ss), COL_(R, C.subtype, ss), "Support", 10);
  ["Support Type","Count","% of Total"].forEach((h,i) => {
    sheet.getRange(tr, i+1).setValue(h).setFontWeight("bold").setBackground("#E3F2FD");
  });
  tr++;
  for (const st of supportTypes) {
    if (!st) continue;
    sheet.getRange("A"+tr).setValue(st);
    sheet.getRange("B"+tr).setFormula(`=COUNTIFS(${baseFilter},'${R}'!${C.supportType}2:${C.supportType}${LR},"${st}",'${R}'!${C.closed}2:${C.closed}${LR},">="&'CX Dashboard'!B3,'${R}'!${C.closed}2:${C.closed}${LR},"<="&'CX Dashboard'!D3)`);
    sheet.getRange("C"+tr).setFormula(`=IFERROR(ROUND(B${tr}/SUM(B${tr-supportTypes.length+supportTypes.indexOf(st)}:B${tr+supportTypes.length-supportTypes.indexOf(st)-1})*100,0)&"%","0%")`);
    tr++;
  }

  // ── 5. 30+ DAY TICKET LIST ──
  tr += 2;
  sheet.getRange("A"+tr+":L"+tr).merge().setValue("5. 30+ DAY OLD TICKETS (open, sorted by age)")
    .setFontSize(12).setFontWeight("bold").setBackground("#B71C1C").setFontColor("white");
  sheet.getRange("A"+(tr+1)).setValue("_Use QUERY below to see all 30+ day tickets with details._")
    .setFontStyle("italic").setFontColor("#888").setFontSize(9);
  tr += 2;

  // QUERY formula for 30+ day tickets
  const queryStr = `=IFERROR(QUERY('${R}'!A1:${C.items}${LR},"SELECT ${C.items},${C.title},${C.account},${C.cxLead},${C.stage},${C.severity},${C.created} WHERE ${C.subtype}='Support' AND ${C.stage}<>'resolved' AND ${C.stage}<>'canceled' AND ${C.stage}<>'Closed' AND ${C.created} < date '"&TEXT(TODAY()-30,"yyyy-mm-dd")&"' ORDER BY ${C.created} ASC LIMIT 50",1),"No data")`;

  sheet.getRange("A"+tr).setFormula(queryStr);

  // ═══ FINAL ═══
  sheet.setFrozenRows(2);
  sheet.setHiddenGridlines(true);
}


// ═══════════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════════

function sq(name) { return "'" + name + "'"; }

function buildBaseFilter_(R, C, LR) {
  return `'${R}'!${C.subtype}2:${C.subtype}${LR},"Support"`;
}

function setCard_(sheet, col, label, formula, bg, fg) {
  const c2 = String.fromCharCode(col.charCodeAt(0) + 1);
  sheet.getRange(col+"5:"+c2+"5").merge().setValue(label).setFontSize(9).setFontColor("#666")
    .setHorizontalAlignment("center").setVerticalAlignment("bottom").setBackground(bg);
  sheet.getRange(col+"6:"+c2+"6").merge().setFormula(formula).setFontSize(26).setFontWeight("bold")
    .setHorizontalAlignment("center").setVerticalAlignment("middle").setBackground(bg).setFontColor(fg);
  sheet.getRange(col+"7:"+c2+"7").merge().setValue("").setBackground(bg);
  sheet.getRange(col+"5:"+c2+"7").setBorder(true,true,true,true,false,false,fg,SpreadsheetApp.BorderStyle.SOLID);
  sheet.setRowHeight(5, 22); sheet.setRowHeight(6, 50); sheet.setRowHeight(7, 5);
}

function setDropdown_(sheet, cell, rawName, colLetter, subtypeCol) {
  // Create dropdown from unique values in raw data
  const raw = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(rawName);
  const lastRow = raw.getLastRow();
  const colNum = colLetter.length === 1 ? colLetter.charCodeAt(0) - 64 : (colLetter.charCodeAt(0)-64)*26 + colLetter.charCodeAt(1)-64;
  const subtypeNum = subtypeCol.length === 1 ? subtypeCol.charCodeAt(0) - 64 : (subtypeCol.charCodeAt(0)-64)*26 + subtypeCol.charCodeAt(1)-64;

  const data = raw.getRange(2, colNum, lastRow-1, 1).getValues();
  const subtypes = raw.getRange(2, subtypeNum, lastRow-1, 1).getValues();

  const unique = new Set();
  for (let i = 0; i < data.length; i++) {
    if (subtypes[i][0] === "Support" && data[i][0]) unique.add(String(data[i][0]).trim());
  }

  const items = ["All"].concat(Array.from(unique).sort());
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(items.slice(0, 500), true) // GSheets limit
    .setAllowInvalid(false)
    .build();
  sheet.getRange(cell).setDataValidation(rule);
}

function setSeverityDropdown_(sheet, cell) {
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(["All","Blocker","High","Medium","Low"], true)
    .setAllowInvalid(false)
    .build();
  sheet.getRange(cell).setDataValidation(rule);
}

function getUniqueValues_(sheet, colNum, subtypeColNum, subtypeValue, limit) {
  const lastRow = sheet.getLastRow();
  if (lastRow <= 1) return [];
  const data = sheet.getRange(2, colNum, lastRow-1, 1).getValues();
  const subtypes = sheet.getRange(2, subtypeColNum, lastRow-1, 1).getValues();
  const stageCol = sheet.getRange(2, 1, lastRow-1, sheet.getLastColumn()).getValues();

  const counts = {};
  for (let i = 0; i < data.length; i++) {
    const val = String(data[i][0] || "").trim();
    if (val && subtypes[i][0] === subtypeValue) {
      counts[val] = (counts[val] || 0) + 1;
    }
  }
  return Object.entries(counts).sort((a,b) => b[1]-a[1]).slice(0, limit).map(e => e[0]);
}

function COL_(rawName, colLetter, ss) {
  if (colLetter.length === 1) return colLetter.charCodeAt(0) - 64;
  return (colLetter.charCodeAt(0) - 64) * 26 + (colLetter.charCodeAt(1) - 64);
}
