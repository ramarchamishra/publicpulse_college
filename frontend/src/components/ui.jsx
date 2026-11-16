import {
  ArrowLeft,
  ArrowRight,
  AlertCircle,
  LoaderCircle,
  Inbox,
} from "lucide-react";
import { number, percent, date } from "../lib/format";
import { useApi } from "../hooks/useApi";
import { useState } from "react";
import { params } from "../services/api";
export function Heading({ eyebrow = "WORKSPACE", title, children, action }) {
  return (
    <header className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{children}</p>
      </div>
      {action}
    </header>
  );
}
export function Empty({ title = "Nothing here yet", children }) {
  return (
    <div className="empty">
      <Inbox size={28} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function ErrorMessage({ error, retry }) {
  return (
    <div className="error" role="alert">
      <AlertCircle size={18} />
      <span>{error?.message || String(error)}</span>
      {retry && <button onClick={retry}>Retry</button>}
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={20} /> Loading workspace…
    </div>
  );
}
export function QueryState({ query, children }) {
  if (query.isPending) return <Loading />;
  if (query.isError)
    return <ErrorMessage error={query.error} retry={query.refetch} />;
  return children(query.data);
}
export function Metrics({ items }) {
  return (
    <div className="metrics">
      {items.map(([label, value, detail]) => (
        <div className="metric" key={label}>
          <span>{label}</span>
          <strong>{typeof value === "number" ? number(value) : value}</strong>
          {detail && <small>{detail}</small>}
        </div>
      ))}
    </div>
  );
}
export function Pagination({ data, onChange }) {
  if (!data || data.pages < 2) return null;
  return (
    <div className="pagination">
      <span>
        {number(data.total)} results · Page {data.page} of {data.pages}
      </span>
      <div>
        <button
          aria-label="Previous page"
          disabled={data.page <= 1}
          onClick={() => onChange(data.page - 1)}
        >
          <ArrowLeft size={16} />
        </button>
        <button
          aria-label="Next page"
          disabled={data.page >= data.pages}
          onClick={() => onChange(data.page + 1)}
        >
          <ArrowRight size={16} />
        </button>
      </div>
    </div>
  );
}
export function Sentiment({ data }) {
  if (!data) return null;
  return (
    <div className="sentiment">
      <div className="sentiment-bar" aria-hidden="true">
        {["positive", "neutral", "negative"].map((label) => (
          <span
            key={label}
            className={label}
            style={{ width: `${data[label].percentage || 0}%` }}
          />
        ))}
      </div>
      <div className="sentiment-legend">
        {["positive", "neutral", "negative"].map((label) => (
          <div key={label}>
            <span className={`dot ${label}`} />
            <span className="capitalize">{label}</span>
            <strong>{percent(data[label].percentage)}</strong>
            <small>{number(data[label].count)}</small>
          </div>
        ))}
      </div>
      <p className="caption">
        {number(data.analyzed_count)} analyzed · {number(data.missing_count)}{" "}
        without results. Percentages use analyzed tweets.
      </p>
      {data.missing_count > 0 && (
        <p className="notice">
          Incomplete coverage: these percentages do not describe all tweets in
          this group.
        </p>
      )}
      <p className="caption">
        Model labels describe tweet tone, not necessarily support for the search
        topic.
      </p>
    </div>
  );
}
export function TweetList({ data }) {
  return data.items.length ? (
    <div className="tweets">
      {data.items.map((tweet) => (
        <article className="tweet" key={tweet.tweet_id}>
          <div className="tweet-meta">
            <strong>{tweet.author}</strong>
            <span>{date(tweet.created_at)}</span>
            <span className={`badge ${tweet.sentiment_label || ""}`}>
              {tweet.sentiment_label || "Not analyzed"}
            </span>
          </div>
          <p>{tweet.text}</p>
          <div className="caption">
            {number(tweet.favorite_count || 0)} likes ·{" "}
            {number(tweet.retweet_count || 0)} reposts
            {tweet.sentiment_confidence != null &&
              ` · Sentiment model score ${percent(tweet.sentiment_confidence * 100)}`}
            {tweet.theme_probability != null &&
              ` · Cluster membership score ${percent(tweet.theme_probability * 100)}`}
          </div>
        </article>
      ))}
    </div>
  ) : (
    <Empty title="No tweets found">
      Try another filter, or collect tweets for this search.
    </Empty>
  );
}
export function Evidence({ path, keyword = "" }) {
  const [page, setPage] = useState(1),
    [q, setQ] = useState(""),
    [sentiment, setSentiment] = useState("");
  const query = useApi(
    `${path}${path.includes("?") ? "&" : "?"}${params({ page, per_page: 10, q, sentiment, keyword })}`,
  );
  return (
    <>
      <div className="filters evidence-filters">
        <label>
          Find text
          <input
            type="search"
            value={q}
            placeholder="Filter evidence…"
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <label>
          Sentiment
          <select
            value={sentiment}
            onChange={(e) => {
              setSentiment(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All sentiment</option>
            <option value="positive">Positive</option>
            <option value="neutral">Neutral</option>
            <option value="negative">Negative</option>
            <option value="missing">Not analyzed</option>
          </select>
        </label>
      </div>
      {keyword && (
        <p className="caption">
          Keyword filter: {keyword}. Matches all keyword words, in any order.
        </p>
      )}
      <QueryState query={query}>
        {(data) => (
          <>
            <p className="caption" role="status">
              {number(data.total)} matching tweets. Filters apply to evidence
              only; the sentiment summary above covers the entire group.
            </p>
            <TweetList data={data} />
            <Pagination data={data} onChange={setPage} />
          </>
        )}
      </QueryState>
    </>
  );
}
export function Keywords({ words = [], profile, selected, onSelect }) {
  if (!profile)
    return (
      <div className="keywords">
        {words.map((word, i) => (
          <span key={i}>{Array.isArray(word) ? word[0] : word}</span>
        ))}
      </div>
    );
  return (
    <section className="keyword-section" aria-label="Theme keywords">
      <div className="section-heading">
        <h3>Evidence-backed keywords</h3>
        {selected && (
          <button onClick={() => onSelect("")}>Clear keyword filter</button>
        )}
      </div>
      <p className="caption">
        Model terms and repeated tweet phrases ranked by how much more common
        they are here than in the rest of this run. Click a term to inspect
        matching tweets.
      </p>
      <div className="keywords">
        {profile.items.slice(0, 8).map((item) => (
          <button
            key={item.term}
            aria-pressed={selected === item.term}
            onClick={() => onSelect?.(selected === item.term ? "" : item.term)}
            title={`${item.tweet_count} of ${profile.tweet_count} unique tweets; ${percent(item.percentage)}`}
          >
            {item.term}
            <small>
              {item.tweet_count} {item.tweet_count === 1 ? "tweet" : "tweets"}
            </small>
          </button>
        ))}
      </div>
      <p className="caption">
        The displayed terms cover{" "}
        {profile.covered_tweet_count ?? profile.items[0]?.tweet_count ?? 0} of{" "}
        {profile.tweet_count} unique tweets. They may describe only part of this
        theme.
      </p>
      {!profile.items.length && (
        <p>
          No distinctive, supported model keywords remain. Inspect the original
          terms and tweets below; a descriptive label is unavailable.
        </p>
      )}
      {profile.comparison && (
        <p className="caption">
          Joint keywords may occur in only one search. Inspect the A / B counts
          in the evidence table.
        </p>
      )}
      <details>
        <summary>Keyword evidence and original model output</summary>
        <p className="caption">
          {profile.support_definition} Reference:{" "}
          {profile.reference_tweet_count} other unique tweets, including
          unclustered tweets. Weights are model relevance weights, not
          probabilities. A keyword is not a factual summary of a theme.
        </p>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Keyword</th>
                <th>Source</th>
                {profile.comparison && <th>A / B tweets</th>}
                <th>In theme</th>
                <th>Elsewhere</th>
                <th>Difference</th>
              </tr>
            </thead>
            <tbody>
              {profile.items.map((item) => (
                <tr key={item.term}>
                  <td>{item.term}</td>
                  <td>
                    {item.origin === "repeated_tweet_phrase"
                      ? "Repeated phrase"
                      : "Model term"}
                  </td>
                  {profile.comparison && (
                    <td>
                      {item.count_a} / {item.count_b}
                    </td>
                  )}
                  <td>
                    {item.tweet_count} · {percent(item.percentage)}
                  </td>
                  <td>
                    {item.other_tweet_count} · {percent(item.other_percentage)}
                  </td>
                  <td>
                    {item.distinctiveness_pp == null
                      ? "No reference"
                      : `${item.distinctiveness_pp.toFixed(1)} pp`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="caption">Original model terms (original order)</p>
        <div className="keywords">
          {words.map((word, i) => (
            <span key={i}>
              {Array.isArray(word)
                ? `${word[0]} · ${Number(word[1]).toPrecision(3)}`
                : word}
            </span>
          ))}
        </div>
        {profile.omitted.length > 0 && (
          <p className="caption">
            Hidden from the concise view:{" "}
            {profile.omitted
              .map(
                (item) => `${item.term} (${item.reason.replaceAll("_", " ")})`,
              )
              .join("; ")}
          </p>
        )}
      </details>
    </section>
  );
}
