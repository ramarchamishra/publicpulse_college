import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.themes.keyword_service import keyword_profiles, matches_keyword
from services.analysis.sentiment_summary import summarize_sentiment
from services.comparisons.comparison_analytics_service import comparison_summary


class KeywordTests(unittest.TestCase):
    def test_general_topics_preserve_model_candidates_and_ground_support(self):
        for query, phrase, other in [('phone','battery life','camera'), ('election','voter turnout','polling'), ('hospital','waiting times','staffing'), ('football','ticket prices','stadium')]:
            with self.subTest(query=query):
                groups = {0:[[query,.9],[phrase.split()[0],.8],[phrase,.8],['unsupported',.7]], 1:[other]}
                docs = [('1',0,f'{query} {phrase}'),('2',0,f'{phrase} {query}'),('3',1,f'{query} {other}')]
                profile=keyword_profiles(groups,docs,[query])[0]
                self.assertEqual(profile['items'][0]['term'],phrase)
                self.assertEqual(profile['items'][0]['tweet_count'],2)
                self.assertEqual(profile['items'][0]['distinctiveness_pp'],100)
                self.assertEqual(profile['items'][0]['model_weight'],.8)
                self.assertEqual(groups[0][0],[query,.9])
                for item in profile['items']:
                    self.assertEqual(item['tweet_count'],sum(matches_keyword(text,item['term']) for _,topic,text in docs if topic==0))

    def test_overlap_and_placeholder_and_single_cluster(self):
        docs=[('same',0,'Battery life is good'),('same',0,'Battery life is good')]
        p=keyword_profiles({0:[['subject subject',.8],['battery life',.4]]},docs,comparison=True)[0]
        self.assertEqual(p['tweet_count'],1)
        self.assertEqual(p['items'][0]['tweet_count'],1)
        self.assertIsNone(p['items'][0]['other_percentage'])
        self.assertEqual(p['omitted'][0]['reason'],'normalization_placeholder')
        self.assertEqual(keyword_profiles({0:['subject']},[('a',0,'subject')])[0]['items'][0]['term'],'subject')

    def test_unicode_mentions_urls_and_all_words_matching(self):
        self.assertTrue(matches_keyword('ＣＡＦÉ prices have risen','café prices'))
        self.assertTrue(matches_keyword('#Battery has long life','battery life'))
        self.assertFalse(matches_keyword('@battery https://x.com/life','battery life'))
        self.assertFalse(matches_keyword('batteries lifelong','battery life'))
        self.assertFalse(matches_keyword('any text',''))

    def test_repeated_phrases_provenance_and_sentence_boundaries(self):
        docs=[('1',0,'Solar panels reduce bills. Clean air matters.'),('2',0,'Solar panels improve homes. Clean air matters.'),('3',1,'Traffic congestion')]
        profile=keyword_profiles({0:[]},docs)[0]
        terms={item['term']:item for item in profile['items']}
        self.assertEqual(terms['solar panels']['origin'],'repeated_tweet_phrase')
        self.assertEqual(terms['solar panels']['tweet_count'],2)
        self.assertNotIn('bills clean',terms)
        self.assertNotIn('homes clean',terms)
        self.assertEqual(profile['covered_tweet_count'],2)

    def test_empty_and_noise_only(self):
        self.assertEqual(keyword_profiles({},[('a',-1,'anything')]),{})
        self.assertEqual(keyword_profiles({0:['missing']},[])[0]['items'],[])

    def test_case_variants_weighted_confidence_and_missing_labels(self):
        s=summarize_sentiment([
            {'label':'Positive','tweet_count':1,'average_confidence':.9},
            {'label':'positive','tweet_count':3,'average_confidence':.5},
            {'label':'unexpected','tweet_count':1,'average_confidence':.8}],5)
        self.assertEqual(s['positive']['count'],4)
        self.assertEqual(s['positive']['percentage'],100)
        self.assertAlmostEqual(s['positive']['average_confidence'],.6)
        self.assertEqual(s['missing_count'],1)

    def test_comparison_current_sentiment_unique_counts_and_legacy_keywords(self):
        result={'search_id_a':1,'search_id_b':2,'search_a':{'topic':'phone'},'search_b':{'topic':'tablet'},'themes':[{'topic_id':0,'keywords':['subject','battery']}], 'sentiment_a':{'missing_count':99}}
        rows=[{'tweet_id':'a','topic_id':0,'search_id':1,'text':'Battery','label':'positive','confidence':.9}, {'tweet_id':'a','topic_id':0,'search_id':2,'text':'Battery','label':'positive','confidence':.9}, {'tweet_id':'b','topic_id':0,'search_id':2,'text':'Battery','label':None,'confidence':None}]
        s=comparison_summary(result,rows)
        self.assertEqual(s['themes'][0]['unique_tweet_count'],2)
        self.assertEqual(s['themes'][0]['overlap_count'],1)
        self.assertEqual(s['themes'][0]['keyword_profile']['items'][0]['tweet_count'],2)
        self.assertEqual(s['sentiment_b']['missing_count'],1)
        self.assertEqual(result['sentiment_a']['missing_count'],99)
        rows[-1].update(label='negative',confidence=.8)
        refreshed=comparison_summary(result,rows)
        self.assertEqual(refreshed['sentiment_b']['missing_count'],0)
        self.assertEqual(refreshed['sentiment_b']['negative']['percentage'],50)

if __name__=='__main__':unittest.main()
