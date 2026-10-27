import { useEffect, useMemo, useRef, useState } from "react";
import { Disclosure, HATCH, IdButton, Json, KV, LAYER, LayerTag, Mono, Note, Section, Stat, T, eyebrow, panel } from "./ui.jsx";

// Agent × model-call matrix for any run listed in the manifest (scripts/demo/build_matrix.py builds and
// validates each run; contract agenttrace-matrix/0.2).  Rows are the agents the trace records; columns are
// model calls in observation order.  Nothing here derives a claim, state, disagreement or ordering
// relation, and no cell carries anything forward.  Each run file is loaded on demand and its sha256 is
// checked against the manifest before use.

const CONTRACT = "agenttrace-matrix/0.2";
// src/demo/data/ is local-only (gitignored): the manifest is loaded only if present, so a fresh clone still builds.
const MANIFEST = import.meta.glob("./data/matrices/index.json", { eager: true, import: "default" })["./data/matrices/index.json"];
const FILES = import.meta.glob("./data/matrices/*.matrix.json", { query: "?raw", import: "default" });
const RUNS = [...(MANIFEST?.runs ?? [])].sort((a, b) => b.agents - a.agents || b.model_calls - a.model_calls || a.run_id.localeCompare(b.run_id));

async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
}
async function loadRun(entry) {
  const loader = FILES[`./data/matrices/${entry.file}`];
  if (!loader) throw new Error(`${entry.file} is listed in the manifest but not present`);
  const text = await loader();
  if ((await sha256(text)) !== entry.sha256) throw new Error(`${entry.file} does not match its manifest sha256; rebuild it with build_matrix.py`);
  const m = JSON.parse(text);
  if (m.contract !== CONTRACT) throw new Error(`${entry.file} has contract ${m.contract}, expected ${CONTRACT}`);
  return m;
}

const fmt = n => n.toLocaleString("en-US");
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const plural = (n, one, many = `${one}s`) => `${fmt(n)} ${n === 1 ? one : many}`;
const CELL = { fill: "#d6e3fa", stroke: "#7f9fd9", glyph: "#1e3a8a" };
const LABEL_W = 192;
const MIN_COL = 28;
const MAX_COL = 36;
const AXIS_H = 46;
const short = s => (s && s.length > 26 ? `${s.slice(0, 25)}…` : s);

// Everything the view needs, derived once per loaded run from the validated matrix data.
export function derive(m) {
  const cols = m.columns;
  const colById = Object.fromEntries(cols.map(c => [c.id, c]));
  const hasUnresolved = cols.some(c => c.row === "$unresolved");
  const rows = [...m.rows.map(r => ({ id: r.id, name: r.agent_id, sub: [r.kind, r.name].filter(Boolean).join(" · "), agent: true })),
    ...(hasUnresolved ? [{ id: "$unresolved", name: "unresolved", sub: "origin not attributed", agent: false }] : [])];
  const rowName = id => (id === "$unresolved" ? "unresolved origin" : id.replace(/^agent:/, ""));
  const callIndex = {};
  for (const r of rows) cols.filter(c => c.row === r.id).forEach((c, i, arr) => { callIndex[c.id] = [i + 1, arr.length]; });
  const amb = Object.fromEntries(m.ambiguities.map(a => [a.field_path.match(/events\[(.+?)\]/)?.[1], a]));
  // Delegation edges: an item produced by one model call that first appears in another agent's input through the delegation_id join.
  const edges = [];
  for (const c of cols) {
    for (const [t] of c.first_delivered_here) {
      if (!c.delegation_input.includes(t)) continue;
      const src = colById[m.evidence[t]?.produced_by];
      if (src && !edges.some(e => e.from === src.id && e.to === c.id)) edges.push({ from: src.id, to: c.id });
    }
  }
  const received = new Set(edges.map(e => e.to));
  const fixtureCols = cols.filter(c => c.fixture_links.length);
  const overlapCols = cols.filter(c => c.overlaps_with.length);
  const maxIn = Math.max(0, ...cols.map(c => c.delivers.length));
  const key = [
    ...cols.filter(c => c.issued_delegations.length).map(c => ({ col: c, label: `Delegation by ${rowName(c.row)}` })),
    ...edges.map(e => ({ col: colById[e.to], label: `${rowName(colById[e.to].row)} receives task` })),
    ...cols.filter(c => c.row === "$unresolved").slice(0, 3).map(c => ({ col: c, label: "Unresolved origin" })),
    ...fixtureCols.filter(c => !received.has(c.id)).slice(0, 4).map(c => ({ col: c, label: "Fixture link" })),
    ...(cols.length ? [{ col: cols[cols.length - 1], label: "Last call" }] : []),
  ].filter((k, i, all) => all.findIndex(x => x.col.id === k.col.id) === i);
  return { cols, colById, rows, rowName, callIndex, amb, edges, received, fixtureCols, overlapCols, maxIn, key, hasUnresolved };
}

