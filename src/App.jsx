import { useState, useRef, useEffect, useCallback, useMemo } from "react";

const COLORS = ["#2563eb","#059669","#7c3aed","#dc2626","#d97706","#0891b2","#4f46e5","#e11d48"];
const MAST = {
  "1.1":{l:"Disobey task spec",c:"FC1"},"1.2":{l:"Disobey role spec",c:"FC1"},
  "1.3":{l:"Step repetition",c:"FC1"},"1.4":{l:"Lost history",c:"FC1"},
  "1.5":{l:"No stopping condition",c:"FC1"},"2.1":{l:"Conv reset",c:"FC2"},
  "2.2":{l:"No clarification",c:"FC2"},"2.3":{l:"Task derail",c:"FC2"},
  "2.4":{l:"Info withholding",c:"FC2"},"2.5":{l:"Ignores input",c:"FC2"},
  "2.6":{l:"Reason-action mismatch",c:"FC2"},"3.1":{l:"Premature end",c:"FC3"},
  "3.2":{l:"No verification",c:"FC3"},"3.3":{l:"Bad verification",c:"FC3"},
};

function ac(agent, agents) {
  if (agent === "Conclusion") return "#6b7280";
  const i = agents.indexOf(agent);
  return COLORS[i >= 0 ? i % COLORS.length : 0];
}

const AG2_DATA = {
  meta:{framework:"AG2",benchmark:"critical thinking",llm:"unknown",total_turns:10,
    problem_statement:"Monica is wrapping Christmas gifts. She has 6 gifts for family, 4 for friends, 2 for teachers. How many inches of ribbon per bow?",
    note_text:"The mathproxyagent keeps asking to continue despite the problem being unsolvable."},
  agents:["mathproxyagent","assistant"],
  failures:{"1.5":{label:"Unaware of stopping conditions",category:"FC1"},"2.5":{label:"Ignored other agent's input",category:"FC2"}},
  turns:[
    {index:0,agent:"mathproxyagent",content:"Let's use Python to solve a math problem.\n\nProblem: Monica has 6 gifts for family, 4 for friends, 2 for teachers. How many inches of ribbon per bow?",phase:"",summary:"setup problem",failures:[],divergence:false,in_loop:false},
    {index:1,agent:"assistant",content:"This problem cannot be solved with the information provided. No ribbon amount is specified.",phase:"",summary:"insufficient data",failures:[],divergence:false,in_loop:false},
    {index:2,agent:"mathproxyagent",content:"Continue. Please keep solving the problem until you need to query.",phase:"",summary:"continue",failures:["1.5","2.5"],divergence:true,in_loop:true},
    {index:3,agent:"assistant",content:"I don't have enough information. I need:\n1. Total ribbon length?\n2. Inches per bow?\nWithout this, unsolvable.",phase:"",summary:"re-explains",failures:[],divergence:false,in_loop:true},
    {index:4,agent:"mathproxyagent",content:"Continue. Please keep solving the problem until you need to query.",phase:"",summary:"continue",failures:["1.5","2.5"],divergence:true,in_loop:true},
    {index:5,agent:"assistant",content:"I really need more information. It can't be solved with current data.",phase:"",summary:"re-explains",failures:[],divergence:false,in_loop:true},
    {index:6,agent:"mathproxyagent",content:"Continue. Please keep solving the problem until you need to query.",phase:"",summary:"continue",failures:["1.5","2.5"],divergence:true,in_loop:true},
    {index:7,agent:"assistant",content:"We cannot solve this — crucial data is missing.",phase:"",summary:"re-explains",failures:[],divergence:false,in_loop:true},
    {index:8,agent:"mathproxyagent",content:"Continue. Please keep solving the problem until you need to query.",phase:"",summary:"continue",failures:["1.5","2.5"],divergence:true,in_loop:true},
    {index:9,agent:"assistant",content:"The problem cannot be solved. Data insufficient.",phase:"",summary:"final answer",failures:[],divergence:false,in_loop:false},
  ],
  loops:[{start:2,end:9}],
  beliefs:{mathproxyagent:"Task should continue",assistant:"Task is blocked"},
  has_divergence:true,
};

