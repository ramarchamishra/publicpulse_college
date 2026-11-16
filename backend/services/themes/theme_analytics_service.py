from database.repositories.theme_runs_repository import (
    get_latest_theme_run,
)
from database.repositories.explorer_repository import get_run, get_search, run_documents
from services.themes.keyword_service import keyword_profiles
from services.analysis.sentiment_summary import summarize_sentiment
from database.repositories.themes_repository import (
    get_themes_for_run,
)
from database.repositories.theme_assignments_repository import (
    get_assignment_statistics_for_run,
    get_theme_sentiment_statistics_for_run,
    get_tweets_for_theme
)

class ThemeAnalyticsService:

    def get_summary_for_search(
        self,
        search_id: int
    ) -> dict | None:
        run = get_latest_theme_run(search_id)

        if run is None:
            return None

        return self.get_summary_for_run(run["id"])

    def get_summary_for_run(self, run_id: int) -> dict | None:
        run = get_run(run_id)
        if run is None:
            return None
        run_id = run["id"]

        themes = get_themes_for_run(run_id)
        statistics = get_assignment_statistics_for_run(run_id)
        search = get_search(run['search_id'])
        profiles = keyword_profiles(
            {theme['bertopic_topic_id']: theme['keywords'] for theme in themes},
            run_documents(run_id), [search['topic']] if search else [],
        )
        for theme in themes:
            theme['keyword_profile'] = profiles[theme['bertopic_topic_id']]
            terms = [item['term'] for item in theme['keyword_profile']['items'][:3]]
            theme['display_name'] = ', '.join(terms) or f"Theme {theme['bertopic_topic_id']}"


        total_count = statistics["total_count"]
        clustered_count = statistics["clustered_count"]
        noise_count = statistics["noise_count"]

        for theme in themes:
            theme["discussion_share_percentage"] = (
                theme["tweet_count"] / total_count * 100
                if total_count else 0.0
            )

        clustered_percentage = (
            clustered_count / total_count * 100
            if total_count else 0.0
        )

        noise_percentage = (
            noise_count / total_count * 100
            if total_count else 0.0
        )

        return {
            "run": dict(run),
            "tweet_count": total_count,
            "theme_count": len(themes),
            "clustered_count": clustered_count,
            "noise_count": noise_count,
            "clustered_percentage": clustered_percentage,
            "noise_percentage": noise_percentage,
            "average_probability": statistics["average_probability"],
            "themes": themes,
        }

    def get_sentiment_summary_for_search(
        self,
        search_id: int,
        model_name: str
    ) -> dict | None:
        summary = self.get_summary_for_search(search_id)
        return self._add_sentiment(summary, model_name)

    def get_sentiment_summary_for_run(self, run_id: int, model_name: str) -> dict | None:
        return self._add_sentiment(self.get_summary_for_run(run_id), model_name)

    def _add_sentiment(self, summary, model_name):
        if summary is None:
            return None

        rows = get_theme_sentiment_statistics_for_run(
            summary["run"]["id"],
            model_name
        )

        rows_by_topic = {}

        for row in rows:
            topic_id = row["bertopic_topic_id"]
            rows_by_topic.setdefault(topic_id, []).append(row)

        noise = {
            "bertopic_topic_id": -1,
            "name": "Unclustered tweets",
            "tweet_count": summary["noise_count"],
            "discussion_share_percentage": summary["noise_percentage"],
        }

        for group in [*summary["themes"], noise]:
            topic_id = group["bertopic_topic_id"]
            total_count = group["tweet_count"]

            group['sentiment'] = summarize_sentiment(rows_by_topic.get(topic_id, []), total_count)

        summary["sentiment"] = summarize_sentiment(rows, summary["tweet_count"])
        summary["sentiment_model"] = model_name
        summary["noise"] = noise

        return summary

    def get_theme_tweets(
        self,
        run_id: int,
        bertopic_topic_id: int,
        model_name: str,
        limit: int = 5
    ) -> list[dict]:
        return get_tweets_for_theme(
            run_id=run_id,
            bertopic_topic_id=bertopic_topic_id,
            model_name=model_name,
            limit=limit
        )
