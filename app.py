"""
TTK Agent -- Web Interface
FastAPI server with WebSocket streaming for the live interview chat.

Run:
    uvicorn app:app --reload --port 8000
Then open:
    http://localhost:8000
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# ── Bootstrap ─────────────────────────────────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(Path(__file__).parent / ".env", override=True)

# Pull shared constants and the HTML graph builder from the CLI module
from ttk_agent import (
    BATCH_ID, ENGINEER, GRAPH_EXTRACTION_SYSTEM, MODEL, PRODUCT,
    SYNTHESIS_SYSTEM, TTK_INTERVIEW_SYSTEM, _build_graph_html,
)

OUTPUT_DIR = Path("ttk_output")
OUTPUT_DIR.mkdir(exist_ok=True)

MAX_TURNS   = 7          # engineer replies before auto-close
TOKEN_LIMIT = 8000       # synthesis / graph agents

# Async Anthropic client (required for FastAPI async context)
aclient = anthropic.AsyncAnthropic()

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="TTK Agent")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")


# ── Utility helpers ───────────────────────────────────────────────────────────

async def stream_to_ws(ws: WebSocket, messages: list, system: str,
                       max_tokens: int = 700) -> str:
    """Stream Claude tokens over WebSocket; return accumulated text."""
    full = ""
    await ws.send_json({"type": "agent_start"})
    async with aclient.messages.stream(
        model=MODEL, max_tokens=max_tokens, system=system, messages=messages,
    ) as stream:
        async for chunk in stream.text_stream:
            full += chunk
            await ws.send_json({"type": "agent_token", "text": chunk})
    await ws.send_json({"type": "agent_done"})
    return full


async def call_silent(messages: list, system: str, max_tokens: int) -> str:
    """Non-streaming Claude call (synthesis / graph)."""
    full = ""
    async with aclient.messages.stream(
        model=MODEL, max_tokens=max_tokens, system=system, messages=messages,
    ) as stream:
        async for chunk in stream.text_stream:
            full += chunk
    return full


def parse_json(raw: str) -> dict:
    s = raw.strip()
    for fence in ("```json", "```"):
        if s.startswith(fence):
            s = s[len(fence):]
    if s.endswith("```"):
        s = s[:-3]
    return json.loads(s.strip())


def build_transcript(history: list) -> str:
    lines = [
        "=" * 65,
        "  TTK AGENT -- INTERVIEW TRANSCRIPT",
        f"  Batch:    {BATCH_ID}",
        f"  Product:  {PRODUCT}",
        f"  Engineer: {ENGINEER}",
        f"  Date:     {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 65, "",
    ]
    for msg in history:
        raw = msg["content"]
        if "[SESSION START" in raw or "[SYSTEM NOTE" in raw:
            continue
        speaker = "TTK AGENT" if msg["role"] == "assistant" else ENGINEER
        lines += [f"[{speaker}]", raw.replace(f"[{ENGINEER}]: ", ""), ""]
    return "\n".join(lines)


# ── WebSocket interview handler ───────────────────────────────────────────────

@app.websocket("/ws/{session_id}")
async def interview_ws(ws: WebSocket, session_id: str):
    await ws.accept()
    history: list[dict] = []
    turn = 0

    try:
        while True:
            data = await ws.receive_json()

            # ── Start: send opening question ──────────────────────────────
            if data["type"] == "start":
                seed = {
                    "role": "user",
                    "content": (
                        f"[SESSION START -- TTK Agent: introduce yourself, "
                        f"reference batch {BATCH_ID} and the tablet rejection issue, "
                        f"ask {ENGINEER} to describe what happened in their own words.]"
                    ),
                }
                history.append(seed)
                opening = await stream_to_ws(ws, history, TTK_INTERVIEW_SYSTEM)
                history.append({"role": "assistant", "content": opening})
                await ws.send_json({"type": "turn_update", "turn": 0,
                                    "max_turns": MAX_TURNS})

            # ── Engineer reply ────────────────────────────────────────────
            elif data["type"] == "message":
                turn += 1
                history.append({"role": "user",
                                 "content": f"[{ENGINEER}]: {data['text'].strip()}"})

                closing = turn >= MAX_TURNS
                messages = list(history)
                if closing:
                    note = (
                        "\n\n[SYSTEM NOTE -- for TTK Agent only: "
                        "Final exchange. Wrap up warmly, summarise the 3-4 "
                        "most valuable tacit insights captured (be specific), "
                        "then say you will now generate the Knowledge Article "
                        "and Process Checklist.]"
                    )
                    messages[-1] = {**messages[-1],
                                    "content": messages[-1]["content"] + note}

                reply = await stream_to_ws(ws, messages, TTK_INTERVIEW_SYSTEM)
                history.append({"role": "assistant", "content": reply})
                await ws.send_json({"type": "turn_update", "turn": turn,
                                    "max_turns": MAX_TURNS})

                if closing:
                    await _post_process(ws, history)
                    break

            # ── Engineer ends early ───────────────────────────────────────
            elif data["type"] == "finish_early":
                await _post_process(ws, history)
                break

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await ws.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass


async def _post_process(ws: WebSocket, history: list):
    """Run Agent 2 (synthesis) and Agent 3 (graph) after the interview ends."""
    transcript = build_transcript(history)
    ts = datetime.now().strftime("%Y%m%d_%H%M")

    # Save transcript
    tx = OUTPUT_DIR / f"Transcript_{BATCH_ID}_{ts}.txt"
    tx.write_text(transcript, encoding="utf-8")
    await ws.send_json({"type": "interview_complete"})

    # ── Agent 2: Knowledge Article + Checklist ────────────────────────────
    await ws.send_json({"type": "phase",
                        "label": "Agent 2 -- Synthesis",
                        "message": "Generating Knowledge Article & Checklist..."})
    try:
        raw = await call_silent(
            messages=[{"role": "user", "content":
                f"Generate the knowledge article and checklist from this "
                f"interview transcript:\n\n{transcript}\n\n"
                "Return ONLY valid JSON with keys 'knowledge_article' and 'checklist'."}],
            system=SYNTHESIS_SYSTEM, max_tokens=TOKEN_LIMIT,
        )
        arts = parse_json(raw)
    except Exception as exc:
        arts = {"knowledge_article": f"Generation error: {exc}", "checklist": ""}

    (OUTPUT_DIR / f"KA_{BATCH_ID}_{ts}.md").write_text(
        arts.get("knowledge_article", ""), encoding="utf-8")
    (OUTPUT_DIR / f"Checklist_{BATCH_ID}_{ts}.md").write_text(
        arts.get("checklist", ""), encoding="utf-8")

    await ws.send_json({"type": "synthesis_done",
                        "knowledge_article": arts.get("knowledge_article", ""),
                        "checklist": arts.get("checklist", "")})

    # ── Agent 3: Knowledge Graph ──────────────────────────────────────────
    await ws.send_json({"type": "phase",
                        "label": "Agent 3 -- Knowledge Graph",
                        "message": "Extracting Knowledge Graph..."})
    try:
        raw = await call_silent(
            messages=[{"role": "user", "content":
                f"Extract the knowledge graph from this interview transcript.\n\n"
                f"{transcript}\n\n"
                "Return ONLY the JSON object described in your instructions."}],
            system=GRAPH_EXTRACTION_SYSTEM, max_tokens=TOKEN_LIMIT,
        )
        gdata = parse_json(raw)
    except Exception:
        gdata = {"nodes": [], "edges": [], "metadata": {}}

    gdata.setdefault("metadata", {})
    gdata["metadata"].update({
        "batch_id": BATCH_ID, "product": PRODUCT, "engineer": ENGINEER,
        "extraction_date": datetime.now().strftime("%Y-%m-%d"),
        "node_count": len(gdata.get("nodes", [])),
        "edge_count":  len(gdata.get("edges", [])),
    })

    html_name = f"KnowledgeGraph_{BATCH_ID}_{ts}.html"
    (OUTPUT_DIR / html_name).write_text(
        _build_graph_html(gdata), encoding="utf-8")
    (OUTPUT_DIR / f"KnowledgeGraph_{BATCH_ID}_{ts}.json").write_text(
        json.dumps(gdata, indent=2, ensure_ascii=False), encoding="utf-8")

    await ws.send_json({
        "type": "graph_done",
        "node_count":   gdata["metadata"]["node_count"],
        "edge_count":   gdata["metadata"]["edge_count"],
        "graph_url":    f"/output/{html_name}",
    })
    await ws.send_json({"type": "all_done"})


# ── Main HTML page ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(_html())


def _html() -> str:
    """Build the single-page frontend, substituting Python constants."""
    return _HTML_TEMPLATE.replace("__BATCH_ID__", BATCH_ID)\
                         .replace("__PRODUCT__",  PRODUCT)\
                         .replace("__ENGINEER__", ENGINEER)\
                         .replace("__MAX_TURNS__", str(MAX_TURNS))


# ── HTML Template ─────────────────────────────────────────────────────────────
# Uses __PLACEHOLDER__ tokens so JS curly braces don't conflict with f-strings.

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TTK Agent | Batch __BATCH_ID__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
:root {
  --navy:   #1a237e;
  --blue:   #3949ab;
  --mid:    #5c6bc0;
  --light:  #e8eaf6;
  --bg:     #f0f2f8;
  --white:  #ffffff;
  --border: #dde1f0;
  --text:   #1c1e2e;
  --muted:  #6b7280;
  --green:  #2e7d32;
  --amber:  #f57f17;
  --red:    #c62828;
  --radius: 12px;
  --shadow: 0 2px 12px rgba(26,35,126,.10);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; font-family: 'Inter', system-ui, sans-serif; background: var(--bg); color: var(--text); font-size: 14px; }

/* ── Layout ── */
#app    { display: flex; flex-direction: column; height: 100vh; }
#header { background: linear-gradient(135deg, var(--navy) 0%, #283593 100%);
          color: #fff; padding: 0 24px; height: 56px;
          display: flex; align-items: center; justify-content: space-between;
          flex-shrink: 0; box-shadow: 0 2px 8px rgba(0,0,0,.25); }
#header h1  { font-size: 16px; font-weight: 700; letter-spacing: .3px; }
#header .sub { font-size: 12px; opacity: .75; margin-top: 1px; }
#header .badge { background: rgba(255,255,255,.15); border-radius: 20px;
                 padding: 4px 12px; font-size: 11px; font-weight: 600; }

#body   { display: flex; flex: 1; overflow: hidden; }

/* ── Chat panel ── */
#chat-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden;
              border-right: 1px solid var(--border); }

#messages   { flex: 1; overflow-y: auto; padding: 24px 28px; display: flex;
              flex-direction: column; gap: 20px; }

/* ── Welcome screen ── */
#welcome { flex: 1; display: flex; align-items: center; justify-content: center;
           padding: 40px; }
.welcome-card { background: var(--white); border-radius: var(--radius);
                box-shadow: var(--shadow); padding: 48px 40px; max-width: 520px;
                text-align: center; }
.welcome-card .icon { font-size: 48px; margin-bottom: 20px; }
.welcome-card h2    { font-size: 22px; font-weight: 700; color: var(--navy);
                      margin-bottom: 10px; }
.welcome-card p     { color: var(--muted); line-height: 1.7; margin-bottom: 8px; }
.welcome-card .meta { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center;
                      margin: 20px 0 28px; }
.tag { background: var(--light); color: var(--blue); border-radius: 20px;
       padding: 4px 12px; font-size: 12px; font-weight: 600; }
#start-btn { background: var(--navy); color: #fff; border: none; padding: 14px 36px;
             border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer;
             transition: background .2s, transform .1s; letter-spacing: .3px; }
#start-btn:hover   { background: var(--blue); }
#start-btn:active  { transform: scale(.98); }
#start-btn:disabled { background: #9fa8da; cursor: not-allowed; transform: none; }

/* ── Message bubbles ── */
.msg-row { display: flex; gap: 12px; align-items: flex-start; }
.msg-row.agent { flex-direction: row; }
.msg-row.user  { flex-direction: row-reverse; }

.avatar { width: 36px; height: 36px; border-radius: 50%; flex-shrink: 0;
          display: flex; align-items: center; justify-content: center;
          font-size: 14px; font-weight: 700; }
.avatar.agent-av { background: var(--navy); color: #fff; }
.avatar.user-av  { background: #e0e0e0; color: var(--text); }

.bubble { max-width: 72%; padding: 14px 18px; border-radius: var(--radius);
          line-height: 1.65; }
.agent .bubble { background: var(--white); border: 1px solid var(--border);
                 border-top-left-radius: 4px; box-shadow: var(--shadow); }
.user  .bubble { background: var(--navy); color: #fff;
                 border-top-right-radius: 4px; }

.bubble .sender { font-size: 11px; font-weight: 700; opacity: .6;
                  margin-bottom: 6px; text-transform: uppercase; letter-spacing: .5px; }
.agent .bubble .sender { color: var(--blue); }
.user  .bubble .sender { color: rgba(255,255,255,.7); }

.bubble .body h1,.bubble .body h2,.bubble .body h3 { margin: 12px 0 6px; font-size: 14px; }
.bubble .body p  { margin-bottom: 8px; }
.bubble .body ul,.bubble .body ol { padding-left: 18px; margin-bottom: 8px; }
.bubble .body li { margin-bottom: 4px; }
.bubble .body strong { font-weight: 600; }
.bubble .body code { background: rgba(0,0,0,.06); padding: 1px 5px; border-radius: 4px;
                     font-size: 12px; }
.user .bubble .body code { background: rgba(255,255,255,.15); }

/* Typing indicator */
.typing-dots { display: flex; gap: 5px; padding: 6px 2px; align-items: center; }
.typing-dots span { width: 7px; height: 7px; background: var(--mid); border-radius: 50%;
                    animation: bounce .9s infinite; }
.typing-dots span:nth-child(2) { animation-delay: .15s; }
.typing-dots span:nth-child(3) { animation-delay: .30s; }
@keyframes bounce { 0%,80%,100%{transform:scale(.7);opacity:.4} 40%{transform:scale(1);opacity:1} }

/* ── Input area ── */
#input-wrap { padding: 16px 24px; border-top: 1px solid var(--border);
              background: var(--white); flex-shrink: 0; }
#input-row  { display: flex; gap: 10px; align-items: flex-end; }
#msg-input  { flex: 1; resize: none; border: 1.5px solid var(--border); border-radius: 10px;
              padding: 10px 14px; font-family: inherit; font-size: 14px; line-height: 1.5;
              outline: none; transition: border-color .2s; max-height: 120px; }
#msg-input:focus { border-color: var(--blue); }
#msg-input:disabled { background: #f9f9f9; color: var(--muted); }

.btn-send  { background: var(--navy); color: #fff; border: none; padding: 10px 20px;
             border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer;
             transition: background .2s; white-space: nowrap; }
.btn-send:hover    { background: var(--blue); }
.btn-send:disabled { background: #9fa8da; cursor: not-allowed; }

.btn-end  { background: transparent; color: var(--muted); border: 1.5px solid var(--border);
            padding: 10px 16px; border-radius: 8px; font-size: 12px; font-weight: 500;
            cursor: pointer; transition: all .2s; white-space: nowrap; }
.btn-end:hover    { border-color: var(--red); color: var(--red); }
.btn-end:disabled { opacity: .4; cursor: not-allowed; }

/* ── Sidebar ── */
#sidebar { width: 340px; flex-shrink: 0; display: flex; flex-direction: column;
           overflow: hidden; background: var(--white); }

/* Context card */
#ctx-card { padding: 20px; border-bottom: 1px solid var(--border); }
#ctx-card h3 { font-size: 11px; font-weight: 700; color: var(--muted);
               text-transform: uppercase; letter-spacing: .6px; margin-bottom: 14px; }
.ctx-row { display: flex; justify-content: space-between; align-items: baseline;
           padding: 5px 0; border-bottom: 1px solid var(--bg); font-size: 13px; }
.ctx-row:last-child { border-bottom: none; }
.ctx-row .label { color: var(--muted); }
.ctx-row .val   { font-weight: 600; color: var(--navy); text-align: right; }

/* Progress */
#progress-card { padding: 20px; border-bottom: 1px solid var(--border); }
#progress-card h3 { font-size: 11px; font-weight: 700; color: var(--muted);
                    text-transform: uppercase; letter-spacing: .6px; margin-bottom: 14px; }
.turn-track { background: var(--bg); border-radius: 10px; height: 6px; overflow: hidden; }
.turn-fill  { background: linear-gradient(90deg, var(--blue), var(--mid));
              height: 100%; border-radius: 10px; transition: width .4s ease; }
#turn-label { font-size: 12px; color: var(--muted); margin-top: 8px; }
#phase-msg  { margin-top: 12px; font-size: 13px; font-weight: 500; color: var(--amber);
              display: flex; align-items: center; gap: 8px; }
.spinner { width: 14px; height: 14px; border: 2px solid var(--border);
           border-top-color: var(--amber); border-radius: 50%;
           animation: spin .7s linear infinite; flex-shrink: 0; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Artifact tabs */
#artifact-card { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.tab-bar { display: flex; border-bottom: 1px solid var(--border); flex-shrink: 0; }
.tab-btn { flex: 1; padding: 11px 4px; border: none; background: transparent;
           font-size: 12px; font-weight: 500; color: var(--muted); cursor: pointer;
           border-bottom: 2px solid transparent; transition: all .2s; }
.tab-btn.active { color: var(--navy); border-bottom-color: var(--navy); font-weight: 700; }
.tab-btn:hover:not(.active) { color: var(--blue); }

.tab-pane { flex: 1; overflow-y: auto; padding: 18px; display: none; font-size: 13px; }
.tab-pane.active { display: block; }
.tab-pane h1,.tab-pane h2 { font-size: 14px; color: var(--navy); margin: 14px 0 6px; }
.tab-pane h3 { font-size: 13px; color: var(--blue); margin: 10px 0 4px; }
.tab-pane p  { line-height: 1.65; margin-bottom: 8px; color: var(--text); }
.tab-pane ul,.tab-pane ol { padding-left: 18px; margin-bottom: 10px; }
.tab-pane li { margin-bottom: 4px; line-height: 1.55; }
.tab-pane table { width: 100%; border-collapse: collapse; font-size: 12px; margin: 10px 0; }
.tab-pane th { background: var(--light); color: var(--navy); text-align: left; padding: 6px 8px; }
.tab-pane td { padding: 5px 8px; border-bottom: 1px solid var(--bg); }
.tab-pane strong { font-weight: 600; }
.tab-pane code { background: var(--bg); padding: 1px 5px; border-radius: 4px; font-size: 11px; }
.tab-pane hr { border: none; border-top: 1px solid var(--border); margin: 12px 0; }

/* Graph tab */
.graph-card { background: var(--bg); border-radius: 10px; padding: 18px; text-align: center;
              border: 1.5px dashed var(--border); }
.graph-card .stats { display: flex; gap: 20px; justify-content: center; margin: 14px 0; }
.graph-stat .n { font-size: 28px; font-weight: 700; color: var(--navy); }
.graph-stat .l { font-size: 11px; color: var(--muted); }
.graph-card .open-btn { background: var(--navy); color: #fff; border: none;
                        padding: 10px 24px; border-radius: 8px; font-size: 13px;
                        font-weight: 600; cursor: pointer; text-decoration: none;
                        display: inline-block; margin-top: 4px; }
.graph-card .open-btn:hover { background: var(--blue); }

.placeholder-art { color: var(--muted); text-align: center; padding: 40px 20px;
                   font-size: 13px; line-height: 1.8; }

/* Checkbox styling for checklist */
.tab-pane input[type=checkbox] { accent-color: var(--navy); margin-right: 6px; }
</style>
</head>
<body>
<div id="app">

  <!-- ── Header ── -->
  <header id="header">
    <div>
      <h1>TTK Agent &mdash; Tech Transfer Knowledge Capture</h1>
      <div class="sub">Pharmaceutical Process Engineering &nbsp;|&nbsp; Scale-Up Support</div>
    </div>
    <div style="display:flex;gap:10px;align-items:center"><div class="badge">Batch __BATCH_ID__</div><a href="/admin" style="color:rgba(255,255,255,.75);font-size:12px;text-decoration:none;border:1px solid rgba(255,255,255,.3);border-radius:6px;padding:4px 10px">Admin &#8599;</a></div>
  </header>

  <!-- ── Body ── -->
  <div id="body">

    <!-- Chat panel -->
    <div id="chat-panel">

      <!-- Welcome screen -->
      <div id="welcome">
        <div class="welcome-card">
          <div class="icon">&#129302;</div>
          <h2>Start Your Knowledge Capture Session</h2>
          <p>The TTK Agent will conduct a structured interview to surface the tacit process
             knowledge from your scale-up experience.</p>
          <p>This session takes approximately <strong>5 minutes</strong>.</p>
          <div class="meta">
            <span class="tag">Batch __BATCH_ID__</span>
            <span class="tag">__PRODUCT__</span>
            <span class="tag">Engineer: __ENGINEER__</span>
          </div>
          <button id="start-btn" onclick="startInterview()">&#9654; &nbsp;Start Interview</button>
        </div>
      </div>

      <!-- Messages -->
      <div id="messages" style="display:none"></div>

      <!-- Input -->
      <div id="input-wrap" style="display:none">
        <div id="input-row">
          <textarea id="msg-input" rows="2"
            placeholder="Type your response and press Enter or click Send..."></textarea>
          <button class="btn-send" id="send-btn" onclick="sendMessage()">Send</button>
          <button class="btn-end"  id="end-btn"  onclick="endEarly()">End</button>
        </div>
      </div>
    </div>

    <!-- Sidebar -->
    <div id="sidebar">

      <!-- Batch context -->
      <div id="ctx-card">
        <h3>Session Context</h3>
        <div class="ctx-row"><span class="label">Batch</span>
                             <span class="val">__BATCH_ID__</span></div>
        <div class="ctx-row"><span class="label">Product</span>
                             <span class="val">__PRODUCT__</span></div>
        <div class="ctx-row"><span class="label">Engineer</span>
                             <span class="val">__ENGINEER__</span></div>
        <div class="ctx-row"><span class="label">Issue</span>
                             <span class="val">Capping &amp; weight variability</span></div>
        <div class="ctx-row"><span class="label">Scale</span>
                             <span class="val">Pilot &#8594; Commercial</span></div>
      </div>

      <!-- Interview progress -->
      <div id="progress-card" style="display:none">
        <h3>Interview Progress</h3>
        <div class="turn-track"><div class="turn-fill" id="turn-fill" style="width:0%"></div></div>
        <div id="turn-label">Turn 0 / __MAX_TURNS__</div>
        <div id="phase-msg" style="display:none">
          <div class="spinner"></div>
          <span id="phase-text"></span>
        </div>
      </div>

      <!-- Artifacts (shown after generation) -->
      <div id="artifact-card" style="display:none">
        <div class="tab-bar">
          <button class="tab-btn active" onclick="showTab('ka')">Knowledge Article</button>
          <button class="tab-btn"        onclick="showTab('cl')">Checklist</button>
          <button class="tab-btn"        onclick="showTab('gr')">Graph</button>
        </div>
        <div id="pane-ka" class="tab-pane active">
          <div class="placeholder-art">Generating Knowledge Article&#8230;</div>
        </div>
        <div id="pane-cl" class="tab-pane">
          <div class="placeholder-art">Generating Checklist&#8230;</div>
        </div>
        <div id="pane-gr" class="tab-pane">
          <div class="placeholder-art">Building Knowledge Graph&#8230;</div>
        </div>
      </div>

    </div><!-- /sidebar -->
  </div><!-- /body -->
</div><!-- /app -->

<script>
// ── State ────────────────────────────────────────────────────────────────────
let ws            = null;
let currentBubble = null;   // DOM element being streamed into
let currentRaw    = "";     // raw markdown accumulator for current agent turn
let agentTyping   = false;
let maxTurns      = __MAX_TURNS__;

// ── WebSocket lifecycle ──────────────────────────────────────────────────────
function startInterview() {
  const btn = document.getElementById("start-btn");
  btn.disabled = true;
  btn.textContent = "Connecting...";

  const sid = crypto.randomUUID();
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws/${sid}`);

  ws.onopen = () => {
    document.getElementById("welcome").style.display = "none";
    document.getElementById("messages").style.display = "flex";
    document.getElementById("input-wrap").style.display = "block";
    document.getElementById("progress-card").style.display = "block";
    disableInput();
    ws.send(JSON.stringify({ type: "start" }));
  };

  ws.onmessage = e => handleMsg(JSON.parse(e.data));

  ws.onerror = () => showSystemMsg("Connection error. Please refresh and try again.", "error");
  ws.onclose = () => { if (agentTyping) showSystemMsg("Connection closed.", "error"); };
}

// ── Message router ───────────────────────────────────────────────────────────
function handleMsg(m) {
  switch (m.type) {

    case "agent_start":
      agentTyping   = true;
      currentRaw    = "";
      currentBubble = addBubble("agent", "TTK Agent");
      currentBubble.querySelector(".body").innerHTML =
        '<div class="typing-dots"><span></span><span></span><span></span></div>';
      scrollBottom();
      break;

    case "agent_token":
      currentRaw += m.text;
      currentBubble.querySelector(".body").textContent = currentRaw;
      scrollBottom();
      break;

    case "agent_done":
      agentTyping = false;
      // Re-render accumulated text as markdown
      currentBubble.querySelector(".body").innerHTML = marked.parse(currentRaw);
      scrollBottom();
      enableInput();
      break;

    case "turn_update":
      updateProgress(m.turn, m.max_turns);
      break;

    case "interview_complete":
      disableInput(true);
      document.getElementById("artifact-card").style.display = "flex";
      showPhase("Generating knowledge artifacts...");
      break;

    case "phase":
      showPhase(m.message, m.label);
      break;

    case "synthesis_done":
      document.getElementById("pane-ka").innerHTML = marked.parse(m.knowledge_article || "");
      // Activate checkboxes in checklist
      let clHtml = marked.parse(m.checklist || "");
      clHtml = clHtml.replace(/\[ \]/g, '<input type="checkbox">');
      clHtml = clHtml.replace(/\[x\]/gi, '<input type="checkbox" checked>');
      document.getElementById("pane-cl").innerHTML = clHtml;
      break;

    case "graph_done":
      document.getElementById("pane-gr").innerHTML = `
        <div class="graph-card">
          <div style="font-size:13px;color:var(--muted);margin-bottom:6px">Knowledge Graph extracted from interview</div>
          <div class="stats">
            <div class="graph-stat"><div class="n">${m.node_count}</div><div class="l">Nodes</div></div>
            <div class="graph-stat"><div class="n">${m.edge_count}</div><div class="l">Edges</div></div>
          </div>
          <a class="open-btn" href="${m.graph_url}" target="_blank">&#128202; &nbsp;Open Interactive Graph</a>
        </div>`;
      break;

    case "all_done":
      hidePhase();
      showSystemMsg("Session complete. All artifacts saved.", "success");
      break;

    case "error":
      showSystemMsg("Error: " + m.message, "error");
      break;
  }
}

// ── Send engineer message ────────────────────────────────────────────────────
function sendMessage() {
  const inp  = document.getElementById("msg-input");
  const text = inp.value.trim();
  if (!text || agentTyping || !ws) return;
  inp.value = "";
  addBubble("user", "__ENGINEER__").querySelector(".body").textContent = text;
  scrollBottom();
  disableInput();
  ws.send(JSON.stringify({ type: "message", text }));
}

function endEarly() {
  if (!ws) return;
  disableInput(true);
  document.getElementById("artifact-card").style.display = "flex";
  showPhase("Generating knowledge artifacts...");
  ws.send(JSON.stringify({ type: "finish_early" }));
}

// ── DOM helpers ──────────────────────────────────────────────────────────────
function addBubble(role, name) {
  const wrap = document.getElementById("messages");
  const row  = document.createElement("div");
  row.className = `msg-row ${role}`;
  const initials = name === "TTK Agent" ? "AI" : name.slice(0, 2).toUpperCase();
  row.innerHTML = `
    <div class="avatar ${role}-av">${initials}</div>
    <div class="bubble">
      <div class="sender">${name}</div>
      <div class="body"></div>
    </div>`;
  wrap.appendChild(row);
  return row;
}

function showSystemMsg(text, kind) {
  const wrap = document.getElementById("messages");
  const el   = document.createElement("div");
  el.style.cssText = `text-align:center;font-size:12px;padding:6px 16px;border-radius:20px;
    margin:4px auto;font-weight:500;
    background:${kind==="error"?"#ffebee":"#e8f5e9"};
    color:${kind==="error"?"#c62828":"#2e7d32"}`;
  el.textContent = text;
  wrap.appendChild(el);
  scrollBottom();
}

function updateProgress(turn, max) {
  const pct = Math.round((turn / max) * 100);
  document.getElementById("turn-fill").style.width  = pct + "%";
  document.getElementById("turn-label").textContent = `Turn ${turn} / ${max}`;
}

function showPhase(msg) {
  const el = document.getElementById("phase-msg");
  document.getElementById("phase-text").textContent = msg;
  el.style.display = "flex";
}
function hidePhase() {
  document.getElementById("phase-msg").style.display = "none";
}

function enableInput() {
  const inp  = document.getElementById("msg-input");
  const send = document.getElementById("send-btn");
  const end  = document.getElementById("end-btn");
  inp.disabled = send.disabled = end.disabled = false;
  inp.focus();
}

function disableInput(permanent = false) {
  const inp  = document.getElementById("msg-input");
  const send = document.getElementById("send-btn");
  const end  = document.getElementById("end-btn");
  inp.disabled = send.disabled = true;
  if (permanent) end.disabled = true;
}

function scrollBottom() {
  const el = document.getElementById("messages");
  el.scrollTop = el.scrollHeight;
}

function showTab(id) {
  ["ka","cl","gr"].forEach(t => {
    document.getElementById(`pane-${t}`).classList.toggle("active", t === id);
    document.querySelectorAll(".tab-btn")[["ka","cl","gr"].indexOf(t)]
      .classList.toggle("active", t === id);
  });
}

// ── Keyboard shortcut: Enter to send, Shift+Enter for newline ────────────────
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("msg-input").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
});
</script>
</body>
</html>"""


