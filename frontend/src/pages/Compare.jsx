import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { percent } from "../lib/format";
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
} from "../components/ui";
function ComparisonResult({ id }) {
  const query = useApi(`/comparisons/${id}`),
    [selected, setSelected] = useState(null),
    [kind, setKind] = useState("all"),
    [filter, setFilter] = useState(""),
    [keyword, setKeyword] = useState("");
  return (
    <QueryState query={query}>
      {(result) => {
        const visible = result.themes.filter(
          (t) =>
            (kind === "all" ||
              (kind === "shared" && t.is_shared) ||
              (kind === "noise" && t.topic_id === -1) ||
              (kind === "a" &&
                t.topic_id !== -1 &&
                t.count_a > 0 &&
                t.count_b === 0) ||
              (kind === "b" &&
                t.topic_id !== -1 &&
                t.count_b > 0 &&
                t.count_a === 0)) &&
            `${t.display_name || ""} ${t.keywords.join(" ")}`
              .toLowerCase()
              .includes(filter.toLowerCase()),
        );
        const theme =
          visible.find((t) => t.topic_id === selected) ||
          visible.find((t) => t.is_shared) ||
          visible[0];
        return (
          <>
            <div className="section-heading">
              <h2>
                {result.search_a.topic} <span className="muted"> / </span>{" "}
                {result.search_b.topic}
              </h2>
              <span className="badge">Joint analysis</span>
            </div>
            <Metrics
              items={[
                ["Unique corpus", result.unique_tweet_count],
                [
                  "Shared discussions",
                  result.themes.filter((t) => t.is_shared).length,
                ],
                ["Overlapping tweets", result.overlap_count],
                ["Unclustered tweets", result.noise_count],
              ]}
            />
            <p className="caption">
              Overlapping tweets belong to both searches and count once in the
              unique corpus. Participation uses each search’s filtered tweet
              corpus, including unclustered tweets.
              {result.exclude_explicit_ads &&
                ` Explicit ads excluded: ${result.excluded_ads_a} from A, ${result.excluded_ads_b} from B.`}
            </p>
            <p className="caption">
              Sentiment:{" "}
              {result.sentiment_basis === "current_stored_results"
                ? "current stored model results for the saved comparison assignments"
                : "snapshot saved with this comparison"}
              . Cluster assignments remain fixed.
            </p>
            <div className="two-col">
              {[
                [
                  "A",
                  result.search_a,
                  result.tweet_count_a,
                  result.sentiment_a,
                ],
                [
                  "B",
                  result.search_b,
                  result.tweet_count_b,
                  result.sentiment_b,
                ],
              ].map(([label, search, count, sentiment]) => (
                <section className="panel" key={label}>
                  <div className="section-heading">
                    <h2>
                      {label} · {search.topic}
                    </h2>
                    <span className="badge">{count} tweets</span>
                  </div>
                  <Sentiment data={sentiment} />
                  {sentiment.missing_count > 0 && (
                    <RunButton path={`/searches/${search.id}/sentiment`}>
                      Analyze missing sentiment for {label}
                    </RunButton>
                  )}
                </section>
              ))}
            </div>
            <div className="filters evidence-filters">
              <label>
                Find a discussion
                <input
                  type="search"
                  value={filter}
                  onChange={(e) => {
                    setFilter(e.target.value);
                    setKeyword("");
                  }}
                />
              </label>
              <label>
                Discussion type
                <select
                  value={kind}
                  onChange={(e) => {
                    setKind(e.target.value);
                    setKeyword("");
                  }}
                >
                  <option value="all">All discussions</option>
                  <option value="shared">Shared</option>
                  <option value="a">A only</option>
                  <option value="b">B only</option>
                  <option value="noise">Unclustered</option>
                </select>
              </label>
            </div>
            {theme ? (
              <div className="explorer">
                <section className="panel theme-list">
                  <h2>Joint discussions</h2>
                  {visible.map((t) => (
                    <button
                      key={t.topic_id}
                      className={
                        theme.topic_id === t.topic_id ? "selected" : ""
                      }
                      aria-pressed={theme.topic_id === t.topic_id}
                      onClick={() => {
                        setSelected(t.topic_id);
                        setKeyword("");
                      }}
                    >
                      <strong>
                        {t.topic_id === -1
                          ? "Unclustered tweets"
                          : t.display_name ||
                            t.keywords.join(", ") ||
                            `Discussion ${t.topic_id}`}
                      </strong>
                      <small>
                        {t.is_shared
                          ? "Shared discussion"
                          : t.topic_id === -1
                            ? "Not a shared discussion"
                            : "One search only"}{" "}
                        · A {t.count_a} / B {t.count_b}
                      </small>
                    </button>
                  ))}
                </section>
                <section className="panel">
                  <h2>
                    {theme.topic_id === -1
                      ? "Unclustered tweets"
                      : `Discussion ${theme.topic_id}`}
                  </h2>
                  <Keywords
                    words={theme.keyword_candidates || theme.keywords}
                    profile={theme.keyword_profile}
                    selected={keyword}
                    onSelect={setKeyword}
                  />
                  {theme.unique_tweet_count != null && (
                    <p className="caption">
                      {theme.unique_tweet_count} unique tweets ·{" "}
                      {theme.overlap_count} belong to both searches.
                    </p>
                  )}
                  <p className="caption">
                    Participation difference (A − B):{" "}
                    {(theme.share_a - theme.share_b).toFixed(1)} percentage
                    points. Descriptive corpus shares, not statistical
                    significance.
                  </p>
                  <div className="participation">
                    {[
                      ["A", theme.share_a, theme.count_a],
                      ["B", theme.share_b, theme.count_b],
                    ].map(([label, share, count]) => (
                      <div key={label}>
                        <span>
                          {label} · {count} tweets
                        </span>
                        <div className="track">
                          <div style={{ width: `${share}%` }} />
                        </div>
                        <strong>{percent(share)}</strong>
                      </div>
                    ))}
                  </div>
                  <div className="two-col">
                    {[
                      ["A", result.search_a, theme.sentiment_a],
                      ["B", result.search_b, theme.sentiment_b],
                    ].map(([label, search, sentiment]) => (
                      <div key={label}>
                        <h3>
                          {label} · {search.topic}
                        </h3>
                        <Sentiment data={sentiment} />
                        <h3>Supporting tweets</h3>
                        <Evidence
                          key={`${id}:${theme.topic_id}:${search.id}:${keyword}`}
                          keyword={keyword}
                          path={`/comparisons/${id}/topics/${theme.topic_id}/tweets?search_id=${search.id}`}
                        />
                      </div>
                    ))}
                  </div>
                </section>
              </div>
            ) : (
              <Empty title="No matching discussions">
                Adjust the text or discussion-type filter.
              </Empty>
            )}
          </>
        );
      }}
    </QueryState>
  );
}
export default function Compare() {
  const [url, setUrl] = useSearchParams(),
    [a, setA] = useState(""),
    [b, setB] = useState(""),
    [ads, setAds] = useState(false);
  const id = url.get("job");
  const preview = useApi(
    a && b && a !== b
      ? `/comparisons/preview?search_id_a=${a}&search_id_b=${b}&exclude_explicit_ads=${ads}`
      : null,
  );
  return (
    <>
      <Heading eyebrow="COMPARATIVE ANALYSIS" title="Where conversations meet">
        Analyze two searches together to discover shared discussions and
        differences.
      </Heading>
      <section className="panel">
        <div className="two-col">
          <SearchPicker
            label="Search A"
            value={a}
            exclude={b}
            onChange={setA}
          />
          <SearchPicker
            label="Search B"
            value={b}
            exclude={a}
            onChange={setB}
          />
        </div>
        <div className="comparison-controls">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={ads}
              onChange={(e) => setAds(e.target.checked)}
            />
            Exclude tweets explicitly marked #ad
          </label>
          <RunButton
            key={`${a}:${b}:${ads}`}
            path="/comparisons"
            payload={{
              search_id_a: Number(a),
              search_id_b: Number(b),
              exclude_explicit_ads: ads,
            }}
            disabled={!a || !b || a === b || !preview.data?.eligible}
            onComplete={(job) => setUrl({ job: job.id })}
          >
            Compare topics
          </RunButton>
        </div>
        {a && b && a !== b && (
          <QueryState query={preview}>
            {(data) => (
              <div aria-live="polite">
                <p>
                  Ready corpus: A {data.tweet_count_a} · B {data.tweet_count_b}{" "}
                  · {data.unique_tweet_count} unique · {data.overlap_count}{" "}
                  overlapping tweets.
                </p>
                {data.reasons.map((reason) => (
                  <p className="notice" key={reason}>
                    {reason}
                  </p>
                ))}
                {data.eligible && (
                  <p className="caption">
                    Eligible for joint analysis. This checks input sizes, not
                    clustering quality.
                  </p>
                )}
              </div>
            )}
          </QueryState>
        )}
        <p className="caption">
          Choose two different searches of comparable size. The smaller corpus
          must be at least half the larger. Individual Theme Discovery runs are
          not required.
        </p>
      </section>
      {id ? (
        <ComparisonResult key={id} id={id} />
      ) : (
        <Empty title="Two topics. One shared view.">
          Select two saved searches or open a completed comparison below.
        </Empty>
      )}
      <JobHistory kind="comparison" />
    </>
  );
}
