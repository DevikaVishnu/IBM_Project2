import React, { useState } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import BeliefEvolution from './BeliefEvolution.jsx'
import AssetOpsTimeline from './AssetOpsTimeline.jsx'
import DemoTab from './demo/DemoTab.jsx'
import { layoutOf, useViewport } from './demo/ui.jsx'
import './index.css'

// These hashes reopen the selected view after a browser reload.
const VIEWS = ['beliefs', 'timeline', 'assetops', 'demo']
const fromHash = () => VIEWS.find(v => window.location.hash === `#${v}`) || 'beliefs'

function Root() {
  const [view, setViewState] = useState(fromHash)
  const setView = v => {
    setViewState(v)
    window.history.replaceState(null, '', v === 'beliefs' ? window.location.pathname : `#${v}`)
  }
  const fixed = layoutOf(useViewport()).fixed
  const shell = view === 'demo' && fixed ? { height: '100vh', display: 'flex', flexDirection: 'column' } : undefined
  return <div style={shell}>
    <nav className="app-nav" aria-label="Application views">
      <button aria-pressed={view === 'beliefs'} onClick={() => setView('beliefs')}>Belief Evolution</button>
      <button aria-pressed={view === 'timeline'} onClick={() => setView('timeline')}>Timeline + Graph</button>
      <button aria-pressed={view === 'assetops'} onClick={() => setView('assetops')}>AssetOpsBench</button>
      <button aria-pressed={view === 'demo'} data-testid="tab-demo" onClick={() => setView('demo')}>AgentTrace 0.3 demo</button>
    </nav>
    {view === 'beliefs' ? <BeliefEvolution /> : view === 'timeline' ? <App /> : view === 'assetops' ? <AssetOpsTimeline /> : <DemoTab />}
  </div>
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode><Root /></React.StrictMode>,
)