# ==============================================================================
#  ADMIN - Knowledge Management Dashboard
# ==============================================================================

import re as _re
from collections import defaultdict as _defaultdict


ADMIN_KA_SYSTEM = """You are a senior pharmaceutical manufacturing knowledge manager.

INPUT: One or more interview transcripts and/or knowledge articles from process engineers
about compression scale-up challenges.

TASK: Write a single, consolidated Knowledge Article that:
  1. Identifies common patterns and recurring root causes across all sessions
  2. Surfaces critical tacit knowledge (undocumented adjustments, operator insights)
  3. Produces authoritative recommendations applicable to future scale-ups
  4. Notes any session-specific findings worth highlighting

OUTPUT FORMAT (markdown):
# Consolidated Knowledge Article
**Sessions analysed:** N  |  **Date:** YYYY-MM-DD  |  **Classification:** Process -- OSD Compression

## Executive Summary
## Recurring Root Causes (ranked by frequency)
## Critical Process Parameters (cross-session comparison table)
## Formulation-Specific Insights
## Operator Tacit Knowledge (undocumented findings)
## Lessons Learned
## Recommendations for Future Scale-Ups"""


ADMIN_CL_SYSTEM = """You are a pharmaceutical manufacturing quality specialist.

INPUT: One or more interview transcripts from process engineers about scale-up events.

TASK: Produce a single, de-duplicated Best Practices Checklist covering ALL sessions.
  - Group by phase: Pre-Scale-Up | Material Release | Equipment Setup | Compression | Documentation
  - Mark CRITICAL items (appear in multiple sessions or caused rejections) with a [CRITICAL] tag
  - Be specific: include parameter values, equipment names, action limits where mentioned
  - Remove redundant items, keeping the most precise version

OUTPUT FORMAT (markdown with - [ ] checkboxes):
# Scale-Up Best Practices -- Consolidated Checklist
**Derived from:** N interview sessions  |  **Date:** YYYY-MM-DD

## Pre-Scale-Up Planning
## Material Release Criteria
## Equipment & Tooling Setup
## Compression Process Controls
## In-Process Monitoring & Escalation
## Knowledge Capture & Documentation"""


