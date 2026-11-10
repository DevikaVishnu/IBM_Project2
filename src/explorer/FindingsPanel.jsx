import { useEffect, useRef, useState } from "react";
import { PlainFinding, guideFinding } from "./PlainView.jsx";
import { Chip, Excerpt, OriginTag, card, eyebrow, linkBtn, mono, v } from "./theme.jsx";

// Findings: optional fields on bundle flags[] (CONTRACT.md, "Findings") plus the optional top-level `assessment`.
// Everything shown comes from the bundle; no trace, run or id is special-cased here.  A finding is hand-validated
// (never "detected"); its observed anchors, computed checks and hand interpretation are kept visibly apart.

export const isFinding = f => f && typeof f.category === "string";
export const findingsOf = b => b.flags.filter(isFinding).sort((x, y) => (x.priority ?? 99) - (y.priority ?? 99));

// One tone per category, for identity only: categories are different kinds of finding, not severities.
const CAT_TONE = { cross_agent_assertion_incompatibility: "primary", direct_evidence_contradiction: "danger",
  recorded_coordination_disagreement: "warning", position_decision_inconsistency: "muted" };
export function CategoryChip({ f }) {
  return <Chip tone={CAT_TONE[f.category] ?? "muted"} title={f.category_definition}>{f.category_label ?? f.category}</Chip>;
}
export function HandValidated() {
  return <Chip tone="warning" title="Checked by a person against the source. Not automatic detection.">hand-validated</Chip>;
}

export function AssessmentNote({ a, compact, plain }) {
  if (!a) return null;
  const not = a.status === "not_assessed";
  return (
    <div role="note" data-testid="assessment" data-status={a.status}
      style={{ ...card, padding: compact ? "8px 12px" : "10px 14px", display: "flex", flexWrap: "wrap", gap: "6px 10px", alignItems: "center", fontSize: 13, lineHeight: 1.5,
        background: not ? "#F8FAFC" : "#FFFBEB", borderColor: not ? v("line") : "#FDE68A" }}>
      <b>{not ? "Not assessed" : "Hand-validated findings"}</b>
      <OriginTag origin={a.origin} />
      {plain
        ? <span style={{ flex: "1 1 420px", color: v("ink") }}>{plain}{" "}
            <details style={{ display: "inline" }}><summary style={{ display: "inline", cursor: "pointer", fontSize: 12, color: v("muted") }}>Technical note</summary> <span style={{ fontSize: 12.5 }}>{a.text}</span></details></span>
        : <span style={{ flex: "1 1 420px", color: v("ink") }}>{a.text}</span>}
      {a.ground_truth && <span style={{ fontSize: 12, color: v("muted") }}>Ground truth: {a.ground_truth}</span>}
    </div>
  );
}

function List({ title, items, testid, tone }) {
  if (!items?.length) return null;
  return (
    <div data-testid={testid}>
      <div style={{ ...eyebrow, marginBottom: 4, color: tone === "unknown" ? "#475569" : undefined }}>{title}</div>
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, lineHeight: 1.55 }}>{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    </div>
  );
}

