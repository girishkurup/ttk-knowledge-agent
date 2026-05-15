"""
TTK Agent -- Tech Transfer Knowledge Capture System
===================================================
Two-agent architecture:

  Agent 1 · TTKInterviewAgent
      Conducts a structured, conversational ~5-minute interview with a process
      engineer (Schulz) about batch SUP30498 (Enalapril OSD tablets).
      Extracts tacit knowledge around tablet capping and weight variability
      during commercial scale-up.

  Agent 2 · KnowledgeSynthesisAgent
      Reads the interview transcript and produces:
        * A structured Knowledge Article
        * A Pre-emptive Process Checklist

Usage:
    python ttk_agent.py          # live interview mode
    python ttk_agent.py --demo   # replay a built-in demo transcript
"""

import anthropic
import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Force UTF-8 stdout/stderr on Windows so Unicode in prompts and LLM output renders correctly
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load ANTHROPIC_API_KEY from .env — override=True so a blank inherited env var doesn't block it
load_dotenv(Path(__file__).parent / ".env", override=True)

# -- Anthropic client ---------------------------------------------------------
client = anthropic.Anthropic()

BATCH_ID  = "SUP30498"
PRODUCT   = "Enalapril Tablets (OSD)"
ENGINEER  = "Schulz"
MODEL     = "claude-sonnet-4-6"

# =============================================================================
#  SYSTEM PROMPTS
# =============================================================================

TTK_INTERVIEW_SYSTEM = f"""You are the TTK Agent (Tech Transfer Knowledge Agent), a specialist in \
capturing tacit process knowledge from pharmaceutical manufacturing engineers.

CONTEXT
-------
You are meeting with {ENGINEER}, a senior process engineer, for a structured \
5-minute knowledge-capture session about batch {BATCH_ID} ({PRODUCT}).

Known facts from batch records and deviation notes:
  * Batch experienced a moderate increase in tablet rejection during commercial scale-up
  * Issues observed: intermittent tablet capping during compression, weight variability
  * Process transferred from pilot plant to commercial site

YOUR ROLE
---------
Conduct a warm, professional interview to surface the tacit knowledge that lives in \
Schulz's head -- the details that never make it into formal documents.

RULES
-----
1. Ask ONE focused question per turn. Never stack two questions.
2. Probe technically when Schulz mentions parameters, observations, or adjustments.
3. Use pharmaceutical manufacturing language naturally (e.g., compaction force, \
   dwell time, punch penetration depth, granule moisture, feed frame speed, \
   pre-compression, turret speed, API morphology).
4. Actively listen -- reference what Schulz said in your follow-up.
5. Explore these areas (weave naturally -- not as a checklist):
     a) What was observed: symptoms, timing, batch progression
     b) Process parameters at time of issue (compaction force, speed, feed frame, \
        punch geometry)
     c) Material factors (API lot, excipient moisture, PSD, blend flowability)
     d) Troubleshooting steps tried and their outcomes
     e) Root cause hypothesis
     f) Resolution -- what finally worked
     g) Undocumented adjustments / "tricks" applied
     h) What Schulz would do differently at scale-up start
6. After 6–8 exchanges, close professionally: thank Schulz, summarize the 3–4 \
   critical insights captured, and state that the Knowledge Article will be generated.

TONE: Collegial, curious, technically credible. Not bureaucratic."""


SYNTHESIS_SYSTEM = """You are a pharmaceutical manufacturing knowledge management specialist.

INPUT: A raw interview transcript between the TTK Agent and a process engineer.

OUTPUT: Valid JSON with exactly two keys:
  "knowledge_article"  -- markdown string (see structure below)
  "checklist"          -- markdown string (see structure below)

KNOWLEDGE ARTICLE STRUCTURE
----------------------------
# Knowledge Article -- [Batch ID]: [Product]
**Document ID:** KA-[YYMMDD]-[Batch]
**Classification:** Process -- Solid Dosage Compression
**Date:** [today]
**Author:** TTK Agent (auto-generated from engineer interview)

## 1. Batch Context
## 2. Problem Description
## 3. Timeline of Events
## 4. Process Parameters of Interest (table: Parameter | Pilot | Commercial | Delta)
## 5. Material / Formulation Factors
## 6. Troubleshooting Steps Taken (numbered list with outcomes)
## 7. Root Cause Analysis
## 8. Resolution
## 9. Lessons Learned
## 10. Recommendations for Future Scale-Ups

CHECKLIST STRUCTURE
-------------------
# Compression Scale-Up Checklist -- Derived from Batch SUP30498

## Pre-Compression (Materials)
## Pre-Compression (Equipment)
## Scale-Up Specific Considerations
## During-Run Monitoring Triggers
## Escalation / Red Flag Criteria
## Documentation Requirements

Use checkboxes: `- [ ] item`
Be specific and actionable -- not generic.

Return ONLY the JSON object. No preamble, no code fences."""


