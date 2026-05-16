# CLAUDE.md — Tech Transfer Knowledge (TTK) Companion Agent Pipeline

## Project Overview

This system captures tacit process engineering knowledge during tech transfers (pilot → commercial scale), structures it into reusable artifacts, and stores it in a queryable knowledge graph. It is composed of two pipelines: **Interview Pipeline** and **Admin Pipeline**.

---

## Architecture

```
Interview Pipeline
├── TTK Interview AI Agent
├── Knowledge Synthesis AI Agent
└── Knowledge Graph Agent

Admin Pipeline
├── Admin Knowledge Article Agent
├── Admin Checklist Agent
└── Admin Graph Agent
```

---

## Interview Pipeline

### 1. TTK Interview AI Agent

**Role:** Conversational agent that elicits tacit knowledge from the Process Engineer (e.g., Schulz) following a deviation or batch event.

**Responsibilities:**
- Detect batch deviation events (e.g., tablet rejection, capping, weight variability)
- Initiate structured dialog with the engineer
- Ask open-ended, then focused questions:
  - What happened? (free description)
  - Classification prompts (substance class, dosage form, equipment type, unit operation, deviation type/subtype, ICH Q9 risk level)
  - Contributing factor identification
  - Corrective/mitigation actions taken
  - Resolution status and residual risks
- Present parameter comparison tables (pilot vs. commercial) when available
- Offer output format choice: Knowledge Article | Checklist | Both
- Confirm all extracted data with the engineer before handoff

**Prompt Behavior:**
- Use EU SPOR referential for dosage form classification
- Use ICH Q9 for risk classification
- Do NOT fabricate classifications — always confirm with engineer
- Play back classifications before proceeding
- Ask one question at a time; do not overwhelm the engineer

**Handoff Trigger:**
- Engineer confirms classification and contributing factors
- Agent passes structured interview JSON to Knowledge Synthesis AI Agent

**Input:** Batch ID, product name, event description (free text)
**Output:** Structured Interview JSON (see schema below)

---

### 2. Knowledge Synthesis AI Agent

**Role:** Converts the structured interview output into a formatted Knowledge Article and/or Checklist per the enterprise template.

**Responsibilities:**
- Parse the Interview JSON from TTK Interview Agent
- Populate the Knowledge Article template:
  - Title
  - Context `<<>>`
  - Trigger Condition `<<>>`
  - Observed Impact `<<>>`
  - Suspected Root Cause `<<>>`
  - Effective Mitigation `<<>>`
  - Recommended Future Controls `<<>>`
  - Knowledge Classification tags (substance class, dosage form, operation, scale, process robustness)
- Generate Compression Scale-Up Risk Verification Checklist:
  - Compression Speed Assessment
  - Granule Physical Property Assessment
  - Environmental Condition Verification
  - Equipment Scale Dependency Review
  - Process Monitoring Readiness
  - Risk Mitigation Preparedness
- Present both artifacts to engineer for review and confirmation
- On confirmation, trigger Admin Pipeline actions

**Prompt Behavior:**
- Never infer data not provided by the engineer
- Use `<<>>` placeholders only where engineer input is pending
- Checklist items must be phrased as verifiable Yes/No questions
- Classify knowledge tags from controlled vocabulary only

**Input:** Structured Interview JSON
**Output:** Knowledge Article (Markdown/JSON), Checklist (Markdown/JSON)

---

### 3. Knowledge Graph Agent

**Role:** Maps synthesized knowledge entities and relationships into a structured knowledge graph for retrieval and future inference.

**Responsibilities:**
- Extract entities: Product, Batch, Site, Process Parameter, Equipment, Deviation, Root Cause, Mitigation, Engineer
- Extract relationships:
  - `Batch → experienced → Deviation`
  - `Deviation → caused_by → RootCause`
  - `RootCause → mitigated_by → Mitigation`
  - `Parameter → changed_between → [PilotSite, CommercialSite]`
  - `KnowledgeArticle → linked_to → Batch`
- Store graph nodes and edges in the enterprise knowledge graph
- Link Knowledge Article and Checklist nodes to the graph
- Flag parameters that appear as risk factors across multiple batches (cross-batch risk signal)

**Prompt Behavior:**
- Use canonical entity identifiers (Batch ID, Product INN, Site Code)
- Do not duplicate nodes — resolve against existing graph before inserting
- Emit confidence scores for inferred relationships
- Support SPARQL or Cypher query interface

**Input:** Knowledge Article JSON + Checklist JSON
**Output:** Graph triples (subject → predicate → object), updated knowledge graph

---

## Admin Pipeline

### 4. Admin Knowledge Article Agent

**Role:** Manages the lifecycle of Knowledge Articles in the enterprise knowledge base.

**Responsibilities:**
- Receive confirmed Knowledge Article from Knowledge Synthesis Agent
- Validate completeness against template schema (all `<<>>` resolved)
- Assign unique Article ID and version
- Save to enterprise knowledge base
- Notify downstream teams (e.g., formulation development) per engineer instruction
- Support actions: Save | Archive | Link to CPV Risk Model | Notify Teams
- Maintain audit trail: author, reviewer, timestamp, batch reference

**Prompt Behavior:**
- Reject incomplete articles (unresolved `<<>>` fields)
- Always confirm save action before committing
- Log notification recipients and timestamp

**Input:** Knowledge Article JSON (confirmed)
**Output:** Saved article record, notification receipt, audit log entry

