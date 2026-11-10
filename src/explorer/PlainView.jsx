import { useEffect, useId, useRef, useState } from "react";
import { Chip, OriginTag, card, eyebrow, linkBtn, v } from "./theme.jsx";

// Plain-language layer for the Belief Explorer.  It renders only an optional guide sidecar (CONTRACT.md,
// "Guide sidecar"): hand-written display copy bound to one bundle sha.  Every value comes from the guide or
// the bundle; nothing is computed, inferred or special-cased here.  With no guide, none of this renders.

const P = { margin: 0, fontSize: 13, lineHeight: 1.5, color: v("ink") };
const MUTED = { fontSize: 12, color: v("muted"), lineHeight: 1.45 };

export const guideFinding = (guide, f) => guide?.findings?.[f.id] ?? null;

/* ---------- agents: name chips with a role popover ---------- */

export function AgentChips({ b, guide }) {
  const rows = (b.matrix?.rows ?? b.skeleton?.agents ?? []).filter(r => r.kind === "agent");
  const [open, setOpen] = useState(null);
  const wrap = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const key = e => { if (e.key === "Escape") setOpen(null); };
    const click = e => { if (wrap.current && !wrap.current.contains(e.target)) setOpen(null); };
    document.addEventListener("keydown", key);
    document.addEventListener("mousedown", click);
    return () => { document.removeEventListener("keydown", key); document.removeEventListener("mousedown", click); };
  }, [open]);
  if (!rows.length) return null;
  return (
    <div ref={wrap} data-testid="agent-chips" style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6 }}>
      <span style={{ ...eyebrow, marginRight: 4 }}>Council agents</span>
      {rows.map(r => <AgentChip key={r.id} r={r} g={guide?.agents?.[r.id]} note={guide?.mechanisms_note} open={open === r.id} onToggle={() => setOpen(open === r.id ? null : r.id)} />)}
    </div>
  );
}

function AgentChip({ r, g, note, open, onToggle }) {
  const id = useId();
  // Open upward when there is no room below, so the popover is never under the fold of a 768 px screen.
  const [up, setUp] = useState(false);
  const toggle = e => { const rc = e.currentTarget.getBoundingClientRect(); setUp(rc.bottom + 260 > window.innerHeight && rc.top > 260); onToggle(); };
  return (
    <span style={{ position: "relative" }}>
      <button data-testid={`agent-${r.id}`} aria-expanded={open} aria-controls={id} onClick={toggle} title="Show this agent's role"
        style={{ display: "inline-flex", alignItems: "center", gap: 6, border: `1px solid ${open ? "#93C5FD" : v("line")}`, background: open ? v("primary-soft") : v("surface"),
          borderRadius: 999, padding: "3px 10px 3px 11px", fontSize: 13, fontWeight: 600, color: v("ink"), cursor: "pointer" }}>
        {r.label}
        <span aria-hidden="true" style={{ width: 15, height: 15, borderRadius: 999, border: `1.5px solid ${v("muted")}`, color: v("muted"), fontSize: 10, fontWeight: 800, display: "inline-flex", alignItems: "center", justifyContent: "center", fontStyle: "italic", fontFamily: "Georgia, serif" }}>i</span>
      </button>
      {open && (
        <div id={id} role="dialog" aria-label={`${r.label}: role`} data-testid={`agent-pop-${r.id}`}
          style={{ ...card, position: "absolute", zIndex: 20, ...(up ? { bottom: "calc(100% + 6px)" } : { top: "calc(100% + 6px)" }), left: 0, width: 300, padding: "10px 12px", boxShadow: "0 8px 24px rgba(15,23,42,.14)", display: "grid", gap: 6 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, justifyContent: "space-between" }}>
            <b style={{ fontSize: 13.5 }}>{r.label}</b>
            <button onClick={onToggle} aria-label="Close" style={{ ...linkBtn, textDecoration: "none", color: v("muted"), fontSize: 16, lineHeight: 1 }}>×</button>
          </div>
          {g?.role
            ? <div style={{ display: "grid", gap: 3 }}><span style={P}>{g.role}</span><span style={{ display: "flex", gap: 6, alignItems: "center", ...MUTED }}><OriginTag origin="observed" />role recorded by the council framework</span></div>
            : <span style={MUTED}>No role is recorded for this agent.</span>}
          {r.sub && <div style={{ ...MUTED, color: v("ink") }}><span style={{ color: v("muted") }}>In this run: </span>{r.sub}</div>}
          {g?.final_label && <div style={{ ...MUTED, color: v("ink") }}><span style={{ color: v("muted") }}>Exported final label: </span>{g.final_label}</div>}
          {note && <div style={{ ...MUTED, borderTop: `1px solid ${v("line")}`, paddingTop: 6 }}>{note}</div>}
        </div>
      )}
    </span>
  );
}

