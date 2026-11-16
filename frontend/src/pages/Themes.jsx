import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { date, percent } from "../lib/format";
import SearchPicker from "../components/SearchPicker";
import { RunButton, JobHistory } from "../components/Jobs";
import {
  Heading,
  QueryState,
  Metrics,
  Sentiment,
  Keywords,
  Evidence,
  Empty,
  Pagination,
} from "../components/ui";
function ThemeResult({ id }) {
  const query = useApi(`/theme-runs/${id}`),
    [selected, setSelected] = useState(null),
    [filter, setFilter] = useState(""),
    [keyword, setKeyword] = useState("");
  return (
    <QueryState query={query}>
      {(result) => {
        const groups = [...result.themes, result.noise].filter((t) =>
          `${t.display_name || t.name} ${(t.keywords || []).map((w) => w[0]).join(" ")}`
            .toLowerCase()
            .includes(filter.toLowerCase()),
        );
        const theme =
          groups.find((t) => t.bertopic_topic_id === selected) || groups[0];
        return (
          <>
            <Metrics
              items={[
                ["Discovered themes", result.theme_count],
                [
                  "Clustered tweets",
                  result.clustered_count,
                  `${percent(result.clustered_percentage)} coverage`,
                ],
                [
                  "Unclustered tweets",
                  result.noise_count,
                  "Not assigned to a discussion",
                ],
              ]}
            />
            <p className="caption">
              Run #{result.run.id} · {date(result.run.created_at, true)} ·{" "}
              {result.run.embedding_model}
            </p>
            {!result.theme_count && (
              <Empty title="No distinct themes in this run">
                The pipeline left these tweets unclustered. You can inspect them
                below.
              </Empty>
            )}
            {result.sentiment?.missing_count > 0 && (
              <RunButton path={`/searches/${result.run.search_id}/sentiment`}>
                Analyze missing sentiment for this search
              </RunButton>
            )}
            <label className="discussion-filter">
              Find a discussion
              <input
                type="search"
                value={filter}
                placeholder="Filter theme names and keywords…"
                onChange={(e) => {
                  setFilter(e.target.value);
                  setKeyword("");
                }}
              />
            </label>
            {!theme ? (
              <Empty title="No matching discussions">
                Try another keyword.
              </Empty>
            ) : (
              <div className="explorer">
                <section className="panel theme-list">
                  <h2>Discussions</h2>
                  {groups.map((t) => (
                    <button
                      className={
                        theme.bertopic_topic_id === t.bertopic_topic_id
                          ? "selected"
                          : ""
                      }
                      key={t.bertopic_topic_id}
                      aria-pressed={
                        theme.bertopic_topic_id === t.bertopic_topic_id
                      }
                      onClick={() => {
                        setSelected(t.bertopic_topic_id);
                        setKeyword("");
                      }}
                    >
                      <strong>
                        {t.keyword_profile ? `#${t.bertopic_topic_id} · ` : ""}
                        {t.display_name || t.name}
                      </strong>
                      <small>
                        {t.tweet_count} tweets ·{" "}
                        {percent(t.discussion_share_percentage)}
                      </small>
                      {t.keyword_profile && (
                        <small>
                          Keyword coverage:{" "}
                          {t.keyword_profile.covered_tweet_count}/
                          {t.tweet_count} tweets
                        </small>
                      )}
                    </button>
                  ))}
                </section>
                <section className="panel">
                  <div className="section-heading">
                    <h2>
                      {theme.keyword_profile
                        ? `Theme ${theme.bertopic_topic_id} · `
                        : ""}
                      {theme.display_name || theme.name}
                    </h2>
                    <span className="badge">{theme.tweet_count} tweets</span>
                  </div>
                  <Keywords
                    words={theme.keywords}
                    profile={theme.keyword_profile}
                    selected={keyword}
                    onSelect={setKeyword}
                  />
                  <Sentiment data={theme.sentiment} />
                  <h3>Supporting tweets</h3>
                  <p className="caption">
                    Ordered by cluster membership score where available; this is
                    not a calibrated accuracy probability.
                  </p>
                  <Evidence
                    key={`${id}:${theme.bertopic_topic_id}:${keyword}`}
                    keyword={keyword}
                    path={`/theme-runs/${id}/topics/${theme.bertopic_topic_id}/tweets`}
                  />
                </section>
              </div>
            )}
          </>
        );
      }}
    </QueryState>
  );
}
function Runs({ search, run, onRun }) {
  const [page, setPage] = useState(1);
  const query = useApi(
    `/searches/${search}/theme-runs?page=${page}&per_page=20`,
  );
  useEffect(() => {
    if (!run && page === 1 && query.data?.items.length)
      onRun(String(query.data.items[0].id));
  }, [run, page, query.data, onRun]);
  return (
    <QueryState query={query}>
      {(data) => (
        <>
          {data.items.length ? (
            <>
              <label>
                Saved analysis run
                <select
                  value={run || ""}
                  onChange={(e) => onRun(e.target.value)}
                >
                  <option value="">Choose a saved run</option>
                  {run &&
                    !data.items.some((r) => String(r.id) === String(run)) && (
                      <option value={run}>Run #{run}</option>
                    )}
                  {data.items.map((r) => (
                    <option key={r.id} value={r.id}>
                      Run #{r.id} · {date(r.created_at, true)} · {r.theme_count}{" "}
                      themes
                    </option>
                  ))}
                </select>
              </label>
              <Pagination data={data} onChange={setPage} />
            </>
          ) : (
            <p>No saved runs. Start discovery to analyze this search.</p>
          )}
        </>
      )}
    </QueryState>
  );
}
export default function Themes() {
  const [url, setUrl] = useSearchParams();
  const search = url.get("search"),
    run = url.get("run");
  return (
    <>
      <Heading eyebrow="ANALYSIS" title="Theme Discovery">
        Find the distinct discussions within a saved search.
      </Heading>
      <section className="panel">
        <div className="two-col">
          <SearchPicker
            label="Search to explore"
            value={search}
            onChange={(value) => setUrl(value ? { search: value } : {})}
          />
          {search && (
            <Runs
              key={search}
              search={search}
              run={run}
              onRun={(value) =>
                setUrl(value ? { search, run: value } : { search })
              }
            />
          )}
        </div>
        {search && (
          <RunButton
            key={search}
            path={`/searches/${search}/theme-runs`}
            onComplete={(job) =>
              setUrl({ search, run: String(job.result.run_id) })
            }
          >
            Run Theme Discovery
          </RunButton>
        )}
      </section>
      {run ? (
        <ThemeResult key={run} id={run} />
      ) : (
        <Empty
          title={
            search
              ? "Choose a run or discover themes"
              : "Choose a search to get started"
          }
        >
          Discovery uses the existing embedding and clustering pipeline. Results
          may take several minutes.
        </Empty>
      )}
      <JobHistory kind="themes" />
    </>
  );
}
