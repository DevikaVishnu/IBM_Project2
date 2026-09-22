import { useState, useRef, useCallback, useEffect, useMemo } from "react";

/* ═══════════════════════════════════════════════
   AGENT REASONING STATE DEFINITIONS
   ═══════════════════════════════════════════════ */
// IBM colorblind-safe palette — distinguishable under deuteranopia, protanopia & tritanopia
// Each state uses a different hue band AND a different lightness level
const ST = {
  idle:       { color: "#f4f4f4", fg: "#525252", label: "Idle",         icon: "·", desc: "Agent exists but not yet active in any phase" },
  asking:     { color: "#bae6ff", fg: "#003a6d", label: "Asking",       icon: "?", desc: "Posing a question or requesting action" },
  proposing:  { color: "#6fdc8c", fg: "#044317", label: "Proposing",    icon: "→", desc: "Suggesting an approach or design decision" },
  building:   { color: "#4589ff", fg: "#ffffff", label: "Building",     icon: "⚙", desc: "Writing code or producing artifacts" },
  reviewing:  { color: "#d4bbff", fg: "#31135e", label: "Reviewing",    icon: "◎", desc: "Evaluating or reflecting on work" },
  req_change: { color: "#f1c21b", fg: "#3e2400", label: "Wants change", icon: "△", desc: "Requesting modifications to current work" },
  approving:  { color: "#08bdba", fg: "#ffffff", label: "Approving",    icon: "✓", desc: "Accepting work as complete" },
  blocked:    { color: "#fa4d56", fg: "#ffffff", label: "Blocked",      icon: "✗", desc: "Believes task cannot proceed" },
  pushing:    { color: "#ff832b", fg: "#ffffff", label: "Pushing",      icon: "▸", desc: "Insisting task continue despite issues" },
  completing: { color: "#009d9a", fg: "#ffffff", label: "Completing",   icon: "◆", desc: "Producing final documentation or deliverables" },
};

const DIV_COLORS = { high: "#dc2626", medium: "#d97706", low: "#6b7280" };

/* Phase display metadata */
const PHASE_META = {
  DemandAnalysis:        { short: "Demand Analysis",  color: "#7c3aed" },
  LanguageChoose:        { short: "Language Choice",  color: "#2563eb" },
  RolePlaying:           { short: "Role Setup",       color: "#94a3b8" },
  Coding:                { short: "Coding",           color: "#0891b2" },
  CodeReviewComment:     { short: "Code Review",      color: "#d97706" },
  CodeReviewModification:{ short: "CR Modify",        color: "#ea580c" },
  TestErrorSummary:      { short: "Test Summary",     color: "#dc2626" },
  EnvironmentDoc:        { short: "Env Doc",          color: "#059669" },
  Reflection:            { short: "Reflection",       color: "#0d9488" },
  Manual:                { short: "Manual",           color: "#4f46e5" },
};

/** For a given turn, determine which agents are "active" (speaker or the other agent in the dyad) vs passive */
function getActiveAgentsForTurn(D, turnIdx) {
  const speaker = D.speakers[turnIdx];
  if (!speaker || speaker === "Conclusion") return new Set();
  const phase = D.phases[turnIdx];
  // Look at nearby turns in the same phase to find the dyad partner
  const dyad = new Set();
  dyad.add(speaker);
  for (let i = Math.max(0, turnIdx - 3); i < Math.min(D.speakers.length, turnIdx + 3); i++) {
    if (D.phases[i] === phase && D.speakers[i] && D.speakers[i] !== "Conclusion" && D.speakers[i] !== speaker) {
      dyad.add(D.speakers[i]);
      break;
    }
  }
  return dyad;
}

const sn = n => ({"Chief Executive Officer":"Exec Officer","Chief Product Officer":"Product Officer",
  "Chief Technology Officer":"Technology Officer","Code Reviewer":"Code Reviewer",
  "mathproxyagent":"MathProxy","Counselor":"Counselor","Programmer":"Programmer",
  "System":"System"}[n] || (n.length>18?n.slice(0,17)+"…":n));

/* ═══════════════════════════════════════════════
   SAMPLE DATA — AG2 (10 turns, clear divergence)
   ═══════════════════════════════════════════════ */
const AG2 = {
  meta:{framework:"AG2",benchmark:"GSM-Plus",problem:"Monica ribbon problem — unsolvable due to missing data",total_turns:10},
  agents:["mathproxyagent","assistant"],
  failures:{"1.5":"Unaware of stopping conditions","2.5":"Ignored other agent input","1.3":"Step repetition"},
  shorts:["setup problem","insufficient data","continue","re-explains","continue","re-explains","continue","re-explains","continue","final answer"],
  phases:["","","","","","","","","",""],
  speakers:["mathproxyagent","assistant","mathproxyagent","assistant","mathproxyagent","assistant","mathproxyagent","assistant","mathproxyagent","assistant"],
  // timeline[turn][agent] = state
  states:[
    ["asking","idle"],["asking","blocked"],["pushing","blocked"],["pushing","blocked"],
    ["pushing","blocked"],["pushing","blocked"],["pushing","blocked"],["pushing","blocked"],
    ["pushing","blocked"],["pushing","blocked"],
  ],
  divergences:[
    {t:2,type:"blocked_vs_pushing",sev:"high",agents:["mathproxyagent","assistant"],
     desc:"mathproxyagent insists the task continue, but assistant believes it cannot proceed. The agents have fundamentally different views of task feasibility.",fm:["1.5","2.5"],det:"live"},
    {t:4,type:"repetition_loop",sev:"medium",agents:["mathproxyagent"],
     desc:"mathproxyagent repeats identical 'Continue' message from turn 3. The system is stuck in a loop it cannot escape.",fm:["1.3"],det:"live"},
    {t:6,type:"repetition_loop",sev:"medium",agents:["mathproxyagent"],
     desc:"mathproxyagent repeats identical content again. Loop has persisted for 5 turns with no progress.",fm:["1.3"],det:"live"},
    {t:8,type:"repetition_loop",sev:"medium",agents:["mathproxyagent"],
     desc:"mathproxyagent repeats identical content. This is the 4th repetition — system never recognizes stopping conditions.",fm:["1.3","1.5"],det:"live"},
  ],
};

/* ═══════════════════════════════════════════════
   SAMPLE DATA — ChatDev Checkers (Trace 0, 0 failures)
   26 real turns — 3 review cycles catching progressively deeper bugs
   Parsed directly from ChatDev log: every turn = one agent speaking
   ═══════════════════════════════════════════════ */
