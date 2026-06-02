/**
 * CX Pulse Dashboard v5 — Works with the existing Shipsy Support Dashboard raw data.
 *
 * TWO functions:
 *   1. patchRawData()     — adds missing "Resolved By" column (AF) to Raw Data tab. Run ONCE.
 *   2. createDashboard()  — builds the visual dashboard tab with charts + tables.
 *
 * HOW TO USE:
 *   1. Open Apps Script editor (Extensions > Apps Script)
 *   2. Create a new script file (+ > Script), name it "dashboard"
 *   3. Paste this entire file
 *   4. Run patchRawData first (one-time fix)
 *   5. Run createDashboard to build the dashboard
 */


// ═══════════════════════════════════════════════
// STEP 1: PATCH — adds "Resolved By" column
// ═══════════════════════════════════════════════

function patchRawData() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const raw = ss.getSheetByName("Raw Data");
  if (!raw) { SpreadsheetApp.getUi().alert("'Raw Data' tab not found"); return; }

  const lastCol = raw.getLastColumn();
  const header = raw.getRange(1, 1, 1, lastCol).getValues()[0];

  // Check if already patched
  if (header.indexOf("Resolved By") !== -1) {
    SpreadsheetApp.getUi().alert("'Resolved By' column already exists at column " + (header.indexOf("Resolved By") + 1));
    return;
  }

  // Add header in next column
  const newCol = lastCol + 1;
  raw.getRange(1, newCol).setValue("Resolved By").setFontWeight("bold").setBackground("#1F4E79").setFontColor("#FFFFFF");

  // Read the Resolution column (Y = col 25) to derive Resolved By
  // The enrichment has t.resolvedBy = cf.tnt__resolved_by but it's not written.
  // We can't access it from the sheet — but we CAN refetch it from DevRev.
  // Simpler: just add the column header now. The NEXT daily run of the main script
  // will need a 1-line edit to populate it.
  //
  // For NOW, let's backfill from the existing data using the Resolution column heuristic:
  const lastRow = raw.getLastRow();
  if (lastRow <= 1) { SpreadsheetApp.getUi().alert("No data rows to patch"); return; }

  const data = raw.getRange(2, 1, lastRow - 1, lastCol).getValues();
  const stateCol = header.indexOf("State");       // J = "open"/"closed"
  const stageCol = header.indexOf("Stage");        // I
  const resCol = header.indexOf("Resolution");     // Y

  const values = [];
  for (let i = 0; i < data.length; i++) {
    const state = (data[i][stateCol] || "").toString().toLowerCase();
    const resolution = (data[i][resCol] || "").toString().toLowerCase();

    let resolvedBy = "";
    if (state === "closed" || state === "resolved") {
      // Heuristic from resolution text
      if (resolution.indexOf("engineering") !== -1 || resolution.indexOf("code") !== -1 || resolution.indexOf("bug fix") !== -1) {
        resolvedBy = "Resolved by Engineering";
      } else if (resolution.indexOf("product") !== -1 || resolution.indexOf("feature") !== -1 || resolution.indexOf("roadmap") !== -1) {
        resolvedBy = "Resolved by Product";
      } else if (resolution) {
        resolvedBy = "Resolved by Support";
      }
    }
    values.push([resolvedBy]);
  }
  raw.getRange(2, newCol, values.length, 1).setValues(values);

  SpreadsheetApp.getUi().alert(
    "Patch complete!\n\n" +
    "Added 'Resolved By' at column " + newCol + " (" + String.fromCharCode(64 + newCol) + ")\n" +
    "Backfilled " + values.filter(v => v[0]).length + " resolved tickets.\n\n" +
    "IMPORTANT: To make this permanent, add this line to writeRawDataSheet_() in the main script:\n" +
    "After 't.devrevUrl' in the rows.push() array, add: t.resolvedBy || ''"
  );
}


// ═══════════════════════════════════════════════
// STEP 2: DASHBOARD
// ═══════════════════════════════════════════════