ADMIN_GR_SYSTEM = """You are a pharmaceutical knowledge graph specialist.

INPUT: One or more interview transcripts from different scale-up sessions.

TASK: Build ONE unified knowledge graph across ALL sessions.
  - Use node types: Batch, Product, Engineer, Operator, Equipment, Site, Issue,
    Parameter, RootCause, Material, Action, Resolution, Lesson, Observation, Session
  - Add a Session node for each distinct interview (label = batch_timestamp)
  - When the same entity appears in multiple sessions, create ONE node and add
    property "sessions" listing which sessions mention it
  - Add cross-session edges: CONFIRMED_BY, ALSO_OBSERVED_IN, GENERALISES_TO
  - Aim for 20-35 nodes and 25-45 edges across all sessions combined
  - Return ONLY valid JSON:
    {"nodes":[{"id","label","type","properties":{}}],
     "edges":[{"id","from","to","label","properties":{}}],
     "metadata":{"session_count":N,"node_count":N,"edge_count":N}}"""


# ── File utilities ─────────────────────────────────────────────────────────────

def _parse_ts(stem: str) -> str:
    m = _re.search(r'(\d{8}_\d{4})', stem)
    return m.group(1) if m else ""


def scan_sessions() -> list[dict]:
    groups: dict[str, dict] = _defaultdict(lambda: {
        "ts": "", "files": [],
        "has_transcript": False, "has_ka": False,
        "has_checklist": False, "has_graph": False,
    })
    for f in sorted(OUTPUT_DIR.glob("*.*")):
        ts = _parse_ts(f.stem)
        if not ts:
            continue
        g = groups[ts]
        g["ts"] = ts
        g["files"].append(f.name)
        if   f.name.startswith("Transcript"):  g["has_transcript"] = True
        elif f.name.startswith("KA"):          g["has_ka"]         = True
        elif f.name.startswith("Checklist"):   g["has_checklist"]  = True
        elif f.name.endswith(".json") and "Graph" in f.name:
            g["has_graph"] = True
    result = []
    for ts, g in sorted(groups.items(), reverse=True):
        try:
            dt = datetime.strptime(ts, "%Y%m%d_%H%M")
            g["display"] = dt.strftime("%Y-%m-%d  %H:%M")
        except ValueError:
            g["display"] = ts
        result.append(g)
    return result


