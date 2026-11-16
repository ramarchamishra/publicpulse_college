import { useState } from "react";
import { NavLink, Routes, Route, Link } from "react-router-dom";
import {
  Activity,
  LayoutDashboard,
  Search,
  Layers3,
  GitCompareArrows,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import Dashboard from "./pages/Dashboard";
import Searches from "./pages/Searches";
import SearchDetail from "./pages/SearchDetail";
import Themes from "./pages/Themes";
import Compare from "./pages/Compare";
import { useApi } from "./hooks/useApi";
import { Empty } from "./components/ui";
export default function App() {
  const [collapsed, setCollapsed] = useState(false),
    health = useApi("/health", 30000);
  return (
    <div className={`app ${collapsed ? "collapsed" : ""}`}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className="sidebar">
        <Link to="/" className="brand">
          <Activity size={25} />
          <span>
            Public<span>Pulse</span>
            <small>DISCUSSION INTELLIGENCE</small>
          </span>
        </Link>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {[
            ["/", LayoutDashboard, "Dashboard"],
            ["/searches", Search, "Searches"],
            ["/themes", Layers3, "Theme Discovery"],
            ["/compare", GitCompareArrows, "Compare Topics"],
          ].map(([to, Icon, label]) => (
            <NavLink end={to === "/"} to={to} key={to} title={label}>
              <Icon size={19} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="connection">
            <span
              className={`status-dot ${health.isSuccess ? "online" : ""}`}
            />
            <span>
              {health.isSuccess
                ? "Local API connected"
                : health.isPending
                  ? "Connecting…"
                  : "API unavailable"}
            </span>
          </div>
          <button
            className="collapse-button"
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          >
            {collapsed ? (
              <PanelLeftOpen size={18} />
            ) : (
              <>
                <PanelLeftClose size={18} />
                <span>Collapse navigation</span>
              </>
            )}
          </button>
        </div>
      </aside>
      <main id="main">
        <div className="topbar">
          <span>
            PublicPulse <span className="muted">/ Research workspace</span>
          </span>
          <span className="local-badge">LOCAL WORKSPACE</span>
        </div>
        <div className="content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/searches" element={<Searches />} />
            <Route path="/searches/:id" element={<SearchDetail />} />
            <Route path="/themes" element={<Themes />} />
            <Route path="/compare" element={<Compare />} />
            <Route
              path="*"
              element={
                <Empty title="Page not found">
                  <Link to="/">Return to dashboard</Link>
                </Empty>
              }
            />
          </Routes>
          <footer>
            PublicPulse{" "}
            <span>Evidence first. A clearer view of public conversation.</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
