"""Separate, durable application state. The analytical database is not migrated."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from database.repositories.explorer_repository import page_result
from services.analysis.sentiment_summary import MODEL_NAME


def now():
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, path, source_path):
        self.path, self.source_path = str(path), str(source_path)
        with self.connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, dedupe_key TEXT NOT NULL,
                    inputs TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
                    result TEXT, error TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_job ON jobs(dedupe_key)
                    WHERE status IN ('pending','running');
                CREATE TABLE IF NOT EXISTS comparison_assignments (
                    job_id TEXT NOT NULL REFERENCES jobs(id), tweet_id TEXT NOT NULL,
                    topic_id INTEGER NOT NULL, search_id INTEGER NOT NULL,
                    PRIMARY KEY(job_id, tweet_id, search_id)
                );
                CREATE INDEX IF NOT EXISTS comparison_evidence
                    ON comparison_assignments(job_id, topic_id, search_id);
            """)

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def decode(row):
        if row is None:
            return None
        item = dict(row)
        item.pop("dedupe_key", None)
        for key in ("inputs", "result"):
            item[key] = json.loads(item[key]) if item[key] else None
        return item

    def recover(self):
        with self.connection() as conn:
            conn.execute("""UPDATE jobs SET status='failed', finished_at=?,
                error='The server stopped before this operation completed. You can run it again.'
                WHERE status IN ('pending','running')""", (now(),))

    def get(self, job_id):
        with self.connection() as conn:
            return self.decode(conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def active(self, key):
        with self.connection() as conn:
            return self.decode(conn.execute(
                "SELECT * FROM jobs WHERE dedupe_key=? AND status IN ('pending','running')",
                (key,)).fetchone())

    def count_active(self):
        with self.connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('pending','running')").fetchone()[0]

    def create(self, job_id, kind, inputs, key):
        with self.connection() as conn:
            conn.execute("""INSERT INTO jobs(id,kind,dedupe_key,inputs,status,created_at)
                VALUES(?,?,?,?,'pending',?)""", (job_id, kind, key, json.dumps(inputs), now()))

    def start(self, job_id):
        with self.connection() as conn:
            conn.execute("UPDATE jobs SET status='running', started_at=? WHERE id=?", (now(), job_id))

    def finish(self, job_id, result=None, error=None):
        with self.connection() as conn:
            conn.execute("UPDATE jobs SET status=?, result=?, error=?, finished_at=? WHERE id=?",
                         ("failed" if error else "completed",
                          json.dumps(result, allow_nan=False) if result is not None else None,
                          error, now(), job_id))

    def list(self, page=1, per_page=20, kind=None, active=False):
        clauses, params = [], []
        if kind:
            clauses.append("kind=?")
            params.append(kind)
        if active:
            clauses.append("status IN ('pending','running')")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM jobs" + where, params).fetchone()[0]
            rows = conn.execute("SELECT * FROM jobs" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
                                [*params, per_page, (page - 1) * per_page]).fetchall()
        return page_result([self.decode(row) for row in rows], total, page, per_page)

    def save_assignments(self, job_id, assignments, memberships):
        with self.connection() as conn:
            conn.executemany("""INSERT INTO comparison_assignments
                (job_id,tweet_id,topic_id,search_id) VALUES(?,?,?,?)""",
                ((job_id, tweet_id, topic_id, search_id)
                 for tweet_id, topic_id in assignments.items()
                 for search_id in memberships[tweet_id]))

    def comparison_rows(self, job_id):
        with self.connection() as conn:
            conn.execute("ATTACH DATABASE ? AS source", (self.source_path,))
            rows = conn.execute("""SELECT a.topic_id, a.search_id, t.tweet_id, t.text,
                lower(sr.label) AS label, sr.confidence
                FROM comparison_assignments a JOIN source.tweets t ON t.tweet_id=a.tweet_id
                LEFT JOIN source.sentiment_results sr ON sr.tweet_id=t.tweet_id AND sr.model_name=?
                WHERE a.job_id=?""", (MODEL_NAME, job_id)).fetchall()
        return [dict(row) for row in rows]

    def evidence(self, job_id, topic_id, search_id, page=1, per_page=20,
                 sentiment='', query='', keyword=''):
        from services.themes.keyword_service import matches_keyword
        with self.connection() as conn:
            conn.create_function('keyword_matches', 2, matches_keyword, deterministic=True)
            conn.execute("ATTACH DATABASE ? AS source", (self.source_path,))
            params = [MODEL_NAME, job_id, topic_id, search_id]
            source = """FROM comparison_assignments a JOIN source.tweets t ON t.tweet_id=a.tweet_id
                LEFT JOIN source.sentiment_results sr ON sr.tweet_id=t.tweet_id AND sr.model_name=?
                WHERE a.job_id=? AND a.topic_id=? AND a.search_id=?"""
            if sentiment == 'missing':
                source += " AND (sr.id IS NULL OR lower(sr.label) NOT IN ('positive','neutral','negative'))"
            elif sentiment:
                source += ' AND lower(sr.label)=?'
                params.append(sentiment)
            if query:
                source += ' AND instr(lower(t.text),lower(?))>0'
                params.append(query)
            if keyword:
                source += ' AND keyword_matches(t.text,?)=1'
                params.append(keyword)
            total = conn.execute('SELECT COUNT(*) ' + source, params).fetchone()[0]
            rows = conn.execute("""SELECT t.*, lower(sr.label) sentiment_label,
                sr.confidence sentiment_confidence """ + source + """
                ORDER BY t.tweet_id DESC LIMIT ? OFFSET ?""",
                [*params, per_page, (page - 1) * per_page]).fetchall()
        return page_result([dict(row) for row in rows], total, page, per_page)
