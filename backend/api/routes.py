from contextlib import closing
from pathlib import Path
import re

from flask import Blueprint, current_app, jsonify, request

from api.errors import APIError
from database.connection import get_connection
from database.repositories import explorer_repository as repo
from services.analysis.sentiment_summary import MODEL_NAME
from services.comparisons.comparison_analytics_service import comparison_summary
from services.comparisons.comparison_inputs import preview_comparison
from services.themes.theme_analytics_service import ThemeAnalyticsService

api = Blueprint("api", __name__, url_prefix="/api")


def ok(data, status=200):
    return jsonify({"data": data}), status


def integer(value, name, minimum=1, maximum=2**31 - 1):
    if isinstance(value, bool) or not re.fullmatch(r"-?\d+", str(value)):
        raise APIError(f"{name} must be an integer.")
    number = int(value)
    if not minimum <= number <= maximum:
        raise APIError(f"{name} must be between {minimum} and {maximum}.")
    return number


def pagination():
    return {"page": integer(request.args.get("page", 1), "page"),
            "per_page": integer(request.args.get("per_page", 20), "per_page", maximum=100)}


def body(allowed):
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise APIError("Send a JSON object.")
    if set(value) - set(allowed):
        raise APIError("The request contains unsupported fields.")
    return value


def query_text(name="q"):
    query = request.args.get(name, "").strip()
    if len(query) > 300:
        raise APIError("The filter must be at most 300 characters.")
    return query


def evidence_filters():
    sentiment = request.args.get('sentiment', '')
    if sentiment not in ('', 'positive', 'neutral', 'negative', 'missing'):
        raise APIError('Invalid sentiment filter.')
    return {'sentiment': sentiment, 'query': query_text(), 'keyword': query_text('keyword')}


def require_search(search_id, tweets=False):
    result = repo.get_search(search_id)
    if result is None:
        raise APIError("Search not found.", 404, "not_found")
    if tweets and not result["tweet_count"]:
        raise APIError("This search has no tweets to analyze.", 422, "empty_search")
    return result


def require_run(run_id):
    result = repo.get_run(run_id)
    if result is None:
        raise APIError("Theme run not found.", 404, "not_found")
    return result


def jobs():
    return current_app.extensions["jobs"]


def require_job(job_id):
    job = jobs().store.get(job_id)
    if not job:
        raise APIError("Operation not found.", 404, "not_found")
    return job


@api.get("/health")
def health():
    if not Path(current_app.config["DATABASE"]).is_file():
        raise APIError("The database is missing. Run flask --app app init-db for a new installation.", 503, "database_unavailable")
    with closing(get_connection()) as conn:
        conn.execute("SELECT id FROM searches LIMIT 1").fetchone()
    return ok({"status": "ok"})


@api.get("/dashboard")
def dashboard():
    return ok(repo.dashboard())


@api.get("/searches")
def searches():
    return ok(repo.list_searches(**pagination(), query=query_text()))


@api.post("/searches")
def create_search():
    data = body({"topic", "limit", "mode"})
    topic = data.get("topic")
    if not isinstance(topic, str) or not topic.strip() or len(topic.strip()) > 200:
        raise APIError("topic must contain 1–200 characters.")
    if not re.search(r"[A-Za-z0-9]", topic):
        raise APIError("The existing English collector needs a topic with letters or numbers.")
    mode = data.get("mode", "Latest")
    if mode not in ("Latest", "Top", "Mixed"):
        raise APIError("mode must be Latest, Top, or Mixed.")
    inputs = {"topic": topic.strip(), "limit": integer(data.get("limit", 100), "limit", maximum=10000),
              "mode": mode}
    return ok(jobs().submit("collection", inputs), 202)


@api.get("/searches/<int:search_id>")
def search_detail(search_id):
    require_search(search_id)
    return ok(repo.search_detail(search_id))


@api.get("/searches/<int:search_id>/tweets")
def search_tweets(search_id):
    require_search(search_id)
    sentiment = request.args.get("sentiment", "")
    if sentiment not in ("", "positive", "neutral", "negative", "missing"):
        raise APIError("Invalid sentiment filter.")
    return ok(repo.tweets_page(search_id=search_id, sentiment=sentiment,
                              query=query_text(), **pagination()))


@api.get("/searches/<int:search_id>/sentiment")
def search_sentiment(search_id):
    require_search(search_id)
    return ok(repo.sentiment_for_search(search_id))


@api.post("/searches/<int:search_id>/sentiment")
def analyze_sentiment(search_id):
    require_search(search_id, tweets=True)
    return ok(jobs().submit("sentiment", {"search_id": search_id}), 202)