---

### 5. Admin Checklist Agent

**Role:** Manages scale-up risk verification checklists as reusable, version-controlled assets.

**Responsibilities:**
- Receive confirmed Checklist from Knowledge Synthesis Agent
- Assign Checklist ID, version, and product/process scope
- Publish as a future scale-up checklist item (linked to process, site, dosage form)
- Enable checklist assignment to upcoming tech transfer projects
- Track checklist completion status per batch/project
- Support adding new items from lessons learned
- Merge duplicate checklist items across articles when identical

**Prompt Behavior:**
- Checklist items must remain in Yes/No verifiable format
- Do not auto-approve items — engineer sign-off required
- Support checklist versioning on every edit

**Input:** Checklist JSON (confirmed)
**Output:** Published checklist, version record, assignment log

---

### 6. Admin Graph Agent

**Role:** Governs the integrity, maintenance, and querying of the enterprise knowledge graph.

**Responsibilities:**
- Merge incoming graph triples from Knowledge Graph Agent into the master graph
- Deduplicate nodes and reconcile entity aliases
- Run cross-batch risk signal detection (parameters flagged in ≥2 deviations)
- Link graph nodes to CPV risk model entries
- Expose query interface for downstream agents and dashboards
- Generate graph health reports: orphan nodes, unlinked articles, low-confidence edges
- Support admin actions: Link to CPV | Merge Nodes | Archive Node | Export Subgraph

**Prompt Behavior:**
- Never overwrite existing confirmed relationships without versioning
- Flag low-confidence inferred edges for human review
- All destructive operations (delete/merge) require admin confirmation

**Input:** Graph triples from Knowledge Graph Agent
**Output:** Updated master graph, risk signal alerts, query results

---

## Structured Interview JSON Schema

```json
{
  "batch_id": "SUP30498",
  "product": "Enalapril",
  "substance_class": "ACE Inhibitor",
  "dosage_form": "Oral Solid Dosage",
  "site": "Commercial",
  "engineer": "Schulz",
  "event_description": "Intermittent tablet capping after ~45 min into compression run",
  "classification": {
    "equipment_type": "",
    "unit_operation": "Compression",
    "deviation_type": "",
    "deviation_subtype": "",
    "ich_q9_risk_level": ""
  },
  "parameters": {
    "compression_speed": { "pilot": "45 rpm", "commercial": "72 rpm" },
    "feed_frame_speed":  { "pilot": "20 rpm", "commercial": "35 rpm" },
    "relative_humidity": { "pilot": "32%",    "commercial": "24%" },
    "granule_lod":       { "pilot": "1.8%",   "commercial": "1.2%" }
  },
  "contributing_factors": ["Reduced granule moisture", "Increased compression speed"],
  "mitigation": "Reduced speed to 58 rpm; increased granule moisture target to 1.8%",
  "resolution_status": "Partial — pilot study initiated",
  "output_format": "Checklist",
  "admin_actions": ["save_to_kb", "create_checklist_item", "notify_formulation_team"]
}
```

---

## Agent Communication Protocol

```
TTK Interview Agent
    → [Interview JSON] →
Knowledge Synthesis Agent
    → [Article JSON + Checklist JSON] →
        ├── Knowledge Graph Agent → Admin Graph Agent
        ├── Admin Knowledge Article Agent
        └── Admin Checklist Agent
```

All inter-agent messages must include:

| Field | Description |
|---|---|
| `agent_id` | Sender agent identifier |
| `target_agent_id` | Receiver agent identifier |
| `payload_type` | `interview_json` \| `article_json` \| `checklist_json` \| `graph_triples` |
| `confirmation_status` | `engineer_confirmed: true/false` |
| `timestamp` | ISO 8601 UTC timestamp |

---

## Guardrails & Compliance

- All classifications must reference controlled vocabularies: EU SPOR, ICH Q9, Drug Information for the Health Care Profession
- No article or checklist is published without engineer confirmation
- All agent actions are logged for GxP audit trail
- PII (engineer names) handled per data privacy policy
- Graph agent must version-control all node/edge mutations

---

## Implementation Notes

- **Framework:** FastAPI + WebSocket (async streaming)
- **LLM:** Claude (Anthropic) via `AsyncAnthropic` client
- **Storage:** SQLite (`ttk_output/ttk_knowledge.db`) — sessions, messages, artifacts, graph nodes/edges
- **Visualisation:** vis-network v9.1.9 (CDN) — interactive graph HTML
- **Serving:** uvicorn + ngrok tunnel (`knowledge.ngrok-free.app`)
- **Key files:**
  - `app.py` — FastAPI server, all WebSocket handlers, HTML templates
  - `database.py` — SQLite schema, read/write helpers, graph merge queries
  - `ttk_agent.py` — CLI agent, system prompts, graph HTML builder
  - `ttk_output/ttk_knowledge.db` — all persisted session data

---

## Testing Notes (R&D/QA)

- **Happy path:** full interview → synthesis → graph → admin save
- **Partial resolution:** article with unresolved `<<>>` fields (should be rejected by Admin Article Agent)
- **Cross-batch signal:** inject 2 batches with same root cause → verify graph agent flags risk signal
- **Engineer rejection flow:** engineer declines classification → agent re-prompts
- **Admin action subsets:** engineer selects options 1, 3, 4 only → verify option 2 (CPV link) is skipped
- **Checklist deduplication:** identical checklist item from two articles → single canonical item in graph
