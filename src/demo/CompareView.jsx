import { useRef, useState } from "react";
import run621 from "./data/aob-621.demo.json";
import run620 from "./data/aob-620f.demo.json";
import { Disclosure, HighlightedText, IdButton, Json, KV, LAYER, LayerTag, Mono, Note, Section, Segmented, Stat, T, eyebrow, panel } from "./ui.jsx";

// State-vs-evidence workflow over pre-built data (scripts/demo/build_demo_data.py): stored fixture
// objects, adapter output and computed comparison results, rendered as they are.  Nothing here
// derives a claim, proposition, state or link.

const RUNS = {
  "aob-621": { label: "621 · positive control", data: run621 },
  "aob-620f": { label: "620-fileobs · abstention control", data: run620 },
};
const fmt = n => n.toLocaleString("en-US");

function prepare(run) {
  const sem = run.fixture.semantic;
  return {
    run, sem, pl: run.fixture.profile_local, st: run.structural,
    tools: sem.evidence.filter(x => x.source === "tool"),
    answer: sem.evidence.find(x => x.source === "agent"),
    call: sem.events.find(e => typeof e.origin === "string" && e.origin.startsWith("agent:")),
    claim: sem.claims[0],
    state: sem.states[0],
    o3: run.comparison.find(c => c.rule === "O3")?.computed,
    cd: run.comparison.find(c => c.rule === "claim_delivery"),
    direct: sem.links.filter(l => l.relation === "supported_by" || l.relation === "contradicted_by"),
    delivers: sem.links.filter(l => l.relation === "delivers"),
  };
}
const PREP = Object.fromEntries(Object.entries(RUNS).map(([k, v]) => [k, prepare(v.data)]));

function FlowNode({ layer, eyebrowText, id, sub, active, onClick, testid, big }) {
  return (
    <button data-testid={testid} onClick={onClick} aria-pressed={active} aria-label={`${eyebrowText}: ${big ?? id}. ${sub}`}
      style={{ flex: 1, minWidth: 0, textAlign: "left", cursor: "pointer", fontFamily: T.sans,
        background: active ? LAYER[layer].tint : T.panel, borderStyle: "solid", borderWidth: active ? "4px 2px 2px" : "4px 1px 1px",
        borderColor: `${LAYER[layer].color} ${active ? T.focus : T.line} ${active ? T.focus : T.line}`,
        borderRadius: 6, padding: "8px 10px", display: "flex", flexDirection: "column", gap: 3 }}>
      <span style={{ ...eyebrow, color: LAYER[layer].color }}>{eyebrowText}</span>
      {big ? <span style={{ fontSize: 18, fontWeight: 700, color: T.ink }}>{big}</span>
        : <span style={{ fontFamily: T.mono, fontSize: 13, color: T.ink, wordBreak: "break-all" }}>{id}</span>}
      <span style={{ fontSize: 12.5, color: T.muted }}>{sub}</span>
    </button>
  );
}

function Edge({ label, layer, vertical }) {
  const c = layer ? LAYER[layer].color : T.faint;
  if (vertical) {
    return (
      <div aria-hidden="true" style={{ display: "flex", alignItems: "center", gap: 8, padding: "2px 0 2px 18px", fontSize: 12.5, color: c, fontWeight: 700 }}>
        <svg width="10" height="22"><line x1="5" y1="0" x2="5" y2="15" stroke={c} strokeWidth="2" strokeDasharray={layer === "structural" ? "3 2" : "none"} /><path d="M0,14 L5,22 L10,14 z" fill={c} /></svg>
        {label}
      </div>
    );
  }
  return (
    <div aria-hidden="true" style={{ width: 66, flex: "none", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 2 }}>
      <span style={{ fontSize: 12, color: c, fontWeight: 700 }}>{label}</span>
      <svg width="56" height="10"><line x1="0" y1="5" x2="47" y2="5" stroke={c} strokeWidth="2" strokeDasharray={layer === "structural" ? "3 2" : "none"} />
        <path d="M47,0 L56,5 L47,10 z" fill={c} /></svg>
    </div>
  );
}