const CHATDEV = {
  meta:{framework:"ChatDev",benchmark:"ProgramDev",problem:"Checkers (Draughts) — gui_design: True — GPT-4o · Trace 0 · 0 MAST failures",total_turns:26},
  agents:["Chief Executive Officer","Chief Product Officer","Chief Technology Officer","Programmer","Code Reviewer","Counselor"],
  failures:{},
  shorts:[
    "asks modality","proposes App","agrees: Application",
    "asks language","Python",
    "instructs coding","writes piece.py board.py main.py",
    "submits for review","main.py has no game loop",
    "requests fix","rewrites main.py with game loop",
    "submits for review","king capture logic wrong",
    "requests fix","rewrites valid_move for kings",
    "submits for review","missing multi-capture",
    "requests fix","adds has_capture_moves",
    "Test Pass!",
    "asks for deps","no external deps",
    "reviews project","confirms no deps",
    "requests manual","writes manual.md"
  ],
  phases:[
    "DemandAnalysis","DemandAnalysis","DemandAnalysis",
    "LanguageChoose","LanguageChoose",
    "Coding","Coding",
    "CodeReviewComment","CodeReviewComment",
    "CodeReviewModification","CodeReviewModification",
    "CodeReviewComment","CodeReviewComment",
    "CodeReviewModification","CodeReviewModification",
    "CodeReviewComment","CodeReviewComment",
    "CodeReviewModification","CodeReviewModification",
    "TestErrorSummary",
    "EnvironmentDoc","EnvironmentDoc",
    "Reflection","Reflection",
    "Manual","Manual"
  ],
  speakers:[
    "Chief Executive Officer","Chief Product Officer","Chief Executive Officer",
    "Chief Executive Officer","Chief Technology Officer",
    "Chief Technology Officer","Programmer",
    "Programmer","Code Reviewer",
    "Code Reviewer","Programmer",
    "Programmer","Code Reviewer",
    "Code Reviewer","Programmer",
    "Programmer","Code Reviewer",
    "Code Reviewer","Programmer",
    "System",
    "Chief Technology Officer","Programmer",
    "Counselor","Chief Executive Officer",
    "Chief Executive Officer","Chief Product Officer"
  ],
  states: [
    // [CEO, CPO, CTO, Prog, Reviewer, Counselor]
    ["proposing","idle","idle","idle","idle","idle"],      // 0  DemandAnalysis — CEO asks modality
    ["idle","proposing","idle","idle","idle","idle"],      // 1  DemandAnalysis — CPO proposes App
    ["approving","idle","idle","idle","idle","idle"],      // 2  DemandAnalysis — CEO agrees
    ["proposing","idle","idle","idle","idle","idle"],      // 3  LanguageChoose — CEO asks language
    ["idle","idle","proposing","idle","idle","idle"],      // 4  LanguageChoose — CTO: Python
    ["idle","idle","proposing","idle","idle","idle"],      // 5  Coding — CTO instructs
    ["idle","idle","idle","building","idle","idle"],       // 6  Coding — Programmer writes code
    ["idle","idle","idle","proposing","idle","idle"],      // 7  ReviewComment C1 — Programmer submits
    ["idle","idle","idle","idle","req_change","idle"],     // 8  ReviewComment C1 — Reviewer: no game loop
    ["idle","idle","idle","idle","proposing","idle"],     // 9  ReviewModify C1 — Reviewer instructs fix
    ["idle","idle","idle","building","idle","idle"],       // 10 ReviewModify C1 — Programmer rewrites
    ["idle","idle","idle","proposing","idle","idle"],      // 11 ReviewComment C2 — Programmer submits
    ["idle","idle","idle","idle","req_change","idle"],     // 12 ReviewComment C2 — Reviewer: king logic
    ["idle","idle","idle","idle","proposing","idle"],      // 13 ReviewModify C2 — Reviewer instructs
    ["idle","idle","idle","building","idle","idle"],       // 14 ReviewModify C2 — Programmer fixes
    ["idle","idle","idle","proposing","idle","idle"],      // 15 ReviewComment C3 — Programmer submits
    ["idle","idle","idle","idle","req_change","idle"],     // 16 ReviewComment C3 — Reviewer: multi-capture
    ["idle","idle","idle","idle","proposing","idle"],      // 17 ReviewModify C3 — Reviewer instructs
    ["idle","idle","idle","building","idle","idle"],       // 18 ReviewModify C3 — Programmer adds logic
    ["idle","idle","idle","idle","idle","idle"],           // 19 TestErrorSummary — System: Pass
    ["idle","idle","proposing","idle","idle","idle"],      // 20 EnvironmentDoc — CTO asks
    ["idle","idle","idle","completing","idle","idle"],     // 21 EnvironmentDoc — Programmer: no deps
    ["idle","idle","idle","idle","idle","reviewing"],      // 22 Reflection — Counselor reviews
    ["reviewing","idle","idle","idle","idle","idle"],      // 23 Reflection — CEO confirms
    ["proposing","idle","idle","idle","idle","idle"],      // 24 Manual — CEO requests
    ["idle","completing","idle","idle","idle","idle"],     // 25 Manual — CPO writes manual
  ],
  divergences:[],
};

/* ═══════════════════════════════════════════════
   SAMPLE DATA — ChatDev TicTacToe (Trace 6, 1 failure)
   26 turns — Reviewer rubber-stamps in C1 & C3
   MAST 1.1: gui_design=True but CLI-only produced
   ═══════════════════════════════════════════════ */
const CHATDEV_TTT = {
  meta:{framework:"ChatDev",benchmark:"ProgramDev",problem:"Tic-Tac-Toe — gui_design: True — GPT-4o · Trace 6 · 1 MAST failure (1.1)",total_turns:26},
  agents:["Chief Executive Officer","Chief Product Officer","Chief Technology Officer","Programmer","Code Reviewer","Counselor"],
  failures:{"1.1":"Task-agent mismatch: gui_design=True but CLI-only produced"},
  shorts:[
    "asks modality","proposes Application","agrees: Application",
    "asks language","Python",
    "instructs coding","writes main.py + tic_tac_toe.py (CLI only ⚠️)",
    "submits for review","<INFO> Finished — rubber stamp ⚠️",
    "passes comments (Finished)","cosmetic changes (Welcome msg)",
    "submits for review","check_winner docstring unclear",
    "requests docstring fix","updates check_winner docstring",
    "submits for review","<INFO> Finished",
    "passes comments (Finished)","no changes",
    "Test Pass!",
    "asks for deps","no external deps",
    "reviews project","confirms no deps",
    "requests manual","writes manual.md"
  ],
  phases:[
    "DemandAnalysis","DemandAnalysis","DemandAnalysis",
    "LanguageChoose","LanguageChoose",
    "Coding","Coding",
    "CodeReviewComment","CodeReviewComment",
    "CodeReviewModification","CodeReviewModification",
    "CodeReviewComment","CodeReviewComment",
    "CodeReviewModification","CodeReviewModification",
    "CodeReviewComment","CodeReviewComment",
    "CodeReviewModification","CodeReviewModification",
    "TestErrorSummary",
    "EnvironmentDoc","EnvironmentDoc",
    "Reflection","Reflection",
    "Manual","Manual"
  ],
  speakers:[
    "Chief Executive Officer","Chief Product Officer","Chief Executive Officer",
    "Chief Executive Officer","Chief Technology Officer",
    "Chief Technology Officer","Programmer",
    "Programmer","Code Reviewer",
    "Code Reviewer","Programmer",
    "Programmer","Code Reviewer",
    "Code Reviewer","Programmer",
    "Programmer","Code Reviewer",
    "Code Reviewer","Programmer",
    "System",
    "Chief Technology Officer","Programmer",
    "Counselor","Chief Executive Officer",
    "Chief Executive Officer","Chief Product Officer"
  ],
  states: [
    // [CEO, CPO, CTO, Prog, Reviewer, Counselor]
    ["proposing","idle","idle","idle","idle","idle"],      // 0  DemandAnalysis — CEO asks
    ["idle","proposing","idle","idle","idle","idle"],      // 1  DemandAnalysis — CPO proposes App
    ["approving","idle","idle","idle","idle","idle"],      // 2  DemandAnalysis — CEO agrees
    ["proposing","idle","idle","idle","idle","idle"],      // 3  LanguageChoose — CEO asks
    ["idle","idle","proposing","idle","idle","idle"],      // 4  LanguageChoose — CTO: Python
    ["idle","idle","proposing","idle","idle","idle"],      // 5  Coding — CTO instructs
    ["idle","idle","idle","building","idle","idle"],       // 6  Coding — Programmer (CLI only ⚠️)
    ["idle","idle","idle","proposing","idle","idle"],      // 7  ReviewComment C1 — Programmer submits
    ["idle","idle","idle","idle","approving","idle"],      // 8  ReviewComment C1 — Reviewer: Finished ⚠️
    ["idle","idle","idle","idle","proposing","idle"],      // 9  ReviewModify C1 — Reviewer passes
    ["idle","idle","idle","building","idle","idle"],      // 10 ReviewModify C1 — Programmer: cosmetic
    ["idle","idle","idle","proposing","idle","idle"],      // 11 ReviewComment C2 — Programmer submits
    ["idle","idle","idle","idle","req_change","idle"],     // 12 ReviewComment C2 — Reviewer: docstring
    ["idle","idle","idle","idle","proposing","idle"],      // 13 ReviewModify C2 — Reviewer instructs
    ["idle","idle","idle","building","idle","idle"],       // 14 ReviewModify C2 — Programmer fixes
    ["idle","idle","idle","proposing","idle","idle"],      // 15 ReviewComment C3 — Programmer submits
    ["idle","idle","idle","idle","approving","idle"],      // 16 ReviewComment C3 — Reviewer: Finished
    ["idle","idle","idle","idle","proposing","idle"],      // 17 ReviewModify C3 — Reviewer passes
    ["idle","idle","idle","approving","idle","idle"],      // 18 ReviewModify C3 — Programmer: no changes
    ["idle","idle","idle","idle","idle","idle"],           // 19 TestErrorSummary — System: Pass
    ["idle","idle","proposing","idle","idle","idle"],      // 20 EnvironmentDoc — CTO asks
    ["idle","idle","idle","completing","idle","idle"],     // 21 EnvironmentDoc — Programmer: no deps
    ["idle","idle","idle","idle","idle","reviewing"],      // 22 Reflection — Counselor reviews
    ["reviewing","idle","idle","idle","idle","idle"],      // 23 Reflection — CEO confirms
    ["proposing","idle","idle","idle","idle","idle"],      // 24 Manual — CEO requests
    ["idle","completing","idle","idle","idle","idle"],     // 25 Manual — CPO writes manual
  ],
  divergences:[
    {t:6,type:"gui_requirement_ignored",sev:"high",agents:["Programmer"],
     desc:"gui_design=True in config but Programmer builds CLI-only app. The GUI requirement from the task specification was never addressed.",fm:["1.1"]},
    {t:8,type:"rubber_stamp_review",sev:"high",agents:["Code Reviewer"],
     desc:"Reviewer says '<INFO> Finished' despite the code being CLI-only when gui_design=True. The missing GUI requirement was not flagged.",fm:["1.1"]},
  ],
};