def load_all_transcripts() -> str:
    txts = sorted(OUTPUT_DIR.glob("Transcript_*.txt"))
    if not txts:
        return ""
    parts = []
    for i, p in enumerate(txts, 1):
        parts.append(f"\n{'='*70}\n  SESSION {i}: {p.name}\n{'='*70}\n")
        parts.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def load_existing_artifacts() -> str:
    kas = sorted(OUTPUT_DIR.glob("KA_*.md"))
    if not kas:
        return ""
    parts = ["--- PREVIOUSLY GENERATED KNOWLEDGE ARTICLES ---"]
    for p in kas:
        parts.append(f"\n[From {p.name}]\n")
        parts.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def merge_graph_jsons() -> dict:
    jsons = sorted(OUTPUT_DIR.glob("KnowledgeGraph_*.json"))
    all_nodes: dict[str, dict] = {}
    all_edges: dict[str, dict] = {}
    session_count = 0

    for p in jsons:
        try:
            g = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        session_count += 1
        src = p.stem
        for n in g.get("nodes", []):
            nid = n["id"]
            if nid in all_nodes:
                existing = all_nodes[nid]
                prev = existing.get("properties", {}).get("sessions", src)
                if src not in prev:
                    existing.setdefault("properties", {})["sessions"] = f"{prev}, {src}"
                    freq = int(existing["properties"].get("frequency", "1")) + 1
                    existing["properties"]["frequency"] = str(freq)
            else:
                node = dict(n)
                node.setdefault("properties", {})["sessions"]  = src
                node.setdefault("properties", {})["frequency"] = "1"
                all_nodes[nid] = node

        for e in g.get("edges", []):
            eid = e.get("id") or f"{e['from']}__{e['label']}__{e['to']}"
            if eid not in all_edges:
                edge = dict(e)
                edge.setdefault("id", eid)
                all_edges[eid] = edge

    nodes = list(all_nodes.values())
    edges = [e for e in all_edges.values()
             if e["from"] in all_nodes and e["to"] in all_nodes]
    return {
        "nodes": nodes, "edges": edges,
        "metadata": {
            "session_count": session_count,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
    }


def _load_transcript_text(ts: str) -> str:
    matches = list(OUTPUT_DIR.glob(f"Transcript_*{ts}*.txt"))
    return matches[0].read_text(encoding="utf-8", errors="replace") if matches else ""


# ── Admin HTML ─────────────────────────────────────────────────────────────────

_ADMIN_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TTK Admin | Knowledge Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
:root {
  --navy: #0d1b4b; --blue: #3949ab; --mid: #5c6bc0; --light: #e8eaf6;
  --bg: #f0f2f8; --white: #ffffff; --border: #dde1f0; --text: #1c1e2e;
  --muted: #6b7280; --green: #2e7d32; --amber: #f57f17; --red: #c62828;
  --teal: #00695c; --radius: 10px; --shadow: 0 2px 12px rgba(13,27,75,.10);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; font-family: 'Inter', system-ui, sans-serif;
             background: var(--bg); color: var(--text); font-size: 14px; }

#app    { display: flex; flex-direction: column; height: 100vh; }
#header { background: linear-gradient(135deg, #0d1b4b 0%, #1a237e 100%);
          color: #fff; padding: 0 24px; height: 56px;
          display: flex; align-items: center; justify-content: space-between;
          flex-shrink: 0; box-shadow: 0 2px 8px rgba(0,0,0,.25); }
