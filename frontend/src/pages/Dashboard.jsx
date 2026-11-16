import { Link } from "react-router-dom";
import { Plus, ArrowUpRight, Layers3, GitCompareArrows } from "lucide-react";
import { useApi } from "../hooks/useApi";
import {
  Heading,
  QueryState,
  Metrics,
  Sentiment,
  Empty,
} from "../components/ui";
import { SearchRows } from "./Searches";
import { JobHistory } from "../components/Jobs";
export default function Dashboard() {
  const query = useApi("/dashboard");
  return (
    <>
      <Heading
        eyebrow="OVERVIEW"
        title="A pulse on the conversation"
        action={
          <Link className="button primary" to="/searches?new=1">
            <Plus size={16} />
            New search
          </Link>
        }
      >
        Explore what people say, how they feel, and where discussions meet.
      </Heading>
      <QueryState query={query}>
        {(data) => (
          <>
            <Metrics
              items={[
                ["Saved searches", data.search_count, "Your collected topics"],
                ["Unique tweets", data.tweet_count, "Across the saved corpus"],
                [
                  "Theme runs",
                  data.theme_run_count,
                  "Independent discovery runs",
                ],
              ]}
            />
            <div className="dashboard-grid">
              <section className="panel">
                <div className="section-heading">
                  <h2>Sentiment overview</h2>
                  <span className="caption">All stored tweets</span>
                </div>
                <Sentiment data={data.sentiment} />
              </section>
              <section className="panel">
                <h2>Explore your data</h2>
                <Link className="action-link" to="/themes">
                  <Layers3 size={20} />
                  <div>
                    <strong>Discover themes</strong>
                    <small>Find discussions within one search</small>
                  </div>
                  <ArrowUpRight size={18} />
                </Link>
                <Link className="action-link" to="/compare">
                  <GitCompareArrows size={20} />
                  <div>
                    <strong>Compare topics</strong>
                    <small>Discover discussions across two searches</small>
                  </div>
                  <ArrowUpRight size={18} />
                </Link>
              </section>
            </div>
            <section className="panel">
              <div className="section-heading">
                <h2>Recent searches</h2>
                <Link to="/searches">View all →</Link>
              </div>
              {data.recent_searches.length ? (
                <SearchRows items={data.recent_searches} />
              ) : (
                <Empty title="Start with a conversation">
                  <Link to="/searches?new=1">Create your first search</Link> to
                  collect tweets and explore their discussions.
                </Empty>
              )}
            </section>
          </>
        )}
      </QueryState>
      <JobHistory />
    </>
  );
}
