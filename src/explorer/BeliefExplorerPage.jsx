import { useEffect, useState } from "react";
import ClaimsPanel from "./ClaimsPanel.jsx";
import MatrixPanel from "./MatrixPanel.jsx";
import { FlagsPanel, Overview, SkeletonPanel } from "./SkeletonFlags.jsx";
import { Chip, ORIGIN, OriginTag, SCOPED_CSS, VARS, card, v } from "./theme.jsx";

// Belief Explorer page.  Renders one trace bundle (contract agenttrace-explorer-bundle/0.1,
// src/explorer/CONTRACT.md) and nothing else: no fetching, no manifest, no global CSS.  The host passes
//   bundle         the loaded bundle, or null
//   status         "ready" | "loading" | "missing" | "error"
//   error          message for status "error"
//   traces         [{trace_id, label, kind}] for the trace switcher (optional)
//   traceId, onTraceChange
// React 18 compatible.  Drop-in for another app: one route rendering a host like ExplorerTab.jsx.

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "claims", label: "Claims & evidence" },
  { id: "matrix", label: "Interaction matrix" },
  { id: "skeleton", label: "Skeleton" },
  { id: "flags", label: "Flags" },
];

function useNarrow() {
  const get = () => (typeof window === "undefined" ? false : window.innerWidth < 1100);
  const [narrow, setNarrow] = useState(get);
  useEffect(() => {
    const on = () => setNarrow(get());
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return narrow;
}

export default function BeliefExplorerPage({ bundle, status = bundle ? "ready" : "missing", error, traces = [], traceId, onTraceChange }) {
  const narrow = useNarrow();
  return (
    <div className="be-root" data-testid="belief-explorer" style={{ ...VARS, background: v("canvas"), color: v("ink"), fontFamily: v("font"), fontSize: 14, minHeight: "100%", lineHeight: 1.45 }}>
      <style>{SCOPED_CSS}</style>
      <header style={{ background: v("surface"), borderBottom: `1px solid ${v("line")}`, padding: "14px 24px", display: "flex", flexWrap: "wrap", alignItems: "center", gap: "10px 24px" }}>
        <div style={{ minWidth: 0 }}>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 750, letterSpacing: -0.2, color: v("ink") }}>Belief Explorer</h1>
          <div style={{ fontSize: 13, color: v("muted") }}>evidence-grounded · AgentTrace 0.3</div>
        </div>
        {traces.length > 0 && (
          <div role="group" aria-label="Trace" data-testid="trace-switcher" style={{ display: "inline-flex", flexWrap: "wrap", gap: 4, background: v("soft"), padding: 3, borderRadius: 9 }}>
            {traces.map(t => {
              const on = t.trace_id === traceId;
              return (
                <button key={t.trace_id} data-testid={`trace-${t.trace_id}`} aria-pressed={on} onClick={() => onTraceChange?.(t.trace_id)}
                  style={{ border: "none", borderRadius: 7, padding: "6px 12px", fontSize: 13, fontWeight: 650, cursor: "pointer",
                    background: on ? v("surface") : "transparent", color: on ? v("ink") : v("muted"), boxShadow: on ? "0 1px 2px rgba(15,23,42,.12), inset 0 -2px 0 #2563EB" : "none" }}>
                  {t.label}
                  <span style={{ display: "block", fontSize: 11, fontWeight: 500, color: v("muted") }}>{t.kind}</span>
                </button>
              );
            })}
          </div>
        )}
        <div role="list" aria-label="Origin tags" style={{ marginLeft: narrow ? 0 : "auto", display: "flex", flexWrap: "wrap", gap: 6 }}>
          {Object.keys(ORIGIN).map(k => <span role="listitem" key={k}><OriginTag origin={k} /></span>)}
        </div>
      </header>
      {status === "missing" && <Notice testid="explorer-local-only">Explorer data is local-only. See docs/DATA.md.</Notice>}
      {status === "loading" && <Notice testid="explorer-loading">Loading trace bundle…</Notice>}
      {status === "error" && <Notice testid="explorer-error" tone="danger">Could not load this trace bundle: {error}</Notice>}
      {status === "ready" && bundle && <TraceView key={bundle.trace.id} b={bundle} narrow={narrow} />}
    </div>
  );
}

function Notice({ children, testid, tone }) {
  return (
    <div style={{ padding: 24 }}>
      <div role={tone === "danger" ? "alert" : "status"} data-testid={testid} style={{ ...card, padding: "16px 18px", fontSize: 14, color: tone === "danger" ? "#B91C1C" : v("ink"),
        background: tone === "danger" ? "#FEF2F2" : v("primary-soft"), borderColor: tone === "danger" ? "#FECACA" : "#BFDBFE" }}>{children}</div>
    </div>
  );
}

