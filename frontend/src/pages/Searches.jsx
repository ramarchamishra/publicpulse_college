import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, ArrowUpRight, Search } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { post, params } from "../services/api";
import { number, date } from "../lib/format";
import {
  Heading,
  QueryState,
  Pagination,
  Empty,
  ErrorMessage,
} from "../components/ui";
import { JobStatus, JobHistory } from "../components/Jobs";
export function SearchRows({ items }) {
  return (
    <div className="search-rows">
      {items.map((s) => (
        <Link className="search-row" key={s.id} to={`/searches/${s.id}`}>
          <div className="search-symbol">
            <Search size={18} />
          </div>
          <div className="search-title">
            <strong>{s.topic}</strong>
            <small>
              #{s.id} · {date(s.scraped_at)} · {s.mode}
            </small>
          </div>
          <span>
            <strong>{number(s.tweet_count)}</strong>
            <small>tweets</small>
          </span>
          <span>
            <strong>{number(s.run_count)}</strong>
            <small>theme runs</small>
          </span>
          <ArrowUpRight size={18} />
        </Link>
      ))}
    </div>
  );
}
function NewSearch() {
  const [id, setId] = useState(null),
    client = useQueryClient();
  const mutation = useMutation({
    mutationFn: (values) => post("/searches", values),
    onSuccess: (job) => {
      setId(job.id);
      client.invalidateQueries();
    },
  });
  return (
    <section className="panel">
      <h2>Collect a new search</h2>
      <p>
        Collect English tweets using your configured X session. Sentiment and
        themes can be run after collection.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const values = new FormData(e.currentTarget);
          mutation.mutate({
            topic: values.get("topic").trim(),
            limit: Number(values.get("limit")),
            mode: values.get("mode"),
          });
        }}
        className="collection-form"
      >
        <label>
          Topic
          <input
            name="topic"
            required
            maxLength={200}
            placeholder="What would you like to explore?"
          />
        </label>
        <label>
          Tweet limit
          <input
            name="limit"
            type="number"
            min="1"
            max="10000"
            defaultValue="100"
            required
          />
        </label>
        <label>
          Search mode
          <select name="mode">
            <option>Latest</option>
            <option>Top</option>
            <option>Mixed</option>
          </select>
        </label>
        <button className="primary" disabled={mutation.isPending} type="submit">
          <Plus size={16} />
          Start collection
        </button>
      </form>
      {mutation.error && <ErrorMessage error={mutation.error} />}
      <JobStatus id={id} />
    </section>
  );
}
export default function Searches() {
  const [url, setUrl] = useSearchParams(),
    [q, setQ] = useState(""),
    [page, setPage] = useState(1);
  const query = useApi(`/searches?${params({ q, page, per_page: 15 })}`);
  return (
    <>
      <Heading
        eyebrow="COLLECTION"
        title="Saved searches"
        action={
          <button
            className="primary"
            onClick={() => setUrl(url.has("new") ? {} : { new: "1" })}
          >
            <Plus size={16} />
            {url.has("new") ? "Close form" : "New search"}
          </button>
        }
      >
        Your starting point for understanding a topic.
      </Heading>
      {url.has("new") && <NewSearch />}
      <section className="panel">
        <div className="section-heading">
          <h2>Search library</h2>
          <label className="filter-label">
            <span className="sr-only">Filter searches</span>
            <input
              type="search"
              placeholder="Filter searches…"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
            />
          </label>
        </div>
        <QueryState query={query}>
          {(data) => (
            <>
              {data.items.length ? (
                <SearchRows items={data.items} />
              ) : (
                <Empty title="No saved searches found">
                  Create a search or adjust your filter.
                </Empty>
              )}
              <Pagination data={data} onChange={setPage} />
            </>
          )}
        </QueryState>
      </section>
      <JobHistory kind="collection" />
    </>
  );
}
