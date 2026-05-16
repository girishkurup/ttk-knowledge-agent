"""
TTK Knowledge Store — SQLite backend
All interview conversations, artifacts and graph data are persisted here.
The knowledge graph is generated from stored conversations, not text files.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path("ttk_output") / "ttk_knowledge.db"


# ── Connection ─────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")   # safe for concurrent reads
    c.execute("PRAGMA foreign_keys=ON")
    return c


# ── Schema ─────────────────────────────────────────────────────────────────────

def init_db():
    """Create tables and migrate any existing JSON/txt files. Safe to call every startup."""
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id   TEXT PRIMARY KEY,
            batch_id     TEXT,
            product      TEXT,
            engineer     TEXT,
            started_at   TEXT DEFAULT (datetime('now')),
            ended_at     TEXT,
            turn_count   INTEGER DEFAULT 0,
            status       TEXT DEFAULT 'in_progress'
        );

        CREATE TABLE IF NOT EXISTS messages (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   TEXT REFERENCES sessions(session_id),
            turn         INTEGER,
            role         TEXT,        -- 'assistant' | 'user'
            content      TEXT,
            created_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS artifacts (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id    TEXT REFERENCES sessions(session_id),
            artifact_type TEXT,       -- 'knowledge_article' | 'checklist' | 'graph_json'
            content       TEXT,
            generated_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS graph_nodes (
            node_id      TEXT,
            session_id   TEXT,
            label        TEXT,
            node_type    TEXT,
            properties   TEXT DEFAULT '{}',
            PRIMARY KEY (node_id, session_id)
        );

        CREATE TABLE IF NOT EXISTS graph_edges (
            edge_id      TEXT,
            session_id   TEXT,
            from_node    TEXT,
            to_node      TEXT,
            label        TEXT,
            properties   TEXT DEFAULT '{}',
            PRIMARY KEY (edge_id, session_id)
        );

        CREATE INDEX IF NOT EXISTS idx_msg_session   ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_art_session   ON artifacts(session_id);
        CREATE INDEX IF NOT EXISTS idx_node_session  ON graph_nodes(session_id);
        CREATE INDEX IF NOT EXISTS idx_edge_session  ON graph_edges(session_id);
        """)


# ── Migration ─────────────────────────────────────────────────────────────────

def migrate_existing_files():
    """Import any KnowledgeGraph_*.json files that aren't yet in the DB."""
    import re
    output_dir = DB_PATH.parent
    jsons = sorted(output_dir.glob("KnowledgeGraph_*.json"))
    if not jsons:
        return
    with _conn() as c:
        for p in jsons:
            session_id = p.stem  # e.g. KnowledgeGraph_SUP30498_20260515_1257
            already = c.execute(
                "SELECT 1 FROM graph_nodes WHERE session_id = ? LIMIT 1", (session_id,)
            ).fetchone()
            if already:
                continue
            try:
                g = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            # derive metadata
            m = re.search(r'(\d{8}_\d{4})', p.stem)
            ts = m.group(1) if m else p.stem
            try:
                dt = datetime.strptime(ts, "%Y%m%d_%H%M")
                started = dt.isoformat()
            except ValueError:
                started = datetime.now().isoformat()
            meta = g.get("metadata", {})
            c.execute(
                "INSERT OR IGNORE INTO sessions "
                "(session_id, batch_id, product, engineer, started_at, status) "
                "VALUES (?,?,?,?,?,'complete')",
                (session_id,
                 meta.get("batch_id", "SUP30498"),
                 meta.get("product", "Enalapril Tablets (OSD)"),
                 meta.get("engineer", "Schulz"),
                 started),
            )
            for n in g.get("nodes", []):
                c.execute(
                    "INSERT OR IGNORE INTO graph_nodes "
                    "(node_id, session_id, label, node_type, properties) VALUES (?,?,?,?,?)",
                    (n["id"], session_id, n.get("label", ""), n.get("type", ""),
                     json.dumps(n.get("properties", {}))),
                )
            for e in g.get("edges", []):
                eid = e.get("id") or f"{e['from']}__{e['label']}__{e['to']}"
                c.execute(
                    "INSERT OR IGNORE INTO graph_edges "
                    "(edge_id, session_id, from_node, to_node, label, properties) "
                    "VALUES (?,?,?,?,?,?)",
                    (eid, session_id, e["from"], e["to"], e.get("label", ""),
                     json.dumps(e.get("properties", {}))),
                )


# ── Write operations ───────────────────────────────────────────────────────────

def create_session(session_id: str, batch_id: str, product: str, engineer: str):
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO sessions (session_id, batch_id, product, engineer) "
            "VALUES (?, ?, ?, ?)",
            (session_id, batch_id, product, engineer),
        )


def save_message(session_id: str, turn: int, role: str, content: str):
    with _conn() as c:
        c.execute(
            "INSERT INTO messages (session_id, turn, role, content) VALUES (?, ?, ?, ?)",
            (session_id, turn, role, content),
        )
        c.execute(
            "UPDATE sessions SET turn_count = MAX(turn_count, ?) WHERE session_id = ?",
            (turn, session_id),
        )


def complete_session(session_id: str):
    with _conn() as c:
        c.execute(
            "UPDATE sessions SET status = 'complete', ended_at = datetime('now') "
            "WHERE session_id = ?",
            (session_id,),
        )


def save_artifact(session_id: str, artifact_type: str, content: str):
    with _conn() as c:
        c.execute(
            "INSERT INTO artifacts (session_id, artifact_type, content) VALUES (?, ?, ?)",
            (session_id, artifact_type, content),
        )