function createDashboard() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const raw = ss.getSheetByName("Raw Data");
  if (!raw) { SpreadsheetApp.getUi().alert("'Raw Data' tab not found"); return; }

  // Detect column positions dynamically
  const lastCol = raw.getLastColumn();
  const headerRow = raw.getRange(1, 1, 1, lastCol).getValues()[0];
  const COL = {};
  for (let i = 0; i < headerRow.length; i++) {
    const name = (headerRow[i] || "").toString().trim();
    COL[name] = i + 1; // 1-indexed
  }

  // Column letter helper
  function colLetter(name) {
    const n = COL[name];
    if (!n) return "ZZ"; // fallback
    if (n <= 26) return String.fromCharCode(64 + n);
    return String.fromCharCode(64 + Math.floor((n - 1) / 26)) + String.fromCharCode(65 + (n - 1) % 26);
  }

  const R = "Raw Data";
  const cOpen = colLetter("Open?");         // K
  const cSev = colLetter("Severity");       // L
  const cAge = colLetter("Age (days)");     // M
  const cCreated = colLetter("Created");    // N
  const cClosed = colLetter("Closed");      // P
  const cStage = colLetter("Stage");        // I
  const cState = colLetter("State");        // J
  const cLead = colLetter("CX Lead (Effective)"); // E
  const cCust = colLetter("Customer");      // C
  const cSLA = colLetter("SLA Breached?");  // S
  const cPod = colLetter("Pod");            // Z
  const cResolvedBy = colLetter("Resolved By"); // AF (after patch)
  const cSentiment = colLetter("Sentiment");
  const cURL = colLetter("DevRev URL");

  Logger.log("Column map: Open=" + cOpen + " Sev=" + cSev + " Age=" + cAge + " Created=" + cCreated +
    " Closed=" + cClosed + " Stage=" + cStage + " Lead=" + cLead + " Cust=" + cCust +
    " SLA=" + cSLA + " ResolvedBy=" + cResolvedBy);

  // Delete existing dashboard
  let dash = ss.getSheetByName("CX Pulse Dashboard");
  if (dash) { dash.getCharts().forEach(c => dash.removeChart(c)); ss.deleteSheet(dash); }
  dash = ss.insertSheet("CX Pulse Dashboard");

  // Column widths
  dash.setColumnWidth(1, 200);
  for (let c = 2; c <= 14; c++) dash.setColumnWidth(c, 110);

  // ═══ HEADER ═══
  dash.getRange("A1:N1").merge().setValue("📊 CX Pulse Dashboard").setFontSize(20).setFontWeight("bold").setBackground("#1A237E").setFontColor("white").setHorizontalAlignment("center");
  dash.getRange("A2:N2").merge().setValue("Source: Raw Data tab · TMS Support tickets · Refreshes daily at 8 AM IST").setFontSize(10).setBackground("#283593").setFontColor("#9FA8DA").setHorizontalAlignment("center");
  dash.setRowHeight(1, 45); dash.setRowHeight(2, 25);

  // ═══ DATE FILTER ═══
  dash.getRange("A3:B3").merge().setValue("📅 Date Filter:").setFontWeight("bold").setBackground("#ECEFF1").setHorizontalAlignment("right");
  dash.getRange("C3").setValue("From:").setBackground("#ECEFF1").setHorizontalAlignment("right");
  dash.getRange("D3").setValue(new Date(Date.now() - 7*86400000)).setNumberFormat("dd-mmm-yyyy").setBackground("#FFF9C4").setFontWeight("bold");
  dash.getRange("D3").setDataValidation(SpreadsheetApp.newDataValidation().requireDate().build());
  dash.getRange("E3").setValue("To:").setBackground("#ECEFF1").setHorizontalAlignment("right");
  dash.getRange("F3").setValue(new Date()).setNumberFormat("dd-mmm-yyyy").setBackground("#FFF9C4").setFontWeight("bold");
  dash.getRange("F3").setDataValidation(SpreadsheetApp.newDataValidation().requireDate().build());
  dash.getRange("G3:N3").merge().setValue("  ↑ Affects: Resolution Rate, TAT, Who Resolves").setFontColor("#999").setBackground("#ECEFF1").setFontSize(9);

  // ═══ KPI CARDS (Row 5-7) ═══
  const cards = [
    {label:"OPEN TICKETS", col:"A", formula:`=COUNTIF('${R}'!${cOpen}:${cOpen},"OPEN")`, bg:"#E3F2FD", fg:"#0D47A1"},
    {label:"BLOCKERS", col:"C", formula:`=COUNTIFS('${R}'!${cOpen}:${cOpen},"OPEN",'${R}'!${cSev}:${cSev},"blocker")`, bg:"#FFEBEE", fg:"#B71C1C"},
    {label:"QUEUED", col:"E", formula:`=COUNTIFS('${R}'!${cOpen}:${cOpen},"OPEN",'${R}'!${cStage}:${cStage},"queued")`, bg:"#FFF3E0", fg:"#E65100"},
    {label:"SLA BREACHED", col:"G", formula:`=COUNTIFS('${R}'!${cOpen}:${cOpen},"OPEN",'${R}'!${cSLA}:${cSLA},"YES")`, bg:"#FCE4EC", fg:"#880E4F"},
    {label:"AVG AGE (days)", col:"I", formula:`=ROUND(AVERAGEIF('${R}'!${cOpen}:${cOpen},"OPEN",'${R}'!${cAge}:${cAge}),1)`, bg:"#E8F5E9", fg:"#1B5E20"},
    {label:"RESOLVE RATIO", col:"K", formula:`=IFERROR(ROUND(COUNTIFS('${R}'!${cClosed}:${cClosed},">="&D3,'${R}'!${cClosed}:${cClosed},"<="&F3,'${R}'!${cOpen}:${cOpen},"CLOSED")/COUNTIFS('${R}'!${cCreated}:${cCreated},">="&D3,'${R}'!${cCreated}:${cCreated},"<="&F3)*100,0)&"%","N/A")`, bg:"#F3E5F5", fg:"#4A148C"},
  ];
  for (const card of cards) {
    const c1 = card.col, c2 = String.fromCharCode(c1.charCodeAt(0)+1);
    dash.getRange(c1+"5:"+c2+"5").merge().setValue(card.label).setFontSize(9).setFontColor("#666").setHorizontalAlignment("center").setVerticalAlignment("bottom").setBackground(card.bg);
    dash.getRange(c1+"6:"+c2+"6").merge().setFormula(card.formula).setFontSize(30).setFontWeight("bold").setHorizontalAlignment("center").setVerticalAlignment("middle").setBackground(card.bg).setFontColor(card.fg);
    dash.getRange(c1+"7:"+c2+"7").merge().setValue("").setBackground(card.bg);
    dash.getRange(c1+"5:"+c2+"7").setBorder(true,true,true,true,false,false,card.fg,SpreadsheetApp.BorderStyle.SOLID);
  }
  dash.setRowHeight(5, 22); dash.setRowHeight(6, 55); dash.setRowHeight(7, 5);

  // ═══ DATA AREA (Row 100+) for charts ═══
  const DR = 100;

  // Aging
  const ageBuckets = [7,15,30,60,90];
  dash.getRange("A"+DR).setValue("Age Bucket"); dash.getRange("B"+DR).setValue("Count");
  for (let i=0;i<ageBuckets.length;i++) {
    dash.getRange("A"+(DR+1+i)).setValue(ageBuckets[i]+"+ days");
    dash.getRange("B"+(DR+1+i)).setFormula(`=COUNTIFS('${R}'!${cOpen}:${cOpen},"OPEN",'${R}'!${cAge}:${cAge},">="&${ageBuckets[i]})`);
  }

  // Stage
  const stageData = [["queued","Queued"],["work_in_progress","WIP"],["awaiting_customer_response","AwCust"],["awaiting_development","AwDev"],["awaiting_product_assist","AwProd"],["in_development","InDev"],["Reassigned to Customer Support","Reassigned"],["Reopen","Reopen"]];
  dash.getRange("D"+DR).setValue("Stage"); dash.getRange("E"+DR).setValue("Count");
  for (let i=0;i<stageData.length;i++) {
    dash.getRange("D"+(DR+1+i)).setValue(stageData[i][1]);
    dash.getRange("E"+(DR+1+i)).setFormula(`=COUNTIFS('${R}'!${cStage}:${cStage},"${stageData[i][0]}",'${R}'!${cOpen}:${cOpen},"OPEN")`);
  }

  // Severity
  const sevs = [["blocker","Blocker"],["high","High"],["medium","Medium"],["low","Low"]];
  dash.getRange("G"+DR).setValue("Severity"); dash.getRange("H"+DR).setValue("Count");
  for (let i=0;i<sevs.length;i++) {
    dash.getRange("G"+(DR+1+i)).setValue(sevs[i][1]);
    dash.getRange("H"+(DR+1+i)).setFormula(`=COUNTIFS('${R}'!${cSev}:${cSev},"${sevs[i][0]}",'${R}'!${cOpen}:${cOpen},"OPEN")`);
  }

  // Who Resolves
  const resolvers = [["Resolved by Support","Support"],["Resolved by Engineering","Engineering"],["Resolved by Product","Product"]];
  dash.getRange("J"+DR).setValue("Resolved By"); dash.getRange("K"+DR).setValue("Count");
  for (let i=0;i<resolvers.length;i++) {
    dash.getRange("J"+(DR+1+i)).setValue(resolvers[i][1]);
    dash.getRange("K"+(DR+1+i)).setFormula(`=COUNTIFS('${R}'!${cResolvedBy}:${cResolvedBy},"${resolvers[i][0]}",'${R}'!${cClosed}:${cClosed},">="&D3,'${R}'!${cClosed}:${cClosed},"<="&F3)`);
  }

  // CX Leads
  const leads = getLead_names_(raw, COL["CX Lead (Effective)"]);
  dash.getRange("A"+(DR+8)).setValue("CX Lead"); dash.getRange("B"+(DR+8)).setValue("Open");
  for (let i=0;i<leads.length;i++) {
    dash.getRange("A"+(DR+9+i)).setValue(leads[i].length > 12 ? leads[i].substring(0,12) : leads[i]);
    dash.getRange("B"+(DR+9+i)).setFormula(`=COUNTIFS('${R}'!${cLead}:${cLead},"${leads[i]}",'${R}'!${cOpen}:${cOpen},"OPEN")`);
  }

  // Accounts
  const accounts = getTop_accounts_(raw, COL["Customer"], COL["Open?"]);
  dash.getRange("D"+(DR+8)).setValue("Account"); dash.getRange("E"+(DR+8)).setValue("Open");
  for (let i=0;i<accounts.length;i++) {
    dash.getRange("D"+(DR+9+i)).setValue(accounts[i].length > 15 ? accounts[i].substring(0,15) : accounts[i]);
    dash.getRange("E"+(DR+9+i)).setFormula(`=COUNTIFS('${R}'!${cCust}:${cCust},"${accounts[i]}",'${R}'!${cOpen}:${cOpen},"OPEN")`);
  }

  // Daily resolution (7 days)
  dash.getRange("G"+(DR+8)).setValue("Date"); dash.getRange("H"+(DR+8)).setValue("Created"); dash.getRange("I"+(DR+8)).setValue("Resolved");
  for (let i=0;i<7;i++) {
    dash.getRange("G"+(DR+9+i)).setFormula(`=F3-${7-i}`).setNumberFormat("dd-mmm");
    dash.getRange("H"+(DR+9+i)).setFormula(`=COUNTIFS('${R}'!${cCreated}:${cCreated},">="&G${DR+9+i},'${R}'!${cCreated}:${cCreated},"<"&G${DR+9+i}+1)`);
    dash.getRange("I"+(DR+9+i)).setFormula(`=COUNTIFS('${R}'!${cClosed}:${cClosed},">="&G${DR+9+i},'${R}'!${cClosed}:${cClosed},"<"&G${DR+9+i}+1,'${R}'!${cOpen}:${cOpen},"CLOSED")`);
  }

  // ═══ FLUSH ═══
  SpreadsheetApp.flush();
  Utilities.sleep(3000);

  // ═══ CHARTS ═══
  // Chart 1: Aging
  dash.insertChart(dash.newChart().setChartType(Charts.ChartType.BAR)
    .addRange(dash.getRange("A"+DR+":A"+(DR+ageBuckets.length)))
    .addRange(dash.getRange("B"+DR+":B"+(DR+ageBuckets.length)))
    .setPosition(9, 1, 0, 0).setOption("useFirstColumnAsDomain",true)
    .setOption("title","Aging Tickets (Open)").setOption("legend",{position:"none"})
    .setOption("colors",["#FF8F00"]).setOption("width",430).setOption("height",260).build());

  // Chart 2: Stage
  dash.insertChart(dash.newChart().setChartType(Charts.ChartType.BAR)
    .addRange(dash.getRange("D"+DR+":D"+(DR+stageData.length)))
    .addRange(dash.getRange("E"+DR+":E"+(DR+stageData.length)))
    .setPosition(9, 7, 0, 0).setOption("useFirstColumnAsDomain",true)
    .setOption("title","Open by Stage").setOption("legend",{position:"none"})
    .setOption("colors",["#C62828"]).setOption("width",430).setOption("height",260).build());

  // Chart 3: Severity donut
  dash.insertChart(dash.newChart().setChartType(Charts.ChartType.PIE)
    .addRange(dash.getRange("G"+DR+":G"+(DR+sevs.length)))
    .addRange(dash.getRange("H"+DR+":H"+(DR+sevs.length)))
    .setPosition(23, 1, 0, 0).setOption("useFirstColumnAsDomain",true)
    .setOption("title","Open by Severity").setOption("pieHole",0.4)
    .setOption("colors",["#B71C1C","#E65100","#F9A825","#2E7D32"])
    .setOption("width",430).setOption("height",260).build());

  // Chart 4: Who Resolves donut
  dash.insertChart(dash.newChart().setChartType(Charts.ChartType.PIE)
    .addRange(dash.getRange("J"+DR+":J"+(DR+resolvers.length)))
    .addRange(dash.getRange("K"+DR+":K"+(DR+resolvers.length)))
    .setPosition(23, 7, 0, 0).setOption("useFirstColumnAsDomain",true)
    .setOption("title","Who Resolves (date range)").setOption("pieHole",0.4)
    .setOption("colors",["#1565C0","#6A1B9A","#00695C"])
    .setOption("width",430).setOption("height",260).build());

  // Chart 5: CX Lead bar
  dash.insertChart(dash.newChart().setChartType(Charts.ChartType.BAR)
    .addRange(dash.getRange("A"+(DR+8)+":A"+(DR+8+leads.length)))
    .addRange(dash.getRange("B"+(DR+8)+":B"+(DR+8+leads.length)))
    .setPosition(37, 1, 0, 0).setOption("useFirstColumnAsDomain",true)
    .setOption("title","Open by CX Lead").setOption("legend",{position:"none"})
    .setOption("colors",["#00695C"]).setOption("width",430).setOption("height",300).build());

  // Chart 6: Account bar
  dash.insertChart(dash.newChart().setChartType(Charts.ChartType.BAR)
    .addRange(dash.getRange("D"+(DR+8)+":D"+(DR+8+accounts.length)))
    .addRange(dash.getRange("E"+(DR+8)+":E"+(DR+8+accounts.length)))
    .setPosition(37, 7, 0, 0).setOption("useFirstColumnAsDomain",true)
    .setOption("title","Open by Account").setOption("legend",{position:"none"})
    .setOption("colors",["#0D47A1"]).setOption("width",430).setOption("height",300).build());

  // Chart 7: Daily Created vs Resolved combo
  dash.insertChart(dash.newChart().setChartType(Charts.ChartType.COMBO)
    .addRange(dash.getRange("G"+(DR+8)+":I"+(DR+8+7)))
    .setPosition(53, 1, 0, 0).setOption("useFirstColumnAsDomain",true)
    .setOption("title","Daily Created vs Resolved (7 days)")
    .setOption("colors",["#E65100","#2E7D32"])
    .setOption("series",{0:{type:"bars"},1:{type:"bars"}})
    .setOption("width",860).setOption("height",280).build());

  // ═══ DETAIL TABLES (Row 72+) ═══
  let tr = 72;

  // ── RESOLUTION TAT ──
  dash.getRange("A"+tr+":G"+tr).merge().setValue("RESOLUTION TAT (date filtered)").setFontSize(12).setFontWeight("bold").setBackground("#FF6F00").setFontColor("white");
  tr++;
  ["Severity","P10 (days)","P50 (days)","P90 (days)","Count"].forEach((h,i) => {
    dash.getRange(tr, i+1).setValue(h).setFontWeight("bold").setBackground("#FFF3E0");
  });
  tr++;

  // TAT = Closed - Created (in days). FILTER for closed tickets in date range.
  const tatBase = `FILTER('${R}'!${cClosed}:${cClosed}-'${R}'!${cCreated}:${cCreated},'${R}'!${cOpen}:${cOpen}="CLOSED",'${R}'!${cClosed}:${cClosed}>=D3,'${R}'!${cClosed}:${cClosed}<=F3`;

  dash.getRange("A"+tr).setValue("All");
  dash.getRange("B"+tr).setFormula(`=IFERROR(ROUND(PERCENTILE(${tatBase}),0.1),"—")`);
  dash.getRange("C"+tr).setFormula(`=IFERROR(ROUND(PERCENTILE(${tatBase}),0.5),"—")`);
  dash.getRange("D"+tr).setFormula(`=IFERROR(ROUND(PERCENTILE(${tatBase}),0.9),"—")`);
  dash.getRange("E"+tr).setFormula(`=IFERROR(COUNT(${tatBase})),0)`);
  tr++;

  for (const [sApi, sDisplay] of sevs) {
    const sevFilter = `${tatBase},'${R}'!${cSev}:${cSev}="${sApi}"`;
    dash.getRange("A"+tr).setValue(sDisplay);
    dash.getRange("B"+tr).setFormula(`=IFERROR(ROUND(PERCENTILE(${sevFilter}),0.1),"—")`);
    dash.getRange("C"+tr).setFormula(`=IFERROR(ROUND(PERCENTILE(${sevFilter}),0.5),"—")`);
    dash.getRange("D"+tr).setFormula(`=IFERROR(ROUND(PERCENTILE(${sevFilter}),0.9),"—")`);
    dash.getRange("E"+tr).setFormula(`=IFERROR(COUNT(${sevFilter})),0)`);
    if (sevs.map(s=>s[0]).indexOf(sApi) % 2 === 0) dash.getRange("A"+tr+":E"+tr).setBackground("#F5F5F5");
    tr++;
  }

  // ── DAILY RESOLUTION RATE ──
  tr += 1;
  dash.getRange("A"+tr+":G"+tr).merge().setValue("DAILY RESOLUTION RATE (last 7 days)").setFontSize(12).setFontWeight("bold").setBackground("#6A1B9A").setFontColor("white");
  tr++;
  ["Date","Created","Resolved","Net"].forEach((h,i) => {
    dash.getRange(tr, i+1).setValue(h).setFontWeight("bold").setBackground("#F3E5F5");
  });
  tr++;
  const drStart = tr;
  for (let i=0;i<7;i++) {
    dash.getRange("A"+tr).setFormula(`=F3-${7-i}`).setNumberFormat("dd-mmm");
    dash.getRange("B"+tr).setFormula(`=COUNTIFS('${R}'!${cCreated}:${cCreated},">="&A${tr},'${R}'!${cCreated}:${cCreated},"<"&A${tr}+1)`);
    dash.getRange("C"+tr).setFormula(`=COUNTIFS('${R}'!${cClosed}:${cClosed},">="&A${tr},'${R}'!${cClosed}:${cClosed},"<"&A${tr}+1,'${R}'!${cOpen}:${cOpen},"CLOSED")`);
    dash.getRange("D"+tr).setFormula(`=B${tr}-C${tr}`).setFontWeight("bold");
    if (i%2===0) dash.getRange("A"+tr+":D"+tr).setBackground("#F5F5F5");
    tr++;
  }
  dash.getRange("A"+tr).setValue("TOTAL").setFontWeight("bold").setBackground("#E8EAF6");
  dash.getRange("B"+tr).setFormula(`=SUM(B${drStart}:B${tr-1})`).setFontWeight("bold").setBackground("#E8EAF6");
  dash.getRange("C"+tr).setFormula(`=SUM(C${drStart}:C${tr-1})`).setFontWeight("bold").setBackground("#E8EAF6");
  dash.getRange("D"+tr).setFormula(`=B${tr}-C${tr}`).setFontWeight("bold").setBackground("#E8EAF6");
  tr++;

  // ── SLA BY ACCOUNT ──
  tr += 1;
  dash.getRange("A"+tr+":G"+tr).merge().setValue("SLA BREACH BY ACCOUNT (open)").setFontSize(12).setFontWeight("bold").setBackground("#AD1457").setFontColor("white");
  tr++;
  ["Account","Open","SLA Breached","Breach %","Avg Age"].forEach((h,i) => {
    dash.getRange(tr, i+1).setValue(h).setFontWeight("bold").setBackground("#FCE4EC");
  });
  tr++;
  for (let i=0;i<accounts.length;i++) {
    const acct = accounts[i];
    dash.getRange("A"+tr).setValue(acct);
    dash.getRange("B"+tr).setFormula(`=COUNTIFS('${R}'!${cCust}:${cCust},"${acct}",'${R}'!${cOpen}:${cOpen},"OPEN")`);
    dash.getRange("C"+tr).setFormula(`=COUNTIFS('${R}'!${cCust}:${cCust},"${acct}",'${R}'!${cOpen}:${cOpen},"OPEN",'${R}'!${cSLA}:${cSLA},"YES")`);
    dash.getRange("D"+tr).setFormula(`=IFERROR(ROUND(C${tr}/B${tr}*100,0)&"%","0%")`);
    dash.getRange("E"+tr).setFormula(`=IFERROR(ROUND(AVERAGEIFS('${R}'!${cAge}:${cAge},'${R}'!${cCust}:${cCust},"${acct}",'${R}'!${cOpen}:${cOpen},"OPEN"),1),"-")`);
    if (i%2===0) dash.getRange("A"+tr+":E"+tr).setBackground("#F5F5F5");
    tr++;
  }

  // ── CX LEAD DETAIL ──
  tr += 1;
  dash.getRange("A"+tr+":N"+tr).merge().setValue("CX LEAD DETAIL (open tickets)").setFontSize(12).setFontWeight("bold").setBackground("#00695C").setFontColor("white");
  tr++;
  const lHeaders = ["CX Lead","Total","Queued","WIP","AwCust","AwDev","AwProd","InDev","Resgn","Reopen","Avg Age","SLA Miss","7+ days","30+ days"];
  lHeaders.forEach((h,i) => dash.getRange(tr,i+1).setValue(h).setFontWeight("bold").setBackground("#E0F2F1").setFontSize(9));
  tr++;
  const stgCols = ["queued","work_in_progress","awaiting_customer_response","awaiting_development","awaiting_product_assist","in_development","Reassigned to Customer Support","Reopen"];
  for (let li=0;li<leads.length;li++) {
    const lead = leads[li];
    dash.getRange("A"+tr).setValue(lead);
    dash.getRange("B"+tr).setFormula(`=COUNTIFS('${R}'!${cLead}:${cLead},"${lead}",'${R}'!${cOpen}:${cOpen},"OPEN")`).setFontWeight("bold");
    for (let s=0;s<stgCols.length;s++) {
      dash.getRange(tr,s+3).setFormula(`=COUNTIFS('${R}'!${cLead}:${cLead},"${lead}",'${R}'!${cOpen}:${cOpen},"OPEN",'${R}'!${cStage}:${cStage},"${stgCols[s]}")`);
    }
    dash.getRange("K"+tr).setFormula(`=IFERROR(ROUND(AVERAGEIFS('${R}'!${cAge}:${cAge},'${R}'!${cLead}:${cLead},"${lead}",'${R}'!${cOpen}:${cOpen},"OPEN"),1),"-")`);
    dash.getRange("L"+tr).setFormula(`=COUNTIFS('${R}'!${cLead}:${cLead},"${lead}",'${R}'!${cOpen}:${cOpen},"OPEN",'${R}'!${cSLA}:${cSLA},"YES")`);
    dash.getRange("M"+tr).setFormula(`=COUNTIFS('${R}'!${cLead}:${cLead},"${lead}",'${R}'!${cOpen}:${cOpen},"OPEN",'${R}'!${cAge}:${cAge},">="&7)`);
    dash.getRange("N"+tr).setFormula(`=COUNTIFS('${R}'!${cLead}:${cLead},"${lead}",'${R}'!${cOpen}:${cOpen},"OPEN",'${R}'!${cAge}:${cAge},">="&30)`);
    if (li%2===0) dash.getRange("A"+tr+":N"+tr).setBackground("#F5F5F5");
    tr++;
  }

  // ═══ FINAL ═══
  dash.setFrozenRows(2);
  dash.setHiddenGridlines(true);

  SpreadsheetApp.getUi().alert(
    "Dashboard v5 created!\n\n" +
    "Columns auto-detected from Raw Data header.\n" +
    "Date filter: D3 (From) and F3 (To)\n\n" +
    "Sections: 6 KPI cards, 7 charts, Resolution TAT,\n" +
    "Daily Resolution Rate, SLA by Account, CX Lead Detail"
  );
}


