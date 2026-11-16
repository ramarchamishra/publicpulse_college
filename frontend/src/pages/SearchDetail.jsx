import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { params } from "../services/api";
import { date } from "../lib/format";
import {
  Heading,
  QueryState,
  Metrics,
  Sentiment,
  TweetList,
  Pagination,
} from "../components/ui";
import { RunButton } from "../components/Jobs";
export default function SearchDetail() {
  const { id } = useParams();
  const detail = useApi(`/searches/${id}`);
  const [page, setPage] = useState(1),
    [sentiment, setSentiment] = useState(""),
    [q, setQ] = useState("");
  const tweets = useApi(
    `/searches/${id}/tweets?${params({ page, per_page: 20, sentiment, q })}`,
  );
  return (
    <QueryState query={detail}>
      {(search) => (
        <>
          <Link className="back-link" to="/searches">
            ← All searches
          </Link>
          <Heading
            eyebrow={`SEARCH #${search.id}`}
            title={search.topic}
            action={
              <Link className="button primary" to={`/themes?search=${id}`}>
                Discover themes →
              </Link>
            }
          >
            {date(search.scraped_at, true)} · {search.mode} · Requested{" "}
            {search.requested_limit} tweets
          </Heading>
          <Metrics
            items={[
              ["Collected tweets", search.tweet_count],
              ["Analyzed tweets", search.sentiment.analyzed_count],
              ["Theme runs", search.run_count],
            ]}
          />
          <section className="panel">
            <div className="section-heading">
              <h2>Sentiment</h2>
              <span className="caption">Cardiff Twitter RoBERTa</span>
            </div>
            <Sentiment data={search.sentiment} />
            {search.sentiment.missing_count > 0 && (
              <RunButton path={`/searches/${id}/sentiment`}>
                Analyze missing sentiment
              </RunButton>
            )}
          </section>
          <section className="panel">
            <div className="section-heading">
              <h2>Tweet explorer</h2>
              <div className="filters">
                <input
                  aria-label="Search tweet text"
                  type="search"
                  placeholder="Search tweet text…"
                  value={q}
                  onChange={(e) => {
                    setQ(e.target.value);
                    setPage(1);
                  }}
                />
                <select
                  aria-label="Filter sentiment"
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
              </div>
            </div>
            <QueryState query={tweets}>
              {(data) => (
                <>
                  <TweetList data={data} />
                  <Pagination data={data} onChange={setPage} />
                </>
              )}
            </QueryState>
          </section>
        </>
      )}
    </QueryState>
  );
}
