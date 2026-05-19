const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.author  = "TTK Agent";
pres.title   = "TTK Companion Agent Pipeline — Executive Briefing";

// ── Palette ────────────────────────────────────────────────────────────────────
const NAVY    = "0D1B4B";
const BLUE    = "3949AB";
const MID     = "5C6BC0";
const LIGHT   = "E8EAF6";
const WHITE   = "FFFFFF";
const MUTED   = "6B7280";
const TEXT    = "1C1E2E";
const GREEN   = "2E7D32";
const AMBER   = "F57F17";
const TEAL    = "00695C";
const BG      = "F4F5FB";

const makeShadow = () => ({ type:"outer", color:"000000", blur:8, offset:3, angle:135, opacity:0.12 });

// ── Helper: navy header bar ────────────────────────────────────────────────────
function addHeader(slide, title) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x:0, y:0, w:10, h:0.85, fill:{color:NAVY}, line:{color:NAVY}
  });
  slide.addText(title, {
    x:0.4, y:0, w:9.2, h:0.85,
    fontSize:22, fontFace:"Georgia", bold:true,
    color:WHITE, valign:"middle", margin:0
  });
}

// ── Helper: footer ─────────────────────────────────────────────────────────────
function addFooter(slide, note) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x:0, y:5.35, w:10, h:0.275, fill:{color:LIGHT}, line:{color:LIGHT}
  });
  slide.addText("TTK Companion Agent Pipeline  |  Executive Briefing  |  2026" + (note ? "   |   " + note : ""), {
    x:0.3, y:5.35, w:9.4, h:0.275,
    fontSize:9, fontFace:"Calibri", color:MUTED, valign:"middle", margin:0
  });
}

// ──────────────────────────────────────────────────────────────────────────────
//  SLIDE 1 — TITLE
// ──────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: NAVY };

  // Left accent stripe
  s.addShape(pres.shapes.RECTANGLE, {
    x:0, y:0, w:0.18, h:5.625, fill:{color:BLUE}, line:{color:BLUE}
  });

  // Decorative rectangle top-right
  s.addShape(pres.shapes.RECTANGLE, {
    x:7.5, y:0, w:2.5, h:2.2, fill:{color:"1A2880"}, line:{color:"1A2880"}
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x:8.2, y:0.3, w:1.5, h:1.5, fill:{color:BLUE}, line:{color:BLUE}
  });

  // Tag chip
  s.addShape(pres.shapes.RECTANGLE, {
    x:0.45, y:1.1, w:2.4, h:0.38, fill:{color:BLUE}, line:{color:BLUE}
  });
  s.addText("EXECUTIVE BRIEFING  |  2026", {
    x:0.45, y:1.1, w:2.4, h:0.38,
    fontSize:9, fontFace:"Calibri", bold:true, color:WHITE,
    align:"center", valign:"middle", charSpacing:1, margin:0
  });

  // Main title
  s.addText("TTK Companion\nAgent Pipeline", {
    x:0.45, y:1.65, w:7.8, h:1.9,
    fontSize:46, fontFace:"Georgia", bold:true, color:WHITE,
    valign:"middle", lineSpacingMultiple:1.1
  });

  // Subtitle
  s.addText("AI-Powered Pharmaceutical Knowledge Capture for Tech Transfers", {
    x:0.45, y:3.6, w:7.5, h:0.55,
    fontSize:17, fontFace:"Calibri", color:"CADCFC", valign:"middle"
  });

  // Bottom bar
  s.addShape(pres.shapes.RECTANGLE, {
    x:0, y:5.1, w:10, h:0.525, fill:{color:"060E2E"}, line:{color:"060E2E"}
  });
  s.addText("knowledge.ngrok-free.app    |    github.com/girishkurup/ttk-knowledge-agent    |    Powered by Claude (Anthropic)", {
    x:0.3, y:5.1, w:9.4, h:0.525,
    fontSize:10, fontFace:"Calibri", color:"8899CC",
    valign:"middle", margin:0
  });
}

