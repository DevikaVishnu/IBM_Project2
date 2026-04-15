import { useState, useMemo } from "react";

const COLORS = ["#2563eb","#059669","#7c3aed","#dc2626","#d97706","#0891b2","#4f46e5","#e11d48"];
const MAST = {
  "1.1":{l:"Disobey task spec",c:"FC1"},"1.2":{l:"Disobey role spec",c:"FC1"},
  "1.3":{l:"Step repetition",c:"FC1"},"1.4":{l:"Lost history",c:"FC1"},
  "1.5":{l:"No stopping condition",c:"FC1"},"2.1":{l:"Conv reset",c:"FC2"},
  "2.2":{l:"No clarification",c:"FC2"},"2.3":{l:"Task derail",c:"FC2"},
  "2.4":{l:"Info withholding",c:"FC2"},"2.5":{l:"Ignores input",c:"FC2"},
  "2.6":{l:"Reason-action mismatch",c:"FC2"},"3.1":{l:"Premature end",c:"FC3"},
  "3.2":{l:"No verification",c:"FC3"},"3.3":{l:"Bad verification",c:"FC3"},
};

function ac(agent,agents){
  if(agent==="Conclusion")return "#6b7280";
  const i=agents.indexOf(agent);
  return COLORS[i%COLORS.length];
}

const AG2_DATA = {
  meta:{framework:"AG2",benchmark:"critical thinking",llm:"unknown",total_turns:10,
    problem_statement:"Monica is wrapping Christmas gifts. She has 6 gifts for family, 4 for friends, 2 for teachers. How many inches of ribbon per bow?",
    note_text:"The mathproxyagent keeps asking to continue despite the problem being unsolvable."},
  agents:["mathproxyagent","assistant"],
  failures:{"1.5":{label:"Unaware of stopping conditions",category:"FC1"},"2.5":{label:"Ignored other agent's input",category:"FC2"}},
  turns:[
    {index:0,agent:"mathproxyagent",content:"Let's use Python to solve a math problem.\n\nProblem: Monica has 6 gifts for family, 4 for friends, 2 for teachers. How many inches of ribbon per bow?",phase:"",short:"setup problem",annotations:[]},
    {index:1,agent:"assistant",content:"This problem cannot be solved with the information provided. No ribbon amount is specified.",phase:"",short:"insufficient data",annotations:[]},
    {index:2,agent:"mathproxyagent",content:"Continue. Please keep solving the problem until you need to query. (If you get to the answer, put it in \\boxed{}.)",phase:"",short:"continue",annotations:[{code:"1.5",type:"failure"},{code:"2.5",type:"failure"},{code:"divergence",type:"divergence"}]},
    {index:3,agent:"assistant",content:"I don't have enough information. I need:\n1. Total ribbon length?\n2. Inches per bow?\nWithout this, unsolvable.",phase:"",short:"re-explains",annotations:[{code:"re-explain",type:"divergence"}]},
    {index:4,agent:"mathproxyagent",content:"Continue. Please keep solving the problem until you need to query. (If you get to the answer, put it in \\boxed{}.)",phase:"",short:"continue",annotations:[{code:"1.5",type:"failure"},{code:"2.5",type:"failure"},{code:"divergence",type:"divergence"}]},
    {index:5,agent:"assistant",content:"I really need more information. It can't be solved with current data.",phase:"",short:"re-explains",annotations:[{code:"re-explain",type:"divergence"}]},
    {index:6,agent:"mathproxyagent",content:"Continue. Please keep solving the problem until you need to query. (If you get to the answer, put it in \\boxed{}.)",phase:"",short:"continue",annotations:[{code:"1.5",type:"failure"},{code:"2.5",type:"failure"},{code:"divergence",type:"divergence"}]},
    {index:7,agent:"assistant",content:"We cannot solve this — crucial data is missing. Any attempt would be assumptions, not facts.",phase:"",short:"re-explains",annotations:[{code:"re-explain",type:"divergence"}]},
    {index:8,agent:"mathproxyagent",content:"Continue. Please keep solving the problem until you need to query. (If you get to the answer, put it in \\boxed{}.)",phase:"",short:"continue",annotations:[{code:"1.5",type:"failure"},{code:"2.5",type:"failure"},{code:"divergence",type:"divergence"}]},
    {index:9,agent:"assistant",content:'The problem cannot be solved. \\boxed{"Data insufficient"}.',phase:"",short:"final answer",annotations:[]},
  ],
  loops:[{start:2,end:9}],
  beliefs:{beliefs:{mathproxyagent:"Task should continue — answer must be produced",assistant:"Task is blocked — critical information missing"},has_divergence:true},
};

