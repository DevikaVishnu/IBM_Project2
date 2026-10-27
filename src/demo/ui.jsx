import { useEffect, useRef, useState } from "react";
import "./demo.css";

// Shared design tokens, layout hooks and primitives for the AgentTrace demo.  Every provenance class
// has one colour plus a text label, used the same way in both workflows.  Text colours meet at least
// 4.5:1 contrast on white.

export const T = {
  ink: "#0b1220", text: "#1f2937", muted: "#4b5565", faint: "#5f6b7d", line: "#d9dee6", soft: "#eef1f5",
  bg: "#f4f6f9", panel: "#ffffff", focus: "#0b1220",
  sans: '"Inter", "Segoe UI", system-ui, -apple-system, sans-serif',
  mono: 'ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace',
};

export const LAYER = {
  observed: { label: "Observed", color: "#475569", tint: "#f1f5f9", desc: "Recorded in the raw trace; resolved by locator and sha256-checked" },
  structural: { label: "Structural", color: "#1d4ed8", tint: "#eef4ff", desc: "Deterministic adapter join (tool_call_id or delegation_id plus exact equality)" },
  hand: { label: "Hand-grounded", color: "#9a4a07", tint: "#fff6ea", desc: "Written by hand in a fixture; never adapter output" },
  unresolved: { label: "Unresolved", color: "#4b5565", tint: "#f6f7f9", desc: "Agent origin not established; nothing semantic is derived from it" },
  computed: { label: "Computed", color: "#6d28d9", tint: "#f5f1ff", desc: "agenttrace.compare/0.1 result over the stored objects" },
};

export const HATCH = "repeating-linear-gradient(45deg, #c9d0da 0 3px, #f6f7f9 3px 6px)";

// Layout mode from the effective viewport (CSS px, so browser zoom shrinks it).  "fixed": the demo
// fills one screen and only designated regions scroll.  "flow": the document scrolls and panels
// reflow; "narrow" additionally stacks the inspector under the main content.
function readViewport() {
  return { w: window.innerWidth, h: window.innerHeight };
}
export function useViewport() {
  const [vp, setVp] = useState(readViewport);
  useEffect(() => {
    const on = () => setVp(readViewport());
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return vp;
}
export function layoutOf({ w, h }) {
  return { fixed: w >= 1200 && h >= 760, narrow: w < 1000, tall: h >= 900 };
}

export function LayerTag({ kind, style }) {
  const l = LAYER[kind];
  return (
    <span title={l.desc} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 700, letterSpacing: 0.3,
      textTransform: "uppercase", color: l.color, whiteSpace: "nowrap", ...style }}>
      <span aria-hidden="true" style={{ width: 9, height: 9, borderRadius: 2, background: kind === "unresolved" ? HATCH : l.color, border: kind === "unresolved" ? `1px solid ${l.color}` : "none" }} />
      {l.label}
    </span>
  );
}

export function Mono({ children, muted, style }) {
  return <span style={{ fontFamily: T.mono, fontSize: 12, color: muted ? T.muted : T.text, ...style }}>{children}</span>;
}

export function IdButton({ id, onClick, active, label }) {
  return (
    <button data-testid={`id-${id}`} onClick={onClick} aria-label={label ?? `Inspect ${id}`} style={{ fontFamily: T.mono, fontSize: 12, padding: "2px 6px", borderRadius: 4, cursor: "pointer",
      border: `1px solid ${active ? T.ink : T.line}`, background: active ? T.ink : T.panel, color: active ? "#fff" : T.text, wordBreak: "break-all", textAlign: "left" }}>{id}</button>
  );
}

export function Segmented({ options, value, onChange, testid, label }) {
  return (
    <div data-testid={testid} role="group" aria-label={label} style={{ display: "inline-flex", flexWrap: "wrap", background: T.soft, borderRadius: 7, padding: 2, gap: 2 }}>
      {options.map(o => (
        <button key={o.value} data-testid={`${testid}-${o.value}`} aria-pressed={value === o.value} onClick={() => onChange(o.value)}
          style={{ fontSize: 13, fontWeight: 600, padding: "6px 12px", border: "none", borderRadius: 5, cursor: "pointer", fontFamily: T.sans,
            background: value === o.value ? T.panel : "transparent", color: value === o.value ? T.ink : T.muted,
            boxShadow: value === o.value ? "0 1px 2px rgba(15,23,42,.18), inset 0 -2px 0 #0b1220" : "none" }}>{o.label}</button>
      ))}
    </div>
  );
}