const CHATDEV_DATA = {"meta":{"framework":"ChatDev","benchmark":"ProgramDev","llm":"GPT-4o","total_turns":37,"problem_statement":"Write a program that generates Fibonacci numbers up to a given number","note_text":""},"agents":["Chief Executive Officer","Chief Product Officer","Conclusion","Chief Technology Officer","Programmer","Code Reviewer","Counselor"],"failures":{"1.1":{"label":"Disobey task specification","category":"FC1"},"2.6":{"label":"Reasoning-action mismatch","category":"FC2"},"3.3":{"label":"Incorrect verification","category":"FC3"}},"turns":[{"index":0,"agent":"Chief Executive Officer","content":"Which product modality do we want?","phase":"DemandAnalysis","short":"start chat","annotations":[]},{"index":1,"agent":"Chief Product Officer","content":"The most suitable modality would be an Application.","phase":"DemandAnalysis","short":"application","annotations":[]},{"index":2,"agent":"Chief Executive Officer","content":"I completely agree. <INFO> Application","phase":"DemandAnalysis","short":"agree","annotations":[]},{"index":3,"agent":"Conclusion","content":"<INFO> Application","phase":"DemandAnalysis","short":"Application","annotations":[]},{"index":4,"agent":"Chief Executive Officer","content":"Which programming language?","phase":"LanguageChoose","short":"start chat","annotations":[]},{"index":5,"agent":"Chief Technology Officer","content":"<INFO> Python","phase":"LanguageChoose","short":"Python","annotations":[]},{"index":6,"agent":"Conclusion","content":"<INFO> Python","phase":"LanguageChoose","short":"Python","annotations":[]},{"index":7,"agent":"Chief Technology Officer","content":"Write files implementing the Fibonacci generator.","phase":"Coding","short":"start chat","annotations":[]},{"index":8,"agent":"Programmer","content":"Created fibonacci.py and main.py.","phase":"Coding","short":"writes code","annotations":[]},{"index":9,"agent":"Conclusion","content":"main.py + fibonacci.py. 38 lines.","phase":"Coding","short":"code complete","annotations":[]},{"index":10,"agent":"Programmer","content":"Please review the code.","phase":"CodeReviewComment","short":"requests review","annotations":[]},{"index":11,"agent":"Code Reviewer","content":"<INFO> Finished","phase":"CodeReviewComment","short":"finished","annotations":[{"code":"3.3","type":"failure"}]},{"index":12,"agent":"Conclusion","content":"<INFO> Finished","phase":"CodeReviewComment","short":"finished","annotations":[]},{"index":13,"agent":"Code Reviewer","content":"Modify codes according to comments.","phase":"CodeReviewModification","short":"modify request","annotations":[]},{"index":14,"agent":"Programmer","content":"Updated output formatting. Added run.sh.","phase":"CodeReviewModification","short":"minor fix","annotations":[]},{"index":15,"agent":"Conclusion","content":"Code updated. 38 lines.","phase":"CodeReviewModification","short":"updated","annotations":[]},{"index":16,"agent":"Programmer","content":"Please review again.","phase":"CodeReviewComment","short":"requests review","annotations":[]},{"index":17,"agent":"Code Reviewer","content":"<INFO> Finished","phase":"CodeReviewComment","short":"finished","annotations":[{"code":"3.3","type":"failure"}]},{"index":18,"agent":"Conclusion","content":"<INFO> Finished","phase":"CodeReviewComment","short":"finished","annotations":[]},{"index":19,"agent":"Code Reviewer","content":"Modify codes.","phase":"CodeReviewModification","short":"modify request","annotations":[]},{"index":20,"agent":"Programmer","content":"No changes — code returned as-is.","phase":"CodeReviewModification","short":"no changes","annotations":[{"code":"2.6","type":"failure"}]},{"index":21,"agent":"Conclusion","content":"Same code.","phase":"CodeReviewModification","short":"no changes","annotations":[]},{"index":22,"agent":"Programmer","content":"Please review again.","phase":"CodeReviewComment","short":"requests review","annotations":[]},{"index":23,"agent":"Code Reviewer","content":"<INFO> Finished","phase":"CodeReviewComment","short":"finished","annotations":[{"code":"3.3","type":"failure"}]},{"index":24,"agent":"Conclusion","content":"<INFO> Finished","phase":"CodeReviewComment","short":"finished","annotations":[]},{"index":25,"agent":"Code Reviewer","content":"Modify codes.","phase":"CodeReviewModification","short":"modify request","annotations":[]},{"index":26,"agent":"Programmer","content":"No changes.","phase":"CodeReviewModification","short":"no changes","annotations":[{"code":"2.6","type":"failure"}]},{"index":27,"agent":"Conclusion","content":"Same code.","phase":"CodeReviewModification","short":"no changes","annotations":[]},{"index":28,"agent":"Chief Technology Officer","content":"Write requirements.txt.","phase":"EnvironmentDoc","short":"request deps","annotations":[]},{"index":29,"agent":"Programmer","content":"requirements.txt: no external deps.","phase":"EnvironmentDoc","short":"no deps","annotations":[]},{"index":30,"agent":"Counselor","content":"Confirmed requirements.","phase":"Reflection","short":"confirmed","annotations":[]},{"index":31,"agent":"Chief Executive Officer","content":"Reviewed and confirmed.","phase":"Reflection","short":"confirmed","annotations":[]},{"index":32,"agent":"Conclusion","content":"requirements.txt confirmed.","phase":"Reflection","short":"confirmed","annotations":[]},{"index":33,"agent":"Conclusion","content":"<INFO> requirements.txt","phase":"Reflection","short":"requirements","annotations":[]},{"index":34,"agent":"Chief Executive Officer","content":"Write manual.md.","phase":"Manual","short":"request manual","annotations":[]},{"index":35,"agent":"Chief Product Officer","content":"Created manual.md.","phase":"Manual","short":"writes manual","annotations":[]},{"index":36,"agent":"Conclusion","content":"manual.md complete. 322s, 10558 tokens.","phase":"Manual","short":"project done","annotations":[{"code":"1.1","type":"failure"}]}],"loops":[],"beliefs":{"beliefs":{"Chief Executive Officer":"Task complete","Chief Product Officer":"Task complete","Chief Technology Officer":"Task complete","Programmer":"Task complete","Code Reviewer":"Task complete","Counselor":"Working on the task"},"has_divergence":true}};

