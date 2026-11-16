import fcntl
import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from api.errors import APIError, OperationError
from database.connection import database_path
from database.repositories.jobs_repository import JobStore
from services.analysis.operations import execute

logger = logging.getLogger(__name__)


class JobService:
    def __init__(self, path, source_path, max_pending=8, runner=execute):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock_file = open(str(path) + ".lock", "a")
        try:
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock_file.close()
            raise RuntimeError("Another API worker owns this job database. Use one worker.") from None
        self.store = JobStore(path, source_path)
        self.store.recover()
        self.source_path = source_path
        self.max_pending, self.runner = max_pending, runner
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="publicpulse")

    def submit(self, kind, inputs):
        key = kind + ":" + json.dumps(inputs, sort_keys=True)
        with self.lock:
            existing = self.store.active(key)
            if existing:
                return existing
            if self.store.count_active() >= self.max_pending:
                raise APIError("The processing queue is full. Wait for an operation to finish.", 429, "queue_full")
            job_id = uuid.uuid4().hex
            self.store.create(job_id, kind, inputs, key)
            self.executor.submit(self._run, job_id, kind, inputs)
        return self.store.get(job_id)

    def _run(self, job_id, kind, inputs):
        token = database_path.set(self.source_path)
        try:
            self.store.start(job_id)
            result = self.runner(kind, inputs, job_id, self.store)
            self.store.finish(job_id, result=result)
        except OperationError as exc:
            self.store.finish(job_id, error=str(exc))
        except (ImportError, ModuleNotFoundError):
            logger.exception("Dependencies unavailable for operation %s", job_id)
            self.store.finish(job_id, error="A processing dependency is unavailable. Install backend/requirements.txt and inspect the server log.")
        except Exception:
            logger.exception("Operation %s failed", job_id)
            self.store.finish(job_id, error="Processing failed. Check the server log for this operation; models, source access, or the input corpus may be unavailable.")
        finally:
            database_path.reset(token)

    def close(self):
        if self.lock_file.closed:
            return
        self.executor.shutdown(wait=True)
        fcntl.flock(self.lock_file, fcntl.LOCK_UN)
        self.lock_file.close()
