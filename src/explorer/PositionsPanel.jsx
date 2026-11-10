import { useMemo, useState } from "react";
import { Chip, Empty, Excerpt, OriginTag, card, eyebrow, linkBtn, mono, v } from "./theme.jsx";

// Computed positions (optional bundle field `positions`, CONTRACT.md "Framework-computed positions").
// Rows: agents (their framework-computed positions), then the council's joint rankings, the overall hypothesis
// scores and the final decision, each on its own row so they are never read as one agent's view.  Columns: the
// bundle's segments (recorded round, else recorded stage), in seq order.  Nothing here is a claim, belief or state.

export const POSITIONS_LABEL = "Framework-computed positions — not agent beliefs";

const KIND = {
  agent_position: { row: "Agent-specific computed position", short: "agent position", tone: "primary" },
  joint_ranking: { row: "Joint council ranking", short: "joint ranking", tone: "warning" },
  hypothesis_scores: { row: "Overall hypothesis scores", short: "overall scores", tone: "muted" },
  final_decision: { row: "Final selected diagnosis", short: "final decision", tone: "success" },
};
// Categorical colours for diagnosis labels, assigned in the bundle's candidate order (no meaning beyond identity).
const PALETTE = ["#2563EB", "#D97706", "#059669", "#DB2777", "#7C3AED", "#0891B2", "#65A30D", "#475569"];

function abbreviations(cands) {
  const out = {};
  const used = new Set();
  for (const c of cands) {
    let a = c.split(/\s+/).map(w => w[0]).join("").toUpperCase();
    if (a.length < 2 || used.has(a)) a = c.replace(/\s+/g, "").slice(0, 3);
    let k = 2;
    while (used.has(a)) a = `${a.slice(0, 3)}${k++}`;
    used.add(a);
    out[c] = a;
  }
  return out;
}

const f3 = x => (typeof x === "number" ? (Math.abs(x) < 1 ? x.toFixed(Math.max(3, (String(x).split(".")[1] ?? "").length)).replace(/^0/, "") : String(x)) : "—");
const who = (agents, id) => agents[id] ?? id;

function Swatch({ color }) {
  return <span aria-hidden="true" style={{ width: 9, height: 9, borderRadius: 2, background: color, display: "inline-block", flex: "none" }} />;
}

function ObsChip({ o, on, onSelect, ab, col, states }) {
  const ld = o.leading;
  const main = o.kind === "hypothesis_scores"
    ? `${o.score_state ?? "S?"} · ${o.basis === "event" ? (o.part === "hypotheses" ? "event" : o.part) : o.basis === "execution_input" ? "in" : "out"}${o.holder.recorded_on_execution ? ` ${o.holder.recorded_on_execution}` : ""}`
    : o.kind === "final_decision" ? `${ab[o.recorded_label] ?? o.recorded_label} · conf ${f3(o.confidence)}`
      : `${ld ? (ld.tie ? ld.labels.map(l => ab[l] ?? l).join("=") : ab[ld.labels[0]] ?? ld.labels[0]) : "?"} ${ld ? f3(ld.score) : ""}`;
  const lead = o.kind === "final_decision" ? o.recorded_label : ld?.labels?.[0];
  const marks = [];
  if (o.draft) marks.push("draft");
  if (ld?.tie) marks.push("tie");
  if (o.recorded_label && ld && !ld.labels.includes(o.recorded_label)) marks.push("label ≠ top");
  if (o.kind === "hypothesis_scores" && o.missing_labels?.length) marks.push(`${o.missing_labels.length} label${o.missing_labels.length > 1 ? "s" : ""} not recorded`);
  const title = [`${KIND[o.kind].row} · seq ${o.seq ?? "unknown"}`, o.recorded_label && `recorded label: ${o.recorded_label}`,
    ld && `top recorded score: ${ld.labels.join(" = ")} ${ld.score}`, o.score_state && `score state ${o.score_state} (leader ${states[o.score_state]?.leading?.labels.join(" = ")})`, ...marks].filter(Boolean).join("\n");
  return (
    <button data-testid={`pos-${o.id}`} aria-pressed={on} title={title} onClick={() => onSelect(o.id)} className="be-hover"
      style={{ display: "flex", alignItems: "center", gap: 5, width: "100%", textAlign: "left", cursor: "pointer", padding: "3px 6px", borderRadius: 6, fontSize: 12, lineHeight: 1.35,
        border: on ? "2px solid #1D4ED8" : `1px ${o.kind === "agent_position" ? "solid" : "dashed"} ${v("line")}`, background: on ? v("primary-soft") : v("surface"), color: v("ink") }}>
      {lead && !ld?.tie ? <Swatch color={col[lead]} /> : <span aria-hidden="true" style={{ width: 9, height: 9, borderRadius: 2, border: "1px solid #94A3B8", flex: "none" }} />}
      <span style={{ ...mono, fontSize: 11.5, whiteSpace: "nowrap" }}>{main}</span>
      {marks.length > 0 && <span style={{ fontSize: 10.5, color: "var(--be-warning-ink)", whiteSpace: "nowrap" }}>{marks.join(" · ")}</span>}
    </button>
  );
}

