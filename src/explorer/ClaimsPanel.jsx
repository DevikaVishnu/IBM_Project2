import { Chip, DELIVERY, Empty, Excerpt, OriginTag, ResultChip, card, claimResult, eyebrow, linkBtn, mono, v } from "./theme.jsx";

// Claims & evidence: a claim list and, for the selected claim, its chain
//   exact words → proposition → state → evidence → delivered to the claiming call? → O3 result.

const agentName = id => (id === "$unresolved" ? "unresolved speaker" : String(id ?? "").replace(/^agent:|^role:/, ""));

function Step({ n, title, origin, children, testid }) {
  return (
    <li data-testid={testid} style={{ display: "grid", gridTemplateColumns: "28px minmax(0, 1fr)", columnGap: 12 }}>
      <div aria-hidden="true" style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
        <span style={{ width: 24, height: 24, borderRadius: 999, background: v("primary-soft"), color: "#1D4ED8", fontSize: 12, fontWeight: 700,
          display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid #BFDBFE" }}>{n}</span>
        <span style={{ flex: 1, width: 2, background: v("line"), marginTop: 4 }} />
      </div>
      <div style={{ paddingBottom: 18, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
          <h4 style={{ margin: 0, fontSize: 13, fontWeight: 700, color: v("ink") }}>{title}</h4>
          {origin && <OriginTag origin={origin} />}
        </div>
        {children}
      </div>
    </li>
  );
}

const p = { margin: "0 0 6px", fontSize: 13, lineHeight: 1.55, color: v("ink") };

function Chain({ b, c, onShowInMatrix }) {
  const prop = b.propositions.find(x => x.id === c.proposition);
  const o3 = c.o3 ?? {};
  const where = c.step != null ? `model call ${c.event.replace(/^ev:llm:/, "")}, output at step ${c.step}` : `${c.event.replace(/^gk:/, "")}, log line ${c.line}`;
  return (
    <div data-testid="claim-chain" style={{ ...card, padding: "16px 18px" }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
        <div style={{ minWidth: 0, flex: "1 1 300px" }}>
          <div style={eyebrow}>Claim chain</div>
          <h2 style={{ margin: "2px 0 0", fontSize: 17, fontWeight: 700, color: v("ink") }}>{c.label}</h2>
        </div>
        <ResultChip value={claimResult(c)} style={{ fontSize: 13 }} />
        {onShowInMatrix && <button style={linkBtn} onClick={() => onShowInMatrix(c)}>Show in matrix</button>}
      </div>
      <ol style={{ listStyle: "none", margin: 0, padding: 0 }}>
        <Step n={1} title="Exact words" origin={c.origin} testid="chain-words">
          <blockquote style={{ margin: 0, padding: "8px 12px", borderLeft: "3px solid #F59E0B", background: "#FFFBEB", borderRadius: 6, ...mono, fontSize: 13, lineHeight: 1.55, color: v("ink"), whiteSpace: "pre-wrap" }}>{c.words}</blockquote>
          <p style={{ ...p, marginTop: 6, color: v("muted") }}>
            {where} · speaker <b style={{ color: v("ink") }}>{agentName(c.speaker)}</b> <OriginTag origin={c.speaker_origin} style={{ marginLeft: 4 }} />
          </p>
        </Step>
        <Step n={2} title="Proposition" origin={prop?.origin} testid="chain-proposition">
          <p style={p}>{prop?.form ?? <i>Not annotated</i>}</p>
        </Step>
        <Step n={3} title="State the claim expresses" origin={c.state?.origin} testid="chain-state">
          <p style={p}><Chip tone={c.state?.value === "TRUE" ? "primary" : c.state?.value === "FALSE" ? "danger" : "warning"}>{c.state?.value ?? "Not annotated"}</Chip>
            {c.state?.value === "UNCERTAIN" && <span style={{ color: v("muted"), marginLeft: 8 }}>hedged by the speaker</span>}</p>
        </Step>
        <Step n={4} title="Evidence" origin={c.links.length ? "hand-annotated" : undefined} testid="chain-evidence">
          {!c.links.length && <p style={{ ...p, color: v("muted") }}>No direct evidence is annotated for this claim.</p>}
          {c.links.map((l, i) => {
            const x = b.evidence[l.evidence];
            return (
              <div key={i} style={{ border: `1px solid ${v("line")}`, borderRadius: 8, padding: "10px 12px", marginBottom: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 6, fontSize: 13 }}>
                  <Chip tone={l.relation === "contradicted_by" ? "danger" : "primary"}>{l.relation}</Chip>
                  <b>{l.step_label ?? (x?.step != null ? `step ${x.step}` : x?.lines ? `L${x.lines.join(", L")}` : "")}</b>
                  {x?.tool && <span style={mono}>{x.tool}</span>}
                  {x?.label && <span>{x.label}</span>}
                  {l.rule_dependent && <Chip tone="warning">rule-dependent</Chip>}
                  {x && <OriginTag origin={x.origin} style={{ marginLeft: "auto" }} />}
                </div>
                {l.grounds && <p style={{ ...p, color: v("muted"), fontSize: 12 }}>{l.grounds}</p>}
                {l.grounding && <p style={{ ...p, color: v("muted"), fontSize: 12 }}>{l.grounding}</p>}
                <Excerpt excerpt={x?.excerpt} maxHeight={180} />
              </div>
            );
          })}
        </Step>
        <Step n={5} title="Delivered to the claiming call?" origin={c.links.some(l => l.delivery) ? "computed" : undefined} testid="chain-delivery">
          {!c.links.some(l => l.delivery) && <p style={{ ...p, color: v("muted") }}>{c.links.length ? "Delivery is not recorded for this trace." : "No evidence to check."}</p>}
          {c.links.filter(l => l.delivery).map((l, i) => {
            const d = DELIVERY[l.delivery.value] ?? { tone: "muted", short: l.delivery.value, text: l.delivery.value };
            const x = b.evidence[l.evidence];
            return (
              <p key={i} data-delivery={l.delivery.value} style={{ ...p, display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
                <Chip tone={d.tone}>{d.short}</Chip>
                <span>{x?.step != null ? `Step ${x.step}` : l.evidence} → {l.delivery.to_event.replace(/^ev:llm:/, "call ")}: {d.text}.</span>
              </p>
            );
          })}
          {c.links.some(l => l.delivery) && <p style={{ ...p, fontSize: 12, color: v("muted") }}>Delivered means presence in the rendered input, not use.</p>}
        </Step>
        <Step n={6} title="Comparison with evidence (O3)" origin={o3.origin} testid="chain-o3">
          {o3.status === "computed" && (
            <>
              <p style={{ ...p, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <ResultChip value={o3.comparison} />
                <span>{o3.meaning}</span>
              </p>
              <p style={{ ...p, fontSize: 12, color: v("muted") }}>
                direct {o3.direct} · delivered direct {o3.delivered_direct} · testimonial {o3.testimonial} · {o3.operation}, computed from {o3.computed_from}
                {o3.fixture_expected && <> · matches the fixture's expected result ({o3.fixture_expected})</>}
              </p>
            </>
          )}
          {o3.status === "rule-dependent" && <p style={p}><ResultChip value="rule-dependent" /> <span style={{ marginLeft: 6 }}>{o3.reason}</span></p>}
          {o3.status === "not computable" && <p style={p}><ResultChip value="not computable" /> <span style={{ marginLeft: 6 }}>{o3.reason}</span></p>}
          {!o3.status && <p style={{ ...p, color: v("muted") }}>Not annotated.</p>}
          {o3.hand_comparison && (
            <p data-testid="hand-comparison" style={{ ...p, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginTop: 8 }}>
              <span style={{ fontWeight: 650 }}>Hand comparison:</span> <ResultChip value={o3.hand_comparison.startsWith("DIFFERS") ? "DIFFERS" : o3.hand_comparison.startsWith("AGREES") ? "AGREES" : o3.hand_comparison} />
              <span>{o3.hand_comparison}</span> <OriginTag origin="hand-annotated" />
            </p>
          )}
        </Step>
      </ol>
      {(c.notes?.length > 0 || c.fixture) && (
        <div style={{ borderTop: `1px solid ${v("line")}`, paddingTop: 10 }}>
          <div style={eyebrow}>Annotation notes</div>
          <ul style={{ margin: "6px 0 0", paddingLeft: 18, fontSize: 13, lineHeight: 1.55, color: v("ink") }}>
            {c.notes?.map((n, i) => <li key={i}>{n}</li>)}
            {c.fixture && <li>Source fixture: <span style={mono}>{c.fixture.file}</span> ({c.fixture.claim})</li>}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function ClaimsPanel({ b, selected, onSelect, onShowInMatrix, narrow }) {
  if (!b.layers.claims || !b.claims.length) {
    return <Empty testid="claims-empty">Not annotated. This trace has no hand-annotated claims, so no claim chain or comparison is shown.</Empty>;
  }
  const c = b.claims.find(x => x.id === selected) ?? b.claims[0];
  const holderless = b.propositions.filter(pr => !b.claims.some(cl => cl.proposition === pr.id));
  return (
    <div style={{ display: "grid", gridTemplateColumns: narrow ? "minmax(0,1fr)" : "minmax(260px, 340px) minmax(0, 1fr)", gap: 14, alignItems: "start" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <nav aria-label="Claims" style={{ ...card, padding: 6 }}>
          <div style={{ ...eyebrow, padding: "8px 10px 4px", display: "flex", alignItems: "center", gap: 8 }}>Claims ({b.claims.length}) <OriginTag origin="hand-annotated" /></div>
          <ul data-testid="claim-list" style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {b.claims.map(x => {
              const active = x.id === c.id;
              return (
                <li key={x.id}>
                  <button className="be-hover" data-testid={`claim-${x.id}`} aria-current={active ? "true" : undefined} onClick={() => onSelect(x.id)}
                    style={{ width: "100%", textAlign: "left", border: "none", borderRadius: 7, cursor: "pointer", padding: "9px 10px", display: "flex", gap: 8, alignItems: "center",
                      background: active ? v("primary-soft") : "transparent", boxShadow: active ? "inset 3px 0 0 #2563EB" : "none", color: v("ink") }}>
                    <span style={{ flex: 1, minWidth: 0, fontSize: 13, fontWeight: active ? 650 : 500, lineHeight: 1.4 }}>{x.label}
                      <span style={{ display: "block", fontSize: 12, color: v("muted"), fontWeight: 400 }}>{x.step != null ? `step ${x.step}` : `L${x.line}`} · {agentName(x.speaker)} · state {x.state?.value}</span>
                    </span>
                    <ResultChip value={claimResult(x)} />
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
        {b.non_claims.length > 0 && (
          <section aria-label="Not claims" style={{ ...card, padding: "10px 14px" }}>
            <div style={{ ...eyebrow, marginBottom: 6 }}>Shown, not claims</div>
            {b.non_claims.map((n, i) => (
              <div key={i} style={{ fontSize: 13, lineHeight: 1.5, marginBottom: 8 }}>
                <div style={{ fontWeight: 650 }}>{n.label}</div>
                <div style={{ color: v("muted") }}>{n.reason}</div>
              </div>
            ))}
          </section>
        )}
        {holderless.length > 0 && (
          <section aria-label="Propositions without a claim" data-testid="holderless" style={{ ...card, padding: "10px 14px" }}>
            <div style={{ ...eyebrow, marginBottom: 6, display: "flex", gap: 8, alignItems: "center" }}>Propositions with no holder</div>
            {holderless.map(pr => (
              <div key={pr.id} style={{ fontSize: 13, lineHeight: 1.5, marginBottom: 8 }}>
                <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}><b>{pr.form}</b> <OriginTag origin={pr.origin} /></div>
                {pr.links.map((l, i) => <div key={i} style={{ color: v("muted") }}>{l.relation} {b.evidence[l.evidence]?.label ?? l.evidence}{l.grounding ? ` · ${l.grounding}` : ""}</div>)}
              </div>
            ))}
            <p style={{ margin: 0, fontSize: 12, color: v("muted") }}>No agent asserted these, so there is no state and no O3 comparison.</p>
          </section>
        )}
      </div>
      <Chain b={b} c={c} onShowInMatrix={onShowInMatrix} />
    </div>
  );
}