#header h1  { font-size: 16px; font-weight: 700; letter-spacing: .3px; }
#header .sub { font-size: 12px; opacity: .75; margin-top: 1px; }
.hdr-link { color: rgba(255,255,255,.75); font-size: 12px; text-decoration: none;
            border: 1px solid rgba(255,255,255,.3); border-radius: 6px;
            padding: 4px 10px; transition: all .2s; }
.hdr-link:hover { background: rgba(255,255,255,.15); color: #fff; }

#body { display: flex; flex: 1; overflow: hidden; }

/* ── Sidebar ── */
#sidebar { width: 240px; flex-shrink: 0; background: var(--white);
           border-right: 1px solid var(--border);
           display: flex; flex-direction: column; overflow: hidden; }
#sidebar-hdr { padding: 16px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
#sidebar-hdr h2 { font-size: 11px; font-weight: 700; color: var(--muted);
                  text-transform: uppercase; letter-spacing: .6px; }
#session-list { flex: 1; overflow-y: auto; padding: 8px; }
.session-row { padding: 10px 12px; border-radius: 8px; cursor: pointer;
               margin-bottom: 4px; transition: background .15s;
               border: 1px solid transparent; }
.session-row:hover  { background: var(--light); }
.session-row.active { background: var(--light); border-color: var(--mid); }
.session-ts { font-size: 12px; font-weight: 600; color: var(--navy); }
.session-badges { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 5px; }
.badge { font-size: 10px; font-weight: 600; padding: 2px 7px; border-radius: 10px; }
.badge-tx { background: #e3f2fd; color: #1565c0; }
.badge-ka { background: #e8f5e9; color: #2e7d32; }
.badge-gr { background: #fff8e1; color: #f57f17; }
.badge-cl { background: #f3e5f5; color: #6a1b9a; }
.no-sessions { color: var(--muted); font-size: 12px; padding: 20px; text-align: center;
               line-height: 1.8; }

/* ── Main ── */
#main { flex: 1; display: flex; flex-direction: column; overflow: hidden;
        padding: 20px; gap: 14px; }

/* ── Action cards ── */
#actions { display: flex; gap: 14px; flex-shrink: 0; }
.action-card { flex: 1; background: var(--white); border-radius: var(--radius);
               box-shadow: var(--shadow); padding: 18px;
               border-left: 4px solid transparent; }
.action-card.ka { border-left-color: var(--blue); }
.action-card.cl { border-left-color: var(--teal); }
.action-card.gr { border-left-color: var(--amber); }
.action-card h3 { font-size: 13px; font-weight: 700; margin-bottom: 6px; }
.action-card p  { font-size: 12px; color: var(--muted); line-height: 1.5; margin-bottom: 14px; }
.action-btns { display: flex; gap: 6px; flex-wrap: wrap; }
.action-btn { border: none; border-radius: 7px; padding: 9px 16px; font-size: 12px;
              font-weight: 600; cursor: pointer; transition: all .2s; color: #fff; }
.action-btn.blue  { background: var(--blue); }
.action-btn.blue:hover  { background: var(--navy); }
.action-btn.teal  { background: var(--teal); }
.action-btn.teal:hover  { background: #004d40; }
.action-btn.amber { background: var(--amber); }
.action-btn.amber:hover { background: #e65100; }
.action-btn.outline { background: transparent; color: var(--muted);
                      border: 1.5px solid var(--border); }
.action-btn.outline:hover { border-color: var(--amber); color: var(--amber); }
.action-btn:disabled { opacity: .45; cursor: not-allowed; }

/* ── Status bar ── */
#status-bar { font-size: 12px; color: var(--muted);
              display: flex; align-items: center; gap: 8px;
              flex-shrink: 0; min-height: 18px; }
.spinner { width: 13px; height: 13px; border: 2px solid var(--border);
           border-top-color: var(--blue); border-radius: 50%;
           animation: spin .7s linear infinite; flex-shrink: 0; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Results ── */
#results { flex: 1; background: var(--white); border-radius: var(--radius);
           box-shadow: var(--shadow); display: flex; flex-direction: column;
           overflow: hidden; }
.tab-bar { display: flex; border-bottom: 1px solid var(--border); flex-shrink: 0; }
.tab-btn { flex: 1; padding: 12px 4px; border: none; background: transparent;
           font-size: 12px; font-weight: 500; color: var(--muted); cursor: pointer;
           border-bottom: 2px solid transparent; transition: all .2s; }
.tab-btn.active { color: var(--navy); border-bottom-color: var(--navy); font-weight: 700; }
.tab-btn:hover:not(.active) { color: var(--blue); }
.tab-pane { flex: 1; overflow-y: auto; padding: 20px; display: none;
            font-size: 13px; line-height: 1.65; }
.tab-pane.active { display: block; }
.tab-pane h1,.tab-pane h2 { font-size: 15px; color: var(--navy); margin: 16px 0 8px; }
.tab-pane h3 { font-size: 13px; color: var(--blue); margin: 12px 0 5px; }
.tab-pane p  { margin-bottom: 8px; }
.tab-pane ul,.tab-pane ol { padding-left: 20px; margin-bottom: 10px; }
.tab-pane li { margin-bottom: 4px; }
.tab-pane table { width: 100%; border-collapse: collapse; font-size: 12px; margin: 10px 0; }
.tab-pane th { background: var(--light); color: var(--navy);
               text-align: left; padding: 7px 10px; }
.tab-pane td { padding: 6px 10px; border-bottom: 1px solid var(--bg); }
.tab-pane strong { font-weight: 600; }
.tab-pane code { background: var(--bg); padding: 1px 5px;
                 border-radius: 4px; font-size: 11px; }
.tab-pane hr { border: none; border-top: 1px solid var(--border); margin: 14px 0; }
.tab-pane input[type=checkbox] { accent-color: var(--navy); margin-right: 7px; }
.cursor { display: inline-block; width: 2px; height: 14px; background: var(--navy);
          vertical-align: middle; animation: blink .8s step-end infinite; margin-left: 2px; }
@keyframes blink { 50% { opacity: 0; } }
.placeholder { color: var(--muted); text-align: center; padding: 60px 20px;
               font-size: 13px; line-height: 1.8; }

/* ── Graph card ── */
.graph-card { background: var(--bg); border-radius: 10px; padding: 28px;
              text-align: center; border: 1.5px dashed var(--border);
              max-width: 440px; margin: 24px auto; }
.graph-stats { display: flex; gap: 28px; justify-content: center; margin: 16px 0; }
.graph-stat .n { font-size: 32px; font-weight: 700; color: var(--navy); }
.graph-stat .l { font-size: 11px; color: var(--muted); }
.open-btn { background: var(--navy); color: #fff; border: none; padding: 10px 24px;
            border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer;
            text-decoration: none; display: inline-block; transition: background .2s; }
.open-btn:hover { background: var(--blue); }

/* ── Transcript modal ── */
#modal-overlay { display: none; position: fixed; inset: 0;
                 background: rgba(0,0,0,.45); z-index: 100;
                 align-items: center; justify-content: center; }
#modal-overlay.open { display: flex; }
#modal-box { background: var(--white); border-radius: var(--radius);
             width: 720px; max-height: 80vh;
             display: flex; flex-direction: column;
             box-shadow: 0 8px 32px rgba(0,0,0,.2); }
#modal-hdr { padding: 16px 20px; border-bottom: 1px solid var(--border);
             display: flex; justify-content: space-between; align-items: center;
             flex-shrink: 0; }
#modal-hdr h3 { font-size: 14px; font-weight: 700; color: var(--navy); }
#modal-close { background: none; border: none; font-size: 22px; cursor: pointer;
               color: var(--muted); line-height: 1; padding: 0 4px; }
#modal-close:hover { color: var(--text); }
#modal-body { flex: 1; overflow-y: auto; padding: 20px; }
#modal-pre { font-size: 12px; font-family: 'Consolas', monospace; line-height: 1.7;
             white-space: pre-wrap; color: var(--text); }