// ──────────────────────────────────────────────────────────────────────────────
//  SLIDE 2 — EXECUTIVE SUMMARY
// ──────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addHeader(s, "Executive Summary");

  const cards = [
    { x:0.3,  label:"PROBLEM",    color:NAVY,  icon:"⚠", text:"Critical tacit knowledge lost during pilot-to-commercial scale-up transitions in pharmaceutical manufacturing. Repeated batch failures. No cross-batch pattern detection." },
    { x:3.55, label:"SOLUTION",   color:BLUE,  icon:"⚙", text:"6-agent AI pipeline that automatically captures, structures and preserves process engineer knowledge during batch deviation events via a structured interview." },
    { x:6.8,  label:"IMPACT",     color:TEAL,  icon:"✓", text:"Every session produces a Knowledge Article, Best Practices Checklist and an interactive Knowledge Graph — all stored in a queryable SQLite database." },
  ];

  cards.forEach(c => {
    s.addShape(pres.shapes.RECTANGLE, {
      x:c.x, y:1.05, w:3.1, h:3.8,
      fill:{color:WHITE}, line:{color:"E0E3F0"}, shadow:makeShadow()
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x:c.x, y:1.05, w:3.1, h:0.5, fill:{color:c.color}, line:{color:c.color}
    });
    s.addText(c.label, {
      x:c.x, y:1.05, w:3.1, h:0.5,
      fontSize:11, fontFace:"Calibri", bold:true, color:WHITE,
      align:"center", valign:"middle", charSpacing:2, margin:0
    });
    s.addText(c.icon, {
      x:c.x+1.1, y:1.65, w:0.9, h:0.9,
      fontSize:32, align:"center", valign:"middle", color:c.color
    });
    s.addText(c.text, {
      x:c.x+0.18, y:2.55, w:2.74, h:2.1,
      fontSize:12, fontFace:"Calibri", color:TEXT,
      valign:"top", lineSpacingMultiple:1.3
    });
  });

  // Deployment line
  s.addShape(pres.shapes.RECTANGLE, {
    x:0.3, y:5.05, w:9.4, h:0.35, fill:{color:LIGHT}, line:{color:LIGHT}
  });
  s.addText("Live:  knowledge.ngrok-free.app   |   Source:  github.com/girishkurup/ttk-knowledge-agent", {
    x:0.3, y:5.05, w:9.4, h:0.35,
    fontSize:10, fontFace:"Calibri", color:BLUE, align:"center", valign:"middle", margin:0
  });

  addFooter(s);
}

// ──────────────────────────────────────────────────────────────────────────────
//  SLIDE 3 — THE PROBLEM
// ──────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addHeader(s, "The Problem — Knowledge Loss at Scale-Up");

  const problems = [
    "Tacit knowledge lost when experienced engineers retire or transfer between sites",
    "Scale-up failures repeat because lessons are never formally documented",
    "Batch deviations at commercial scale (capping, weight variability) cost millions in rejected batches",
    "Traditional documentation is manual, inconsistent, and rarely completed in practice",
    "No cross-batch pattern detection — each deviation event treated in isolation",
  ];

  const colors = [NAVY, BLUE, MID, AMBER, TEAL];
  problems.forEach((p, i) => {
    const y = 1.1 + i * 0.82;
    s.addShape(pres.shapes.RECTANGLE, {
      x:0.35, y:y, w:0.07, h:0.62, fill:{color:colors[i]}, line:{color:colors[i]}
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x:0.55, y:y, w:8.8, h:0.62,
      fill:{color:i%2===0 ? BG : WHITE}, line:{color:"E8EAF6"}
    });
    s.addText(p, {
      x:0.75, y:y, w:8.5, h:0.62,
      fontSize:14, fontFace:"Calibri", color:TEXT, valign:"middle"
    });
  });

  // Right stat callout
  s.addShape(pres.shapes.RECTANGLE, {
    x:8.9, y:1.1, w:0.85, h:4.1,
    fill:{color:NAVY}, line:{color:NAVY}
  });
  ["$M", "Lost", "per", "batch", "event"].forEach((t,i) => {
    s.addText(t, {
      x:8.9, y:1.1 + i*0.78, w:0.85, h:0.78,
      fontSize:t==="$M"?20:10, fontFace:"Georgia", bold:t==="$M",
      color:WHITE, align:"center", valign:"middle", margin:0
    });
  });

  addFooter(s);
}

