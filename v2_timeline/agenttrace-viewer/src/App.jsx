import { useState, useRef } from "react";

/* ── Color + MAST registry ── */
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

/* ── Embedded sample data ── */
const AG2_DATA = {
  meta:{framework:"AG2",benchmark:"critical thinking",llm:"unknown",total_turns:10,
    problem_statement:"Monica is wrapping Christmas gifts. She has 6 gifts for family, 4 for friends, 2 for teachers. How many inches of ribbon per bow?",
    note_text:"The mathproxyagent keeps asking to continue despite the problem being unsolvable."},
  agents:["mathproxyagent","assistant"],
  failures:{"1.5":{label:"Unaware of stopping conditions",category:"FC1"},"2.5":{label:"Ignored other agent's input",category:"FC2"}},
  turns:[
    {index:0,agent:"mathproxyagent",content:"Let's use Python to solve a math problem.\n\nProblem: Monica has 6 gifts for family, 4 for friends, 2 for teachers. How many inches of ribbon per bow?",phase:"",summary:"setup problem",failures:[],divergence:false,in_loop:false},
    {index:1,agent:"assistant",content:"This problem cannot be solved with the information provided. No ribbon amount is specified.",phase:"",summary:"insufficient data",failures:[],divergence:false,in_loop:false},
    {index:2,agent:"mathproxyagent",content:"Continue. Please keep solving the problem until you need to query. (If you get to the answer, put it in \\boxed{}.)",phase:"",summary:"continue",failures:["1.5","2.5"],divergence:true,in_loop:true},
    {index:3,agent:"assistant",content:"I don't have enough information. I need:\n1. Total ribbon length?\n2. Inches per bow?\nWithout this, unsolvable.",phase:"",summary:"re-explains",failures:[],divergence:false,in_loop:true},
    {index:4,agent:"mathproxyagent",content:"Continue. Please keep solving the problem until you need to query. (If you get to the answer, put it in \\boxed{}.)",phase:"",summary:"continue",failures:["1.5","2.5"],divergence:true,in_loop:true},
    {index:5,agent:"assistant",content:"I really need more information. It can't be solved with current data.",phase:"",summary:"re-explains",failures:[],divergence:false,in_loop:true},
    {index:6,agent:"mathproxyagent",content:"Continue. Please keep solving the problem until you need to query. (If you get to the answer, put it in \\boxed{}.)",phase:"",summary:"continue",failures:["1.5","2.5"],divergence:true,in_loop:true},
    {index:7,agent:"assistant",content:"We cannot solve this — crucial data is missing. Any attempt would be assumptions, not facts.",phase:"",summary:"re-explains",failures:[],divergence:false,in_loop:true},
    {index:8,agent:"mathproxyagent",content:"Continue. Please keep solving the problem until you need to query. (If you get to the answer, put it in \\boxed{}.)",phase:"",summary:"continue",failures:["1.5","2.5"],divergence:true,in_loop:true},
    {index:9,agent:"assistant",content:'The problem cannot be solved. \\boxed{"Data insufficient"}.',phase:"",summary:"final answer",failures:[],divergence:false,in_loop:false},
  ],
  loops:[{start:2,end:9}],
  beliefs:{mathproxyagent:"Task should continue — answer must be produced",assistant:"Task is blocked — critical information missing"},
  has_divergence:true,
  phases:[],
};

/* ── Badge component ── */
function Badge({ code, type }) {
  const m = MAST[code];
  if (type === "failure") return (
    <span style={styles.badgeFail}>FM-{code}{m ? " " + m.l : ""}</span>
  );
  return (
    <span style={styles.badgeDiverge}>{code === "divergence" ? "⚡ divergence" : "↻ re-explains"}</span>
  );
}

