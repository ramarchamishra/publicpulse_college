import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, CheckCircle2, CircleAlert, Clock3 } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { post } from "../services/api";
import { date } from "../lib/format";
import { ErrorMessage, QueryState, Pagination, Empty } from "./ui";
export function JobRow({ job }) {
  const Icon = {
    pending: Clock3,
    running: LoaderCircle,
    completed: CheckCircle2,
    failed: CircleAlert,
  }[job.status];
  return (
    <div className={`job ${job.status}`}>
      <Icon size={18} className={job.status === "running" ? "spin" : ""} />
      <div>
        <strong className="capitalize">
          {job.kind} · {job.status}
        </strong>
        <p>
          {job.inputs.topic ||
            (job.inputs.search_id
              ? `Search #${job.inputs.search_id}`
              : `Searches #${job.inputs.search_id_a} and #${job.inputs.search_id_b}`)}{" "}
          · {date(job.created_at, true)}
        </p>
        {job.error && <p role="alert">{job.error}</p>}
        {job.status === "pending" && <p>Queued for the local worker.</p>}
        {job.status === "running" && (
          <p>
            Processing. Model loading and analysis may take several minutes.
          </p>
        )}
      </div>
      {job.status === "completed" &&
        (job.kind === "comparison" ? (
          <Link to={`/compare?job=${job.id}`}>View result →</Link>
        ) : job.kind === "themes" ? (
          <Link
            to={`/themes?search=${job.inputs.search_id}&run=${job.result.run_id}`}
          >
            View themes →
          </Link>
        ) : (
          <Link
            to={`/searches/${job.result.search_id || job.inputs.search_id}`}
          >
            View search →
          </Link>
        ))}
    </div>
  );
}
export function JobStatus({ id, onComplete }) {
  const client = useQueryClient(),
    seen = useRef(null);
  const query = useApi(id ? `/jobs/${id}` : null, (q) =>
    ["pending", "running"].includes(q.state.data?.status) ? 1500 : false,
  );
  useEffect(() => {
    if (query.data?.status === "completed" && seen.current !== query.data.id) {
      seen.current = query.data.id;
      client.invalidateQueries();
      onComplete?.(query.data);
    }
  }, [query.data, client, onComplete]);
  if (!id) return null;
  return <QueryState query={query}>{(job) => <JobRow job={job} />}</QueryState>;
}
export function RunButton({
  path,
  payload,
  children,
  onComplete,
  disabled = false,
}) {
  const [id, setId] = useState(null),
    [busy, setBusy] = useState(false);
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => post(path, payload),
    onSuccess: (job) => {
      setId(job.id);
      setBusy(true);
      client.invalidateQueries({ queryKey: ["/jobs?page=1&per_page=10"] });
    },
  });
  const job = useApi(id ? `/jobs/${id}` : null, (q) =>
    ["pending", "running"].includes(q.state.data?.status) ? 1500 : false,
  );
  useEffect(() => {
    if (["completed", "failed"].includes(job.data?.status)) setBusy(false);
  }, [job.data]);
  return (
    <div className="run-action">
      <button
        className="primary"
        disabled={disabled || busy || mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {busy || mutation.isPending ? (
          <LoaderCircle size={16} className="spin" />
        ) : null}
        {children}
      </button>
      {mutation.error && <ErrorMessage error={mutation.error} />}
      <JobStatus id={id} onComplete={onComplete} />
    </div>
  );
}
export function JobHistory({ kind }) {
  const [page, setPage] = useState(1);
  const query = useApi(
    `/jobs?page=${page}&per_page=10${kind ? `&kind=${kind}` : ""}`,
    3000,
  );
  const client = useQueryClient(),
    previous = useRef("");
  useEffect(() => {
    const signature = query.data?.items
      .map((j) => `${j.id}:${j.status}`)
      .join("|");
    if (signature && previous.current && signature !== previous.current)
      client.invalidateQueries({
        predicate: (q) => !String(q.queryKey[0]).startsWith("/jobs"),
      });
    previous.current = signature;
  }, [query.data, client]);
  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Operation history</h2>
        <span className="caption">Saved across reloads</span>
      </div>
      <QueryState query={query}>
        {(data) => (
          <>
            {data.items.length ? (
              data.items.map((job) => <JobRow key={job.id} job={job} />)
            ) : (
              <Empty title="No operations yet">
                Collection and analysis activity will appear here.
              </Empty>
            )}
            <Pagination data={data} onChange={setPage} />
          </>
        )}
      </QueryState>
    </section>
  );
}