// ──────────────────────────────────────────────────────────────────────────────
//  SLIDE 4 — WHY AGENTIC? SUITABILITY CRITERIA
// ──────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addHeader(s, "Why Agentic? — Suitability Criteria");

  const criteria = [
    {
      n:"01", color:NAVY,
      title:"Repetitive & High Volume",
      body:"Knowledge capture interviews occur after every batch deviation event across all products, sites and engineers — a continuous, recurring need.",
    },
    {
      n:"02", color:BLUE,
      title:"Measurable Outcomes",
      body:"Success is quantifiable: article completeness, graph node count, checklist coverage, sessions captured. No ambiguity in what 'done' looks like.",
    },
    {
      n:"03", color:MID,
      title:"Current System is Slow",
      body:"Manual post-event documentation takes days or weeks — if it happens at all. The agent captures the same knowledge in 5 minutes during the event.",
    },
    {
      n:"04", color:TEAL,
      title:"Current System is Expensive",
      body:"Undocumented lessons lead to repeated batch failures. Each rejected commercial batch costs millions. Agentic capture breaks the repeat-failure cycle.",
    },
    {
      n:"05", color:AMBER,
      title:"Multi-Step Logic with Clear Handoffs",
      body:"Interview → Synthesis → Graph → Admin is a defined pipeline with structured inputs/outputs at each stage — ideal for an agent chain.",
    },
    {
      n:"06", color:GREEN,
      title:"No ERP / CRM Integration Required",
      body:"Standalone SQLite + file system. No SAP, Salesforce or complex enterprise integration — simple deployment, low risk, fast time to value.",
    },
  ];

  const positions = [
    {col:0,row:0},{col:1,row:0},{col:2,row:0},
    {col:0,row:1},{col:1,row:1},{col:2,row:1},
  ];

  criteria.forEach((c, i) => {
    const x = 0.28 + positions[i].col * 3.18;
    const y = 1.0  + positions[i].row * 2.2;

    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w:3.05, h:2.05,
      fill:{color:WHITE}, line:{color:"E0E3F0"}, shadow:makeShadow()
    });
    // coloured top bar
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w:3.05, h:0.42, fill:{color:c.color}, line:{color:c.color}
    });
    // number badge
    s.addShape(pres.shapes.RECTANGLE, {
      x:x+0.1, y:y+0.5, w:0.44, h:0.44,
      fill:{color:c.color}, line:{color:c.color}
    });
    s.addText(c.n, {
      x:x+0.1, y:y+0.5, w:0.44, h:0.44,
      fontSize:13, fontFace:"Georgia", bold:true, color:WHITE,
      align:"center", valign:"middle", margin:0
    });
    // checkmark in top bar
    s.addText("✓", {
      x:x+2.6, y, w:0.38, h:0.42,
      fontSize:16, fontFace:"Calibri", bold:true, color:WHITE,
      align:"center", valign:"middle", margin:0
    });
    s.addText(c.title, {
      x, y, w:2.55, h:0.42,
      fontSize:10, fontFace:"Calibri", bold:true, color:WHITE,
      valign:"middle", margin:8
    });
    s.addText(c.body, {
      x:x+0.65, y:y+0.5, w:2.3, h:1.45,
      fontSize:10.5, fontFace:"Calibri", color:TEXT,
      valign:"top", lineSpacingMultiple:1.3
    });
  });

  addFooter(s, "All 6 criteria met — strong fit for agentic automation");
}

