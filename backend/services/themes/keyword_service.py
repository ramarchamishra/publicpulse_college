"""Read-only, evidence-grounded keyword presentation. No ML or clustering changes.

Original model terms are preserved. Repeated phrases from original tweets can
supplement them; all suggested terms expose their provenance and support.
"""
import math
import re
import unicodedata
from collections import defaultdict
from services.preprocessing.regex_text_cleaner import RegexTextCleaner

_cleaner = RegexTextCleaner()
# General English function words, not a topic-specific blacklist. These only
# constrain supplementary phrases and remove function-word-only model terms.
FUNCTION_WORDS = frozenset('''a an the and or but if then than so as at by for from
in into of on onto to with without about above below over under through between
is are was were be been being am do does did doing have has had having can could
will would shall should may might must i me my mine we us our ours you your yours
he him his she her hers it its they them their theirs this that these those
what which who whom whose when where why how all any each every both either
neither some such no not only just very also too more most much many less few
there here now still already again really get got getting go going gone come
came said say says want wants wanted like likes gonna ve ll re don doesn didn
won isn aren wasn weren im rt via'''.split())


def tokens(text):
    return tuple(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", _cleaner.clean(text or "")).casefold()))


def matches_keyword(text, keyword):
    wanted = set(tokens(keyword))
    return bool(wanted) and wanted.issubset(set(tokens(text)))


def keyword_profiles(groups, documents, query_topics=(), comparison=False):
    """Rank by within-theme minus outside-theme prevalence, then support.

    Repeated IDs count once. Noise is retained in the reference corpus. Terms
    match all their words, ignoring order. Supplementary bigrams must occur
    adjacently in at least two distinct tweets in this theme before inclusion.
    No extra keywords are invented for empty, singleton, or unsupported groups.
    """
    documents = list(documents)
    corpus = {str(tweet_id): (topic, tokens(text)) for tweet_id, topic, text in documents}
    members, postings = defaultdict(set), defaultdict(set)
    phrases = defaultdict(lambda: defaultdict(set))
    query_words = set().union(*(set(tokens(q)) for q in query_topics)) if query_topics else set()
    blocked = FUNCTION_WORDS | query_words | ({'subject'} if comparison else set())
    for tweet_id, (topic, sequence) in corpus.items():
        members[topic].add(tweet_id)
        for word in set(sequence):
            postings[word].add(tweet_id)
        # Keep punctuation as a boundary: do not manufacture phrases across
        # separate sentences, URLs, or mentions removed by preprocessing.
        # Token adjacency alone is insufficient, so check the source below.
    texts = {str(tweet_id): unicodedata.normalize('NFKC', text or '').casefold()
             for tweet_id, _, text in documents}
    for tweet_id, (topic, _) in corpus.items():
        text = texts[tweet_id]
        text = re.sub(r'https?://\S+|@\w+', ' . ', text)
        for segment in re.split(r'[.!?;:\n\r,]+', text):
            sequence = tokens(segment)
            for left, right in zip(sequence, sequence[1:]):
                if len(left) > 1 and len(right) > 1 and left not in blocked and right not in blocked and left != right and not (left.isdigit() and right.isdigit()):
                    phrases[topic][f'{left} {right}'].add(tweet_id)
    profiles = {}
    for topic, raw in groups.items():
        candidates, omitted, seen = [], [], set()
        inside, outside = len(members[topic]), len(corpus) - len(members[topic])
        entries = [(entry, 'model') for entry in raw]
        entries += [(phrase, 'repeated_tweet_phrase') for phrase, ids in sorted(phrases[topic].items()) if len(ids) >= 2]
        for rank, (entry, origin) in enumerate(entries):
            term = str(entry[0] if isinstance(entry, (list, tuple)) else entry).strip()
            words = frozenset(tokens(term))
            reason = None
            if not words:
                reason = 'empty'
            elif comparison and 'subject' in words:
                reason = 'normalization_placeholder'
            elif words.issubset(query_words):
                reason = 'search_terms_only'
            elif words.issubset(FUNCTION_WORDS):
                reason = 'function_words_only'
            elif words in seen:
                reason = 'duplicate'
            seen.add(words)
            ids = set.intersection(*(postings[w] for w in words)) if words else set()
            count = len(ids & members[topic])
            if reason is None and count == 0:
                reason = 'no_supporting_tweets'
            if reason:
                if origin == 'model':
                    omitted.append({'term': term, 'reason': reason})
                continue
            other = len(ids) - count
            prevalence = count / inside if inside else 0
            background = other / outside if outside else None
            weight = entry[1] if isinstance(entry, (list, tuple)) and len(entry) > 1 else None
            if not isinstance(weight, (int, float)) or not math.isfinite(weight):
                weight = None
            candidates.append({
                'term': term, 'tweet_count': count, 'percentage': prevalence * 100,
                'other_tweet_count': other, 'origin': origin,
                'other_percentage': background * 100 if background is not None else None,
                'distinctiveness_pp': (prevalence - background) * 100 if background is not None else None,
                'model_weight': weight, '_rank': rank, '_words': words, '_ids': ids & members[topic],
            })
        candidates.sort(key=lambda c: (-(c['distinctiveness_pp'] if outside else c['percentage']), -c['tweet_count'], -len(c['_words']), c['_rank']))
        selected = []
        for candidate in candidates:
            if any((candidate['_words'] <= kept['_words'] or kept['_words'] <= candidate['_words'])
                   and candidate['_ids'] == kept['_ids'] for kept in selected):
                if candidate['origin'] == 'model':
                    omitted.append({'term': candidate['term'], 'reason': 'redundant_same_support'})
                continue
            selected.append(candidate)
            if len(selected) == 12:
                break
        covered = set().union(*(c['_ids'] for c in selected[:8])) if selected else set()
        for candidate in selected:
            candidate.pop('_rank'); candidate.pop('_words'); candidate.pop('_ids')
        profiles[topic] = {
            'items': selected, 'omitted': omitted, 'tweet_count': inside,
            'covered_tweet_count': len(covered),
            'reference_tweet_count': outside,
            'method': 'model_and_repeated_phrases_evidence_v2',
            'support_definition': 'Tweets containing all keyword words; word order is ignored. URLs and mentions are excluded.',
        }
    return profiles