// Observation-order strip: one tab stop, arrow keys move between events (roving tabindex).
function EventStrip({ p, sel, onSelect }) {
  const mapped = new Set(Object.values(p.st.event_map));
  const reverse = Object.fromEntries(Object.entries(p.st.event_map).map(([f, a]) => [a, f]));
  const refs = useRef([]);
  const tl = p.st.timeline;
  const activeIdx = Math.max(0, tl.findIndex(e => sel.type === "event" && (sel.id === e.id || sel.id === reverse[e.id])));
  const pick = i => { const e = tl[i]; onSelect({ type: "event", id: reverse[e.id] ?? e.id }); refs.current[i]?.focus(); };
  const onKey = (e, i) => {
    const k = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tl.length - 1 }[e.key];
    if (k !== undefined) { e.preventDefault(); pick(Math.max(0, Math.min(tl.length - 1, k))); }
  };
  return (
    <div role="toolbar" aria-label="Observed events in observation order" data-testid="event-strip" style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 44, overflowX: "auto", padding: "0 2px 2px" }}>
      {tl.map((e, i) => {
        const isMapped = mapped.has(e.id);
        const active = sel.type === "event" && (sel.id === e.id || sel.id === reverse[e.id]);
        const h = e.kind === "model_call" ? 32 : e.kind === "tool_call" ? 20 : 14;
        return (
          <button key={e.id} ref={el => { refs.current[i] = el; }} data-testid={`tl-${e.id}`} tabIndex={i === activeIdx ? 0 : -1}
            aria-label={`${e.id}, ${e.kind.replace("_", " ")}, ${e.origin}, seq ${e.start_seq} to ${e.end_seq}${isMapped ? ", in this comparison" : ""}`}
            aria-pressed={active} title={`${e.id} · ${e.origin} · seq ${e.start_seq}–${e.end_seq}`}
            onClick={() => pick(i)} onKeyDown={ev => onKey(ev, i)}
            style={{ flex: 1, minWidth: 9, height: h, padding: 0, cursor: "pointer", borderRadius: 2,
              border: active ? `3px solid ${LAYER.structural.color}` : e.kind === "framework_eviction" ? `2px solid ${T.faint}` : "none",
              background: e.kind === "framework_eviction" ? "transparent" : isMapped ? T.ink : e.kind === "model_call" ? "#8592a6" : "#c4ccd8" }} />
        );
      })}
    </div>
  );
}