/* ═══════════════════════════════════════════════
   SAMPLE DATA — ChatDev Gomoku (Trace 7, 2 failures)
   26 turns — 2 of 3 review cycles rubber-stamped
   MAST 1.3: ignored GUI constraint, 3.3: wrong final output
   ═══════════════════════════════════════════════ */
const CHATDEV_GOMOKU = {
  meta:{framework:"ChatDev",benchmark:"ProgramDev",problem:"Gomoku — gui_design: True — GPT-4o · Trace 7 · 2 MAST failures (1.3, 3.3)",total_turns:26},
  agents:["Chief Executive Officer","Chief Product Officer","Chief Technology Officer","Programmer","Code Reviewer","Counselor"],
  failures:{"1.3":"Ignored GUI constraint: gui_design=True but CLI-only","3.3":"Wrong final output: CLI-only, incomplete vs specification"},
  shorts:[
    "asks modality","proposes Application","agrees → Application",
    "asks language","<INFO> Python",
    "instructs coding","writes gomoku.py + main.py (CLI only ⚠️)",
    "submits for review","<INFO> Finished — rubber stamp ⚠️",
    "passes comments (Finished)","cosmetic: improved error/win messages",
    "submits for review","<INFO> Finished — rubber stamp ⚠️",
    "passes comments (Finished)","no real changes",
    "submits for review","place_stone errors not specific enough",
    "instructs: split bounds vs occupied","splits place_stone into specific errors",
    "Test Pass!",
    "asks for deps","no external deps",
    "reviews project","confirms no deps",
    "requests manual","writes manual.md ⚠️ describes CLI as complete"
  ],
  phases:[
    "DemandAnalysis","DemandAnalysis","DemandAnalysis",
    "LanguageChoose","LanguageChoose",
    "Coding","Coding",
    "CodeReviewComment","CodeReviewComment",
    "CodeReviewModification","CodeReviewModification",
    "CodeReviewComment","CodeReviewComment",
    "CodeReviewModification","CodeReviewModification",
    "CodeReviewComment","CodeReviewComment",
    "CodeReviewModification","CodeReviewModification",
    "TestErrorSummary",
    "EnvironmentDoc","EnvironmentDoc",
    "Reflection","Reflection",
    "Manual","Manual"
  ],
  speakers:[
    "Chief Executive Officer","Chief Product Officer","Chief Executive Officer",
    "Chief Executive Officer","Chief Technology Officer",
    "Chief Technology Officer","Programmer",
    "Programmer","Code Reviewer",
    "Code Reviewer","Programmer",
    "Programmer","Code Reviewer",
    "Code Reviewer","Programmer",
    "Programmer","Code Reviewer",
    "Code Reviewer","Programmer",
    "System",
    "Chief Technology Officer","Programmer",
    "Counselor","Chief Executive Officer",
    "Chief Executive Officer","Chief Product Officer"
  ],
  states: [
    // [CEO, CPO, CTO, Prog, Reviewer, Counselor]
    ["proposing","idle","idle","idle","idle","idle"],      // 0  DemandAnalysis — CEO asks
    ["idle","proposing","idle","idle","idle","idle"],      // 1  DemandAnalysis — CPO proposes App
    ["approving","idle","idle","idle","idle","idle"],      // 2  DemandAnalysis — CEO agrees
    ["proposing","idle","idle","idle","idle","idle"],      // 3  LanguageChoose — CEO asks
    ["idle","idle","proposing","idle","idle","idle"],      // 4  LanguageChoose — CTO: Python
    ["idle","idle","proposing","idle","idle","idle"],      // 5  Coding — CTO instructs
    ["idle","idle","idle","building","idle","idle"],       // 6  Coding — Programmer (CLI only ⚠️)
    ["idle","idle","idle","proposing","idle","idle"],      // 7  ReviewComment C1 — Programmer submits
    ["idle","idle","idle","idle","approving","idle"],      // 8  ReviewComment C1 — Reviewer: Finished ⚠️
    ["idle","idle","idle","idle","proposing","idle"],      // 9  ReviewModify C1 — Reviewer passes
    ["idle","idle","idle","building","idle","idle"],       // 10 ReviewModify C1 — Programmer: cosmetic
    ["idle","idle","idle","proposing","idle","idle"],      // 11 ReviewComment C2 — Programmer submits
    ["idle","idle","idle","idle","approving","idle"],      // 12 ReviewComment C2 — Reviewer: Finished ⚠️
    ["idle","idle","idle","idle","proposing","idle"],      // 13 ReviewModify C2 — Reviewer passes
    ["idle","idle","idle","approving","idle","idle"],      // 14 ReviewModify C2 — Programmer: no changes
    ["idle","idle","idle","proposing","idle","idle"],      // 15 ReviewComment C3 — Programmer submits
    ["idle","idle","idle","idle","req_change","idle"],     // 16 ReviewComment C3 — Reviewer: place_stone
    ["idle","idle","idle","idle","proposing","idle"],      // 17 ReviewModify C3 — Reviewer instructs
    ["idle","idle","idle","building","idle","idle"],       // 18 ReviewModify C3 — Programmer fixes
    ["idle","idle","idle","idle","idle","idle"],           // 19 TestErrorSummary — System: Pass
    ["idle","idle","proposing","idle","idle","idle"],      // 20 EnvironmentDoc — CTO asks
    ["idle","idle","idle","completing","idle","idle"],     // 21 EnvironmentDoc — Programmer: no deps
    ["idle","idle","idle","idle","idle","reviewing"],      // 22 Reflection — Counselor reviews
    ["reviewing","idle","idle","idle","idle","idle"],      // 23 Reflection — CEO confirms
    ["proposing","idle","idle","idle","idle","idle"],      // 24 Manual — CEO requests
    ["idle","completing","idle","idle","idle","idle"],     // 25 Manual — CPO writes manual ⚠️
  ],
  divergences:[
    {t:6,type:"gui_requirement_ignored",sev:"high",agents:["Programmer"],
     desc:"gui_design=True in config but Programmer builds CLI-only app. The GUI constraint was ignored at the coding phase.",fm:["1.3"]},
    {t:8,type:"rubber_stamp_review",sev:"high",agents:["Code Reviewer"],
     desc:"Reviewer says '<INFO> Finished' despite CLI-only code when gui_design=True. First rubber-stamp — GUI gap not flagged.",fm:["1.3"]},
    {t:12,type:"rubber_stamp_review",sev:"medium",agents:["Code Reviewer"],
     desc:"Second consecutive '<INFO> Finished' rubber-stamp. Pattern of non-review established.",fm:["1.3"]},
    {t:25,type:"wrong_final_output",sev:"high",agents:["Chief Product Officer"],
     desc:"Manual describes CLI-only Gomoku as the complete product. The GUI requirement was never recovered — cascading into wrong final output.",fm:["3.3"]},
  ],
};

