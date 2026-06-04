/**
 * F.R.I.D.A.Y Deep Analysis — Sheet Formatter
 *
 * HOW TO RUN:
 * 1. Open the Google Sheet
 * 2. Extensions > Apps Script
 * 3. Paste this entire script (replace any existing code)
 * 4. Click Run > formatSheet
 * 5. Authorize when prompted
 */

function formatSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var source = ss.getSheets()[0];
  var data = source.getDataRange().getValues();

  // Define sections and their row ranges
  var sections = [];
  var currentSection = null;
  var sectionStart = -1;

  for (var i = 0; i < data.length; i++) {
    var cell = String(data[i][0]);
    if (cell.indexOf("=====") === 0) {
      if (currentSection) {
        sections.push({ name: currentSection, startRow: sectionStart, endRow: i - 1 });
      }
      currentSection = cell.replace(/=+\s*/g, "").trim();
      sectionStart = i + 1;
    }
  }
  if (currentSection) {
    sections.push({ name: currentSection, startRow: sectionStart, endRow: data.length - 1 });
  }

  // Color themes per section
  var themes = {
    "OVERVIEW KPIs":              { header: "#1e3a5f", headerFont: "#ffffff", accent: "#dbeafe", band: "#f0f7ff" },
    "VOLUME METRICS":             { header: "#1a4d2e", headerFont: "#ffffff", accent: "#d1fae5", band: "#f0fdf4" },
    "OUTCOME BREAKDOWN":          { header: "#5b21b6", headerFont: "#ffffff", accent: "#ede9fe", band: "#f5f3ff" },
    "KEY RATES":                  { header: "#0e7490", headerFont: "#ffffff", accent: "#cffafe", band: "#ecfeff" },
    "PIPELINE ARCHITECTURE":      { header: "#7c2d12", headerFont: "#ffffff", accent: "#fed7aa", band: "#fff7ed" },
    "OUTPUT ARTIFACTS":           { header: "#166534", headerFont: "#ffffff", accent: "#bbf7d0", band: "#f0fdf4" },
    "SLACK MESSAGE PATTERNS":     { header: "#6b21a8", headerFont: "#ffffff", accent: "#e9d5ff", band: "#faf5ff" },
    "RCA ACCURACY ANALYSIS":      { header: "#b91c1c", headerFont: "#ffffff", accent: "#fecaca", band: "#fef2f2" },
    "RCA ACCURACY — TICKET DETAILS": { header: "#9a3412", headerFont: "#ffffff", accent: "#fed7aa", band: "#fff7ed" },
    "STRENGTH & WEAKNESS PATTERNS": { header: "#1e40af", headerFont: "#ffffff", accent: "#bfdbfe", band: "#eff6ff" },
    "INVESTIGATION TOOLS USED":   { header: "#0f766e", headerFont: "#ffffff", accent: "#99f6e4", band: "#f0fdfa" },
    "SYSTEM IDENTITIES":          { header: "#4338ca", headerFont: "#ffffff", accent: "#c7d2fe", band: "#eef2ff" },
    "RECOMMENDATIONS":            { header: "#065f46", headerFont: "#ffffff", accent: "#a7f3d0", band: "#ecfdf5" }
  };

  // Tab name mapping (shorter names for tabs)
  var tabNames = {
    "OVERVIEW KPIs": "Overview",
    "VOLUME METRICS": "Volume",
    "OUTCOME BREAKDOWN": "Outcomes",
    "KEY RATES": "Key Rates",
    "PIPELINE ARCHITECTURE": "Pipeline",
    "OUTPUT ARTIFACTS": "Artifacts",
    "SLACK MESSAGE PATTERNS": "Slack Patterns",
    "RCA ACCURACY ANALYSIS": "RCA Accuracy",
    "RCA ACCURACY — TICKET DETAILS": "RCA Details",
    "STRENGTH & WEAKNESS PATTERNS": "Strengths & Gaps",
    "INVESTIGATION TOOLS USED": "Tools",
    "SYSTEM IDENTITIES": "Identities",
    "RECOMMENDATIONS": "Recommendations"
  };

  // Create each tab
  for (var s = 0; s < sections.length; s++) {
    var sec = sections[s];
    var tabName = tabNames[sec.name] || sec.name.substring(0, 28);
    var theme = themes[sec.name] || { header: "#374151", headerFont: "#ffffff", accent: "#e5e7eb", band: "#f9fafb" };

    // Create new sheet
    var sheet;
    try {
      sheet = ss.insertSheet(tabName);
    } catch(e) {
      sheet = ss.getSheetByName(tabName);
      if (sheet) sheet.clear();
      else sheet = ss.insertSheet(tabName + " ");
    }

    // Collect rows for this section (skip empty rows)
    var rows = [];
    for (var r = sec.startRow; r <= sec.endRow; r++) {
      var row = data[r];
      var isEmpty = row.every(function(cell) { return String(cell).trim() === ""; });
      if (!isEmpty) rows.push(row);
    }

    if (rows.length === 0) continue;

    // Write title row (merged)
    var titleText = tabNames[sec.name] || sec.name;
    sheet.getRange(1, 1).setValue(titleText);
    sheet.getRange(1, 1, 1, 5).merge();
    sheet.getRange(1, 1).setFontSize(16).setFontWeight("bold").setFontColor(theme.header);
    sheet.setRowHeight(1, 36);

    // Subtitle
    sheet.getRange(2, 1).setValue("F.R.I.D.A.Y Agent Deep Analysis | Apr 30 – May 31, 2026");
    sheet.getRange(2, 1, 1, 5).merge();
    sheet.getRange(2, 1).setFontSize(10).setFontColor("#6b7280").setFontStyle("italic");
    sheet.setRowHeight(2, 22);

    // Blank row
    sheet.setRowHeight(3, 8);

    // Header row (row 4) — use the CSV header: SECTION, METRIC, VALUE, DETAIL, FORMULA/SOURCE
    // But customize per section
    var headers = ["Category", "Metric", "Value", "Detail", "Source / Formula"];
    if (sec.name === "RCA ACCURACY — TICKET DETAILS") {
      headers = ["Ticket", "Verdict", "F.R.I.D.A.Y Said", "Human Said", "Key Insight"];
    } else if (sec.name === "RECOMMENDATIONS") {
      headers = ["Recommendation", "Priority", "Impact", "Effort", "Detail"];
    } else if (sec.name === "STRENGTH & WEAKNESS PATTERNS") {
      headers = ["Type", "Area", "Accuracy", "Detail", ""];
    } else if (sec.name === "SYSTEM IDENTITIES") {
      headers = ["Identity", "Name", "ID", "Role", "Platform"];
    } else if (sec.name === "INVESTIGATION TOOLS USED") {
      headers = ["Tool", "Purpose", "Success Rate", "Notes", ""];
    }

    var headerRange = sheet.getRange(4, 1, 1, 5);
    headerRange.setValues([headers]);
    headerRange.setFontWeight("bold")
               .setFontColor(theme.headerFont)
               .setBackground(theme.header)
               .setFontSize(11)
               .setHorizontalAlignment("left");
    sheet.setRowHeight(4, 30);

    // Data rows starting at row 5
    for (var dr = 0; dr < rows.length; dr++) {
      var rowData = rows[dr];
      var sheetRow = dr + 5;

      // Write data (skip first column if it's the section name repeating)
      var writeData = [rowData[0], rowData[1], rowData[2], rowData[3], rowData[4]];
      sheet.getRange(sheetRow, 1, 1, 5).setValues([writeData]);

      // Alternating row colors
      var bgColor = (dr % 2 === 0) ? theme.band : "#ffffff";
      sheet.getRange(sheetRow, 1, 1, 5).setBackground(bgColor);

      // Style the value column (C) — bold
      sheet.getRange(sheetRow, 3).setFontWeight("bold");

      // Font size
      sheet.getRange(sheetRow, 1, 1, 5).setFontSize(10);
      sheet.setRowHeight(sheetRow, 26);
    }

    // Column widths
    sheet.setColumnWidth(1, 180);
    sheet.setColumnWidth(2, 250);
    sheet.setColumnWidth(3, 200);
    sheet.setColumnWidth(4, 350);
    sheet.setColumnWidth(5, 250);

    // Add borders to the data area
    var totalRows = rows.length + 4;
    var dataArea = sheet.getRange(4, 1, rows.length + 1, 5);
    dataArea.setBorder(true, true, true, true, true, true, "#d1d5db", SpreadsheetApp.BorderStyle.SOLID);

    // Freeze header row
    sheet.setFrozenRows(4);

    // Add a summary KPI row for specific tabs
    if (sec.name === "RCA ACCURACY ANALYSIS") {
      var kpiRow = totalRows + 2;
      sheet.getRange(kpiRow, 1).setValue("HEADLINE");
      sheet.getRange(kpiRow, 2).setValue("84.6% Overall Accuracy");
      sheet.getRange(kpiRow, 1, 1, 5).setBackground(theme.accent)
           .setFontWeight("bold").setFontSize(14);
      sheet.setRowHeight(kpiRow, 36);
    }

    if (sec.name === "OUTCOME BREAKDOWN") {
      var kpiRow = totalRows + 2;
      sheet.getRange(kpiRow, 1).setValue("SUCCESS");
      sheet.getRange(kpiRow, 2).setValue("386 RCAs from 523 runs = 73.8% success rate");
      sheet.getRange(kpiRow, 1, 1, 5).setBackground(theme.accent)
           .setFontWeight("bold").setFontSize(14);
      sheet.setRowHeight(kpiRow, 36);
    }

    // Color-code specific cells
    if (sec.name === "RCA ACCURACY — TICKET DETAILS") {
      for (var cr = 5; cr < 5 + rows.length; cr++) {
        var verdict = String(sheet.getRange(cr, 2).getValue()).toUpperCase();
        if (verdict === "MATCH") {
          sheet.getRange(cr, 2).setBackground("#d1fae5").setFontColor("#065f46");
        } else if (verdict.indexOf("PARTIAL") >= 0) {
          sheet.getRange(cr, 2).setBackground("#fef3c7").setFontColor("#92400e");
        } else if (verdict === "MISMATCH") {
          sheet.getRange(cr, 2).setBackground("#fecaca").setFontColor("#991b1b");
        }
      }
    }

    if (sec.name === "RECOMMENDATIONS") {
      for (var cr = 5; cr < 5 + rows.length; cr++) {
        var priority = String(sheet.getRange(cr, 2).getValue()).toUpperCase();
        if (priority === "HIGH") {
          sheet.getRange(cr, 2).setBackground("#fecaca").setFontColor("#991b1b").setFontWeight("bold");
        } else if (priority === "MEDIUM") {
          sheet.getRange(cr, 2).setBackground("#fef3c7").setFontColor("#92400e").setFontWeight("bold");
        } else if (priority === "LOW") {
          sheet.getRange(cr, 2).setBackground("#d1fae5").setFontColor("#065f46");
        }
      }
    }

    if (sec.name === "STRENGTH & WEAKNESS PATTERNS") {
      for (var cr = 5; cr < 5 + rows.length; cr++) {
        var type = String(sheet.getRange(cr, 1).getValue());
        if (type === "Strength") {
          sheet.getRange(cr, 1).setBackground("#d1fae5").setFontColor("#065f46").setFontWeight("bold");
        } else if (type === "Weakness") {
          sheet.getRange(cr, 1).setBackground("#fecaca").setFontColor("#991b1b").setFontWeight("bold");
        }
      }
    }

    // Set tab color
    sheet.setTabColor(theme.header);
  }

  // Create a Dashboard tab at the beginning
  var dashboard = ss.insertSheet("Dashboard", 0);
  dashboard.setTabColor("#1e1e1e");

  // Dashboard title
  dashboard.getRange(1, 1).setValue("F.R.I.D.A.Y Agent");
  dashboard.getRange(1, 1, 1, 6).merge();
  dashboard.getRange(1, 1).setFontSize(28).setFontWeight("bold").setFontColor("#1e1e1e");
  dashboard.setRowHeight(1, 48);

  dashboard.getRange(2, 1).setValue("Deep Analysis Report | 31-Day Performance | Apr 30 - May 31, 2026");
  dashboard.getRange(2, 1, 1, 6).merge();
  dashboard.getRange(2, 1).setFontSize(12).setFontColor("#6b7280").setFontStyle("italic");
  dashboard.setRowHeight(2, 24);

  dashboard.setRowHeight(3, 12);

  // KPI Cards Row
  var kpiRow = 4;
  var kpis = [
    { label: "Total Tickets", value: "2,298", color: "#1e3a5f", bg: "#dbeafe" },
    { label: "Agent Runs", value: "523", color: "#5b21b6", bg: "#ede9fe" },
    { label: "RCAs Generated", value: "386", color: "#166534", bg: "#d1fae5" },
    { label: "FR Drafts", value: "68", color: "#b45309", bg: "#fef3c7" },
    { label: "Coverage", value: "22.8%", color: "#0e7490", bg: "#cffafe" },
    { label: "Accuracy", value: "84.6%", color: "#b91c1c", bg: "#fecaca" }
  ];

  for (var k = 0; k < kpis.length; k++) {
    var col = k + 1;
    dashboard.getRange(kpiRow, col).setValue(kpis[k].value);
    dashboard.getRange(kpiRow, col).setFontSize(24).setFontWeight("bold")
             .setFontColor(kpis[k].color).setBackground(kpis[k].bg)
             .setHorizontalAlignment("center");
    dashboard.setRowHeight(kpiRow, 50);
    dashboard.getRange(kpiRow + 1, col).setValue(kpis[k].label);
    dashboard.getRange(kpiRow + 1, col).setFontSize(10).setFontColor("#6b7280")
             .setHorizontalAlignment("center").setBackground(kpis[k].bg);
    dashboard.setColumnWidth(col, 150);
  }
  dashboard.setRowHeight(kpiRow + 1, 28);

  // Add borders to KPI cards
  dashboard.getRange(kpiRow, 1, 2, 6).setBorder(true, true, true, true, true, true, "#d1d5db", SpreadsheetApp.BorderStyle.SOLID);

  dashboard.setRowHeight(6, 16);

  // Outcome breakdown mini-table
  var obRow = 7;
  dashboard.getRange(obRow, 1).setValue("Outcome Breakdown");
  dashboard.getRange(obRow, 1, 1, 3).merge();
  dashboard.getRange(obRow, 1).setFontSize(14).setFontWeight("bold").setFontColor("#1e1e1e");

  var outcomes = [
    ["RCA + FR Draft", "68", "13.0%", "#d1fae5"],
    ["RCA Only", "318", "60.8%", "#dbeafe"],
    ["Skipped", "133", "25.4%", "#fef3c7"],
    ["Failed", "4", "0.8%", "#fecaca"]
  ];

  // Headers
  dashboard.getRange(obRow + 1, 1, 1, 3).setValues([["Category", "Count", "% of Runs"]]);
  dashboard.getRange(obRow + 1, 1, 1, 3).setFontWeight("bold").setBackground("#374151").setFontColor("#ffffff").setFontSize(10);

  for (var o = 0; o < outcomes.length; o++) {
    var row = obRow + 2 + o;
    dashboard.getRange(row, 1, 1, 3).setValues([[outcomes[o][0], outcomes[o][1], outcomes[o][2]]]);
    dashboard.getRange(row, 1, 1, 3).setBackground(outcomes[o][3]).setFontSize(10);
    dashboard.getRange(row, 2).setFontWeight("bold").setHorizontalAlignment("center");
    dashboard.getRange(row, 3).setHorizontalAlignment("center");
  }
  dashboard.getRange(obRow + 1, 1, 5, 3).setBorder(true, true, true, true, true, true, "#d1d5db", SpreadsheetApp.BorderStyle.SOLID);

  // Accuracy mini-table
  dashboard.getRange(obRow, 4).setValue("RCA Accuracy (20 tickets sampled)");
  dashboard.getRange(obRow, 4, 1, 3).merge();
  dashboard.getRange(obRow, 4).setFontSize(14).setFontWeight("bold").setFontColor("#1e1e1e");

  var accuracy = [
    ["Match (80-100%)", "6", "46.2%", "#d1fae5"],
    ["Partial (50-80%)", "5", "38.5%", "#fef3c7"],
    ["Mismatch", "2", "15.4%", "#fecaca"],
    ["Overall Accuracy", "11/13", "84.6%", "#dbeafe"]
  ];

  dashboard.getRange(obRow + 1, 4, 1, 3).setValues([["Category", "Count", "Rate"]]);
  dashboard.getRange(obRow + 1, 4, 1, 3).setFontWeight("bold").setBackground("#374151").setFontColor("#ffffff").setFontSize(10);

  for (var a = 0; a < accuracy.length; a++) {
    var row = obRow + 2 + a;
    dashboard.getRange(row, 4, 1, 3).setValues([[accuracy[a][0], accuracy[a][1], accuracy[a][2]]]);
    dashboard.getRange(row, 4, 1, 3).setBackground(accuracy[a][3]).setFontSize(10);
    dashboard.getRange(row, 5).setFontWeight("bold").setHorizontalAlignment("center");
    dashboard.getRange(row, 6).setHorizontalAlignment("center");
  }
  dashboard.getRange(obRow + 1, 4, 5, 3).setBorder(true, true, true, true, true, true, "#d1d5db", SpreadsheetApp.BorderStyle.SOLID);

  // Key rates row
  var ratesRow = 14;
  dashboard.setRowHeight(13, 16);
  dashboard.getRange(ratesRow, 1).setValue("Key Rates");
  dashboard.getRange(ratesRow, 1, 1, 6).merge();
  dashboard.getRange(ratesRow, 1).setFontSize(14).setFontWeight("bold");

  var rates = [
    { label: "RCA Success", value: "73.8%", detail: "386/523 runs" },
    { label: "FR Draft Rate", value: "17.6%", detail: "68/386 RCAs" },
    { label: "Skip Rate", value: "25.4%", detail: "133 unmapped" },
    { label: "Reliability", value: "99.2%", detail: "4 failures only" },
    { label: "Daily Avg Tickets", value: "74.1", detail: "2298/31 days" },
    { label: "Daily Avg Runs", value: "16.9", detail: "523/31 days" }
  ];

  dashboard.getRange(ratesRow + 1, 1, 1, 6).setValues([rates.map(function(r) { return r.label; })]);
  dashboard.getRange(ratesRow + 1, 1, 1, 6).setFontWeight("bold").setFontSize(10).setFontColor("#6b7280").setHorizontalAlignment("center");
  dashboard.getRange(ratesRow + 2, 1, 1, 6).setValues([rates.map(function(r) { return r.value; })]);
  dashboard.getRange(ratesRow + 2, 1, 1, 6).setFontSize(18).setFontWeight("bold").setHorizontalAlignment("center").setFontColor("#1e1e1e");
  dashboard.getRange(ratesRow + 3, 1, 1, 6).setValues([rates.map(function(r) { return r.detail; })]);
  dashboard.getRange(ratesRow + 3, 1, 1, 6).setFontSize(9).setFontColor("#9ca3af").setHorizontalAlignment("center");

  dashboard.getRange(ratesRow + 1, 1, 3, 6).setBorder(true, true, true, true, true, true, "#e5e7eb", SpreadsheetApp.BorderStyle.SOLID);

  // Navigation footer
  var navRow = 19;
  dashboard.setRowHeight(18, 16);
  dashboard.getRange(navRow, 1).setValue("Navigate to tabs below for detailed data:");
  dashboard.getRange(navRow, 1, 1, 6).merge();
  dashboard.getRange(navRow, 1).setFontSize(11).setFontColor("#6b7280");

  var tabList = ["Overview", "Volume", "Outcomes", "Key Rates", "Pipeline", "Artifacts",
                 "Slack Patterns", "RCA Accuracy", "RCA Details", "Strengths & Gaps",
                 "Tools", "Identities", "Recommendations"];
  for (var t = 0; t < tabList.length; t++) {
    var tRow = navRow + 1 + Math.floor(t / 3);
    var tCol = (t % 3) * 2 + 1;
    dashboard.getRange(tRow, tCol).setValue((t + 1) + ". " + tabList[t]);
    dashboard.getRange(tRow, tCol).setFontSize(10).setFontColor("#4338ca");
  }

  // Freeze dashboard
  dashboard.setFrozenRows(3);

  // Delete original data sheet
  var origSheet = ss.getSheets().filter(function(s) { return s.getName() !== "Dashboard" && !tabNames[s.getName()] && Object.values(tabNames).indexOf(s.getName()) === -1; });
  // Try to delete Sheet1 / the original CSV import sheet
  for (var d = 0; d < ss.getSheets().length; d++) {
    var sh = ss.getSheets()[d];
    var shName = sh.getName();
    if (shName === "Sheet1" || shName === "F.R.I.D.A.Y Agent — Deep Analysis (Apr 30 – May 31, 2026)") {
      ss.deleteSheet(sh);
      break;
    }
  }

  // Set Dashboard as active
  ss.setActiveSheet(dashboard);

  SpreadsheetApp.flush();
  SpreadsheetApp.getUi().alert("Done! Your F.R.I.D.A.Y Deep Analysis sheet is formatted with " + (sections.length + 1) + " tabs.");
}