GRAPH_EXTRACTION_SYSTEM = """You are a pharmaceutical knowledge graph extraction specialist.

INPUT: An interview transcript between a TTK Agent and a process engineer.

TASK: Extract all entities and relationships as a knowledge graph.

NODE TYPES — use exactly these labels:
  Batch        A manufacturing batch (e.g., SUP30498)
  Product      A drug product (e.g., Enalapril Tablets OSD)
  Engineer     A named process engineer
  Operator     A named machine operator or technician
  Equipment    A named piece of equipment (tablet press, etc.)
  Site         A manufacturing site (pilot plant, commercial)
  Issue        A process problem (capping, lamination, weight variability)
  Parameter    A measurable process parameter (turret speed, LOD, force)
  RootCause    An identified or hypothesised root cause
  Material     A material, excipient, or API
  Action       A troubleshooting or corrective action taken
  Resolution   The final resolution or confirmed fix
  Lesson       A lessons-learned insight or recommendation
  Observation  A specific, time-stamped observation during the batch

EDGE LABELS — use these or invent precise domain-specific labels:
  EXPERIENCED, CAUSED_BY, RESOLVED_BY, INVESTIGATED_BY, PERFORMED_BY
  RAN_ON, SCALED_TO, TRANSFERRED_FROM, TRANSFERRED_TO
  LINKED_TO, CHANGED_FROM, CHANGED_TO, INTERACTS_WITH
  RESULTED_IN, ADDRESSED, MODIFIED, DERIVED_FROM
  RECOMMENDS, REPORTED, OBSERVED_IN, IDENTIFIED_BY, CONTRIBUTED_TO

RULES:
1. Every distinct entity in the transcript becomes a node.
2. Every meaningful relationship becomes a directed edge.
3. Node IDs: lowercase, underscores, no spaces (e.g., "batch_sup30498", "issue_capping").
4. Include 2-4 key properties per node and 0-2 per edge.
5. Aim for 15-25 nodes and 20-35 edges.
6. Return ONLY valid JSON — no markdown, no preamble.

OUTPUT:
{
  "nodes": [
    { "id": "string", "label": "short display label", "type": "NodeType",
      "properties": { "key": "value" } }
  ],
  "edges": [
    { "id": "string", "from": "node_id", "to": "node_id",
      "label": "RELATIONSHIP", "properties": { "key": "value" } }
  ],
  "metadata": {
    "batch_id": "string", "product": "string", "engineer": "string",
    "extraction_date": "string", "node_count": 0, "edge_count": 0
  }
}"""


# =============================================================================
#  AGENT 1 -- TTK Interview Agent
# =============================================================================