/* ---------- overview summary ---------- */

function Block({ title, children, testid, action }) {
  return (
    <div data-testid={testid} style={{ display: "grid", gap: 6, alignContent: "start", minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8 }}><span style={eyebrow}>{title}</span>{action}</div>
      {children}
    </div>
  );
}

function NumberLine({ rows }) {
  const pts = rows.map(r => ({ ...r, x: Number(r.value) })).filter(r => Number.isFinite(r.x));
  if (pts.length < 2) return null;
  const lo = Math.min(...pts.map(p => p.x)), hi = Math.max(...pts.map(p => p.x)), pad = (hi - lo) * 0.12 || 0.01;
  const W = 280, X = x => 14 + ((x - (lo - pad)) / (hi - lo + 2 * pad)) * (W - 28);
  const reading = pts.find(p => p.gap == null);
  return (
    <svg viewBox={`0 0 ${W} 46`} width="100%" style={{ maxWidth: W, display: "block" }} role="img"
      aria-label={pts.map(p => `${p.label} ${p.value}${p.gap ? `, gap ${p.gap}` : ""}`).join("; ")}>
      <line x1={10} x2={W - 10} y1={24} y2={24} stroke="#CBD5E1" strokeWidth={2} />
      {reading && pts.filter(p => p !== reading).map(p => (
        <line key={`g${p.label}`} x1={X(reading.x)} x2={X(p.x)} y1={24} y2={24} stroke={p.closer ? "#16A34A" : "#94A3B8"} strokeWidth={4} strokeLinecap="round" />
      ))}
      {pts.map(p => {
        const isR = p === reading;
        return (
          <g key={p.label}>
            <circle cx={X(p.x)} cy={24} r={isR ? 6 : 4.5} fill={isR ? "#0F172A" : p.closer ? "#16A34A" : "#64748B"} stroke="#fff" strokeWidth={1.5} />
            <text x={X(p.x)} y={isR ? 11 : 42} textAnchor="middle" fontSize={10.5} fontWeight={isR ? 700 : 500} fill={isR ? "#0F172A" : "#475569"}>{p.value}</text>
          </g>
        );
      })}
    </svg>
  );
}

export function PlainSummary({ b, guide, onOpenFinding }) {
  const ov = guide?.overview;
  if (!ov) return null;
  const fd = (b.positions?.observations ?? []).find(o => o.kind === "final_decision");
  const prio = id => b.flags.find(f => f.id === id)?.priority;
  const seeFinding = id => id && prio(id) != null &&
    <button style={{ ...linkBtn, fontSize: 12 }} data-testid={`summary-finding-${id}`} onClick={() => onOpenFinding(id)}>Finding #{prio(id)}</button>;
  const review = fd?.review_decision;
  return (
    <section data-testid="plain-summary" aria-label="Summary" style={{ ...card, padding: "14px 16px", display: "grid", gap: 14 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))", gap: "14px 22px" }}>
        <Block title="What was diagnosed" testid="summary-subject">
          <b style={{ fontSize: 16, lineHeight: 1.25 }}>{ov.subject.title}</b>
          <p style={{ ...P, color: v("muted"), fontSize: 12.5 }}>{ov.subject.text}</p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>{ov.subject.readings.map(x => <span key={x} style={{ fontSize: 11.5, background: v("soft"), borderRadius: 4, padding: "1px 6px", color: "#334155", whiteSpace: "nowrap" }}>{x}</span>)}</div>
        </Block>
        <Block title="Final system decision" testid="summary-decision">
          {fd ? <>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
              <b style={{ fontSize: 16, lineHeight: 1.25 }}>{fd.recorded_label}</b>
              {fd.confidence != null && <span style={{ fontSize: 12.5, color: v("muted") }}>confidence {fd.confidence} ({Math.round(fd.confidence * 100)}%)</span>}
            </div>
            {review && <span><Chip tone={/HUMAN_REVIEW/.test(review) ? "warning" : "muted"} title={review}>{/REQUIRES_HUMAN_REVIEW/.test(review) ? "Requires human review" : review}</Chip></span>}
            {ov.decision?.text && <p style={{ ...P, fontSize: 12.5, color: v("muted") }}>{ov.decision.text}</p>}
            <span style={{ display: "flex", alignItems: "center", gap: 6, ...MUTED }}><OriginTag origin={fd.origin} />Final Coordinator record (framework)</span>
          </> : <p style={{ ...P, color: v("muted") }}>No final decision is recorded.</p>}
        </Block>
        <Block title="Main divergence" testid="summary-divergence" action={seeFinding(ov.divergence?.finding)}>
          <p style={P}>{ov.divergence?.text}</p>
        </Block>
        <Block title="What the numbers show" testid="summary-numbers" action={seeFinding(ov.numbers?.finding)}>
          <NumberLine rows={ov.numbers.rows} />
          <div style={{ display: "grid", gap: 1 }}>
            {ov.numbers.rows.filter(r => r.gap).map(r => (
              <span key={r.label} style={{ fontSize: 12, color: r.closer ? "var(--be-success-ink)" : v("muted"), fontWeight: r.closer ? 650 : 400 }}>{r.label} {r.value} · gap {r.gap}{r.closer ? " (closer)" : ""}</span>
            ))}
          </div>
          <p style={{ ...P, fontSize: 12.5 }}>{ov.numbers.text}</p>
        </Block>
      </div>
      <div style={{ borderTop: `1px solid ${v("line")}`, paddingTop: 10, display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px 16px" }}>
        <AgentChips b={b} guide={guide} />
        <span style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 6, ...MUTED }}><OriginTag origin={guide.origin} />plain-language summary of the findings; values from the trace</span>
      </div>
    </section>
  );
}

