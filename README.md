# PublicPulse

PublicPulse is a local discussion research application built with **Python, Flask, SQLite, React, JavaScript, Vite, Tailwind CSS, and Lucide**. It explores saved searches, Cardiff sentiment, independent Theme Discovery runs, and joint comparisons of two searches.

## Run locally

Use Python 3.12 and Node.js 22 or newer. From the repository root:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
npm install --prefix frontend
```

The existing root `venv/`, if present, can also be used; it already contains the analytical dependencies in this workspace. For browsing stored data and running the isolated API tests without ML dependencies, install `backend/requirements-api.txt` instead.

Preserve the existing `backend/.env`. On a fresh installation only, copy `backend/.env.example` to `backend/.env` and configure your X session cookies for collection. No credentials are needed to browse stored data. The frontend's optional `API_PROXY_TARGET` is documented in `frontend/.env.example`; by default Vite proxies `/api` to `http://127.0.0.1:5000`.

Start the backend in one terminal:

```bash
cd backend
.venv/bin/python -m flask --app app run --host 127.0.0.1 --port 5000 --no-reload
# Alternatively, with the existing root environment:
# ../venv/bin/python app.py
```

Start the frontend in another:

```bash
cd frontend
npm run dev
```

Open http://127.0.0.1:5173. Run `npm run build` and `npm run preview` inside `frontend/` to check the production bundle locally (preview uses port 4173 and the same API proxy).

The existing analytical database is `backend/database/publicpulse.db`. Startup does not migrate it. For a genuinely new database, explicitly run `flask --app app init-db` using the configured Python environment from `backend/`. This creates missing original tables without dropping data. Do not use this command to silently change a user's existing database.

## Architecture

- `backend/api/`: thin Flask routes, request validation, consistent JSON errors.
- `backend/database/repositories/explorer_repository.py`: paginated reads and aggregate statistics over the original schema.
- `backend/services/analysis/operations.py`: adapters to collection, Cardiff sentiment, existing Theme Discovery, and independent joint comparison.
- `backend/services/analysis/job_service.py`: one serial worker with duplicate suppression and bounded pending operations.
- `backend/database/repositories/jobs_repository.py`: durable job state and comparison assignments in **a separate database**, `backend/instance/jobs.sqlite3`.
- `frontend/src/pages/`: dashboard, searches, search details, Theme Discovery, comparison.
- `frontend/src/components/`: reusable search selectors, pagination, sentiment bars, evidence, operation status, and other UI.
- `frontend/src/services/api.js`: centralized API communication; React Query manages request caching and polling.

API startup and ordinary reads never import PyTorch, transformers, sentence-transformers, or BERTopic. The worker imports analytical services on demand. Existing model caches are reused within a process. The embedding model remains `BAAI/bge-large-en-v1.5`; sentiment uses `cardiffnlp/twitter-roberta-base-sentiment-latest`. Clustering configuration and algorithms are unchanged.

### Data and calculation semantics

Sentiment counts use only the Cardiff model. Percentages use tweets with sentiment results as the denominator, and missing results are disclosed separately; percentages are null when none are analyzed. The dashboard counts unique stored tweets, including any not currently linked to a search. Search counts include only that search's membership.

Theme Discovery uses one search and saves its own runs, keywords, assignments, and noise. Evidence is ordered by assignment probability where available; it is not an invented summary or generated representative quote.

Comparison takes **two search IDs** and runs the existing joint pipeline. It never matches saved individual themes. The smaller search must contain at least half as many tweets as the larger after optional explicit `#ad` filtering. Overlapping tweets count in both per-search participation totals but once in the unique corpus. Unclustered tweets are shown separately and never called shared discussions. Discussion participation percentages use the full filtered per-search corpus, including noise. Comparison sentiments summarize existing stored Cardiff results; comparison does not automatically run sentiment.

### Operations and limits

Jobs expose `pending`, `running`, `completed`, or `failed`, without invented progress percentages. Identical active inputs return the same job. The default queue accepts up to eight active operations. Status and completed results survive reloads. Interrupted jobs are marked failed on restart and can be explicitly rerun; the system does not silently resume partially completed analytics.

**Run one API process with one worker and no Flask auto-reloader.** An OS file lock prevents two workers from opening the same job store. Keep `PUBLICPULSE_DATABASE` and `PUBLICPULSE_JOB_DATABASE` paired: use a separate job database for each analytical corpus. Relative paths resolve from `backend/`.

The application is for trusted local use, bound to loopback, with no authentication layer. Browser writes go through the Vite same-origin proxy; cross-site browser writes are rejected. Do not expose the development servers to the internet.

ML operations can take minutes on CPU and require significant memory. Cached models can be used with `HF_HUB_OFFLINE=1`; otherwise model downloads require network access. At least seven unique tweets are required by the unchanged UMAP initialization. Passing this minimum does not guarantee useful clusters: sparse vocabularies and small/noise-heavy corpora can still fail in the original pipeline. Errors are retained as failed jobs with server-side diagnostics; no algorithm tuning is performed.