class TTKInterviewAgent:
    """Conducts a structured lessons-learned interview with a process engineer."""

    MAX_ENGINEER_TURNS = 7   # after this many engineer replies, close the interview

    def __init__(self):
        self.history: list[dict] = []
        self.engineer_turns = 0

    # -- helpers --------------------------------------------------------------

    def _call(self, extra_instruction: str = "") -> str:
        messages = list(self.history)
        if extra_instruction:
            messages[-1] = dict(messages[-1])
            messages[-1]["content"] += f"\n\n[SYSTEM NOTE -- for TTK Agent only: {extra_instruction}]"

        full_text = ""
        with client.messages.stream(
            model=MODEL,
            max_tokens=600,
            system=TTK_INTERVIEW_SYSTEM,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
                full_text += text
        print()  # newline after stream ends
        return full_text

    # -- public API -----------------------------------------------------------

    def open_interview(self) -> str:
        """Generate the TTK Agent's opening statement."""
        seed = {
            "role": "user",
            "content": (
                "[SESSION START -- TTK Agent: introduce yourself, reference batch "
                f"{BATCH_ID} and the tablet rejection issue, ask {ENGINEER} to "
                "describe what happened in their own words.]"
            ),
        }
        self.history.append(seed)
        opening = self._call()
        self.history.append({"role": "assistant", "content": opening})
        return opening

    def respond_to_engineer(self, engineer_reply: str) -> tuple[str, bool]:
        """
        Process engineer's input and return (agent_response, interview_complete).
        interview_complete=True signals the synthesis agent should run.
        """
        self.engineer_turns += 1
        self.history.append({"role": "user", "content": f"[{ENGINEER}]: {engineer_reply}"})

        closing = self.engineer_turns >= self.MAX_ENGINEER_TURNS
        note = (
            "This is the final exchange. Wrap up: thank the engineer warmly, "
            "summarise the 3–4 most valuable insights captured (be specific), "
            "then state you will generate the Knowledge Article and Checklist."
        ) if closing else ""

        response = self._call(extra_instruction=note)
        self.history.append({"role": "assistant", "content": response})
        return response, closing

    def transcript(self) -> str:
        """Return the full conversation as a formatted text transcript."""
        lines = [
            "=" * 65,
            "  TTK AGENT -- INTERVIEW TRANSCRIPT",
            f"  Batch:    {BATCH_ID}",
            f"  Product:  {PRODUCT}",
            f"  Engineer: {ENGINEER}",
            f"  Date:     {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "=" * 65,
            "",
        ]
        for msg in self.history:
            raw = msg["content"]
            # strip internal system seeds
            if "[SESSION START" in raw or "[SYSTEM NOTE" in raw:
                continue
            if msg["role"] == "assistant":
                lines += ["[TTK AGENT]", raw, ""]
            else:
                text = raw.replace(f"[{ENGINEER}]: ", "")
                lines += [f"[{ENGINEER}]", text, ""]
        return "\n".join(lines)


# =============================================================================
#  AGENT 2 -- Knowledge Synthesis Agent
# =============================================================================

class KnowledgeSynthesisAgent:
    """Transforms an interview transcript into a Knowledge Article and Checklist."""

    def synthesize(self, transcript: str) -> dict:
        _header("SYNTHESIS AGENT  --  processing transcript")
        full_text = ""
        with client.messages.stream(
            model=MODEL,
            max_tokens=8000,
            system=SYNTHESIS_SYSTEM,
            messages=[{
                "role": "user",
                "content": (
                    "Generate the knowledge article and checklist from this "
                    f"interview transcript:\n\n{transcript}\n\n"
                    "Return ONLY valid JSON with keys 'knowledge_article' and 'checklist'."
                ),
            }],
        ) as stream:
            for text in stream.text_stream:
                print(".", end="", flush=True)
                full_text += text
        print("\n")

        # strip accidental code fences
        cleaned = full_text.strip()
        for fence in ("```json", "```"):
            if cleaned.startswith(fence):
                cleaned = cleaned[len(fence):]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"knowledge_article": cleaned, "checklist": "⚠ Parse error -- see knowledge_article."}

    def save(self, artifacts: dict, output_dir: Path) -> tuple[Path, Path]:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        ka = output_dir / f"KA_{BATCH_ID}_{ts}.md"
        cl = output_dir / f"Checklist_{BATCH_ID}_{ts}.md"
        ka.write_text(artifacts["knowledge_article"], encoding="utf-8")
        cl.write_text(artifacts["checklist"], encoding="utf-8")
        return ka, cl


# =============================================================================
#  AGENT 3 -- Knowledge Graph Agent
# =============================================================================

# One hex colour per node type — used in both Python and the generated HTML
_NODE_COLORS: dict[str, str] = {
    "Batch":       "#2196F3",
    "Product":     "#00BCD4",
    "Engineer":    "#FF9800",
    "Operator":    "#FF5722",
    "Equipment":   "#607D8B",
    "Site":        "#9C27B0",
    "Issue":       "#F44336",
    "Parameter":   "#F9A825",
    "RootCause":   "#B71C1C",
    "Material":    "#388E3C",
    "Action":      "#673AB7",
    "Resolution":  "#2E7D32",
    "Lesson":      "#00838F",
    "Observation": "#E64A19",
}


class KnowledgeGraphAgent:
    """Extracts a knowledge graph from a transcript and saves JSON + interactive HTML."""

    def extract(self, transcript: str) -> dict:
        _header("KNOWLEDGE GRAPH AGENT  --  extracting entities and relationships")
        full_text = ""
        with client.messages.stream(
            model=MODEL,
            max_tokens=8000,
            system=GRAPH_EXTRACTION_SYSTEM,
            messages=[{
                "role": "user",
                "content": (
                    "Extract the knowledge graph from this interview transcript.\n\n"
                    f"{transcript}\n\n"
                    "Return ONLY the JSON object described in your instructions."
                ),
            }],
        ) as stream:
            for text in stream.text_stream:
                print(".", end="", flush=True)
                full_text += text
        print("\n")

        cleaned = full_text.strip()
        for fence in ("```json", "```"):
            if cleaned.startswith(fence):
                cleaned = cleaned[len(fence):]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        try:
            data = json.loads(cleaned.strip())
        except json.JSONDecodeError:
            print("  [Graph Agent] JSON parse error -- returning empty graph")
            data = {"nodes": [], "edges": [], "metadata": {}}

        data.setdefault("metadata", {})
        data["metadata"].update({
            "batch_id": BATCH_ID,
            "product": PRODUCT,
            "engineer": ENGINEER,
            "extraction_date": datetime.now().strftime("%Y-%m-%d"),
            "node_count": len(data.get("nodes", [])),
            "edge_count": len(data.get("edges", [])),
        })
        return data

    def save(self, graph_data: dict, output_dir: Path) -> tuple[Path, Path]:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        json_path = output_dir / f"KnowledgeGraph_{BATCH_ID}_{ts}.json"
        html_path = output_dir / f"KnowledgeGraph_{BATCH_ID}_{ts}.html"
        json_path.write_text(json.dumps(graph_data, indent=2, ensure_ascii=False), encoding="utf-8")
        html_path.write_text(_build_graph_html(graph_data), encoding="utf-8")
        return json_path, html_path


