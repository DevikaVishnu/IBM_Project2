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

const BAND_H = 34;

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
    return { idx, byCol };
  }, [mx]);
  const n = mx?.columns.length ?? 0;
  const g = useGridGeometry(wrap, n);
  const flag = b.flags.find(f => f.id === highlightFlag);
  const flagCols = flag ? (flag.columns ?? flag.events).filter(e => view?.idx[e] != null) : [];

  if (!mx || !b.layers.matrix) return <Empty testid="matrix-empty">The interaction matrix is not available for this trace.</Empty>;
  if (!n) return <Empty testid="matrix-empty">No model calls were recorded in this trace.</Empty>;
  const col = mx.columns[view.idx[selectedCol]] ?? null;
  const sel = col ? { col: col.id, row: rowSel && rowSel.col === col.id ? rowSel.row : col.row } : null;
  const onSelect = s => { setRowSel(s); onSelectCol(s.col); };
  const isHand = mx.origin === "hand-reconstructed";
  const lanesList = (mx.overlays ?? []).filter(o => o.kind === "lane");
  const clip = g ? { position: "absolute", left: g.labelW, width: g.visibleW, overflow: "hidden" } : null;

  return (
    <div style={{ display: "grid", gridTemplateColumns: narrow ? "minmax(0,1fr)" : "minmax(0,1fr) 360px", gap: 14, alignItems: "start" }}>
      <section aria-label="Interaction matrix" data-testid="matrix-panel" style={{ ...card, overflow: "hidden" }}>
        <div style={{ padding: "12px 16px", borderBottom: `1px solid ${v("line")}`, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
          <h2 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: v("ink") }}>Interaction matrix</h2>
          <OriginTag origin={mx.origin} />
          <span style={{ fontSize: 12.5, color: v("muted") }}>{d.rows.length} {d.rows.length === 1 ? "row" : "rows"} × {n} columns · {mx.axis}{mx.source_contract ? ` · ${mx.source_contract}` : ""}</span>
        </div>
        {mx.note && <div data-testid="matrix-note" style={{ padding: "8px 16px", fontSize: 13, color: isHand ? "#5B21B6" : "#1E3A8A", background: isHand ? "#F5F3FF" : v("primary-soft"), borderBottom: `1px solid ${v("line")}` }}>
          {mx.note}{isHand ? " The axis numbers are log lines; a \"D\" cell received an item produced in another row." : ""}</div>}
        <div role="list" aria-label="Matrix legend" style={{ display: "flex", flexWrap: "wrap", gap: "6px 16px", padding: "8px 16px", fontSize: 12.5, color: v("muted"), borderBottom: `1px solid ${v("soft")}` }}>
          <Legend sw={<span style={{ ...sw, background: "#d6e3fa", border: "1px solid #7f9fd9" }} />}>{isHand ? "LLM call / check" : "Observed model call"}</Legend>
          {mx.rows.some(r => r.kind === "unresolved") && !isHand && <Legend sw={<span style={{ ...sw, background: "repeating-linear-gradient(45deg,#c9d0da 0 3px,#f6f7f9 3px 6px)", border: "1px solid #6b7486" }} />}>Unresolved origin (?)</Legend>}
          {mx.edges.length > 0 && <Legend sw={<b style={{ color: "#1d4ed8" }}>⇢ D</b>}>{isHand ? "Handoff issued / received" : "Delegation issued / received"}</Legend>}
          <Legend sw={<b style={{ color: "#B45309" }}>◆</b>}>Claim (hand-annotated)</Legend>
          <Legend sw={<b style={{ color: "#B91C1C" }}>⚑</b>}>Flag</Legend>
          {lanesList.length > 0 && <Legend sw={<b style={{ color: "#6D28D9" }}>▾</b>}>Lane marker</Legend>}
          {flag && <Legend sw={<span style={{ ...sw, background: "rgba(245,158,11,0.3)" }} />}>Columns of “{flag.title}”</Legend>}
        </div>
        <div ref={wrap} style={{ position: "relative" }}>
          <div aria-label="Markers" data-testid="marker-band" style={{ height: BAND_H, position: "relative", borderBottom: `1px solid ${v("soft")}` }}>
            <span style={{ ...eyebrow, position: "absolute", left: 14, top: 10 }}>Markers</span>
            {g && (
              <div style={{ ...clip, top: 0, height: BAND_H }}>
                <div style={{ position: "relative", transform: `translateX(${-g.scrollLeft}px)`, height: BAND_H }}>
                  {mx.columns.map((c, i) => {
                    const ov = view.byCol[c.id] ?? [];
                    if (!ov.length) return null;
                    const nc = ov.filter(o => o.kind === "claim").length, nf = new Set(ov.filter(o => o.kind === "flag").map(o => o.ref)).size, nl = ov.filter(o => o.kind === "lane").length;
                    const glyphs = [nc && ["◆", nc, "#B45309"], nf && ["⚑", nf, "#B91C1C"], nl && ["▾", nl, "#6D28D9"]].filter(Boolean);
                    return (
                      <button key={c.id} data-testid={`marker-${c.id}`} title={ov.map(o => `${o.kind}: ${o.label}`).join("\n")}
                        aria-label={`Markers at ${c.label ?? `step ${c.order}`}: ${ov.map(o => o.label).join("; ")}`} onClick={() => onSelect({ col: c.id, row: c.row })}
                        style={{ position: "absolute", left: i * g.colW + 1, top: 3, width: g.colW - 2, height: BAND_H - 6, padding: 0, cursor: "pointer", borderRadius: 5,
                          border: `1px solid ${c.id === selectedCol ? "#0F172A" : v("line")}`, background: v("surface"), display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", lineHeight: 1 }}>
                        {glyphs.slice(0, 2).map(([gl, k, color]) => <b key={gl} style={{ color, fontSize: glyphs.length > 1 ? 10 : 12 }}>{gl}{k > 1 ? k : ""}</b>)}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
          <Matrix m={model} d={d} sel={sel} onSelect={onSelect} onActivate={() => inspector.current?.focus()} layout={LAYOUT} />
          {g && flagCols.length > 0 && (
            <div aria-hidden="true" data-testid="flag-highlight" style={{ ...clip, top: g.top, height: g.height, pointerEvents: "none" }}>
              <div style={{ position: "relative", transform: `translateX(${-g.scrollLeft}px)`, height: g.height }}>
                {flagCols.map(id => <span key={id} style={{ position: "absolute", left: view.idx[id] * g.colW, width: g.colW, top: 0, height: g.height, background: "rgba(245,158,11,0.22)", boxShadow: "inset 0 0 0 1px rgba(180,83,9,0.35)" }} />)}
              </div>
            </div>
          )}
        </div>
        <div style={{ padding: "8px 16px 10px", borderTop: `1px solid ${v("soft")}`, fontSize: 12.5, color: v("muted"), lineHeight: 1.5 }}>
          {mx.order_caveat ? `${mx.order_caveat.split(". ")[0].replace(/\.$/, "")}. ` : ""}{isHand ? "Delivered means presence in the rendered input as reconstructed in §14, not use." : "Delivered means byte-identical presence in a rendered input, not use."}
        </div>
        {lanesList.length > 0 && (
          <div aria-label="Annotated lanes" style={{ padding: "8px 16px 12px", borderTop: `1px solid ${v("soft")}`, display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
            <span style={{ ...eyebrow, marginRight: 4 }}>Lanes</span><OriginTag origin="hand-annotated" style={{ marginRight: 6 }} />
            {lanesList.map(o => (
              <button key={o.id} onClick={() => onSelect({ col: o.column, row: o.row })} className="be-hover"
                style={{ fontSize: 12.5, padding: "3px 8px", borderRadius: 6, border: `1px solid ${o.column === selectedCol ? "#0F172A" : v("line")}`, background: v("surface"), cursor: "pointer", color: v("ink") }}>{o.label}</button>
            ))}
          </div>
        )}
      </section>
      <div ref={inspector} tabIndex={-1}>
        <ColumnInspector b={b} col={col} overlays={col ? view.byCol[col.id] ?? [] : []} onOpenClaim={onOpenClaim} onOpenFlag={onOpenFlag} />
      </div>
    </div>
  );
}

const sw = { display: "inline-block", width: 12, height: 12, borderRadius: 3 };
function Legend({ sw: swatch, children }) {
  return <span role="listitem" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><span aria-hidden="true" style={{ display: "inline-flex" }}>{swatch}</span>{children}</span>;
}

function ColumnInspector({ b, col, overlays, onOpenClaim, onOpenFlag }) {
  const mx = b.matrix;
  if (!col) {
    return <aside aria-label="Column details" data-testid="col-inspector" style={{ ...card, padding: 16, fontSize: 13, color: v("muted") }}>Select a column or a marker to see the call, its markers and their claim chains.</aside>;
  }
  const row = mx.rows.find(r => r.id === col.row);
  const claims = overlays.filter(o => o.kind === "claim");
  const flagIds = [...new Set(overlays.filter(o => o.kind === "flag").map(o => o.ref))];
  const involved = b.flags.filter(f => f.events.includes(col.id) && !flagIds.includes(f.id));
  const lanes = overlays.filter(o => o.kind === "lane");
  const edgesIn = mx.edges.filter(e => e.to === col.id), edgesOut = mx.edges.filter(e => e.from === col.id);
  const ev = b.skeleton?.events?.find(e => e.id === col.id);
  return (
    <aside aria-label="Column details" data-testid="col-inspector" style={{ ...card, padding: "14px 16px", display: "flex", flexDirection: "column", gap: 12 }}>
      <div>
        <div style={eyebrow}>Selected column</div>
        <h3 style={{ margin: "2px 0 4px", fontSize: 16, fontWeight: 700, color: v("ink") }}>{col.label ?? `Model call at step ${col.order}`}</h3>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", fontSize: 13 }}>
          <span>{row?.kind === "unresolved" ? <i>{row.label}</i> : <b>{row?.label}</b>}</span><OriginTag origin={col.origin} />
        </div>
      </div>
      <dl style={{ display: "grid", gridTemplateColumns: "max-content minmax(0,1fr)", gap: "4px 12px", margin: 0, fontSize: 13 }}>
        <dt style={{ color: v("muted") }}>{mx.origin === "hand-reconstructed" ? "log line" : "raw steps"}</dt><dd style={{ margin: 0, ...mono }}>{col.steps[0] === col.steps[1] ? col.steps[0] : `${col.steps[0]}–${col.steps[1]}`}</dd>
        {col.phase && <><dt style={{ color: v("muted") }}>phase</dt><dd style={{ margin: 0 }}>{col.phase}</dd></>}
        {ev?.produces && <><dt style={{ color: v("muted") }}>produces</dt><dd style={{ margin: 0 }}>{ev.produces}</dd></>}
        {mx.delivery_track && <><dt style={{ color: v("muted") }}>input items</dt><dd style={{ margin: 0 }}>{fmt(col.delivers)} delivered · {fmt(col.first)} new to this agent</dd></>}
        {col.tools?.length > 0 && <><dt style={{ color: v("muted") }}>issued</dt><dd style={{ margin: 0, ...mono }}>{[...new Set(col.tools)].join(", ")}</dd></>}
        {col.overlaps > 0 && <><dt style={{ color: v("muted") }}>overlaps</dt><dd style={{ margin: 0 }}>{col.overlaps} other calls (no precedence implied)</dd></>}
      </dl>
      {(edgesIn.length > 0 || edgesOut.length > 0) && (
        <div style={{ fontSize: 13, lineHeight: 1.5 }}>
          {edgesOut.map(e => <div key={e.to}>Handoff out → {mx.columns.find(c => c.id === e.to)?.label ?? e.to.replace(/^ev:llm:/, "call ")} <span style={{ color: v("muted") }}>({e.via})</span></div>)}
          {edgesIn.map(e => <div key={e.from}>Handoff in ← {mx.columns.find(c => c.id === e.from)?.label ?? e.from.replace(/^ev:llm:/, "call ")} <span style={{ color: v("muted") }}>({e.via})</span></div>)}
        </div>
      )}
      <div data-testid="col-markers">
        <div style={{ ...eyebrow, marginBottom: 6 }}>Markers here</div>
        {!claims.length && !flagIds.length && !lanes.length && <p style={{ margin: 0, fontSize: 13, color: v("muted") }}>No annotated claim or flag at this column.</p>}
        {claims.map(o => {
          const c = b.claims.find(x => x.id === o.ref);
          return (
            <button key={o.id} className="be-hover" data-testid={`open-claim-${o.ref}`} onClick={() => onOpenClaim(o.ref)}
              style={{ display: "flex", width: "100%", alignItems: "center", gap: 8, textAlign: "left", border: `1px solid ${v("line")}`, borderRadius: 7, background: v("surface"), padding: "7px 9px", marginBottom: 6, cursor: "pointer", color: v("ink") }}>
              <b style={{ color: "#B45309" }}>◆</b><span style={{ flex: 1, fontSize: 13 }}>{o.label}</span>
              {c && <Chip tone="muted">{c.state?.value}</Chip>}<span aria-hidden="true" style={{ color: v("muted") }}>→</span>
            </button>
          );
        })}
        {flagIds.map(id => {
          const f = b.flags.find(x => x.id === id);
          return (
            <button key={id} className="be-hover" data-testid={`open-flag-${id}`} onClick={() => onOpenFlag(id)}
              style={{ display: "flex", width: "100%", alignItems: "center", gap: 8, textAlign: "left", border: `1px solid ${v("line")}`, borderRadius: 7, background: v("surface"), padding: "7px 9px", marginBottom: 6, cursor: "pointer", color: v("ink") }}>
              <b style={{ color: "#B91C1C" }}>⚑</b><span style={{ flex: 1, fontSize: 13 }}>{f?.title ?? id}</span><span aria-hidden="true" style={{ color: v("muted") }}>→</span>
            </button>
          );
        })}
        {lanes.map(o => <div key={o.id} style={{ fontSize: 13, color: "#5B21B6", marginBottom: 4 }}>▾ {o.label}</div>)}
        {(claims.length > 0 || flagIds.length > 0 || lanes.length > 0) && <OriginTag origin="hand-annotated" />}
      </div>
      {involved.length > 0 && (
        <div style={{ fontSize: 13 }}>
          <div style={{ ...eyebrow, marginBottom: 4 }}>Also involved in</div>
          {involved.map(f => <div key={f.id}><button style={linkBtn} onClick={() => onOpenFlag(f.id)}>{f.title}</button></div>)}
        </div>
      )}
    </aside>
  );
}
