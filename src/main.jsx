import React, { useState } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import BeliefEvolution from './BeliefEvolution.jsx'
import DemoTab from './demo/DemoTab.jsx'
import { layoutOf, useViewport } from './demo/ui.jsx'
import './index.css'

// '#demo' and '#timeline' reopen those tabs after a reload; no hash keeps the default view.
const VIEWS = ['beliefs', 'timeline', 'demo']
const fromHash = () => VIEWS.find(v => window.location.hash === `#${v}`) || 'beliefs'

function Root() {
  const [view, setViewState] = useState(fromHash)
  const setView = v => {
    setViewState(v)
    window.history.replaceState(null, '', v === 'beliefs' ? window.location.pathname : `#${v}`)
  }
  // At desktop size the demo is a fixed-viewport workspace (tab bar plus demo fill one screen); when the
  // effective viewport is smaller (e.g. browser zoom) the document scrolls and the demo reflows.
  const fixed = layoutOf(useViewport()).fixed
  const shell = view === 'demo' && fixed ? { height: '100vh', display: 'flex', flexDirection: 'column' } : undefined
  return <div style={shell}>
    <div style={{display:'flex',gap:0,padding:'8px 16px',borderBottom:'1px solid #e2e8f0',background:'#f8fafc'}}>
      <button onClick={()=>setView('beliefs')} style={{
        fontSize:12,padding:'6px 16px',border:'1px solid #e2e8f0',borderRadius:'6px 0 0 6px',
        background:view==='beliefs'?'#3b82f6':'#fff',color:view==='beliefs'?'#fff':'#64748b',
        cursor:'pointer',fontWeight:600,fontFamily:'inherit',
      }}>⚡ Belief Evolution</button>
      <button onClick={()=>setView('timeline')} style={{
        fontSize:12,padding:'6px 16px',border:'1px solid #e2e8f0',borderLeft:'none',borderRadius:'0 6px 6px 0',
        background:view==='timeline'?'#3b82f6':'#fff',color:view==='timeline'?'#fff':'#64748b',
        cursor:'pointer',fontWeight:600,fontFamily:'inherit',
      }}>Timeline + Graph</button>
      <button onClick={()=>setView('demo')} data-testid="tab-demo" style={{
        fontSize:12,padding:'6px 16px',border:'1px solid #e2e8f0',borderRadius:6,marginLeft:8,
        background:view==='demo'?'#3b82f6':'#fff',color:view==='demo'?'#fff':'#64748b',
        cursor:'pointer',fontWeight:600,fontFamily:'inherit',
      }}>AgentTrace 0.3 demo</button>
    </div>
    {view === 'beliefs' ? <BeliefEvolution /> : view === 'demo' ? <DemoTab /> : <App />}
  </div>
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
)