Collection uses the existing Twikit scraper, English relevance filtering, and `Latest`, `Top`, or `Mixed` modes. The requested limit is a maximum, not a guarantee. X credentials, access restrictions, rate limits, and the collector's existing cooldowns can prevent or delay results. A failed collection can leave an empty search record because the existing ingestion service creates the search before collection. Sentiment saves results incrementally; rerunning analyzes only missing tweets. There is no cancellation or distributed processing system.

## API

All successes are `{ "data": ... }`; errors are `{ "error": { "code": "...", "message": "..." } }`. List responses have `items`, `page`, `per_page`, `total`, and `pages`. Page sizes default to 20 and are capped at 100.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Database connectivity |
| GET | `/api/dashboard` | Counts, sentiment, recent searches |
| GET | `/api/searches?q=&page=&per_page=` | Search library |
| POST | `/api/searches` | Queue collection: `topic`, `limit`, `mode` |
| GET | `/api/searches/:id` | Metadata, sentiment, latest run |
| GET | `/api/searches/:id/tweets` | Paged evidence; optional `q` and `sentiment` |
| GET / POST | `/api/searches/:id/sentiment` | Stored summary / queue missing sentiment |
| GET / POST | `/api/searches/:id/theme-runs` | Paged runs / queue discovery |
| GET | `/api/theme-runs/:id` | Themes, keywords, coverage, noise, sentiment |
| GET | `/api/theme-runs/:id/topics/:topic/tweets` | Paged theme evidence; `-1` is noise |
| POST | `/api/comparisons` | Queue `search_id_a`, `search_id_b`, optional `exclude_explicit_ads` |
| GET | `/api/comparisons/:job` | Completed joint result |
| GET | `/api/comparisons/:job/topics/:topic/tweets?search_id=` | Paged evidence by source |
| GET | `/api/jobs?kind=&active=true&page=&per_page=` | Operation history or active jobs |
| GET | `/api/jobs/:id` | Status, failure, completed result |

POST operations return HTTP 202 and a job. Tweet sentiment filters are `positive`, `neutral`, `negative`, and `missing`; omit to show all. Invalid requests return 400/422, missing resources 404, incomplete comparison results 409, full queues 429, and unavailable databases 503. Internal stack traces and credentials are not sent to clients.

## Verification

```bash
backend/.venv/bin/python -m unittest discover -s backend/tests -v
npm test --prefix frontend
npm run build --prefix frontend
```

Backend tests create disposable databases in temporary directories, exercise real repositories/routes, and inject a controlled worker for expensive operations. They cover pagination, model-scoped sentiment, themes, comparison evidence, validation, serialized jobs, duplicate suppression, failures, restart recovery, and model-free reads. Frontend tests cover routing, form submission, selection constraints, saved theme evidence, and failure handling. Test fixtures are confined to tests and are never served as application data.

Live verification details and any environmental limitations are recorded in `VERIFICATION.md`.

## Keyword evidence and analytical usability

Saved themes and comparisons include a `keyword_profile` and a display name. Profiles combine original model candidates with two-word phrases that occur next to each other in at least two distinct tweets in a theme. A general English function-word list constrains supplementary phrases. Query-only terms, comparison subject placeholders, unsupported candidates, and redundant terms are omitted from the concise view. Original model terms remain inspectable.

Candidates are ordered by **within-theme prevalence minus prevalence in the remainder of the run**, then support count, phrase length, and stable candidate order. With no reference corpus, support determines order. At most 12 terms are returned and eight shown as filter buttons. Keyword support counts unique tweet IDs containing all normalized keyword words, in any order, excluding mentions and URLs. This matching definition also powers the evidence endpoint's `keyword` filter. It is not an exact-phrase count, semantic truth score, or calibrated probability. Supplementary candidates expose `origin: repeated_tweet_phrase`; model candidates retain their original relevance weight. The coverage count is the union of tweets matched by the eight displayed terms.

Keyword suggestions can describe only a small part of a weak or generic cluster. Coverage is shown explicitly rather than claiming every theme has a reliable description. The method is designed for the expected fewer-than-1,800 tweets per search, including joint corpora of up to about 3,600 unique tweets. This is a workload expectation, not a new collection restriction.

Theme and comparison evidence endpoints accept `keyword`, `q`, and `sentiment` in addition to pagination. Filters affect the evidence list only; group sentiment summaries remain based on all assigned tweets. Unknown stored sentiment labels count as missing. Case variants are combined, and model confidence averages are weighted by tweet counts.

`GET /api/comparisons/preview?search_id_a=...&search_id_b=...&exclude_explicit_ads=false` reports filtered corpus counts, unique and overlapping tweets, size ratio, and eligibility reasons without loading ML. POST uses the same preflight. This checks input validity, not expected clustering quality.

Completed comparison reads recompute sentiment from current stored Cardiff results over the **saved joint assignments**, so running missing sentiment does not require rerunning clustering. The response declares `sentiment_basis`; older results without evidence retain their saved snapshot. Joint keyword evidence shows separate A/B support, and overlap counts are shown per discussion. Participation differences are expressed in percentage points and are descriptive, not significance tests.

The UI opens the latest saved theme run automatically, supports searching discussion names/keywords, separates shared/one-sided/noise comparison views, and links keyword support directly to paginated evidence. Missing sentiment can be analyzed from either workspace. No scraper is run during validation.