export function Stat({ label, value, layer, note }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2, paddingRight: 18, marginRight: 18, borderRight: `1px solid ${T.line}`, marginBottom: 4 }}>
      <span style={{ fontSize: 12, letterSpacing: 0.3, textTransform: "uppercase", color: T.faint, fontWeight: 700, whiteSpace: "nowrap" }}>{label}</span>
      <span style={{ display: "flex", alignItems: "baseline", gap: 6, flexWrap: "wrap" }}>
        <span style={{ fontSize: 18, fontWeight: 650, color: layer ? LAYER[layer].color : T.ink, fontVariantNumeric: "tabular-nums" }}>{value}</span>
        {note && <span style={{ fontSize: 12, color: T.muted }}>{note}</span>}
      </span>
    </div>
  );
}

// Inspector building blocks.
export function Section({ title, layer, children, testid }) {
  return (
    <section data-testid={testid} aria-label={title} style={{ padding: "12px 16px", borderTop: `1px solid ${T.line}` }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
        <h3 style={{ fontSize: 13, fontWeight: 700, color: T.ink, margin: 0 }}>{title}</h3>
        {layer && <LayerTag kind={layer} />}
      </div>
      {children}
    </section>
  );
}

export function KV({ rows }) {
  return (
    <dl style={{ display: "grid", gridTemplateColumns: "minmax(90px, max-content) minmax(0, 1fr)", columnGap: 12, rowGap: 5, fontSize: 13, margin: 0 }}>
      {rows.filter(Boolean).map(([k, v]) => [
        <dt key={`${k}-k`} style={{ color: T.faint }}>{k}</dt>,
        <dd key={`${k}-v`} style={{ color: T.text, wordBreak: "break-all", margin: 0 }}>{v}</dd>,
      ])}
    </dl>
  );
}

export function Note({ children, tone = "plain", testid }) {
  const tones = { plain: [T.muted, "transparent", "transparent"], info: ["#1e3a8a", "#eef4ff", "#c9d8fb"], caution: ["#1f2937", "#f6f7f9", "#9aa3b2"] };
  const [c, bg, b] = tones[tone];
  return <div data-testid={testid} style={{ fontSize: 13, lineHeight: 1.5, color: c, background: bg, border: `1px ${tone === "caution" ? "dashed" : "solid"} ${b}`,
    borderRadius: 6, padding: tone === "plain" ? 0 : "8px 10px", marginTop: 8 }}>{children}</div>;
}

export function Disclosure({ label, children, testid }) {
  return (
    <details data-testid={testid} style={{ marginTop: 8 }}>
      <summary style={{ fontSize: 13, color: T.muted, cursor: "pointer" }}>{label}</summary>
      <div style={{ marginTop: 6 }}>{children}</div>
    </details>
  );
}

export function Json({ value }) {
  return <pre tabIndex={0} aria-label="Raw JSON" style={{ fontFamily: T.mono, fontSize: 12, lineHeight: 1.5, whiteSpace: "pre-wrap", wordBreak: "break-all", background: T.bg,
    border: `1px solid ${T.line}`, borderRadius: 6, padding: 8, margin: 0 }}>{JSON.stringify(value, null, 1)}</pre>;
}

// Text with highlighted spans.  Offsets are Python code points, so slicing is by code point.  The
// pane is a labelled, keyboard-focusable region that scrolls itself (never the page) to its first
// highlight, also after a resize.
export function HighlightedText({ text, spans, color, testid, label, height }) {
  const box = useRef(null);
  const spanKey = JSON.stringify(spans);
  useEffect(() => {
    const align = () => {
      const pre = box.current;
      const mark = pre?.querySelector("mark");
      if (pre && mark && pre.scrollHeight > pre.clientHeight) pre.scrollTop += mark.getBoundingClientRect().top - pre.getBoundingClientRect().top - 32;
    };
    align();
    window.addEventListener("resize", align);
    return () => window.removeEventListener("resize", align);
  }, [text, spanKey]);
  const cps = Array.from(text);
  const parts = [];
  let at = 0;
  [...spans].sort((a, b) => a[0] - b[0]).forEach(([s, e], i) => {
    if (s > at) parts.push(<span key={`t${i}`}>{cps.slice(at, s).join("")}</span>);
    parts.push(<mark key={`m${i}`} data-testid="span-mark" style={{ background: color, color: T.ink, padding: "0 1px", borderRadius: 2, textDecoration: "underline", textDecorationThickness: 2, textUnderlineOffset: 3 }}>{cps.slice(s, e).join("")}</mark>);
    at = e;
  });
  if (at < cps.length) parts.push(<span key="end">{cps.slice(at).join("")}</span>);
  return <pre ref={box} data-testid={testid} tabIndex={0} role="region" aria-label={label} style={{ fontFamily: T.mono, fontSize: 13, lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-word",
    margin: 0, padding: "10px 14px", height: height ?? "100%", overflow: "auto", color: T.text, boxSizing: "border-box" }}>{parts}</pre>;
}

export const panel = { background: T.panel, border: `1px solid ${T.line}`, borderRadius: 8, minHeight: 0, minWidth: 0 };
export const eyebrow = { fontSize: 12, fontWeight: 700, letterSpacing: 0.5, textTransform: "uppercase", color: T.faint };
