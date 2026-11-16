import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { params } from "../services/api";
import { QueryState, Pagination } from "./ui";
export default function SearchPicker({ label, value, onChange, exclude }) {
  const [q, setQ] = useState(""),
    [page, setPage] = useState(1);
  const results = useApi(`/searches?${params({ q, page, per_page: 20 })}`);
  const selected = useApi(value ? `/searches/${value}` : null);
  return (
    <div className="picker">
      <label>
        {label}
        <input
          type="search"
          placeholder="Find a saved search…"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
        />
      </label>
      {value && (
        <p className="selection">
          Selected: {selected.data?.topic || `Search #${value}`}
        </p>
      )}
      <QueryState query={results}>
        {(data) => (
          <>
            <select
              aria-label={label}
              value={String(value || "")}
              onChange={(e) => onChange(e.target.value)}
            >
              <option value="">Choose a search</option>
              {value &&
                !data.items.some((s) => String(s.id) === String(value)) && (
                  <option value={value}>
                    {selected.data?.topic || `Search #${value}`}
                  </option>
                )}
              {data.items.map((s) => (
                <option
                  key={s.id}
                  value={s.id}
                  disabled={String(s.id) === String(exclude)}
                >
                  {s.topic} · #{s.id} · {s.tweet_count} tweets
                </option>
              ))}
            </select>
            <Pagination data={data} onChange={setPage} />
          </>
        )}
      </QueryState>
    </div>
  );
}