function findings(m, d) {
  const out = [];
  const err = m.run.error;
  if (m.run.status && m.run.status !== "ok") {
    out.push({ layer: "observed", text: `Run ended with status "${m.run.status}"${err ? `: ${[err.type, err.message].filter(Boolean).join(" — ")}` : ""} (last record: ${m.run.terminal_event.type}).` });
  }
  for (const e of d.edges) {
    const a = d.colById[e.from], b = d.colById[e.to];
    out.push({ layer: "structural", text: `${d.rowName(a.row)} delegated a task at seq ${a.order}; its description first reached ${d.rowName(b.row)}'s input at seq ${b.order}.`, col: b });
  }
  for (const c of d.cols.filter(c => c.issued_delegations.length && !d.edges.some(e => e.from === c.id))) {
    out.push({ layer: "structural", text: `${d.rowName(c.row)} issued a task delegation at seq ${c.order}; no receiving input was observed.`, col: c });
  }
  const unres = d.cols.filter(c => c.row === "$unresolved");
  if (unres.length) {
    const rules = [...new Set(unres.map(c => c.origin_rule))].join(", ");
    out.push({ layer: "unresolved", text: `${plural(unres.length, "model call")} ${unres.length === 1 ? "has" : "have"} an agent origin the trace does not establish (${rules}); nothing semantic is derived from ${unres.length === 1 ? "it" : "them"}.`, col: unres[0] });
  }
  if (m.telemetry.delivery === "absent") out.push({ layer: "observed", text: "Rendered model inputs were not captured, so no deliveries can be shown for this run." });
  if (d.overlapCols.length) out.push({ layer: "observed", text: `${plural(d.overlapCols.length, "model call")} overlap other model calls in observation order; overlap implies no precedence.` });
  if (m.fixture_links.length) out.push({ layer: "hand", text: `${m.fixture_links.length} of the deliveries are also recorded in a hand-grounded fixture.`, col: d.fixtureCols[0] });
  out.push({ layer: "observed", text: "No semantic claims were extracted, so no beliefs, agreement or disagreement are shown." });
  return out;
}

function glyphOf(c, d) {
  if (c.row === "$unresolved") return "?";
  if (c.issued_delegations.length) return "⇢";
  if (d.received.has(c.id)) return "D";
  if (c.fixture_links.length) return "◆";
  if (c.overlaps_with.length) return "∥";
  return "";
}

function describe(d, colId, rowId) {
  const c = d.colById[colId];
  if (!c) return "No model call selected.";
  const row = d.rowName(rowId);
  if (c.row !== rowId) return `${row} at seq ${c.order}: no observation. Nothing is carried forward.`;
  const [i, n] = d.callIndex[c.id] ?? [];
  const kind = c.row === "$unresolved" ? "model call with unresolved agent origin" : `model call ${i} of ${n}, no semantic claim extracted`;
  return `${row}, seq ${c.order}: ${kind}. ${c.row === "$unresolved" ? "" : `${c.delivers.length} items in its rendered input.`}`;
}