def save_graph(session_id: str, graph_data: dict):
    with _conn() as c:
        for n in graph_data.get("nodes", []):
            c.execute(
                "INSERT OR REPLACE INTO graph_nodes "
                "(node_id, session_id, label, node_type, properties) VALUES (?,?,?,?,?)",
                (n["id"], session_id, n.get("label", ""), n.get("type", ""),
                 json.dumps(n.get("properties", {}))),
            )
        for e in graph_data.get("edges", []):
            eid = e.get("id") or f"{e['from']}__{e['label']}__{e['to']}"
            c.execute(
                "INSERT OR REPLACE INTO graph_edges "
                "(edge_id, session_id, from_node, to_node, label, properties) "
                "VALUES (?,?,?,?,?,?)",
                (eid, session_id, e["from"], e["to"], e.get("label", ""),
                 json.dumps(e.get("properties", {}))),
            )


# ── Read operations ────────────────────────────────────────────────────────────

def get_all_sessions() -> list[dict]:
    """Return all sessions for the admin sidebar, newest first."""
    with _conn() as c:
        rows = c.execute("""
            SELECT
                s.session_id, s.batch_id, s.product, s.engineer,
                s.started_at, s.ended_at, s.turn_count, s.status,
                MAX(CASE WHEN a.artifact_type = 'knowledge_article' THEN 1 ELSE 0 END) AS has_ka,
                MAX(CASE WHEN a.artifact_type = 'checklist'         THEN 1 ELSE 0 END) AS has_checklist,
                MAX(CASE WHEN a.artifact_type = 'graph_json'        THEN 1 ELSE 0 END) AS has_graph
            FROM sessions s
            LEFT JOIN artifacts a ON s.session_id = a.session_id
            GROUP BY s.session_id
            ORDER BY s.started_at DESC
        """).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        try:
            dt = datetime.fromisoformat(d["started_at"])
            d["display"] = dt.strftime("%Y-%m-%d  %H:%M")
        except Exception:
            d["display"] = d["started_at"] or d["session_id"]
        result.append(d)
    return result


def get_session_transcript(session_id: str) -> str:
    """Return a human-readable transcript for one session."""
    with _conn() as c:
        s = c.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if not s:
            return "(session not found)"
        msgs = c.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()

    lines = [
        "=" * 65,
        "  TTK AGENT -- INTERVIEW TRANSCRIPT",
        f"  Session:  {session_id}",
        f"  Batch:    {s['batch_id']}",
        f"  Product:  {s['product']}",
        f"  Engineer: {s['engineer']}",
        f"  Date:     {s['started_at']}",
        f"  Turns:    {s['turn_count']}",
        "=" * 65, "",
    ]
    for m in msgs:
        content = m["content"]
        if "[SESSION START" in content or "[SYSTEM NOTE" in content:
            continue
        speaker = "TTK AGENT" if m["role"] == "assistant" else s["engineer"]
        lines += [f"[{speaker}]", content.replace(f"[{s['engineer']}]: ", ""), ""]
    return "\n".join(lines)


def get_all_conversations_text() -> str:
    """Return all complete sessions as concatenated text for LLM input."""
    with _conn() as c:
        sessions = c.execute(
            "SELECT session_id, batch_id, engineer, product, started_at "
            "FROM sessions WHERE status = 'complete' ORDER BY started_at"
        ).fetchall()
        if not sessions:
            return ""

        parts = []
        for i, s in enumerate(sessions, 1):
            msgs = c.execute(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
                (s["session_id"],),
            ).fetchall()
            sep = "=" * 70
            parts.append(
                f"\n{sep}\n"
                f"  SESSION {i}: {s['batch_id']} | {s['engineer']} | {s['started_at']}\n"
                f"{sep}\n"
            )
            for m in msgs:
                content = m["content"]
                if "[SESSION START" in content or "[SYSTEM NOTE" in content:
                    continue
                speaker = "TTK AGENT" if m["role"] == "assistant" else s["engineer"]
                clean = content.replace(f"[{s['engineer']}]: ", "")
                parts.append(f"[{speaker}]\n{clean}\n")

        return "\n".join(parts)


def get_merged_graph() -> dict:
    """Merge all session graphs from DB into one unified graph."""
    with _conn() as c:
        node_rows = c.execute("""
            SELECT node_id, label, node_type,
                   GROUP_CONCAT(session_id, ', ') AS sessions,
                   COUNT(*)                        AS frequency,
                   properties
            FROM graph_nodes
            GROUP BY node_id
        """).fetchall()

        edge_rows = c.execute("""
            SELECT edge_id, from_node, to_node, label, properties
            FROM graph_edges
            GROUP BY edge_id
        """).fetchall()

        session_count = c.execute(
            "SELECT COUNT(DISTINCT session_id) FROM sessions WHERE status = 'complete'"
        ).fetchone()[0]

    node_ids = {r["node_id"] for r in node_rows}

    nodes = []
    for r in node_rows:
        props = json.loads(r["properties"] or "{}")
        props["sessions"]  = r["sessions"]
        props["frequency"] = str(r["frequency"])
        nodes.append({
            "id":         r["node_id"],
            "label":      r["label"],
            "type":       r["node_type"],
            "properties": props,
        })

    edges = []
    for r in edge_rows:
        if r["from_node"] in node_ids and r["to_node"] in node_ids:
            edges.append({
                "id":         r["edge_id"],
                "from":       r["from_node"],
                "to":         r["to_node"],
                "label":      r["label"],
                "properties": json.loads(r["properties"] or "{}"),
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "session_count": session_count,
            "node_count":    len(nodes),
            "edge_count":    len(edges),
            "generated":     datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
    }