// ═══ HELPERS — read actual data from Raw Data for dynamic lists ═══

function getLead_names_(sheet, colIdx) {
  const lastRow = sheet.getLastRow();
  if (lastRow <= 1) return [];
  const data = sheet.getRange(2, colIdx, lastRow - 1, 1).getValues();
  const openCol = sheet.getRange(2, 11, lastRow - 1, 1).getValues(); // K = Open?
  const counts = {};
  for (let i = 0; i < data.length; i++) {
    const name = (data[i][0] || "").toString().trim();
    const isOpen = (openCol[i][0] || "").toString().trim();
    if (name && isOpen === "OPEN") counts[name] = (counts[name] || 0) + 1;
  }
  return Object.entries(counts).sort((a,b) => b[1] - a[1]).slice(0, 15).map(e => e[0]);
}

function getTop_accounts_(sheet, custColIdx, openColIdx) {
  const lastRow = sheet.getLastRow();
  if (lastRow <= 1) return [];
  const data = sheet.getRange(2, custColIdx, lastRow - 1, 1).getValues();
  const openCol = sheet.getRange(2, openColIdx, lastRow - 1, 1).getValues();
  const counts = {};
  for (let i = 0; i < data.length; i++) {
    const name = (data[i][0] || "").toString().trim();
    const isOpen = (openCol[i][0] || "").toString().trim();
    if (name && name !== "Unknown" && isOpen === "OPEN") counts[name] = (counts[name] || 0) + 1;
  }
  return Object.entries(counts).sort((a,b) => b[1] - a[1]).slice(0, 12).map(e => e[0]);
}