function useSize(ref) {
  const [size, setSize] = useState({ w: 900, h: 400 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(([e]) => setSize({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return size;
}

export function Matrix({ m, d, sel, onSelect, onActivate, layout }) {
  const outer = useRef(null);
  const scroller = useRef(null);
  const { w, h } = useSize(outer);
  const n = d.cols.length;
  const telemetry = m.telemetry.delivery === "present";
  const colW = clamp(Math.floor((w - LABEL_W - 4) / Math.max(n, 1)), MIN_COL, MAX_COL);
  const weights = d.rows.map(r => (r.agent ? 1 : 0.55));
  const totalW = weights.reduce((a, b) => a + b, 0);
  let laneH = 64, trackH = telemetry ? 120 : 44;
  if (layout.fixed) {
    const usable = Math.max(260, h - AXIS_H - 30);
    if (telemetry) trackH = clamp(usable * 0.3, 80, 200);
    laneH = clamp((usable - trackH - 30 - 8 * d.rows.length) / totalW, 34, 120);
  }
  const lanes = weights.map(x => Math.round(laneH * x));
  const laneY = [];
  lanes.reduce((y, hgt, i) => { laneY[i] = y; return y + hgt + 8; }, 10);
  const trackY = (laneY[lanes.length - 1] ?? 10) + (lanes[lanes.length - 1] ?? 0) + 20;
  const axisY = trackY + trackH + 8;
  const height = axisY + AXIS_H;
  const width = Math.max(n * colW, 1);
  const x = i => i * colW;
  const selIdx = d.cols.findIndex(c => c.id === sel?.col);
  const rowIdx = d.rows.findIndex(r => r.id === sel?.row);
  const idx = Object.fromEntries(d.cols.map((c, i) => [c.id, i]));
  const rowOf = Object.fromEntries(d.rows.map((r, i) => [r.id, i]));

  useEffect(() => { // keep the selected column visible inside the horizontally scrolling region
    const el = scroller.current;
    if (!el || selIdx < 0) return;
    const left = selIdx * colW, right = left + colW, margin = colW * 2;
    if (left < el.scrollLeft + margin || right > el.scrollLeft + el.clientWidth - margin) el.scrollLeft = Math.max(0, left - el.clientWidth / 2);
  }, [selIdx, colW]);

  if (!n) {
    return (
      <div data-testid="matrix-empty" style={{ padding: 24 }}>
        <p style={{ fontSize: 14, color: T.text, margin: 0 }}><b>No model calls were recorded in this trace.</b> The agents below appear in the record but made no observable model call.</p>
        <ul style={{ fontSize: 13, color: T.muted }}>{d.rows.map(r => <li key={r.id}><Mono>{r.name}</Mono> · {r.sub}</li>)}</ul>
      </div>
    );
  }

  const onKey = e => {
    const go = i => { const c = d.cols[clamp(i, 0, n - 1)]; onSelect({ col: c.id, row: c.row }); };
    const keys = {
      ArrowRight: () => go(selIdx + 1), ArrowLeft: () => go(selIdx - 1), Home: () => go(0), End: () => go(n - 1),
      PageDown: () => go(selIdx + 10), PageUp: () => go(selIdx - 10),
      ArrowDown: () => onSelect({ col: sel.col, row: d.rows[clamp(rowIdx + 1, 0, d.rows.length - 1)].id }),
      ArrowUp: () => onSelect({ col: sel.col, row: d.rows[clamp(rowIdx - 1, 0, d.rows.length - 1)].id }),
      Enter: onActivate, " ": onActivate,
    };
    if (keys[e.key]) { e.preventDefault(); keys[e.key](); }
  };

  return (
    <div ref={outer} style={{ flex: layout.fixed ? 1 : "none", minHeight: 0, overflowY: layout.fixed ? "auto" : "visible", overflowX: "hidden" }}>
      <div data-testid="matrix-grid" role="grid" tabIndex={0} onKeyDown={onKey} aria-describedby="matrix-help matrix-live"
        aria-label={`Agent by model-call matrix, ${d.rows.length} rows, ${n} model calls`} style={{ display: "flex" }}>
        <svg width={LABEL_W} height={height} style={{ flex: "none", display: "block", fontFamily: T.sans, background: T.panel, borderRight: `1px solid ${T.line}` }} aria-hidden="true">
          {d.rows.map((r, ri) => {
            const mid = laneY[ri] + lanes[ri] / 2;
            const big = lanes[ri] >= 44;
            const count = d.cols.filter(c => c.row === r.id).length;
            return (
              <g key={r.id}>
                <title>{`${r.name} · ${r.sub}`}</title>
                {ri === rowIdx && <rect x={0} y={laneY[ri]} width={4} height={lanes[ri]} fill={T.ink} />}
                <text x={14} y={mid - (big ? 9 : 0)} fontFamily={T.mono} fontSize={14} fontWeight={700} fill={T.ink}>{short(r.name)}</text>
                {big && <text x={14} y={mid + 7} fontSize={12} fill={T.faint}>{short(r.sub)}</text>}
                <text x={14} y={mid + (big ? 23 : 15)} fontSize={12} fill={T.muted}>{plural(count, "call")}</text>
              </g>
            );
          })}
          <text x={14} y={trackY + 16} fontSize={13} fontWeight={700} fill={T.ink}>Rendered input</text>
          {telemetry ? (
            <>
              <text x={14} y={trackY + 33} fontSize={12} fill={T.faint}>items delivered (max {d.maxIn})</text>
              <rect x={14} y={trackY + 44} width={11} height={11} fill="#b9cdf3" stroke="#7f9fd9" /><text x={31} y={trackY + 54} fontSize={12} fill={T.muted}>present</text>
              <rect x={14} y={trackY + 62} width={11} height={11} fill={LAYER.structural.color} /><text x={31} y={trackY + 72} fontSize={12} fill={T.muted}>first here</text>
            </>
          ) : <text x={14} y={trackY + 33} fontSize={12} fill={T.faint}>not captured</text>}
          <text x={14} y={axisY + 16} fontSize={12} fill={T.faint}>first raw seq →</text>
        </svg>

        <div ref={scroller} data-testid="matrix" style={{ flex: 1, minWidth: 0, overflowX: "auto", overflowY: "hidden" }}>
          <svg width={width} height={height} style={{ display: "block", fontFamily: T.sans }} aria-hidden="true">
            <defs>
              <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="6" height="6" fill="#f6f7f9" /><rect width="3" height="6" fill="#c9d0da" />
              </pattern>
              <marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
                <path d="M0,0 L8,4 L0,8 z" fill={LAYER.structural.color} />
              </marker>
            </defs>
            {selIdx >= 0 && <rect x={x(selIdx)} y={2} width={colW} height={height - 4} fill="rgba(11,18,32,0.07)" rx={3} />}
            {d.rows.map((r, ri) => (
              <g key={r.id}>
                <line x1={0} x2={width} y1={laneY[ri] + lanes[ri] / 2} y2={laneY[ri] + lanes[ri] / 2} stroke={T.soft} />
                {d.cols.map((c, i) => {
                  const here = c.row === r.id;
                  const isSel = sel?.col === c.id && sel?.row === r.id;
                  const kind = !here ? "empty" : r.id === "$unresolved" ? "unresolved" : "observed";
                  const glyph = here ? glyphOf(c, d) : "";
                  return (
                    <g key={c.id} data-testid={`cell-${r.id}-${c.id}`} onClick={() => onSelect({ col: c.id, row: r.id })} style={{ cursor: "pointer" }}>
                      <title>{describe(d, c.id, r.id)}</title>
                      <rect x={x(i) + 2} y={laneY[ri] + 3} width={colW - 4} height={lanes[ri] - 6} rx={3}
                        fill={kind === "empty" ? (isSel ? "#fff" : "transparent") : kind === "unresolved" ? "url(#hatch)" : CELL.fill}
                        stroke={kind === "empty" ? (isSel ? T.focus : "none") : kind === "unresolved" ? "#6b7486" : CELL.stroke} strokeDasharray={kind === "empty" && isSel ? "4 3" : "none"} />
                      {isSel && <rect x={x(i) + 0.5} y={laneY[ri] + 1.5} width={colW - 1} height={lanes[ri] - 3} rx={4} fill="none" stroke={T.focus} strokeWidth={3} />}
                      {glyph && <text x={x(i) + colW / 2} y={laneY[ri] + lanes[ri] / 2 + 5} textAnchor="middle" fontSize={15} fontWeight={700}
                        fill={glyph === "◆" ? LAYER.hand.color : kind === "unresolved" ? T.text : CELL.glyph}>{glyph}</text>}
                    </g>
                  );
                })}
              </g>
            ))}
            {d.edges.map(e => {
              const a = d.colById[e.from], b = d.colById[e.to];
              const ra = rowOf[a.row], rb = rowOf[b.row];
              if (ra == null || rb == null) return null;
              const x1 = x(idx[a.id]) + colW / 2, x2 = x(idx[b.id]) + colW / 2;
              const down = rb > ra;
              const y1 = down ? laneY[ra] + lanes[ra] - 3 : laneY[ra] + 3, y2 = down ? laneY[rb] + 4 : laneY[rb] + lanes[rb] - 4;
              const bend = down ? 16 : -16;
              return <path key={`${e.from}-${e.to}`} data-testid="delegation-link" d={`M${x1},${y1} C${x1},${y1 + bend} ${x2},${y2 - bend} ${x2},${y2}`} fill="none"
                stroke={LAYER.structural.color} strokeWidth={2} strokeDasharray="4 3" markerEnd="url(#arrow)" />;
            })}
            <line x1={0} x2={width} y1={trackY + trackH} y2={trackY + trackH} stroke={T.line} />
            {telemetry ? d.cols.map((c, i) => {
              if (c.row === "$unresolved") return <text key={c.id} x={x(i) + colW / 2} y={trackY + trackH - 6} fontSize={11} fill={T.faint} textAnchor="middle">n/a</text>;
              const tot = c.delivers.length, first = c.first_delivered_here.length;
              const scale = d.maxIn ? (trackH - 6) / d.maxIn : 0;
              return (
                <g key={c.id} onClick={() => onSelect({ col: c.id, row: c.row })} style={{ cursor: "pointer" }}>
                  <rect x={x(i) + 4} y={trackY + trackH - tot * scale} width={colW - 8} height={tot * scale} fill="#b9cdf3" stroke="#7f9fd9" strokeWidth={0.75} />
                  <rect x={x(i) + 4} y={trackY + trackH - first * scale} width={colW - 8} height={first * scale} fill={LAYER.structural.color} />
                </g>
              );
            }) : <text x={8} y={trackY + 26} fontSize={12.5} fill={T.muted}>Rendered model inputs were not captured in this trace, so no deliveries can be shown.</text>}
            {d.cols.map((c, i) => (
              <text key={c.id} transform={`translate(${x(i) + colW / 2 + 4},${axisY + 2}) rotate(-90)`} fontSize={11.5} fill={sel?.col === c.id ? T.ink : T.faint}
                fontWeight={sel?.col === c.id ? 800 : 400} fontFamily={T.mono} textAnchor="end">{c.order}</text>
            ))}
          </svg>
        </div>
      </div>
      <div id="matrix-live" aria-live="polite" style={srOnly}>{sel ? describe(d, sel.col, sel.row) : ""}</div>
    </div>
  );
}
const srOnly = { position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)", whiteSpace: "nowrap" };

function itemLabel(m, id) {
  const x = m.evidence[id];
  if (!x) return id;
  const prod = m.other_events[x.produced_by];
  const tool = x.raw_ref.tool ?? prod?.origin?.replace(/^tool:/, "");
  switch (x.kind) {
    case "question": return "The task question";
    case "tool_argument": return `“${x.raw_ref.argument}” argument of a ${x.raw_ref.tool} call`;
    case "eviction_substitute": return "Framework notice replacing a large tool result";
    default: return `Result of ${tool ?? "a tool"}`;
  }
}

function EvidenceItem({ m, id, locator, onOpen }) {
  const x = m.evidence[id];
  if (!x) return <div style={{ padding: "4px 0" }}><Mono>{id}</Mono></div>;
  const src = typeof x.source === "string" ? x.source : `unresolved (${x.source.candidates.join(" or ")})`;
  return (
    <details style={{ borderTop: `1px solid ${T.soft}`, padding: "6px 0" }}>
      <summary style={{ cursor: "pointer", fontSize: 13 }}>{itemLabel(m, id)} <span style={{ color: T.faint }}>· from {src}</span></summary>
      <div style={{ padding: "8px 0 2px 14px" }}>
        {x.excerpt != null && <pre style={{ fontFamily: T.mono, fontSize: 12, lineHeight: 1.5, whiteSpace: "pre-wrap", wordBreak: "break-word", background: T.bg,
          border: `1px solid ${T.line}`, borderRadius: 5, padding: "6px 8px", margin: 0 }}>{x.excerpt}{x.excerpt_complete ? "" : " …"}</pre>}
        <p style={{ fontSize: 12, color: T.faint, margin: "4px 0 0" }}>{x.excerpt_complete ? "Complete value." : "Excerpt (first 300 characters)."}</p>
        <Disclosure label="Technical details">
          <KV rows={[["id", <Mono key="i">{id}</Mono>],
            ["produced by", x.produced_by ? <IdButton id={x.produced_by} onClick={() => onOpen(x.produced_by)} /> : "external (no producing event)"],
            locator && ["in this input", <Mono key="l" muted>{locator}</Mono>], ["raw locator", <Mono key="r" muted>{x.raw_ref.locator}</Mono>],
            x.raw_ref.sha256 && ["sha256", <Mono key="s" muted>{x.raw_ref.sha256}</Mono>], x.raw_ref.size != null && ["size", `${fmt(x.raw_ref.size)} chars`]]} />
        </Disclosure>
      </div>
    </details>
  );
}

function CallInspector({ m, d, col, onOpen }) {
  const amb = d.amb[col.id];
  const unresolved = col.row === "$unresolved";
  const [i, n] = d.callIndex[col.id] ?? [];
  const edgeIn = d.edges.filter(e => e.to === col.id).map(e => d.colById[e.from]);
  const edgeOut = d.edges.filter(e => e.from === col.id).map(e => d.colById[e.to]);
  const tools = col.issued_tool_events.map(t => m.other_events[t]?.origin.replace(/^tool:/, "").replace(/^framework:/, "framework ")).filter(Boolean);
  return (
    <>
      <Section title={unresolved ? "Model call with unresolved origin" : `Model call ${i} of ${n} by ${d.rowName(col.row)}`} layer={unresolved ? "unresolved" : "observed"} testid="insp-call">
        {unresolved
          ? <Note tone="caution" testid="insp-unresolved">The trace does not establish which agent made this call. Candidates: {amb?.candidates.map(c => c.replace(/^agent:/, "")).join(", ")}. Nothing semantic is derived from it.</Note>
          : <p style={{ fontSize: 13, margin: 0, lineHeight: 1.5 }}>Observed at seq {col.order}. No semantic claim was extracted, so it carries no belief state.</p>}
        {col.overlaps_with.length > 0 && <Note>Overlaps in observation order with {col.overlaps_with.length} other model {col.overlaps_with.length === 1 ? "call" : "calls"}; overlap implies no precedence.</Note>}
      </Section>
      {(edgeIn.length > 0 || edgeOut.length > 0 || col.issued_delegations.length > 0) && (
        <Section title="Delegation" layer="structural">
          {edgeIn.map(a => <p key={a.id} style={pText}>Received a task description produced by {d.rowName(a.row)} at seq {a.order} (joined by delegation id).</p>)}
          {edgeOut.map(b => <p key={b.id} style={pText}>Delegated a task; the description first reached {d.rowName(b.row)} at seq {b.order}.</p>)}
          {col.issued_delegations.length > 0 && !edgeOut.length && <p style={pText}>Issued a task delegation; no receiving input was observed.</p>}
          {col.issued_delegations.map(id => <EvidenceItem key={id} m={m} id={id} onOpen={onOpen} />)}
        </Section>
      )}
      {!unresolved && m.telemetry.delivery === "present" && (
        <Section title="What it received" layer="structural" testid="insp-input">
          <p style={pText}>{plural(col.delivers.length, "item")} in its rendered input · {col.first_delivered_here.length} new to this agent.</p>
          {col.first_delivered_here.map(([t, loc]) => <EvidenceItem key={t} m={m} id={t} locator={loc} onOpen={onOpen} />)}
          <Note>Presence in the rendered input does not show the item was used.</Note>
        </Section>
      )}
      {!unresolved && m.telemetry.delivery !== "present" && <Section title="What it received"><p style={pText}>Not captured in this trace.</p></Section>}
      {tools.length > 0 && (
        <Section title="What it issued" layer="observed">
          <p style={pText}>{tools.length === 1 ? "One tool call" : `${tools.length} tool calls`}: {[...new Set(tools)].join(", ")}.</p>
        </Section>
      )}
      {col.fixture_links.length > 0 && (
        <Section title="Hand-grounded fixture" layer="hand" testid="insp-fixture">
          <p style={pText}>{col.fixture_links.length === 1 ? "One delivery here is" : `${col.fixture_links.length} deliveries here are`} also recorded in the hand-grounded fixture ({col.fixture_links.join(", ")}).</p>
        </Section>
      )}
      <Section title="Technical details">
        <Disclosure label="Identifiers, locators and origin rule" testid="tech">
          <KV rows={[["event id", <Mono key="i">{col.id}</Mono>], ["raw seq", `${col.start_seq}–${col.end_seq}`], ["raw agent_id", <Mono key="a">{String(col.raw_agent_id)}</Mono>],
            ["origin basis", `${col.origin_label ?? ""} ${col.origin_rule ?? ""}`], ["input", <Mono key="in" muted>{col.input_locator || "not captured"}</Mono>],
            ["output", <Mono key="o" muted>{col.output_locator}</Mono>], unresolved && amb && ["reason", amb.reason],
            col.issued_tool_events.length > 0 && ["tool events", <span key="t" style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>{col.issued_tool_events.map(t => <IdButton key={t} id={t} onClick={() => onOpen(t)} />)}</span>]]} />
        </Disclosure>
        <Disclosure label="Raw column JSON" testid="raw-json"><Json value={col} /></Disclosure>
      </Section>
    </>
  );
}
const pText = { fontSize: 13, margin: "0 0 6px", lineHeight: 1.5 };

function EventInspector({ m, d, id, onBack, onCall }) {
  const e = m.other_events[id];
  const seq = Number(e?.raw_ref.issued_at?.match(/seq=(\d+)/)?.[1]);
  const issuer = d.cols.find(c => c.end_seq === seq);
  return (
    <>
      <Section title={id.startsWith("ev:evict") ? "Framework eviction" : `Tool call: ${e?.origin.replace(/^tool:/, "")}`} layer="observed">
        {issuer && <p style={pText}>Issued by {d.rowName(issuer.row)} at seq {issuer.order}. <IdButton id={issuer.id} label={`Go to model call ${issuer.id}`} onClick={() => onCall(issuer)} /></p>}
        <Disclosure label="Technical details"><KV rows={[["id", <Mono key="i">{id}</Mono>], ["raw seq", e?.raw_ref.seq.join(", ")], e?.raw_ref.tool_call_id && ["tool_call_id", <Mono key="t" muted>{e.raw_ref.tool_call_id}</Mono>]]} /><Json value={e} /></Disclosure>
      </Section>
      <div style={{ padding: "8px 16px 12px" }}><button onClick={onBack} style={linkBtn}>← Back to selected cell</button></div>
    </>
  );
}

const linkBtn = { fontSize: 13, color: LAYER.structural.color, background: "none", border: "none", cursor: "pointer", padding: 2, textDecoration: "underline" };
const sw = { display: "inline-block", width: 13, height: 13, borderRadius: 2 };
function Legend({ swatch, children }) {
  return <span role="listitem" style={{ display: "inline-flex", alignItems: "center", gap: 6, whiteSpace: "nowrap" }}><span aria-hidden="true" style={{ display: "inline-flex" }}>{swatch}</span>{children}</span>;
}

function RunView({ m, layout }) {
  const d = useMemo(() => derive(m), [m]);
  const first = d.key[0]?.col ?? d.cols[0];
  const [sel, setSel] = useState(first ? { col: first.id, row: first.row } : null);
  const [event, setEvent] = useState(null);
  const inspector = useRef(null);
  const col = sel ? d.colById[sel.col] : null;
  const onCell = s => { setSel(s); setEvent(null); };
  const onOpen = id => { const c = d.colById[id]; if (c) onCell({ col: c.id, row: c.row }); else setEvent(id); };
  const toInspector = () => { inspector.current?.focus(); inspector.current?.scrollIntoView({ block: "nearest" }); };
  const cellHere = col && col.row === sel.row;
  const fixed = layout.fixed;
  const facts = findings(m, d);
  const agentsLabel = m.rows.map(r => r.agent_id).join(", ") || "none";

  return (
    <div data-testid="matrix-view" data-run={m.run.run_id} style={{ display: "grid", gridTemplateColumns: layout.narrow ? "minmax(0, 1fr)" : `minmax(0, 1fr) ${fixed ? "clamp(340px, 26vw, 440px)" : "minmax(300px, 34%)"}`,
      gap: 12, padding: "0 12px 12px", height: fixed ? "100%" : "auto", boxSizing: "border-box", alignItems: "start" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 12, minHeight: 0, minWidth: 0, height: fixed ? "100%" : "auto" }}>
        <section aria-label="Run summary" style={{ ...panel, padding: "12px 16px" }} data-testid="matrix-summary">
          <div style={{ display: "flex", flexWrap: "wrap" }}>
            <Stat label="Agents" value={m.rows.length} note={agentsLabel} />
            <Stat label="Model calls" value={fmt(d.cols.length)} />
            {d.hasUnresolved && <Stat label="Unresolved origin" value={fmt(m.counts.per_row.$unresolved)} layer="unresolved" />}
            <Stat label="Deliveries" value={m.telemetry.delivery === "present" ? fmt(m.counts.delivers) : "—"} layer="structural" note={m.telemetry.delivery === "present" ? "" : "not captured"} />
            <Stat label="Semantic claims" value="0" note="not extracted" />
            <Stat label="Status" value={m.run.status ?? "unknown"} />
          </div>
          {/* On shorter desktop screens the findings start collapsed so the matrix keeps its space. */}
          <details open={!layout.fixed || layout.tall} style={{ marginTop: 6 }}>
            <summary style={{ fontSize: 13, fontWeight: 700, color: T.ink, cursor: "pointer" }}>Findings ({facts.length})</summary>
            <ul data-testid="findings" aria-label="Findings" style={{ listStyle: "none", padding: 0, margin: "6px 0 0", display: "flex", flexDirection: "column", gap: 4 }}>
              {facts.map((f, k) => (
                <li key={k} style={{ display: "flex", flexWrap: "wrap", columnGap: 10, alignItems: "baseline", fontSize: 13, lineHeight: 1.45 }}>
                  <span style={{ flex: "none", minWidth: 136 }}><LayerTag kind={f.layer} /></span>
                  <span style={{ flex: "1 1 260px" }}>{f.text}{f.col && <> <button onClick={() => onCell({ col: f.col.id, row: f.col.row })} style={linkBtn} aria-label={`Show seq ${f.col.order} in the matrix`}>show</button></>}</span>
                </li>
              ))}
            </ul>
          </details>
        </section>

        <section aria-label="Agent by model-call matrix" style={{ ...panel, flex: fixed ? 1 : "none", display: "flex", flexDirection: "column", overflow: "hidden", minHeight: fixed ? 260 : undefined }}>
          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", columnGap: 12, rowGap: 8, padding: "10px 16px", borderBottom: `1px solid ${T.line}` }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", columnGap: 8 }}>
              <h2 style={{ fontSize: 14, fontWeight: 700, color: T.ink, margin: 0 }}>Agent × model-call matrix</h2>
              <span id="matrix-help" style={{ fontSize: 12.5, color: T.faint }}>columns in observation order · scroll sideways, or focus the matrix and use ← → ↑ ↓, Home, End, Enter</span>
            </div>
            {d.key.length > 0 && (
              <nav aria-label="Key events" data-testid="jumps" style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6 }}>
                <span style={{ ...eyebrow, marginRight: 2 }}>Key events</span>
                {d.key.map(k => {
                  const active = sel?.col === k.col.id;
                  return (
                    <button key={k.col.id} data-testid={`jump-${k.col.id}`} aria-label={`${k.label}, seq ${k.col.order}`} aria-pressed={active}
                      onClick={() => onCell({ col: k.col.id, row: k.col.row })}
                      style={{ fontSize: 13, padding: "4px 9px", borderRadius: 5, cursor: "pointer", whiteSpace: "nowrap", fontFamily: T.sans,
                        border: `1px solid ${active ? T.ink : T.line}`, background: active ? T.ink : T.panel, color: active ? "#fff" : T.text }}>
                      {k.label} <span style={{ fontFamily: T.mono }}>{k.col.order}</span>
                    </button>
                  );
                })}
                {!fixed && <button onClick={toInspector} style={{ ...linkBtn, marginLeft: 4 }}>Go to details ↓</button>}
              </nav>
            )}
          </div>
          <div role="list" aria-label="Matrix legend" style={{ display: "flex", flexWrap: "wrap", columnGap: 18, rowGap: 6, alignItems: "center", padding: "8px 16px", fontSize: 13, color: T.muted, borderBottom: `1px solid ${T.soft}` }}>
            <Legend swatch={<span style={{ ...sw, background: CELL.fill, border: `1px solid ${CELL.stroke}` }} />}>Observed model call</Legend>
            {d.hasUnresolved && <Legend swatch={<span style={{ ...sw, background: HATCH, border: "1px solid #6b7486", fontSize: 11, fontWeight: 700, textAlign: "center", lineHeight: "13px" }}>?</span>}>Unresolved origin</Legend>}
            {d.edges.length > 0 && <Legend swatch={<b style={{ color: CELL.glyph }}>⇢ D</b>}>Delegation issued / received</Legend>}
            {d.fixtureCols.length > 0 && <Legend swatch={<b style={{ color: LAYER.hand.color }}>◆</b>}>Fixture link</Legend>}
            {d.overlapCols.length > 0 && <Legend swatch={<b style={{ color: CELL.glyph }}>∥</b>}>Overlapping observation</Legend>}
            <Legend swatch={<span style={{ ...sw, border: `1px dashed ${T.faint}` }} />}>No observation (blank)</Legend>
            <Legend swatch={<span style={{ ...sw, border: `3px solid ${T.focus}` }} />}>Selected cell</Legend>
          </div>
          <Matrix m={m} d={d} sel={sel} onSelect={onCell} onActivate={toInspector} layout={layout} />
          <p style={{ padding: "8px 16px", margin: 0, fontSize: 12.5, color: T.muted, borderTop: `1px solid ${T.soft}` }}>
            Observation order only: column position implies no precedence, causation or belief persistence · delivered means byte-identical presence, not use.
          </p>
        </section>
      </div>

      <aside data-testid="inspector" aria-label="Inspector" style={{ ...panel, display: "flex", flexDirection: "column", overflow: fixed ? "hidden" : "visible", height: fixed ? "100%" : "auto" }}>
        <div style={{ padding: "12px 16px" }}>
          <div style={eyebrow}>Inspector</div>
          <h2 data-testid="inspector-title" style={{ fontSize: 16, fontWeight: 700, color: T.ink, margin: "4px 0 0" }}>
            {event ? "Tool call" : !col ? "Nothing selected" : cellHere ? `${d.rowName(col.row)} · seq ${col.order}` : `${d.rowName(sel.row)} · seq ${col.order}`}
          </h2>
        </div>
        <div ref={inspector} data-testid="cell-detail" tabIndex={fixed ? 0 : -1} role="region" aria-label="Selected cell details" style={{ flex: 1, minHeight: 0, overflowY: fixed ? "auto" : "visible" }}>
          {event ? <EventInspector m={m} d={d} id={event} onBack={() => setEvent(null)} onCall={c => onCell({ col: c.id, row: c.row })} />
            : !col ? <Section title="No model calls"><p style={pText}>This trace has no observable model calls to inspect.</p></Section>
              : cellHere ? <CallInspector m={m} d={d} col={col} onOpen={onOpen} />
                : <Section title="No observation"><p style={pText}><b>{d.rowName(sel.row)}</b> has no model call at seq {col.order}. Nothing is carried forward from earlier calls, so no state is shown or implied.</p></Section>}
        </div>
        <div style={{ borderTop: `1px solid ${T.line}`, padding: "8px 16px 10px" }}>
          <Disclosure label="Run provenance and records the adapter did not represent" testid="sources">
            <KV rows={[["run id", <Mono key="r">{m.run.run_id}</Mono>], ["record run id", <Mono key="rr" muted>{m.run.record_run_id}</Mono>], ["model", m.run.model],
              ...Object.entries(m.provenance).filter(([, v]) => v != null).map(([k, v]) => [k, <Mono key={k} muted>{typeof v === "object" ? JSON.stringify(v) : v}</Mono>])]} />
            <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
              {m.skipped.filter(s => s.seq.length).map((s, i) => <li key={i} style={{ fontSize: 12, color: T.muted, marginBottom: 3 }}><Mono>{s.kind}</Mono> seq {s.seq.join(", ")}</li>)}
            </ul>
          </Disclosure>
        </div>
      </aside>
    </div>
  );
}

export default function MatrixView({ layout }) {
  const [runId, setRunId] = useState(RUNS[0]?.run_id ?? null);
  const [state, setState] = useState({ status: "loading", runId: null, m: null, error: null });
  useEffect(() => {
    const entry = RUNS.find(r => r.run_id === runId);
    if (!entry) return undefined;
    let alive = true;
    loadRun(entry).then(m => alive && setState({ status: "ready", runId, m, error: null }))
      .catch(err => alive && setState({ status: "error", runId, m: null, error: String(err.message ?? err) }));
    return () => { alive = false; };
  }, [runId]);
  const current = state.runId === runId ? state : { status: "loading" };
  const fixed = layout.fixed;
  if (!MANIFEST) return <div style={{ padding: 16 }}><Note tone="info" testid="local-only-data">Demo data is local-only. See <Mono>docs/DATA.md</Mono> to get or build it.</Note></div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: fixed ? "100%" : "auto" }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10, padding: "10px 12px" }}>
        <label htmlFor="run-select" style={{ fontSize: 13, fontWeight: 700, color: T.ink }}>Run</label>
        <select id="run-select" data-testid="run-select" value={runId ?? ""} onChange={e => setRunId(e.target.value)}
          style={{ fontSize: 14, fontFamily: T.sans, padding: "6px 10px", borderRadius: 6, border: `1px solid ${T.line}`, background: T.panel, color: T.ink, maxWidth: "100%" }}>
          {RUNS.map(r => <option key={r.run_id} value={r.run_id}>{`${r.run_id} — ${plural(r.agents, "agent")}, ${plural(r.model_calls, "model call")}${r.delivery_telemetry === "absent" ? ", no input telemetry" : ""}, ${r.status}`}</option>)}
        </select>
        <span data-testid="load-state" style={{ fontSize: 12.5, color: T.muted }}>
          {current.status === "loading" ? "Loading…" : current.status === "error" ? "" : "Validated run data · sha256 checked against the manifest"}
        </span>
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>
        {!RUNS.length && <p style={{ padding: 16 }}>No runs in the manifest. Build one with <Mono>scripts/demo/build_matrix.py</Mono>.</p>}
        {current.status === "error" && <div role="alert" style={{ margin: 12, ...panel, padding: 16, color: "#991b1b", fontSize: 14 }}>Could not load this run: {current.error}</div>}
        {current.status === "ready" && <RunView key={runId} m={current.m} layout={layout} />}
      </div>
    </div>
  );
}
