import React, { useState } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import BeliefEvolution from './BeliefEvolution.jsx'
import './index.css'

function Root() {
  const [view, setView] = useState('beliefs')
  return <>
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
    </div>
    {view === 'beliefs' ? <BeliefEvolution /> : <App />}
  </>
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
)
