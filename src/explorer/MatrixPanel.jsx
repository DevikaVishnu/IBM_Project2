import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Matrix, derive } from "../demo/MatrixView.jsx";
import { Chip, Empty, OriginTag, card, eyebrow, fmt, linkBtn, mono, v } from "./theme.jsx";

// Interaction matrix: rows = agents, columns = model calls in observation order.  The grid is the
// earlier matrix view's own code (Matrix and derive from src/demo/MatrixView.jsx), fed by a small
// adapter from the bundle's matrix layer.  The grid stays claim-free: claim, flag and lane markers are
// overlays from the bundle's annotation layer, drawn in a marker band above the grid and a highlight
// layer over it, both kept in step with the grid's own horizontal scroll.

const LAYOUT = { fixed: false, narrow: false, tall: false };

// Bundle matrix layer -> the agenttrace-matrix/0.2 fields that derive() and Matrix read.  Only counts
// and the handoff joins are needed, so lists are filled to the bundle's counts with placeholders.
export function toMatrixModel(mx) {
  const fill = (k, f) => Array.from({ length: k }, (_, i) => f(i));
  const edgesTo = {};
  const evidence = {};
  for (const e of mx.edges) {
    const key = `${e.item}@${e.to}`;
    (edgesTo[e.to] ||= []).push(key);
    evidence[key] = { produced_by: e.from };
  }
  const columns = mx.columns.map(c => {
    const handoffs = edgesTo[c.id] ?? [];
    const first = [...handoffs.map(k => [k, ""]), ...fill(Math.max(0, c.first - handoffs.length), i => [`#first-${c.id}-${i}`, ""])];
    return {
      id: c.id, order: c.order, row: c.row, start_seq: c.steps[0], end_seq: c.steps[1],
      delivers: fill(Math.max(c.delivers, first.length), i => i), first_delivered_here: first, delegation_input: handoffs,
      issued_delegations: c.delegation_out ? ["#delegation"] : [], overlaps_with: fill(c.overlaps, i => i), fixture_links: [],
      issued_tool_events: [], origin_rule: c.origin === "unresolved" ? "unresolved" : null,
    };
  });
  return {
    rows: mx.rows.filter(r => r.id !== "$unresolved").map(r => ({ id: r.id, agent_id: r.label, kind: r.sub, name: null })),
    columns, evidence, ambiguities: [], telemetry: { delivery: mx.delivery_track ? "present" : "absent" },
  };
}

// Geometry of the rendered grid, read from its DOM so the overlays line up with whatever width it chose.
function useGridGeometry(wrap, n) {
  const [g, setG] = useState(null);
  const measure = () => {
    const el = wrap.current;
    const grid = el?.querySelector('[data-testid="matrix-grid"]');
    const scroller = el?.querySelector('[data-testid="matrix"]');
    const svg = scroller?.querySelector("svg");
    if (!grid || !scroller || !svg || !n) return;
    const next = { labelW: grid.firstElementChild.getBoundingClientRect().width, colW: svg.width.baseVal.value / n,
      top: grid.offsetTop, height: grid.offsetHeight, visibleW: scroller.clientWidth, scrollLeft: scroller.scrollLeft };
    setG(prev => (prev && Object.keys(next).every(k => prev[k] === next[k]) ? prev : next));
  };
  useLayoutEffect(measure);
  useEffect(() => {
    const scroller = wrap.current?.querySelector('[data-testid="matrix"]');
    if (!scroller) return undefined;
    scroller.addEventListener("scroll", measure, { passive: true });
    const ro = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    ro?.observe(scroller);
    const svg = scroller.querySelector("svg");
    if (svg) ro?.observe(svg);
    return () => { scroller.removeEventListener("scroll", measure); ro?.disconnect(); };
  });
  return g;
}