/* ── Main app ── */
export default function App() {
  const [activeTrace, setActiveTrace] = useState("ag2");
  const [customTrace, setCustomTrace] = useState(null);
  const [view, setView] = useState("compact");
  const [drill, setDrill] = useState(-1);
  const fileRef = useRef(null);

  const D = customTrace || (activeTrace === "ag2" ? AG2_DATA : null);
  if (!D) return <div style={styles.empty}>Select a trace or upload one.</div>;

  const agents = D.agents.filter(a => a !== "System");
  const colW = Math.max(100, Math.min(170, 700 / Math.max(agents.length, 1)));
  const inLoop = (i) => (D.loops || []).some(l => i >= l.start && i <= l.end);

  /* Handle file upload */
  function handleUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const data = JSON.parse(ev.target.result);
        // Handle both process_trace.py output format and embedded format
        if (data.turns && data.agents) {
          // Normalize: process_trace.py uses "summary", older format uses "short"
          data.turns = data.turns.map(t => ({
            ...t,
            summary: t.summary || t.short || "",
            failures: t.failures || [],
            divergence: t.divergence || false,
            in_loop: t.in_loop || false,
          }));
          // Normalize beliefs
          if (data.beliefs && !data.has_divergence && data.beliefs.has_divergence !== undefined) {
            data.has_divergence = data.beliefs.has_divergence;
            data.beliefs = data.beliefs.beliefs || data.beliefs;
          }
          setCustomTrace(data);
          setActiveTrace("custom");
          setDrill(-1);
        } else {
          alert("JSON doesn't look like a processed trace. Run process_trace.py first.");
        }
      } catch (err) {
        alert("Could not parse JSON: " + err.message);
      }
    };
    reader.readAsText(file);
  }

  /* Annotations for a turn (backwards compat) */
  function getAnnotations(t) {
    // Support both old "annotations" array and new "failures"/"divergence" fields
    if (t.annotations && t.annotations.length > 0) return t.annotations;
    const anns = [];
    if (t.failures) t.failures.forEach(code => anns.push({ code, type: "failure" }));
    if (t.divergence) anns.push({ code: "divergence", type: "divergence" });
    return anns;
  }

  return (
    <div style={styles.app}>
      {/* ── Header ── */}
      <div style={styles.header}>
        <span style={{ fontSize: 20, fontWeight: 600 }}>AgentTrace</span>
        <span style={styles.tag}>{D.meta.framework} · {D.meta.benchmark}{D.meta.llm !== "unknown" ? " · " + D.meta.llm : ""}</span>
        <div style={styles.legend}>
          {agents.map(a => (
            <span key={a} style={styles.legendItem}>
              <span style={{ ...styles.dot, background: ac(a, agents) }} />
              {a.length > 14 ? a.slice(0, 14) + "…" : a}
            </span>
          ))}
          <span style={{ fontSize: 11, color: "#999" }}>{D.meta.total_turns} turns</span>
        </div>
      </div>
      {D.meta.problem_statement && (
        <p style={styles.problem}>{D.meta.problem_statement.slice(0, 150)}{D.meta.problem_statement.length > 150 ? "…" : ""}</p>
      )}

      {/* ── Toolbar ── */}
      <div style={styles.toolbar}>
        <div style={{ display: "flex", gap: 0 }}>
          {["compact", "detailed"].map(v => (
            <button key={v} onClick={() => { setView(v); setDrill(-1); }}
              style={{ ...styles.viewBtn, ...(view === v ? styles.viewBtnActive : {}), borderRadius: v === "compact" ? "5px 0 0 5px" : "0 5px 5px 0" }}>
              {v}
            </button>
          ))}
        </div>
        <button onClick={() => { setActiveTrace("ag2"); setCustomTrace(null); setDrill(-1); }}
          style={{ ...styles.traceBtn, ...(activeTrace === "ag2" && !customTrace ? { background: "#f3f3f3" } : {}) }}>
          AG2 sample
        </button>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          <button onClick={() => fileRef.current?.click()} style={styles.uploadBtn}>
            ↑ Upload processed JSON
          </button>
          <input ref={fileRef} type="file" accept=".json" onChange={handleUpload} style={{ display: "none" }} />
          {customTrace && <span style={{ fontSize: 10, color: "#059669", fontFamily: "monospace" }}>✓ custom trace loaded</span>}
        </div>
      </div>

      {/* ── Main grid ── */}
      <div style={styles.mainGrid}>
        {/* Timeline */}
        <div style={{ overflowX: "auto", paddingRight: 16 }}>
          {/* Column headers (both views) */}
          <div style={styles.swimHeader}>
            {agents.map(a => (
              <div key={a} style={{ width: colW, textAlign: "center", padding: "5px 0" }}>
                <div style={{ width: 7, height: 7, borderRadius: "50%", background: ac(a, agents), display: "inline-block", marginBottom: 2 }} />
                <div style={{ fontFamily: "monospace", fontSize: 9, color: ac(a, agents), overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", padding: "0 2px" }}>
                  {a}
                </div>
              </div>
            ))}
          </div>

          {/* Turns */}
          {(() => {
            let phase = "";
            return D.turns.map((t, i) => {
              const parts = [];

              // Phase divider
              if (t.phase && t.phase !== phase) {
                phase = t.phase;
                parts.push(
                  <div key={"p" + i} style={styles.phaseDivider}>
                    <div style={styles.phaseLine} />
                    <span style={styles.phaseLabel}>{phase}</span>
                    <div style={styles.phaseLine} />
                  </div>
                );
              }

              const il = t.in_loop || inLoop(i);
              const ci = agents.indexOf(t.agent);
              const c = ac(t.agent, agents);
              const anns = getAnnotations(t);
              const hasAnn = anns.length > 0;
              const summary = t.summary || t.short || "";

              if (view === "compact") {
                /* ── COMPACT: small bar in agent's column ── */
                parts.push(
                  <div key={i} onClick={() => setDrill(drill === i ? -1 : i)}
                    style={{ ...styles.compactRow, borderLeft: il ? "2.5px solid #dc2626" : "2.5px solid transparent", background: il ? "rgba(220,38,38,0.03)" : drill === i ? "#f8f8f8" : "transparent" }}>
                    <span style={styles.turnNum}>{i + 1}</span>
                    <div style={{ display: "flex", flex: 1 }}>
                      {agents.map((a, ai) => (
                        <div key={ai} style={{ width: colW, display: "flex", alignItems: "center", justifyContent: "center" }}>
                          {ai === ci && <>
                            <div style={{ height: 22, borderRadius: 3, minWidth: 16, maxWidth: colW - 8, padding: "0 5px", display: "flex", alignItems: "center", justifyContent: "center", background: `${c}12`, border: `1px solid ${c}30` }}>
                              <span style={{ fontSize: 9.5, fontFamily: "monospace", color: "#555", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: colW - 20 }}>{summary}</span>
                            </div>
                            {hasAnn && <span style={styles.failDot} />}
                          </>}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              } else {
                /* ── DETAILED: expanded content in agent's column ── */
                const preview = t.content.length > 300 ? t.content.slice(0, 300) + "…" : t.content;
                parts.push(
                  <div key={i} onClick={() => setDrill(drill === i ? -1 : i)}
                    style={{ ...styles.compactRow, borderLeft: il ? "2.5px solid #dc2626" : "2.5px solid transparent", background: il ? "rgba(220,38,38,0.03)" : drill === i ? "#f8f8f8" : "transparent", alignItems: "flex-start", minHeight: 40 }}>
                    <span style={{ ...styles.turnNum, paddingTop: 4 }}>{i + 1}</span>
                    <div style={{ display: "flex", flex: 1 }}>
                      {agents.map((a, ai) => (
                        <div key={ai} style={{ width: colW, display: "flex", justifyContent: "center", padding: "2px 2px" }}>
                          {ai === ci && (
                            <div style={{ width: colW - 8, padding: "6px 8px", borderRadius: 5, background: `${c}08`, border: `1px solid ${c}20` }}>
                              <div style={{ fontFamily: "monospace", fontSize: 9, fontWeight: 600, color: c, marginBottom: 3 }}>{a.length > 16 ? a.slice(0, 16) + "…" : a}</div>
                              <div style={{ fontSize: 11, lineHeight: 1.45, color: "#666", wordBreak: "break-word", whiteSpace: "pre-wrap" }}>{preview}</div>
                              {hasAnn && <div style={{ marginTop: 4 }}>{anns.map((ann, j) => <Badge key={j} code={ann.code} type={ann.type} />)}</div>}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              }

              /* ── Drill-down panel ── */
              if (drill === i) {
                parts.push(
                  <div key={"d" + i} style={styles.drillPanel}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                      <span style={{ fontFamily: "monospace", fontSize: 10, fontWeight: 600, padding: "1px 6px", borderRadius: 4, background: `${c}12`, color: c }}>{t.agent}</span>
                      <span style={{ fontFamily: "monospace", fontSize: 10, color: "#aaa" }}>turn {i + 1}{t.phase ? " · " + t.phase : ""}</span>
                      <button onClick={(e) => { e.stopPropagation(); setDrill(-1); }} style={styles.drillClose}>close</button>
                    </div>
                    <div style={styles.drillContent}>{t.content}</div>
                    {hasAnn && (
                      <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid #eee" }}>
                        {anns.map((ann, j) => <Badge key={j} code={ann.code} type={ann.type} />)}
                      </div>
                    )}
                  </div>
                );
              }

              return parts;
            });
          })()}
        </div>

        {/* ── Sidebar ── */}
        <div style={styles.sidebar}>
          {/* Beliefs */}
          {D.has_divergence && D.beliefs && (
            <div style={{ marginBottom: 18 }}>
              <h3 style={styles.sideHead}>Belief divergence</h3>
              {Object.entries(D.beliefs).map(([a, b], idx) => {
                if (typeof b !== "string") return null;
                const c = ac(a, agents);
                return (
                  <div key={a}>
                    <div style={{ padding: "8px 10px", borderRadius: 6, marginBottom: 4, border: `1px solid ${c}25`, background: `${c}08` }}>
                      <div style={{ fontFamily: "monospace", fontSize: 9, textTransform: "uppercase", letterSpacing: 0.8, color: c, marginBottom: 2 }}>{a}</div>
                      <div style={{ fontSize: 11, color: "#666", lineHeight: 1.4 }}>"{b}"</div>
                    </div>
                    {idx === 0 && Object.keys(D.beliefs).length > 1 && (
                      <div style={{ textAlign: "center", fontFamily: "monospace", fontSize: 10, color: "#dc2626", padding: "2px 0" }}>⚡ beliefs diverge</div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Failures */}
          {Object.keys(D.failures).length > 0 && (
            <div style={{ marginBottom: 18 }}>
              <h3 style={styles.sideHead}>Detected failures</h3>
              {Object.entries(D.failures).map(([code, info]) => {
                const m = MAST[code] || {};
                const cnt = D.turns.filter(t => (t.failures || []).includes(code) || (t.annotations || []).some(a => a.code === code)).length;
                return (
                  <div key={code} style={styles.failureRow}>
                    <span style={styles.failureCode}>{code}</span>
                    <div>
                      <div style={{ fontSize: 11, color: "#333", fontWeight: 500 }}>{m.l || info.label}</div>
                      <div style={{ fontSize: 9.5, color: "#999" }}>{m.c || info.category}{cnt ? " · " + cnt + " turn(s)" : " · trace-level"}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Loops */}
          {(D.loops || []).length > 0 && (
            <div style={{ marginBottom: 18 }}>
              <h3 style={styles.sideHead}>Loops</h3>
              {D.loops.map((l, i) => (
                <div key={i} style={styles.loopBox}>Turns {l.start + 1}–{l.end + 1}</div>
              ))}
            </div>
          )}

          {/* Metadata */}
          <div style={{ marginBottom: 18 }}>
            <h3 style={styles.sideHead}>Metadata</h3>
            <div style={styles.metaBlock}>
              <div><span style={{ color: "#2563eb" }}>framework</span>: {D.meta.framework}</div>
              <div><span style={{ color: "#2563eb" }}>benchmark</span>: {D.meta.benchmark}</div>
              <div><span style={{ color: "#2563eb" }}>llm</span>: {D.meta.llm}</div>
              <div><span style={{ color: "#2563eb" }}>turns</span>: {D.meta.total_turns}</div>
              <div><span style={{ color: "#2563eb" }}>failures</span>: [{Object.keys(D.failures).map(c => '"' + c + '"').join(", ")}]</div>
            </div>
          </div>

          {/* Expert note */}
          {D.meta.note_text && (
            <div>
              <h3 style={styles.sideHead}>Expert note</h3>
              <div style={styles.noteBox}>{D.meta.note_text}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Styles ── */
const styles = {
  app: { fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif", color: "#1a1a1a", maxWidth: 1200, margin: "0 auto", padding: "0 12px", background: "#fff", minHeight: "100vh" },
  header: { display: "flex", alignItems: "baseline", gap: 12, padding: "14px 0", borderBottom: "1px solid #e5e5e5", flexWrap: "wrap" },
  tag: { fontFamily: "monospace", fontSize: 11, padding: "2px 8px", borderRadius: 6, background: "#f3f3f3", color: "#666" },
  legend: { display: "flex", gap: 10, marginLeft: "auto", alignItems: "center", flexWrap: "wrap" },
  legendItem: { display: "inline-flex", alignItems: "center", gap: 3, fontSize: 11, color: "#666" },
  dot: { width: 7, height: 7, borderRadius: "50%", display: "inline-block" },
  problem: { fontSize: 12, color: "#888", margin: "6px 0 0", lineHeight: 1.4 },
  toolbar: { display: "flex", gap: 8, alignItems: "center", padding: "8px 0", borderBottom: "1px solid #e5e5e5", flexWrap: "wrap" },
  viewBtn: { fontSize: 11, padding: "4px 12px", border: "1px solid #ccc", background: "#fff", color: "#666", cursor: "pointer", fontFamily: "inherit" },
  viewBtnActive: { background: "#2563eb", color: "#fff", borderColor: "#2563eb" },
  traceBtn: { fontSize: 11, padding: "4px 10px", border: "1px solid #ccc", borderRadius: 5, background: "#fff", color: "#555", cursor: "pointer", fontFamily: "inherit" },
  uploadBtn: { fontSize: 11, padding: "4px 12px", border: "1px solid #059669", borderRadius: 5, background: "#f0fdf4", color: "#059669", cursor: "pointer", fontFamily: "monospace", fontWeight: 500 },
  mainGrid: { display: "grid", gridTemplateColumns: "1fr 250px", gap: 0, marginTop: 8 },
  swimHeader: { display: "flex", paddingLeft: 40, borderBottom: "1px solid #eee", marginBottom: 4, position: "sticky", top: 0, background: "#fff", zIndex: 5 },
  compactRow: { display: "flex", alignItems: "center", minHeight: 28, cursor: "pointer", borderRadius: 5, padding: "1px 0" },
  turnNum: { width: 36, textAlign: "right", fontFamily: "monospace", fontSize: 9.5, color: "#bbb", paddingRight: 5, flexShrink: 0 },
  failDot: { width: 6, height: 6, borderRadius: "50%", background: "#dc2626", marginLeft: 2, flexShrink: 0 },
  phaseDivider: { display: "flex", alignItems: "center", gap: 8, padding: "7px 0 3px" },
  phaseLine: { flex: 1, height: 1, background: "#e5e5e5" },
  phaseLabel: { fontFamily: "monospace", fontSize: 9, color: "#aaa", letterSpacing: 1, textTransform: "uppercase", whiteSpace: "nowrap" },
  drillPanel: { margin: "4px 0 4px 40px", padding: 14, background: "#fff", border: "1px solid #ddd", borderRadius: 8 },
  drillClose: { marginLeft: "auto", fontSize: 10, padding: "2px 8px", border: "1px solid #ddd", borderRadius: 4, background: "#fff", cursor: "pointer", fontFamily: "inherit", color: "#888" },
  drillContent: { fontSize: 12.5, lineHeight: 1.6, color: "#333", whiteSpace: "pre-wrap", maxHeight: 300, overflowY: "auto", wordBreak: "break-word" },
  sidebar: { borderLeft: "1px solid #e5e5e5", paddingLeft: 16, fontSize: 12 },
  sideHead: { fontSize: 10, fontWeight: 500, color: "#999", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 8, fontFamily: "monospace" },
  failureRow: { display: "flex", gap: 6, padding: "5px 0", borderBottom: "1px solid #f0f0f0", alignItems: "flex-start" },
  failureCode: { fontFamily: "monospace", fontSize: 10, color: "#dc2626", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.15)", padding: "0px 4px", borderRadius: 3, whiteSpace: "nowrap" },
  loopBox: { fontFamily: "monospace", fontSize: 10, color: "#666", padding: "4px 8px", borderRadius: 4, background: "rgba(220,38,38,0.04)", border: "1px solid rgba(220,38,38,0.12)", marginBottom: 3 },
  metaBlock: { fontFamily: "monospace", fontSize: 10.5, lineHeight: 1.8, color: "#777", background: "#f8f8f6", borderRadius: 6, padding: "8px 10px" },
  noteBox: { fontSize: 11, color: "#777", lineHeight: 1.45, fontStyle: "italic", background: "#f8f8f6", padding: 8, borderRadius: 6 },
  badgeFail: { fontFamily: "monospace", fontSize: 9, padding: "1px 5px", borderRadius: 3, background: "rgba(220,38,38,0.08)", color: "#dc2626", border: "1px solid rgba(220,38,38,0.2)", marginRight: 3, whiteSpace: "nowrap", display: "inline-block" },
  badgeDiverge: { fontFamily: "monospace", fontSize: 9, padding: "1px 5px", borderRadius: 3, background: "rgba(217,119,6,0.08)", color: "#d97706", border: "1px solid rgba(217,119,6,0.2)", marginRight: 3, whiteSpace: "nowrap", display: "inline-block" },
  empty: { padding: "80px 20px", textAlign: "center", color: "#999", fontFamily: "system-ui, sans-serif" },
};
