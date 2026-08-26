/* ============================================================
   1. PASTE YOUR DEPLOYED CLOUD RUN URL HERE (no trailing slash)
   Leave null and every demo runs on cached samples.
   ============================================================ */
const API_BASE = "https://governance-api-806052580337.asia-south1.run.app";

/* ============================================================
   2. RESUME — every page renders from this object. Edit here only.
   ============================================================ */
const RESUME = {
  name:"Aayera Ahmad",
  location:"Bengaluru, India",
  email:"aayera1029@gmail.com",
  phone:"+91 7408478673",
  linkedin:"https://linkedin.com/in/aayeraahmad531",
  github:"https://github.com/aayeraahmad531",
  resumePdf:"Aayera_Ahmad_CV.pdf",

  summary:"I build <strong>LLM-powered applications, RAG pipelines and agentic workflows</strong>, and deploy them as containerised services on GCP. Four years at Harman Connected Services across cloud infrastructure and generative AI, with Google certifications in Generative AI, Vertex AI, Agentic AI and Responsible AI. The work I care most about is <strong>making model output trustworthy enough to ship</strong> — grounding answers in verified sources, evaluating across model families, and knowing what a system does when it is wrong.",

  experience:[{
    role:"Engineer — AI & Cloud",
    org:"Harman Connected Services",
    where:"Bengaluru",
    when:"Mar 2022 — Present",
    bullets:[
      "Developed LLM-powered applications and conversational agents using OpenAI and Gemini APIs with LangChain, reducing manual effort across business workflows.",
      "Built and optimised RAG pipelines using vector databases and embedding models to ground LLM responses in verified sources and reduce hallucinations.",
      "Applied prompt engineering including few-shot prompting and structured outputs to improve response consistency across production use cases.",
      "Engineered FastAPI microservices connecting LLM APIs and Vertex AI endpoints to internal tools and data pipelines.",
      "Deployed containerised AI services on GCP Cloud Run with GitHub Actions CI/CD, logging and monitoring.",
      "Ran model evaluation across OpenAI, Gemini and Vertex AI families, assessing accuracy, latency and cost to guide model selection.",
      "Contributed to GCP infrastructure work supporting AI service delivery, including Cloud Run deployments and backend API integration."
    ]
  }],

  skills:[
    {group:"AI & LLMs", items:"OpenAI · Gemini · Vertex AI · LangChain · LangGraph · Prompt engineering · RAG pipelines · Agentic AI · Vector databases · Embeddings · Model evaluation · LLM orchestration"},
    {group:"Cloud & Backend", items:"GCP (Cloud Run, Vertex AI, Cloud SQL) · Python · FastAPI · REST APIs · Docker · CI/CD with GitHub Actions"},
    {group:"Practices", items:"Prompt optimisation · Model evaluation · Responsible AI · Agile and Scrum · JIRA"}
  ],

  certifications:[
    {name:"AI Agents Intensive — Agentic AI & Multi-Agent Systems", issuer:"Kaggle & Google · 2025"},
    {name:"Generative AI with Vertex AI", issuer:"Google Cloud · 2026"},
    {name:"Introduction to Large Language Models", issuer:"Google Cloud · 2026"},
    {name:"Prompt Design", issuer:"Google Cloud · 2026"},
    {name:"Responsible AI", issuer:"Google Cloud · 2026"},
    {name:"Serverless Applications on Cloud Run", issuer:"Google Cloud · 2025"},
    {name:"CI/CD Pipelines on Google Cloud", issuer:"Google Cloud · 2025"}
  ],

  education:[{
    degree:"B.Tech — Information Technology",
    school:"Dr. A.P.J. Abdul Kalam Technical University, Lucknow",
    when:"2018 — 2022", note:"CGPA 7.28"
  }]
};