/* ---------- finding cards ---------- */

const VERDICT = { yes: ["success", "Yes"], no: ["danger", "No"], closer: ["success", "Closer"], note: ["muted", null] };

export function PlainFinding({ x }) {
  const cmp = x.compare;
  return (
    <div data-testid="finding-plain" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: "10px 22px", marginTop: 8, alignItems: "start" }}>
      <div style={{ display: "grid", gap: 8, minWidth: 0 }}>
        <p style={P}>{x.what}</p>
        {x.who?.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 5, alignItems: "center" }} data-testid="finding-who">
            <span style={{ ...eyebrow, fontSize: 10.5, marginRight: 2 }}>Involved</span>
            {x.who.map((w, i) => (
              <span key={i} style={{ fontSize: 12, border: `1px solid ${v("line")}`, borderRadius: 6, padding: "1px 7px", background: w.name === "Framework" ? v("soft") : v("surface") }}>
                <b style={{ fontWeight: 650 }}>{w.name}</b><span style={{ color: v("muted") }}> · {w.how}</span>
              </span>
            ))}
          </div>
        )}
        {cmp?.rows?.length > 0 && (
          <table data-testid="finding-compare" style={{ borderCollapse: "collapse", fontSize: 12.5, width: "100%", maxWidth: 520 }}>
            <thead><tr>{cmp.columns.map(c => <th key={c} style={{ textAlign: "left", fontWeight: 600, color: v("muted"), fontSize: 11.5, padding: "3px 8px", borderBottom: `1px solid ${v("line")}` }}>{c}</th>)}</tr></thead>
            <tbody>
              {cmp.rows.map((r, i) => {
                const vd = VERDICT[r.verdict];
                const lastIsVerdict = cmp.columns.length > r.cells.length;
                return (
                  <tr key={i} style={{ borderBottom: `1px solid ${v("soft")}`, background: r.verdict === "closer" ? "#F0FDF4" : r.verdict === "no" && !lastIsVerdict ? "#FEF2F2" : undefined }}>
                    {r.cells.map((c, j) => <td key={j} style={{ padding: "3px 8px", fontWeight: j === 0 ? 600 : 400, fontVariantNumeric: "tabular-nums" }}>{c}</td>)}
                    {lastIsVerdict && <td style={{ padding: "3px 8px" }}>{vd?.[1] ? <Chip tone={vd[0]}>{vd[1]}</Chip> : null}</td>}
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      <div style={{ display: "grid", gap: 8, minWidth: 0 }}>
        {x.why && <div><div style={{ ...eyebrow, fontSize: 10.5, marginBottom: 2 }}>Why it matters</div><p style={P}>{x.why}</p></div>}
        {x.uncertainty && (
          <div data-testid="finding-uncertainty" style={{ background: "#F8FAFC", border: `1px dashed #CBD5E1`, borderRadius: 6, padding: "6px 9px" }}>
            <div style={{ ...eyebrow, fontSize: 10.5, marginBottom: 2, color: "#475569" }}>What we can't say</div>
            <p style={{ ...P, fontSize: 12.5, color: "#334155" }}>{x.uncertainty}</p>
          </div>
        )}
      </div>
    </div>
  );
}