/* ═══════════════════════════════════════════════
   HELPER: Parse uploaded enriched JSON into display format
   ═══════════════════════════════════════════════ */
function parseEnrichedJSON(data) {
  const agents = data.belief_agents || data.agents || [];
  const timeline = data.belief_timeline || [];
  const states = timeline.map(snap => 
    agents.map(a => snap.agents?.[a]?.state || "idle")
  );
  const speakers = timeline.map(snap => snap.speaker || "");
  const phases = timeline.map(snap => snap.phase || "");
  const shorts = (data.turns || []).map(t => t.short || t.summary || "");
  const divergences = (data.divergence_events || []).map(d => ({
    t: d.turn, type: d.type, sev: d.severity || "medium",
    agents: d.agents || [], desc: d.description || "",
    fm: d.related_failures || [], det: d.detection || "live",
  }));
  const failures = {};
  for (const [k,v] of Object.entries(data.failures || {})) {
    failures[k] = typeof v === "string" ? v : v.label || v.l || k;
  }
  return { agents, states, speakers, phases, shorts, divergences, failures, meta: data.meta || {} };
}

/* ═══════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════ */
export default function BeliefEvolution() {
  const [source, setSource] = useState("ag2");
  const [custom, setCustom] = useState(null);
  const [playhead, setPlayhead] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [selected, setSelected] = useState(null); // {type:"cell",turn,agentIdx} or {type:"div",idx}
  const [highlightedPhase, setHighlightedPhase] = useState(null); // phase name user clicked
  const fileRef = useRef(null);
  const playRef = useRef(null);

  const raw = custom || (source === "ag2" ? AG2 : source === "chatdev" ? CHATDEV : source === "chatdev_ttt" ? CHATDEV_TTT : source === "chatdev_gomoku" ? CHATDEV_GOMOKU : CHATDEV);
  const D = raw;
  const totalTurns = D.states.length;

  // Reset playhead on source change
  useEffect(() => { setPlayhead(0); setSelected(null); setPlaying(false); setHighlightedPhase(null); }, [source]);

  // Autoplay
  useEffect(() => {
    if (!playing) return;
    playRef.current = setInterval(() => {
      setPlayhead(p => {
        if (p >= totalTurns - 1) { setPlaying(false); return p; }
        return p + 1;
      });
    }, 600);
    return () => clearInterval(playRef.current);
  }, [playing, totalTurns]);

  // File upload handler
  const handleUpload = useCallback((e) => {
    const file = e.target.files[0]; if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const data = JSON.parse(ev.target.result);
        const parsed = parseEnrichedJSON(data);
        setCustom(parsed);
        setSource("custom");
        setPlayhead(0);
        setSelected(null);
      } catch (err) { alert("Parse error: " + err.message); }
    };
    reader.readAsText(file);
  }, []);

  // Collect phases for dividers — now includes dyad agents
  const phaseRanges = useMemo(() => {
    const ranges = [];
    let cur = null;
    for (let i = 0; i <= playhead; i++) {
      const p = D.phases[i];
      if (p && p !== "RolePlaying" && (!cur || cur.name !== p)) {
        if (cur) cur.end = i - 1;
        // Find dyad agents for this phase
        const dyadAgents = new Set();
        for (let j = i; j < D.phases.length && D.phases[j] === p; j++) {
          if (D.speakers[j] && D.speakers[j] !== "Conclusion") dyadAgents.add(D.speakers[j]);
        }
        cur = { name: p, start: i, end: i, agents: [...dyadAgents] };
        ranges.push(cur);
      } else if (cur) { cur.end = i; }
    }
    return ranges;
  }, [D.phases, D.speakers, playhead]);

  // Which phase is the current playhead turn in?
  const currentPhase = useMemo(() => {
    return phaseRanges.find(pr => playhead >= pr.start && playhead <= pr.end) || null;
  }, [phaseRanges, playhead]);

  // Compute which belief states actually appear in this dataset (for legend filtering)
  const usedStates = useMemo(() => {
    const s = new Set();
    for (let ti = 0; ti <= playhead; ti++) {
      for (const st of (D.states[ti] || [])) { s.add(st); }
    }
    return s;
  }, [D.states, playhead]);

  // Visible divergences (up to playhead)
  const visibleDivs = useMemo(() =>
    D.divergences.filter(d => d.t <= playhead),
    [D.divergences, playhead]
  );

  // Which turns have divergence markers
  const divTurns = useMemo(() => {
    const s = new Set();
    visibleDivs.forEach(d => s.add(d.t));
    return s;
  }, [visibleDivs]);

  const CELL_W = Math.max(58, Math.min(80, 900 / totalTurns));
  const CELL_H = 38;
  const CELL_GAP = 2; // gap between cells
  const COL = CELL_W + CELL_GAP; // total column slot width
  const LABEL_W = 140;
  const gridW = LABEL_W + totalTurns * COL + 20;

  // Detail panel content
  const detail = useMemo(() => {
    if (!selected) return null;
    if (selected.type === "cell") {
      const { turn, agentIdx } = selected;
      const agent = D.agents[agentIdx];
      const state = D.states[turn]?.[agentIdx] || "idle";
      const isSpeaker = D.speakers[turn] === agent;
      const short = D.shorts[turn] || "";
      const divsHere = D.divergences.filter(d => d.t === turn && d.agents.includes(agent));
      // Find the phase this turn belongs to
      const phase = D.phases[turn] && D.phases[turn] !== "RolePlaying" ? D.phases[turn] : null;
      const phaseRange = phaseRanges.find(pr => turn >= pr.start && turn <= pr.end);
      const activeAgents = getActiveAgentsForTurn(D, turn);
      const isActiveInPhase = activeAgents.has(agent);
      return { kind: "cell", agent, turn, state, isSpeaker, short, divsHere, phase, phaseRange, isActiveInPhase };
    }
    if (selected.type === "div") {
      const d = visibleDivs[selected.idx];
      const phase = D.phases[d.t] && D.phases[d.t] !== "RolePlaying" ? D.phases[d.t] : null;
      const phaseRange = phaseRanges.find(pr => d.t >= pr.start && d.t <= pr.end);
      return { kind: "div", ...d, phase, phaseRange };
    }
    return null;
  }, [selected, D, visibleDivs, phaseRanges]);

  return (
    <div style={css.root}>
      {/* ─── HEADER ─── */}
      <div style={css.header}>
        <div style={css.titleBlock}>
          <span style={css.title}>AgentTrace</span>
          <span style={css.subtitle}>Reasoning State Evolution</span>
        </div>
        <div style={css.controls}>
          <button onClick={()=>{setSource("ag2");setCustom(null);}} style={{...css.srcBtn,...(source==="ag2"?css.srcActive:{})}}>AG2 sample</button>
          <button onClick={()=>{setSource("chatdev");setCustom(null);}} style={{...css.srcBtn,...(source==="chatdev"?css.srcActive:{})}}>Checkers (0 fail)</button>
          <button onClick={()=>{setSource("chatdev_ttt");setCustom(null);}} style={{...css.srcBtn,...(source==="chatdev_ttt"?css.srcActive:{})}}>TicTacToe (1 fail)</button>
          <button onClick={()=>{setSource("chatdev_gomoku");setCustom(null);}} style={{...css.srcBtn,...(source==="chatdev_gomoku"?css.srcActive:{})}}>Gomoku (2 fail)</button>
          <button onClick={()=>fileRef.current?.click()} style={css.uploadBtn}>↑ Load enriched JSON</button>
          <input ref={fileRef} type="file" accept=".json" onChange={handleUpload} style={{display:"none"}}/>
        </div>
      </div>

      {/* ─── PROBLEM ─── */}
      {D.meta.problem && <div style={css.problem}>{D.meta.problem}</div>}

      {/* ─── PHASE TABS ─── */}
      {(() => {
        // Collect unique phases in order from data
        const seen = new Set();
        const uniquePhases = [];
        for (const p of D.phases) {
          if (p && p !== "RolePlaying" && !seen.has(p)) { seen.add(p); uniquePhases.push(p); }
        }
        if (uniquePhases.length === 0) return null;
        return (
          <div style={{display:"flex",gap:6,flexWrap:"wrap",padding:"8px 0 4px",borderBottom:"1px solid #e2e8f0",marginBottom:0}}>
            {uniquePhases.map(pname => {
              const pm = PHASE_META[pname] || {short:pname,color:"#94a3b8"};
              // Find the first turn of this phase in the data
              const firstTurn = D.phases.indexOf(pname);
              const isActive = currentPhase && currentPhase.name === pname;
              const isHighlighted = highlightedPhase === pname;
              const isReached = firstTurn <= playhead;
              return (
                <button key={pname}
                  onClick={() => {
                    if (firstTurn >= 0) {
                      setPlayhead(Math.max(firstTurn, firstTurn));
                      setHighlightedPhase(pname);
                      setPlaying(false);
                      setSelected(null);
                    }
                  }}
                  style={{
                    fontSize: 11, fontWeight: isActive || isHighlighted ? 700 : 500,
                    padding: "4px 12px",
                    borderRadius: 16,
                    border: isActive || isHighlighted
                      ? `2px solid ${pm.color}`
                      : `1px solid ${isReached ? pm.color+"60" : "#e2e8f0"}`,
                    background: isActive || isHighlighted
                      ? pm.color
                      : isReached ? pm.color+"12" : "#f8fafc",
                    color: isActive || isHighlighted ? "#fff" : isReached ? pm.color : "#94a3b8",
                    cursor: "pointer",
                    fontFamily: "inherit",
                    transition: "all 0.15s",
                    boxShadow: isActive || isHighlighted ? `0 2px 8px ${pm.color}44` : "none",
                    outline: "none",
                  }}
                >
                  {pm.short}
                </button>
              );
            })}
          </div>
        );
      })()}

      {/* ─── PLAYHEAD ─── */}
      <div style={css.playbar}>
        <button onClick={()=>{setPlaying(!playing);}} style={css.playBtn}>{playing?"⏸":"▶"}</button>
        <button onClick={()=>{setPlayhead(0);setPlaying(false);setSelected(null);}} style={css.playBtn}>⏮</button>
        <input type="range" min={0} max={totalTurns-1} value={playhead}
          onChange={e=>{setPlayhead(+e.target.value);setPlaying(false);setHighlightedPhase(null);}}
          style={{flex:1,margin:"0 12px",accentColor:"#3b82f6"}} />
        <span style={css.turnLabel}>Turn <b>{playhead+1}</b> / {totalTurns}</span>
        {D.speakers[playhead] && <span style={css.speakerLabel}>— {sn(D.speakers[playhead])}</span>}
        {currentPhase && (() => {
          const pm = PHASE_META[currentPhase.name];
          return <span style={{
            fontSize:10, padding:"2px 8px", borderRadius:4,
            background: pm ? pm.color+"18" : "#f1f5f9",
            color: pm ? pm.color : "#64748b",
            border: `1px solid ${pm ? pm.color+"40" : "#e2e8f0"}`,
            fontFamily:"monospace", fontWeight:600,
            display:"inline-flex", alignItems:"center", gap:4,
          }}>
            {currentPhase.name}
            {currentPhase.agents.length > 0 && <span style={{fontWeight:400,opacity:0.8}}>
              ({currentPhase.agents.map(a=>sn(a)).join(" ↔ ")})
            </span>}
          </span>;
        })()}
      </div>

      {/* ─── MAIN AREA ─── */}
      <div style={css.mainArea}>
        {/* Grid wrapper: sticky labels on left, scrollable cells on right */}
        <div style={{flex:1, display:"flex", minWidth:0}}>

          {/* ── STICKY LABEL COLUMN ── */}
          <div style={{
            flexShrink: 0,
            width: LABEL_W,
            zIndex: 2,
            background: "#fff",
          }}>
            {/* Spacer for phase bar row */}
            <div style={{height: 38, marginBottom: 4}} />
            {/* Spacer for turn numbers row */}
            <div style={{height: 16, marginBottom: 2}} />
            {/* Agent name rows */}
            {D.agents.map((agent, ai) => (
              <div key={agent} style={{
                height: CELL_H + 4,
                marginBottom: 1,
                display: "flex",
                alignItems: "center",
                justifyContent: "flex-end",
                paddingRight: 10,
              }}>
                <span style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 10,
                  fontWeight: 600,
                  color: ai < 8 ? ["#2563eb","#059669","#7c3aed","#dc2626","#d97706","#0891b2","#4f46e5","#e11d48"][ai] : "#666",
                  overflow: "hidden",
                  whiteSpace: "nowrap",
                  textOverflow: "ellipsis",
                  maxWidth: LABEL_W - 14,
                  display: "block",
                  textAlign: "right",
                }}>{sn(agent)}</span>
              </div>
            ))}
            {/* Spacer for divergence track row */}
            <div style={{height: 32}} />
          </div>

          {/* ── SCROLLABLE CELLS COLUMN ── */}
          <div style={{overflowX: "auto", flex: 1, minWidth: 0}}>

          {/* Phase bars */}
          <div style={{position:"relative", minHeight:38, marginBottom:4, height:38}}>
            {phaseRanges.map((pr,i) => {
              const pm = PHASE_META[pr.name] || {short:pr.name,color:"#94a3b8"};
              const w = (pr.end - pr.start + 1) * COL - CELL_GAP;
              const isActive = currentPhase && currentPhase.name === pr.name && currentPhase.start === pr.start;
              const isHighlight = highlightedPhase === pr.name;
              return (
                <div key={i} style={{
                  position:"absolute",
                  left: pr.start * COL,
                  width: Math.max(w, 2),
                  top: 0,
                  bottom: 0,
                  display:"flex",flexDirection:"column",alignItems:"center",gap:0,
                }}>
                  <div style={{
                    width:"100%",
                    height: "100%",
                    background: isHighlight ? pm.color+"30" : isActive ? pm.color+"20" : pm.color+"0c",
                    borderTop: `2px solid ${isHighlight ? pm.color : isActive ? pm.color : pm.color+"60"}`,
                    borderLeft: `1px solid ${isHighlight ? pm.color+"80" : pm.color+"30"}`,
                    borderRight: `1px solid ${isHighlight ? pm.color+"80" : pm.color+"30"}`,
                    borderRadius:"4px 4px 0 0",
                    padding: "3px 4px 2px",
                    textAlign:"center",
                    overflow:"hidden",whiteSpace:"nowrap",
                    transition:"background 0.2s",
                    boxShadow: isHighlight ? `0 2px 8px ${pm.color}30` : "none",
                    display:"flex",flexDirection:"column",justifyContent:"center",alignItems:"center",
                  }}>
                    <div style={{fontSize:8,fontWeight: isHighlight ? 800 : 700,color:pm.color,fontFamily:"'JetBrains Mono',monospace",letterSpacing:0.3,lineHeight:1.2}}>
                      {w > 120 ? pm.short : w > 60 ? pm.short.slice(0,8) : pm.short.slice(0,3)}
                    </div>
                    {w > 80 && pr.agents.length > 0 && (
                      <div style={{fontSize:7,color:pm.color+"99",fontFamily:"monospace",lineHeight:1.2,marginTop:1}}>
                        {pr.agents.map(a=>sn(a)).join("↔")}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Turn numbers */}
          <div style={{display:"flex",height:14,marginBottom:2}}>
            {Array.from({length:totalTurns},(_, i)=>(
              <div key={i} style={{
                width:COL,flexShrink:0,textAlign:"center",fontSize:7.5,
                fontFamily:"monospace",
                color: i <= playhead ? (divTurns.has(i)?"#dc2626":"#94a3b8") : "#e2e8f0",
              }}>{i+1}</div>
            ))}
          </div>

          {/* Belief Grid — cells only (no labels) */}
          {D.agents.map((agent, ai) => (
            <div key={agent} style={{display:"flex",alignItems:"center",height:CELL_H+4,marginBottom:1}}>
              {D.states.map((turnStates, ti) => {
                const state = turnStates[ai] || "idle";
                const st = ST[state] || ST.idle;
                const visible = ti <= playhead;
                const isSpeaker = D.speakers[ti] === agent;
                const hasDivHere = visible && D.divergences.some(d => d.t === ti && d.agents.includes(agent));
                const isSelected = selected?.type==="cell" && selected.turn===ti && selected.agentIdx===ai;

                const activeAgents = getActiveAgentsForTurn(D, ti);
                const isActiveInPhase = activeAgents.has(agent);
                const isPassive = !isActiveInPhase;

                const colPhase = D.phases[ti];
                const isInHighlightedPhase = highlightedPhase && colPhase === highlightedPhase;
                const highlightPm = isInHighlightedPhase ? (PHASE_META[highlightedPhase] || {color:"#94a3b8"}) : null;

                return (
                  <div key={ti}
                    onClick={()=>visible && !isPassive && setSelected({type:"cell",turn:ti,agentIdx:ai})}
                    style={{
                      width: CELL_W,
                      height: CELL_H,
                      flexShrink: 0,
                      marginRight: CELL_GAP,
                      borderRadius: 4,
                      background: !visible ? "#fafafa"
                        : isPassive ? (isInHighlightedPhase ? highlightPm.color+"10" : "transparent")
                        : st.color,
                      border: isSelected ? "2px solid #1e293b"
                        : isInHighlightedPhase && isPassive ? `1px solid ${highlightPm.color}40`
                        : isPassive && visible ? "1px solid #f0f0f0"
                        : hasDivHere ? "2px solid #dc2626"
                        : isSpeaker && visible ? `2px solid ${st.fg}55`
                        : "1px solid transparent",
                      cursor: visible && !isPassive ? "pointer" : "default",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      opacity: !visible ? 0.15 : isPassive ? (isInHighlightedPhase ? 0.4 : 0.0) : 1,
                      transition: "opacity 0.2s, background 0.2s",
                      position: "relative",
                      boxShadow: isInHighlightedPhase && !isPassive && visible ? `inset 0 0 0 2px ${highlightPm.color}60` : "none",
                    }}
                  >
                    {visible && !isPassive && (
                      <span style={{
                        fontSize: state === "req_change" ? 8 : 9,
                        fontWeight: 800,
                        color: st.fg,
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        maxWidth: CELL_W - 6,
                        fontFamily: "inherit",
                        textAlign: "center",
                        display: "block",
                        lineHeight: 1,
                        letterSpacing: -0.2,
                      }}>
                        {st.label}
                      </span>
                    )}
                    {hasDivHere && !isPassive && (
                      <div style={{
                        position:"absolute",top:-3,right:-3,
                        width:8,height:8,borderRadius:"50%",
                        background:"#dc2626",border:"1.5px solid #fff",
                      }}/>
                    )}
                  </div>
                );
              })}
            </div>
          ))}

          {/* Divergence track */}
          <div style={{display:"flex",height:28,alignItems:"flex-start",marginTop:4}}>
            {Array.from({length:totalTurns},(_,ti)=>{
              const divsHere = visibleDivs.filter(d=>d.t===ti);
              if(divsHere.length===0) return <div key={ti} style={{width:COL,flexShrink:0,height:28}}/>;
              const sev = divsHere.some(d=>d.sev==="high") ? "high" : "medium";
              const idx = visibleDivs.indexOf(divsHere[0]);
              return (
                <div key={ti} onClick={()=>setSelected({type:"div",idx})}
                  style={{
                    width:COL,flexShrink:0,height:28,display:"flex",flexDirection:"column",alignItems:"center",
                    cursor:"pointer",
                  }}>
                  <div style={{width:1,height:6,background:DIV_COLORS[sev]}}/>
                  <div style={{fontSize:10,color:DIV_COLORS[sev],fontWeight:700,lineHeight:1}}>⚡</div>
                  {divsHere.length>1 && <div style={{fontSize:7,color:"#999",fontFamily:"monospace"}}>×{divsHere.length}</div>}
                </div>
              );
            })}
          </div>

          </div>{/* end scrollable cells */}
        </div>{/* end grid wrapper */}

        {/* ─── LEGEND ─── */}
        <div style={css.legend}>
          <div style={css.legendTitle}>REASONING STATES</div>
          {Object.entries(ST).filter(([k])=> k === "idle" || usedStates.has(k)).map(([k,v])=>(
            <div key={k} style={{...css.legendItem, opacity: usedStates.has(k) ? 1 : 0.4}}>
              <div style={{width:16,height:16,borderRadius:3,background:v.color,border: k==="idle"?"1px solid #d1d5db":"none",flexShrink:0}}/>
              <span style={{fontSize:10,color:"#1e293b",fontWeight:600}}>{v.label}</span>
            </div>
          ))}
          {/* Visual key for passive vs active */}
          <div style={{...css.legendTitle,marginTop:12}}>GRID VISUAL KEY</div>
          <div style={css.legendItem}>
            <div style={{width:14,height:14,borderRadius:3,background:"transparent",border:"1px dashed #e5e7eb"}}/>
            <span style={{fontSize:9,color:"#94a3b8"}}>Not in this phase</span>
          </div>
          <div style={css.legendItem}>
            <div style={{width:14,height:14,borderRadius:3,border:"2px solid #666",background:"#86efac",display:"flex",alignItems:"center",justifyContent:"center"}}>
              <span style={{fontSize:7,color:"#166534",fontWeight:700}}>→</span>
            </div>
            <span style={{fontSize:9,color:"#94a3b8"}}>Active speaker</span>
          </div>
          <div style={css.legendItem}>
            <div style={{width:14,height:2,background:"#cbd5e1",borderRadius:1}}/>
            <span style={{fontSize:9,color:"#94a3b8"}}>Phase boundary</span>
          </div>

          <div style={{...css.legendTitle,marginTop:12}}>DIVERGENCES</div>
          <div style={css.legendItem}>
            <div style={{width:14,height:14,borderRadius:7,background:"#dc2626",display:"flex",alignItems:"center",justifyContent:"center"}}>
              <span style={{fontSize:7,color:"#fff",fontWeight:700}}>⚡</span>
            </div>
            <span style={{fontSize:10,color:"#64748b"}}>Belief conflict detected</span>
          </div>

          {/* Phase list */}
          {phaseRanges.length > 0 && <>
            <div style={{...css.legendTitle,marginTop:12}}>PHASES ({phaseRanges.length})</div>
            {phaseRanges.map((pr,i)=>{
              const pm = PHASE_META[pr.name] || {short:pr.name,color:"#94a3b8"};
              const isActive = currentPhase && currentPhase.start === pr.start;
              return (
                <div key={i} style={{...css.legendItem,marginBottom:3,padding:"2px 0",
                  background: isActive ? pm.color+"10" : "transparent",
                  borderRadius:3, transition:"background 0.2s",
                }}>
                  <div style={{width:8,height:8,borderRadius:2,background:pm.color,flexShrink:0}}/>
                  <div style={{display:"flex",flexDirection:"column",minWidth:0}}>
                    <span style={{fontSize:9,fontWeight:600,color:isActive?pm.color:"#475569"}}>{pm.short}</span>
                    {pr.agents.length>0 && <span style={{fontSize:7.5,color:"#94a3b8",fontFamily:"monospace",whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{pr.agents.map(a=>sn(a)).join("↔")}</span>}
                  </div>
                  <span style={{fontSize:7,color:"#94a3b8",fontFamily:"monospace",marginLeft:"auto",flexShrink:0}}>t{pr.start+1}–{pr.end+1}</span>
                </div>
              );
            })}
          </>}

          {Object.keys(D.failures).length > 0 && <>
            <div style={{...css.legendTitle,marginTop:12}}>FAILURES IN TRACE</div>
            {Object.entries(D.failures).map(([code,label])=>(
              <div key={code} style={{...css.legendItem,marginBottom:2}}>
                <span style={{fontFamily:"monospace",fontSize:9,color:"#dc2626",background:"#fef2f2",padding:"1px 4px",borderRadius:3,border:"1px solid #fecaca"}}>
                  {code}
                </span>
                <span style={{fontSize:9.5,color:"#64748b"}}>{typeof label === "string" ? label : label?.label || code}</span>
              </div>
            ))}
          </>}
        </div>
      </div>

      {/* ─── DETAIL PANEL ─── */}
      {detail && (
        <div style={css.detailPanel}>
          <button onClick={()=>setSelected(null)} style={css.detailClose}>✕</button>

          {detail.kind === "cell" && <>
            <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:10}}>
              <div style={{
                width:24,height:24,borderRadius:5,
                background:ST[detail.state]?.color||"#eee",
                display:"flex",alignItems:"center",justifyContent:"center",
              }}>
                <span style={{fontSize:13,color:ST[detail.state]?.fg||"#666",fontWeight:700}}>{ST[detail.state]?.icon}</span>
              </div>
              <div>
                <div style={{fontFamily:"monospace",fontSize:12,fontWeight:600,color:"#1e293b"}}>{detail.agent}</div>
                <div style={{fontSize:10,color:"#64748b"}}>Turn {detail.turn+1} · Reasoning state: {ST[detail.state]?.label || detail.state}</div>
              </div>
              {detail.isSpeaker && <span style={{fontSize:9,background:"#dbeafe",color:"#1e40af",padding:"2px 6px",borderRadius:4,fontFamily:"monospace"}}>SPEAKER</span>}
              {!detail.isActiveInPhase && <span style={{fontSize:9,background:"#f1f5f9",color:"#94a3b8",padding:"2px 6px",borderRadius:4,fontFamily:"monospace"}}>NOT IN PHASE</span>}
            </div>
            {/* Phase context bar */}
            {detail.phaseRange && (() => {
              const pm = PHASE_META[detail.phaseRange.name] || {short:detail.phaseRange.name,color:"#94a3b8"};
              return <div style={{
                display:"flex",alignItems:"center",gap:8,marginBottom:10,
                padding:"6px 10px",borderRadius:6,
                background:pm.color+"10",border:`1px solid ${pm.color}25`,
              }}>
                <div style={{width:8,height:8,borderRadius:2,background:pm.color,flexShrink:0}}/>
                <span style={{fontSize:10,fontWeight:600,color:pm.color,fontFamily:"monospace"}}>{detail.phaseRange.name}</span>
                {detail.phaseRange.agents.length > 0 && <span style={{fontSize:9,color:"#64748b",fontFamily:"monospace"}}>
                  {detail.phaseRange.agents.map(a=>sn(a)).join(" ↔ ")}
                </span>}
                <span style={{fontSize:8,color:"#94a3b8",fontFamily:"monospace",marginLeft:"auto"}}>turns {detail.phaseRange.start+1}–{detail.phaseRange.end+1}</span>
              </div>;
            })()}
            {detail.short && (() => {
              // Build a rich, context-aware belief description
              const agentShort = sn(detail.agent);
              const stLabel = ST[detail.state]?.label || detail.state;
              const phaseName = detail.phaseRange?.name || detail.phase || "";
              const pmShort = PHASE_META[phaseName]?.short || phaseName;

              // Contextual interpretations per state + context
              const beliefMap = {
                proposing: `${agentShort} is putting forward a plan or decision to the team. They believe their suggestion is the right path forward and are seeking alignment.`,
                approving: `${agentShort} has reviewed the previous output and considers it satisfactory. Their belief is that the work meets the requirement and can proceed.`,
                building: `${agentShort} is actively constructing the deliverable — writing code, drafting content, or producing artifacts. They believe they have a clear enough specification to act.`,
                reviewing: `${agentShort} is inspecting the work against requirements. They are forming a judgment about whether the current state is acceptable.`,
                req_change: `${agentShort} has identified a gap or issue. They believe the current output does not yet meet expectations and is requesting specific modifications.`,
                asking: `${agentShort} is seeking information or clarification before committing to an action. They believe they lack sufficient context to proceed independently.`,
                completing: `${agentShort} believes the task is done and is producing final deliverables — documentation, summaries, or closure artifacts.`,
                blocked: `${agentShort} believes the task cannot proceed in its current form. They have identified an unresolvable constraint or missing input.`,
                pushing: `${agentShort} believes the task should continue despite another agent's objection. They are insisting forward progress is possible or required.`,
                idle: `${agentShort} is not actively participating in this turn. They are waiting for their role to become relevant in the current phase.`,
              };

              const contextLine = detail.short
                ? `In this turn: "${detail.short}"`
                : "";

              const primaryDesc = beliefMap[detail.state] || `${agentShort} is in the ${stLabel} state.`;

              // Add phase context
              const phaseContext = phaseName && detail.isActiveInPhase
                ? ` This is occurring during the ${pmShort} phase.`
                : "";

              return (
                <div style={{
                  marginBottom:10, padding:"12px 14px", borderRadius:6,
                  background: ST[detail.state]?.color+"10" || "#f8fafc",
                  border: `1px solid ${ST[detail.state]?.color+"30" || "#e2e8f0"}`,
                  borderLeft: `3px solid ${ST[detail.state]?.color || "#94a3b8"}`,
                }}>
                  <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:6}}>
                    <div style={{
                      width:18,height:18,borderRadius:4,
                      background:ST[detail.state]?.color||"#eee",
                      display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0,
                    }}>
                      <span style={{fontSize:10,color:ST[detail.state]?.fg||"#666",fontWeight:700}}>{ST[detail.state]?.icon}</span>
                    </div>
                    <div style={{fontSize:11,fontWeight:700,color:ST[detail.state]?.color||"#334155"}}>
                      {stLabel}
                      {detail.isSpeaker && <span style={{fontSize:9,background:"#dbeafe",color:"#1e40af",padding:"1px 5px",borderRadius:4,fontFamily:"monospace",marginLeft:6,fontWeight:600}}>SPEAKER</span>}
                    </div>
                  </div>
                  <div style={{fontSize:12,color:"#1e293b",lineHeight:1.6,marginBottom:contextLine?6:0}}>
                    {primaryDesc}{phaseContext}
                  </div>
                  {contextLine && (
                    <div style={{fontSize:10.5,color:"#475569",lineHeight:1.5,fontStyle:"italic",borderTop:`1px solid ${ST[detail.state]?.color+"20"||"#e2e8f0"}`,paddingTop:6,marginTop:2}}>
                      {contextLine}
                    </div>
                  )}
                </div>
              );
            })()}
            {detail.divsHere.length > 0 && <div style={{marginTop:8}}>
              {detail.divsHere.map((d,i)=>(
                <div key={i} style={{padding:"8px 10px",background:"#fef2f2",borderRadius:6,border:"1px solid #fecaca",marginBottom:6}}>
                  <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:4}}>
                    <span style={{fontSize:10,fontWeight:700,color:"#dc2626"}}>
                      ⚡ DIVERGENCE
                    </span>
                    <span style={{fontSize:9,color:"#94a3b8",fontFamily:"monospace"}}>{d.type}</span>
                  </div>
                  <div style={{fontSize:11,color:"#334155",lineHeight:1.5}}>{d.desc}</div>
                  {d.fm.length>0 && <div style={{marginTop:4}}>
                    {d.fm.map(f=><span key={f} style={{fontFamily:"monospace",fontSize:9,color:"#dc2626",background:"#fef2f2",padding:"1px 5px",borderRadius:3,border:"1px solid #fecaca",marginRight:4}}>FM-{f}</span>)}
                  </div>}
                </div>
              ))}
            </div>}
          </>}

          {detail.kind === "div" && <>
            <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:10}}>
              <span style={{fontSize:16}}>⚡</span>
              <div>
                <div style={{fontFamily:"monospace",fontSize:12,fontWeight:600,color:"#dc2626"}}>
                  DIVERGENCE
                </div>
                <div style={{fontSize:10,color:"#64748b"}}>Turn {detail.t+1} · {detail.type.replace(/_/g," ")}</div>
              </div>
            </div>
            {/* Phase context bar */}
            {detail.phaseRange && (() => {
              const pm = PHASE_META[detail.phaseRange.name] || {short:detail.phaseRange.name,color:"#94a3b8"};
              return <div style={{
                display:"flex",alignItems:"center",gap:8,marginBottom:10,
                padding:"6px 10px",borderRadius:6,
                background:pm.color+"10",border:`1px solid ${pm.color}25`,
              }}>
                <div style={{width:8,height:8,borderRadius:2,background:pm.color,flexShrink:0}}/>
                <span style={{fontSize:10,fontWeight:600,color:pm.color,fontFamily:"monospace"}}>{detail.phaseRange.name}</span>
                {detail.phaseRange.agents.length > 0 && <span style={{fontSize:9,color:"#64748b",fontFamily:"monospace"}}>
                  {detail.phaseRange.agents.map(a=>sn(a)).join(" ↔ ")}
                </span>}
                <span style={{fontSize:8,color:"#94a3b8",fontFamily:"monospace",marginLeft:"auto"}}>turns {detail.phaseRange.start+1}–{detail.phaseRange.end+1}</span>
              </div>;
            })()}
            <div style={{fontSize:12,color:"#334155",lineHeight:1.6,marginBottom:10}}>{detail.desc}</div>
            <div style={{display:"flex",gap:8,flexWrap:"wrap",marginBottom:8}}>
              <span style={{fontSize:10,color:"#64748b"}}>Agents involved:</span>
              {detail.agents.map(a=><span key={a} style={{fontFamily:"monospace",fontSize:10,fontWeight:600,color:"#1e293b"}}>{sn(a)}</span>)}
            </div>
            {detail.fm?.length>0 && <div>
              <span style={{fontSize:10,color:"#64748b"}}>Related MAST failures: </span>
              {detail.fm.map(f=><span key={f} style={{fontFamily:"monospace",fontSize:10,color:"#dc2626",background:"#fef2f2",padding:"2px 6px",borderRadius:3,border:"1px solid #fecaca",marginRight:4}}>FM-{f} {D.failures[f] || ""}</span>)}
            </div>}
            <div style={{marginTop:10,padding:"8px 10px",background:"#f8fafc",borderRadius:6,border:"1px solid #e2e8f0"}}>
              <div style={{fontSize:9,color:"#94a3b8",fontFamily:"monospace",marginBottom:4}}>AGENT STATES AT THIS MOMENT</div>
              <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
                {D.agents.map((a,ai)=>{
                  const state = D.states[detail.t]?.[ai] || "idle";
                  const st = ST[state] || ST.idle;
                  const involved = detail.agents.includes(a);
                  return <div key={a} style={{
                    display:"flex",alignItems:"center",gap:4,padding:"3px 6px",borderRadius:4,
                    background: involved ? st.color+"30" : "transparent",
                    border: involved ? `1px solid ${st.color}` : "1px solid transparent",
                  }}>
                    <div style={{width:10,height:10,borderRadius:2,background:st.color}}/>
                    <span style={{fontSize:9.5,fontFamily:"monospace",fontWeight:involved?700:400,color:"#334155"}}>{sn(a)}: {st.label}</span>
                  </div>;
                })}
              </div>
            </div>
          </>}
        </div>
      )}

      {/* ─── EMPTY STATE HINT ─── */}
      {!selected && visibleDivs.length > 0 && (
        <div style={{padding:"16px 20px",background:"#fffbeb",borderRadius:8,border:"1px solid #fef3c7",marginTop:8,fontSize:11,color:"#92400e",lineHeight:1.5}}>
          <b>{visibleDivs.length} divergence event{visibleDivs.length>1?"s":""}</b> detected up to turn {playhead+1}. Click any ⚡ marker or highlighted cell to inspect the belief conflict.
        </div>
      )}
      {playhead === 0 && !selected && (
        <div style={{padding:"20px",textAlign:"center",color:"#94a3b8",fontSize:12,lineHeight:1.6}}>
          Drag the playhead slider to step through the conversation.<br/>
          Watch how each agent's reasoning state evolves and where they diverge.
        </div>
      )}
      {/* Scientific disclaimer */}
      <div style={{padding:"12px 16px",marginTop:12,background:"#f8fafc",borderRadius:6,border:"1px solid #e2e8f0"}}>
        <div style={{fontSize:9,color:"#94a3b8",lineHeight:1.6,fontStyle:"italic"}}>
          Reasoning states are inferred from observable conversational behavior using rule-based extraction and do not necessarily reflect latent internal states.
          This visualization represents an interpretable baseline for agent cognitive-state approximation, not formal belief inference.
          States shown (e.g., Building, Reviewing, Approving) combine task-activity and epistemic dimensions into a single categorical representation.
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════
   STYLES
   ═══════════════════════════════════════════════ */