/* ---------- cached samples (zero API cost) ---------- */
const SAMPLE = {
  bias:{overall_bias_score:.92,
    spans:[{text:"young, energetic salesman",category:"gender"},{text:"10+ years experience",category:"age"},{text:"cultural fit for our Western team",category:"cultural"},{text:"rockstar",category:"gender"}],
    categories:[
      {bias_type:"gender",detected:true,confidence:.85,examples:["salesman","he","rockstar","crush targets"],suggestion:"Replace gendered titles and pronouns with neutral equivalents, and swap aggressive masculine-coded verbs for plain descriptions of the work."},
      {bias_type:"age",detected:true,confidence:.96,examples:["young","energetic","10+ years"],suggestion:"Remove youth-coded adjectives and re-check whether the years requirement is genuinely essential at this level."},
      {bias_type:"cultural",detected:true,confidence:.94,examples:["Western team","cultural fit"],suggestion:"Replace subjective cultural criteria with objective competencies and stated company values."}],
    summary:"Flagged bias across 3 categories. Revisions recommended before publishing."},
  comp:{compliant:false,score:50,
    summary:"The described lending system breaches core EU AI Act requirements. Automatic denial without human review conflicts with Article 14, and postal code as a decision input creates proxy discrimination risk under Article 10.",
    violations:[
      {principle:"Human oversight",severity:"high",article_reference:"Art. 14",description:"Fully automated credit denial with no human review or appeal path fails oversight requirements for high-risk systems.",action:"Add a mandatory human review step before any final rejection is issued.",source:"High-risk AI systems shall be designed and developed in such a way that they can be effectively overseen by natural persons during the period in which they are in use."},
      {principle:"Non-discrimination",severity:"high",article_reference:"Art. 10",description:"Postal code is a documented proxy for race and income, producing indirect discriminatory impact.",action:"Drop geographic features from decision inputs and run demographic parity tests on the remainder.",source:"Training, validation and testing data sets shall be subject to data governance appropriate to the intended purpose, including examination in view of possible biases."}]},
  hall:{topic:"Discovery of Radium",questions_tested:3,hallucination_rate:.33,
    results:[
      {question:"Who discovered radium?",answer:"Marie and Pierre Curie discovered radium.",verdict:"ACCURATE",confidence:1,reasoning:"Matches the retrieved passage directly.",source:"Radium was discovered in 1898 by Marie and Pierre Curie, who extracted it from pitchblende residues."},
      {question:"In what year was radium isolated in pure metallic form?",answer:"1902, by Marie Curie alone.",verdict:"HALLUCINATED",confidence:.9,reasoning:"The retrieved passage gives 1910 and names two people. 1902 was the year radium chloride was isolated, not the metal.",source:"Pure metallic radium was first isolated in 1910 by Marie Curie and André-Louis Debierne through electrolysis."},
      {question:"What element was discovered alongside radium?",answer:"Polonium, earlier the same year.",verdict:"ACCURATE",confidence:.95,reasoning:"Consistent with the retrieved passage.",source:"The Curies announced polonium in July 1898 and radium in December of the same year."}]}
};

/* ---------- helpers ---------- */
const $ = id => document.getElementById(id);
const esc = s => {const d=document.createElement("div");d.textContent=(s==null?"":s);return d.innerHTML};

/* scroll reveal */
document.addEventListener("DOMContentLoaded",()=>{
  const els=document.querySelectorAll(".rv,.flag");
  if(!("IntersectionObserver" in window)){els.forEach(e=>e.classList.add("in"));return}
  const io=new IntersectionObserver((es,o)=>{
    es.forEach((e,i)=>{if(e.isIntersecting){setTimeout(()=>e.target.classList.add("in"),i*90);o.unobserve(e.target)}})
  },{rootMargin:"0px 0px -8% 0px"});
  els.forEach(e=>io.observe(e));
});

/* warm the container when a demo comes into view */
let warmed=false;
function warmOn(elId){
  if(!API_BASE||!("IntersectionObserver" in window))return;
  const t=$(elId); if(!t) return;
  const io=new IntersectionObserver(es=>{
    if(!warmed&&es.some(e=>e.isIntersecting)){warmed=true;io.disconnect();fetch(API_BASE+"/health").catch(()=>{})}
  },{rootMargin:"120% 0px"});
  io.observe(t);
}

function markLive(key){
  if(!API_BASE)return;
  const d=$("dot-"+key),m=$("mode-"+key);
  if(d)d.classList.add("live"); if(m)m.textContent="live";
}

function count(k){
  const el=$("in-"+k),c=$("c-"+k); if(!el||!c)return;
  const n=el.value.length; c.textContent=n+" / 2000"; c.classList.toggle("over",n>2000);
}

