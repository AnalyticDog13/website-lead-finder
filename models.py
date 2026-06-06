import sqlite3
from dataclasses import dataclass, asdict
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

def init_db(db_path: str = "leads.db"):
    conn = sqlite3.connect(db_path)
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
            scraped_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def insert_lead(lead: Lead, db_path: str = "leads.db") -> int:
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("""
        INSERT INTO leads (business_name, category, phone, email, website_url,
                          has_website, quality_score, quality_notes, source,
                          address, status, user_notes, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        lead.business_name, lead.category, lead.phone, lead.email,
        lead.website_url, int(lead.has_website), lead.quality_score,
        lead.quality_notes, lead.source, lead.address, lead.status,
        lead.user_notes, lead.scraped_at,
    ))
    conn.commit()
    lead_id = cursor.lastrowid
    conn.close()
    return lead_id

def get_leads(db_path: str = "leads.db", category: str = None, status: str = None) -> list:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM leads WHERE 1=1"
    params = []
    if category and category != "all":
        query += " AND category = ?"
        params.append(category)
    if status and status != "all":
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY scraped_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_lead_status(lead_id: int, status: str, user_notes: str = None, db_path: str = "leads.db"):
    conn = sqlite3.connect(db_path)
    if user_notes is not None:
        conn.execute("UPDATE leads SET status = ?, user_notes = ? WHERE id = ?",
                     (status, user_notes, lead_id))
    else:
        conn.execute("UPDATE leads SET status = ? WHERE id = ?", (status, lead_id))
    conn.commit()
    conn.close()
