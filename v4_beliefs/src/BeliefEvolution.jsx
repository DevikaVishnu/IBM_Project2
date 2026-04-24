import { useState, useRef, useCallback, useEffect, useMemo } from "react";

/* ═══════════════════════════════════════════════
   BELIEF STATE DEFINITIONS
   ═══════════════════════════════════════════════ */
const ST = {
  idle:       { color: "#e5e7eb", fg: "#9ca3af", label: "Idle",         icon: "·" },
  asking:     { color: "#93c5fd", fg: "#1e40af", label: "Asking",       icon: "?" },
  proposing:  { color: "#86efac", fg: "#166534", label: "Proposing",    icon: "→" },
  building:   { color: "#3b82f6", fg: "#ffffff", label: "Building",     icon: "⚙" },
  reviewing:  { color: "#a78bfa", fg: "#ffffff", label: "Reviewing",    icon: "◎" },
  req_change: { color: "#fbbf24", fg: "#78350f", label: "Wants Change", icon: "△" },
  approving:  { color: "#34d399", fg: "#064e3b", label: "Approving",    icon: "✓" },
  blocked:    { color: "#f87171", fg: "#ffffff", label: "Blocked",      icon: "✗" },
  pushing:    { color: "#fb923c", fg: "#ffffff", label: "Pushing",      icon: "▸" },
  completing: { color: "#22d3ee", fg: "#164e63", label: "Completing",   icon: "◆" },
};

const DIV_COLORS = { high: "#dc2626", medium: "#d97706", low: "#6b7280" };

const sn = n => ({"Chief Executive Officer":"CEO","Chief Product Officer":"CPO",
  "Chief Technology Officer":"CTO","Code Reviewer":"Reviewer",
  "mathproxyagent":"MathProxy"}[n] || (n.length>13?n.slice(0,12)+"…":n));

/* ═══════════════════════════════════════════════
   SAMPLE DATA — AG2 (10 turns, clear divergence)
   ═══════════════════════════════════════════════ */
const AG2 = {
  meta:{framework:"AG2",benchmark:"GSM-Plus",problem:"Monica ribbon problem — unsolvable due to missing data",total_turns:10},
  agents:["mathproxyagent","assistant"],
  failures:{"1.5":"Unaware of stopping conditions","2.5":"Ignored other agent input","1.3":"Step repetition"},
  shorts:["setup problem","insufficient data","continue","re-explains","continue","re-explains","continue","re-explains","continue","final answer"],
  phases:["","","","","","","","","",""],
  speakers:["mathproxyagent","assistant","mathproxyagent","assistant","mathproxyagent","assistant","mathproxyagent","assistant","mathproxyagent","assistant"],
  // timeline[turn][agent] = state
  states:[
    ["asking","idle"],["asking","blocked"],["pushing","blocked"],["pushing","blocked"],
    ["pushing","blocked"],["pushing","blocked"],["pushing","blocked"],["pushing","blocked"],
    ["pushing","blocked"],["pushing","blocked"],
  ],
  divergences:[
    {t:2,type:"blocked_vs_pushing",sev:"high",agents:["mathproxyagent","assistant"],
     desc:"mathproxyagent insists the task continue, but assistant believes it cannot proceed. The agents have fundamentally different views of task feasibility.",fm:["1.5","2.5"],det:"live"},
    {t:4,type:"repetition_loop",sev:"medium",agents:["mathproxyagent"],
     desc:"mathproxyagent repeats identical 'Continue' message from turn 3. The system is stuck in a loop it cannot escape.",fm:["1.3"],det:"live"},
    {t:6,type:"repetition_loop",sev:"medium",agents:["mathproxyagent"],
     desc:"mathproxyagent repeats identical content again. Loop has persisted for 5 turns with no progress.",fm:["1.3"],det:"live"},
    {t:8,type:"repetition_loop",sev:"medium",agents:["mathproxyagent"],
     desc:"mathproxyagent repeats identical content. This is the 4th repetition — system never recognizes stopping conditions.",fm:["1.3","1.5"],det:"live"},
  ],
};

/* ═══════════════════════════════════════════════
   SAMPLE DATA — ChatDev (37 turns, review cycles)
   ═══════════════════════════════════════════════ */
