// collect.mjs <configPath> <RUN_DATE>  — deterministic, read-only. Node, no deps.
import fs from "node:fs"; import os from "node:os"; import path from "node:path"; import crypto from "node:crypto";
const cfg = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const RUN_DATE = process.argv[3];                       // YYYY-MM-DD, supplied by the agent (stable)
if (!/^\d{4}-\d{2}-\d{2}$/.test(RUN_DATE||"")) { console.error("bad RUN_DATE"); process.exit(3); }
const API="https://api.devrev.ai", FRIDAY="don:identity:dvrv-us-1:devo/xXjPo9nF:devu/2940";
function loadToken(){ if (process.env[cfg.devrevTokenKey]) return process.env[cfg.devrevTokenKey];
  const e=fs.readFileSync(cfg.devrevTokenPath,"utf8");
  const m=e.match(new RegExp("^\\s*(?:export\\s+)?"+cfg.devrevTokenKey+"=(.+)$","m"));
  if(!m) throw new Error("token not found"); return m[1].trim().replace(/^["']|["']$/g,""); }
const TOKEN=loadToken(); const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function api(p,params={}){ const u=new URL(API+p); for(const[k,v]of Object.entries(params)) if(v!=null)u.searchParams.set(k,v);
  for(let a=0;;a++){ let r; try{ r=await fetch(u,{headers:{Authorization:TOKEN}}); }catch(e){ if(a<6){await sleep(1000*(a+1));continue;} throw e; }
    if(r.status===429 && a<6){ await sleep(1500*(a+1)); continue; }
    if(!r.ok) throw new Error(p+" HTTP "+r.status); return r.json(); } }
const fmt=new Intl.DateTimeFormat("en-CA",{timeZone:cfg.timezone,year:"numeric",month:"2-digit",day:"2-digit"});
const dayOf=d=>fmt.format(new Date(d));
const stageOf=t=>t.stage?.name||t.stage?.stage?.name||"";      // dual-shape (matches build-dataset.mjs)
const done=new Set(cfg.doneStages);
const subtypeOK=t=>String(t.subtype||"").toLowerCase()===String(cfg.subtype||"support").toLowerCase();
const excl=(cfg.excludeOrgSubstrings||[]).map(s=>s.toLowerCase());
const orgOf=t=>t.rev_org?.display_name||t.account?.display_name||"(none)";
const isExcluded=t=>excl.some(s=>orgOf(t).toLowerCase().includes(s));
const isFriday=a=>!!a&&(a.id===FRIDAY||a.display_id==="DEVU-2940"||/\bFriday\b/.test(a.display_name||a.full_name||""));
const norm=s=>(s||"").replace(/[*_`>#]/g,"").replace(/^\s+/,"").toLowerCase();
const trunc=(s,n)=>{ s=(s||"").replace(/\r/g,""); return s&&s.length>n?s.slice(0,n)+" …":s; };
const sentimentOf=s=>(s&&typeof s==="object")?(s.label??null):(s??null);
async function timeline(don){ const out=[]; let c=null,p=0,capped=false;
  do{ const r=await api("/timeline-entries.list",{object:don,limit:50,cursor:c});
    for(const e of r.timeline_entries||[]){ if(e.type!=="timeline_comment") continue;
      out.push({body:e.body||"",vis:e.visibility||"",by:e.created_by||{},at:e.created_date}); }
    c=r.next_cursor; p++; if(p>=20 && c){ capped=true; break; } } while(c);
  return {comments:out, capped}; }
// 1) paginate modified-desc; collect stage-done, subtype-ok, RUN_DATE tickets; DEDUPE; robust stop
const seen=new Map(); let pages=0, reachedPast=false, cursor=null;
const PAGE_CAP=80;                                             // ~8000 modified/day headroom
while(pages<PAGE_CAP){ const r=await api("/works.list",{type:"ticket",limit:100,cursor,sort_by:"modified_date:desc"});
  const w=r.works||[]; if(!w.length){ reachedPast=true; break; }
  for(const t of w){ const d=dayOf(t.modified_date); if(d>RUN_DATE) continue;
    if(d===RUN_DATE && done.has(stageOf(t)) && subtypeOK(t)) seen.set(t.id,t); }
  const newest=dayOf(w[0].modified_date), oldest=dayOf(w[w.length-1].modified_date);
  cursor=r.next_cursor; pages++;
  if(oldest<RUN_DATE){ reachedPast=true; break; }             // whole tail now older than RUN_DATE
  if(!cursor){ reachedPast=true; break; } }
const truncated = (pages>=PAGE_CAP && !reachedPast);
const all=[...seen.values()];
const resolvedTotal=all.length;
const scope=all.filter(t=>!isExcluded(t)); const excludedByOrg=resolvedTotal-scope.length;
// cap BEFORE expensive per-ticket fetches
const overCap = scope.length>cfg.maxTickets;
const RUN=path.join(os.homedir(),".friday-retro/run",RUN_DATE);
fs.mkdirSync(path.join(RUN,"bundles"),{recursive:true});
let neverRan=0, ranNoRCA=0, skipped=0, failed=0, errors=0; const judgeIds=[];
if(!truncated && !overCap){
  let i=0; const CC=8;
  await Promise.all(Array.from({length:CC},async()=>{ while(i<scope.length){ const idx=i++; const t=scope[idx];
    try{ const {comments,capped}=await timeline(t.id); const fri=comments.filter(c=>isFriday(c.by));
      if(!fri.length){ neverRan++; continue; }
      const allb=fri.map(c=>c.body).join("\n");
      if(/workspace is not mapped|not mapped to a shipsy org|does not have a mapped org|skipping auto-investigation/i.test(allb)){ skipped++; continue; }
      if(/investigation failed|failed to (?:complete|run)|unhandled (?:error|exception)/i.test(allb)){ failed++; continue; }
      const rca=fri.find(c=>/##\s*Root Cause Analysis/i.test(c.body)||/\[Auto-Investigation Draft Response\]/i.test(c.body));
      if(!rca){ ranNoRCA++; continue; }                       // ran but no judgeable RCA — NOT 'never ran'
      const ext=fri.filter(c=>c.vis==="external").sort((a,b)=>(a.at<b.at?-1:a.at>b.at?1:0))[0];
      const postFri=comments.filter(c=>!isFriday(c.by)&&c.at>rca.at&&!/feedback to friday is pending/i.test(c.body));
      const fb=comments.filter(c=>!isFriday(c.by)&&norm(c.body).startsWith("feedback to friday")&&!/is pending/i.test(c.body));
      const full=(await api("/works.get",{id:t.id})).work; const an=c=>c.by?.display_name||c.by?.full_name||c.by?.display_id||"unknown";
      fs.writeFileSync(path.join(RUN,"bundles",t.display_id+".json"),JSON.stringify({
        id:t.display_id, org:orgOf(full), title:full.title, severity:full.severity, closeDay:RUN_DATE,
        evidenceIncomplete:capped, sentiment:sentimentOf(full.sentiment),
        resolvedBy:full.custom_fields?.tnt__resolved_by||null,
        humanRCA:trunc(full.custom_fields?.ctype__root_cause_and_resolution_details,1200),
        friday_rca:trunc(rca.body,3200), friday_external_to_customer: ext?trunc(ext.body,2200):null,
        human_feedback_to_friday: fb.map(f=>({by:an(f),text:trunc(f.body,800)})),
        activity_after_friday: postFri.slice(0,10).map(c=>({by:an(c),vis:c.vis,text:trunc(c.body,700)})),
      },null,2)); judgeIds.push(t.display_id);
    }catch(e){ errors++; } } }));
}
const fridayRan = judgeIds.length + skipped + failed + ranNoRCA;   // scope - neverRan
const funnel={ date:RUN_DATE, tz:cfg.timezone, resolvedTotal, excludedByOrg, inScope:scope.length,
  fridayRan, judgeable:judgeIds.length, skipped, failed, ranNoRCA, neverRan, errors,
  truncated, overCap, reachedPast, pagesScanned:pages };
fs.writeFileSync(path.join(RUN,"funnel.json"),JSON.stringify(funnel,null,2));
fs.writeFileSync(path.join(RUN,"judge-ids.json"),JSON.stringify(judgeIds));
console.log(JSON.stringify(funnel));
if(truncated||overCap) process.exit(4);                            // signal the gate