// ──────────────────────────────────────────────────────────────────────────────
//  SLIDE 5 (was 4) — ARCHITECTURE
// ──────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addHeader(s, "Architecture — Two Pipelines");

  // Interview pipeline box
  s.addShape(pres.shapes.RECTANGLE, {
    x:0.3, y:1.0, w:4.55, h:3.85,
    fill:{color:WHITE}, line:{color:"E0E3F0"}, shadow:makeShadow()
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x:0.3, y:1.0, w:4.55, h:0.45, fill:{color:NAVY}, line:{color:NAVY}
  });
  s.addText("INTERVIEW PIPELINE  —  Automatic", {
    x:0.3, y:1.0, w:4.55, h:0.45,
    fontSize:11, fontFace:"Calibri", bold:true, color:WHITE,
    align:"center", valign:"middle", charSpacing:1, margin:0
  });

  const interview = [
    { n:"1", name:"TTK Interview Agent",       desc:"Structured 5-turn conversation with process engineer via WebSocket streaming" },
    { n:"2", name:"Knowledge Synthesis Agent", desc:"Generates Knowledge Article + Risk Verification Checklist from interview JSON" },
    { n:"3", name:"Knowledge Graph Agent",     desc:"Extracts entities & relationships into graph nodes/edges, stored in SQLite" },
  ];
  interview.forEach((ag, i) => {
    const y = 1.6 + i * 1.05;
    s.addShape(pres.shapes.RECTANGLE, {
      x:0.5, y:y, w:0.45, h:0.45,
      fill:{color:BLUE}, line:{color:BLUE}
    });
    s.addText(ag.n, {
      x:0.5, y:y, w:0.45, h:0.45,
      fontSize:16, fontFace:"Georgia", bold:true, color:WHITE,
      align:"center", valign:"middle", margin:0
    });
    s.addText(ag.name, {
      x:1.05, y:y, w:3.6, h:0.28,
      fontSize:12, fontFace:"Calibri", bold:true, color:NAVY, margin:0
    });
    s.addText(ag.desc, {
      x:1.05, y:y+0.28, w:3.6, h:0.38,
      fontSize:10, fontFace:"Calibri", color:MUTED, margin:0
    });
    // Arrow between agents
    if(i < 2) {
      s.addShape(pres.shapes.RECTANGLE, {
        x:0.65, y:y+0.55, w:0.14, h:0.45,
        fill:{color:MID}, line:{color:MID}
      });
    }
  });

  // Admin pipeline box
  s.addShape(pres.shapes.RECTANGLE, {
    x:5.15, y:1.0, w:4.55, h:3.85,
    fill:{color:WHITE}, line:{color:"E0E3F0"}, shadow:makeShadow()
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x:5.15, y:1.0, w:4.55, h:0.45, fill:{color:TEAL}, line:{color:TEAL}
  });
  s.addText("ADMIN PIPELINE  —  On Demand", {
    x:5.15, y:1.0, w:4.55, h:0.45,
    fontSize:11, fontFace:"Calibri", bold:true, color:WHITE,
    align:"center", valign:"middle", charSpacing:1, margin:0
  });

  const admin = [
    { n:"4", name:"Admin KA Agent",        desc:"Consolidates all sessions into one authoritative Knowledge Article" },
    { n:"5", name:"Admin Checklist Agent", desc:"De-duplicated cross-session best practices checklist with [CRITICAL] tags" },
    { n:"6", name:"Admin Graph Agent",     desc:"Unified knowledge graph — SQL merge or full LLM re-extraction" },
  ];
  admin.forEach((ag, i) => {
    const y = 1.6 + i * 1.05;
    s.addShape(pres.shapes.RECTANGLE, {
      x:5.35, y:y, w:0.45, h:0.45,
      fill:{color:TEAL}, line:{color:TEAL}
    });
    s.addText(ag.n, {
      x:5.35, y:y, w:0.45, h:0.45,
      fontSize:16, fontFace:"Georgia", bold:true, color:WHITE,
      align:"center", valign:"middle", margin:0
    });
    s.addText(ag.name, {
      x:5.9, y:y, w:3.6, h:0.28,
      fontSize:12, fontFace:"Calibri", bold:true, color:NAVY, margin:0
    });
    s.addText(ag.desc, {
      x:5.9, y:y+0.28, w:3.6, h:0.38,
      fontSize:10, fontFace:"Calibri", color:MUTED, margin:0
    });
    if(i < 2) {
      s.addShape(pres.shapes.RECTANGLE, {
        x:5.5, y:y+0.55, w:0.14, h:0.45,
        fill:{color:"00897B"}, line:{color:"00897B"}
      });
    }
  });

  // Tech stack bar
  s.addShape(pres.shapes.RECTANGLE, {
    x:0.3, y:5.0, w:9.4, h:0.3, fill:{color:LIGHT}, line:{color:LIGHT}
  });
  s.addText("Tech Stack:  Claude API (Anthropic)  |  FastAPI  |  WebSocket  |  SQLite  |  vis-network  |  ngrok  |  GitHub", {
    x:0.3, y:5.0, w:9.4, h:0.3,
    fontSize:10, fontFace:"Calibri", color:NAVY, align:"center", valign:"middle", bold:true, margin:0
  });

  addFooter(s);
}

