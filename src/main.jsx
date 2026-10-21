import React, { useState } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import BeliefEvolution from './BeliefEvolution.jsx'
import AssetOpsTimeline from './AssetOpsTimeline.jsx'
import './index.css'

function Root() {
  const [view, setView] = useState('beliefs')
  return <>
    <div className="app-nav">
      <button aria-pressed={view==='beliefs'} onClick={()=>setView('beliefs')}>Belief Evolution</button>
      <button aria-pressed={view==='timeline'} onClick={()=>setView('timeline')}>Timeline + Graph</button>
      <button aria-pressed={view==='assetops'} onClick={()=>setView('assetops')}>AssetOpsBench</button>
    </div>
    {view === 'beliefs' ? <BeliefEvolution /> : view === 'assetops' ? <AssetOpsTimeline /> : <App />}
  </>
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
)