</style>
</head>
<body>
<div id="app">

  <header id="header">
    <div>
      <h1>Knowledge Management Dashboard</h1>
      <div class="sub">Admin &nbsp;|&nbsp; Pharmaceutical Tech Transfer</div>
    </div>
    <a href="/" class="hdr-link">&#8592; Engineer View</a>
  </header>

  <div id="body">

    <!-- Sidebar: session list -->
    <div id="sidebar">
      <div id="sidebar-hdr"><h2>Past Sessions</h2></div>
      <div id="session-list"><p class="no-sessions">Connecting...</p></div>
    </div>

    <!-- Main content -->
    <div id="main">

      <!-- Action cards -->
      <div id="actions">
        <div class="action-card ka">
          <h3>Knowledge Article</h3>
          <p>Consolidated article from all interview transcripts, surfacing patterns and tacit knowledge across sessions.</p>
          <div class="action-btns">
            <button class="action-btn blue" id="btn-ka" onclick="genKA()">Generate Article</button>
          </div>
        </div>
        <div class="action-card cl">
          <h3>Best Practices Checklist</h3>
          <p>De-duplicated checklist by process phase, marking critical items that appear across multiple sessions.</p>
          <div class="action-btns">
            <button class="action-btn teal" id="btn-cl" onclick="genCL()">Generate Checklist</button>
          </div>
        </div>
        <div class="action-card gr">
          <h3>Knowledge Graph</h3>
          <p>Unified graph merging entities and relationships from all sessions into one interactive visualisation.</p>
          <div class="action-btns">
            <button class="action-btn amber"   id="btn-gr-merge" onclick="genGraph('merge')">Merge Sessions</button>
            <button class="action-btn outline" id="btn-gr-llm"   onclick="genGraph('llm')">Re-extract (LLM)</button>
          </div>
        </div>
      </div>

      <!-- Status bar -->
      <div id="status-bar">
        <span id="status-text">Ready &mdash; select an action above or click a session to view its transcript.</span>
      </div>

      <!-- Results tabs -->
      <div id="results">
        <div class="tab-bar">
          <button class="tab-btn active" onclick="showTab('ka')">Knowledge Article</button>
          <button class="tab-btn"        onclick="showTab('cl')">Best Practices</button>
          <button class="tab-btn"        onclick="showTab('gr')">Knowledge Graph</button>
        </div>
        <div id="pane-ka" class="tab-pane active">
          <p class="placeholder">Click <strong>Generate Article</strong> to create a consolidated knowledge article from all sessions.</p>
        </div>
        <div id="pane-cl" class="tab-pane">
          <p class="placeholder">Click <strong>Generate Checklist</strong> to create a best-practices checklist from all sessions.</p>
        </div>
        <div id="pane-gr" class="tab-pane">
          <p class="placeholder">Click <strong>Merge Sessions</strong> to programmatically combine all session graphs, or <strong>Re-extract (LLM)</strong> to re-analyse from scratch.</p>
        </div>
      </div>

    </div><!-- /main -->
  </div><!-- /body -->
