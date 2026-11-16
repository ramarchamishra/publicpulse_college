"""Read-time analytics over saved joint assignments; never runs clustering."""
from collections import defaultdict
from copy import deepcopy
from services.analysis.sentiment_summary import summarize_sentiment
from services.themes.keyword_service import keyword_profiles, tokens


def comparison_summary(result, rows):
    summary = deepcopy(result)
    if not rows:
        summary['evidence_available'] = False
        summary['sentiment_basis'] = 'saved_snapshot'
        return summary
    summary['evidence_available'] = True
    summary['sentiment_basis'] = 'current_stored_results'
    groups = {t['topic_id']: t.get('keyword_candidates', t['keywords'])
              for t in summary['themes'] if t['topic_id'] != -1}
    profiles = keyword_profiles(groups,
        [(r['tweet_id'], r['topic_id'], r['text']) for r in rows],
        [summary['search_a']['topic'], summary['search_b']['topic']], comparison=True)
    by_source, by_topic = defaultdict(list), defaultdict(list)
    for row in rows:
        row = {**row, '_words': set(tokens(row['text']))}
        by_source[row['search_id']].append(row)
        by_topic[row['topic_id']].append(row)

    def sentiment(items):
        return summarize_sentiment([
            {'label': r['label'], 'tweet_count': 1, 'average_confidence': r['confidence']}
            for r in items], len(items))

    for side in ('a', 'b'):
        summary['sentiment_' + side] = sentiment(by_source[summary['search_id_' + side]])
    for theme in summary['themes']:
        items = by_topic[theme['topic_id']]
        ids = {r['tweet_id'] for r in items}
        theme['unique_tweet_count'] = len(ids)
        theme['overlap_count'] = len(items) - len(ids)
        for side in ('a', 'b'):
            theme['sentiment_' + side] = sentiment([
                r for r in items if r['search_id'] == summary['search_id_' + side]])
        if theme['topic_id'] != -1:
            theme['keyword_profile'] = profiles[theme['topic_id']]
            theme['keyword_profile']['comparison'] = True
            for item in theme['keyword_profile']['items']:
                wanted = set(tokens(item['term']))
                for side in ('a', 'b'):
                    item['count_' + side] = sum(wanted <= row['_words'] for row in items
                        if row['search_id'] == summary['search_id_' + side])
            theme['display_name'] = ', '.join(c['term'] for c in theme['keyword_profile']['items'][:3]) or f"Discussion {theme['topic_id']}"
    return summary
