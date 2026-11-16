"""Paginated application reads, sharing the existing connection and repositories."""
from contextlib import closing

from database.connection import get_connection
from database.repositories.theme_runs_repository import get_latest_theme_run
from services.analysis.sentiment_summary import MODEL_NAME, summarize_sentiment


def page_result(items, total, page, per_page):
    return {"items": items, "total": total, "page": page, "per_page": per_page,
            "pages": (total + per_page - 1) // per_page}


SEARCH_SELECT = """
SELECT s.*,
 (SELECT COUNT(*) FROM search_tweets st WHERE st.search_id=s.id) AS tweet_count,
 (SELECT COUNT(*) FROM theme_discovery_runs r WHERE r.search_id=s.id) AS run_count,
 (SELECT COUNT(*) FROM search_tweets st JOIN sentiment_results sr
  ON sr.tweet_id=st.tweet_id AND sr.model_name=?
  WHERE st.search_id=s.id) AS analyzed_count
FROM searches s
"""


def list_searches(page=1, per_page=20, query=""):
    with closing(get_connection()) as conn:
        where = " WHERE instr(lower(s.topic), lower(?)) > 0"
        total = conn.execute("SELECT COUNT(*) FROM searches s" + where, (query,)).fetchone()[0]
        rows = conn.execute(SEARCH_SELECT + where + " ORDER BY s.id DESC LIMIT ? OFFSET ?",
                            (MODEL_NAME, query, per_page, (page - 1) * per_page)).fetchall()
        return page_result([dict(row) for row in rows], total, page, per_page)


def get_search(search_id):
    with closing(get_connection()) as conn:
        row = conn.execute(SEARCH_SELECT + " WHERE s.id=?", (MODEL_NAME, search_id)).fetchone()
        return dict(row) if row else None


def sentiment_for_search(search_id=None):
    with closing(get_connection()) as conn:
        source = "tweets t"
        params = [MODEL_NAME]
        where = ""
        if search_id is not None:
            source += " JOIN search_tweets st ON st.tweet_id=t.tweet_id"
            where = " WHERE st.search_id=?"
            params.append(search_id)
        rows = conn.execute(
            f"""SELECT lower(sr.label) label, COUNT(*) tweet_count,
            AVG(sr.confidence) average_confidence FROM {source}
            LEFT JOIN sentiment_results sr ON sr.tweet_id=t.tweet_id AND sr.model_name=?
            {where} GROUP BY lower(sr.label)""", params).fetchall()
        return summarize_sentiment(rows, sum(row["tweet_count"] for row in rows))


def dashboard():
    with closing(get_connection()) as conn:
        counts = {key: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for key, table in (
                      ("search_count", "searches"), ("tweet_count", "tweets"),
                      ("theme_run_count", "theme_discovery_runs"))}
    return {**counts, "sentiment": sentiment_for_search(),
            "recent_searches": list_searches(per_page=5)["items"]}


def search_detail(search_id):
    search = get_search(search_id)
    if search:
        search["sentiment"] = sentiment_for_search(search_id)
        latest = get_latest_theme_run(search_id)
        search["latest_run"] = dict(latest) if latest else None
    return search


def tweets_page(search_id=None, run_id=None, topic_id=None, page=1, per_page=20,
                sentiment="", query="", keyword=""):
    params = [MODEL_NAME]
    source = "tweets t"
    extra = ""
    order = "t.created_at DESC, t.tweet_id DESC"
    conditions = []
    if search_id is not None:
        source += " JOIN search_tweets st ON st.tweet_id=t.tweet_id"
        conditions.append("st.search_id=?")
        params.append(search_id)
    if run_id is not None:
        source += " JOIN theme_assignments ta ON ta.tweet_id=t.tweet_id"
        conditions += ["ta.run_id=?", "ta.bertopic_topic_id=?"]
        params += [run_id, topic_id]
        extra = ", ta.probability AS theme_probability"
        order = "ta.probability DESC, t.tweet_id ASC"
    source += " LEFT JOIN sentiment_results sr ON sr.tweet_id=t.tweet_id AND sr.model_name=?"
    if sentiment == "missing":
        conditions.append("(sr.id IS NULL OR lower(sr.label) NOT IN ('positive','neutral','negative'))")
    elif sentiment:
        conditions.append("lower(sr.label)=?")
        params.append(sentiment)
    if query:
        conditions.append("instr(lower(t.text),lower(?))>0")
        params.append(query)
    if keyword:
        conditions.append("keyword_matches(t.text,?)=1")
        params.append(keyword)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    with closing(get_connection()) as conn:
        from services.themes.keyword_service import matches_keyword
        conn.create_function('keyword_matches', 2, matches_keyword, deterministic=True)
        total = conn.execute(f"SELECT COUNT(*) FROM {source}{where}", params).fetchone()[0]
        rows = conn.execute(
            f"""SELECT t.*, lower(sr.label) sentiment_label,
            sr.confidence sentiment_confidence {extra} FROM {source}{where}
            ORDER BY {order} LIMIT ? OFFSET ?""",
            [*params, per_page, (page - 1) * per_page]).fetchall()
    return page_result([dict(row) for row in rows], total, page, per_page)


def list_runs(search_id, page=1, per_page=20):
    with closing(get_connection()) as conn:
        total = conn.execute("SELECT COUNT(*) FROM theme_discovery_runs WHERE search_id=?",
                             (search_id,)).fetchone()[0]
        rows = conn.execute("""
            SELECT r.*, (SELECT COUNT(*) FROM themes t WHERE t.run_id=r.id) theme_count,
            (SELECT COUNT(*) FROM theme_assignments ta WHERE ta.run_id=r.id) tweet_count
            FROM theme_discovery_runs r WHERE search_id=? ORDER BY r.id DESC LIMIT ? OFFSET ?
        """, (search_id, per_page, (page - 1) * per_page)).fetchall()
    return page_result([dict(row) for row in rows], total, page, per_page)


def get_run(run_id):
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT * FROM theme_discovery_runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None


def sentiment_by_tweet_ids(ids):
    """Batch reads below SQLite's portable variable limit."""
    result = {}
    with closing(get_connection()) as conn:
        ids = list(ids)
        for offset in range(0, len(ids), 500):
            chunk = ids[offset:offset + 500]
            rows = conn.execute(f"""
                SELECT tweet_id, lower(label) label, confidence FROM sentiment_results
                WHERE model_name=? AND tweet_id IN ({','.join('?' for _ in chunk)})
            """, [MODEL_NAME, *chunk]).fetchall()
            result.update({row["tweet_id"]: dict(row) for row in rows})
    return result


def run_documents(run_id):
    """One bounded corpus read for keyword evidence; never sent to the browser."""
    with closing(get_connection()) as conn:
        rows = conn.execute('''SELECT t.tweet_id, ta.bertopic_topic_id, t.text
            FROM theme_assignments ta JOIN tweets t ON t.tweet_id=ta.tweet_id
            WHERE ta.run_id=?''', (run_id,)).fetchall()
    return [(r['tweet_id'], r['bertopic_topic_id'], r['text']) for r in rows]


def comparison_documents(search_id_a, search_id_b):
    with closing(get_connection()) as conn:
        rows = conn.execute('''SELECT st.search_id,t.tweet_id,t.text FROM search_tweets st
            JOIN tweets t ON t.tweet_id=st.tweet_id WHERE st.search_id IN (?,?)''',
            (search_id_a, search_id_b)).fetchall()
    return [dict(row) for row in rows]