</div><!-- /app -->

<!-- Transcript modal -->
<div id="modal-overlay" onclick="closeModal(event)">
  <div id="modal-box">
    <div id="modal-hdr">
      <h3 id="modal-title">Transcript</h3>
      <button id="modal-close" onclick="closeModal()">&#215;</button>
    </div>
    <div id="modal-body"><pre id="modal-pre">Loading...</pre></div>
  </div>
</div>

<script>
// ── WebSocket ─────────────────────────────────────────────────────────────────
let ws          = null;
let streamTarget = null;
let streamRaw    = "";

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/admin/ws`);
  ws.onopen    = () => { ws.send(JSON.stringify({ type: "list_sessions" })); };
  ws.onmessage = e  => handleMsg(JSON.parse(e.data));
  ws.onerror   = ()  => setStatus("WebSocket error. Reload to reconnect.", true);
  ws.onclose   = ()  => { ws = null; setTimeout(connect, 3000); };
}

// ── Message handler ───────────────────────────────────────────────────────────
function handleMsg(m) {
  switch (m.type) {

    case "sessions":
      renderSessions(m.data);
      setStatus(`${m.data.length} session${m.data.length !== 1 ? "s" : ""} found. Click a session to view its transcript.`);
      break;

    case "transcript_content":
      document.getElementById("modal-pre").textContent = m.text || "(empty)";
      break;

    case "progress":
      setStatus(m.message);
      break;

    case "gen_start":
      streamTarget = m.target;
      streamRaw    = "";
      showTab(m.target);
      document.getElementById(`pane-${m.target}`).innerHTML =
        '<span class="cursor"></span>';
      break;

    case "gen_token":
      if (m.target === streamTarget) {
        streamRaw += m.text;
        const p = document.getElementById(`pane-${m.target}`);
        p.innerHTML = streamRaw.replace(/</g,"&lt;") + '<span class="cursor"></span>';
        p.scrollTop = p.scrollHeight;
      }
      break;

    case "gen_done": {
      streamTarget = null;
      const pane = document.getElementById(`pane-${m.target}`);
      let html = marked.parse(m.content || streamRaw || "");
      if (m.target === "cl") {
        html = html.replace(/\[ \]/g,  '<input type="checkbox">');
        html = html.replace(/\[x\]/gi, '<input type="checkbox" checked>');
      }
      pane.innerHTML = html;
      enableAllBtns();
      const labels = { ka: "Knowledge Article", cl: "Checklist", gr: "Graph" };
      setStatus(`${labels[m.target] || m.target} generated successfully.`);
      break;
    }

    case "graph_ready":
      showTab("gr");
      document.getElementById("pane-gr").innerHTML = `
        <div class="graph-card">
          <div style="font-size:13px;color:var(--muted);margin-bottom:6px">Unified Knowledge Graph</div>
          <div class="graph-stats">
            <div class="graph-stat"><div class="n">${m.session_count}</div><div class="l">Sessions</div></div>
            <div class="graph-stat"><div class="n">${m.node_count}</div><div class="l">Nodes</div></div>
            <div class="graph-stat"><div class="n">${m.edge_count}</div><div class="l">Edges</div></div>
          </div>
          <a class="open-btn" href="${m.url}" target="_blank">&#128202;&nbsp; Open Interactive Graph</a>
        </div>`;
      enableAllBtns();
      setStatus(`Graph built: ${m.node_count} nodes, ${m.edge_count} edges across ${m.session_count} session(s).`);
      break;

    case "error":
      setStatus("Error: " + m.message, true);
      enableAllBtns();
      break;
  }
}

// ── Session list ──────────────────────────────────────────────────────────────
function renderSessions(sessions) {
  const el = document.getElementById("session-list");
  if (!sessions || !sessions.length) {
    el.innerHTML = '<p class="no-sessions">No sessions found.<br>Run an interview first.</p>';
    return;
  }
  el.innerHTML = sessions.map(s => `
    <div class="session-row" onclick="viewTranscript('${s.ts}', this)"
         title="Click to view transcript">
      <div class="session-ts">${s.display}</div>
      <div class="session-badges">
        ${s.has_transcript ? '<span class="badge badge-tx">TX</span>' : ""}
        ${s.has_ka         ? '<span class="badge badge-ka">KA</span>'  : ""}
        ${s.has_checklist  ? '<span class="badge badge-cl">CL</span>'  : ""}
        ${s.has_graph      ? '<span class="badge badge-gr">GR</span>'  : ""}
      </div>
    </div>`).join("");
}

// ── Transcript modal ──────────────────────────────────────────────────────────
function viewTranscript(ts, row) {
  document.querySelectorAll(".session-row").forEach(r => r.classList.remove("active"));
  row.classList.add("active");
  document.getElementById("modal-title").textContent = "Transcript — " + ts;
  document.getElementById("modal-pre").textContent   = "Loading...";
  document.getElementById("modal-overlay").classList.add("open");
  if (ws) ws.send(JSON.stringify({ type: "view_transcript", ts }));
}

function closeModal(e) {
  if (!e || e.target === document.getElementById("modal-overlay") ||
      e.currentTarget === document.getElementById("modal-close")) {
    document.getElementById("modal-overlay").classList.remove("open");
  }
}

// ── Actions ───────────────────────────────────────────────────────────────────
function genKA() {
  if (!ws) return;
  disableAllBtns();
  setStatus("Generating Knowledge Article...");
  showTab("ka");
  ws.send(JSON.stringify({ type: "gen_ka" }));
}

function genCL() {
  if (!ws) return;
  disableAllBtns();
  setStatus("Generating Best Practices Checklist...");
  showTab("cl");
  ws.send(JSON.stringify({ type: "gen_cl" }));
}

function genGraph(mode) {
  if (!ws) return;
  disableAllBtns();
  setStatus(mode === "merge" ? "Merging session graphs..." : "Re-extracting graph with LLM...");
  showTab("gr");
  ws.send(JSON.stringify({ type: "gen_graph", mode }));
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function showTab(id) {
  ["ka","cl","gr"].forEach((t, i) => {
    document.getElementById(`pane-${t}`).classList.toggle("active", t === id);
    document.querySelectorAll(".tab-btn")[i].classList.toggle("active", t === id);
  });
}

function setStatus(msg, isError = false) {
  const el = document.getElementById("status-bar");
  el.innerHTML = isError
    ? `<span style="color:var(--red)">${msg}</span>`
    : `<span id="status-text">${msg}</span>`;
}

function disableAllBtns() {
  ["btn-ka","btn-cl","btn-gr-merge","btn-gr-llm"].forEach(id => {
    const b = document.getElementById(id);
    if (b) b.disabled = true;
  });
  document.getElementById("status-bar").innerHTML =
    '<div class="spinner"></div><span>Working&hellip;</span>';
}

function enableAllBtns() {
  ["btn-ka","btn-cl","btn-gr-merge","btn-gr-llm"].forEach(id => {
    const b = document.getElementById(id);
    if (b) b.disabled = false;
  });
}

connect();
</script>
</body>
</html>"""


# ── Admin WebSocket handler ────────────────────────────────────────────────────

@app.websocket("/admin/ws")
async def admin_ws(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data   = await ws.receive_json()
            action = data.get("type")

            if action == "list_sessions":
                await ws.send_json({"type": "sessions", "data": scan_sessions()})

            elif action == "view_transcript":
                txt = _load_transcript_text(data.get("ts", ""))
                await ws.send_json({"type": "transcript_content", "text": txt})

            elif action == "gen_ka":
                corpus = load_all_transcripts()
                extras = load_existing_artifacts()
                if not corpus:
                    await ws.send_json({"type": "error",
                                        "message": "No interview transcripts found in ttk_output/."})
                    continue
                combined = corpus + ("\n\n" + extras if extras else "")
                await ws.send_json({"type": "gen_start", "target": "ka"})
                full = ""
                async with aclient.messages.stream(
                    model=MODEL, max_tokens=TOKEN_LIMIT,
                    system=ADMIN_KA_SYSTEM,
                    messages=[{"role": "user", "content":
                        f"Generate a consolidated knowledge article from:\n\n{combined}"}],
                ) as stream:
                    async for chunk in stream.text_stream:
                        full += chunk
                        await ws.send_json({"type": "gen_token", "target": "ka", "text": chunk})
                ts = datetime.now().strftime("%Y%m%d_%H%M")
                (OUTPUT_DIR / f"Admin_KA_{ts}.md").write_text(full, encoding="utf-8")
                await ws.send_json({"type": "gen_done", "target": "ka", "content": full})

            elif action == "gen_cl":
                corpus = load_all_transcripts()
                if not corpus:
                    await ws.send_json({"type": "error",
                                        "message": "No interview transcripts found in ttk_output/."})
                    continue
                await ws.send_json({"type": "gen_start", "target": "cl"})
                full = ""
                async with aclient.messages.stream(
                    model=MODEL, max_tokens=TOKEN_LIMIT,
                    system=ADMIN_CL_SYSTEM,
                    messages=[{"role": "user", "content":
                        f"Generate a consolidated best-practices checklist from:\n\n{corpus}"}],
                ) as stream:
                    async for chunk in stream.text_stream:
                        full += chunk
                        await ws.send_json({"type": "gen_token", "target": "cl", "text": chunk})
                ts = datetime.now().strftime("%Y%m%d_%H%M")
                (OUTPUT_DIR / f"Admin_Checklist_{ts}.md").write_text(full, encoding="utf-8")
                await ws.send_json({"type": "gen_done", "target": "cl", "content": full})

            elif action == "gen_graph":
                mode = data.get("mode", "merge")
                ts   = datetime.now().strftime("%Y%m%d_%H%M")

                if mode == "merge":
                    await ws.send_json({"type": "progress",
                                        "message": "Merging existing session graphs..."})
                    gdata = merge_graph_jsons()
                else:
                    corpus = load_all_transcripts()
                    if not corpus:
                        await ws.send_json({"type": "error", "message": "No transcripts found."})
                        continue
                    await ws.send_json({"type": "gen_start", "target": "gr"})
                    raw = ""
                    async with aclient.messages.stream(
                        model=MODEL, max_tokens=TOKEN_LIMIT,
                        system=ADMIN_GR_SYSTEM,
                        messages=[{"role": "user", "content":
                            f"Build a unified knowledge graph from ALL sessions:\n\n{corpus}\n\n"
                            "Return ONLY the JSON object."}],
                    ) as stream:
                        async for chunk in stream.text_stream:
                            raw += chunk
                            await ws.send_json({"type": "gen_token", "target": "gr", "text": "."})
                    try:
                        gdata = parse_json(raw)
                    except Exception:
                        gdata = merge_graph_jsons()

                gdata.setdefault("metadata", {}).update({
                    "generated":  datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "node_count": len(gdata.get("nodes", [])),
                    "edge_count": len(gdata.get("edges", [])),
                })

                html_name = f"Admin_Graph_{ts}.html"
                json_name = f"Admin_Graph_{ts}.json"
                (OUTPUT_DIR / html_name).write_text(
                    _build_graph_html(gdata), encoding="utf-8")
                (OUTPUT_DIR / json_name).write_text(
                    json.dumps(gdata, indent=2, ensure_ascii=False), encoding="utf-8")

                await ws.send_json({
                    "type":          "graph_ready",
                    "url":           f"/output/{html_name}",
                    "node_count":    gdata["metadata"]["node_count"],
                    "edge_count":    gdata["metadata"]["edge_count"],
                    "session_count": gdata["metadata"].get("session_count", 1),
                })

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await ws.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass


@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    return HTMLResponse(_ADMIN_HTML)
