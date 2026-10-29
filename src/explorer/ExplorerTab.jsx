import { useEffect, useState } from "react";
import BeliefExplorerPage from "./BeliefExplorerPage.jsx";
import { loadBundle, manifest, traces } from "./loadBundles.js";

// AP host for the Belief Explorer: owns trace selection and loading, passes the bundle to the page.
// The selected trace is kept in the URL query (?trace=<id>) so a reload reopens it.
const initial = () => {
  const q = new URLSearchParams(window.location.search).get("trace");
  return traces.some(t => t.trace_id === q) ? q : traces[0]?.trace_id ?? null;
};

export default function ExplorerTab() {
  const [traceId, setTraceId] = useState(initial);
  const [state, setState] = useState({ id: null, bundle: null, error: null });
  useEffect(() => {
    if (!traceId) return undefined;
    let alive = true;
    loadBundle(traceId).then(b => alive && setState({ id: traceId, bundle: b, error: null }))
      .catch(e => alive && setState({ id: traceId, bundle: null, error: String(e.message ?? e) }));
    return () => { alive = false; };
  }, [traceId]);
  const choose = id => {
    setTraceId(id);
    const u = new URL(window.location.href);
    u.searchParams.set("trace", id);
    window.history.replaceState(null, "", u);
  };
  const status = !manifest || !traces.length ? "missing" : state.id !== traceId ? "loading" : state.error ? "error" : "ready";
  return <BeliefExplorerPage bundle={status === "ready" ? state.bundle : null} status={status} error={state.error} traces={traces} traceId={traceId} onTraceChange={choose} />;
}