const CHATDEV_DATA = {"meta":{"framework":"ChatDev","benchmark":"ProgramDev","llm":"GPT-4o","total_turns":37,"problem_statement":"Write a program that generates Fibonacci numbers up to a given number","note_text":""},"agents":["Chief Executive Officer","Chief Product Officer","Conclusion","Chief Technology Officer","Programmer","Code Reviewer","Counselor"],"failures":{"1.1":{"label":"Disobey task specification","category":"FC1"},"2.6":{"label":"Reasoning-action mismatch","category":"FC2"},"3.3":{"label":"Incorrect verification","category":"FC3"}},"turns":[{"index":0,"agent":"Chief Executive Officer","content":"Which product modality do we want?","phase":"DemandAnalysis","short":"start chat","annotations":[]},{"index":1,"agent":"Chief Product Officer","content":"The most suitable modality would be an Application. This allows us to create an interactive and functional tool that can dynamically generate and display Fibonacci numbers based on user input.","phase":"DemandAnalysis","short":"application","annotations":[]},{"index":2,"agent":"Chief Executive Officer","content":"I completely agree. An Application modality is indeed the most suitable choice. <INFO> Application","phase":"DemandAnalysis","short":"agree: application","annotations":[]},{"index":3,"agent":"Conclusion","content":"<INFO> Application","phase":"DemandAnalysis","short":"Application","annotations":[]},{"index":4,"agent":"Chief Executive Officer","content":"Which programming language should we use?","phase":"LanguageChoose","short":"start chat","annotations":[]},{"index":5,"agent":"Chief Technology Officer","content":"<INFO> Python","phase":"LanguageChoose","short":"Python","annotations":[]},{"index":6,"agent":"Conclusion","content":"<INFO> Python","phase":"LanguageChoose","short":"Python","annotations":[]},{"index":7,"agent":"Chief Technology Officer","content":"Write one or multiple files implementing the Fibonacci generator. Ensure all functions are implemented, no placeholders.","phase":"Coding","short":"start chat","annotations":[]},{"index":8,"agent":"Programmer","content":"Created fibonacci.py and main.py with generate_fibonacci_upto(limit) function. Handles user input and validation.","phase":"Coding","short":"writes code","annotations":[]},{"index":9,"agent":"Conclusion","content":"Architecture: main.py (entry point) + fibonacci.py (generator logic). 38 lines of code.","phase":"Coding","short":"code complete","annotations":[]},{"index":10,"agent":"Programmer","content":"Please review the code against ChatDev regulations: all classes imported, all methods implemented, all methods commented, no bugs, conforms to task.","phase":"CodeReviewComment","short":"requests review","annotations":[]},{"index":11,"agent":"Code Reviewer","content":"<INFO> Finished","phase":"CodeReviewComment","short":"finished","annotations":[{"code":"3.3","type":"failure"}]},{"index":12,"agent":"Conclusion","content":"<INFO> Finished","phase":"CodeReviewComment","short":"finished","annotations":[]},{"index":13,"agent":"Code Reviewer","content":"Modify codes according to comments. Output the full and complete codes with all bugs fixed.","phase":"CodeReviewModification","short":"modify request","annotations":[]},{"index":14,"agent":"Programmer","content":"Updated output formatting: print(\", \".join(map(str, fibonacci_numbers))). Added run.sh script.","phase":"CodeReviewModification","short":"minor fix","annotations":[]},{"index":15,"agent":"Conclusion","content":"fibonacci.py + main.py + run.sh updated. 38 lines total.","phase":"CodeReviewModification","short":"code updated","annotations":[]},{"index":16,"agent":"Programmer","content":"Please review the code again.","phase":"CodeReviewComment","short":"requests review","annotations":[]},{"index":17,"agent":"Code Reviewer","content":"<INFO> Finished","phase":"CodeReviewComment","short":"finished","annotations":[{"code":"3.3","type":"failure"}]},{"index":18,"agent":"Conclusion","content":"<INFO> Finished","phase":"CodeReviewComment","short":"finished","annotations":[]},{"index":19,"agent":"Code Reviewer","content":"Modify codes according to comments.","phase":"CodeReviewModification","short":"modify request","annotations":[]},{"index":20,"agent":"Programmer","content":"No changes — code returned as-is with identical output.","phase":"CodeReviewModification","short":"no changes","annotations":[{"code":"2.6","type":"failure"}]},{"index":21,"agent":"Conclusion","content":"Same code, no modifications.","phase":"CodeReviewModification","short":"no changes","annotations":[]},{"index":22,"agent":"Programmer","content":"Please review the code again.","phase":"CodeReviewComment","short":"requests review","annotations":[]},{"index":23,"agent":"Code Reviewer","content":"<INFO> Finished","phase":"CodeReviewComment","short":"finished","annotations":[{"code":"3.3","type":"failure"}]},{"index":24,"agent":"Conclusion","content":"<INFO> Finished","phase":"CodeReviewComment","short":"finished","annotations":[]},{"index":25,"agent":"Code Reviewer","content":"Modify codes according to comments.","phase":"CodeReviewModification","short":"modify request","annotations":[]},{"index":26,"agent":"Programmer","content":"No changes — code returned as-is.","phase":"CodeReviewModification","short":"no changes","annotations":[{"code":"2.6","type":"failure"}]},{"index":27,"agent":"Conclusion","content":"Same code, no modifications.","phase":"CodeReviewModification","short":"no changes","annotations":[]},{"index":28,"agent":"Chief Technology Officer","content":"Write a requirements.txt file specifying project dependencies.","phase":"EnvironmentDoc","short":"request deps","annotations":[]},{"index":29,"agent":"Programmer","content":"requirements.txt: # No external dependencies required for this project.","phase":"EnvironmentDoc","short":"no deps","annotations":[]},{"index":30,"agent":"Counselor","content":"Confirmed: requirements.txt with no external dependencies.","phase":"Reflection","short":"confirmed","annotations":[]},{"index":31,"agent":"Chief Executive Officer","content":"Reviewed requirements and confirmed correctness.","phase":"Reflection","short":"confirmed","annotations":[]},{"index":32,"agent":"Conclusion","content":"requirements.txt confirmed.","phase":"Reflection","short":"confirmed","annotations":[]},{"index":33,"agent":"Conclusion","content":"<INFO> requirements.txt — no external dependencies.","phase":"Reflection","short":"requirements","annotations":[]},{"index":34,"agent":"Chief Executive Officer","content":"Write a manual.md file with detailed user documentation.","phase":"Manual","short":"request manual","annotations":[]},{"index":35,"agent":"Chief Product Officer","content":"Created manual.md with introduction, features, installation, usage instructions, project structure, and license info.","phase":"Manual","short":"writes manual","annotations":[]},{"index":36,"agent":"Conclusion","content":"manual.md complete. Project finished in 322 seconds, 10558 total tokens.","phase":"Manual","short":"project done","annotations":[{"code":"1.1","type":"failure"}]}],"loops":[],"beliefs":{"beliefs":{"Chief Executive Officer":"Task complete","Chief Product Officer":"Task complete","Chief Technology Officer":"Task complete","Programmer":"Task complete","Code Reviewer":"Task complete","Counselor":"Working on the task"},"has_divergence":true}};