export function FindingCard({ b, f, active, onSelect, nav, guide }) {
  // With guide copy, the card leads with the plain-language finding and keeps everything below behind
  // "Technical evidence"; without it the card is unchanged.
  const plain = guideFinding(guide, f);
  const [tech, setTech] = useState(false);
  const showTech = plain ? tech : active;
  const claims = Object.fromEntries(b.claims.map(c => [c.id, c]));
  const cols = Object.fromEntries((b.matrix?.columns ?? []).map(c => [c.id, c]));
  const pos = Object.fromEntries((b.positions?.observations ?? []).map(o => [o.id, o]));
  const colName = id => { const c = cols[id]; return c ? `${id.replace(/^llm:|:1$/g, "").replace(/^exec:/, "")} · ${c.kind === "deterministic_execution" ? "code" : "model call"} · seq ${c.order}` : id; };
  const posName = id => { const o = pos[id]; return o ? `${o.kind.replace("_", " ")} · seq ${o.seq}${o.recorded_label ? ` · ${o.recorded_label}` : ""}` : id; };
  const evName = id => b.evidence[id]?.label?.replace(/ \(hand-grounded\)$/, "") ?? id;
  const btn = { ...linkBtn, fontSize: 12.5 };
  // When a card is opened here, the previously open card collapses; keep the newly opened card's top in view.
  const ref = useRef(null);
  const wasActive = useRef(active);
  useEffect(() => {
    if (active && !wasActive.current && ref.current) {
      const r = ref.current.getBoundingClientRect();
      if (r.top < 0 || r.top > window.innerHeight * 0.5) ref.current.scrollIntoView({ block: "start" });
    }
    wasActive.current = active;
  }, [active]);
  return (
    <article ref={ref} data-testid={`finding-${f.id}`} aria-label={f.title} aria-expanded={active}
      style={{ ...card, padding: "14px 16px", borderColor: active ? "#F59E0B" : undefined, boxShadow: active ? "0 0 0 2px #FDE68A" : "none" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span style={{ ...mono, fontWeight: 700, color: v("muted") }}>#{f.priority}</span>
        <CategoryChip f={f} />
        <HandValidated />
        <h3 style={{ margin: 0, fontSize: 14.5, fontWeight: 700, color: v("ink"), flex: "1 1 320px" }}>{plain ? plain.title : f.title}</h3>
        {plain && f.columns?.length > 0 && <button style={btn} data-testid={`finding-matrix-${f.id}`} onClick={() => nav.column(f, f.columns[0])}>Show in matrix</button>}
        {plain
          ? <button style={btn} data-testid={`finding-toggle-${f.id}`} aria-expanded={tech} onClick={() => { setTech(!tech); if (!tech) onSelect(f.id); }}>{tech ? "Hide technical evidence" : "Technical evidence"}</button>
          : <button style={btn} data-testid={`finding-toggle-${f.id}`} onClick={() => onSelect(active ? null : f.id)}>{active ? "Hide details" : "Show details"}</button>}
      </div>
      {plain ? <PlainFinding x={plain} /> : <p style={{ margin: "8px 0 0", fontSize: 13.5, lineHeight: 1.55, color: v("ink") }}>{f.text}</p>}
      {plain && tech && (
        <div data-testid="finding-technical" style={{ marginTop: 12, paddingTop: 10, borderTop: `1px dashed ${v("line")}` }}>
          <div style={{ ...eyebrow, marginBottom: 4 }}>Technical evidence · original finding</div>
          <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55, color: v("ink") }}>{f.text}</p>
        </div>
      )}
      {(!plain || tech) && <div data-testid={`finding-nav-${f.id}`} style={{ display: "flex", flexWrap: "wrap", gap: "4px 14px", marginTop: 8, fontSize: 12.5, alignItems: "baseline" }}>
        {f.refs?.claims?.length > 0 && <span><span style={{ color: v("muted") }}>Claims:</span>{" "}
          {f.refs.claims.map((id, i) => <span key={id}>{i > 0 && " · "}<button style={btn} data-testid={`finding-claim-${id}`} onClick={() => nav.claim(id)}>{claims[id]?.label ?? id}</button></span>)}</span>}
        {f.columns?.length > 0 && <span><span style={{ color: v("muted") }}>Matrix:</span>{" "}
          {f.columns.map((id, i) => <span key={id}>{i > 0 && " · "}<button style={btn} data-testid={`finding-col-${id}`} onClick={() => nav.column(f, id)}>{colName(id)}</button></span>)}</span>}
        {f.refs?.positions?.length > 0 && <span><span style={{ color: v("muted") }}>Computed positions:</span>{" "}
          {f.refs.positions.map((id, i) => <span key={id}>{i > 0 && " · "}<button style={btn} data-testid={`finding-pos-${id}`} onClick={() => nav.position(id)}>{posName(id)}</button></span>)}</span>}
      </div>}
      {showTech && (
        <div style={{ marginTop: 12, display: "grid", gap: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(380px, 1fr))", gap: 12, alignItems: "start" }}>
            <div data-testid="finding-observed">
              <div style={{ ...eyebrow, marginBottom: 4 }}>Observed in the trace</div>
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 6 }}>
                {f.observed.map((o, i) => (
                  <li key={i} style={{ fontSize: 13, lineHeight: 1.45 }}>
                    <span style={{ display: "flex", gap: 6, alignItems: "baseline", flexWrap: "wrap" }}><OriginTag origin={o.origin} /><span>{o.text}</span></span>
                    <span style={{ display: "block", ...mono, background: v("canvas"), borderRadius: 4, padding: "2px 6px", marginTop: 2, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{o.value}</span>
                    <span style={{ display: "block", ...mono, fontSize: 11, color: v("muted"), wordBreak: "break-all" }}>{o.locator}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div data-testid="finding-computed">
              <div style={{ ...eyebrow, marginBottom: 4 }}>Computed checks</div>
              {f.computed?.length ? (
                <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 6 }}>
                  {f.computed.map((x, i) => <li key={i} style={{ display: "flex", gap: 8, alignItems: "baseline", fontSize: 13, lineHeight: 1.5 }}><OriginTag origin={x.origin} style={{ flex: "none" }} /><span>{x.text}</span></li>)}
                </ul>
              ) : <p style={{ margin: 0, fontSize: 13, color: v("muted") }}>None.</p>}
            </div>
          </div>
          <div data-testid="finding-interpretation" style={{ background: "#FFFBEB", border: "1px solid #FDE68A", borderRadius: 8, padding: "8px 12px" }}>
            <div style={{ ...eyebrow, marginBottom: 4, display: "flex", gap: 6, alignItems: "center" }}>Interpretation <OriginTag origin={f.interpretation.origin} /></div>
            <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55 }}>{f.interpretation.text}</p>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(380px, 1fr))", gap: 12, alignItems: "start" }}>
            <List title="Limitations" items={f.limitations} testid="finding-limitations" />
            <List title="Unknown / not established" items={f.unknowns} testid="finding-unknowns" tone="unknown" />
          </div>
          {f.evidence?.length > 0 && (
            <details data-testid="finding-evidence">
              <summary style={{ fontSize: 13, cursor: "pointer", color: v("muted") }}>Messages and evidence items ({f.evidence.length})</summary>
              <div style={{ marginTop: 8, display: "grid", gap: 8 }}>
                {f.evidence.map(id => {
                  const x = b.evidence[id];
                  return x && (
                    <div key={id}>
                      <div style={{ fontSize: 12.5, color: v("muted"), marginBottom: 4, display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                        {evName(id)}{x.text_mechanism && <Chip tone={x.text_mechanism === "deterministic" ? "muted" : "primary"}>{x.text_mechanism === "deterministic" ? "code-built text" : "LLM-voiced text"}</Chip>}<OriginTag origin={x.origin} />
                      </div>
                      <Excerpt excerpt={x.excerpt} maxHeight={120} />
                    </div>
                  );
                })}
              </div>
            </details>
          )}
        </div>
      )}
    </article>
  );
}

export function FindingsSummary({ b, onOpenFinding, guide }) {
  const a = b.assessment;
  if (!a) return null;
  const fs = findingsOf(b);
  return (
    <section data-testid="overview-findings" aria-label="Findings" style={{ ...card, padding: "12px 16px" }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", marginBottom: fs.length ? 8 : 0 }}>
        <h3 style={{ margin: 0, fontSize: 14.5, fontWeight: 700 }}>Findings</h3>
        {a.status === "not_assessed" ? <Chip tone="muted">Not assessed</Chip> : <HandValidated />}
        <OriginTag origin={a.origin} />
        <span style={{ fontSize: 12.5, color: v("muted"), flex: "1 1 360px" }}>{a.status === "not_assessed" ? a.text : "Checked by hand against the source, not detected automatically, and not a complete search."}</span>
        {fs.length > 0 && <button style={linkBtn} onClick={() => onOpenFinding(null)}>Open findings</button>}
      </div>
      {fs.length > 0 && (
        <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 2 }}>
          {fs.map(f => (
            <li key={f.id}>
              <button className="be-hover" data-testid={`overview-finding-${f.id}`} onClick={() => onOpenFinding(f.id)}
                style={{ width: "100%", display: "flex", gap: 8, alignItems: "center", textAlign: "left", background: "none", border: "none", borderRadius: 6, padding: "5px 6px", cursor: "pointer", fontSize: 13, color: v("ink") }}>
                <span style={{ ...mono, color: v("muted"), width: 22 }}>#{f.priority}</span>
                <span style={{ flex: "none", width: 270 }}><CategoryChip f={f} /></span>
                <span style={{ flex: 1 }}>{guideFinding(guide, f)?.title ?? f.title}</span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