// ──────────────────────────────────────────────────────────────────────────────
//  SLIDE 5 — 6 AI AGENTS
// ──────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addHeader(s, "6 AI Agents — Roles & Responsibilities");

  const agents = [
    { n:"1", name:"TTK Interview Agent",       color:NAVY, desc:"Conversational elicitation via WebSocket streaming. ICH Q9 risk classification. EU SPOR dosage form referential. Max 7 turns." },
    { n:"2", name:"Knowledge Synthesis Agent", color:BLUE, desc:"Produces Knowledge Article + Risk Verification Checklist from interview JSON. Never infers — only confirmed engineer data." },
    { n:"3", name:"Knowledge Graph Agent",     color:MID,  desc:"Extracts entities & relationships into structured graph JSON. 14 node types. Stores nodes/edges in SQLite automatically." },
    { n:"4", name:"Admin KA Agent",            color:TEAL, desc:"Consolidates all session articles into one authoritative document. Surfaces patterns and tacit knowledge across all sessions." },
    { n:"5", name:"Admin Checklist Agent",     color:"00897B", desc:"Cross-session best practices checklist with [CRITICAL] tags. De-duplicated, phase-grouped: Pre-Scale-Up → Documentation." },
    { n:"6", name:"Admin Graph Agent",         color:AMBER, desc:"Unified graph via SQL merge (fast, no LLM) or full re-extraction. Cross-session edges: CONFIRMED_BY, ALSO_OBSERVED_IN." },
  ];

  const positions = [
    {col:0, row:0}, {col:1, row:0}, {col:2, row:0},
    {col:0, row:1}, {col:1, row:1}, {col:2, row:1},
  ];

  agents.forEach((ag, i) => {
    const col = positions[i].col;
    const row = positions[i].row;
    const x = 0.25 + col * 3.2;
    const y = 1.0  + row * 2.2;

    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w:3.05, h:2.0,
      fill:{color:WHITE}, line:{color:"E8EAF6"}, shadow:makeShadow()
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w:3.05, h:0.38, fill:{color:ag.color}, line:{color:ag.color}
    });
    // Agent number circle (via small square)
    s.addShape(pres.shapes.RECTANGLE, {
      x:x+0.1, y:y+0.44, w:0.42, h:0.42,
      fill:{color:ag.color}, line:{color:ag.color}
    });
    s.addText(ag.n, {
      x:x+0.1, y:y+0.44, w:0.42, h:0.42,
      fontSize:16, fontFace:"Georgia", bold:true, color:WHITE,
      align:"center", valign:"middle", margin:0
    });
    s.addText(ag.name, {
      x, y, w:3.05, h:0.38,
      fontSize:10, fontFace:"Calibri", bold:true, color:WHITE,
      align:"center", valign:"middle", charSpacing:0.5, margin:0
    });
    s.addText(ag.desc, {
      x:x+0.62, y:y+0.44, w:2.33, h:1.46,
      fontSize:10.5, fontFace:"Calibri", color:TEXT,
      valign:"top", lineSpacingMultiple:1.25
    });
  });

  addFooter(s, "Agents 1–3 run automatically | Agents 4–6 run on demand");
}