function TraceView({ b, narrow }) {
  const [tab, setTab] = useState("overview");
  const [claim, setClaim] = useState(b.claims[0]?.id ?? null);
  const [flag, setFlag] = useState(null);
  const firstMarker = b.matrix?.overlays?.find(o => o.kind === "claim")?.column ?? b.matrix?.overlays?.[0]?.column ?? b.matrix?.columns?.[0]?.id ?? null;
  const [col, setCol] = useState(firstMarker);
  const openClaim = id => { setClaim(id); setTab("claims"); };
  const openFlag = id => { setFlag(id); setTab("flags"); };
  const claimInMatrix = c => { const o = b.matrix?.overlays?.find(x => x.ref === c.id); if (o) setCol(o.column); setTab("matrix"); };
  const flagInMatrix = f => { setFlag(f.id); const o = b.matrix?.overlays?.find(x => x.ref === f.id); setCol(o?.column ?? f.events.find(e => b.matrix?.columns.some(c => c.id === e)) ?? col); setTab("matrix"); };
  const t = b.trace;
  return (
    <>
      <div style={{ padding: "14px 24px 0", display: "flex", flexWrap: "wrap", alignItems: "center", gap: "6px 14px" }}>
        <h2 data-testid="trace-title" style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>{t.label}</h2>
        <span style={{ fontSize: 13, color: v("muted") }}>{[t.framework, t.model, t.scenario && `scenario ${t.scenario}`, t.status && `status ${t.status}`].filter(Boolean).join(" · ")}</span>
        <span data-testid="honesty-label" style={{ marginLeft: narrow ? 0 : "auto", display: "inline-flex", gap: 6, alignItems: "center", fontSize: 12.5 }}>
          <Chip tone="warning">Annotations: {b.honesty.annotations}</Chip>
        </span>
      </div>
      <nav role="tablist" aria-label="Views" style={{ display: "flex", flexWrap: "wrap", gap: 2, padding: "10px 24px 0", borderBottom: `1px solid ${v("line")}` }}>
        {TABS.map(x => {
          const on = tab === x.id;
          return (
            <button key={x.id} role="tab" aria-selected={on} data-testid={`tab-${x.id}`} onClick={() => setTab(x.id)}
              style={{ border: "none", background: "none", padding: "8px 14px", fontSize: 13.5, fontWeight: on ? 700 : 550, cursor: "pointer", color: on ? "#1D4ED8" : v("muted"),
                boxShadow: on ? "inset 0 -2px 0 #2563EB" : "none" }}>{x.label}</button>
          );
        })}
      </nav>
      <main role="tabpanel" aria-label={TABS.find(x => x.id === tab)?.label} style={{ padding: "16px 24px 28px" }}>
        {tab === "overview" && <Overview b={b} onTab={setTab} onOpenClaim={openClaim} onOpenFlag={openFlag} />}
        {tab === "claims" && <ClaimsPanel b={b} selected={claim} onSelect={setClaim} onShowInMatrix={claimInMatrix} narrow={narrow} />}
        {tab === "matrix" && <MatrixPanel b={b} selectedCol={col} onSelectCol={setCol} highlightFlag={flag} onOpenClaim={openClaim} onOpenFlag={openFlag} narrow={narrow} />}
        {tab === "skeleton" && <SkeletonPanel b={b} onShowColumn={id => { setCol(id); setTab("matrix"); }} />}
        {tab === "flags" && <FlagsPanel b={b} selected={flag} onSelect={setFlag} onShowInMatrix={flagInMatrix} />}
        <details style={{ marginTop: 18 }} data-testid="provenance">
          <summary style={{ fontSize: 13, color: v("muted"), cursor: "pointer" }}>Provenance and display rules</summary>
          <ul style={{ fontSize: 12.5, color: v("muted"), lineHeight: 1.6, paddingLeft: 18 }}>
            {b.honesty.rules.map((r, i) => <li key={i}>{r}</li>)}
            <li>Skeleton: {b.honesty.skeleton}.</li>
          </ul>
          <dl style={{ display: "grid", gridTemplateColumns: "max-content minmax(0,1fr)", gap: "3px 12px", fontSize: 12, margin: 0 }}>
            {Object.entries(b.provenance).filter(([, x]) => x != null).map(([k, x]) => [
              <dt key={`${k}k`} style={{ color: v("muted") }}>{k}</dt>,
              <dd key={`${k}v`} style={{ margin: 0, fontFamily: v("mono"), wordBreak: "break-all" }}>{String(x)}</dd>,
            ])}
          </dl>
        </details>
      </main>
    </>
  );
}
