"""Adapters to the existing services. ML imports happen only inside worker jobs."""
import asyncio
import os
from collections import defaultdict
from pathlib import Path

from api.errors import OperationError
from database.repositories.explorer_repository import get_search, sentiment_by_tweet_ids
from services.analysis.sentiment_summary import summarize_sentiment


def collect(inputs):
    if not all(os.getenv(key) for key in ("X_AUTHTOKEN", "X_CT0")):
        raise OperationError("Collection needs X_AUTHTOKEN and X_CT0 in backend/.env.")
    from services.analysis.ingestion_service import IngestionService

    async def run():
        service = IngestionService(
            strict_errors=True,
            export_directory=Path(__file__).resolve().parents[2] / "instance" / "collection",
        )
        try:
            return await service.ingest_topic(**inputs)
        finally:
            await service.scraper.client.http.aclose()

    return asyncio.run(run())


def sentiment(inputs):
    from services.analysis.analysis_service import AnalysisService
    return AnalysisService().analyze_search(inputs["search_id"])


def themes(inputs):
    from services.themes.theme_discovery_service import ThemeDiscoveryService
    return ThemeDiscoveryService().discover_for_search(inputs["search_id"])


def comparison(inputs, job_id, store):
    from services.comparisons.search_comparison_service import SearchComparisonService
    service = SearchComparisonService()
    try:
        prepared = service.prepare_comparison(**inputs)
    except ValueError as exc:
        # prepare_comparison only raises known validation errors, before loading models.
        raise OperationError(str(exc)) from exc
    if prepared["unique_tweet_count"] < 7:
        raise OperationError("The existing comparison pipeline requires at least 7 unique tweets after filtering.")
    discovery = service.discover_shared_themes(**inputs)
    summary = service.summarize_joint_themes(discovery)
    assignments = discovery["topic_assignments"]
    memberships = discovery["tweet_search_ids"]
    stored_sentiments = sentiment_by_tweet_ids(assignments)

    def group_sentiment(ids):
        stats = defaultdict(list)
        for tweet_id in ids:
            row = stored_sentiments.get(tweet_id)
            if row:
                stats[row["label"]].append(row["confidence"])
        rows = [{"label": label, "tweet_count": len(values),
                 "average_confidence": sum(values) / len(values)}
                for label, values in stats.items()]
        return summarize_sentiment(rows, len(ids))

    search_a, search_b = inputs["search_id_a"], inputs["search_id_b"]
    grouped = defaultdict(list)
    sources = defaultdict(list)
    for tweet_id, topic_id in assignments.items():
        for search_id in memberships[tweet_id]:
            grouped[(topic_id, search_id)].append(tweet_id)
            sources[search_id].append(tweet_id)
    for theme in summary["themes"]:
        if theme['topic_id'] != -1 and 'model' in discovery:
            theme['keyword_candidates'] = [
                [str(word), float(weight)]
                for word, weight in (discovery['model'].get_topic(theme['topic_id']) or [])
            ]
        theme["sentiment_a"] = group_sentiment(grouped[(theme["topic_id"], search_a)])
        theme["sentiment_b"] = group_sentiment(grouped[(theme["topic_id"], search_b)])
    store.save_assignments(job_id, assignments, memberships)
    return {
        **summary, "search_a": get_search(search_a), "search_b": get_search(search_b),
        **{key: discovery[key] for key in (
            "tweet_count_a", "tweet_count_b", "unique_tweet_count", "theme_count",
            "clustered_count", "noise_count")},
        "overlap_count": prepared["overlap_count"],
        "excluded_ads_a": prepared["excluded_ads_a"], "excluded_ads_b": prepared["excluded_ads_b"],
        "exclude_explicit_ads": inputs["exclude_explicit_ads"],
        "sentiment_a": group_sentiment(sources[search_a]),
        "sentiment_b": group_sentiment(sources[search_b]),
    }


def execute(kind, inputs, job_id, store):
    if kind == "comparison":
        return comparison(inputs, job_id, store)
    return {"collection": collect, "sentiment": sentiment, "themes": themes}[kind](inputs)