// ──────────────────────────────────────────────────────────────────────────────
//  SLIDE 6 — KEY FEATURES
// ──────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addHeader(s, "Key Features");

  const features = [
    { icon:"◉", title:"Real-Time Streaming Interview",    body:"WebSocket streaming — AI agent types live in browser with no page refresh. Up to 7 engineer turns." },
    { icon:"◎", title:"Knowledge Article Generation",     body:"Auto-generated Markdown article with context, root cause, mitigation and knowledge classification tags." },
    { icon:"☑", title:"Interactive Best Practices Checklist", body:"Checkbox-enabled checklist with [CRITICAL] tags. Phase-grouped: Pre-Scale-Up → Compression → Documentation." },
    { icon:"◈", title:"Interactive Knowledge Graph",      body:"52 nodes, 46 edges across 4 sessions. vis-network browser visualisation with search and node inspector." },
    { icon:"⊡", title:"SQLite Persistence",               body:"Every message, artifact, graph node/edge stored. Auto-migration of legacy JSON files on startup." },
    { icon:"⊞", title:"Admin Dashboard",                  body:"Session sidebar, transcript viewer modal, tab results, LLM streaming — all via WebSocket." },
  ];

  features.forEach((f, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 0.3  + col * 4.9;
    const y = 1.05 + row * 1.45;

    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w:4.6, h:1.28,
      fill:{color:WHITE}, line:{color:"E0E3F0"}, shadow:makeShadow()
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w:0.07, h:1.28,
      fill:{color:BLUE}, line:{color:BLUE}
    });
    s.addText(f.title, {
      x:x+0.18, y:y+0.1, w:4.3, h:0.32,
      fontSize:13, fontFace:"Calibri", bold:true, color:NAVY, margin:0
    });
    s.addText(f.body, {
      x:x+0.18, y:y+0.42, w:4.3, h:0.76,
      fontSize:11.5, fontFace:"Calibri", color:MUTED,
      valign:"top", lineSpacingMultiple:1.3
    });
  });

  addFooter(s);
}

// ──────────────────────────────────────────────────────────────────────────────
//  SLIDE 7 — KNOWLEDGE GRAPH
// ──────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addHeader(s, "Knowledge Graph — Unified Cross-Session Intelligence");

  // Stat callouts
  const stats = [
    { n:"52",  l:"Nodes",    color:NAVY },
    { n:"46",  l:"Edges",    color:BLUE },
    { n:"4",   l:"Sessions", color:TEAL },
    { n:"14",  l:"Node Types", color:AMBER },
  ];
  stats.forEach((st, i) => {
    const x = 0.35 + i * 2.35;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y:1.0, w:2.1, h:1.4,
      fill:{color:st.color}, line:{color:st.color}, shadow:makeShadow()
    });
    s.addText(st.n, {
      x, y:1.0, w:2.1, h:0.95,
      fontSize:52, fontFace:"Georgia", bold:true, color:WHITE,
      align:"center", valign:"middle", margin:0
    });
    s.addText(st.l, {
      x, y:1.95, w:2.1, h:0.45,
      fontSize:13, fontFace:"Calibri", color:"CADCFC",
      align:"center", valign:"middle", margin:0
    });
  });

  // Details two columns
  const leftBullets = [
    "Node types: Batch, Product, Engineer, Operator, Equipment, Site, Issue, Parameter, RootCause, Material, Action, Resolution, Lesson, Observation, Session",
    "Built by Claude LLM from interview transcripts automatically",
    "Stored in SQLite — graph_nodes + graph_edges tables",
  ];
  const rightBullets = [
    "Cross-session edges: CONFIRMED_BY, ALSO_OBSERVED_IN, GENERALISES_TO",
    "Visualised interactively via vis-network in browser — search, filter, inspect any node",
    "Admin: merge all sessions (SQL, instant) or re-extract via LLM",
  ];

  [leftBullets, rightBullets].forEach((bullets, col) => {
    bullets.forEach((b, i) => {
      const x = 0.35 + col * 4.95;
      const y = 2.65 + i * 0.88;
      s.addShape(pres.shapes.RECTANGLE, {
        x, y:y+0.12, w:0.07, h:0.55,
        fill:{color: col===0 ? BLUE : TEAL}, line:{color: col===0 ? BLUE : TEAL}
      });
      s.addText(b, {
        x:x+0.2, y, w:4.55, h:0.82,
        fontSize:11.5, fontFace:"Calibri", color:TEXT,
        valign:"middle", lineSpacingMultiple:1.25
      });
    });
  });

  // Vertical divider
  s.addShape(pres.shapes.RECTANGLE, {
    x:4.95, y:2.6, w:0.05, h:2.6, fill:{color:LIGHT}, line:{color:LIGHT}
  });

  addFooter(s);
}