const css = {
  root: {
    fontFamily: "'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif",
    maxWidth: 1100,
    margin: "0 auto",
    padding: "0 16px 40px",
    color: "#1e293b",
    background: "#fff",
    minHeight: "100vh",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "18px 0 12px",
    borderBottom: "1px solid #e2e8f0",
    flexWrap: "wrap",
    gap: 12,
  },
  titleBlock: { display: "flex", alignItems: "baseline", gap: 8 },
  title: { fontSize: 20, fontWeight: 700, color: "#0f172a", letterSpacing: -0.5 },
  subtitle: { fontSize: 13, color: "#64748b", fontWeight: 400 },
  controls: { display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" },
  srcBtn: {
    fontSize: 11, padding: "5px 12px", border: "1px solid #e2e8f0",
    borderRadius: 5, background: "#fff", color: "#64748b",
    cursor: "pointer", fontFamily: "inherit", fontWeight: 500,
  },
  srcActive: { background: "#3b82f6", color: "#fff", borderColor: "#3b82f6" },
  uploadBtn: {
    fontSize: 11, padding: "5px 12px", border: "1px solid #86efac",
    borderRadius: 5, background: "#f0fdf4", color: "#16a34a",
    cursor: "pointer", fontFamily: "monospace", fontWeight: 600,
  },
  problem: {
    fontSize: 11.5, color: "#64748b", lineHeight: 1.5,
    padding: "8px 0", margin: 0, fontStyle: "italic",
  },
  playbar: {
    display: "flex", alignItems: "center", gap: 8,
    padding: "10px 0", borderBottom: "1px solid #e2e8f0",
  },
  playBtn: {
    width: 32, height: 28, border: "1px solid #e2e8f0", borderRadius: 5,
    background: "#f8fafc", cursor: "pointer", fontSize: 13,
    display: "flex", alignItems: "center", justifyContent: "center",
    color: "#3b82f6", fontFamily: "inherit",
  },
  turnLabel: { fontFamily: "monospace", fontSize: 11, color: "#475569", whiteSpace: "nowrap" },
  speakerLabel: { fontSize: 10, color: "#94a3b8", fontFamily: "monospace" },
  mainArea: {
    display: "flex", gap: 16, marginTop: 12,
    position: "relative",
  },
  legend: {
    width: 210, flexShrink: 0,
    paddingLeft: 16, borderLeft: "1px solid #e2e8f0",
    maxHeight: 600, overflowY: "auto",
  },
  legendTitle: {
    fontSize: 9, fontWeight: 600, color: "#94a3b8",
    textTransform: "uppercase", letterSpacing: 0.8,
    fontFamily: "monospace", marginBottom: 8,
  },
  legendItem: {
    display: "flex", alignItems: "center", gap: 6,
    marginBottom: 5,
  },
  detailPanel: {
    marginTop: 12, padding: "16px 20px",
    background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 8,
    position: "relative",
  },
  detailClose: {
    position: "absolute", top: 10, right: 10,
    width: 24, height: 24, border: "1px solid #e2e8f0", borderRadius: 4,
    background: "#fff", cursor: "pointer", fontSize: 11,
    display: "flex", alignItems: "center", justifyContent: "center",
    color: "#94a3b8", fontFamily: "inherit",
  },
};