/* ═══ AGENT GRAPH ═══ */
function buildGraph(turns, agents) {
  const counts = {};
  turns.forEach(t => { counts[t.agent] = (counts[t.agent] || 0) + 1; });
  const ec = {}, ep = {};
  for (let i = 0; i < turns.length - 1; i++) {
    const s = turns[i].agent, d = turns[i+1].agent;
    if (s !== d) {
      const k = s + "\x00" + d;
      ec[k] = (ec[k] || 0) + 1;
      const ph = turns[i].phase || "";
      if (ph) { ep[k] = ep[k] || new Set(); ep[k].add(ph); }
    }
  }
  const skip = new Set(["System"]);
  const nodes = agents.filter(a => !skip.has(a)).map(id => ({ id, count: counts[id] || 0 }));
  const edges = Object.entries(ec)
    .filter(([k]) => { const [s,d] = k.split("\x00"); return !skip.has(s) && !skip.has(d); })
    .map(([k, w]) => { const [s,d] = k.split("\x00"); return { source: s, target: d, weight: w, phases: [...(ep[k]||[])] }; });
  return { nodes, edges };
}

function AgentGraph({ turns, agents, acFn }) {
  const svgRef = useRef(null);
  const animRef = useRef(null);
  const dragRef = useRef(null);
  const [pos, setPos] = useState(null);
  const [hov, setHov] = useState(null);
  const [dragging, setDragging] = useState(null);
  const graph = useMemo(() => buildGraph(turns, agents), [turns, agents]);
  const W = 700, H = 400;

  useEffect(() => {
    const n = graph.nodes.length;
    const cx = W/2, cy = H/2, r = Math.min(W,H)*0.3;
    const init = {};
    graph.nodes.forEach((nd, i) => {
      const a = (2*Math.PI*i)/n - Math.PI/2;
      init[nd.id] = { x: cx+r*Math.cos(a), y: cy+r*Math.sin(a), vx:0, vy:0 };
    });
    setPos(init);
  }, [graph]);

  useEffect(() => {
    if (!pos) return;
    let p = {}; Object.keys(pos).forEach(k => { p[k] = {...pos[k]}; });
    let tick = 0;
    function step() {
      if (tick > 180) return;
      tick++;
      const alpha = Math.max(0.001, 1 - tick/180);
      const {nodes, edges} = graph;
      for (let i=0;i<nodes.length;i++) for (let j=i+1;j<nodes.length;j++) {
        const a=p[nodes[i].id], b=p[nodes[j].id];
        let dx=b.x-a.x, dy=b.y-a.y, dist=Math.sqrt(dx*dx+dy*dy)||1;
        const f=7000/(dist*dist)*alpha;
        a.vx-=(dx/dist)*f; a.vy-=(dy/dist)*f;
        b.vx+=(dx/dist)*f; b.vy+=(dy/dist)*f;
      }
      edges.forEach(e => {
        const a=p[e.source], b=p[e.target]; if(!a||!b) return;
        let dx=b.x-a.x, dy=b.y-a.y, dist=Math.sqrt(dx*dx+dy*dy)||1;
        const f=(dist-120)*0.02*alpha;
        a.vx+=(dx/dist)*f; a.vy+=(dy/dist)*f;
        b.vx-=(dx/dist)*f; b.vy-=(dy/dist)*f;
      });
      nodes.forEach(n => { const q=p[n.id]; q.vx+=(W/2-q.x)*0.005*alpha; q.vy+=(H/2-q.y)*0.005*alpha; });
      nodes.forEach(n => {
        const q=p[n.id]; if(dragRef.current===n.id) return;
        q.vx*=0.55; q.vy*=0.55; q.x+=q.vx; q.y+=q.vy;
        q.x=Math.max(55,Math.min(W-55,q.x)); q.y=Math.max(45,Math.min(H-45,q.y));
      });
      setPos({...p});
      if(tick<180) animRef.current=requestAnimationFrame(step);
    }
    animRef.current=requestAnimationFrame(step);
    return () => { if(animRef.current) cancelAnimationFrame(animRef.current); };
  }, [graph, pos===null]);

  const onMD = useCallback((e, id) => { e.preventDefault(); dragRef.current=id; setDragging(id); }, []);
  useEffect(() => {
    if(!dragging) return;
    const svg = svgRef.current;
    const mv = (e) => { const r=svg.getBoundingClientRect(); const x=e.clientX-r.left, y=e.clientY-r.top;
      setPos(prev => prev ? {...prev,[dragging]:{...prev[dragging],x:Math.max(55,Math.min(W-55,x)),y:Math.max(45,Math.min(H-45,y)),vx:0,vy:0}} : prev); };
    const up = () => { dragRef.current=null; setDragging(null); };
    window.addEventListener("mousemove",mv); window.addEventListener("mouseup",up);
    return () => { window.removeEventListener("mousemove",mv); window.removeEventListener("mouseup",up); };
  }, [dragging]);

  if(!pos) return null;
  const maxW = Math.max(...graph.edges.map(e=>e.weight),1);
  const maxC = Math.max(...graph.nodes.map(n=>n.count),1);

  function epath(e) {
    const s=pos[e.source], t=pos[e.target]; if(!s||!t) return "";
    const dx=t.x-s.x, dy=t.y-s.y, dist=Math.sqrt(dx*dx+dy*dy)||1;
    const rev = graph.edges.some(o=>o.source===e.target&&o.target===e.source);
    const bend = (rev ? 0.35 : 0.12) * dist;
    const mx=(s.x+t.x)/2+(-dy/dist)*bend, my=(s.y+t.y)/2+(dx/dist)*bend;
    return `M${s.x},${s.y} Q${mx},${my} ${t.x},${t.y}`;
  }
  function arrowAt(e) {
    const s=pos[e.source], t=pos[e.target]; if(!s||!t) return {x:0,y:0,a:0};
    const dx=t.x-s.x, dy=t.y-s.y, dist=Math.sqrt(dx*dx+dy*dy)||1;
    const r=16+(graph.nodes.find(n=>n.id===e.target)?.count/maxC)*10;
    const rev=graph.edges.some(o=>o.source===e.target&&o.target===e.source);
    const bend=(rev?0.35:0.12)*dist;
    const mx=(s.x+t.x)/2+(-dy/dist)*bend, my=(s.y+t.y)/2+(dx/dist)*bend;
    const tt=1-(r+5)/dist;
    const px=(1-tt)*(1-tt)*s.x+2*(1-tt)*tt*mx+tt*tt*t.x;
    const py=(1-tt)*(1-tt)*s.y+2*(1-tt)*tt*my+tt*tt*t.y;
    const tdx=2*(1-tt)*(mx-s.x)+2*tt*(t.x-mx), tdy=2*(1-tt)*(my-s.y)+2*tt*(t.y-my);
    return {x:px,y:py,a:Math.atan2(tdy,tdx)*180/Math.PI};
  }
  function lbl(e) {
    const s=pos[e.source], t=pos[e.target]; if(!s||!t) return {x:0,y:0};
    const dx=t.x-s.x, dy=t.y-s.y, dist=Math.sqrt(dx*dx+dy*dy)||1;
    const rev=graph.edges.some(o=>o.source===e.target&&o.target===e.source);
    const bend=(rev?0.35:0.12)*dist;
    const mx=(s.x+t.x)/2+(-dy/dist)*bend, my=(s.y+t.y)/2+(dx/dist)*bend;
    return {x:.25*s.x+.5*mx+.25*t.x, y:.25*s.y+.5*my+.25*t.y};
  }
  const sn = (name) => ({
    "Chief Executive Officer":"CEO","Chief Product Officer":"CPO",
    "Chief Technology Officer":"CTO","Code Reviewer":"Reviewer"
  }[name] || (name.length>12?name.slice(0,11)+"…":name));

  return <div>
    <div style={{fontSize:10,color:"#aaa",fontFamily:"monospace",marginBottom:6}}>
      Drag nodes to rearrange · Hover for details · Edge labels = message count
    </div>
    <svg ref={svgRef} width={W} height={H} style={{background:"#fafaf9",borderRadius:8,border:"1px solid #e5e5e5",display:"block",cursor:dragging?"grabbing":"default"}}>
      {graph.edges.map((e,i) => {
        const sw=1+(e.weight/maxW)*3, hl=hov===e.source||hov===e.target;
        const a=arrowAt(e), l=lbl(e);
        return <g key={i}>
          <path d={epath(e)} fill="none" stroke={hl?"#555":"#ccc"} strokeWidth={sw} strokeOpacity={hl?.9:.6}/>
          <polygon points="0,-3.5 7,0 0,3.5" fill={hl?"#555":"#999"} transform={`translate(${a.x},${a.y}) rotate(${a.a})`}/>
          <text x={l.x} y={l.y} textAnchor="middle" dy={-5} style={{fontSize:9,fontFamily:"monospace",fill:hl?"#333":"#bbb",pointerEvents:"none"}}>{e.weight}</text>
        </g>;
      })}
      {graph.nodes.map(nd => {
        const p2=pos[nd.id]; if(!p2) return null;
        const r=16+(nd.count/maxC)*10, c=acFn(nd.id), hl=hov===nd.id;
        return <g key={nd.id} onMouseDown={ev=>onMD(ev,nd.id)} onMouseEnter={()=>setHov(nd.id)} onMouseLeave={()=>setHov(null)} style={{cursor:"grab"}}>
          {hl && <circle cx={p2.x} cy={p2.y} r={r+4} fill={c} opacity={.15}/>}
          <circle cx={p2.x} cy={p2.y} r={r} fill={c} opacity={hl?1:.8} stroke={hl?"#333":"#fff"} strokeWidth={hl?2:1.5}/>
          <text x={p2.x} y={p2.y} textAnchor="middle" dy=".35em" style={{fontSize:10,fontWeight:600,fill:"#fff",pointerEvents:"none",fontFamily:"system-ui"}}>{sn(nd.id)}</text>
          <text x={p2.x} y={p2.y+r+13} textAnchor="middle" style={{fontSize:9,fill:"#999",pointerEvents:"none",fontFamily:"monospace"}}>{nd.count} turns</text>
        </g>;
      })}
    </svg>
    {hov && (() => {
      const nd=graph.nodes.find(n=>n.id===hov);
      const out=graph.edges.filter(e=>e.source===hov), inp=graph.edges.filter(e=>e.target===hov);
      if(!nd) return null;
      return <div style={{marginTop:8,padding:"8px 10px",background:"#f8f8f6",borderRadius:6,border:"1px solid #e5e5e5",fontSize:11,color:"#555"}}>
        <span style={{fontWeight:600,color:acFn(hov)}}>{hov}</span>
        <span style={{color:"#aaa"}}> · {nd.count} turns</span>
        {out.length>0 && <div style={{marginTop:4}}><span style={{color:"#999",fontSize:10}}>→ sends to: </span>{out.map((e,i)=><span key={i} style={{fontFamily:"monospace",fontSize:10}}>{e.target} ×{e.weight}{i<out.length-1?", ":""}</span>)}</div>}
        {inp.length>0 && <div style={{marginTop:2}}><span style={{color:"#999",fontSize:10}}>← receives: </span>{inp.map((e,i)=><span key={i} style={{fontFamily:"monospace",fontSize:10}}>{e.source} ×{e.weight}{i<inp.length-1?", ":""}</span>)}</div>}
      </div>;
    })()}
  </div>;
}

