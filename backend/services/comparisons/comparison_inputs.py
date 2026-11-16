"""Cheap preflight mirroring existing joint pipeline eligibility, without ML."""
import re
from database.repositories.explorer_repository import comparison_documents


def preview_comparison(a, b, exclude_ads=False):
    rows = comparison_documents(a, b)
    sources = {a:set(), b:set()}
    excluded = {a:0, b:0}
    for row in rows:
        if exclude_ads and re.search(r'(?<!\w)#ad\b', row['text'] or '', re.IGNORECASE):
            excluded[row['search_id']] += 1
        else:
            sources[row['search_id']].add(row['tweet_id'])
    count_a, count_b = len(sources[a]), len(sources[b])
    unique = len(sources[a] | sources[b])
    ratio = min(count_a,count_b)/max(count_a,count_b) if max(count_a,count_b) else 0
    reasons = []
    if not count_a or not count_b:
        reasons.append('Both searches need tweets after filtering.')
    if ratio < .5:
        reasons.append('The smaller filtered search must have at least half as many tweets as the larger search.')
    if unique < 7:
        reasons.append('At least 7 unique tweets are needed after filtering and overlap removal.')
    return {'tweet_count_a':count_a,'tweet_count_b':count_b,'unique_tweet_count':unique,
            'overlap_count':len(sources[a] & sources[b]),'size_ratio':ratio,
            'excluded_ads_a':excluded[a],'excluded_ads_b':excluded[b],
            'eligible':not reasons,'reasons':reasons}