# =============================================================================
#  DEMO TRANSCRIPT  (--demo flag)
# =============================================================================

DEMO_TRANSCRIPT = f"""
{'='*65}
  TTK AGENT -- INTERVIEW TRANSCRIPT (DEMO)
  Batch:    {BATCH_ID}
  Product:  {PRODUCT}
  Engineer: {ENGINEER}
  Date:     2026-05-15 09:32
{'='*65}

[TTK AGENT]
Good morning, Schulz. I'm the TTK Agent -- I'm here to help capture the \
process knowledge from batch {BATCH_ID} before it stays locked in the \
deviation notes. I understand the team saw a meaningful uptick in tablet \
rejection during commercial compression. Can you walk me through what you \
observed -- what was happening at the press and when did it first show up?

[{ENGINEER}]
Sure. We started the campaign with Korsch XL800 at commercial scale. About \
2,000 tablets in, the metal detector rejections started climbing -- primarily \
capping events. The pilot batches on the Korsch XL400 had been clean. We \
were running the same recipe, but the rejection rate went from less than 0.5% \
on the pilot to around 4–5% on commercial.

[TTK AGENT]
That's a significant jump. When you say capping -- were you seeing full \
cap-offs where the crown separates completely, or more of a lamination tendency \
where the tablet wanted to delaminate but didn't always eject broken? And was \
it occurring on specific punch positions or random across the turret?

[{ENGINEER}]
More lamination tendency than full caps initially, but some punches were worse. \
Positions 12 and 13 on the upper punch row were the worst offenders -- we pulled \
and inspected them; they looked fine, no chips or marks. The lamination was \
occurring just after the ejection cam, not at main compression.

[TTK AGENT]
Interesting -- post-ejection suggests the tablet was holding together under load \
but losing cohesion as dwell time ended. What were your main compression force \
settings? And had you changed dwell time or turret speed relative to the XL400 \
campaign?

[{ENGINEER}]
Pilot ran at 12 kN main, 3 kN pre-compression, 20 RPM turret. Commercial we \
tried to match -- 12 kN main, 3.5 kN pre, but turret was at 35 RPM to hit rate \
targets. So effective dwell time dropped considerably. We didn't think it would \
matter because the formulation had been validated at those pressures on the small \
press.

[TTK AGENT]
That dwell time reduction is a critical variable. Enalapril maleate can be \
tricky -- the API has a tendency toward elastic recovery under rapid compression \
cycles. Beyond turret speed, did you check the granule moisture or LOD on the \
commercial-scale blend versus the pilot lots? And what was the blend moisture \
target?

[{ENGINEER}]
Target was 2.0% LOD. Pilot lots came in at 1.9–2.1%. The commercial blend came \
in at 1.6% -- we were within spec but on the low end. We didn't flag it at the \
time. In hindsight, lower moisture reduced the plasticity of the granules and \
that probably made elastic recovery worse under the faster compression cycle.

[TTK AGENT]
That's a key insight -- the interaction between low-end moisture and shortened \
dwell time amplified the capping tendency. What steps did the team take once \
capping was confirmed? Did you reduce turret speed, change compression force, or \
something else?

[{ENGINEER}]
We dropped turret speed to 28 RPM first -- rejection dropped to about 2%. Then \
we bumped pre-compression to 4.5 kN to improve consolidation. That got us to \
under 1%. We also added a force-feeder speed adjustment -- slowing the feed frame \
reduced over-fill variability and that helped the weight CV drop from 1.8% to \
0.9%. The combination of those three got us to an acceptable state.

[TTK AGENT]
And throughout that troubleshooting, were there any undocumented adjustments -- \
anything the press operator or team did that isn't captured in the deviation \
record?

[{ENGINEER}]
Yes, actually. The operator -- Maria -- noticed the lower punch penetration depth \
was set to the pilot value. She manually adjusted it 0.2mm deeper to improve \
die fill consistency. It helped the weight uniformity significantly. That \
adjustment is not in the batch record because it's within the equipment \
operating range, but it made a real difference.

[TTK AGENT]
That's exactly the kind of tacit knowledge this session is designed to capture. \
Thank you, Schulz -- this has been extremely valuable.

To summarise what I've captured:
  1. Dwell time compression: scaling from XL400 to XL800 at higher RPM \
     substantially reduced dwell time -- the formulation's elastic recovery \
     sensitivity was not evaluated against the new dwell profile.
  2. Moisture at the low end of spec interacts critically with rapid compression \
     -- a 2.0% target should carry a tighter commercial action limit (e.g., ≥1.8%).
  3. Pre-compression force requires re-optimisation at commercial scale, not \
     direct transfer from pilot.
  4. Punch penetration depth -- a 0.2mm deeper setting improved die fill; this \
     parameter should be explicitly included in the commercial compression \
     procedure, not left as an implicit pilot carry-over.

I'll now generate the Knowledge Article and Checklist from this session. \
These will be available for the next scale-up and for training new engineers \
on this formulation.
""".strip()