async function call(key,path,payload,btn,label){
  if(!API_BASE) return {data:SAMPLE[key],cached:true};
  btn.disabled=true;btn.textContent="Running…";
  try{
    const ctrl=new AbortController(),t=setTimeout(()=>ctrl.abort(),60000);
    const r=await fetch(API_BASE+path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload),signal:ctrl.signal});
    clearTimeout(t);
    if(r.status===429) return {error:"Hourly limit reached. Showing a cached result.",data:SAMPLE[key],cached:true};
    if(r.status===422) return {error:"Input rejected — check the length limit.",data:SAMPLE[key],cached:true};
    if(!r.ok) throw new Error("HTTP "+r.status);
    return {data:await r.json(),cached:false};
  }catch(e){
    return {error:"Service didn't respond. Showing a cached result.",data:SAMPLE[key],cached:true};
  }finally{btn.disabled=false;btn.textContent=label}
}
const banner = r => r.error?'<p class="err">'+esc(r.error)+'</p>':(r.cached?'<p class="err">Cached sample — no live service configured yet.</p>':"");
const sevCls = s => ({high:"high",medium:"med",med:"med",low:"low"})[String(s).toLowerCase()]||"low";

function redline(text,spans){
  if(!spans||!spans.length) return esc(text);
  const marks=[];
  spans.forEach(s=>{const i=text.indexOf(s.text);if(i>=0)marks.push({s:i,e:i+s.text.length,c:s.category||"gender"})});
  marks.sort((a,b)=>a.s-b.s);
  let out="",pos=0;
  marks.forEach(m=>{if(m.s<pos)return;out+=esc(text.slice(pos,m.s));out+='<mark data-sev="'+esc(m.c)+'" title="'+esc(m.c)+'">'+esc(text.slice(m.s,m.e))+'</mark>';pos=m.e});
  return out+esc(text.slice(pos));
}

/* ---------- demo runners ---------- */
const DEFAULTS = {
  bias:"We are looking for a young, energetic salesman with 10+ years experience. He should be a cultural fit for our Western team and a real rockstar who can crush targets.",
  comp:"Our AI model automatically rejects credit applications for applicants living in specific postal codes without human intervention.",
  ctx:"Fintech automated lending system"
};

async function runBias(btn){
  const box=$("out-bias"),text=$("in-bias").value;
  box.classList.add("show");box.innerHTML='<p class="err">Matching against the bias lexicon…</p>';
  const res=await call("bias","/api/bias",{job_description:text,analysis_type:["gender","age","cultural"]},btn,"Run audit");
  const d=res.data;
  let h=banner(res)+'<div class="verdict"><span class="big">'+Math.round(d.overall_bias_score*100)+'%</span><span class="cap">bias score · '+d.categories.filter(c=>c.detected).length+' categories flagged</span></div>';
  h+='<div class="redline">'+redline(text,d.spans)+'</div>';
  if(d.observations&&d.observations.length){
    h+='<div class="obs"><b>Noted, not flagged</b><ul>'+
       d.observations.map(function(o){return '<li>'+esc(o)+'</li>'}).join("")+
       '</ul></div>';
  }
  d.categories.forEach(c=>{
    h+='<div class="finding"><div class="finding-top">'+
       '<span class="sev '+(c.detected?(c.confidence>.9?"high":"med"):"clear")+'">'+(c.detected?"flagged":"clear")+'</span>'+
       '<span class="finding-name">'+esc(c.bias_type)+'</span>'+
       '<span class="art">confidence '+Math.round(c.confidence*100)+'%</span></div>'+
       '<div class="terms">'+(c.examples||[]).map(e=>'<span class="term">'+esc(e)+'</span>').join("")+'</div>'+
       '<div class="fix">'+esc(c.suggestion)+'</div></div>';
  });
  if(d.summary)h+='<p class="fix" style="margin-top:18px">'+esc(d.summary)+'</p>';
  box.innerHTML=h;
}
function resetBias(){$("in-bias").value=DEFAULTS.bias;count("bias");$("out-bias").classList.remove("show")}

