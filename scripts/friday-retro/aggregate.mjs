// aggregate.mjs <configPath> <RUN_DATE>  — deterministic. Prints Slack message to stdout.
import fs from "node:fs"; import os from "node:os"; import path from "node:path";
const cfg=JSON.parse(fs.readFileSync(process.argv[2],"utf8")); const RUN_DATE=process.argv[3];
const RUN=path.join(os.homedir(),".friday-retro/run",RUN_DATE);
const F=JSON.parse(fs.readFileSync(path.join(RUN,"funnel.json"),"utf8"));
const V=fs.existsSync(path.join(RUN,"verdicts.json"))?JSON.parse(fs.readFileSync(path.join(RUN,"verdicts.json"),"utf8")):[];
const die=m=>{ console.error("aggregate: "+m); process.exit(2); };
// neutralize Slack control sequences in any text taken from tickets
const S=s=>String(s||"").replace(/<!(channel|here|everyone)>/gi,"!$1").replace(/<@[^>]+>/g,"@user")
  .replace(/<#[^>]+>/g,"#chan").replace(/<(https?:[^|>]+)\|([^>]+)>/g,"$2").replace(/[<>]/g,"").replace(/\s+/g," ").trim();
const vv=x=>x.adjusted_verdict||x.friday_verdict, ii=x=>x.adjusted_impact||x.impact;
const c=(arr,f)=>arr.reduce((o,x)=>{const k=f(x);o[k]=(o[k]||0)+1;return o;},{});
const nice=new Date(RUN_DATE+"T00:00:00Z").toLocaleDateString("en-GB",{day:"2-digit",month:"short",timeZone:"UTC"});
if(F.judgeable===0){ console.log(`🔍 *Friday Impact — Resolved Today (${nice})*\nNo judgeable Friday runs today. Resolved in scope ${F.inScope} · Friday ran ${F.fridayRan} · skipped ${F.skipped} · failed ${F.failed} · never ran ${F.neverRan}.\n_Sent using Claude._`); process.exit(0); }
if(V.length!==F.judgeable) die(`verdicts ${V.length} != judgeable ${F.judgeable}`);
const verd=c(V,vv), imp=c(V,ii), cust=c(V,x=>x.customer_reaction);
const sum=o=>Object.values(o).reduce((a,b)=>a+b,0);
if(sum(verd)!==F.judgeable) die("verdict counts don't reconcile");
const right=(verd["Correct"]||0)+(verd["Partially correct"]||0), wrong=verd["Incorrect"]||0;
const spedup=imp["Sped up resolution"]||0, setback=imp["Misled or added noise"]||0;
const noReply=cust["No response"]||0, corrected=V.filter(x=>x.supported===false).length;
// by org
const orgs={}; for(const x of V){ const o=(x.org||"?"); const g=orgs[o]??={ran:0,right:0,help:0,set:0,neg:0};
  g.ran++; if(vv(x)==="Correct"||vv(x)==="Partially correct")g.right++; if(x.helpful==="Yes")g.help++;
  if(ii(x)==="Misled or added noise")g.set++; if(x.customer_reaction==="Negative")g.neg++; }
if(sum(Object.fromEntries(Object.entries(orgs).map(([k,v])=>[k,v.ran])))!==F.judgeable) die("by-org sum mismatch");
const top=Object.entries(orgs).sort((a,b)=>b[1].ran-a[1].ran);
const sig=g=>g.set>0||g.neg>g.ran/2?"🔴":(g.right===g.ran&&g.neg===0?"🟢":"🟡");
const orgRows=top.slice(0,8).map(([o,g])=>`${o.slice(0,16).padEnd(16)} ${String(g.ran).padStart(3)}  ${String(g.right).padStart(4)}  ${String(g.help).padStart(5)}  ${String(g.set).padStart(6)}  ${String(g.neg).padStart(3)}  ${sig(g)}`).join("\n");
const more=top.length>8?`\n+${top.length-8} more orgs`:"";
const line=x=>`• <https://app.devrev.ai/shipsy/works/${x.id}|${x.id}> ${S(x.org)} — ${S(x.one_line)}`;
const review=V.filter(x=>ii(x)==="Misled or added noise").map(line).join("\n")||"_none today_";
const wins=V.filter(x=>x.helpful==="Yes"||ii(x)==="Sped up resolution").slice(0,4).map(line).join("\n")||"_none today_";
const pct=n=>Math.round(100*n/F.judgeable);
const msg=`🔍 *Friday Impact — Resolved Today (${nice})*
_Full coverage — every resolved-today ticket Friday ran on, judged from its DevRev timeline + adversarially verified_

Resolved in scope *${F.inScope}* · Friday ran ${F.fridayRan} · judged ${F.judgeable} · skipped ${F.skipped} · failed ${F.failed} · never ran ${F.neverRan}
━━━━━━━━━━━━━━━━━━━━━━━━
*Bottom line:* ${pct(right)}% right/partly, ${pct(wrong)}% wrong · ${spedup} sped up · ${setback} set back · ${noReply}/${F.judgeable} customers didn't reply.

*1. SCOREBOARD*
\`\`\`
Right?    Correct ${verd["Correct"]||0}  Partly ${verd["Partially correct"]||0}  Wrong ${verd["Incorrect"]||0}  Unverifiable ${verd["Not verifiable"]||0}
Helped?   Sped up ${spedup}  No effect ${imp["Neutral / no clear effect"]||0}  Set back ${setback}
Customer  Positive ${cust["Positive"]||0}  Neutral ${cust["Neutral"]||0}  No-reply ${noReply}  Negative ${cust["Negative"]||0}
\`\`\`
*2. BY ORG*  (helps vs hurts)
\`\`\`
Org               Ran  Right  Helped  SetBack  Neg
${orgRows}${more}
\`\`\`
*3. ⚠ REVIEW — Friday set these back*
${review}

*4. ✅ CLEAR WINS*
${wins}
━━━━━━━━━━━━━━━━━━━━━━━━
_Method: DevRev timelines only · adversarial verify (corrected ${corrected}/${F.judgeable}) · verdicts inferred (no explicit feedback) · Sent using Claude_`;
if(msg.length>3900){ // keep top-level under Slack limits; emit review+wins as a threaded overflow
  const head=msg.split("*3. ⚠ REVIEW")[0]+`\n_(details in thread)_`;
  console.log(head); console.log("\0THREAD\0"); console.log(`*⚠ REVIEW — set back*\n${review}\n\n*✅ WINS*\n${wins}`);
} else console.log(msg);