// ──────────────────────────────────────────────────────────────────────────────
//  SLIDE 8 — COMPLIANCE & GUARDRAILS
// ──────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: NAVY };

  // Accent stripe
  s.addShape(pres.shapes.RECTANGLE, {
    x:0, y:0, w:10, h:0.85, fill:{color:"060E2E"}, line:{color:"060E2E"}
  });
  s.addText("Compliance & Guardrails", {
    x:0.4, y:0, w:9.2, h:0.85,
    fontSize:22, fontFace:"Georgia", bold:true,
    color:WHITE, valign:"middle", margin:0
  });

  const guards = [
    { icon:"⚖", text:"EU SPOR referential for dosage form classification — controlled vocabulary only" },
    { icon:"⚖", text:"ICH Q9 risk classification — High / Medium / Low — confirmed by engineer before proceeding" },
    { icon:"✓", text:"No article or checklist published without explicit engineer confirmation — GxP compliant" },
    { icon:"▤", text:"Full GxP audit trail — all agent actions logged with timestamp, session ID and engineer identity" },
    { icon:"◉", text:"PII handling per data privacy policy — engineer names stored only in session context" },
    { icon:"↺", text:"Graph agent versions all node and edge mutations — no silent overwrites of confirmed data" },
    { icon:"✗", text:"No fabricated classifications — agent always confirms with engineer before registering any tag" },
  ];

  guards.forEach((g, i) => {
    const x  = i < 4 ? 0.5 : 5.3;
    const y  = i < 4 ? 1.05 + i * 1.0 : 1.05 + (i-4) * 1.0;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y:y+0.1, w:0.5, h:0.6,
      fill:{color:BLUE}, line:{color:BLUE}
    });
    s.addText(g.icon, {
      x, y:y+0.1, w:0.5, h:0.6,
      fontSize:16, color:WHITE, align:"center", valign:"middle", margin:0
    });
    s.addText(g.text, {
      x:x+0.62, y, w:4.3, h:0.82,
      fontSize:12, fontFace:"Calibri", color:"CADCFC",
      valign:"middle", lineSpacingMultiple:1.2
    });
  });

  // Footer
  s.addShape(pres.shapes.RECTANGLE, {
    x:0, y:5.35, w:10, h:0.275, fill:{color:"060E2E"}, line:{color:"060E2E"}
  });
  s.addText("TTK Companion Agent Pipeline  |  Executive Briefing  |  2026", {
    x:0.3, y:5.35, w:9.4, h:0.275,
    fontSize:9, fontFace:"Calibri", color:"4455AA", valign:"middle", margin:0
  });
}

