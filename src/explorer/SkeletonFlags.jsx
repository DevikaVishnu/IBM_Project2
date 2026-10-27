import { useState } from "react";
import { Chip, Empty, Excerpt, OriginTag, Section, card, eyebrow, fmt, linkBtn, mono, v } from "./theme.jsx";

const KIND_LABEL = { model_call: "model call", tool_call: "tool call", framework_eviction: "framework eviction", check: "check (no LLM call)" };
const agentName = id => (id === "$unresolved" ? "unresolved" : id === "$not_reconstructed" ? "not reconstructed" : String(id ?? "").replace(/^agent:|^role:/, ""));

export function SkeletonPanel({ b, onShowColumn }) {
  const sk = b.skeleton;
  const [kind, setKind] = useState("all");
  if (!sk || !b.layers.skeleton) return <Empty testid="skeleton-empty">The skeleton is not available for this trace.</Empty>;
  const kinds = [...new Set(sk.events.map(e => e.kind))];
  const rows = sk.events.filter(e => kind === "all" || e.kind === kind);
  const cols = new Set((b.matrix?.columns ?? []).map(c => c.id));
  const dl = sk.delivery;
  return (
    <div style={{ display: "grid", gap: 14 }}>
      <Section title="Agents" origin={sk.origin} testid="skeleton-agents">
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          {sk.agents.map(a => (
            <div key={a.id} style={{ border: `1px solid ${v("line")}`, borderRadius: 8, padding: "8px 12px", minWidth: 180, background: a.kind === "unresolved" ? "#F8FAFC" : v("surface") }}>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}><b style={{ ...mono, fontSize: 13 }}>{a.label}</b><OriginTag origin={a.origin} /></div>
              <div style={{ fontSize: 12.5, color: v("muted"), marginTop: 2 }}>{a.sub}{a.parent ? ` · parent ${agentName(a.parent)}` : ""}{a.status ? ` · status ${a.status}` : ""}</div>
              {a.cite && <div style={{ fontSize: 12, color: v("muted"), marginTop: 2 }}>cited L{a.cite.line}</div>}
            </div>
          ))}
        </div>
        {sk.handoffs.length > 0 && (
          <div style={{ marginTop: 12, fontSize: 13, lineHeight: 1.6 }}>
            <div style={{ ...eyebrow, marginBottom: 4 }}>Handoffs</div>
            {sk.handoffs.map(h => <div key={`${h.from}-${h.to}`}>{h.from.replace(/^ev:llm:/, "call ")} → {h.to.replace(/^ev:llm:/, "call ")} <span style={{ color: v("muted") }}>· {h.via}</span> <OriginTag origin={h.origin} /></div>)}
          </div>
        )}
      </Section>
      {dl && (
        <Section title="Delivery (from §14)" origin="hand-reconstructed" testid="skeleton-delivery">
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, lineHeight: 1.6 }}>
            {dl.delivered.map(d => <li key={d.item}><b>{b.evidence[d.item]?.label ?? d.item}</b> → {d.to.map(t => t.replace(/^gk:/, "")).join(", ")} <span style={{ color: v("muted") }}>({d.lines})</span></li>)}
            {dl.not_delivered.map(d => <li key={d.item}><b>{b.evidence[d.item]?.label ?? d.item}</b> → <Chip tone="danger">not delivered</Chip> to {d.to.map(t => t.replace(/^gk:/, "")).join(", ")} <span style={{ color: v("muted") }}>· coverage {d.coverage}</span></li>)}
          </ul>
        </Section>
      )}
      <Section title={`Events (${rows.length})`} origin={sk.origin} testid="skeleton-events"
        right={<label style={{ fontSize: 13, color: v("muted") }}>Kind{" "}
          <select value={kind} onChange={e => setKind(e.target.value)} style={{ fontSize: 13, padding: "3px 6px", borderRadius: 6, border: `1px solid ${v("line")}` }}>
            <option value="all">all</option>{kinds.map(k => <option key={k} value={k}>{KIND_LABEL[k] ?? k}</option>)}
          </select></label>}>
        <div style={{ maxHeight: 520, overflow: "auto", border: `1px solid ${v("line")}`, borderRadius: 8 }} tabIndex={0} role="region" aria-label="Event table">
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead style={{ position: "sticky", top: 0, background: v("canvas") }}>
              <tr>{["order", "steps", "kind", "agent", "label", "origin", ""].map(h => <th key={h} style={{ textAlign: "left", padding: "6px 10px", fontSize: 11, textTransform: "uppercase", letterSpacing: 0.5, color: v("muted"), borderBottom: `1px solid ${v("line")}` }}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map(e => (
                <tr key={e.id} style={{ borderBottom: `1px solid ${v("soft")}` }}>
                  <td style={{ padding: "5px 10px", ...mono }}>{e.order}</td>
                  <td style={{ padding: "5px 10px", ...mono }}>{e.steps[0] === e.steps[1] ? e.steps[0] : `${e.steps[0]}–${e.steps[1]}`}</td>
                  <td style={{ padding: "5px 10px" }}>{KIND_LABEL[e.kind] ?? e.kind}</td>
                  <td style={{ padding: "5px 10px", ...mono }}>{agentName(e.agent)}</td>
                  <td style={{ padding: "5px 10px" }}>{e.label}{e.phase ? <span style={{ color: v("muted") }}> · {e.phase}</span> : null}{e.produces ? <span style={{ color: v("muted") }}> · produces {e.produces}</span> : null}{e.tokens ? <span style={{ color: v("muted") }}> · {e.tokens}</span> : null}</td>
                  <td style={{ padding: "5px 10px" }}><OriginTag origin={e.origin} /></td>
                  <td style={{ padding: "5px 10px" }}>{cols.has(e.id) && <button style={linkBtn} onClick={() => onShowColumn(e.id)}>matrix</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {sk.skipped?.length > 0 && (
          <details style={{ marginTop: 10 }}>
            <summary style={{ fontSize: 13, color: v("muted"), cursor: "pointer" }}>Records the adapter did not represent ({sk.skipped.length} kinds)</summary>
            <ul style={{ margin: "6px 0 0", paddingLeft: 18, fontSize: 12.5, color: v("muted") }}>
              {sk.skipped.map((s, i) => <li key={i}><span style={mono}>{s.kind}</span>{s.steps.length ? ` · steps ${s.steps.join(", ")}` : ""}</li>)}
            </ul>
          </details>
        )}
      </Section>
    </div>
  );
}

export function FlagsPanel({ b, selected, onSelect, onShowInMatrix }) {
  if (!b.layers.flags || !b.flags.length) return <Empty testid="flags-empty">No flags are annotated for this trace.</Empty>;
  return (
    <div data-testid="flags" style={{ display: "grid", gap: 12 }}>
      {b.flags.map(f => {
        const active = f.id === selected;
        return (
          <article key={f.id} data-testid={`flag-${f.id}`} aria-label={f.title} onClick={() => onSelect(f.id)}
            style={{ ...card, padding: "14px 16px", borderColor: active ? "#F59E0B" : undefined, boxShadow: active ? "0 0 0 2px #FDE68A" : "none" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <b style={{ color: "#B91C1C" }} aria-hidden="true">⚑</b>
              <h3 style={{ margin: 0, fontSize: 14.5, fontWeight: 700, color: v("ink") }}>{f.title}</h3>
              <OriginTag origin={f.origin} />
              <span style={{ ...mono, color: v("muted") }}>{f.kind}</span>
              {f.events.some(e => (b.matrix?.columns ?? []).some(c => c.id === e) || (b.skeleton?.events ?? []).some(x => x.id === e)) &&
                <button style={{ ...linkBtn, marginLeft: "auto" }} onClick={ev => { ev.stopPropagation(); onShowInMatrix(f); }}>Show in matrix</button>}
            </div>
            <p style={{ margin: "8px 0 0", fontSize: 13.5, lineHeight: 1.55, color: v("ink") }}>{f.text}</p>
            {f.caveat && <p style={{ margin: "6px 0 0", fontSize: 12.5, color: v("muted") }}>{f.caveat}</p>}
            {f.computed?.length > 0 && (
              <ul style={{ listStyle: "none", margin: "10px 0 0", padding: 0, display: "grid", gap: 4 }}>
                {f.computed.map((x, i) => <li key={i} style={{ display: "flex", gap: 8, alignItems: "baseline", fontSize: 13, lineHeight: 1.5 }}><OriginTag origin={x.origin} style={{ flex: "none" }} /><span>{x.text}</span></li>)}
              </ul>
            )}
            {active && f.evidence.length > 0 && (
              <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
                {f.evidence.map(id => {
                  const x = b.evidence[id];
                  return x && (
                    <div key={id}>
                      <div style={{ fontSize: 12.5, color: v("muted"), marginBottom: 4 }}>{x.label ?? `step ${x.step}`}{x.tool ? ` · ${x.tool}` : ""} <OriginTag origin={x.origin} /></div>
                      <Excerpt excerpt={x.excerpt} maxHeight={140} />
                    </div>
                  );
                })}
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}

export function Overview({ b, onTab, onOpenClaim, onOpenFlag }) {
  const sk = b.skeleton ?? {};
  const mx = b.matrix;
  const c = sk.counts ?? {};
  const results = {};
  for (const cl of b.claims) {
    const r = cl.o3?.status === "computed" ? cl.o3.comparison : cl.o3?.status ?? "none";
    results[r] = (results[r] ?? 0) + 1;
  }
  const delivered = b.claims.flatMap(cl => cl.links.map(l => l.delivery?.value).filter(Boolean));
  const agentRows = mx ? mx.rows.filter(r => r.kind !== "unresolved") : sk.agents ?? [];
  const tiles = [
    { label: b.trace.framework?.startsWith("ChatDev") ? "Roles" : "Agents", value: agentRows.length, origin: sk.origin ?? "observed", note: agentRows.map(r => r.label).join(", ") },
    { label: mx?.origin === "hand-reconstructed" ? "LLM calls" : "Model calls", value: c.model_calls ?? c.llm_calls ?? mx?.columns.length, origin: sk.origin ?? "observed",
      note: c.reconstructed_llm_calls != null ? `${c.reconstructed_llm_calls} reconstructed in §14` : c.unresolved_origin_events ? `${c.unresolved_origin_events} with unresolved origin` : null },
    { label: "Events", value: c.events ?? sk.events?.length, origin: sk.counts_origin ?? "computed", note: c.tool_events != null ? `${fmt(c.tool_events)} tool · ${fmt(c.eviction_events)} eviction` : null },
    { label: "Evidence items", value: c.evidence, origin: sk.counts_origin ?? "computed", note: c.entities != null ? `${c.entities} entities` : null },
    { label: "Deliveries", value: c.delivers, origin: sk.counts_origin ?? "computed", note: mx?.origin === "computed" ? "structural, byte-identical" : "from §14" },
    { label: "Claims", value: b.claims.length, origin: "hand-annotated", note: b.non_claims.length ? `+${b.non_claims.length} shown, not claims` : null },
    { label: "O3 computed", value: b.claims.filter(cl => cl.o3?.status === "computed").length, origin: "computed", note: `of ${b.claims.length} claims` },
    { label: "Flags", value: b.flags.length, origin: b.flags[0]?.origin ?? "hand-annotated" },
  ];
  const facts = b.facts.filter(f => !f.id.startsWith("lane:") && !f.handoff);
  const handoff = b.facts.find(f => f.handoff);
  return (
    <div data-testid="overview" style={{ display: "grid", gap: 14 }}>
      <div data-testid="tiles" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 10 }}>
        {tiles.map(t => (
          <div key={t.label} data-testid={`tile-${t.label}`} style={{ ...card, padding: "12px 14px", display: "flex", flexDirection: "column", gap: 4 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, justifyContent: "space-between" }}><span style={eyebrow}>{t.label}</span></div>
            <span style={{ fontSize: 26, fontWeight: 700, color: v("ink"), fontVariantNumeric: "tabular-nums", lineHeight: 1.1 }}>{t.value == null ? "—" : fmt(t.value)}</span>
            {t.note && <span style={{ fontSize: 12, color: v("muted"), lineHeight: 1.4 }}>{t.note}</span>}
            <OriginTag origin={t.origin} style={{ alignSelf: "flex-start", marginTop: 2 }} />
          </div>
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 14, alignItems: "start" }}>
        <Section title="Claims vs evidence" origin={b.claims.length ? "computed" : undefined} testid="overview-results"
          right={b.claims.length > 0 && <button style={linkBtn} onClick={() => onTab("claims")}>Open claims</button>}>
          {!b.claims.length ? <p style={{ margin: 0, fontSize: 13, color: v("muted") }}>Not annotated.</p> : (
            <>
              <ResultBar results={results} total={b.claims.length} />
              <ul style={{ listStyle: "none", margin: "10px 0 0", padding: 0, display: "grid", gap: 2 }}>
                {b.claims.map(cl => (
                  <li key={cl.id}>
                    <button className="be-hover" onClick={() => onOpenClaim(cl.id)} style={{ width: "100%", display: "flex", gap: 8, alignItems: "center", textAlign: "left", background: "none", border: "none", borderRadius: 6, padding: "5px 6px", cursor: "pointer", fontSize: 13, color: v("ink") }}>
                      <span style={{ flex: 1 }}>{cl.label}</span><ResultBadge cl={cl} />
                    </button>
                  </li>
                ))}
              </ul>
              <p style={{ margin: "8px 0 0", fontSize: 12, color: v("muted") }}>
                Claims and links are hand-annotated (illustrative, not gold). Delivery to the claiming call: {countBy(delivered)}.
              </p>
            </>
          )}
        </Section>
        <Section title="Flags" origin={b.flags.length ? b.flags[0].origin : undefined} testid="overview-flags" right={b.flags.length > 0 && <button style={linkBtn} onClick={() => onTab("flags")}>Open flags</button>}>
          {!b.flags.length ? <p style={{ margin: 0, fontSize: 13, color: v("muted") }}>None annotated.</p> : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 2 }}>
              {b.flags.map(f => (
                <li key={f.id}><button className="be-hover" onClick={() => onOpenFlag(f.id)} style={{ width: "100%", display: "flex", gap: 8, textAlign: "left", background: "none", border: "none", borderRadius: 6, padding: "5px 6px", cursor: "pointer", fontSize: 13, color: v("ink") }}>
                  <b style={{ color: "#B91C1C" }} aria-hidden="true">⚑</b><span>{f.title}</span></button></li>
              ))}
            </ul>
          )}
        </Section>
        {handoff && (
          <Section title={handoff.title} origin="hand-annotated" testid="overview-handoff">
            <p style={{ margin: "0 0 8px", fontSize: 13, lineHeight: 1.5 }}>
              Description <span style={{ ...mono, background: v("canvas"), padding: "1px 4px", borderRadius: 4 }}>“{handoff.handoff.description}”</span>{" "}
              <Chip tone="success">delivered byte-identical</Chip> <OriginTag origin="computed" /> at call {handoff.handoff.received_by.replace(/^ev:llm:/, "")}.
            </p>
            <div style={{ ...eyebrow, margin: "8px 0 4px" }}>Not in the description, though root had them</div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, lineHeight: 1.6 }}>
              {handoff.handoff.not_in_description.map(it => <li key={it.label}>{it.label} <span style={{ color: v("muted") }}>({it.where}{it.check ? `; ${it.check}` : ""})</span></li>)}
            </ul>
            <p style={{ margin: "8px 0 0", fontSize: 12.5, color: v("muted") }}>{handoff.text}</p>
            {handoff.handoff.observed.map((o, i) => <p key={i} style={{ margin: "6px 0 0", fontSize: 12.5, display: "flex", gap: 6, alignItems: "baseline" }}><OriginTag origin={o.origin} /> <span>{o.text}</span></p>)}
          </Section>
        )}
        <Section title="Facts" testid="overview-facts">
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8 }}>
            {facts.map(f => (
              <li key={f.id} style={{ fontSize: 13, lineHeight: 1.5, display: "grid", gap: 3, ...(f.discrepancy ? { background: "#FFFBEB", border: "1px solid #FDE68A", borderRadius: 6, padding: "6px 8px" } : {}) }}>
                <span style={{ display: "flex", gap: 6, alignItems: "center" }}><OriginTag origin={f.origin} /><b>{f.title}</b>{f.discrepancy && <Chip tone="warning">discrepancy</Chip>}</span>
                <span>{f.text}</span>
              </li>
            ))}
          </ul>
        </Section>
        <Section title="Layers in this bundle" testid="overview-layers">
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexWrap: "wrap", gap: 6 }}>
            {Object.entries(b.layers).map(([k, on]) => <li key={k}><Chip tone={on ? "primary" : "muted"} title={on ? "present" : "not available"}>{on ? "✓" : "–"} {k}</Chip></li>)}
          </ul>
          {mx && (
            <p style={{ margin: "10px 0 0", fontSize: 13 }}>
              <button style={linkBtn} onClick={() => onTab("matrix")}>Open the interaction matrix</button> · {mx.rows.length} rows × {mx.columns.length} columns · {(mx.overlays ?? []).length} markers
            </p>
          )}
        </Section>
      </div>
    </div>
  );
}

function countBy(values) {
  if (!values.length) return "not recorded";
  const m = {};
  values.forEach(x => { m[x] = (m[x] ?? 0) + 1; });
  return Object.entries(m).map(([k, n]) => `${n} ${k}`).join(", ");
}

const BAR = { AGREES: "#16A34A", DIFFERS_FROM_DIRECT: "#DC2626", "rule-dependent": "#F59E0B", NOT_APPLICABLE: "#94A3B8", UNKNOWN: "#CBD5E1", "not computable": "#E2E8F0", UNRESOLVED: "#CBD5E1", none: "#F1F5F9" };
const LBL = { AGREES: "agrees", DIFFERS_FROM_DIRECT: "differs", "rule-dependent": "rule-dependent", NOT_APPLICABLE: "not compared", UNKNOWN: "unknown", "not computable": "not computable", UNRESOLVED: "unresolved", none: "no result" };
function ResultBar({ results, total }) {
  const entries = Object.entries(results);
  return (
    <div>
      <div role="img" aria-label={entries.map(([k, n]) => `${n} ${LBL[k] ?? k}`).join(", ")} style={{ display: "flex", height: 12, borderRadius: 6, overflow: "hidden", border: `1px solid ${v("line")}` }}>
        {entries.map(([k, n]) => <span key={k} style={{ width: `${(100 * n) / total}%`, background: BAR[k] ?? "#CBD5E1", borderRight: "2px solid #fff" }} />)}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 14px", marginTop: 6, fontSize: 12.5, color: v("muted") }}>
        {entries.map(([k, n]) => <span key={k} style={{ display: "inline-flex", gap: 5, alignItems: "center" }}><span style={{ width: 9, height: 9, borderRadius: 2, background: BAR[k] ?? "#CBD5E1" }} />{n} {LBL[k] ?? k}</span>)}
      </div>
    </div>
  );
}
function ResultBadge({ cl }) {
  const r = cl.o3?.status === "computed" ? cl.o3.comparison : cl.o3?.status ?? "none";
  const hand = cl.o3?.hand_comparison;
  return <span style={{ display: "inline-flex", gap: 4 }}><Chip tone={{ AGREES: "success", DIFFERS_FROM_DIRECT: "danger", "rule-dependent": "warning" }[r] ?? "muted"}>{LBL[r] ?? r}</Chip>{hand && <Chip tone="warning" title="hand comparison (hand-annotated)">hand: {hand}</Chip>}</span>;
}