async function runComp(btn){
  const box=$("out-comp");
  box.classList.add("show");box.innerHTML='<p class="err">Retrieving relevant articles…</p>';
  const res=await call("comp","/api/compliance",{content:$("in-comp").value,context:$("ctx-comp").value},btn,"Check compliance");
  const d=res.data,recs=d.recommendations||[];
  let h=banner(res)+'<div class="verdict"><span class="big" style="color:'+(d.compliant?"var(--clear)":"var(--high)")+'">'+(d.compliant?"Compliant":"Not compliant")+'</span><span class="cap">score '+d.score+'/100 · '+(d.violations||[]).length+' violations</span></div>';
  (d.violations||[]).forEach(v=>{
    const fix=v.action||(recs.find(r=>r.principle===v.principle)||{}).action||"";
    h+='<div class="finding"><div class="finding-top">'+
       '<span class="sev '+sevCls(v.severity)+'">'+esc(v.severity)+'</span>'+
       '<span class="finding-name">'+esc(v.principle)+'</span>'+
       '<span class="art">'+esc(v.article_reference)+'</span></div>'+
       '<p>'+esc(v.description)+'</p>'+
       (fix?'<div class="fix">'+esc(fix)+'</div>':"")+
       (v.source?'<div class="src"><b>Retrieved source</b>'+esc(v.source)+'</div>':"")+'</div>';
  });
  if(d.summary)h+='<p class="fix" style="margin-top:18px">'+esc(d.summary)+'</p>';
  box.innerHTML=h;
}
function resetComp(){$("in-comp").value=DEFAULTS.comp;$("ctx-comp").value=DEFAULTS.ctx;count("comp");$("out-comp").classList.remove("show")}

async function runHall(btn){
  const box=$("out-hall");
  box.classList.add("show");box.innerHTML='<p class="err">Generating questions, answering, then grading against sources. This takes a few seconds…</p>';
  const res=await call("hall","/api/hallucination",{topic:$("in-hall").value,num_questions:Math.min(3,+$("n-hall").value||3)},btn,"Run test");
  const d=res.data;
  let h=banner(res)+'<div class="verdict"><span class="big" style="color:'+(d.hallucination_rate>0?"var(--high)":"var(--clear)")+'">'+Math.round(d.hallucination_rate*100)+'%</span><span class="cap">hallucination rate · '+d.questions_tested+' questions on '+esc(d.topic)+'</span></div>';
  (d.results||[]).forEach(r=>{
    const v=String(r.verdict).toUpperCase();
    const cls=v==="ACCURATE"?"clear":(v==="HALLUCINATED"?"high":"med");
    h+='<div class="finding"><div class="finding-top">'+
       '<span class="sev '+cls+'">'+esc(v)+'</span><span class="art">confidence '+Math.round(r.confidence*100)+'%</span></div>'+
       '<div class="qa"><div class="q">'+esc(r.question)+'</div><div class="a">'+esc(r.answer)+'</div></div>'+
       '<div class="fix">'+esc(r.reasoning)+'</div>'+
       (r.source?'<div class="src"><b>Graded against</b>'+esc(r.source)+'</div>':"")+'</div>';
  });
  box.innerHTML=h;
}
function resetHall(){$("in-hall").selectedIndex=0;$("n-hall").value=3;$("out-hall").classList.remove("show")}

/* ---------- shared footer ---------- */
function renderFooter(){
  const l=$("r-links"); if(!l) return;
  l.innerHTML=[["Email","mailto:"+RESUME.email],["GitHub",RESUME.github],["LinkedIn",RESUME.linkedin],["Résumé (PDF)",RESUME.resumePdf]]
    .map(([t,h])=>'<a href="'+esc(h)+'"'+(h.indexOf("http")===0?' target="_blank" rel="noopener"':"")+'>'+esc(t)+'</a>').join("");
  const f=$("r-fine");
  if(f)f.innerHTML=esc(RESUME.location)+" · "+esc(RESUME.phone)+
    "<br>Demos call a service that sleeps when idle. The first run may take a few seconds to wake it.";
}
document.addEventListener("DOMContentLoaded",renderFooter);

/* ---------- experience accordion ---------- */
document.addEventListener("DOMContentLoaded",function(){
  const items=document.querySelectorAll(".acc-item");
  items.forEach(function(it){
    const btn=it.querySelector(".acc-head");
    if(!btn)return;
    btn.addEventListener("click",function(){
      const open=it.hasAttribute("data-open");
      items.forEach(function(o){
        o.removeAttribute("data-open");
        const b=o.querySelector(".acc-head");
        if(b)b.setAttribute("aria-expanded","false");
      });
      if(!open){it.setAttribute("data-open","1");btn.setAttribute("aria-expanded","true")}
    });
  });
});

/* ---------- skills filter ---------- */
document.addEventListener("DOMContentLoaded",function(){
  const btns=document.querySelectorAll(".filt");
  const tiles=document.querySelectorAll(".tile");
  if(!btns.length||!tiles.length)return;
  btns.forEach(function(b){
    b.addEventListener("click",function(){
      const f=b.getAttribute("data-f");
      btns.forEach(function(x){x.classList.remove("on")});
      b.classList.add("on");
      tiles.forEach(function(t){
        t.classList.toggle("hide", f!=="all" && t.getAttribute("data-cat")!==f);
      });
    });
  });
});


