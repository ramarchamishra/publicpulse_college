"""Integration tests use temporary SQLite files, never the saved corpus."""
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from database.connection import database_path, get_connection
from database.schema import create_tables
from services.analysis.sentiment_summary import MODEL_NAME
from services.analysis.job_service import JobService
from api.errors import OperationError


class APIIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name) / 'data.db')
        self.jobs = str(Path(self.temp.name) / 'jobs.sqlite3')
        token = database_path.set(self.db)
        create_tables()
        conn = get_connection()
        conn.executemany('INSERT INTO searches(id,topic,requested_limit,mode) VALUES(?,?,?,?)', [(1,'Alpha',10,'Latest'),(2,'Beta',10,'Top'),(3,'Empty',10,'Latest')])
        for i in range(10):
            conn.execute('INSERT INTO tweets(tweet_id,text,author) VALUES(?,?,?)', (str(i),f'Evidence tweet {i}','author'))
            for search_id in [1,2]:
                conn.execute('INSERT INTO search_tweets VALUES(?,?)',(search_id,str(i)))
        conn.execute('INSERT INTO sentiment_results(tweet_id,model_name,label,confidence) VALUES(?,?,?,?)',('0',MODEL_NAME,'Positive',.9))
        conn.execute('INSERT INTO sentiment_results(tweet_id,model_name,label,confidence) VALUES(?,?,?,?)',('1','other-model','Negative',.9))
        conn.execute("INSERT INTO theme_discovery_runs(id,search_id,embedding_model,pipeline_version) VALUES(1,1,'existing','v1')")
        conn.execute('INSERT INTO themes(id,run_id,bertopic_topic_id,name,keywords) VALUES(1,1,0,?,?)',('A discussion',json.dumps([['evidence',.9]])))
        conn.execute("INSERT INTO theme_assignments(run_id,tweet_id,theme_id,bertopic_topic_id,probability) VALUES(1,'0',1,0,.8)")
        conn.execute("INSERT INTO theme_assignments(run_id,tweet_id,theme_id,bertopic_topic_id) VALUES(1,'1',NULL,-1)")
        conn.commit(); conn.close(); database_path.reset(token)
        self.calls=[]
        def runner(kind, inputs, job_id, store):
            self.calls.append((kind,inputs))
            return {'search_id':inputs.get('search_id',1),'run_id':1}
        self.app=create_app({'TESTING':True,'DATABASE':self.db,'JOB_DATABASE':self.jobs,'JOB_RUNNER':runner})
        self.client=self.app.test_client()

    def tearDown(self):
        self.app.extensions['jobs'].close()
        self.temp.cleanup()

    def data(self,path):
        response=self.client.get('/api'+path)
        self.assertEqual(response.status_code,200,response.json)
        return response.json['data']

    def test_reads_and_pagination(self):
        self.assertEqual(self.data('/health')['status'],'ok')
        self.assertEqual(self.data('/dashboard')['tweet_count'],10)
        self.assertEqual(self.data('/searches?per_page=1&page=2')['items'][0]['id'],2)
        self.assertEqual(self.data('/searches?q=Alpha')['total'],1)
        page=self.data('/searches/1/tweets?per_page=3&page=2')
        self.assertEqual(len(page['items']),3); self.assertEqual(page['total'],10)
        self.assertEqual(self.data('/searches/1/tweets?sentiment=positive')['total'],1)
        self.assertEqual(self.data('/searches/1/tweets?sentiment=missing')['total'],9)
        self.assertEqual(self.data('/searches/1/tweets?q=tweet%202')['total'],1)
        summary=self.data('/searches/1')['sentiment']
        self.assertEqual(summary['positive']['percentage'],100)
        self.assertEqual(summary['missing_count'],9)
        self.assertIsNone(self.data('/searches/3/sentiment')['positive']['percentage'])

    def test_theme_results(self):
        self.assertEqual(self.data('/searches/1/theme-runs')['total'],1)
        result=self.data('/theme-runs/1')
        self.assertEqual(result['noise_count'],1)
        self.assertEqual(result['themes'][0]['sentiment']['positive']['percentage'],100)
        self.assertEqual(self.data('/theme-runs/1/topics/0/tweets')['items'][0]['tweet_id'],'0')
        self.assertEqual(self.data('/theme-runs/1/topics/-1/tweets')['total'],1)
        self.assertEqual(self.client.get('/api/theme-runs/1/topics/99/tweets').status_code,404)

    def test_validation_and_errors(self):
        for path in ['/searches?page=0','/searches?per_page=101','/searches/1/tweets?sentiment=bad']:
            self.assertEqual(self.client.get('/api'+path).status_code,400)
        self.assertEqual(self.client.get('/api/searches/99').status_code,404)
        self.assertEqual(self.client.post('/api/searches',json={'topic':' '}).status_code,400)
        self.assertEqual(self.client.post('/api/searches',json={'topic':'A','limit':True}).status_code,400)
        self.assertEqual(self.client.post('/api/comparisons',json={'search_id_a':1,'search_id_b':1}).status_code,422)
        self.assertEqual(self.client.post('/api/searches/3/theme-runs',json={}).status_code,422)
        self.assertEqual(self.client.post('/api/searches',json={'topic':'A'},headers={'Sec-Fetch-Site':'cross-site'}).status_code,403)
        self.assertNotIn('traceback',str(self.client.get('/api/unknown').json).lower())

    def test_operations_and_comparison_evidence(self):
        for path,body,kind in [('/searches',{'topic':'New'},'collection'),('/searches/1/sentiment',{},'sentiment'),('/searches/1/theme-runs',{},'themes'),('/comparisons',{'search_id_a':1,'search_id_b':2},'comparison')]:
            response=self.client.post('/api'+path,json=body)
            self.assertEqual(response.status_code,202,response.json)
            job_id=response.json['data']['id']
            for _ in range(100):
                job=self.data('/jobs/'+job_id)
                if job['status'] in ('completed','failed'):break
                time.sleep(.01)
            self.assertEqual(job['status'],'completed')
            self.assertEqual(job['kind'],kind)
        store=self.app.extensions['jobs'].store
        store.save_assignments(job_id,{'0':0},{'0':{1,2}})
        store.finish(job_id,result={'search_id_a':1,'search_id_b':2,'themes':[{'topic_id':0}]})
        for search_id in [1,2]:
            page=self.data(f'/comparisons/{job_id}/topics/0/tweets?search_id={search_id}')
            self.assertEqual(page['total'],1);self.assertEqual(page['items'][0]['tweet_id'],'0')
        self.assertEqual(self.client.get(f'/api/comparisons/{job_id}/topics/0/tweets?search_id=3').status_code,400)

    def test_keyword_evidence_sentiment_filters_and_comparison_preflight(self):
        summary = self.data('/theme-runs/1')
        profile = summary['themes'][0]['keyword_profile']
        self.assertEqual(profile['items'][0]['tweet_count'], 1)
        self.assertEqual(self.data('/theme-runs/1/topics/0/tweets?keyword=evidence&sentiment=positive')['total'], 1)
        self.assertEqual(self.data('/theme-runs/1/topics/0/tweets?keyword=absent')['total'], 0)
        self.assertEqual(self.client.get('/api/theme-runs/1/topics/0/tweets?sentiment=bad').status_code, 400)
        preview = self.data('/comparisons/preview?search_id_a=1&search_id_b=2')
        self.assertEqual(preview['overlap_count'], 10)
        self.assertEqual(preview['unique_tweet_count'], 10)
        self.assertTrue(preview['eligible'])
        token=database_path.set(self.db)
        conn=get_connection()
        conn.execute("DELETE FROM search_tweets WHERE tweet_id IN ('6','7','8','9')")
        conn.commit();conn.close();database_path.reset(token)
        preview=self.data('/comparisons/preview?search_id_a=1&search_id_b=2')
        self.assertFalse(preview['eligible'])
        self.assertEqual(self.client.post('/api/comparisons',json={'search_id_a':1,'search_id_b':2}).status_code,422)

    def test_saved_comparison_refreshes_sentiment_without_reclustering(self):
        store=self.app.extensions['jobs'].store
        store.create('saved','comparison',{'search_id_a':1,'search_id_b':2},'saved')
        store.save_assignments('saved',{'0':0,'1':0},{'0':{1,2},'1':{2}})
        store.finish('saved',result={'search_id_a':1,'search_id_b':2,'search_a':{'topic':'Alpha'},'search_b':{'topic':'Beta'},'themes':[{'topic_id':0,'keywords':['evidence']}], 'sentiment_b':{'missing_count':2}})
        result=self.data('/comparisons/saved')
        self.assertEqual(result['sentiment_b']['missing_count'],1)
        self.assertEqual(result['themes'][0]['overlap_count'],1)
        self.assertEqual(self.data('/comparisons/saved/topics/0/tweets?search_id=2&keyword=evidence&sentiment=missing')['total'],1)
        token=database_path.set(self.db);conn=get_connection()
        conn.execute('INSERT INTO sentiment_results(tweet_id,model_name,label,confidence) VALUES(?,?,?,?)',('1',MODEL_NAME,'negative',.8))
        conn.commit();conn.close();database_path.reset(token)
        refreshed=self.data('/comparisons/saved')
        self.assertEqual(refreshed['sentiment_b']['negative']['percentage'],50)
        self.assertEqual(refreshed['sentiment_b']['missing_count'],0)
        self.assertEqual(self.calls,[])

    def test_reads_do_not_import_ml(self):
        self.data('/dashboard'); self.data('/theme-runs/1')
        for name in ['torch','transformers','sentence_transformers','bertopic']:
            self.assertNotIn(name,sys.modules)


class JobTests(unittest.TestCase):
    def test_serial_dedup_failure_and_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'jobs.sqlite3'
            entered=threading.Event();release=threading.Event();calls=[]
            def runner(kind,inputs,*_):
                calls.append(inputs['n']);entered.set();release.wait(3)
                if inputs['n']==2:raise OperationError('Expected failure')
                return {'done':True}
            service=JobService(path,Path(directory)/'data.db',runner=runner)
            try:
                first=service.submit('sentiment',{'n':1});self.assertTrue(entered.wait(2))
                self.assertEqual(service.submit('sentiment',{'n':1})['id'],first['id'])
                second=service.submit('sentiment',{'n':2})
                self.assertEqual(calls,[1]);self.assertEqual(second['status'],'pending')
                with self.assertRaises(RuntimeError):JobService(path,'unused')
                release.set();service.close()
                self.assertEqual(service.store.get(first['id'])['status'],'completed')
                self.assertEqual(service.store.get(second['id'])['error'],'Expected failure')
                service.store.create('interrupted','themes',{},'interrupted')
                reopened=JobService(path,'unused')
                self.assertEqual(reopened.store.get('interrupted')['status'],'failed');reopened.close()
            finally:release.set();service.close()

if __name__=='__main__':unittest.main()