// ──────────────────────────────────────────────────────────────────────────────
//  SLIDE 9 — DEPLOYMENT
// ──────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: BG };
  addHeader(s, "Deployment & Access");

  const envs = [
    {
      label:"LOCAL",      color:NAVY,
      url:"localhost:8000",
      lines:[
        "uvicorn app:app --reload --port 8000",
        "Engineer view: /",
        "Admin dashboard: /admin",
        "SQLite DB: ttk_output/ttk_knowledge.db",
      ]
    },
    {
      label:"PUBLIC",     color:BLUE,
      url:"knowledge.ngrok-free.app",
      lines:[
        "ngrok static domain (free tier)",
        "Permanent URL — no change on restart",
        "Engineer: knowledge.ngrok-free.app",
        "Admin: knowledge.ngrok-free.app/admin",
      ]
    },
    {
      label:"CLOUD (RECOMMENDED)", color:TEAL,
      url:"Railway.app",
      lines:[
        "railway.toml included in repo",
        "Connect github.com/girishkurup/ttk-knowledge-agent",
        "Set ANTHROPIC_API_KEY in Railway dashboard",
        "Permanent URL — no laptop required",
      ]
    },
  ];

  envs.forEach((env, i) => {
    const x = 0.3 + i * 3.2;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y:1.0, w:3.05, h:3.95,
      fill:{color:WHITE}, line:{color:"E0E3F0"}, shadow:makeShadow()
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y:1.0, w:3.05, h:0.48, fill:{color:env.color}, line:{color:env.color}
    });
    s.addText(env.label, {
      x, y:1.0, w:3.05, h:0.48,
      fontSize:11, fontFace:"Calibri", bold:true, color:WHITE,
      align:"center", valign:"middle", charSpacing:1.5, margin:0
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x:x+0.15, y:1.62, w:2.75, h:0.44,
      fill:{color:LIGHT}, line:{color:LIGHT}
    });
    s.addText(env.url, {
      x:x+0.15, y:1.62, w:2.75, h:0.44,
      fontSize:12, fontFace:"Consolas", bold:true, color:env.color,
      align:"center", valign:"middle", margin:0
    });
    s.addText(env.lines.map(l => ({ text:l, options:{bullet:true, breakLine:true} })).concat([{text:""}]), {
      x:x+0.2, y:2.2, w:2.65, h:2.55,
      fontSize:11, fontFace:"Calibri", color:TEXT,
      valign:"top", lineSpacingMultiple:1.4
    });
  });

  // GitHub link
  s.addShape(pres.shapes.RECTANGLE, {
    x:0.3, y:5.05, w:9.4, h:0.3, fill:{color:NAVY}, line:{color:NAVY}
  });
  s.addText("GitHub:  github.com/girishkurup/ttk-knowledge-agent  —  All source code + session data + SQLite DB committed", {
    x:0.3, y:5.05, w:9.4, h:0.3,
    fontSize:10, fontFace:"Calibri", color:WHITE, align:"center", valign:"middle", margin:0
  });

  addFooter(s);
}

// ──────────────────────────────────────────────────────────────────────────────
//  SLIDE 10 — ROADMAP
// ──────────────────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: WHITE };
  addHeader(s, "Roadmap — Next Steps");

  const items = [
    { n:"01", title:"Cloud Deployment",        body:"Deploy to Railway for permanent corporate-accessible URL independent of local machine.", color:NAVY },
    { n:"02", title:"Expand Coverage",          body:"Add more process engineers, batch events and unit operations: granulation, coating, packaging.", color:BLUE },
    { n:"03", title:"CPV Integration",          body:"Link knowledge graph nodes to CPV (Continued Process Verification) risk model entries.", color:MID },
    { n:"04", title:"Cross-Batch Risk Signals", body:"Auto-detect parameters flagged in ≥2 deviation events across batches and alert the admin.", color:TEAL },
    { n:"05", title:"Graph Query Interface",    body:"Add SPARQL or Cypher query interface for downstream agents and regulatory reporting.", color:AMBER },
    { n:"06", title:"Role-Based Access",        body:"Authentication layer — separate Engineer view and Admin view with audit-logged access control.", color:GREEN },
  ];

  items.forEach((item, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 0.3  + col * 4.9;
    const y = 1.0  + row * 1.5;

    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w:4.6, h:1.32,
      fill:{color:"FAFBFF"}, line:{color:"E0E3F0"}, shadow:makeShadow()
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w:0.65, h:1.32, fill:{color:item.color}, line:{color:item.color}
    });
    s.addText(item.n, {
      x, y, w:0.65, h:1.32,
      fontSize:22, fontFace:"Georgia", bold:true, color:WHITE,
      align:"center", valign:"middle", margin:0
    });
    s.addText(item.title, {
      x:x+0.78, y:y+0.1, w:3.7, h:0.35,
      fontSize:13, fontFace:"Calibri", bold:true, color:NAVY, margin:0
    });
    s.addText(item.body, {
      x:x+0.78, y:y+0.46, w:3.7, h:0.76,
      fontSize:11, fontFace:"Calibri", color:MUTED,
      valign:"top", lineSpacingMultiple:1.3
    });
  });

  addFooter(s, "TTK Companion Agent Pipeline — Confidential");
}

// ── Write file ─────────────────────────────────────────────────────────────────
pres.writeFile({ fileName: "C:\\Users\\giris_i001\\Desktop\\techtransferknowledgeagent\\TTK_Executive_Briefing.pptx" })
  .then(() => console.log("✓ TTK_Executive_Briefing.pptx created"))
  .catch(e => { console.error("ERROR:", e); process.exit(1); });