/* ---------- hero: adversarial challenge ----------
   Visitor writes a false claim; the tester retrieves a source and grades it.
   Requires POST /api/challenge {topic, claim} -> {verdict, confidence, reasoning, source}
   Falls back to a canned response if the endpoint is unavailable. */
document.addEventListener("DOMContentLoaded",function(){
  const box=$("puz"); if(!box) return;
  const go=$("puz-go"), out=$("puz-out"), prog=$("puz-prog"),
        hint=$("puz-hint"), claimEl=$("puz-claim"), topicEl=$("puz-topic");

  let left=3, caught=0, slipped=0, log=[];

  const FALLBACK={verdict:"HALLUCINATED",confidence:.93,
    reasoning:"The retrieved passage contradicts this claim on a specific detail. Nothing in the indexed source supports it.",
    source:"Radium was discovered in 1898 by Marie and Pierre Curie, who extracted it from pitchblende residues at Jáchymov."};

  function paint(){
    prog.textContent = left>0 ? left+" attempt"+(left>1?"s":"")+" left" : "Done";
    let h="";
    log.forEach(function(e){
      const cls = e.verdict==="ACCURATE" ? "ok" : (e.verdict==="HALLUCINATED" ? "hal" : "hal");
      h+='<div class="puz-try"><div class="tq">“'+esc(e.claim)+'”</div>'+
         '<div class="tr2"><span class="pv '+cls+'">'+esc(e.verdict)+'</span>'+
         '<span class="puz-hint" style="margin:0">confidence '+Math.round(e.confidence*100)+'%</span></div>'+
         '<div class="psrc"><b>Why</b>'+esc(e.reasoning)+'</div>'+
         (e.source?'<div class="psrc"><b>Retrieved source</b>'+esc(e.source)+'</div>':'')+'</div>';
    });
    if(left===0){
      h+='<div class="pfinal" style="padding-top:22px;border-top:1px solid #22272F;margin-top:18px">'+
         '<div class="fs">Caught '+caught+' of 3'+(slipped?' <span>· '+slipped+' slipped through</span>':' <span>· nothing slipped through</span>')+'</div>'+
         '<p>'+(slipped
            ? 'One got past — which is worth knowing, and exactly why the tester returns the passage it graded against rather than just a verdict. You can check its work.'
            : 'Every claim was checked against a retrieved passage, not against the model\'s memory. That is the whole difference: the grader has to point at something.')+
         '</p></div>';
    }
    out.innerHTML=h;
    out.classList.toggle("show", !!h);
  }

  go.addEventListener("click",async function(){
    const claim=(claimEl.value||"").trim();
    if(claim.length<12){hint.textContent="Write a bit more — at least a full sentence.";return}
    if(left===0) return;
    go.disabled=true; go.textContent="Checking…";
    hint.textContent="retrieving a source and grading…";

    let d=FALLBACK, live=false;
    if(API_BASE){
      try{
        const ctrl=new AbortController(), kill=setTimeout(()=>ctrl.abort(),45000);
        const r=await fetch(API_BASE+"/api/challenge",{method:"POST",
          headers:{"Content-Type":"application/json"},
          body:JSON.stringify({topic:topicEl.value,claim:claim}),signal:ctrl.signal});
        clearTimeout(kill);
        if(r.ok){d=await r.json();live=true}
      }catch(e){}
    }
    go.disabled=false; go.textContent="Submit claim";

    const v=String(d.verdict||"UNCERTAIN").toUpperCase();
    if(v==="HALLUCINATED") caught++; else slipped++;
    log.unshift({claim:claim, verdict:v, confidence:d.confidence||0,
                 reasoning:d.reasoning||"", source:d.source||""});
    left--;
    claimEl.value="";
    hint.textContent = live
      ? (left>0 ? "Try a subtler one — change a date, not the whole story." : "")
      : "Service unreachable — showing a cached example.";
    if(left===0){ go.disabled=true; go.textContent="Out of attempts";
      go.insertAdjacentHTML("afterend",
        '<a class="pbtn" href="hallucination.html" style="text-decoration:none;margin-left:10px">Run the full tester</a>'); }
    paint();
  });

  claimEl.addEventListener("keydown",function(e){
    if((e.metaKey||e.ctrlKey)&&e.key==="Enter") go.click();
  });
});