function O3Inspector({ p, onSelect }) {
  const { o3, pl, cd, run } = p;
  const unknown = o3.comparison === "UNKNOWN";
  const rows = [["direct", o3.direct.value, o3.basis.direct], ["delivered direct", o3.delivered_direct.value, o3.basis.delivered_direct], ["other testifiers", o3.testimonial.value, o3.basis.testimonial]];
  return (
    <>
      <Section title="State vs evidence (O3)" layer="computed" testid="insp-o3">
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", columnGap: 10, marginBottom: 8 }}>
          <span data-testid="o3-comparison" style={{ fontSize: 24, fontWeight: 700, color: unknown ? T.muted : "#166534" }}>{o3.comparison}</span>
          <span style={{ fontSize: 13, color: T.muted }}>holder {o3.holder} at <Mono>{o3.event}</Mono> · basis {o3.basis.comparison}</span>
        </div>
        <table style={{ fontSize: 13, borderCollapse: "collapse", width: "100%" }}>
          <thead><tr style={{ color: T.faint, textAlign: "left" }}><th style={th}>component</th><th style={th}>value</th><th style={th}>basis</th></tr></thead>
          <tbody>{rows.map(([k, v, b]) => (
            <tr key={k}><td style={td}>{k}</td><td style={{ ...td, fontFamily: T.mono, fontWeight: 700, color: v === "TRUE" ? "#166534" : T.muted }}>{v}</td><td style={{ ...td, color: T.faint }}>{b}</td></tr>
          ))}</tbody>
        </table>
        {unknown
          ? <Note tone="caution" testid="o3-unknown-note">UNKNOWN: no stored direct evidence bears on this proposition, so the state cannot be compared with evidence. This is insufficient evidence, not a contradiction.</Note>
          : <Note>The holder's stated value agrees with stored direct evidence that was delivered to the model call. Agreement is not proof that the agent used it.</Note>}
      </Section>
      {o3.delivered_direct.counted.length > 0 && (
        <Section title="Counted direct evidence" layer="hand" testid="o3-counted">
          {o3.delivered_direct.counted.map(c => (
            <div key={c.target} style={{ fontSize: 13, lineHeight: 1.6 }}>
              <Mono>{c.relation}</Mono> → <IdButton id={c.target} onClick={() => onSelect({ type: "evidence", id: c.target })} />
              <div style={{ color: T.muted }}>Link hand-grounded in the fixture · delivery {c.o2_whole_item} (structural)</div>
            </div>
          ))}
        </Section>
      )}
      {unknown && (pl.link_assessment || []).length > 0 && (
        <Section title="Why no direct link" layer="hand">
          {pl.link_assessment.filter(a => a.outcome === "no link").map(a => (
            <div key={a.item} style={{ fontSize: 13, lineHeight: 1.5, marginBottom: 10 }}>
              <IdButton id={a.item} onClick={() => onSelect({ type: "evidence", id: a.item })} />
              <p style={{ color: T.text, margin: "4px 0 0" }}>{a.reason}</p>
            </div>
          ))}
        </Section>
      )}
      {cd && (
        <Section title="Claim delivery" layer="computed">
          <p style={{ fontSize: 13, margin: 0, lineHeight: 1.5 }}><b style={{ fontFamily: T.mono, color: T.muted }}>{cd.computed.value}</b>
            <span style={{ color: T.muted }}> — {cd.note || `delivered set checked: ${cd.computed.provenance.flatMap(x => x.delivered_set || []).join(", ")} (exact substring)`}</span></p>
        </Section>
      )}
      <Section title="Checks against hand-written expectations" layer="computed" testid="checks">
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {run.comparison.map((c, i) => (
            <li key={i} style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", columnGap: 8, fontSize: 13, padding: "3px 0" }}>
              <span><Mono>{c.rule}</Mono> <span style={{ color: T.faint, wordBreak: "break-all" }}>{Object.entries(c.inputs).map(([k, v]) => (k === "state" ? `state[${v}]` : v)).join(" · ")}</span></span>
              <b style={{ color: c.matches_expected ? "#166534" : "#b91c1c" }}>{c.matches_expected ? "✓ matches" : "✗ differs"}</b>
            </li>
          ))}
        </ul>
        <Note testid="basis-legend">Basis: <b>0.3</b> = rule stated in schema 0.3 · <b>PD</b> = profile-derived, a choice 0.3 does not make (agenttrace.compare/0.1) · <b>0.3+PD</b> = a 0.3 rule with a profile-derived condition.</Note>
        <Disclosure label="Show computed results JSON"><Json value={run.comparison} /></Disclosure>
      </Section>
    </>
  );
}
const th = { fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: 0.4, padding: "2px 8px 4px 0" };
const td = { padding: "3px 8px 3px 0", borderTop: `1px solid ${T.soft}` };

function EvidenceInspector({ p, id, onSelect }) {
  const x = p.sem.evidence.find(e => e.id === id);
  const t = p.run.texts[id];
  const dl = p.delivers.filter(l => l.target === id);
  const dir = p.direct.filter(l => l.target === id);
  return (
    <>
      <Section title={x.source === "agent" ? "Model output" : "Tool result"} layer="observed" testid="insp-evidence">
        <KV rows={[
          ["source", x.source],
          ["produced by", <IdButton key="p" id={x.produced_by} onClick={() => onSelect({ type: "event", id: x.produced_by })} />],
          ["raw locator", <Mono key="l" muted>{x.raw_ref.locator}</Mono>],
          ["sha256", <Mono key="s" muted>{t.text_sha256} ✓ verified</Mono>],
          ["length", `${fmt(t.length)} chars${t.complete ? "" : ` · display excerpt ${fmt(t.text.length)}`}`],
        ]} />
      </Section>
      {dl.length > 0 && (
        <Section title="Delivered to" layer="structural">
          {dl.map(l => {
            const rep = p.st.delivers_reproduced.find(r => r.fixture_link[1] === l.target && r.fixture_link[0] === l.source);
            return (
              <div key={l.raw_ref.locator} style={{ fontSize: 13, marginBottom: 8, lineHeight: 1.5 }}>
                <IdButton id={l.source} onClick={() => onSelect({ type: "event", id: l.source })} /> <span style={{ color: T.muted }}>byte-identical at</span>
                <div><Mono muted style={{ wordBreak: "break-all" }}>{l.raw_ref.locator}</Mono></div>
                {rep && <div style={{ color: rep.reproduced ? "#166534" : "#b91c1c" }}>{rep.reproduced ? `✓ reproduced by the adapter (${rep.adapter_link.join(" → ")})` : "✗ not reproduced by the adapter"}</div>}
              </div>
            );
          })}
          <Note>Delivered means present in the rendered input; it does not show the item was used.</Note>
        </Section>
      )}
      {dir.length > 0 && (
        <Section title="Direct link to a proposition" layer="hand">
          {dir.map(l => (
            <div key={l.source} style={{ fontSize: 13, lineHeight: 1.5 }}>
              <Mono>{l.source}</Mono> <Mono muted>{l.relation}</Mono> this item · {l.raw_ref.spans?.length ?? 0} spans
              <p style={{ color: T.muted, margin: "4px 0 0" }}>{l.raw_ref.grounds}</p>
            </div>
          ))}
        </Section>
      )}
      <Section title="Raw record"><Disclosure label="Show evidence JSON" testid="raw-json"><Json value={x} /></Disclosure></Section>
    </>
  );
}

function ClaimInspector({ p, onSelect }) {
  const c = p.claim;
  const prop = p.sem.propositions.find(x => x.id === c.proposition);
  return (
    <>
      <Section title="Claim" layer="hand" testid="insp-claim">
        <blockquote style={{ fontSize: 14, lineHeight: 1.5, color: T.ink, borderLeft: `4px solid ${LAYER.hand.color}`, padding: "2px 0 2px 10px", margin: "0 0 10px" }}>“{c.raw_ref.text}”</blockquote>
        <KV rows={[
          ["id", <Mono key="i">{c.id}</Mono>],
          ["evidence", <IdButton key="e" id={c.evidence} onClick={() => onSelect({ type: "evidence", id: c.evidence })} />],
          ["span", `[${c.raw_ref.span.join(", ")}) code points`],
          c.raw_ref.subject_context_text && ["subject context", `“${c.raw_ref.subject_context_text}”`],
        ]} />
      </Section>
      <Section title="Proposition" layer="hand"><Mono style={{ wordBreak: "break-word" }}>{prop?.form}</Mono></Section>
      <Section title="State" layer="hand">
        <KV rows={[["holder", p.o3.holder], ["event", <Mono key="e">{p.o3.event}</Mono>], ["value", <b key="v" style={{ fontFamily: T.mono }}>{p.state.value}</b>]]} />
        <Note>Grounded only by this claim; nothing is carried to other events.</Note>
      </Section>
      <Section title="Raw record"><Disclosure label="Show claim JSON"><Json value={{ claim: c, proposition: prop, state: p.state }} /></Disclosure></Section>
    </>
  );
}

function EventInspector({ p, id }) {
  const fx = p.sem.events.find(e => e.id === id);
  const adapterId = fx ? p.st.event_map[id] : id;
  const a = p.st.timeline.find(e => e.id === adapterId);
  return (
    <>
      {fx && (
        <Section title="Fixture event" layer="hand">
          <KV rows={[["origin", fx.origin], ["raw seq", fx.raw_ref.seq.join(", ")], fx.raw_ref.input_locator && ["input", <Mono key="i" muted>{fx.raw_ref.input_locator}</Mono>],
            fx.raw_ref.note && ["note", fx.raw_ref.note]]} />
        </Section>
      )}
      {a && (
        <Section title="Adapter event" layer="structural" testid="insp-event">
          <KV rows={[["id", <Mono key="i">{a.id}</Mono>], ["kind", a.kind.replace("_", " ")], ["origin", a.origin], ["raw seq", `${a.start_seq}–${a.end_seq}`],
            a.tool_call_id && ["tool_call_id", <Mono key="t" muted>{a.tool_call_id}</Mono>], a.origin_rule && ["origin basis", `${a.origin_basis} · ${a.origin_rule}`],
            a.kind === "model_call" && ["deliveries in", a.delivers_in]]} />
          {fx && p.st.event_map_notes[id] && <Note>{p.st.event_map_notes[id]}</Note>}
        </Section>
      )}
      <Section title="Raw record"><Disclosure label="Show event JSON"><Json value={{ fixture: fx ?? null, adapter: a ?? null }} /></Disclosure></Section>
    </>
  );
}

export default function CompareView({ layout }) {
  const [runKey, setRunKey] = useState("aob-621");
  const [sel, setSel] = useState({ type: "o3" });
  const [tab, setTab] = useState(0);
  const p = PREP[runKey];
  const fixed = layout.fixed;
  const vertical = !fixed;
  const tool = p.tools[Math.min(tab, p.tools.length - 1)];
  const toolText = p.run.texts[tool.id];
  const toolSpans = p.direct.filter(l => l.target === tool.id).flatMap(l => l.raw_ref.spans || []);
  const answerText = p.run.texts[p.answer.id];
  const checks = p.run.comparison.filter(c => c.matches_expected).length;
  const switchRun = k => { setRunKey(k); setSel({ type: "o3" }); setTab(0); };
  const title = sel.type === "o3" ? "O3 result" : sel.type === "claim" ? p.claim.id : sel.id;
  const paneH = fixed ? "100%" : "min(60vh, 520px)";

  return (
    <div data-testid="demo-view" style={{ display: "grid", gridTemplateColumns: layout.narrow ? "minmax(0, 1fr)" : `minmax(0, 1fr) ${fixed ? "clamp(340px, 26vw, 440px)" : "minmax(300px, 34%)"}`,
      gap: 12, padding: 12, height: fixed ? "100%" : "auto", boxSizing: "border-box", alignItems: "start" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 12, minHeight: 0, minWidth: 0, height: fixed ? "100%" : "auto" }}>
        <section aria-label="Comparison summary" style={{ ...panel, padding: "12px 16px" }}>
          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", columnGap: 12, rowGap: 8 }}>
            <h2 style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", columnGap: 10, margin: 0, fontWeight: 400 }}>
              <span style={{ fontSize: 16, fontWeight: 700, color: T.ink }}>State vs evidence · hand-grounded research example</span>
              <span style={{ fontSize: 13, color: T.muted }}>Real AssetOpsBench trace · <Mono muted style={{ wordBreak: "break-all" }}>{p.run.fixture.semantic.run.id}</Mono></span>
            </h2>
            <Segmented testid="run" label="Run" value={runKey} onChange={switchRun} options={Object.entries(RUNS).map(([k, v]) => ({ value: k, label: v.label }))} />
          </div>
          <p data-testid="handgrounded-banner" style={{ fontSize: 13, lineHeight: 1.5, color: T.text, background: LAYER.hand.tint, border: `1px solid ${LAYER.hand.color}55`, borderRadius: 6, padding: "6px 10px", margin: "8px 0 0" }}>
            <LayerTag kind="hand" /> The claim, proposition, state and direct links here were written by hand for runs 621 and 620-fileobs only.
            They are not generated for other traces, and the observation matrix never shows claims or states.
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", marginTop: 10 }}>
            <Stat label="Holder" value={p.o3.holder.replace("agent:", "")} note={p.o3.event} />
            <Stat label="Stated value" value={p.state.value} layer="hand" note="hand-grounded" />
            <Stat label="Direct evidence" value={p.o3.direct.value} layer="computed" />
            <Stat label="Comparison" value={p.o3.comparison} layer="computed" />
            <Stat label="Checks" value={`${checks}/${p.run.comparison.length}`} note="match expected" />
          </div>
        </section>

        <section aria-label="Evidence chain" style={{ ...panel, padding: "10px 16px" }}>
          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "baseline", columnGap: 12, marginBottom: 8 }}>
            <h2 style={{ fontSize: 14, fontWeight: 700, color: T.ink, margin: 0 }}>Evidence chain</h2>
            <span style={{ fontSize: 12.5, color: T.faint }}>delivered means present in the rendered input, not used</span>
          </div>
          <div data-testid="chain" style={{ display: "flex", flexDirection: vertical ? "column" : "row", alignItems: "stretch" }}>
            <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 4 }}>
              {p.tools.map((x, i) => (
                <FlowNode key={x.id} testid={`node-${x.id}`} layer="observed" eyebrowText="Tool result" id={x.id} active={sel.id === x.id}
                  sub={`seq ${x.raw_ref.seq} · ${fmt(p.run.texts[x.id].length)} chars`} onClick={() => { setSel({ type: "evidence", id: x.id }); setTab(i); }} />
              ))}
            </div>
            <Edge label="delivers" layer="structural" vertical={vertical} />
            <FlowNode testid="node-call" layer="observed" eyebrowText="Model call" id={p.call.id} active={sel.id === p.call.id}
              sub={`rendered input · seq ${p.call.raw_ref.seq[0]}`} onClick={() => setSel({ type: "event", id: p.call.id })} />
            <Edge label="produces" vertical={vertical} />
            <FlowNode testid="node-answer" layer="observed" eyebrowText="Answer" id={p.answer.id} active={sel.id === p.answer.id}
              sub={`llm_end ${p.answer.raw_ref.seq} · ${fmt(answerText.length)} chars`} onClick={() => setSel({ type: "evidence", id: p.answer.id })} />
            <Edge label="contains" vertical={vertical} />
            <FlowNode testid="node-claim" layer="hand" eyebrowText="Claim · state" id={p.claim.id} active={sel.type === "claim"}
              sub={`span [${p.claim.raw_ref.span.join(", ")}) · ${p.state.value}`} onClick={() => setSel({ type: "claim" })} />
            <Edge label="O3" layer="computed" vertical={vertical} />
            <FlowNode testid="node-o3" layer="computed" eyebrowText="Comparison" big={p.o3.comparison} active={sel.type === "o3"}
              sub={p.o3.comparison === "UNKNOWN" ? "insufficient evidence, not a contradiction" : `direct ${p.o3.direct.value} · delivered ${p.o3.delivered_direct.value}`}
              onClick={() => setSel({ type: "o3" })} />
          </div>
        </section>

        <div style={{ flex: fixed ? 1 : "none", minHeight: 0, display: "grid", gridTemplateColumns: layout.narrow ? "minmax(0, 1fr)" : "minmax(0, 1fr) minmax(0, 1fr)", gap: 12 }}>
          <section aria-label="Tool evidence" data-testid="card-evidence" style={{ ...panel, display: "flex", flexDirection: "column", overflow: "hidden", minHeight: 0 }}>
            <PaneHead title="Tool evidence" right={<><LayerTag kind="observed" />{toolSpans.length > 0 && <LayerTag kind="hand" style={{ marginLeft: 10 }} />}</>}>
              {p.tools.length > 1 && <Segmented testid="evtab" label="Tool result" value={String(tab)} onChange={v => setTab(Number(v))} options={p.tools.map((x, i) => ({ value: String(i), label: x.id.split(":").pop() }))} />}
              <Mono muted style={{ wordBreak: "break-all" }}>{tool.raw_ref.locator}</Mono>
            </PaneHead>
            <div style={{ flex: 1, minHeight: 0 }}><HighlightedText text={toolText.text} spans={toolSpans} color="#fde3b8" testid="evidence-text" label={`Tool evidence ${tool.id}`} height={paneH} /></div>
            <PaneFoot>{toolSpans.length ? `Highlighted and underlined: the ${toolSpans.length} spans cited by the hand-grounded supported_by link.` : "No stored direct link cites this item."}
              {!toolText.complete && ` Display excerpt: first ${fmt(toolText.text.length)} of ${fmt(toolText.length)} chars; the full item is hash-checked at build time.`}</PaneFoot>
          </section>
          <section aria-label="Agent answer" data-testid="card-answer" style={{ ...panel, display: "flex", flexDirection: "column", overflow: "hidden", minHeight: 0 }}>
            <PaneHead title="Agent answer" right={<><LayerTag kind="observed" /><LayerTag kind="hand" style={{ marginLeft: 10 }} /></>}>
              <Mono muted style={{ wordBreak: "break-all" }}>{p.answer.raw_ref.locator}</Mono>
            </PaneHead>
            <div style={{ flex: 1, minHeight: 0 }}><HighlightedText text={answerText.text} spans={p.sem.claims.map(c => c.raw_ref.span)} color="#fcd89a" testid="answer-text" label={`Agent answer ${p.answer.id}`} height={paneH} /></div>
            <PaneFoot>Highlighted and underlined: the hand-grounded claim span. The rest of the answer has no extracted claims.</PaneFoot>
          </section>
        </div>

        <section aria-label="Observed events" style={{ ...panel, padding: "8px 16px" }}>
          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", columnGap: 12, fontSize: 12.5, color: T.muted, marginBottom: 4 }}>
            <span><b style={{ color: T.ink }}>Observed events</b> · {p.st.timeline.length} adapter events in observation order · dark = in this comparison · ← → keys</span>
            <span>{p.st.overlaps} overlapping pairs; order implies no precedence or causation</span>
          </div>
          <EventStrip p={p} sel={sel} onSelect={setSel} />
        </section>
      </div>

      <aside data-testid="inspector" aria-label="Inspector" style={{ ...panel, display: "flex", flexDirection: "column", overflow: fixed ? "hidden" : "visible", height: fixed ? "100%" : "auto" }}>
        <div style={{ padding: "12px 16px" }}>
          <div style={eyebrow}>Inspector</div>
          <h2 data-testid="inspector-title" style={{ fontFamily: T.mono, fontSize: 16, fontWeight: 700, color: T.ink, margin: "4px 0 0", wordBreak: "break-all" }}>{title}</h2>
        </div>
        <div data-testid="detail" tabIndex={fixed ? 0 : -1} role="region" aria-label="Inspector details" style={{ flex: 1, minHeight: 0, overflowY: fixed ? "auto" : "visible" }}>
          {sel.type === "o3" && <O3Inspector p={p} onSelect={setSel} />}
          {sel.type === "evidence" && <EvidenceInspector p={p} id={sel.id} onSelect={setSel} />}
          {sel.type === "claim" && <ClaimInspector p={p} onSelect={setSel} />}
          {sel.type === "event" && <EventInspector p={p} id={sel.id} />}
        </div>
        <div style={{ borderTop: `1px solid ${T.line}`, padding: "8px 16px 10px" }}>
          <Disclosure label="Sources" testid="sources">
            <KV rows={Object.entries(p.run.provenance).map(([k, v]) => [k, <Mono key={k} muted>{v}</Mono>])} />
          </Disclosure>
        </div>
      </aside>
    </div>
  );
}

function PaneHead({ title, right, children }) {
  return (
    <div style={{ padding: "9px 14px", borderBottom: `1px solid ${T.line}`, display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: 6 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, color: T.ink, margin: 0 }}>{title}</h3><span style={{ display: "flex", flexWrap: "wrap" }}>{right}</span>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10, minWidth: 0 }}>{children}</div>
    </div>
  );
}

function PaneFoot({ children }) {
  return <p style={{ padding: "7px 14px", margin: 0, borderTop: `1px solid ${T.soft}`, fontSize: 12.5, color: T.muted, lineHeight: 1.45 }}>{children}</p>;
}