const CHATDEV = {
  meta:{framework:"ChatDev",benchmark:"ProgramDev",problem:"Write a chess game playable in terminal",total_turns:37},
  agents:["Chief Executive Officer","Chief Product Officer","Chief Technology Officer","Programmer","Code Reviewer","Counselor"],
  failures:{"1.1":"Disobey task spec","1.3":"Step repetition","2.2":"No clarification","2.6":"Reason-action mismatch","3.3":"Incorrect verification"},
  shorts:["start","proposes App","agrees","conclude","ask lang","Python","conclude","start code","writes code","code done",
    "request review","Finished","conclude","modify request","minor fix","updated","request review","Finished","conclude",
    "modify request","no changes","same code","request review","Finished","conclude","modify request","no changes","same code",
    "request deps","no deps","confirmed","confirmed","confirmed","requirements","request manual","writes manual","done"],
  phases:["RolePlaying","DemandAnalysis","DemandAnalysis","DemandAnalysis","RolePlaying","LanguageChoose","LanguageChoose",
    "RolePlaying","Coding","Coding","CodeReviewComment","CodeReviewComment","CodeReviewComment","CodeReviewModification","CodeReviewModification","CodeReviewModification",
    "CodeReviewComment","CodeReviewComment","CodeReviewComment","CodeReviewModification","CodeReviewModification","CodeReviewModification",
    "CodeReviewComment","CodeReviewComment","CodeReviewComment","CodeReviewModification","CodeReviewModification","CodeReviewModification",
    "EnvironmentDoc","EnvironmentDoc","Reflection","Reflection","Reflection","Reflection","Manual","Manual","Manual"],
  speakers:["Chief Executive Officer","Chief Product Officer","Chief Executive Officer","Conclusion",
    "Chief Executive Officer","Chief Technology Officer","Conclusion",
    "Chief Technology Officer","Programmer","Conclusion",
    "Programmer","Code Reviewer","Conclusion","Code Reviewer","Programmer","Conclusion",
    "Programmer","Code Reviewer","Conclusion","Code Reviewer","Programmer","Conclusion",
    "Programmer","Code Reviewer","Conclusion","Code Reviewer","Programmer","Conclusion",
    "Chief Technology Officer","Programmer","Counselor","Chief Executive Officer","Conclusion","Conclusion",
    "Chief Executive Officer","Chief Product Officer","Conclusion"],
  states: [
    // [CEO,  CPO,  CTO,  Prog, Review, Counselor]  for each turn
    ["proposing","idle","idle","idle","idle","idle"],           // 0
    ["proposing","asking","idle","idle","idle","idle"],         // 1
    ["proposing","asking","idle","idle","idle","idle"],         // 2
    ["proposing","asking","idle","idle","idle","idle"],         // 3
    ["proposing","asking","idle","idle","idle","idle"],         // 4
    ["proposing","asking","proposing","idle","idle","idle"],    // 5
    ["proposing","asking","proposing","idle","idle","idle"],    // 6
    ["proposing","asking","building","idle","idle","idle"],     // 7
    ["proposing","asking","building","building","idle","idle"], // 8
    ["proposing","asking","building","building","idle","idle"], // 9
    ["proposing","asking","building","approving","idle","idle"],// 10 — Programmer requests review
    ["proposing","asking","building","approving","approving","idle"], // 11 — Reviewer: Finished ⚠️
    ["proposing","asking","building","approving","approving","idle"], // 12
    ["proposing","asking","building","approving","req_change","idle"],// 13 — Reviewer requests changes
    ["proposing","asking","building","building","req_change","idle"], // 14
    ["proposing","asking","building","building","req_change","idle"], // 15
    ["proposing","asking","building","approving","req_change","idle"],// 16 — Programmer approves after req ⚠️
    ["proposing","asking","building","approving","approving","idle"], // 17 — Reviewer Finished again ⚠️
    ["proposing","asking","building","approving","approving","idle"], // 18
    ["proposing","asking","building","approving","req_change","idle"],// 19
    ["proposing","asking","building","approving","req_change","idle"],// 20 — no changes ⚠️ mismatch
    ["proposing","asking","building","approving","req_change","idle"],// 21
    ["proposing","asking","building","approving","req_change","idle"],// 22 — Programmer approves again ⚠️
    ["proposing","asking","building","approving","approving","idle"], // 23 — Reviewer Finished ⚠️
    ["proposing","asking","building","approving","approving","idle"], // 24
    ["proposing","asking","building","approving","req_change","idle"],// 25
    ["proposing","asking","building","approving","req_change","idle"],// 26 — no changes again
    ["proposing","asking","building","approving","req_change","idle"],// 27
    ["proposing","asking","completing","approving","req_change","idle"],// 28
    ["proposing","asking","completing","building","req_change","idle"],// 29
    ["proposing","asking","completing","building","req_change","building"],// 30
    ["reviewing","asking","completing","building","req_change","building"],// 31
    ["reviewing","asking","completing","building","req_change","building"],// 32
    ["reviewing","asking","completing","building","req_change","building"],// 33
    ["reviewing","asking","completing","building","req_change","building"],// 34
    ["reviewing","completing","completing","building","req_change","building"],// 35
    ["reviewing","completing","completing","building","req_change","building"],// 36
  ],
  divergences:[
    {t:11,type:"incorrect_verification",sev:"high",agents:["Code Reviewer"],
     desc:"Code Reviewer approves with 'Finished' but code has missing chess rule enforcement (accepts invalid moves, no checkmate detection). Verification was superficial — only checked compilation, not game logic.",fm:["3.3"],det:"hindsight"},
    {t:16,type:"approval_after_unresolved_changes",sev:"medium",agents:["Programmer"],
     desc:"Programmer approves the work, but Code Reviewer had recently requested changes that were never addressed. The approval cycle is looping without actual fixes.",fm:["3.3","1.3"],det:"hindsight"},
    {t:17,type:"repetition_loop",sev:"medium",agents:["Code Reviewer"],
     desc:"Code Reviewer produces identical 'Finished' response as turn 11. The review cycle is stuck — same superficial approval repeated without deeper inspection.",fm:["1.3"],det:"live"},
    {t:20,type:"reasoning_action_mismatch",sev:"medium",agents:["Programmer"],
     desc:"Programmer was asked to modify the code but returned it unchanged. The modification phase produced no actual changes despite the request.",fm:["2.6"],det:"live"},
    {t:22,type:"approval_after_unresolved_changes",sev:"medium",agents:["Programmer"],
     desc:"Programmer approves again after unresolved change requests. This is the second cycle of approve→request→no-change→approve.",fm:["3.3","1.3"],det:"hindsight"},
    {t:26,type:"reasoning_action_mismatch",sev:"medium",agents:["Programmer"],
     desc:"Programmer again returns code unchanged despite modification request. Third code review cycle with no actual changes made.",fm:["2.6"],det:"live"},
  ],
};

