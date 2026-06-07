import sqlite3
from dataclasses import dataclass
from typing import Optional

@dataclass
class Lead:
    business_name: str
    category: str
    phone: str
    email: str
    website_url: str
    has_website: bool
    quality_score: Optional[int]
    quality_notes: str
    source: str
    address: str
    status: str
    user_notes: str
    scraped_at: str
    id: Optional[int] = None
    visited: bool = False
    worth_reaching_out: Optional[bool] = None
    outreach_summary: str = ""

def init_db(db_path: str = "leads.db"):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_name TEXT NOT NULL,
                category TEXT,
                phone TEXT,
                email TEXT,
                website_url TEXT,
                has_website INTEGER,
                quality_score INTEGER,
                quality_notes TEXT,
                source TEXT,
                address TEXT,
                status TEXT DEFAULT 'review',
                user_notes TEXT DEFAULT '',
                scraped_at TEXT,
                visited INTEGER DEFAULT 0,
                worth_reaching_out INTEGER,
                outreach_summary TEXT DEFAULT ''
            )
        """)
        for col, definition in [
            ("visited", "INTEGER DEFAULT 0"),
            ("worth_reaching_out", "INTEGER"),
            ("outreach_summary", "TEXT DEFAULT ''"),
        ]:
            try:
                conn.execute(f"ALTER TABLE leads ADD COLUMN {col} {definition}")
            except sqlite3.OperationalError:
                pass
        conn.commit()
    finally:
        conn.close()

def business_exists(name: str, db_path: str = "leads.db") -> bool:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT id FROM leads WHERE LOWER(TRIM(business_name)) = LOWER(TRIM(?))",
            (name,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()

def get_lead_by_id(lead_id: int, db_path: str = "leads.db") -> Optional[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def insert_lead(lead: Lead, db_path: str = "leads.db") -> int:
    conn = sqlite3.connect(db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM leads WHERE LOWER(TRIM(business_name)) = LOWER(TRIM(?))",
            (lead.business_name,)
        ).fetchone()
        if existing:
            return existing[0]

        cursor = conn.execute("""
            INSERT INTO leads (business_name, category, phone, email, website_url,
                              has_website, quality_score, quality_notes, source,
                              address, status, user_notes, scraped_at,
                              visited, worth_reaching_out, outreach_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lead.business_name, lead.category, lead.phone, lead.email,
            lead.website_url, int(lead.has_website), lead.quality_score,
            lead.quality_notes, lead.source, lead.address, lead.status,
            lead.user_notes, lead.scraped_at,
            int(lead.visited),
            int(lead.worth_reaching_out) if lead.worth_reaching_out is not None else None,
            lead.outreach_summary,
        ))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def get_leads(db_path: str = "leads.db", category: str = None, status: str = None) -> list:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        query = "SELECT * FROM leads WHERE 1=1"
        params = []
        if category and category != "all":
            query += " AND category = ?"
            params.append(category)
        if status and status != "all":
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY has_website ASC, COALESCE(quality_score, 0) ASC, scraped_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def update_lead_status(
    lead_id: int,
    status: str,
    user_notes: str = None,
    visited: bool = None,
    worth_reaching_out: Optional[bool] = None,
    email: str = None,
    db_path: str = "leads.db",
):
    conn = sqlite3.connect(db_path)
    try:
        sets = ["status = ?"]
        params = [status]
        if user_notes is not None:
            sets.append("user_notes = ?")
            params.append(user_notes)
        if visited is not None:
            sets.append("visited = ?")
            params.append(int(visited))
        if worth_reaching_out is not None:
            sets.append("worth_reaching_out = ?")
            params.append(int(worth_reaching_out))
        if email is not None:
            sets.append("email = ?")
            params.append(email)
        params.append(lead_id)
        conn.execute(f"UPDATE leads SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()
    finally:
        conn.close()

def delete_leads_by_status(status: str, db_path: str = "leads.db") -> int:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute("DELETE FROM leads WHERE status = ?", (status,))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()

def save_outreach_summary(lead_id: int, summary: str, db_path: str = "leads.db"):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE leads SET outreach_summary = ? WHERE id = ?", (summary, lead_id))
        conn.commit()
    finally:
        conn.close()
