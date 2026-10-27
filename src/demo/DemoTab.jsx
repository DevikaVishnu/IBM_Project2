import { useState } from "react";
import MatrixView from "./MatrixView.jsx";
import CompareView from "./CompareView.jsx";
import { LayerTag, Segmented, T, layoutOf, useViewport } from "./ui.jsx";

// AgentTrace demo shell with two read-only workflows over pre-built data.  At desktop size it fills
// the space below the app's tab bar and only designated regions scroll; at smaller effective
// viewports (browser zoom) it reflows and the document scrolls, so nothing is clipped.
export default function DemoTab() {
  const [mode, setMode] = useState("matrix");
  const layout = layoutOf(useViewport());
  return (
    <div className="at-demo" data-testid="demo-shell" style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", background: T.bg, fontFamily: T.sans, color: T.text }}>
      <header style={{ display: "flex", flexWrap: "wrap", alignItems: "center", columnGap: 16, rowGap: 8, padding: "8px 16px", minHeight: 48, boxSizing: "border-box", flex: "none", background: T.panel, borderBottom: `1px solid ${T.line}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9, whiteSpace: "nowrap" }}>
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <rect x="1" y="1" width="7" height="7" rx="1.5" fill={T.ink} /><rect x="10" y="1" width="7" height="7" rx="1.5" fill="#1d4ed8" />
            <rect x="1" y="10" width="7" height="7" rx="1.5" fill="#9a4a07" /><rect x="10" y="10" width="7" height="7" rx="1.5" fill="#6d28d9" />
          </svg>
          <h1 style={{ fontSize: 15, fontWeight: 700, color: T.ink, margin: 0 }}>AgentTrace</h1>
          <span style={{ fontSize: 14, color: T.muted }}>Belief Explorer</span>
        </div>
        <Segmented testid="mode" label="Workflow" value={mode} onChange={setMode} options={[
          { value: "matrix", label: "Observation matrix · any validated run" },
          { value: "compare", label: "Hand-grounded example · 621 / 620" },
        ]} />
        <div role="list" aria-label="Provenance classes" style={{ marginLeft: layout.narrow ? 0 : "auto", display: "flex", flexWrap: "wrap", alignItems: "center", columnGap: 14, rowGap: 4 }}>
          {["observed", "structural", "hand", "unresolved", "computed"].map(k => <span role="listitem" key={k}><LayerTag kind={k} /></span>)}
        </div>
      </header>
      <div style={{ flex: 1, minHeight: 0 }}>{mode === "matrix" ? <MatrixView layout={layout} /> : <CompareView layout={layout} />}</div>
    </div>
  );
}