function Badge({code,type}){
  const m=MAST[code];
  if(type==="failure") return <span style={{fontFamily:"monospace",fontSize:9,padding:"1px 5px",borderRadius:3,background:"rgba(220,38,38,0.08)",color:"#dc2626",border:"1px solid rgba(220,38,38,0.2)",marginRight:3,whiteSpace:"nowrap"}}>FM-{code}{m?" "+m.l:""}</span>;
  return <span style={{fontFamily:"monospace",fontSize:9,padding:"1px 5px",borderRadius:3,background:"rgba(217,119,6,0.08)",color:"#d97706",border:"1px solid rgba(217,119,6,0.2)",marginRight:3,whiteSpace:"nowrap"}}>{code==="divergence"?"⚡ divergence":"↻ re-explains"}</span>;
}

export default function App(){
  const [trace,setTrace]=useState("ag2");
  const [view,setView]=useState("compact");
  const [drill,setDrill]=useState(-1);

  const D=trace==="ag2"?AG2_DATA:CHATDEV_DATA;
  const agents=D.agents.filter(a=>a!=="System");
  const colW=Math.max(100,Math.min(170,700/Math.max(agents.length,1)));

  const inLoop=(i)=>D.loops.some(l=>i>=l.start&&i<=l.end);

  return <div style={{fontFamily:"'Segoe UI',system-ui,sans-serif",color:"#1a1a1a",maxWidth:1100}}>
    {/* Header */}
    <div style={{display:"flex",alignItems:"baseline",gap:12,padding:"12px 0",borderBottom:"1px solid #e5e5e5",flexWrap:"wrap"}}>
      <span style={{fontSize:20,fontWeight:600}}>AgentTrace</span>
      <span style={{fontFamily:"monospace",fontSize:11,padding:"2px 8px",borderRadius:6,background:"#f3f3f3",color:"#666"}}>{D.meta.framework} · {D.meta.benchmark}{D.meta.llm!=="unknown"?" · "+D.meta.llm:""}</span>
      <div style={{display:"flex",gap:10,marginLeft:"auto",alignItems:"center",flexWrap:"wrap"}}>
        {agents.map(a=><span key={a} style={{display:"inline-flex",alignItems:"center",gap:3,fontSize:11,color:"#666"}}>
          <span style={{width:7,height:7,borderRadius:"50%",background:ac(a,agents),display:"inline-block"}}/>
          {a.length>12?a.slice(0,12)+"…":a}
        </span>)}
        <span style={{fontSize:11,color:"#999"}}>{D.meta.total_turns} turns</span>
      </div>
    </div>
    {D.meta.problem_statement&&<p style={{fontSize:12,color:"#888",margin:"6px 0 0",lineHeight:1.4}}>{D.meta.problem_statement.slice(0,120)}{D.meta.problem_statement.length>120?"…":""}</p>}

    {/* Toolbar */}
    <div style={{display:"flex",gap:8,alignItems:"center",padding:"8px 0",borderBottom:"1px solid #e5e5e5",flexWrap:"wrap"}}>
      <div style={{display:"flex",gap:0}}>
        {["compact","detailed"].map(v=><button key={v} onClick={()=>{setView(v);setDrill(-1);}} style={{fontSize:11,padding:"4px 12px",border:"1px solid #ccc",background:view===v?"#2563eb":"#fff",color:view===v?"#fff":"#666",cursor:"pointer",borderRadius:v==="compact"?"5px 0 0 5px":"0 5px 5px 0",fontFamily:"inherit"}}>{v}</button>)}
      </div>
      <div style={{display:"flex",gap:4}}>
        {["ag2","chatdev"].map(t=><button key={t} onClick={()=>{setTrace(t);setDrill(-1);}} style={{fontSize:11,padding:"4px 10px",border:"1px solid #ccc",borderRadius:5,background:trace===t?"#f3f3f3":"#fff",color:"#555",cursor:"pointer",fontFamily:"inherit"}}>{t==="ag2"?"AG2 trace":"ChatDev trace"}</button>)}
      </div>
    </div>

    {/* Main layout */}
    <div style={{display:"grid",gridTemplateColumns:"1fr 240px",gap:0,marginTop:8}}>
      {/* Timeline */}
      <div style={{overflowX:"auto",paddingRight:16}}>
        {/* Column headers */}
        {view==="compact"&&<div style={{display:"flex",paddingLeft:40,borderBottom:"1px solid #eee",marginBottom:4,position:"sticky",top:0,background:"#fff",zIndex:5}}>
          {agents.map(a=><div key={a} style={{width:colW,textAlign:"center",padding:"5px 0"}}>
            <div style={{width:7,height:7,borderRadius:"50%",background:ac(a,agents),display:"inline-block",marginBottom:2}}/>
            <div style={{fontFamily:"monospace",fontSize:9,color:ac(a,agents),overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",padding:"0 2px"}}>{a}</div>
          </div>)}
        </div>}

        {(()=>{
          let phase="";
          return D.turns.map((t,i)=>{
            const parts=[];
            if(t.phase&&t.phase!==phase){
              phase=t.phase;
              parts.push(<div key={"p"+i} style={{display:"flex",alignItems:"center",gap:8,padding:"7px 0 3px"}}>
                <div style={{flex:1,height:1,background:"#e5e5e5"}}/>
                <span style={{fontFamily:"monospace",fontSize:9,color:"#aaa",letterSpacing:1,textTransform:"uppercase",whiteSpace:"nowrap"}}>{phase}</span>
                <div style={{flex:1,height:1,background:"#e5e5e5"}}/>
              </div>);
            }

            const il=inLoop(i);
            const ci=agents.indexOf(t.agent);
            const c=ac(t.agent,agents);
            const hasAnn=t.annotations&&t.annotations.length>0;

            if(view==="compact"){
              parts.push(<div key={i} onClick={()=>setDrill(drill===i?-1:i)} style={{display:"flex",alignItems:"center",minHeight:28,cursor:"pointer",borderRadius:5,padding:"1px 0",borderLeft:il?"2.5px solid #dc2626":"2.5px solid transparent",background:il?"rgba(220,38,38,0.03)":drill===i?"#f8f8f8":"transparent"}}>
                <span style={{width:36,textAlign:"right",fontFamily:"monospace",fontSize:9.5,color:"#bbb",paddingRight:5,flexShrink:0}}>{i+1}</span>
                <div style={{display:"flex",flex:1}}>
                  {agents.map((a,ai)=><div key={ai} style={{width:colW,display:"flex",alignItems:"center",justifyContent:"center"}}>
                    {ai===ci&&<><div style={{height:22,borderRadius:3,minWidth:16,maxWidth:colW-8,padding:"0 5px",display:"flex",alignItems:"center",justifyContent:"center",background:`${c}12`,border:`1px solid ${c}30`}}>
                      <span style={{fontSize:9.5,fontFamily:"monospace",color:"#555",whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis",maxWidth:colW-20}}>{t.short}</span>
                    </div>
                    {hasAnn&&<span style={{width:6,height:6,borderRadius:"50%",background:"#dc2626",marginLeft:2,flexShrink:0}}/>}</>}
                  </div>)}
                </div>
              </div>);
            } else {
              const preview=t.content.length>200?t.content.slice(0,200)+"…":t.content;
              parts.push(<div key={i} onClick={()=>setDrill(drill===i?-1:i)} style={{padding:"8px 8px 8px 40px",borderRadius:5,cursor:"pointer",position:"relative",borderLeft:il?"2.5px solid #dc2626":"2.5px solid transparent",background:il?"rgba(220,38,38,0.03)":drill===i?"#f8f8f8":"transparent",marginBottom:1}}>
                <span style={{position:"absolute",left:6,top:10,fontFamily:"monospace",fontSize:9.5,color:"#bbb",width:28,textAlign:"right"}}>{i+1}</span>
                <span style={{fontFamily:"monospace",fontSize:10,fontWeight:600,padding:"1px 6px",borderRadius:4,background:`${c}12`,color:c,display:"inline-block",marginBottom:3}}>{t.agent}</span>
                <div style={{fontSize:12,lineHeight:1.5,color:"#666",whiteSpace:"pre-wrap",wordBreak:"break-word"}}>{preview}</div>
                {hasAnn&&<div style={{marginTop:3}}>{t.annotations.map((a,j)=><Badge key={j} code={a.code} type={a.type}/>)}</div>}
              </div>);
            }

            // Drill-down panel
            if(drill===i){
              parts.push(<div key={"d"+i} style={{margin:"4px 0 4px 40px",padding:14,background:"#fff",border:"1px solid #ddd",borderRadius:8}}>
                <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:8}}>
                  <span style={{fontFamily:"monospace",fontSize:10,fontWeight:600,padding:"1px 6px",borderRadius:4,background:`${c}12`,color:c}}>{t.agent}</span>
                  <span style={{fontFamily:"monospace",fontSize:10,color:"#aaa"}}>turn {t.index+1}{t.phase?" · "+t.phase:""}</span>
                  <button onClick={(e)=>{e.stopPropagation();setDrill(-1);}} style={{marginLeft:"auto",fontSize:10,padding:"2px 8px",border:"1px solid #ddd",borderRadius:4,background:"#fff",cursor:"pointer",fontFamily:"inherit",color:"#888"}}>close</button>
                </div>
                <div style={{fontSize:12.5,lineHeight:1.6,color:"#333",whiteSpace:"pre-wrap",maxHeight:300,overflowY:"auto",wordBreak:"break-word"}}>{t.content}</div>
                {hasAnn&&<div style={{marginTop:8,paddingTop:8,borderTop:"1px solid #eee"}}>{t.annotations.map((a,j)=><Badge key={j} code={a.code} type={a.type}/>)}</div>}
              </div>);
            }

            return parts;
          });
        })()}
      </div>

      {/* Sidebar */}
      <div style={{borderLeft:"1px solid #e5e5e5",paddingLeft:16,fontSize:12}}>
        {D.beliefs.has_divergence&&<div style={{marginBottom:18}}>
          <h3 style={{fontSize:10,fontWeight:500,color:"#999",textTransform:"uppercase",letterSpacing:0.8,marginBottom:8,fontFamily:"monospace"}}>Belief divergence</h3>
          {Object.entries(D.beliefs.beliefs).map(([a,b],i)=>{
            const c=ac(a,agents);
            return <div key={a}>
              <div style={{padding:"8px 10px",borderRadius:6,marginBottom:4,border:`1px solid ${c}25`,background:`${c}08`}}>
                <div style={{fontFamily:"monospace",fontSize:9,textTransform:"uppercase",letterSpacing:0.8,color:c,marginBottom:2}}>{a}</div>
                <div style={{fontSize:11,color:"#666",lineHeight:1.4}}>"{b}"</div>
              </div>
              {i===0&&Object.keys(D.beliefs.beliefs).length>1&&<div style={{textAlign:"center",fontFamily:"monospace",fontSize:10,color:"#dc2626",padding:"2px 0"}}>⚡ beliefs diverge</div>}
            </div>;
          })}
        </div>}

        {Object.keys(D.failures).length>0&&<div style={{marginBottom:18}}>
          <h3 style={{fontSize:10,fontWeight:500,color:"#999",textTransform:"uppercase",letterSpacing:0.8,marginBottom:8,fontFamily:"monospace"}}>Detected failures</h3>
          {Object.entries(D.failures).map(([code,info])=>{
            const m=MAST[code]||{};
            const cnt=D.turns.filter(t=>t.annotations.some(a=>a.code===code)).length;
            return <div key={code} style={{display:"flex",gap:6,padding:"5px 0",borderBottom:"1px solid #f0f0f0",alignItems:"flex-start"}}>
              <span style={{fontFamily:"monospace",fontSize:10,color:"#dc2626",background:"rgba(220,38,38,0.06)",border:"1px solid rgba(220,38,38,0.15)",padding:"0px 4px",borderRadius:3,whiteSpace:"nowrap"}}>{code}</span>
              <div>
                <div style={{fontSize:11,color:"#333",fontWeight:500}}>{m.l||info.label}</div>
                <div style={{fontSize:9.5,color:"#999"}}>{m.c||info.category}{cnt?" · "+cnt+" turn(s)":" · trace-level"}</div>
              </div>
            </div>;
          })}
        </div>}

        {D.loops.length>0&&<div style={{marginBottom:18}}>
          <h3 style={{fontSize:10,fontWeight:500,color:"#999",textTransform:"uppercase",letterSpacing:0.8,marginBottom:8,fontFamily:"monospace"}}>Loops</h3>
          {D.loops.map((l,i)=><div key={i} style={{fontFamily:"monospace",fontSize:10,color:"#666",padding:"4px 8px",borderRadius:4,background:"rgba(220,38,38,0.04)",border:"1px solid rgba(220,38,38,0.12)",marginBottom:3}}>Turns {l.start+1}–{l.end+1}</div>)}
        </div>}

        <div style={{marginBottom:18}}>
          <h3 style={{fontSize:10,fontWeight:500,color:"#999",textTransform:"uppercase",letterSpacing:0.8,marginBottom:8,fontFamily:"monospace"}}>Metadata</h3>
          <div style={{fontFamily:"monospace",fontSize:10.5,lineHeight:1.8,color:"#777",background:"#f8f8f6",borderRadius:6,padding:"8px 10px"}}>
            <div><span style={{color:"#2563eb"}}>framework</span>: {D.meta.framework}</div>
            <div><span style={{color:"#2563eb"}}>benchmark</span>: {D.meta.benchmark}</div>
            <div><span style={{color:"#2563eb"}}>llm</span>: {D.meta.llm}</div>
            <div><span style={{color:"#2563eb"}}>turns</span>: {D.meta.total_turns}</div>
            <div><span style={{color:"#2563eb"}}>failures</span>: [{Object.keys(D.failures).map(c=>'"'+c+'"').join(", ")}]</div>
          </div>
        </div>

        {D.meta.note_text&&<div>
          <h3 style={{fontSize:10,fontWeight:500,color:"#999",textTransform:"uppercase",letterSpacing:0.8,marginBottom:8,fontFamily:"monospace"}}>Expert note</h3>
          <div style={{fontSize:11,color:"#777",lineHeight:1.45,fontStyle:"italic",background:"#f8f8f6",padding:8,borderRadius:6}}>{D.meta.note_text}</div>
        </div>}
      </div>
    </div>
  </div>;
}