@api.get("/searches/<int:search_id>/theme-runs")
def theme_runs(search_id):
    require_search(search_id)
    return ok(repo.list_runs(search_id, **pagination()))


@api.post("/searches/<int:search_id>/theme-runs")
def discover_themes(search_id):
    search = require_search(search_id, tweets=True)
    # The unchanged UMAP spectral initialization uses five components and needs >6 samples.
    if search["tweet_count"] < 7:
        raise APIError("The existing Theme Discovery pipeline requires at least 7 tweets.", 422, "insufficient_data")
    return ok(jobs().submit("themes", {"search_id": search_id}), 202)


@api.get("/theme-runs/<int:run_id>")
def theme_run(run_id):
    require_run(run_id)
    return ok(ThemeAnalyticsService().get_sentiment_summary_for_run(run_id, MODEL_NAME))


@api.get("/theme-runs/<int:run_id>/topics/<topic_id>/tweets")
def theme_tweets(run_id, topic_id):
    require_run(run_id)
    topic_id = integer(topic_id, "topic_id", minimum=-1)
    summary = ThemeAnalyticsService().get_summary_for_run(run_id)
    if topic_id not in {-1, *(t["bertopic_topic_id"] for t in summary["themes"])}:
        raise APIError("Theme not found in this run.", 404, "not_found")
    return ok(repo.tweets_page(run_id=run_id, topic_id=topic_id, **evidence_filters(), **pagination()))


@api.post("/comparisons")
def compare():
    data = body({"search_id_a", "search_id_b", "exclude_explicit_ads"})
    a = integer(data.get("search_id_a"), "search_id_a")
    b = integer(data.get("search_id_b"), "search_id_b")
    if a == b:
        raise APIError("Choose two different saved searches.", 422, "same_search")
    require_search(a)
    require_search(b)
    exclude_ads = data.get("exclude_explicit_ads", False)
    if not isinstance(exclude_ads, bool):
        raise APIError("exclude_explicit_ads must be a boolean.")
    preview = preview_comparison(a, b, exclude_ads)
    if not preview['eligible']:
        raise APIError(' '.join(preview['reasons']), 422, 'ineligible_comparison')
    return ok(jobs().submit("comparison", {
        "search_id_a": a, "search_id_b": b, "exclude_explicit_ads": exclude_ads,
    }), 202)


@api.get('/comparisons/preview')
def comparison_preview():
    a = integer(request.args.get('search_id_a'), 'search_id_a')
    b = integer(request.args.get('search_id_b'), 'search_id_b')
    if a == b:
        raise APIError('Choose two different saved searches.', 422, 'same_search')
    require_search(a)
    require_search(b)
    exclude = request.args.get('exclude_explicit_ads', 'false')
    if exclude not in ('true', 'false'):
        raise APIError('exclude_explicit_ads must be true or false.')
    return ok(preview_comparison(a, b, exclude == 'true'))


@api.get("/jobs")
def list_jobs():
    kind = request.args.get("kind")
    if kind and kind not in ("collection", "sentiment", "themes", "comparison"):
        raise APIError("Invalid operation kind.")
    return ok(jobs().store.list(**pagination(), kind=kind, active=request.args.get("active") == "true"))


@api.get("/jobs/<job_id>")
def get_job(job_id):
    return ok(require_job(job_id))


@api.get("/comparisons/<job_id>")
def get_comparison(job_id):
    job = require_job(job_id)
    if job["kind"] != "comparison":
        raise APIError("Comparison not found.", 404, "not_found")
    if job["status"] != "completed":
        raise APIError("This comparison has no completed result yet.", 409, "not_completed")
    return ok(comparison_summary(job["result"], jobs().store.comparison_rows(job_id)))


@api.get("/comparisons/<job_id>/topics/<topic_id>/tweets")
def comparison_tweets(job_id, topic_id):
    job = require_job(job_id)
    if job["kind"] != "comparison" or job["status"] != "completed":
        raise APIError("Completed comparison not found.", 404, "not_found")
    topic_id = integer(topic_id, "topic_id", minimum=-1)
    search_id = integer(request.args.get("search_id"), "search_id")
    result = job["result"]
    if search_id not in (result["search_id_a"], result["search_id_b"]):
        raise APIError("This search does not belong to the comparison.")
    if topic_id not in {t["topic_id"] for t in result["themes"]}:
        raise APIError("Discussion not found.", 404, "not_found")
    return ok(jobs().store.evidence(job_id, topic_id, search_id, **evidence_filters(), **pagination()))
