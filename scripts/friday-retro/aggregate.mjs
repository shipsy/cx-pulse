// aggregate.mjs <configPath> <RUN_DATE>  — deterministic. Prints leadership-quality Slack digest.
import fs from "node:fs"; import os from "node:os"; import path from "node:path";
const cfg=JSON.parse(fs.readFileSync(process.argv[2],"utf8")); const RUN_DATE=process.argv[3];
const RUN=path.join(os.homedir(),".friday-retro/run",RUN_DATE);
const F=JSON.parse(fs.readFileSync(path.join(RUN,"funnel.json"),"utf8"));
const V=fs.existsSync(path.join(RUN,"verdicts.json"))?JSON.parse(fs.readFileSync(path.join(RUN,"verdicts.json"),"utf8")):[];
const die=m=>{ console.error("aggregate: "+m); process.exit(2); };

// --- helpers ---
const S=s=>String(s||"").replace(/<!(channel|here|everyone)>/gi,"!$1").replace(/<@[^>]+>/g,"@user")
  .replace(/<#[^>]+>/g,"#chan").replace(/<(https?:[^|>]+)\|([^>]+)>/g,"$2").replace(/[<>]/g,"").replace(/\s+/g," ").trim();
const trunc=(s,n)=>{ s=S(s); return s.length>n?s.slice(0,n)+"…":s; };
const vv=x=>x.adjusted_verdict||x.friday_verdict, ii=x=>x.adjusted_impact||x.impact;
const c=(arr,f)=>arr.reduce((o,x)=>{const k=f(x);o[k]=(o[k]||0)+1;return o;},{});
const sum=o=>Object.values(o).reduce((a,b)=>a+b,0);
const lnk=id=>`<https://app.devrev.ai/shipsy/works/${id}|${id}>`;
const nice=new Date(RUN_DATE+"T00:00:00Z").toLocaleDateString("en-GB",{day:"2-digit",month:"short",timeZone:"UTC"});

// exclude label (e.g. "DTDC")
const exLabel=(cfg.excludeOrgSubstrings||[]).length===1
  ?cfg.excludeOrgSubstrings[0].toUpperCase():"excluded orgs";
const pctRan=F.inScope?Math.round(100*F.fridayRan/F.inScope):0;

// --- funnel waterfall (always shown) ---
const funnel=`Resolved today ${String(F.resolvedTotal).padStart(14)}
  − ${exLabel.padEnd(20)} −${F.excludedByOrg}
  = In scope ${String(F.inScope).padStart(15)}
      Friday ran ${String(F.fridayRan).padStart(11)}   (${pctRan}%)
        → judged (real RCA) ${F.judgeable}
        → skipped/unmapped  ${F.skipped}
        → failed             ${F.failed}
      Friday never ran ${String(F.neverRan).padStart(6)}`;

// --- empty day ---
if(F.judgeable===0){
  console.log(`🔍 *Friday Impact — Resolved Today (${nice}, ex-${exLabel})*\n_No judgeable Friday runs today._\n\n${funnel}\n\n_Sent using Claude._`);
  process.exit(0);
}

// --- assertions ---
if(V.length!==F.judgeable) die(`verdicts ${V.length} != judgeable ${F.judgeable}`);
const verd=c(V,vv), imp=c(V,ii), cust=c(V,x=>x.customer_reaction);
if(sum(verd)!==F.judgeable) die("verdict counts don't reconcile");

// --- stats ---
const right=(verd["Correct"]||0)+(verd["Partially correct"]||0), wrong=verd["Incorrect"]||0;
const spedup=imp["Sped up resolution"]||0, setback=imp["Misled or added noise"]||0;
const noReply=cust["No response"]||0, corrected=V.filter(x=>x.supported===false).length;
const neutralNoReply=(cust["Neutral"]||0)+noReply;
const posCount=cust["Positive"]||0, negCount=cust["Negative"]||0;
const pct=n=>Math.round(100*n/F.judgeable);

// --- bottom line (narrative) ---
const helpWord=spedup>setback?"broadly helpful":"mixed";
const custEdge=posCount>=negCount
  ?`positive (${posCount}) edges negative (${negCount})`
  :`negative (${negCount}) still edges positive (${posCount})`;
const bottomLine=`*Bottom line:* right or partly right on ${pct(right)}% (${right}/${F.judgeable}), wrong ${pct(wrong)}% (${wrong}), and ${helpWord} — ${spedup} sped up resolution, ${setback} set the ticket back. ${pct(noReply)}% of customers never reply; among those who do, ${custEdge}.`;

// --- scoreboard ---
const scoreboard=`*1. SCOREBOARD (${F.judgeable} judged)*
Was Friday right?  🟢 Correct ${verd["Correct"]||0}  🟡 Partly ${verd["Partially correct"]||0}  🔴 Wrong ${verd["Incorrect"]||0}  ⚪ Unverifiable ${verd["Not verifiable"]||0}
Did it help?       🟢 Sped up ${spedup}  ⚪ No effect ${imp["Neutral / no clear effect"]||0}          🔴 Set back ${setback}
Customer           🟢 Positive ${posCount}  ⚪ Neutral/No-reply ${neutralNoReply}   🔴 Negative ${negCount}`;

// --- why it missed ---
const wrongRCA=V.filter(x=>vv(x)==="Incorrect");
const wrongProcess=V.filter(x=>ii(x)==="Misled or added noise"&&vv(x)!=="Incorrect");
const missLines=[];
if(wrongRCA.length) missLines.push(
  `Wrong root cause ${String(wrongRCA.length).padStart(33)}   ${wrongRCA.map(x=>x.id).join(", ")}`);
if(wrongProcess.length) missLines.push(
  `Wrong external response / process ${String(wrongProcess.length).padStart(5)}   ${wrongProcess.map(x=>x.id).join(", ")}`);
const missSection=missLines.length?missLines.join("\n"):"_none today_";

// --- by org ---
const orgs={}; for(const x of V){ const o=(x.org||"?"); const g=orgs[o]??={ran:0,right:0,help:0,set:0,neg:0};
  g.ran++; if(vv(x)==="Correct"||vv(x)==="Partially correct")g.right++; if(x.helpful==="Yes")g.help++;
  if(ii(x)==="Misled or added noise")g.set++; if(x.customer_reaction==="Negative")g.neg++; }
if(sum(Object.fromEntries(Object.entries(orgs).map(([k,v])=>[k,v.ran])))!==F.judgeable) die("by-org sum mismatch");
const top=Object.entries(orgs).sort((a,b)=>b[1].ran-a[1].ran);
const sig=g=>g.set>0||g.neg>g.ran/2?"🔴":(g.right===g.ran&&g.neg===0?"🟢":"🟡");
const orgRows=top.slice(0,7).map(([o,g])=>
  `${o.slice(0,16).padEnd(16)} ${String(g.ran).padStart(3)}  ${String(g.right).padStart(5)}  ${String(g.help).padStart(6)}  ${String(g.set).padStart(7)}  ${String(g.neg).padStart(4)}  ${sig(g)}`
).join("\n");
const moreOrgs=top.length>7?`\n+${top.length-7} more orgs`:"";

// --- review: full narrative for set-back tickets ---
const reviewTickets=V.filter(x=>ii(x)==="Misled or added noise");
const reviewLines=reviewTickets.map(x=>{
  const parts=[`🔴 ${lnk(x.id)} ${S(x.org)} — ${trunc(x.issue_summary,45)}.`];
  if(x.friday_did) parts.push(`Friday → "${trunc(x.friday_did,55)}";`);
  if(x.customer_reaction==="Negative"&&x.customer_reaction_evidence)
    parts.push(`customer: _"${trunc(x.customer_reaction_evidence,50)}"_`);
  else if(x.team_response) parts.push(trunc(x.team_response,65));
  else if(x.verdict_reason) parts.push(trunc(x.verdict_reason,65));
  return parts.join(" ");
}).join("\n")||"_none today_";

// --- wins: full narrative, prioritize positive customer reactions ---
const winTickets=V.filter(x=>x.helpful==="Yes"||ii(x)==="Sped up resolution")
  .sort((a,b)=>{
    const sc=x=>(x.customer_reaction==="Positive"?2:0)+(ii(x)==="Sped up resolution"?1:0);
    return sc(b)-sc(a);
  }).slice(0,4);
const winLines=winTickets.map(x=>{
  const parts=[`🟢 ${lnk(x.id)} ${S(x.org)} — ${trunc(x.issue_summary,45)}.`];
  if(x.friday_did) parts.push(`Friday → "${trunc(x.friday_did,55)}";`);
  if(x.customer_reaction==="Positive"&&x.customer_reaction_evidence)
    parts.push(`customer: *"${trunc(x.customer_reaction_evidence,50)}"*`);
  else if(x.team_response) parts.push(trunc(x.team_response,55));
  return parts.join(" ");
}).join("\n")||"_none today_";

// --- compose full message ---
const msg=`🔍 *Friday Impact — Resolved Today (${nice}, ex-${exLabel})*
_Full coverage — every resolved-today ticket Friday ran on, judged from its DevRev timeline + adversarially verified_

${funnel}
━━━━━━━━━━━━━━━━━━━━━━━━

${bottomLine}

${scoreboard}

*2. WHY IT MISSED*
${missSection}

*3. BY ORG — where Friday helps vs hurts*
\`\`\`
Org               Ran  Right  Helped  SetBack   Neg
${orgRows}${moreOrgs}
\`\`\`

*4. ⚠ REVIEW — Friday set these back*
${reviewLines}

*5. ✅ CLEAR WINS*
${winLines}
━━━━━━━━━━━━━━━━━━━━━━━━
_Method: DevRev timelines only · adversarial verify (corrected ${corrected}/${F.judgeable}) · verdicts inferred (0 explicit "Feedback to Friday") · Sent using Claude_`;

// thread overflow if too long for Slack
if(msg.length>3900){
  const head=msg.split("*4. ⚠ REVIEW")[0]+`\n_(details in thread)_`;
  const thread=`*4. ⚠ REVIEW — Friday set these back*\n${reviewLines}\n\n*5. ✅ CLEAR WINS*\n${winLines}`;
  console.log(head); console.log("\0THREAD\0"); console.log(thread);
} else console.log(msg);