/* ═══ Badge ═══ */
function Badge({code,type}){
  const m=MAST[code];
  if(type==="failure") return <span style={S.badgeFail}>FM-{code}{m?" "+m.l:""}</span>;
  return <span style={S.badgeDiverge}>{code==="divergence"?"⚡ divergence":"↻ re-explains"}</span>;
}

/* ═══ MAIN ═══ */
export default function App(){
  const [activeTrace,setActiveTrace]=useState("ag2");
  const [customTrace,setCustomTrace]=useState(null);
  const [view,setView]=useState("compact");
  const [drill,setDrill]=useState(-1);
  const fileRef=useRef(null);

  const D=customTrace||(activeTrace==="ag2"?AG2_DATA:CHATDEV_DATA);
  if(!D) return <div style={S.empty}>Select a trace or upload one.</div>;

  const agents=D.agents.filter(a=>a!=="System");
  const colW=Math.max(100,Math.min(170,700/Math.max(agents.length,1)));
  const inLoop=(i)=>(D.loops||[]).some(l=>i>=l.start&&i<=l.end);
  const acFn=(agent)=>ac(agent,agents);

  function handleUpload(e){
    const file=e.target.files[0]; if(!file) return;
    const reader=new FileReader();
    reader.onload=(ev)=>{
      try{
        const data=JSON.parse(ev.target.result);
        if(data.turns&&data.agents){
          data.turns=data.turns.map(t=>({...t,summary:t.summary||t.short||"",failures:t.failures||[],divergence:t.divergence||false,in_loop:t.in_loop||false}));
          if(data.beliefs&&!data.has_divergence&&data.beliefs.has_divergence!==undefined){data.has_divergence=data.beliefs.has_divergence;data.beliefs=data.beliefs.beliefs||data.beliefs;}
          setCustomTrace(data);setActiveTrace("custom");setDrill(-1);
        } else alert("Not a processed trace.");
      }catch(err){alert("Parse error: "+err.message);}
    };
    reader.readAsText(file);
  }

  function getAnn(t){
    if(t.annotations&&t.annotations.length>0) return t.annotations;
    const a=[];
    if(t.failures) t.failures.forEach(c=>a.push({code:c,type:"failure"}));
    if(t.divergence) a.push({code:"divergence",type:"divergence"});
    return a;
  }

  return <div style={S.app}>
    {/* Header */}
    <div style={S.header}>
      <span style={{fontSize:20,fontWeight:600}}>AgentTrace</span>
      <span style={S.tag}>{D.meta.framework} · {D.meta.benchmark}{D.meta.llm!=="unknown"?" · "+D.meta.llm:""}</span>
      <div style={S.legend}>
        {agents.map(a=><span key={a} style={S.legendItem}><span style={{...S.dot,background:ac(a,agents)}}/>{a.length>14?a.slice(0,14)+"…":a}</span>)}
        <span style={{fontSize:11,color:"#999"}}>{D.meta.total_turns} turns</span>
      </div>
    </div>
    {D.meta.problem_statement&&<p style={S.problem}>{D.meta.problem_statement.slice(0,150)}{D.meta.problem_statement.length>150?"…":""}</p>}

    {/* Toolbar */}
    <div style={S.toolbar}>
      <div style={{display:"flex",gap:0}}>
        {["compact","detailed","graph"].map((v,vi)=><button key={v} onClick={()=>{setView(v);setDrill(-1);}}
          style={{...S.viewBtn,...(view===v?S.viewBtnActive:{}),borderRadius:vi===0?"5px 0 0 5px":vi===2?"0 5px 5px 0":"0"}}>
          {v==="graph"?"⬡ graph":v}
        </button>)}
      </div>
      <button onClick={()=>{setActiveTrace("ag2");setCustomTrace(null);setDrill(-1);setView(v=>v==="graph"?v:"compact");}} style={{...S.traceBtn,...(activeTrace==="ag2"&&!customTrace?{background:"#f3f3f3"}:{})}}>AG2 sample</button>
      <button onClick={()=>{setActiveTrace("chatdev");setCustomTrace(null);setDrill(-1);setView(v=>v==="graph"?v:"compact");}} style={{...S.traceBtn,...(activeTrace==="chatdev"&&!customTrace?{background:"#f3f3f3"}:{})}}>ChatDev sample</button>
      <div style={{marginLeft:"auto",display:"flex",alignItems:"center",gap:8}}>
        <button onClick={()=>fileRef.current?.click()} style={S.uploadBtn}>↑ Upload JSON</button>
        <input ref={fileRef} type="file" accept=".json" onChange={handleUpload} style={{display:"none"}}/>
        {customTrace&&<span style={{fontSize:10,color:"#059669",fontFamily:"monospace"}}>✓ custom loaded</span>}
      </div>
    </div>

    {/* Main */}
    <div style={S.mainGrid}>
      <div style={{overflowX:"auto",paddingRight:16}}>

        {/* GRAPH VIEW */}
        {view==="graph"&&<div style={{padding:"12px 0"}}><AgentGraph turns={D.turns} agents={agents} acFn={acFn}/></div>}

        {/* TIMELINE VIEWS */}
        {view!=="graph"&&<>
          <div style={S.swimHeader}>
            {agents.map(a=><div key={a} style={{width:colW,textAlign:"center",padding:"5px 0"}}>
              <div style={{width:7,height:7,borderRadius:"50%",background:ac(a,agents),display:"inline-block",marginBottom:2}}/>
              <div style={{fontFamily:"monospace",fontSize:9,color:ac(a,agents),overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",padding:"0 2px"}}>{a}</div>
            </div>)}
          </div>
          {(()=>{let phase=""; return D.turns.map((t,i)=>{
            const parts=[];
            if(t.phase&&t.phase!==phase){phase=t.phase;parts.push(<div key={"p"+i} style={S.phaseDivider}><div style={S.phaseLine}/><span style={S.phaseLabel}>{phase}</span><div style={S.phaseLine}/></div>);}
            const il=t.in_loop||inLoop(i), ci=agents.indexOf(t.agent), c=ac(t.agent,agents), anns=getAnn(t), hasAnn=anns.length>0, summary=t.summary||t.short||"";
            if(view==="compact"){
              parts.push(<div key={i} onClick={()=>setDrill(drill===i?-1:i)} style={{...S.compactRow,borderLeft:il?"2.5px solid #dc2626":"2.5px solid transparent",background:il?"rgba(220,38,38,0.03)":drill===i?"#f8f8f8":"transparent"}}>
                <span style={S.turnNum}>{i+1}</span>
                <div style={{display:"flex",flex:1}}>
                  {agents.map((a,ai)=><div key={ai} style={{width:colW,display:"flex",alignItems:"center",justifyContent:"center"}}>
                    {ai===ci&&<><div style={{height:22,borderRadius:3,minWidth:16,maxWidth:colW-8,padding:"0 5px",display:"flex",alignItems:"center",justifyContent:"center",background:`${c}12`,border:`1px solid ${c}30`}}>
                      <span style={{fontSize:9.5,fontFamily:"monospace",color:"#555",whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis",maxWidth:colW-20}}>{summary}</span>
                    </div>{hasAnn&&<span style={S.failDot}/>}</>}
                  </div>)}
                </div>
              </div>);
            } else {
              const preview=t.content.length>300?t.content.slice(0,300)+"…":t.content;
              parts.push(<div key={i} onClick={()=>setDrill(drill===i?-1:i)} style={{...S.compactRow,borderLeft:il?"2.5px solid #dc2626":"2.5px solid transparent",background:il?"rgba(220,38,38,0.03)":drill===i?"#f8f8f8":"transparent",alignItems:"flex-start",minHeight:40}}>
                <span style={{...S.turnNum,paddingTop:4}}>{i+1}</span>
                <div style={{display:"flex",flex:1}}>
                  {agents.map((a,ai)=><div key={ai} style={{width:colW,display:"flex",justifyContent:"center",padding:"2px"}}>
                    {ai===ci&&<div style={{width:colW-8,padding:"6px 8px",borderRadius:5,background:`${c}08`,border:`1px solid ${c}20`}}>
                      <div style={{fontFamily:"monospace",fontSize:9,fontWeight:600,color:c,marginBottom:3}}>{a.length>16?a.slice(0,16)+"…":a}</div>
                      <div style={{fontSize:11,lineHeight:1.45,color:"#666",wordBreak:"break-word",whiteSpace:"pre-wrap"}}>{preview}</div>
                      {hasAnn&&<div style={{marginTop:4}}>{anns.map((ann,j)=><Badge key={j} code={ann.code} type={ann.type}/>)}</div>}
                    </div>}
                  </div>)}
                </div>
              </div>);
            }
            if(drill===i){parts.push(<div key={"d"+i} style={S.drillPanel}>
              <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:8}}>
                <span style={{fontFamily:"monospace",fontSize:10,fontWeight:600,padding:"1px 6px",borderRadius:4,background:`${c}12`,color:c}}>{t.agent}</span>
                <span style={{fontFamily:"monospace",fontSize:10,color:"#aaa"}}>turn {i+1}{t.phase?" · "+t.phase:""}</span>
                <button onClick={e=>{e.stopPropagation();setDrill(-1);}} style={S.drillClose}>close</button>
              </div>
              <div style={S.drillContent}>{t.content}</div>
              {hasAnn&&<div style={{marginTop:8,paddingTop:8,borderTop:"1px solid #eee"}}>{anns.map((ann,j)=><Badge key={j} code={ann.code} type={ann.type}/>)}</div>}
            </div>);}
            return parts;
          });})()}
        </>}
      </div>

      {/* Sidebar */}
      <div style={S.sidebar}>
        {((D.has_divergence&&D.beliefs)||(D.beliefs?.has_divergence))&&<div style={{marginBottom:18}}>
          <h3 style={S.sideHead}>Belief divergence</h3>
          {Object.entries(D.beliefs?.beliefs||D.beliefs).map(([a,b],idx)=>{
            if(typeof b!=="string") return null;
            const c=ac(a,agents);
            return <div key={a}>
              <div style={{padding:"8px 10px",borderRadius:6,marginBottom:4,border:`1px solid ${c}25`,background:`${c}08`}}>
                <div style={{fontFamily:"monospace",fontSize:9,textTransform:"uppercase",letterSpacing:.8,color:c,marginBottom:2}}>{a}</div>
                <div style={{fontSize:11,color:"#666",lineHeight:1.4}}>"{b}"</div>
              </div>
              {idx===0&&Object.keys(D.beliefs?.beliefs||D.beliefs).length>1&&<div style={{textAlign:"center",fontFamily:"monospace",fontSize:10,color:"#dc2626",padding:"2px 0"}}>⚡ beliefs diverge</div>}
            </div>;
          })}
        </div>}
        {Object.keys(D.failures).length>0&&<div style={{marginBottom:18}}>
          <h3 style={S.sideHead}>Detected failures</h3>
          {Object.entries(D.failures).map(([code,info])=>{
            const m=MAST[code]||{};
            const cnt=D.turns.filter(t=>(t.failures||[]).includes(code)||(t.annotations||[]).some(a=>a.code===code)).length;
            return <div key={code} style={S.failureRow}>
              <span style={S.failureCode}>{code}</span>
              <div><div style={{fontSize:11,color:"#333",fontWeight:500}}>{m.l||info.label}</div>
              <div style={{fontSize:9.5,color:"#999"}}>{m.c||info.category}{cnt?" · "+cnt+" turn(s)":" · trace-level"}</div></div>
            </div>;
          })}
        </div>}
        {(D.loops||[]).length>0&&<div style={{marginBottom:18}}>
          <h3 style={S.sideHead}>Loops</h3>
          {D.loops.map((l,i)=><div key={i} style={S.loopBox}>Turns {l.start+1}–{l.end+1}</div>)}
        </div>}
        <div style={{marginBottom:18}}>
          <h3 style={S.sideHead}>Metadata</h3>
          <div style={S.metaBlock}>
            <div><span style={{color:"#2563eb"}}>framework</span>: {D.meta.framework}</div>
            <div><span style={{color:"#2563eb"}}>benchmark</span>: {D.meta.benchmark}</div>
            <div><span style={{color:"#2563eb"}}>llm</span>: {D.meta.llm}</div>
            <div><span style={{color:"#2563eb"}}>turns</span>: {D.meta.total_turns}</div>
            <div><span style={{color:"#2563eb"}}>failures</span>: [{Object.keys(D.failures).map(c=>'"'+c+'"').join(", ")}]</div>
          </div>
        </div>
        {D.meta.note_text&&<div><h3 style={S.sideHead}>Expert note</h3><div style={S.noteBox}>{D.meta.note_text}</div></div>}
      </div>
    </div>
  </div>;
}

const S={
  app:{fontFamily:"'Segoe UI',system-ui,-apple-system,sans-serif",color:"#1a1a1a",maxWidth:1200,margin:"0 auto",padding:"0 12px",background:"#fff",minHeight:"100vh"},
  header:{display:"flex",alignItems:"baseline",gap:12,padding:"14px 0",borderBottom:"1px solid #e5e5e5",flexWrap:"wrap"},
  tag:{fontFamily:"monospace",fontSize:11,padding:"2px 8px",borderRadius:6,background:"#f3f3f3",color:"#666"},
  legend:{display:"flex",gap:10,marginLeft:"auto",alignItems:"center",flexWrap:"wrap"},
  legendItem:{display:"inline-flex",alignItems:"center",gap:3,fontSize:11,color:"#666"},
  dot:{width:7,height:7,borderRadius:"50%",display:"inline-block"},
  problem:{fontSize:12,color:"#888",margin:"6px 0 0",lineHeight:1.4},
  toolbar:{display:"flex",gap:8,alignItems:"center",padding:"8px 0",borderBottom:"1px solid #e5e5e5",flexWrap:"wrap"},
  viewBtn:{fontSize:11,padding:"4px 12px",border:"1px solid #ccc",background:"#fff",color:"#666",cursor:"pointer",fontFamily:"inherit"},
  viewBtnActive:{background:"#2563eb",color:"#fff",borderColor:"#2563eb"},
  traceBtn:{fontSize:11,padding:"4px 10px",border:"1px solid #ccc",borderRadius:5,background:"#fff",color:"#555",cursor:"pointer",fontFamily:"inherit"},
  uploadBtn:{fontSize:11,padding:"4px 12px",border:"1px solid #059669",borderRadius:5,background:"#f0fdf4",color:"#059669",cursor:"pointer",fontFamily:"monospace",fontWeight:500},
  mainGrid:{display:"grid",gridTemplateColumns:"1fr 250px",gap:0,marginTop:8},
  swimHeader:{display:"flex",paddingLeft:40,borderBottom:"1px solid #eee",marginBottom:4,position:"sticky",top:0,background:"#fff",zIndex:5},
  compactRow:{display:"flex",alignItems:"center",minHeight:28,cursor:"pointer",borderRadius:5,padding:"1px 0"},
  turnNum:{width:36,textAlign:"right",fontFamily:"monospace",fontSize:9.5,color:"#bbb",paddingRight:5,flexShrink:0},
  failDot:{width:6,height:6,borderRadius:"50%",background:"#dc2626",marginLeft:2,flexShrink:0},
  phaseDivider:{display:"flex",alignItems:"center",gap:8,padding:"7px 0 3px"},
  phaseLine:{flex:1,height:1,background:"#e5e5e5"},
  phaseLabel:{fontFamily:"monospace",fontSize:9,color:"#aaa",letterSpacing:1,textTransform:"uppercase",whiteSpace:"nowrap"},
  drillPanel:{margin:"4px 0 4px 40px",padding:14,background:"#fff",border:"1px solid #ddd",borderRadius:8},
  drillClose:{marginLeft:"auto",fontSize:10,padding:"2px 8px",border:"1px solid #ddd",borderRadius:4,background:"#fff",cursor:"pointer",fontFamily:"inherit",color:"#888"},
  drillContent:{fontSize:12.5,lineHeight:1.6,color:"#333",whiteSpace:"pre-wrap",maxHeight:300,overflowY:"auto",wordBreak:"break-word"},
  sidebar:{borderLeft:"1px solid #e5e5e5",paddingLeft:16,fontSize:12},
  sideHead:{fontSize:10,fontWeight:500,color:"#999",textTransform:"uppercase",letterSpacing:.8,marginBottom:8,fontFamily:"monospace"},
  failureRow:{display:"flex",gap:6,padding:"5px 0",borderBottom:"1px solid #f0f0f0",alignItems:"flex-start"},
  failureCode:{fontFamily:"monospace",fontSize:10,color:"#dc2626",background:"rgba(220,38,38,0.06)",border:"1px solid rgba(220,38,38,0.15)",padding:"0px 4px",borderRadius:3,whiteSpace:"nowrap"},
  loopBox:{fontFamily:"monospace",fontSize:10,color:"#666",padding:"4px 8px",borderRadius:4,background:"rgba(220,38,38,0.04)",border:"1px solid rgba(220,38,38,0.12)",marginBottom:3},
  metaBlock:{fontFamily:"monospace",fontSize:10.5,lineHeight:1.8,color:"#777",background:"#f8f8f6",borderRadius:6,padding:"8px 10px"},
  noteBox:{fontSize:11,color:"#777",lineHeight:1.45,fontStyle:"italic",background:"#f8f8f6",padding:8,borderRadius:6},
  badgeFail:{fontFamily:"monospace",fontSize:9,padding:"1px 5px",borderRadius:3,background:"rgba(220,38,38,0.08)",color:"#dc2626",border:"1px solid rgba(220,38,38,0.2)",marginRight:3,whiteSpace:"nowrap",display:"inline-block"},
  badgeDiverge:{fontFamily:"monospace",fontSize:9,padding:"1px 5px",borderRadius:3,background:"rgba(217,119,6,0.08)",color:"#d97706",border:"1px solid rgba(217,119,6,0.2)",marginRight:3,whiteSpace:"nowrap",display:"inline-block"},
  empty:{padding:"80px 20px",textAlign:"center",color:"#999",fontFamily:"system-ui,sans-serif"},
};
