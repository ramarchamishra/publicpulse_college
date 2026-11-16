"""Check the joint adapter's overlap and sparse-sentiment semantics without ML."""
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.analysis.operations import comparison
from api.errors import OperationError


class ComparisonAdapterTests(unittest.TestCase):
    def service(self, unique=7):
        service=Mock()
        service.prepare_comparison.return_value={'unique_tweet_count':unique,'overlap_count':1,'excluded_ads_a':0,'excluded_ads_b':0}
        service.discover_shared_themes.return_value={
            'tweet_search_ids':{'overlap':{1,2},'only_a':{1},'only_b':{2}},
            'topic_assignments':{'overlap':0,'only_a':0,'only_b':-1},
            'tweet_count_a':2,'tweet_count_b':2,'unique_tweet_count':3,
            'theme_count':1,'clustered_count':2,'noise_count':1,
        }
        service.summarize_joint_themes.return_value={'search_id_a':1,'search_id_b':2,'themes':[{'topic_id':0},{'topic_id':-1}]}
        module=types.ModuleType('services.comparisons.search_comparison_service')
        module.SearchComparisonService=Mock(return_value=service)
        return service,module

    def test_joint_service_memberships_and_missing_sentiment(self):
        service,module=self.service()
        store=Mock()
        with patch.dict(sys.modules,{'services.comparisons.search_comparison_service':module}), patch('services.analysis.operations.get_search',side_effect=lambda i:{'id':i}), patch('services.analysis.operations.sentiment_by_tweet_ids',return_value={'overlap':{'label':'positive','confidence':.9}}):
            result=comparison({'search_id_a':1,'search_id_b':2,'exclude_explicit_ads':False},'job',store)
        service.discover_shared_themes.assert_called_once_with(search_id_a=1,search_id_b=2,exclude_explicit_ads=False)
        self.assertEqual(result['sentiment_a']['missing_count'],1)
        self.assertEqual(result['sentiment_b']['positive']['percentage'],100)
        self.assertEqual(result['themes'][0]['sentiment_b']['analyzed_count'],1)
        self.assertEqual(result['themes'][1]['sentiment_b']['missing_count'],1)
        store.save_assignments.assert_called_once()

    def test_unique_corpus_guard_precedes_clustering(self):
        service,module=self.service(unique=6)
        with patch.dict(sys.modules,{'services.comparisons.search_comparison_service':module}):
            with self.assertRaisesRegex(OperationError,'7 unique tweets'):
                comparison({'search_id_a':1,'search_id_b':2,'exclude_explicit_ads':False},'job',Mock())
        service.discover_shared_themes.assert_not_called()