function Scores({ o, ab, col, cands }) {
  if (!o.scores) return <p style={{ margin: 0, fontSize: 13, color: v("muted") }} data-testid="pos-no-scores"><Chip tone="muted">Unknown</Chip> {o.unknown.scores}</p>;
  const rows = Object.entries(o.scores).sort((a, b) => b[1] - a[1]);
  const max = Math.max(...rows.map(r => r[1]), 0.0001);
  return (
    <div data-testid="pos-scores">
      <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 12.5 }}>
        <tbody>
          {rows.map(([l, s]) => (
            <tr key={l}>
              <td style={{ padding: "2px 8px 2px 0", whiteSpace: "nowrap" }}><Swatch color={col[l]} /> <span style={{ marginLeft: 4 }}>{l}</span> <span style={{ ...mono, color: v("muted") }}>({ab[l]})</span></td>
              <td style={{ width: "50%", padding: "2px 8px" }}><div aria-hidden="true" style={{ height: 8, width: `${(s / max) * 100}%`, background: col[l], borderRadius: 2, opacity: 0.85 }} /></td>
              <td style={{ ...mono, textAlign: "right", padding: "2px 0" }}>{s}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {o.missing_labels?.length > 0 && <p data-testid="pos-missing-labels" style={{ margin: "6px 0 0", fontSize: 12.5, color: v("muted") }}>
        Not recorded here (UNKNOWN, not zero): {o.missing_labels.join(", ")}. {cands.length > rows.length && "The leading diagnosis is the top of the recorded labels only."}</p>}
    </div>
  );
}

function Field({ k, children, testid }) {
  return [<dt key={`${k}k`} style={{ color: v("muted") }}>{k}</dt>, <dd key={`${k}v`} data-testid={testid} style={{ margin: 0, minWidth: 0, wordBreak: "break-word" }}>{children}</dd>];
}

function Inspector({ b, P, o, ab, col, agents, onSelect, onShowInMatrix }) {
  if (!o) return <aside data-testid="pos-inspector" style={{ ...card, padding: 16, fontSize: 13, color: v("muted") }}>Select a position observation to see its recorded scores, source event and related council message.</aside>;
  const rel = o.related ?? {};
  const states = Object.fromEntries((P.score_states ?? []).map(s => [s.id, s]));
  const same = P.observations.filter(x => x.kind === o.kind && (o.kind !== "agent_position" || x.holder.agent === o.holder.agent));
  const i = same.findIndex(x => x.id === o.id);
  const colBtn = (c, label) => <button key={c} className="be-hover" data-testid={`pos-goto-${c}`} style={{ ...linkBtn, ...mono, fontSize: 12.5 }} onClick={() => onShowInMatrix(c)} title="Show this column in the interaction matrix">{label ?? c}</button>;
  const holder = o.kind === "agent_position" ? who(agents, o.holder.agent) : o.kind === "joint_ranking" ? "the council (no single agent)" : "the framework (no agent)";
  const msgEv = rel.evidence ? b.evidence[rel.evidence] : null;
  return (
    <aside aria-label="Selected position observation" data-testid="pos-inspector" style={{ ...card, padding: "16px 18px", display: "flex", flexDirection: "column", gap: 12, minWidth: 0 }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
        <span style={eyebrow}>{KIND[o.kind].row}</span>
        <Chip tone={KIND[o.kind].tone}>framework-computed · not a belief</Chip>
        <OriginTag origin={o.origin} />
        <span style={{ marginLeft: "auto", display: "inline-flex", gap: 8 }}>
          <button style={linkBtn} disabled={i <= 0} onClick={() => onSelect(same[i - 1].id)} data-testid="pos-prev">← previous</button>
          <button style={linkBtn} disabled={i >= same.length - 1} onClick={() => onSelect(same[i + 1].id)} data-testid="pos-next">next →</button>
        </span>
      </div>
      <div style={{ fontSize: 14, fontWeight: 700 }} data-testid="pos-title">
        {holder} · {P.segments.find(s => s.id === o.segment)?.label} · seq {o.seq ?? "unknown"}{o.draft ? " · draft" : ""}
      </div>
      <p style={{ margin: 0, fontSize: 12.5, color: v("muted") }}>{i + 1} of {same.length} {KIND[o.kind].short} records{o.kind === "agent_position" ? " for this agent" : ""}. Stepping through them shows recorded values in order; it does not show an agent changing its mind.</p>
      <Scores o={o} ab={ab} col={col} cands={P.candidates} />
      <dl style={{ display: "grid", gridTemplateColumns: "max-content minmax(0,1fr)", gap: "4px 12px", fontSize: 12.5, margin: 0 }}>
        <Field k="Leading (computed)" testid="pos-leading">{o.leading ? <>{o.leading.labels.join(" = ")} {o.leading.tie ? <Chip tone="warning">exact tie</Chip> : <span style={{ color: v("muted") }}>margin {o.leading.margin ?? "—"} (values as recorded)</span>}</> : <span style={{ color: v("muted") }}>none: no scores recorded</span>}</Field>
        <Field k="Recorded label">{o.recorded_label ?? <span style={{ color: v("muted") }}>none recorded</span>}{o.recorded_label && o.leading && !o.leading.labels.includes(o.recorded_label) && <Chip tone="warning" style={{ marginLeft: 6 }}>differs from top score</Chip>}</Field>
        <Field k="Confidence" testid="pos-confidence">{o.confidence != null ? <><span style={mono}>{o.confidence}</span> <span style={{ color: v("muted") }}>({o.confidence_field})</span></> : <><Chip tone="muted">Unknown</Chip> <span style={{ color: v("muted") }}>{o.unknown.confidence}</span></>}</Field>
        <Field k="Round / phase">{o.round != null ? `round ${o.round}` : <span style={{ color: v("muted") }}>{o.unknown.round}</span>}{o.phase ? ` · ${o.phase}` : ""}{o.stage ? ` · stage ${o.stage}` : ""}</Field>
        <Field k="Seq">{o.seq ?? "unknown"} <span style={{ color: v("muted") }}>({o.seq_basis})</span></Field>
        <Field k="Values at" testid="pos-locator"><span style={mono}>{o.locator}</span></Field>
        <Field k="Source event" testid="pos-event">{o.event ? <><span style={mono}>{o.event.type ? `${o.event.type} ` : ""}{o.event.locator}</span> <span style={{ color: v("muted") }}>· {o.event_join} · {o.event.event_id}</span></> : <><Chip tone="muted">Unknown</Chip> <span style={{ color: v("muted") }}>{o.unknown.event ?? "no event joined"}</span></>}</Field>
        {o.kind === "agent_position" && <>
          <Field k="Previous label">{o.old_label ?? <span style={{ color: v("muted") }}>none recorded</span>}</Field>
          <Field k="moved_by (recorded)">{o.moved_by.length ? o.moved_by.map(a => who(agents, a)).join(", ") : <span style={{ color: v("muted") }}>empty</span>}</Field>
          {o.method && <Field k="Method (recorded)">{o.method}</Field>}
          <Field k="Message payload"><span style={mono}>{o.message_payload.locator}</span> {o.message_payload.same_scores && o.message_payload.same_label ? <Chip tone="success">same values</Chip> : <Chip tone="danger">values differ</Chip>}</Field>
        </>}
        {o.kind === "joint_ranking" && <>
          <Field k="Converged / dissent">{String(o.converged)} · {o.dissent.length ? o.dissent.map(a => who(agents, a)).join(", ") : "no dissent recorded"}</Field>
          <Field k="Also recorded at" testid="pos-also">{o.also_recorded_at.length ? o.also_recorded_at.map(e => `${e.type} ${e.locator}`).join("; ") : "—"} <span style={{ color: v("muted") }}>({o.also_rule})</span></Field>
          {o.member_positions && <Field k="Agent scores in the message">{Object.entries(o.member_positions.values).map(([a, s]) => <div key={a}>{who(agents, a)}: <span style={mono}>{Object.entries(s).map(([l, x]) => `${ab[l] ?? l} ${x}`).join(", ")}</span></div>)}<span style={{ color: v("muted") }}>{o.member_positions.note}</span></Field>}
        </>}
        {o.kind === "hypothesis_scores" && <>
          <Field k="Record" testid="pos-basis">{o.basis === "event" ? `scoring event (${o.part}${o.source ? `, source ${o.source}` : ""})` : `${o.basis === "execution_input" ? "score list given to" : "score list returned by"} execution ${o.holder.recorded_on_execution} (run for ${who(agents, o.holder.execution_agent)})`}</Field>
          <Field k="Score state" testid="pos-state">{o.score_state ? <>{o.score_state} · first recorded at seq {states[o.score_state].first_seq} ({states[o.score_state].observations.length} records)</> : o.score_state_ambiguous ? `ambiguous: matches ${o.score_state_ambiguous.join(", ")}` : "—"}</Field>
          {o.execution_finding && <Field k="Execution's recorded finding">{o.execution_finding.label ?? "none"} · confidence {o.execution_finding.confidence ?? "none"} <span style={{ color: v("muted") }}>(the execution record, not these scores)</span></Field>}
        </>}
        {o.kind === "final_decision" && <Field k="Review decision">{o.review_decision}</Field>}
      </dl>
      <div data-testid="pos-related" style={{ border: `1px solid ${v("line")}`, borderRadius: 8, padding: "10px 12px", fontSize: 13, lineHeight: 1.55 }}>
        <div style={{ ...eyebrow, marginBottom: 4 }}>Related council interaction · joined by {rel.join}</div>
        {rel.message && <div>Message <b style={mono}>{rel.message}</b>{rel.found ? <> {rel.type} from {who(agents, rel.sender)} ({rel.text_mechanism === "llm_voice" ? "LLM-voiced text" : "code-built text"})</> : " (not among recorded messages)"}</div>}
        {rel.execution && <div>Execution <b style={mono}>{rel.execution}</b> of {who(agents, rel.agent)}</div>}
        <div>Grid column: {rel.columns?.length ? rel.columns.map(c => colBtn(c)) : <span style={{ color: v("muted") }}>none</span>} <span style={{ color: v("muted") }}>({rel.column_rule ?? rel.join})</span></div>
        {rel.received_in && <div data-testid="pos-received">Message text recorded in the model input of: {rel.received_in.length ? rel.received_in.map((c, k) => <span key={c}>{k ? ", " : ""}{colBtn(c)}</span>) : <span style={{ color: v("muted") }}>no recorded delivery</span>}{rel.code_access ? ` · ${rel.code_access} code-only reads` : ""}</div>}
        {rel.received_in && <p style={{ margin: "4px 0 0", fontSize: 12, color: v("muted") }}>Delivery is of the message text. Whether the score payload itself reached a model input is not established here.</p>}
        {msgEv && <details style={{ marginTop: 6 }}><summary style={{ cursor: "pointer", fontSize: 12.5 }}>Message text</summary><Excerpt excerpt={msgEv.excerpt} maxHeight={160} /></details>}
        {o.kind === "final_decision" && b.evidence[o.evidence] && <details style={{ marginTop: 6 }}><summary style={{ cursor: "pointer", fontSize: 12.5 }}>Final diagnosis text</summary><Excerpt excerpt={b.evidence[o.evidence].excerpt} maxHeight={120} /></details>}
      </div>
    </aside>
  );
}

export default function PositionsPanel({ b, narrow, onShowInMatrix, focus }) {
  const P = b.positions;
  const [sel, setSel] = useState(() => (focus && P?.observations.some(o => o.id === focus) ? focus : null) ?? P?.observations.find(o => o.kind === "agent_position")?.id ?? P?.observations[0]?.id ?? null);
  const derived = useMemo(() => {
    if (!P) return null;
    const ab = abbreviations(P.candidates);
    const col = Object.fromEntries(P.candidates.map((c, i) => [c, PALETTE[i % PALETTE.length]]));
    const agents = Object.fromEntries((b.matrix?.rows ?? b.skeleton?.agents ?? []).map(r => [r.id, r.label]));
    const rows = [...P.agents.map(a => ({ id: `agent:${a}`, label: who(agents, a), sub: KIND.agent_position.row, test: o => o.kind === "agent_position" && o.holder.agent === a })),
      ...["joint_ranking", "hypothesis_scores", "final_decision"].filter(k => P.observations.some(o => o.kind === k))
        .map(k => ({ id: k, label: KIND[k].row, sub: k === "joint_ranking" ? "council · no single agent" : "framework · no agent", test: o => o.kind === k }))];
    const cell = {};
    for (const o of P.observations) for (const r of rows) if (r.test(o)) (cell[`${r.id}|${o.segment}`] ||= []).push(o);
    return { ab, col, agents, rows, cell, states: Object.fromEntries(P.score_states.map(s => [s.id, s])) };
  }, [P, b]);
  if (!P) return <Empty testid="positions-empty">No framework-computed positions are recorded in this trace bundle.</Empty>;
  const { ab, col, agents, rows, cell, states } = derived;
  const o = P.observations.find(x => x.id === sel) ?? null;
  const SEG_W = 104;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }} data-testid="positions-panel">
      <section style={{ ...card, padding: "12px 16px", borderColor: "#FDE68A", background: "#FFFBEB" }} aria-labelledby="pos-label">
        <h2 id="pos-label" data-testid="positions-label" style={{ margin: 0, fontSize: 16, fontWeight: 750, color: "#78350F" }}>{P.label}</h2>
        <p style={{ margin: "4px 0 0", fontSize: 13, lineHeight: 1.5, color: "#78350F" }}>
          These are scores the council code computed and recorded. They are not what any agent expressed, so they are kept apart from Claims &amp; evidence and are never shown as belief states.
          {" "}{P.counts.agent_position} agent positions · {P.counts.joint_ranking} joint rankings · {P.counts.hypothesis_scores} overall hypothesis-score records in {P.score_states.length} score states · {P.counts.final_decision} final decision.
        </p>
        <details style={{ marginTop: 6 }}><summary style={{ cursor: "pointer", fontSize: 12.5, color: "#78350F" }}>Display rules</summary>
          <ul style={{ margin: "4px 0 0", paddingLeft: 18, fontSize: 12.5, color: "#78350F" }}>{P.rules.map((r, i) => <li key={i}>{r}</li>)}</ul></details>
      </section>

      <section style={{ ...card, padding: "12px 16px" }} aria-label="Overall hypothesis score states" data-testid="pos-states">
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: 8, marginBottom: 8 }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700 }}>Overall hypothesis score states</h3>
          <span style={{ fontSize: 12.5, color: v("muted") }}>shared framework scores, numbered in order of first record. The changes between states are not recorded as events and belong to no agent.</span>
        </div>
        <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexWrap: "wrap", gap: 8, alignItems: "stretch" }}>
          {P.score_states.map((s, k) => (
            <li key={s.id} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {k > 0 && <span aria-hidden="true" style={{ color: v("muted") }}>→</span>}
              <button data-testid={`pos-state-${s.id}`} className="be-hover" onClick={() => setSel(s.observations[0])} title={s.first_locator}
                style={{ textAlign: "left", cursor: "pointer", border: `1px solid ${o?.score_state === s.id ? "#1D4ED8" : v("line")}`, borderRadius: 8, background: v("surface"), padding: "6px 10px", fontSize: 12.5, lineHeight: 1.4 }}>
                <div style={{ fontWeight: 700 }}>{s.id} <span style={{ fontWeight: 500, color: v("muted") }}>· seq {s.first_seq} · {s.observations.length} record{s.observations.length > 1 ? "s" : ""}</span></div>
                <div style={{ display: "flex", alignItems: "center", gap: 5 }}>{!s.leading.tie && <Swatch color={col[s.leading.labels[0]]} />}<b>{s.leading.labels.join(" = ")}</b> <span style={mono}>{s.leading.score}</span>
                  <span style={{ color: v("muted") }}>{s.leading.tie ? "tie" : `+${s.leading.margin}`}</span></div>
              </button>
            </li>
          ))}
        </ol>
      </section>

      <div style={{ display: "grid", gridTemplateColumns: narrow ? "minmax(0,1fr)" : "minmax(0, 1.55fr) minmax(360px, 1fr)", gap: 14, alignItems: "start" }}>
        <section style={{ ...card, overflow: "hidden" }} aria-label="Positions by holder and round">
          <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 12px", padding: "10px 14px", borderBottom: `1px solid ${v("line")}`, fontSize: 12 }} data-testid="pos-legend">
            {P.candidates.map(c => <span key={c} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}><Swatch color={col[c]} />{ab[c]} = {c}</span>)}
            <span style={{ color: v("muted") }}>· solid border: one agent's position · dashed: council or framework</span>
          </div>
          <div style={{ overflow: "auto", maxHeight: narrow ? 520 : 560 }} data-testid="pos-table" tabIndex={0} aria-label="Computed positions table, scrollable">
            <table style={{ borderCollapse: "separate", borderSpacing: 0, fontSize: 12 }}>
              <thead>
                <tr>
                  <th scope="col" style={{ position: "sticky", left: 0, top: 0, zIndex: 3, background: v("canvas"), minWidth: 150, textAlign: "left", padding: "6px 10px", borderBottom: `1px solid ${v("line")}`, borderRight: `1px solid ${v("line")}` }}>Holder</th>
                  {P.segments.map(s => (
                    <th key={s.id} scope="col" title={`seq ${s.first_seq}–${s.last_seq}`} style={{ position: "sticky", top: 0, zIndex: 2, background: s.round != null ? v("canvas") : "#F8FAFC", minWidth: SEG_W, maxWidth: SEG_W + 30, textAlign: "left", verticalAlign: "bottom", padding: "6px 6px", fontWeight: 650, borderBottom: `1px solid ${v("line")}`, fontStyle: s.round != null ? "normal" : "italic" }}>
                      <div style={{ lineHeight: 1.25 }}>{s.label}</div><div style={{ ...mono, fontSize: 10.5, color: v("muted"), fontWeight: 400 }}>seq {s.first_seq}{s.last_seq !== s.first_seq ? `–${s.last_seq}` : ""}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r, ri) => (
                  <tr key={r.id} data-testid={`pos-row-${r.id}`}>
                    <th scope="row" style={{ position: "sticky", left: 0, zIndex: 1, background: v("surface"), textAlign: "left", padding: "6px 10px", verticalAlign: "top", borderRight: `1px solid ${v("line")}`, borderTop: ri && rows[ri - 1].id.startsWith("agent:") && !r.id.startsWith("agent:") ? "2px solid #94A3B8" : `1px solid ${v("soft")}` }}>
                      <div style={{ fontWeight: 650 }}>{r.label}</div><div style={{ fontSize: 11, color: v("muted"), fontWeight: 400 }}>{r.sub}</div>
                    </th>
                    {P.segments.map(s => (
                      <td key={s.id} style={{ verticalAlign: "top", padding: 3, borderTop: ri && rows[ri - 1].id.startsWith("agent:") && !r.id.startsWith("agent:") ? "2px solid #94A3B8" : `1px solid ${v("soft")}`, background: s.round != null ? "transparent" : "#FAFAFB" }}>
                        <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                          {(cell[`${r.id}|${s.id}`] ?? []).map(x => <ObsChip key={x.id} o={x} on={x.id === sel} onSelect={setSel} ab={ab} col={col} states={states} />)}
                        </div>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{ margin: 0, padding: "8px 14px", fontSize: 12, color: v("muted"), borderTop: `1px solid ${v("line")}` }}>
            Columns are recorded rounds, else the recorded stage (italic), in seq order; a cell can hold several records. Order is observation order only and implies no causation.
          </p>
        </section>
        <Inspector b={b} P={P} o={o} ab={ab} col={col} agents={agents} onSelect={setSel} onShowInMatrix={onShowInMatrix} />
      </div>
    </div>
  );
}
