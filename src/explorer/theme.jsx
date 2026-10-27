// Design tokens and small primitives for the Belief Explorer.  Everything is scoped to the page root:
// CSS variables are set on the root element and the only stylesheet is a <style> block whose selectors
// all start with .be-root, so the page can drop into another app (e.g. Mission Control) unchanged.

export const VARS = {
  "--be-canvas": "#F7F9FC",
  "--be-surface": "#FFFFFF",
  "--be-ink": "#0F172A",
  "--be-muted": "#64748B",
  "--be-line": "#E2E8F0",
  "--be-primary": "#2563EB",
  "--be-primary-soft": "#EFF6FF",
  "--be-success": "#16A34A",
  "--be-warning": "#F59E0B",
  "--be-danger": "#DC2626",
  // Darker text variants of the status colours, for 4.5:1 contrast on white.
  "--be-success-ink": "#15803D",
  "--be-warning-ink": "#B45309",
  "--be-danger-ink": "#B91C1C",
  "--be-soft": "#F1F5F9",
  "--be-font": '"Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif',
  "--be-mono": '"JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace',
};
export const v = name => `var(--be-${name})`;

export const SCOPED_CSS = `
.be-root, .be-root * { box-sizing: border-box; }
.be-root button { font-family: inherit; }
.be-root :focus-visible { outline: 3px solid #2563EB; outline-offset: 2px; border-radius: 4px; }
.be-root .be-hover:hover { background: #F1F5F9; }
.be-root .be-cell:hover rect.be-cell-body { stroke: #0F172A; }
@media (prefers-reduced-motion: reduce) { .be-root * { scroll-behavior: auto !important; transition: none !important; } }
`;

export const HATCH = "repeating-linear-gradient(45deg, #CBD5E1 0 3px, #F8FAFC 3px 6px)";

export const ORIGIN = {
  observed: { label: "Observed", color: "#334155", bg: "#F1F5F9", desc: "Recorded in the raw trace and resolved by locator" },
  computed: { label: "Computed", color: "#1D4ED8", bg: "#EFF6FF", desc: "Derived deterministically by code (adapter joins, matrix pipeline, agenttrace.compare/0.1)" },
  "hand-annotated": { label: "Hand-annotated", color: "#B45309", bg: "#FFFBEB", desc: "Written by a person: illustrative, not gold" },
  "hand-reconstructed": { label: "Hand-reconstructed", color: "#6D28D9", bg: "#F5F3FF", desc: "Rebuilt by hand from a document (schema §14), cited lines checked" },
  unresolved: { label: "Unresolved", color: "#475569", bg: "#F8FAFC", desc: "Not established by the trace; nothing semantic is derived from it" },
};

export function OriginTag({ origin, style }) {
  const o = ORIGIN[origin] ?? ORIGIN.unresolved;
  return (
    <span title={o.desc} data-origin={origin} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, fontWeight: 700, letterSpacing: 0.3,
      textTransform: "uppercase", color: o.color, background: o.bg, border: `1px ${origin === "unresolved" ? "dashed" : "solid"} ${o.color}33`,
      borderRadius: 999, padding: "2px 8px", whiteSpace: "nowrap", lineHeight: 1.4, ...style }}>
      <span aria-hidden="true" style={{ width: 7, height: 7, borderRadius: 2, background: origin === "unresolved" ? HATCH : o.color, border: origin === "unresolved" ? `1px solid ${o.color}` : "none" }} />
      {o.label}
    </span>
  );
}

const TONE = {
  success: ["var(--be-success-ink)", "#F0FDF4", "#BBF7D0"],
  danger: ["var(--be-danger-ink)", "#FEF2F2", "#FECACA"],
  warning: ["var(--be-warning-ink)", "#FFFBEB", "#FDE68A"],
  primary: ["#1D4ED8", "var(--be-primary-soft)", "#BFDBFE"],
  muted: ["#475569", "#F8FAFC", "#CBD5E1"],
};

export const RESULT = {
  AGREES: { label: "Agrees", tone: "success" },
  DIFFERS_FROM_DIRECT: { label: "Differs", tone: "danger" },
  DIFFERS: { label: "Differs", tone: "danger" },
  UNKNOWN: { label: "Unknown", tone: "muted" },
  UNRESOLVED: { label: "Unresolved", tone: "muted" },
  AMBIGUOUS: { label: "Ambiguous", tone: "warning" },
  NOT_APPLICABLE: { label: "Not compared", tone: "muted" },
  "rule-dependent": { label: "Rule-dependent", tone: "warning" },
  "not computable": { label: "Not computable", tone: "muted" },
  none: { label: "No result", tone: "muted" },
};

