import { useMemo, useState } from "react";

// runs/assetopsbench/ is local-only (gitignored): each trace is loaded only if its file is present, so a fresh clone still builds.
const DATA = import.meta.glob(["../runs/assetopsbench/assetops-607-events.json", "../runs/assetopsbench/assetops-620-events.json"], { eager: true, import: "default" });
const traces = Object.fromEntries([
  ["607", { task: "Find Chiller 6 failure modes that its sensors can monitor.", events: DATA["../runs/assetopsbench/assetops-607-events.json"] }],
  ["620", { task: "Choose Chiller 6 sensors and data timing for trip detection.", events: DATA["../runs/assetopsbench/assetops-620-events.json"] }],
].filter(([, v]) => v.events));

function eventInfo(event) {
  if (event.action === "final_answer") return { label: "Final answer", status: "answer", output: event.message };
  try {
    const wrapped = JSON.parse(event.message);
    const raw = Array.isArray(wrapped.output) ? wrapped.output.map(x => x.text || "").join("\n") : String(wrapped.output || "");
    const output = JSON.parse(raw);
    return { label: event.target, status: output.error ? "error" : "ok", input: wrapped.input, output };
  } catch { return { label: event.target, status: "unknown", output: event.message }; }
}

export default function AssetOpsTimeline() {
  if (!Object.keys(traces).length) return <main style={s.page}><div style={s.kicker}>AssetOpsBench trace</div><p data-testid="local-only-data" style={s.task}>AssetOpsBench run traces are local-only and are not in this repository. Put the <code>assetops-*-events.json</code> files in <code>runs/assetopsbench/</code> to see the timeline.</p></main>;
  return <Timeline />;
}

function Timeline() {
  const [id, setId] = useState(Object.keys(traces)[0]);
  const [selected, setSelected] = useState(0);
  const trace = traces[id];
  const items = useMemo(() => trace.events.map(eventInfo), [trace]);
  const current = items[selected];

  return <main style={s.page}>
    <header style={s.header}>
      <div>
        <div style={s.kicker}>AssetOpsBench trace</div>
        <h1 style={s.title}>Scenario {id}</h1>
        <p style={s.task}>{trace.task}</p>
      </div>
      <div style={s.tabs} aria-label="Scenario selection">
        {Object.keys(traces).map(key => <button key={key} onClick={() => { setId(key); setSelected(0); }} style={{ ...s.tab, ...(key === id ? s.activeTab : {}) }}>Scenario {key}</button>)}
      </div>
    </header>

    <section aria-label="Events in order">
      <p style={s.hint}>Read left to right. Click a step to see what happened.</p>
      <div style={s.track}>
        {items.map((item, index) => <button key={trace.events[index].source_trace} onClick={() => setSelected(index)} style={{ ...s.step, ...(selected === index ? s.selected : {}), ...(item.status === "error" ? s.error : {}), ...(item.status === "answer" ? s.answer : {}) }}>
          <span style={s.number}>{index + 1}</span>
          <span style={s.stepLabel}>{item.label}</span>
          <span style={s.status}>{item.status === "error" ? "failed" : item.status === "answer" ? "answer" : "done"}</span>
        </button>)}
      </div>
    </section>

    <section style={s.detail} aria-label="Selected step detail">
      <div style={s.detailTop}><span>Step {selected + 1}</span><strong>{current.label}</strong></div>
      {current.input && <div><h2 style={s.detailLabel}>Input</h2><pre style={s.code}>{JSON.stringify(current.input, null, 2)}</pre></div>}
      <div><h2 style={s.detailLabel}>{current.status === "answer" ? "Answer" : "Result"}</h2><pre style={s.code}>{typeof current.output === "string" ? current.output : JSON.stringify(current.output, null, 2)}</pre></div>
    </section>
  </main>;
}

const s = {
  page: { maxWidth: 1100, margin: "0 auto", padding: "24px 16px 40px", color: "#172033", fontFamily: "'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif" },
  header: { display: "flex", justifyContent: "space-between", gap: 24, alignItems: "flex-start", flexWrap: "wrap", marginBottom: 40 },
  kicker: { fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".08em", color: "#64748b" },
  title: { fontSize: 32, margin: "7px 0" }, task: { margin: 0, color: "#475569", fontSize: 16, maxWidth: 610, lineHeight: 1.5 },
  tabs: { display: "flex", border: "1px solid #d1d5db", borderRadius: 7, overflow: "hidden" }, tab: { border: 0, borderRight: "1px solid #d1d5db", background: "#fff", padding: "9px 12px", cursor: "pointer", color: "#475569", fontWeight: 600 }, activeTab: { background: "#172033", color: "#fff" },
  hint: { color: "#64748b", fontSize: 13, marginBottom: 12 }, track: { display: "flex", gap: 0, overflowX: "auto", padding: "10px 0 26px" },
  step: { minWidth: 142, flex: "1 0 142px", minHeight: 112, padding: 14, textAlign: "left", cursor: "pointer", border: "1px solid #d1d5db", borderRight: 0, background: "#fff", color: "#172033", display: "flex", flexDirection: "column", gap: 7 }, selected: { background: "#eff6ff", outline: "2px solid #2563eb", outlineOffset: -2, zIndex: 1 }, error: { borderTop: "4px solid #dc2626" }, answer: { borderTop: "4px solid #15803d" },
  number: { color: "#94a3b8", fontFamily: "monospace", fontSize: 12 }, stepLabel: { fontWeight: 700, overflowWrap: "anywhere" }, status: { color: "#64748b", fontSize: 12, marginTop: "auto" },
  detail: { borderTop: "1px solid #d1d5db", paddingTop: 24, maxWidth: 760 }, detailTop: { display: "flex", gap: 12, alignItems: "baseline", color: "#64748b", fontSize: 13, marginBottom: 16 }, detailLabel: { fontSize: 13, margin: "16px 0 7px", color: "#475569" }, code: { margin: 0, whiteSpace: "pre-wrap", overflowWrap: "anywhere", maxHeight: 320, overflowY: "auto", padding: 14, borderRadius: 6, background: "#f1f5f9", color: "#172033", fontSize: 12, lineHeight: 1.5 },
};
