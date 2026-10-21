import { useMemo, useState } from "react";
import scenario607 from "../runs/assetopsbench/assetops-607-events.json";
import scenario620 from "../runs/assetopsbench/assetops-620-events.json";

const SCENARIOS = {
  "607": {
    title: "Scenario 607 — failure modes and sensors",
    note: "Two Chiller failure-mode lookups fail; the agent later uses pump data, which does not prove a Chiller fact.",
    events: scenario607,
  },
  "620": {
    title: "Scenario 620 — anomaly-model sensors",
    note: "The agent looks up installed sensors, measured sensors, and the available date range before answering.",
    events: scenario620,
  },
};

function unpack(event) {
  if (event.action === "final_answer") return { summary: event.message, error: false };
  try {
    const payload = JSON.parse(event.message);
    const output = Array.isArray(payload.output) ? payload.output.map(x => x.text || "").join("\n") : String(payload.output || "");
    const parsed = JSON.parse(output);
    if (parsed.error) return { summary: parsed.error, error: true };
    return { summary: parsed.message || output.slice(0, 180), error: false };
  } catch {
    return { summary: event.message.slice(0, 180), error: /error/i.test(event.message) };
  }
}

function shortPointer(source) {
  return source.replace("assetopsbench:", "").replace("/trajectory/", "…/");
}

export default function AssetOpsTimeline() {
  const [scenarioId, setScenarioId] = useState("607");
  const [selected, setSelected] = useState(0);
  const scenario = SCENARIOS[scenarioId];
  const events = scenario.events;
  const current = events[selected] || events[0];
  const summary = useMemo(() => events.map(unpack), [events]);

  return <main style={styles.page}>
    <div style={styles.eyebrow}>AssetOpsBench trace viewer</div>
    <h1 style={styles.title}>{scenario.title}</h1>
    <p style={styles.note}>{scenario.note}</p>

    <div style={styles.switcher} aria-label="Choose AssetOpsBench scenario">
      {Object.keys(SCENARIOS).map(id => <button key={id} onClick={() => { setScenarioId(id); setSelected(0); }} style={{...styles.scenarioButton, ...(scenarioId === id ? styles.scenarioActive : {})}}>
        Scenario {id}
      </button>)}
    </div>

    <div style={styles.grid}>
      <section aria-label="Trace events">
        <div style={styles.sectionTitle}>{events.length} recorded events</div>
        <ol style={styles.timeline}>
          {events.map((event, index) => {
            const item = summary[index];
            const active = index === selected;
            return <li key={event.source_trace} style={styles.item}>
              <button onClick={() => setSelected(index)} style={{...styles.eventButton, ...(active ? styles.eventActive : {}), ...(item.error ? styles.eventError : {})}}>
                <span style={styles.index}>{index + 1}</span>
                <span style={styles.eventMain}>
                  <strong>{event.action === "tool_call" ? event.target : "Final answer"}</strong>
                  <span style={styles.summary}>{item.summary}</span>
                </span>
                {item.error && <span style={styles.errorLabel}>tool problem</span>}
              </button>
            </li>;
          })}
        </ol>
      </section>

      <aside style={styles.detail} aria-label="Selected event details">
        <div style={styles.sectionTitle}>Selected event</div>
        <p><b>Agent:</b> {current.agent}</p>
        <p><b>Action:</b> {current.action}</p>
        <p><b>Target:</b> {current.target}</p>
        <p><b>Source:</b> <code style={styles.code}>{shortPointer(current.source_trace)}</code></p>
        <div style={styles.messageLabel}>Recorded message</div>
        <pre style={styles.message}>{current.message}</pre>
      </aside>
    </div>
  </main>;
}

const styles = {
  page: { maxWidth: 1040, margin: "0 auto", padding: "28px 20px 48px", color: "#172033" },
  eyebrow: { color: "#64748b", fontSize: 12, fontWeight: 600, letterSpacing: ".04em", textTransform: "uppercase" },
  title: { fontSize: 26, margin: "8px 0" },
  note: { margin: "0 0 18px", color: "#475569", maxWidth: 760, lineHeight: 1.5 },
  switcher: { display: "flex", gap: 8, marginBottom: 24 },
  scenarioButton: { cursor: "pointer", border: "1px solid #cbd5e1", background: "#fff", color: "#334155", borderRadius: 6, padding: "8px 12px", fontWeight: 600 },
  scenarioActive: { background: "#2563eb", color: "#fff", borderColor: "#2563eb" },
  grid: { display: "grid", gridTemplateColumns: "minmax(0, 1.1fr) minmax(300px, .9fr)", gap: 22, alignItems: "start" },
  sectionTitle: { fontSize: 13, fontWeight: 700, color: "#475569", marginBottom: 10 },
  timeline: { listStyle: "none", padding: 0, margin: 0, borderLeft: "2px solid #dbeafe" },
  item: { position: "relative", marginLeft: 14, marginBottom: 9 },
  eventButton: { width: "100%", textAlign: "left", cursor: "pointer", display: "flex", gap: 10, alignItems: "flex-start", border: "1px solid #e2e8f0", background: "#fff", borderRadius: 7, padding: 10, color: "#172033" },
  eventActive: { borderColor: "#2563eb", boxShadow: "0 0 0 2px #dbeafe" },
  eventError: { borderLeft: "4px solid #dc2626" },
  index: { flex: "0 0 auto", color: "#64748b", fontSize: 12, fontFamily: "monospace", paddingTop: 2 },
  eventMain: { minWidth: 0, display: "grid", gap: 3 },
  summary: { color: "#475569", fontSize: 13, lineHeight: 1.35, overflow: "hidden", textOverflow: "ellipsis" },
  errorLabel: { marginLeft: "auto", flex: "0 0 auto", color: "#b91c1c", fontSize: 11, fontWeight: 700 },
  detail: { border: "1px solid #e2e8f0", borderRadius: 8, padding: 16, background: "#f8fafc", fontSize: 13, lineHeight: 1.45, position: "sticky", top: 12 },
  code: { fontSize: 11, overflowWrap: "anywhere" },
  messageLabel: { fontWeight: 700, marginTop: 14, marginBottom: 6 },
  message: { whiteSpace: "pre-wrap", overflowWrap: "anywhere", maxHeight: 390, overflowY: "auto", background: "#0f172a", color: "#e2e8f0", padding: 12, borderRadius: 6, fontSize: 11, lineHeight: 1.4 },
};