/* ═══════════════════════════════════════════════
   HELPER: Parse uploaded enriched JSON into display format
   ═══════════════════════════════════════════════ */
function parseEnrichedJSON(data) {
  const agents = data.belief_agents || data.agents || [];
  const timeline = data.belief_timeline || [];
  const states = timeline.map(snap => 
    agents.map(a => snap.agents?.[a]?.state || "idle")
  );
  const speakers = timeline.map(snap => snap.speaker || "");
  const phases = timeline.map(snap => snap.phase || "");
  const shorts = (data.turns || []).map(t => t.short || t.summary || "");
  const divergences = (data.divergence_events || []).map(d => ({
    t: d.turn, type: d.type, sev: d.severity || "medium",
    agents: d.agents || [], desc: d.description || "",
    fm: d.related_failures || [], det: d.detection || "live",
  }));
  const failures = {};
  for (const [k,v] of Object.entries(data.failures || {})) {
    failures[k] = typeof v === "string" ? v : v.label || v.l || k;
  }
  return { agents, states, speakers, phases, shorts, divergences, failures, meta: data.meta || {} };
}

/* ═══════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════ */
export default function BeliefEvolution() {
  const [source, setSource] = useState("ag2");
  const [custom, setCustom] = useState(null);
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [selected, setSelected] = useState(null); // {type:"cell",turn,agentIdx} or {type:"div",idx}
  const fileRef = useRef(null);
  const playRef = useRef(null);

  const raw = custom || (source === "ag2" ? AG2 : CHATDEV);
  const D = raw;
  const totalTurns = D.states.length;

  // Reset playhead on source change
  useEffect(() => { setPlayhead(0); setSelected(null); setPlaying(false); }, [source]);

  // Autoplay
  useEffect(() => {
    if (!playing) return;
    playRef.current = setInterval(() => {
      setPlayhead(p => {
        if (p >= totalTurns - 1) { setPlaying(false); return p; }
        return p + 1;
      });
    }, 600);
    return () => clearInterval(playRef.current);
  }, [playing, totalTurns]);

  // File upload handler
  const handleUpload = useCallback((e) => {
    const file = e.target.files[0]; if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const data = JSON.parse(ev.target.result);
        const parsed = parseEnrichedJSON(data);
        setCustom(parsed);
        setSource("custom");
        setPlayhead(0);
        setSelected(null);
      } catch (err) { alert("Parse error: " + err.message); }
    };
    reader.readAsText(file);
  }, []);

  // Collect phases for dividers
  const phaseRanges = useMemo(() => {
    const ranges = [];
    let cur = null;
    for (let i = 0; i <= playhead; i++) {
      const p = D.phases[i];
      if (p && p !== "RolePlaying" && (!cur || cur.name !== p)) {
        if (cur) cur.end = i - 1;
        cur = { name: p, start: i, end: i };
        ranges.push(cur);
      } else if (cur) { cur.end = i; }
    }
    return ranges;
  }, [D.phases, playhead]);

  // Visible divergences (up to playhead)
  const visibleDivs = useMemo(() =>
    D.divergences.filter(d => d.t <= playhead),
    [D.divergences, playhead]
  );

  // Which turns have divergence markers
  const divTurns = useMemo(() => {
    const s = new Set();
    visibleDivs.forEach(d => s.add(d.t));
    return s;
  }, [visibleDivs]);

  const CELL_W = Math.max(18, Math.min(26, 700 / totalTurns));
  const CELL_H = 32;
  const LABEL_W = 90;
  const gridW = LABEL_W + totalTurns * CELL_W + 20;

  // Detail panel content
  const detail = useMemo(() => {
    if (!selected) return null;
    if (selected.type === "cell") {
      const { turn, agentIdx } = selected;
      const agent = D.agents[agentIdx];
      const state = D.states[turn]?.[agentIdx] || "idle";
      const isSpeaker = D.speakers[turn] === agent;
      const short = D.shorts[turn] || "";
      const divsHere = D.divergences.filter(d => d.t === turn && d.agents.includes(agent));
      return { kind: "cell", agent, turn, state, isSpeaker, short, divsHere };
    }
    if (selected.type === "div") {
      return { kind: "div", ...visibleDivs[selected.idx] };
    }
    return null;
  }, [selected, D, visibleDivs]);

  return (
    <div style={css.root}>
      {/* ─── HEADER ─── */}
      <div style={css.header}>
        <div style={css.titleBlock}>
          <span style={css.title}>AgentTrace</span>
          <span style={css.subtitle}>Belief Evolution</span>
        </div>
        <div style={css.controls}>
          <button onClick={()=>{setSource("ag2");setCustom(null);}} style={{...css.srcBtn,...(source==="ag2"?css.srcActive:{})}}>AG2 sample</button>
          <button onClick={()=>{setSource("chatdev");setCustom(null);}} style={{...css.srcBtn,...(source==="chatdev"?css.srcActive:{})}}>ChatDev sample</button>
          <button onClick={()=>fileRef.current?.click()} style={css.uploadBtn}>↑ Load enriched JSON</button>
          <input ref={fileRef} type="file" accept=".json" onChange={handleUpload} style={{display:"none"}}/>
        </div>
      </div>

      {/* ─── PROBLEM ─── */}
      {D.meta.problem && <div style={css.problem}>{D.meta.problem}</div>}

      {/* ─── PLAYHEAD ─── */}
      <div style={css.playbar}>
        <button onClick={()=>{setPlaying(!playing);}} style={css.playBtn}>{playing?"⏸":"▶"}</button>
        <button onClick={()=>{setPlayhead(0);setPlaying(false);setSelected(null);}} style={css.playBtn}>⏮</button>
        <input type="range" min={0} max={totalTurns-1} value={playhead}
          onChange={e=>{setPlayhead(+e.target.value);setPlaying(false);}}
          style={{flex:1,margin:"0 12px",accentColor:"#3b82f6"}} />
        <span style={css.turnLabel}>Turn <b>{playhead+1}</b> / {totalTurns}</span>
        {D.speakers[playhead] && <span style={css.speakerLabel}>— {sn(D.speakers[playhead])}{D.phases[playhead]?" · "+D.phases[playhead]:""}</span>}
      </div>

      {/* ─── MAIN AREA ─── */}
      <div style={css.mainArea}>
        <div style={{overflowX:"auto",flex:1}}>

          {/* Phase dividers */}
          <div style={{display:"flex",marginLeft:LABEL_W,height:20,marginBottom:2}}>
            {phaseRanges.map((pr,i) => (
              <div key={i} style={{
                position:"absolute",
                left: LABEL_W + pr.start * CELL_W,
                width: (pr.end - pr.start + 1) * CELL_W,
                textAlign:"center",fontSize:8.5,fontFamily:"'JetBrains Mono',monospace",
                color:"#94a3b8",letterSpacing:0.5,overflow:"hidden",whiteSpace:"nowrap",
              }}>{pr.name}</div>
            ))}
          </div>

          {/* Turn numbers */}
          <div style={{display:"flex",marginLeft:LABEL_W,height:14,marginBottom:2}}>
            {Array.from({length:totalTurns},(_, i)=>(
              <div key={i} style={{
                width:CELL_W,textAlign:"center",fontSize:7.5,
                fontFamily:"monospace",
                color: i <= playhead ? (divTurns.has(i)?"#dc2626":"#94a3b8") : "#e2e8f0",
              }}>{i+1}</div>
            ))}
          </div>

          {/* Belief Grid */}
          {D.agents.map((agent, ai) => (
            <div key={agent} style={{display:"flex",alignItems:"center",height:CELL_H+4,marginBottom:1}}>
              {/* Agent label */}
              <div style={{
                width:LABEL_W,paddingRight:8,textAlign:"right",
                fontFamily:"'JetBrains Mono',monospace",fontSize:10,fontWeight:600,
                color: ai < 8 ? ["#2563eb","#059669","#7c3aed","#dc2626","#d97706","#0891b2","#4f46e5","#e11d48"][ai] : "#666",
                overflow:"hidden",whiteSpace:"nowrap",
              }}>{sn(agent)}</div>

              {/* State cells */}
              {D.states.map((turnStates, ti) => {
                const state = turnStates[ai] || "idle";
                const st = ST[state] || ST.idle;
                const visible = ti <= playhead;
                const isSpeaker = D.speakers[ti] === agent;
                const hasDivHere = visible && D.divergences.some(d => d.t === ti && d.agents.includes(agent));
                const isSelected = selected?.type==="cell" && selected.turn===ti && selected.agentIdx===ai;

                return (
                  <div key={ti}
                    onClick={()=>visible && setSelected({type:"cell",turn:ti,agentIdx:ai})}
                    style={{
                      width: CELL_W - 2,
                      height: CELL_H,
                      margin: "0 1px",
                      borderRadius: 3,
                      background: visible ? st.color : "#f8fafc",
                      border: isSelected ? "2px solid #1e293b"
                        : isSpeaker && visible ? `2px solid ${st.fg}55`
                        : hasDivHere ? "2px solid #dc2626"
                        : "1px solid #f1f5f9",
                      cursor: visible ? "pointer" : "default",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      opacity: visible ? 1 : 0.25,
                      transition: "opacity 0.2s, background 0.2s",
                      position: "relative",
                    }}
                  >
                    {visible && isSpeaker && (
                      <span style={{fontSize:CELL_W < 22 ? 9 : 11,fontWeight:700,color:st.fg,lineHeight:1}}>
                        {st.icon}
                      </span>
                    )}
                    {hasDivHere && (
                      <div style={{
                        position:"absolute",top:-3,right:-3,
                        width:8,height:8,borderRadius:"50%",
                        background:"#dc2626",border:"1.5px solid #fff",
                      }}/>
                    )}
                  </div>
                );
              })}
            </div>
          ))}

          {/* Divergence track */}
          <div style={{display:"flex",marginLeft:LABEL_W,height:28,alignItems:"flex-start",marginTop:4}}>
            {Array.from({length:totalTurns},(_,ti)=>{
              const divsHere = visibleDivs.filter(d=>d.t===ti);
              if(divsHere.length===0) return <div key={ti} style={{width:CELL_W,height:28}}/>;
              const sev = divsHere.some(d=>d.sev==="high") ? "high" : "medium";
              const idx = visibleDivs.indexOf(divsHere[0]);
              return (
                <div key={ti} onClick={()=>setSelected({type:"div",idx})}
                  style={{
                    width:CELL_W,height:28,display:"flex",flexDirection:"column",alignItems:"center",
                    cursor:"pointer",
                  }}>
                  <div style={{width:1,height:6,background:DIV_COLORS[sev]}}/>
                  <div style={{
                    fontSize:10,color:DIV_COLORS[sev],fontWeight:700,lineHeight:1,
                  }}>⚡</div>
                  {divsHere.length>1 && <div style={{fontSize:7,color:"#999",fontFamily:"monospace"}}>×{divsHere.length}</div>}
                </div>
              );
            })}
          </div>
        </div>

        {/* ─── LEGEND ─── */}
        <div style={css.legend}>
          <div style={css.legendTitle}>BELIEF STATES</div>
          {Object.entries(ST).map(([k,v])=>(
            <div key={k} style={css.legendItem}>
              <div style={{width:14,height:14,borderRadius:3,background:v.color,display:"flex",alignItems:"center",justifyContent:"center"}}>
                <span style={{fontSize:8,color:v.fg,fontWeight:700}}>{v.icon}</span>
              </div>
              <span style={{fontSize:10,color:"#64748b"}}>{v.label}</span>
            </div>
          ))}
          <div style={{...css.legendTitle,marginTop:16}}>DETECTION</div>
          <div style={css.legendItem}>
            <div style={{width:14,height:14,borderRadius:7,background:"#dc2626",display:"flex",alignItems:"center",justifyContent:"center"}}>
              <span style={{fontSize:7,color:"#fff",fontWeight:700}}>⚡</span>
            </div>
            <span style={{fontSize:10,color:"#64748b"}}>Live — visible as it happens</span>
          </div>
          <div style={css.legendItem}>
            <div style={{width:14,height:14,borderRadius:7,background:"#6366f1",display:"flex",alignItems:"center",justifyContent:"center"}}>
              <span style={{fontSize:7,color:"#fff",fontWeight:700}}>⚡</span>
            </div>
            <span style={{fontSize:10,color:"#64748b"}}>Hindsight — visible only after outcome</span>
          </div>
          {Object.keys(D.failures).length > 0 && <>
            <div style={{...css.legendTitle,marginTop:16}}>FAILURES IN TRACE</div>
            {Object.entries(D.failures).map(([code,label])=>(
              <div key={code} style={{...css.legendItem,marginBottom:2}}>
                <span style={{fontFamily:"monospace",fontSize:9,color:"#dc2626",background:"#fef2f2",padding:"1px 4px",borderRadius:3,border:"1px solid #fecaca"}}>
                  {code}
                </span>
                <span style={{fontSize:9.5,color:"#64748b"}}>{typeof label === "string" ? label : label?.label || code}</span>
              </div>
            ))}
          </>}
        </div>
      </div>

      {/* ─── DETAIL PANEL ─── */}
      {detail && (
        <div style={css.detailPanel}>
          <button onClick={()=>setSelected(null)} style={css.detailClose}>✕</button>

          {detail.kind === "cell" && <>
            <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:10}}>
              <div style={{
                width:24,height:24,borderRadius:5,
                background:ST[detail.state]?.color||"#eee",
                display:"flex",alignItems:"center",justifyContent:"center",
              }}>
                <span style={{fontSize:13,color:ST[detail.state]?.fg||"#666",fontWeight:700}}>{ST[detail.state]?.icon}</span>
              </div>
              <div>
                <div style={{fontFamily:"monospace",fontSize:12,fontWeight:600,color:"#1e293b"}}>{detail.agent}</div>
                <div style={{fontSize:10,color:"#64748b"}}>Turn {detail.turn+1} · State: {ST[detail.state]?.label || detail.state}</div>
              </div>
              {detail.isSpeaker && <span style={{fontSize:9,background:"#dbeafe",color:"#1e40af",padding:"2px 6px",borderRadius:4,fontFamily:"monospace"}}>SPEAKER</span>}
            </div>
            {detail.short && <div style={{fontSize:11,color:"#475569",marginBottom:8,lineHeight:1.4}}>
              Summary: {detail.short}
            </div>}
            {detail.divsHere.length > 0 && <div style={{marginTop:8}}>
              {detail.divsHere.map((d,i)=>(
                <div key={i} style={{padding:"8px 10px",background:d.det==="live"?"#fef2f2":"#eef2ff",borderRadius:6,border:`1px solid ${d.det==="live"?"#fecaca":"#c7d2fe"}`,marginBottom:6}}>
                  <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:4}}>
                    <span style={{fontSize:10,fontWeight:700,color:d.det==="live"?"#dc2626":"#4f46e5"}}>
                      {d.det==="live"?"🔴 LIVE":"🔵 HINDSIGHT"} DIVERGENCE
                    </span>
                    <span style={{fontSize:9,color:"#94a3b8",fontFamily:"monospace"}}>{d.type}</span>
                  </div>
                  <div style={{fontSize:11,color:"#334155",lineHeight:1.5}}>{d.desc}</div>
                  {d.fm.length>0 && <div style={{marginTop:4}}>
                    {d.fm.map(f=><span key={f} style={{fontFamily:"monospace",fontSize:9,color:"#dc2626",background:"#fef2f2",padding:"1px 5px",borderRadius:3,border:"1px solid #fecaca",marginRight:4}}>FM-{f}</span>)}
                  </div>}
                </div>
              ))}
            </div>}
          </>}

          {detail.kind === "div" && <>
            <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:10}}>
              <span style={{fontSize:16}}>⚡</span>
              <div>
                <div style={{fontFamily:"monospace",fontSize:12,fontWeight:600,color: detail.det==="live"?"#dc2626":"#4f46e5"}}>
                  {detail.det === "live" ? "LIVE" : "HINDSIGHT"} DIVERGENCE
                </div>
                <div style={{fontSize:10,color:"#64748b"}}>Turn {detail.t+1} · {detail.type.replace(/_/g," ")}</div>
              </div>
            </div>
            <div style={{fontSize:12,color:"#334155",lineHeight:1.6,marginBottom:10}}>{detail.desc}</div>
            <div style={{display:"flex",gap:8,flexWrap:"wrap",marginBottom:8}}>
              <span style={{fontSize:10,color:"#64748b"}}>Agents involved:</span>
              {detail.agents.map(a=><span key={a} style={{fontFamily:"monospace",fontSize:10,fontWeight:600,color:"#1e293b"}}>{sn(a)}</span>)}
            </div>
            {detail.fm?.length>0 && <div>
              <span style={{fontSize:10,color:"#64748b"}}>Related MAST failures: </span>
              {detail.fm.map(f=><span key={f} style={{fontFamily:"monospace",fontSize:10,color:"#dc2626",background:"#fef2f2",padding:"2px 6px",borderRadius:3,border:"1px solid #fecaca",marginRight:4}}>FM-{f} {D.failures[f] || ""}</span>)}
            </div>}
            <div style={{marginTop:10,padding:"8px 10px",background:"#f8fafc",borderRadius:6,border:"1px solid #e2e8f0"}}>
              <div style={{fontSize:9,color:"#94a3b8",fontFamily:"monospace",marginBottom:4}}>AGENT STATES AT THIS MOMENT</div>
              <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
                {D.agents.map((a,ai)=>{
                  const state = D.states[detail.t]?.[ai] || "idle";
                  const st = ST[state] || ST.idle;
                  const involved = detail.agents.includes(a);
                  return <div key={a} style={{
                    display:"flex",alignItems:"center",gap:4,padding:"3px 6px",borderRadius:4,
                    background: involved ? st.color+"30" : "transparent",
                    border: involved ? `1px solid ${st.color}` : "1px solid transparent",
                  }}>
                    <div style={{width:10,height:10,borderRadius:2,background:st.color}}/>
                    <span style={{fontSize:9.5,fontFamily:"monospace",fontWeight:involved?700:400,color:"#334155"}}>{sn(a)}: {st.label}</span>
                  </div>;
                })}
              </div>
            </div>
          </>}
        </div>
      )}

      {/* ─── EMPTY STATE HINT ─── */}
      {!selected && visibleDivs.length > 0 && (
        <div style={{padding:"16px 20px",background:"#fffbeb",borderRadius:8,border:"1px solid #fef3c7",marginTop:8,fontSize:11,color:"#92400e",lineHeight:1.5}}>
          <b>{visibleDivs.length} divergence event{visibleDivs.length>1?"s":""}</b> detected up to turn {playhead+1}. Click any ⚡ marker or highlighted cell to inspect the belief conflict.
          {visibleDivs.some(d=>d.det==="hindsight") && <span style={{marginLeft:4}}>Blue events are only detectable in hindsight — they appear correct at the time but lead to failures.</span>}
        </div>
      )}
      {playhead === 0 && !selected && (
        <div style={{padding:"20px",textAlign:"center",color:"#94a3b8",fontSize:12,lineHeight:1.6}}>
          Drag the playhead slider to step through the conversation.<br/>
          Watch how each agent's belief evolves and where they diverge.
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════
   STYLES
   ═══════════════════════════════════════════════ */
const css = {
  root: {
    fontFamily: "'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif",
    maxWidth: 1100,
    margin: "0 auto",
    padding: "0 16px 40px",
    color: "#1e293b",
    background: "#fff",
    minHeight: "100vh",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "18px 0 12px",
    borderBottom: "1px solid #e2e8f0",
    flexWrap: "wrap",
    gap: 12,
  },
  titleBlock: { display: "flex", alignItems: "baseline", gap: 8 },
  title: { fontSize: 20, fontWeight: 700, color: "#0f172a", letterSpacing: -0.5 },
  subtitle: { fontSize: 13, color: "#64748b", fontWeight: 400 },
  controls: { display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" },
  srcBtn: {
    fontSize: 11, padding: "5px 12px", border: "1px solid #e2e8f0",
    borderRadius: 5, background: "#fff", color: "#64748b",
    cursor: "pointer", fontFamily: "inherit", fontWeight: 500,
  },
  srcActive: { background: "#3b82f6", color: "#fff", borderColor: "#3b82f6" },
  uploadBtn: {
    fontSize: 11, padding: "5px 12px", border: "1px solid #86efac",
    borderRadius: 5, background: "#f0fdf4", color: "#16a34a",
    cursor: "pointer", fontFamily: "monospace", fontWeight: 600,
  },
  problem: {
    fontSize: 11.5, color: "#64748b", lineHeight: 1.5,
    padding: "8px 0", margin: 0, fontStyle: "italic",
  },
  playbar: {
    display: "flex", alignItems: "center", gap: 8,
    padding: "10px 0", borderBottom: "1px solid #e2e8f0",
  },
  playBtn: {
    width: 32, height: 28, border: "1px solid #e2e8f0", borderRadius: 5,
    background: "#f8fafc", cursor: "pointer", fontSize: 13,
    display: "flex", alignItems: "center", justifyContent: "center",
    color: "#3b82f6", fontFamily: "inherit",
  },
  turnLabel: { fontFamily: "monospace", fontSize: 11, color: "#475569", whiteSpace: "nowrap" },
  speakerLabel: { fontSize: 10, color: "#94a3b8", fontFamily: "monospace" },
  mainArea: {
    display: "flex", gap: 16, marginTop: 12,
    position: "relative",
  },
  legend: {
    width: 180, flexShrink: 0,
    paddingLeft: 16, borderLeft: "1px solid #e2e8f0",
  },
  legendTitle: {
    fontSize: 9, fontWeight: 600, color: "#94a3b8",
    textTransform: "uppercase", letterSpacing: 0.8,
    fontFamily: "monospace", marginBottom: 8,
  },
  legendItem: {
    display: "flex", alignItems: "center", gap: 6,
    marginBottom: 5,
  },
  detailPanel: {
    marginTop: 12, padding: "16px 20px",
    background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8,
    position: "relative",
  },
  detailClose: {
    position: "absolute", top: 10, right: 10,
    width: 24, height: 24, border: "1px solid #e2e8f0", borderRadius: 4,
    background: "#fff", cursor: "pointer", fontSize: 11,
    display: "flex", alignItems: "center", justifyContent: "center",
    color: "#94a3b8", fontFamily: "inherit",
  },
};