# =============================================================================
#  UI HELPERS
# =============================================================================

def _header(title: str) -> None:
    print(f"\n{'-'*65}")
    print(f"  {title}")
    print(f"{'-'*65}\n")

def _banner() -> None:
    print("\n" + "=" * 65)
    print("  TTK AGENT  --  Tech Transfer Knowledge Capture System")
    print("  Pharmaceutical Process Engineering  |  Scale-Up Support")
    print("=" * 65)
    print(f"  Batch:    {BATCH_ID}")
    print(f"  Product:  {PRODUCT}")
    print(f"  Engineer: {ENGINEER}")
    print(f"  Session:  {datetime.now().strftime('%Y-%m-%d  %H:%M')}")
    print("=" * 65)
    print("\n  Commands during interview:")
    print("    * Type your response and press Enter")
    print("    * Type  done  to end the session early")
    print()

def _preview(text: str, label: str, lines: int = 25) -> None:
    _header(f"PREVIEW -- {label}")
    split = text.split("\n")
    print("\n".join(split[:lines]))
    if len(split) > lines:
        print(f"\n  ... {len(split) - lines} more lines in the saved file")


# Raw HTML template — uses __PLACEHOLDER__ tokens instead of f-string so that
# JavaScript's curly braces don't conflict with Python's f-string syntax.
_GRAPH_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Knowledge Graph -- __BATCH_ID__ | TTK Agent</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',Arial,sans-serif;background:#f5f7fa;color:#333;height:100vh;display:flex;flex-direction:column;overflow:hidden}
  #hdr{background:linear-gradient(135deg,#1a237e,#283593);color:#fff;padding:10px 18px;display:flex;justify-content:space-between;align-items:center;flex-shrink:0}
  #hdr h1{font-size:17px;font-weight:600}
  #hdr .sub{font-size:11px;opacity:.75;margin-top:2px}
  #hdr .meta{font-size:11px;opacity:.8;text-align:right}
  #main{display:flex;flex:1;overflow:hidden}
  #net-wrap{flex:1;position:relative;background:#fff;border-right:1px solid #e0e0e0}
  #network{width:100%;height:100%}
  .ctrls{position:absolute;top:10px;left:10px;display:flex;gap:6px;z-index:10}
  .btn{background:#fff;border:1px solid #ccc;padding:5px 10px;border-radius:4px;font-size:11px;cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,.12)}
  .btn:hover{background:#f0f0f0}
  #sidebar{width:270px;display:flex;flex-direction:column;background:#fff;overflow-y:auto;flex-shrink:0}
  .panel{padding:14px;border-bottom:1px solid #efefef}
  .panel-title{font-size:11px;font-weight:700;color:#777;text-transform:uppercase;letter-spacing:.6px;margin-bottom:10px}
  #stats{display:flex;border-bottom:1px solid #efefef}
  .stat{flex:1;text-align:center;padding:12px 4px;border-right:1px solid #efefef}
  .stat:last-child{border-right:none}
  .stat-n{font-size:24px;font-weight:700;color:#1a237e;line-height:1}
  .stat-l{font-size:10px;color:#999;margin-top:3px}
  .legend-row{display:flex;align-items:center;margin:4px 0;font-size:12px}
  .dot{width:11px;height:11px;border-radius:50%;margin-right:8px;flex-shrink:0}
  #det-content{font-size:12px;color:#555}
  .tag{display:inline-block;padding:2px 8px;border-radius:10px;color:#fff;font-size:11px;margin-bottom:6px}
  .node-lbl{font-size:15px;font-weight:600;color:#222;margin-bottom:8px}
  .prop-table{width:100%;border-collapse:collapse;margin-top:4px}
  .prop-table td{padding:3px 0;vertical-align:top;border-bottom:1px solid #f5f5f5}
  .prop-table td:first-child{color:#999;width:42%;font-size:11px;padding-right:6px}
  .rel-section{margin-top:10px}
  .rel-title{font-size:11px;color:#aaa;font-weight:700;margin-bottom:4px}
  .rel-row{font-size:11px;padding:3px 0;border-bottom:1px solid #f7f7f7;color:#555}
  .placeholder{color:#ccc;font-style:italic}
  #ftr{background:#f5f5f5;border-top:1px solid #e0e0e0;padding:5px 14px;font-size:10px;color:#aaa;display:flex;justify-content:space-between;flex-shrink:0}
  #search-wrap{padding:10px 14px;border-bottom:1px solid #efefef}
  #search{width:100%;padding:5px 8px;border:1px solid #ddd;border-radius:4px;font-size:12px}
</style>
</head>
<body>
<div id="hdr">
  <div>
    <h1>Knowledge Graph &mdash; Batch __BATCH_ID__</h1>
    <div class="sub">__PRODUCT__ &nbsp;|&nbsp; TTK Agent Knowledge Capture</div>
  </div>
  <div class="meta">
    <div>Engineer: __ENGINEER__</div>
    <div>Generated: __TIMESTAMP__</div>
  </div>
</div>
<div id="main">
  <div id="net-wrap">
    <div class="ctrls">
      <button class="btn" onclick="net.fit()">Fit View</button>
      <button class="btn" id="phys-btn" onclick="togglePhysics()">Freeze Layout</button>
      <button class="btn" onclick="dlJSON()">Export JSON</button>
    </div>
    <div id="network"></div>
  </div>
  <div id="sidebar">
    <div id="stats">
      <div class="stat"><div class="stat-n">__N_NODES__</div><div class="stat-l">Nodes</div></div>
      <div class="stat"><div class="stat-n">__N_EDGES__</div><div class="stat-l">Edges</div></div>
      <div class="stat"><div class="stat-n" id="type-count">-</div><div class="stat-l">Types</div></div>
    </div>
    <div id="search-wrap">
      <input id="search" type="text" placeholder="Search nodes..." oninput="filterNodes(this.value)">
    </div>
    <div class="panel">
      <div class="panel-title">Node Types</div>
      <div id="legend-items"></div>
    </div>
    <div class="panel" style="flex:1">
      <div class="panel-title">Selected Node</div>
      <div id="det-content"><p class="placeholder">Click any node to inspect</p></div>
    </div>
  </div>
</div>
<div id="ftr">
  <span>TTK Agent &mdash; Tech Transfer Knowledge Capture System</span>
  <span>Batch __BATCH_ID__ &nbsp;|&nbsp; __PRODUCT__</span>
</div>
<script>
const G      = __GRAPH_JSON__;
const COLORS = __COLORS_JSON__;
let physOn   = true;

function shade(hex, p) {
  const n=parseInt(hex.replace('#',''),16);
  const r=Math.min(255,Math.max(0,(n>>16)+p));
  const g=Math.min(255,Math.max(0,((n>>8)&0xFF)+p));
  const b=Math.min(255,Math.max(0,(n&0xFF)+p));
  return '#'+((1<<24)+(r<<16)+(g<<8)+b).toString(16).slice(1);
}
function contrast(hex) {
  const n=parseInt(hex.replace('#',''),16);
  const lum=(0.299*(n>>16)+0.587*((n>>8)&0xFF)+0.114*(n&0xFF))/255;
  return lum>0.5?'#222':'#fff';
}
function nodeTip(n) {
  const c=COLORS[n.type]||'#999';
  let h='<div style="font-family:Segoe UI,Arial;font-size:12px;background:#fff;padding:8px;border-radius:4px;box-shadow:0 2px 8px rgba(0,0,0,.2);max-width:230px">';
  h+='<span style="background:'+c+';color:'+contrast(c)+';padding:2px 7px;border-radius:10px;font-size:10px">'+n.type+'</span>';
  h+='<div style="font-weight:600;margin:5px 0 3px">'+n.label+'</div>';
  Object.entries(n.properties||{}).forEach(([k,v])=>{h+='<div style="color:#777">'+k+': <b>'+v+'</b></div>';});
  return h+'</div>';
}
function edgeTip(e) {
  let h='<div style="font-family:Segoe UI,Arial;font-size:11px;background:#fff;padding:6px 10px;border-radius:4px;box-shadow:0 2px 6px rgba(0,0,0,.15)"><b>'+e.label+'</b>';
  Object.entries(e.properties||{}).forEach(([k,v])=>{h+='<br>'+k+': '+v;});
  return h+'</div>';
}

// Legend
const usedTypes=[...new Set(G.nodes.map(n=>n.type))].sort();
document.getElementById('type-count').textContent=usedTypes.length;
const legEl=document.getElementById('legend-items');
usedTypes.forEach(t=>{
  legEl.innerHTML+='<div class="legend-row"><div class="dot" style="background:'+(COLORS[t]||'#999')+'"></div>'+t+'</div>';
});

// Build vis datasets
const nodesDS=new vis.DataSet(G.nodes.map(n=>{
  const c=COLORS[n.type]||'#999';
  return {
    id:n.id, label:n.label, title:nodeTip(n),
    color:{background:c,border:shade(c,-25),highlight:{background:c,border:'#1a237e'},hover:{background:shade(c,15),border:shade(c,-15)}},
    font:{color:contrast(c),size:12},
    shape:'dot',size:22,shadow:{enabled:true,size:4,x:2,y:2},
    _raw:n
  };
}));
const edgesDS=new vis.DataSet(G.edges.map(e=>({
  id:e.id,from:e.from,to:e.to,label:e.label,title:edgeTip(e),
  arrows:'to',width:1.5,selectionWidth:2.5,
  font:{size:10,align:'middle',background:'white',strokeWidth:0},
  color:{color:'#bbb',highlight:'#1a237e',hover:'#3949AB'},
  smooth:{type:'dynamic'},_raw:e
})));

// Network
const net=new vis.Network(document.getElementById('network'),{nodes:nodesDS,edges:edgesDS},{
  nodes:{shape:'dot',size:22,font:{size:12,face:'Segoe UI,Arial'},borderWidth:2},
  edges:{width:1.5,font:{size:10,face:'Segoe UI,Arial'}},
  physics:{
    solver:'forceAtlas2Based',
    forceAtlas2Based:{gravitationalConstant:-55,centralGravity:0.006,springLength:170,springConstant:0.05,damping:0.4},
    stabilization:{iterations:300,updateInterval:30}
  },
  interaction:{hover:true,tooltipDelay:120,keyboard:true}
});
net.on('stabilizationIterationsDone',()=>{
  net.setOptions({physics:{enabled:false}});
  physOn=false;
  document.getElementById('phys-btn').textContent='Unfreeze Layout';
});

// Click -> detail panel
net.on('click',p=>{
  if(!p.nodes.length){document.getElementById('det-content').innerHTML='<p class="placeholder">Click any node to inspect</p>';return;}
  const raw=G.nodes.find(n=>n.id===p.nodes[0]);
  if(!raw)return;
  const c=COLORS[raw.type]||'#999';
  let h='<span class="tag" style="background:'+c+'">'+raw.type+'</span>';
  h+='<div class="node-lbl">'+raw.label+'</div>';
  const props=Object.entries(raw.properties||{});
  if(props.length){
    h+='<table class="prop-table">';
    props.forEach(([k,v])=>{h+='<tr><td>'+k+'</td><td>'+v+'</td></tr>';});
    h+='</table>';
  }
  const rels=G.edges.filter(e=>e.from===raw.id||e.to===raw.id);
  if(rels.length){
    h+='<div class="rel-section"><div class="rel-title">Relationships ('+rels.length+')</div>';
    rels.forEach(e=>{
      const out=e.from===raw.id;
      const otherId=out?e.to:e.from;
      const other=G.nodes.find(n=>n.id===otherId);
      h+='<div class="rel-row">'+(out?'&rarr;':'&larr;')+' <b>'+e.label+'</b> &nbsp;'+(other?other.label:otherId)+'</div>';
    });
    h+='</div>';
  }
  document.getElementById('det-content').innerHTML=h;
});

// Search
function filterNodes(q){
  const term=q.toLowerCase().trim();
  if(!term){
    G.nodes.forEach(n=>{const c=COLORS[n.type]||'#999';nodesDS.update({id:n.id,color:{background:c,border:shade(c,-25)}});});
    return;
  }
  G.nodes.forEach(n=>{
    const hit=n.label.toLowerCase().includes(term)||n.type.toLowerCase().includes(term)||JSON.stringify(n.properties||{}).toLowerCase().includes(term);
    const c=COLORS[n.type]||'#999';
    nodesDS.update({id:n.id,color:hit?{background:c,border:shade(c,-25)}:{background:'#eee',border:'#ccc'}});
  });
}
function togglePhysics(){
  physOn=!physOn;
  net.setOptions({physics:{enabled:physOn}});
  document.getElementById('phys-btn').textContent=physOn?'Freeze Layout':'Unfreeze Layout';
}
function dlJSON(){
  const b=new Blob([JSON.stringify(G,null,2)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(b);
  a.download='KnowledgeGraph___BATCH_ID__.json';a.click();
}
</script>
</body>
</html>"""


def _build_graph_html(graph_data: dict) -> str:
    """Return a self-contained HTML page with an interactive vis-network graph.

    Uses __PLACEHOLDER__ substitution so JavaScript braces don't conflict
    with Python f-string syntax.
    """
    graph_json   = json.dumps(graph_data, ensure_ascii=False)
    colors_json  = json.dumps(_NODE_COLORS, ensure_ascii=False)
    ts_str       = datetime.now().strftime("%Y-%m-%d %H:%M")
    meta         = graph_data.get("metadata", {})
    n_nodes      = str(meta.get("node_count", len(graph_data.get("nodes", []))))
    n_edges      = str(meta.get("edge_count", len(graph_data.get("edges", []))))

    tpl = _GRAPH_HTML_TEMPLATE
    return (tpl
        .replace("__GRAPH_JSON__",  graph_json)
        .replace("__COLORS_JSON__", colors_json)
        .replace("__BATCH_ID__",    BATCH_ID)
        .replace("__PRODUCT__",     PRODUCT)
        .replace("__ENGINEER__",    ENGINEER)
        .replace("__TIMESTAMP__",   ts_str)
        .replace("__N_NODES__",     n_nodes)
        .replace("__N_EDGES__",     n_edges)
    )


# =============================================================================
#  ENTRY POINT
# =============================================================================

def _run_post_interview(transcript_text: str, output_dir: Path) -> None:
    """Shared pipeline: synthesis + knowledge graph, run after any interview."""
    synthesis = KnowledgeSynthesisAgent()
    graph_agent = KnowledgeGraphAgent()

    # Agent 2 -- Knowledge Article + Checklist
    artifacts = synthesis.synthesize(transcript_text)
    ka_path, cl_path = synthesis.save(artifacts, output_dir)
    print(f"  Knowledge Article  --> {ka_path}")
    print(f"  Checklist          --> {cl_path}")

    # Agent 3 -- Knowledge Graph (JSON + HTML)
    graph_data = graph_agent.extract(transcript_text)
    json_path, html_path = graph_agent.save(graph_data, output_dir)
    m = graph_data.get("metadata", {})
    print(f"  Knowledge Graph    --> {json_path}  ({m.get('node_count',0)} nodes, {m.get('edge_count',0)} edges)")
    print(f"  Graph Viewer (HTML)--> {html_path}")
    print(f"\n  Open the HTML file in any browser to explore the interactive graph.")

    _preview(artifacts["knowledge_article"], "Knowledge Article")
    _preview(artifacts["checklist"], "Compression Scale-Up Checklist")

    # Quick graph summary in console
    _header("KNOWLEDGE GRAPH -- node summary")
    from collections import Counter
    type_counts = Counter(n["type"] for n in graph_data.get("nodes", []))
    for ntype, count in sorted(type_counts.items()):
        print(f"  {ntype:<14} {count} node{'s' if count != 1 else ''}")
    print()


def run_live_interview(output_dir: Path) -> None:
    interview = TTKInterviewAgent()

    _header("TTK AGENT  --  Opening Interview")
    interview.open_interview()

    done = False
    while not done:
        print(f"\n{'-'*65}")
        try:
            user_input = input(f"  [{ENGINEER}] > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n  [Session interrupted]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("done", "exit", "quit", "end"):
            print("\n  [Ending interview early -- proceeding to synthesis]\n")
            break

        print(f"\n[TTK AGENT]")
        _, done = interview.respond_to_engineer(user_input)

    transcript_text = interview.transcript()
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    tx_path = output_dir / f"Transcript_{BATCH_ID}_{ts}.txt"
    tx_path.write_text(transcript_text, encoding="utf-8")
    print(f"\n  Transcript saved   --> {tx_path}\n")

    _run_post_interview(transcript_text, output_dir)

    print("\n" + "=" * 65)
    print("  KNOWLEDGE CAPTURE COMPLETE")
    print("=" * 65 + "\n")


def run_demo(output_dir: Path) -> None:
    """Synthesize from the built-in demo transcript (no live input needed)."""
    _header("DEMO MODE  --  using pre-loaded interview transcript")
    print(DEMO_TRANSCRIPT)

    _run_post_interview(DEMO_TRANSCRIPT, output_dir)

    print("\n" + "=" * 65)
    print("  DEMO COMPLETE  --  artifacts saved to ttk_output/")
    print("=" * 65 + "\n")


def main() -> None:
    demo_mode = "--demo" in sys.argv
    output_dir = Path("ttk_output")
    output_dir.mkdir(exist_ok=True)

    _banner()

    if demo_mode:
        run_demo(output_dir)
    else:
        run_live_interview(output_dir)


if __name__ == "__main__":
    main()