const BAND_H = 40;
// Explorer column widths: wide enough for readable markers and axis labels; long traces scroll sideways.
const MIN_COL = 44;
const MAX_COL = 72;
const short = (s, k = 34) => (s && s.length > k ? `${s.slice(0, k - 1)}…` : s);
const callName = id => String(id ?? "").replace(/^ev:llm:/, "call ").replace(/^gk:/, "");
const agentName = id => (id === "$unresolved" ? "unresolved origin" : String(id ?? "").replace(/^agent:|^role:/, "").replace(/^\$not_reconstructed$/, "not reconstructed"));

export default function MatrixPanel({ b, selectedCol, onSelectCol, highlightFlag, onOpenClaim, onOpenFlag, narrow }) {
  const mx = b.matrix;
  const wrap = useRef(null);
  const inspector = useRef(null);
  const [rowSel, setRowSel] = useState(null);
  const model = useMemo(() => (mx ? toMatrixModel(mx) : null), [mx]);
  const d = useMemo(() => (model ? derive(model) : null), [model]);
  const view = useMemo(() => {
    if (!mx) return null;
    const idx = Object.fromEntries(mx.columns.map((c, i) => [c.id, i]));
    const byCol = {};
    for (const o of mx.overlays ?? []) (byCol[o.column] ||= []).push(o);
    const nth = {};
    const perRow = {};
    for (const c of mx.columns) { perRow[c.row] = (perRow[c.row] ?? 0) + 1; nth[c.id] = perRow[c.row]; }
    return { idx, byCol, nth, perRow };
  }, [mx]);
  const n = mx?.columns.length ?? 0;
  const g = useGridGeometry(wrap, n);
  const flag = b.flags.find(f => f.id === highlightFlag);
  const flagCols = flag ? (flag.columns ?? flag.events).filter(e => view?.idx[e] != null) : [];
  const selIdx = view && selectedCol != null ? view.idx[selectedCol] ?? -1 : -1;

  // Keep the selected column in view, also after a resize or a zoom change.
  useEffect(() => {
    const scroller = wrap.current?.querySelector('[data-testid="matrix"]');
    if (!scroller || !g || selIdx < 0) return;
    const left = selIdx * g.colW, right = left + g.colW, margin = Math.min(3 * g.colW, scroller.clientWidth / 4);
    if (left < scroller.scrollLeft + margin || right > scroller.scrollLeft + scroller.clientWidth - margin) scroller.scrollLeft = Math.max(0, left - scroller.clientWidth / 2 + g.colW / 2);
  }, [selIdx, g?.colW, g?.visibleW]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!mx || !b.layers.matrix) return <Empty testid="matrix-empty">The interaction matrix is not available for this trace.</Empty>;
  if (!n) return <Empty testid="matrix-empty">No model calls were recorded in this trace.</Empty>;
  const col = selIdx >= 0 ? mx.columns[selIdx] : null;
  const sel = col ? { col: col.id, row: rowSel && rowSel.col === col.id ? rowSel.row : col.row } : null;
  const onSelect = s => { setRowSel(s); onSelectCol(s.col); };
  const go = i => { const c = mx.columns[Math.max(0, Math.min(n - 1, i))]; onSelect({ col: c.id, row: c.row }); };
  const isHand = mx.origin === "hand-reconstructed";
  const clip = g ? { position: "absolute", left: g.labelW, width: g.visibleW, overflow: "hidden" } : null;
  const runFlags = b.flags.filter(f => f.kind === "run_status");
  // Jump targets: annotated lanes if the trace has them, otherwise one entry per marked column.
  const lanes = (mx.overlays ?? []).filter(o => o.kind === "lane");
  const jumps = lanes.length ? lanes.map(o => ({ id: o.id, column: o.column, row: o.row, label: o.label, glyph: "▾", color: "#6D28D9" }))
    : Object.entries(view.byCol).sort((a, b2) => view.idx[a[0]] - view.idx[b2[0]]).map(([cid, ov]) => {
      const c = mx.columns[view.idx[cid]];
      const nc = ov.filter(o => o.kind === "claim").length, nf = new Set(ov.filter(o => o.kind === "flag").map(o => o.ref)).size;
      return { id: cid, column: cid, row: c.row, label: `${c.label ?? callName(cid)} · ${[nc && `${nc} claim${nc > 1 ? "s" : ""}`, nf && `${nf} flag${nf > 1 ? "s" : ""}`].filter(Boolean).join(", ")}`,
        glyph: nc ? "◆" : "⚑", color: nc ? "#B45309" : "#B91C1C" };
    });
  const here = col ? view.byCol[col.id] ?? [] : [];
  const nClaims = here.filter(o => o.kind === "claim").length, nFlags = new Set(here.filter(o => o.kind === "flag").map(o => o.ref)).size;

  return (
    <div style={{ display: "grid", gridTemplateColumns: narrow ? "minmax(0,1fr)" : "minmax(0,1fr) clamp(320px, 24vw, 400px)", gap: 16, alignItems: "start" }}>
      <section aria-labelledby="mx-title" data-testid="matrix-panel" style={{ ...card, overflow: "hidden" }}>
        <header style={{ padding: "14px 18px 12px", borderBottom: `1px solid ${v("line")}` }}>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
            <h2 id="mx-title" style={{ margin: 0, fontSize: 16, fontWeight: 700, color: v("ink") }}>Model-call observations</h2>
            <OriginTag origin={mx.origin} />
            <span style={{ marginLeft: "auto", fontSize: 12.5, color: v("muted") }}>{d.rows.length} {d.rows.length === 1 ? "row" : "rows"} × {n} {isHand ? "events" : "model calls"}{mx.source_contract ? ` · ${mx.source_contract}` : ""}</span>
          </div>
          <p data-testid="matrix-scope" style={{ margin: "6px 0 0", fontSize: 13, lineHeight: 1.5, color: v("muted") }}>
            {isHand
              ? <>Rows are ChatDev roles; columns are the LLM calls and the test gate in log-line order. This is not a complete event timeline: messages and phases outside these calls are not columns (see Skeleton).</>
              : <>Rows are agents; each column is one model call, in observation order. This is not a complete event timeline: tool calls, file events and framework records are not columns (see Skeleton).</>}
          </p>
        </header>
        {runFlags.map(f => (
          <div key={f.id} role="note" data-testid="run-status-banner" style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10, padding: "10px 18px", background: "#FEF2F2", borderBottom: "1px solid #FECACA", fontSize: 13.5, color: "#7F1D1D" }}>
            <b style={{ color: "#B91C1C" }} aria-hidden="true">⚑</b><b>{f.title}.</b><span style={{ flex: "1 1 320px" }}>{f.text}</span>
            <button style={{ ...linkBtn, color: "#B91C1C" }} onClick={() => onOpenFlag(f.id)}>Open flag</button>
          </div>
        ))}
        {mx.note && <div data-testid="matrix-note" style={{ padding: "8px 18px", fontSize: 13, lineHeight: 1.5, color: isHand ? "#5B21B6" : "#1E3A8A", background: isHand ? "#F5F3FF" : v("primary-soft"), borderBottom: `1px solid ${v("line")}` }}>
          {mx.note}{isHand ? " The axis numbers are log lines; a \"D\" cell received an item produced in another row." : ""}</div>}
        {jumps.length > 0 && (
          <nav aria-label="Annotated moments" data-testid="jump-bar" style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6, padding: "10px 18px", borderBottom: `1px solid ${v("soft")}` }}>
            <span style={{ ...eyebrow, marginRight: 2 }}>Annotated moments</span><OriginTag origin="hand-annotated" style={{ marginRight: 6 }} />
            {jumps.map(j => {
              const on = j.column === selectedCol;
              return (
                <button key={j.id} className="be-hover" aria-pressed={on} onClick={() => onSelect({ col: j.column, row: j.row })}
                  style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, padding: "4px 10px", borderRadius: 7, cursor: "pointer", color: v("ink"),
                    border: `1px solid ${on ? "#2563EB" : v("line")}`, background: on ? v("primary-soft") : v("surface"), fontWeight: on ? 650 : 500 }}>
                  <b aria-hidden="true" style={{ color: j.color }}>{j.glyph}</b>{j.label}
                </button>
              );
            })}
          </nav>
        )}
        <div role="list" aria-label="Matrix legend" style={{ display: "flex", flexWrap: "wrap", gap: "6px 18px", padding: "8px 18px", fontSize: 12.5, color: v("muted"), borderBottom: `1px solid ${v("soft")}` }}>
          <Legend sw={<span style={{ ...sw, background: "#d6e3fa", border: "1px solid #7f9fd9" }} />}>{isHand ? "LLM call or check" : "Observed model call"}</Legend>
          {d.hasUnresolved && <Legend sw={<span style={{ ...sw, background: "repeating-linear-gradient(45deg,#c9d0da 0 3px,#f6f7f9 3px 6px)", border: "1px solid #6b7486" }} />}>Unresolved agent origin (?)</Legend>}
          {mx.edges.length > 0 && <Legend sw={<b style={{ color: "#1d4ed8" }}>⇢ D</b>}>{isHand ? "Item handed to another role / received" : "Task delegated / received"}</Legend>}
          <Legend sw={<b style={{ color: "#B45309" }}>◆</b>}>Claim</Legend>
          <Legend sw={<b style={{ color: "#B91C1C" }}>⚑</b>}>Flag</Legend>
          {lanes.length > 0 && <Legend sw={<b style={{ color: "#6D28D9" }}>▾</b>}>Annotated moment</Legend>}
          {flag && <Legend sw={<span style={{ ...sw, background: "rgba(245,158,11,0.35)" }} />}>Columns of “{flag.title}”</Legend>}
          {mx.delivery_track && <Legend sw={<span style={{ ...sw, background: "#b9cdf3" }} />}>Rendered-input items (dark: new to that agent)</Legend>}
        </div>
        <div ref={wrap} style={{ position: "relative" }}>
          <div aria-label="Markers" data-testid="marker-band" style={{ height: BAND_H, position: "relative", borderBottom: `1px solid ${v("soft")}`, background: v("canvas") }}>
            <span style={{ ...eyebrow, position: "absolute", left: 14, top: 13 }}>Markers</span>
            {g && (
              <div style={{ ...clip, top: 0, height: BAND_H }}>
                <div style={{ position: "relative", transform: `translateX(${-g.scrollLeft}px)`, height: BAND_H }}>
                  {mx.columns.map((c, i) => {
                    const ov = view.byCol[c.id] ?? [];
                    if (!ov.length) return null;
                    const nc = ov.filter(o => o.kind === "claim").length, nf = new Set(ov.filter(o => o.kind === "flag").map(o => o.ref)).size, nl = ov.filter(o => o.kind === "lane").length;
                    const glyphs = [nc && ["◆", nc, "#B45309"], nf && ["⚑", nf, "#B91C1C"], nl && ["▾", nl, "#6D28D9"]].filter(Boolean);
                    const on = c.id === selectedCol;
                    return (
                      <button key={c.id} data-testid={`marker-${c.id}`} title={ov.map(o => `${o.kind}: ${o.label}`).join("\n")}
                        aria-label={`Markers at ${c.label ?? `step ${c.order}`}: ${ov.map(o => o.label).join("; ")}`} onClick={() => onSelect({ col: c.id, row: c.row })}
                        style={{ position: "absolute", left: i * g.colW + 2, top: 4, width: g.colW - 4, height: BAND_H - 8, padding: "0 2px", cursor: "pointer", borderRadius: 6,
                          border: `1.5px solid ${on ? "#2563EB" : "#CBD5E1"}`, background: on ? v("primary-soft") : v("surface"), display: "flex", alignItems: "center", justifyContent: "center", gap: 3, lineHeight: 1, overflow: "hidden" }}>
                        {glyphs.slice(0, g.colW >= 56 ? 3 : 2).map(([gl, k, color]) => <b key={gl} style={{ color, fontSize: 13, whiteSpace: "nowrap" }}>{gl}{k > 1 ? <span style={{ fontSize: 11 }}>{k}</span> : ""}</b>)}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
          <Matrix m={model} d={d} sel={sel} onSelect={onSelect} onActivate={() => inspector.current?.focus()} layout={LAYOUT} minCol={MIN_COL} maxCol={MAX_COL} />
          {g && flagCols.length > 0 && (
            <div aria-hidden="true" data-testid="flag-highlight" style={{ ...clip, top: g.top, height: g.height, pointerEvents: "none" }}>
              <div style={{ position: "relative", transform: `translateX(${-g.scrollLeft}px)`, height: g.height }}>
                {flagCols.map(id => <span key={id} style={{ position: "absolute", left: view.idx[id] * g.colW, width: g.colW, top: 0, height: g.height, background: "rgba(245,158,11,0.22)", boxShadow: "inset 0 0 0 1px rgba(180,83,9,0.35)" }} />)}
              </div>
            </div>
          )}
        </div>
        {col && (
          <div data-testid="selection-bar" aria-live="polite" style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "6px 12px", padding: "10px 18px", borderTop: `1px solid ${v("line")}`, background: v("canvas"), fontSize: 13.5 }}>
            <span style={{ ...eyebrow }}>Selected</span>
            <b>{agentName(col.row)}</b>
            <span>{col.label ? `${col.label} · ` : ""}{isHand ? "event" : "model call"} {view.nth[col.id]} of {view.perRow[col.row]}</span>
            <span style={{ ...mono, color: v("muted") }}>{isHand ? "log line" : "steps"} {col.steps[0] === col.steps[1] ? col.steps[0] : `${col.steps[0]}–${col.steps[1]}`}</span>
            {(nClaims > 0 || nFlags > 0) && <span>{nClaims > 0 && <b style={{ color: "#B45309" }}>◆ {nClaims} </b>}{nFlags > 0 && <b style={{ color: "#B91C1C" }}>⚑ {nFlags}</b>}</span>}
            <span style={{ marginLeft: "auto", display: "inline-flex", gap: 6 }}>
              <button className="be-hover" onClick={() => go(selIdx - 1)} disabled={selIdx <= 0} style={navBtn} aria-label="Previous column">‹ Previous</button>
              <button className="be-hover" onClick={() => go(selIdx + 1)} disabled={selIdx >= n - 1} style={navBtn} aria-label="Next column">Next ›</button>
              {narrow && <button style={linkBtn} onClick={() => { inspector.current?.scrollIntoView({ block: "start" }); inspector.current?.focus(); }}>Details ↓</button>}
            </span>
          </div>
        )}
        <p style={{ margin: 0, padding: "8px 18px 12px", borderTop: `1px solid ${v("soft")}`, fontSize: 12.5, color: v("muted"), lineHeight: 1.5 }}>
          {mx.order_caveat ? `${mx.order_caveat.split(". ")[0].replace(/\.$/, "")}. ` : ""}{isHand ? "Delivered means presence in the rendered input as reconstructed in §14, not use." : "Delivered means byte-identical presence in a rendered input, not use."}
          {" "}Keyboard: focus the grid, then ← → (Home, End, Page Up/Down) to move and Enter for details.
        </p>
      </section>
      <div ref={inspector} tabIndex={-1} style={{ outline: "none" }}>
        <ColumnInspector b={b} col={col} view={view} overlays={here} onOpenClaim={onOpenClaim} onOpenFlag={onOpenFlag} />
      </div>
    </div>
  );
}

const navBtn = { fontSize: 13, padding: "4px 10px", borderRadius: 7, border: "1px solid #CBD5E1", background: "#FFFFFF", cursor: "pointer", color: "#0F172A" };
const sw = { display: "inline-block", width: 12, height: 12, borderRadius: 3 };
function Legend({ sw: swatch, children }) {
  return <span role="listitem" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><span aria-hidden="true" style={{ display: "inline-flex" }}>{swatch}</span>{children}</span>;
}

function ColumnInspector({ b, col, view, overlays, onOpenClaim, onOpenFlag }) {
  const mx = b.matrix;
  if (!col) {
    return <aside aria-label="Selected column" data-testid="col-inspector" style={{ ...card, padding: 16, fontSize: 13, color: v("muted") }}>Select a column or a marker to see the call, its markers and their claim chains.</aside>;
  }
  const isHand = mx.origin === "hand-reconstructed";
  const claims = overlays.filter(o => o.kind === "claim");
  const flagIds = [...new Set(overlays.filter(o => o.kind === "flag").map(o => o.ref))];
  const involved = b.flags.filter(f => (f.columns ?? f.events).includes(col.id) && !flagIds.includes(f.id));
  const lanes = overlays.filter(o => o.kind === "lane");
  const edgesIn = mx.edges.filter(e => e.to === col.id), edgesOut = mx.edges.filter(e => e.from === col.id);
  const ev = b.skeleton?.events?.find(e => e.id === col.id);
  const handoff = b.facts.find(f => f.handoff && (f.handoff.issued_by === col.id || f.handoff.received_by === col.id))?.handoff;
  const dt = { color: v("muted") }, dd = { margin: 0 };
  return (
    <aside aria-label="Selected column" data-testid="col-inspector" style={{ ...card, padding: "16px 18px", display: "flex", flexDirection: "column", gap: 14 }}>
      <div>
        <div style={eyebrow}>Selected column</div>
        <h3 style={{ margin: "4px 0 6px", fontSize: 17, fontWeight: 700, color: v("ink") }}>{agentName(col.row)} · {col.label ?? `model call ${view.nth[col.id]} of ${view.perRow[col.row]}`}</h3>
        <OriginTag origin={col.origin} />
      </div>
      <dl style={{ display: "grid", gridTemplateColumns: "max-content minmax(0,1fr)", gap: "5px 14px", margin: 0, fontSize: 13.5 }}>
        <dt style={dt}>{isHand ? "log line" : "raw steps"}</dt><dd style={{ ...dd, ...mono, fontSize: 13 }}>{col.steps[0] === col.steps[1] ? col.steps[0] : `${col.steps[0]}–${col.steps[1]}`}</dd>
        {col.phase && <><dt style={dt}>phase</dt><dd style={dd}>{col.phase}</dd></>}
        {ev?.produces && <><dt style={dt}>produces</dt><dd style={dd}>{ev.produces}</dd></>}
        {mx.delivery_track && <><dt style={dt}>input</dt><dd style={dd}>{fmt(col.delivers)} items delivered · {fmt(col.first)} new to this agent</dd></>}
        {col.tools?.length > 0 && <><dt style={dt}>issued</dt><dd style={{ ...dd, ...mono, fontSize: 13 }}>{[...new Set(col.tools)].join(", ")}</dd></>}
        {col.overlaps > 0 && <><dt style={dt}>overlaps</dt><dd style={dd}>{col.overlaps} other calls (no precedence implied)</dd></>}
      </dl>
      {(edgesIn.length > 0 || edgesOut.length > 0) && (
        <div style={{ fontSize: 13.5, lineHeight: 1.55 }}>
          <div style={{ ...eyebrow, marginBottom: 4, display: "flex", gap: 6, alignItems: "center" }}>Handoff <OriginTag origin={(edgesIn[0] ?? edgesOut[0]).origin} /></div>
          {edgesOut.map(e => <div key={e.to}>→ to {agentName(mx.columns.find(c => c.id === e.to)?.row)} at {mx.columns.find(c => c.id === e.to)?.label ?? callName(e.to)} <span style={{ color: v("muted") }}>({e.via})</span></div>)}
          {edgesIn.map(e => <div key={e.from}>← from {agentName(mx.columns.find(c => c.id === e.from)?.row)} at {mx.columns.find(c => c.id === e.from)?.label ?? callName(e.from)} <span style={{ color: v("muted") }}>({e.via})</span></div>)}
        </div>
      )}
      {handoff && (
        <div data-testid="inspector-handoff" style={{ border: `1px solid ${v("line")}`, borderRadius: 8, padding: "10px 12px", fontSize: 13, lineHeight: 1.55 }}>
          <div style={{ marginBottom: 6 }}>Task description <span style={{ ...mono, background: v("canvas"), padding: "1px 4px", borderRadius: 4 }}>“{handoff.description}”</span>{" "}
            <Chip tone="success">delivered byte-identical</Chip> <OriginTag origin="computed" /></div>
          <div style={{ ...eyebrow, margin: "8px 0 4px", display: "flex", gap: 6, alignItems: "center" }}>Not in the description <OriginTag origin="hand-annotated" /></div>
          <ul style={{ margin: 0, paddingLeft: 18 }}>{handoff.not_in_description.map(it => <li key={it.label}>{it.label} <span style={{ color: v("muted") }}>({it.where})</span></li>)}</ul>
          <p style={{ margin: "6px 0 0", color: v("muted") }}>Formal non-delivery to the helper: <Chip tone="muted">UNKNOWN</Chip></p>
        </div>
      )}
      <div data-testid="col-markers">
        <div style={{ ...eyebrow, marginBottom: 6, display: "flex", gap: 6, alignItems: "center" }}>Markers here {(claims.length > 0 || flagIds.length > 0 || lanes.length > 0) && <OriginTag origin="hand-annotated" />}</div>
        {!claims.length && !flagIds.length && !lanes.length && <p style={{ margin: 0, fontSize: 13, color: v("muted") }}>No annotated claim or flag at this column.</p>}
        {claims.map(o => {
          const c = b.claims.find(x => x.id === o.ref);
          return (
            <button key={o.id} className="be-hover" data-testid={`open-claim-${o.ref}`} onClick={() => onOpenClaim(o.ref)}
              style={{ display: "flex", width: "100%", alignItems: "center", gap: 8, textAlign: "left", border: `1px solid ${v("line")}`, borderRadius: 8, background: v("surface"), padding: "8px 10px", marginBottom: 6, cursor: "pointer", color: v("ink") }}>
              <b style={{ color: "#B45309" }} aria-hidden="true">◆</b><span style={{ flex: 1, fontSize: 13.5 }}>{o.label}</span>
              {c && <Chip tone="muted">{c.state?.value}</Chip>}<span aria-hidden="true" style={{ color: v("muted") }}>→</span>
            </button>
          );
        })}
        {flagIds.map(id => {
          const f = b.flags.find(x => x.id === id);
          return (
            <button key={id} className="be-hover" data-testid={`open-flag-${id}`} onClick={() => onOpenFlag(id)}
              style={{ display: "flex", width: "100%", alignItems: "center", gap: 8, textAlign: "left", border: `1px solid ${v("line")}`, borderRadius: 8, background: v("surface"), padding: "8px 10px", marginBottom: 6, cursor: "pointer", color: v("ink") }}>
              <b style={{ color: "#B91C1C" }} aria-hidden="true">⚑</b><span style={{ flex: 1, fontSize: 13.5 }}>{f?.title ?? id}</span><span aria-hidden="true" style={{ color: v("muted") }}>→</span>
            </button>
          );
        })}
        {lanes.map(o => <div key={o.id} style={{ fontSize: 13.5, color: "#5B21B6", marginBottom: 4 }}>▾ {o.label}</div>)}
      </div>
      {involved.length > 0 && (
        <div style={{ fontSize: 13.5 }}>
          <div style={{ ...eyebrow, marginBottom: 4 }}>Also part of</div>
          {involved.map(f => <div key={f.id}><button style={linkBtn} onClick={() => onOpenFlag(f.id)}>⚑ {short(f.title, 48)}</button></div>)}
        </div>
      )}
    </aside>
  );
}
