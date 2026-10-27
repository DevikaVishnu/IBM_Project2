// Bundle loading for the AP viewer (outside BeliefExplorerPage).  src/explorer/data/ is local-only and
// gitignored: the manifest is imported only if present, so a fresh clone still builds.  Each bundle is
// loaded on demand and its sha256 is checked against the manifest before use.

export const CONTRACT = "agenttrace-explorer-bundle/0.1";
const MANIFEST = import.meta.glob("./data/index.json", { eager: true, import: "default" })["./data/index.json"] ?? null;
const FILES = import.meta.glob("./data/*.bundle.json", { query: "?raw", import: "default" });

export const manifest = MANIFEST;
export const traces = MANIFEST?.bundles ?? [];

async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
}

export async function loadBundle(traceId) {
  const entry = traces.find(t => t.trace_id === traceId);
  if (!entry) throw new Error(`${traceId} is not in the manifest`);
  const loader = FILES[`./data/${entry.file}`];
  if (!loader) throw new Error(`${entry.file} is listed in the manifest but not present`);
  const text = await loader();
  if ((await sha256(text)) !== entry.sha256) throw new Error(`${entry.file} does not match its manifest sha256; rebuild with scripts/explorer/build_bundle.py`);
  const b = JSON.parse(text);
  if (b.contract !== CONTRACT) throw new Error(`${entry.file} has contract ${b.contract}, expected ${CONTRACT}`);
  return b;
}