export function Chip({ tone = "muted", children, title, style }) {
  const [c, bg, b] = TONE[tone] ?? TONE.muted;
  return <span title={title} style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12, fontWeight: 650, color: c, background: bg,
    border: `1px solid ${b}`, borderRadius: 6, padding: "1px 7px", whiteSpace: "nowrap", lineHeight: 1.5, ...style }}>{children}</span>;
}

// The single O3 outcome shown for a claim: the computed comparison if there is one, else the status.
export function claimResult(c) {
  const o = c.o3;
  if (!o) return "none";
  if (o.status === "computed") return o.comparison;
  return o.status;
}
export function ResultChip({ value, style }) {
  const r = RESULT[value] ?? { label: String(value), tone: "muted" };
  return <Chip tone={r.tone} style={style} title={value}>{r.label}</Chip>;
}

export const DELIVERY = {
  DELIVERED: { tone: "success", short: "Delivered", text: "Yes: byte-identical in the claiming call's rendered input" },
  UNKNOWN: { tone: "muted", short: "Unknown", text: "Not established. Absence is never shown as non-delivery without coverage" },
  UNRESOLVED: { tone: "muted", short: "Unresolved", text: "Unresolved: the claiming call's agent origin is not established, so delivery to an agent cannot be stated" },
  NOT_APPLICABLE: { tone: "muted", short: "N/A", text: "Not applicable: the target is not an agent-input event" },
  NOT_DELIVERED: { tone: "danger", short: "Not delivered", text: "Not delivered (coverage established)" },
  WHOLE_NOT_DELIVERED: { tone: "danger", short: "Not delivered whole", text: "The whole item was not delivered (size bound)" },
};

export const card = { background: v("surface"), border: `1px solid ${v("line")}`, borderRadius: 10, minWidth: 0 };
export const eyebrow = { fontSize: 11, fontWeight: 700, letterSpacing: 0.6, textTransform: "uppercase", color: v("muted") };
export const mono = { fontFamily: v("mono"), fontSize: 12 };
export const linkBtn = { background: "none", border: "none", padding: 0, color: "#1D4ED8", cursor: "pointer", fontSize: 13, textDecoration: "underline", textUnderlineOffset: 2 };
export const fmt = n => (typeof n === "number" ? n.toLocaleString("en-US") : n ?? "—");

export function Section({ title, origin, children, right, testid }) {
  return (
    <section data-testid={testid} aria-label={title} style={{ ...card, padding: "14px 16px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: v("ink") }}>{title}</h3>
        {origin && <OriginTag origin={origin} />}
        {right && <span style={{ marginLeft: "auto" }}>{right}</span>}
      </div>
      {children}
    </section>
  );
}

export function Empty({ children, testid }) {
  return <div data-testid={testid} style={{ padding: "18px 16px", fontSize: 13, color: v("muted"), border: `1px dashed ${v("line")}`, borderRadius: 10, background: v("surface") }}>{children}</div>;
}

// Excerpt with highlighted spans (code-point offsets).
export function Excerpt({ excerpt, maxHeight = 220 }) {
  if (!excerpt) return null;
  const cps = Array.from(excerpt.text ?? "");
  const parts = [];
  let at = 0;
  [...(excerpt.spans ?? [])].sort((a, b) => a[0] - b[0]).forEach(([s, e], i) => {
    if (s < at) return;
    if (s > at) parts.push(<span key={`t${i}`}>{cps.slice(at, s).join("")}</span>);
    parts.push(<mark key={`m${i}`} style={{ background: "#FEF3C7", color: "var(--be-ink)", borderRadius: 2, padding: "0 1px", boxShadow: "inset 0 -2px 0 #F59E0B" }}>{cps.slice(s, e).join("")}</mark>);
    at = e;
  });
  if (at < cps.length) parts.push(<span key="end">{cps.slice(at).join("")}</span>);
  return (
    <pre tabIndex={0} aria-label="Evidence excerpt" style={{ ...mono, lineHeight: 1.55, whiteSpace: "pre-wrap", wordBreak: "break-word", margin: 0, padding: "8px 10px",
      background: v("canvas"), border: `1px solid ${v("line")}`, borderRadius: 8, maxHeight, overflow: "auto", color: v("ink") }}>
      {excerpt.start > 0 && <span style={{ color: v("muted") }}>…</span>}{parts}{!excerpt.complete && <span style={{ color: v("muted") }}> …</span>}
    </pre>
  );
}
