import React, { useEffect, useMemo, useState } from "react";

function sevClass(sev) {
  const s = String(sev || "").toUpperCase();
  if (s === "P1") return "pill p1";
  if (s === "P2") return "pill p2";
  return "pill p3";
}

function formatTime(ts) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return String(ts);
  }
}

export default function App() {
  const apiBase = (import.meta.env.VITE_API_BASE || "http://localhost:3000").replace(/\/$/, "");
  const [incidents, setIncidents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${apiBase}/incidents`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const list = Array.isArray(data) ? data : [];
      setIncidents(list);
      setSelected((prev) => {
        if (prev && list.some((x) => x._id === prev._id)) {
          return list.find((x) => x._id === prev._id) || prev;
        }
        return list[0] || null;
      });
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const active = useMemo(() => incidents.slice(0, 20), [incidents]);

  return (
    <div className="container">
      <div className="header">
        <div>
          <h1 className="h-title">AI Incident Detection Dashboard</h1>
          <p className="h-sub">Active incidents with AI-style triage fields (Prometheus + Loki via n8n).</p>
        </div>
        <div className="actions">
          <button className="button" onClick={load} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      {error ? (
        <div className="panel">
          <div className="panel-title">Error</div>
          <div className="mono">{error}</div>
        </div>
      ) : null}

      <div className="split">
        <div className="panel">
          <div className="panel-title">Active Incidents</div>
          <table className="table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Service</th>
                <th>Severity</th>
                <th>Error %</th>
                <th>Latency (ms)</th>
              </tr>
            </thead>
            <tbody>
              {active.map((x) => (
                <tr key={x._id} onClick={() => setSelected(x)} style={{ cursor: "pointer" }}>
                  <td>{formatTime(x.timestamp)}</td>
                  <td>{x.service_name}</td>
                  <td><span className={sevClass(x.severity)}>{x.severity}</span></td>
                  <td>{Number(x.error_rate_percent).toFixed(1)}</td>
                  <td>{Math.round(Number(x.latency_ms))}</td>
                </tr>
              ))}
              {!active.length ? (
                <tr>
                  <td colSpan={5} className="mono">No incidents yet. Wait for simulator spikes or execute the n8n workflow.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>

        <div className="panel">
          <div className="panel-title">Incident Details</div>
          {selected ? (
            <>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center" }}>
                <div>
                  <div style={{ fontWeight: 800, fontSize: 16 }}>{selected.service_name}</div>
                  <div className="mono" style={{ color: "var(--muted)", marginTop: 2 }}>{formatTime(selected.timestamp)}</div>
                </div>
                <span className={sevClass(selected.severity)}>{selected.severity}</span>
              </div>

              <div className="kv">
                <div className="k">Correlation ID</div>
                <div className="mono">{selected.correlation_id}</div>

                <div className="k">Error Rate</div>
                <div>{Number(selected.error_rate_percent).toFixed(1)}%</div>

                <div className="k">Latency</div>
                <div>{Math.round(Number(selected.latency_ms))} ms</div>

                <div className="k">DB Utilization</div>
                <div>{Math.round(Number(selected.db_pool_utilization))}%</div>

                <div className="k">Root Cause</div>
                <div>{selected.probable_root_cause}</div>

                <div className="k">Actions</div>
                <div>{selected.recommended_actions}</div>
              </div>

              <details style={{ marginTop: 10 }}>
                <summary className="mono" style={{ color: "var(--muted)", cursor: "pointer" }}>Raw payload</summary>
                <pre className="mono" style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(selected.raw || selected, null, 2)}</pre>
              </details>
            </>
          ) : (
            <div className="mono">Select an incident to view details.</div>
          )}
        </div>
      </div>

      <div style={{ marginTop: 14 }} className="panel">
        <div className="panel-title">Timeline</div>
        <div className="mono" style={{ color: "var(--muted)" }}>Newest to oldest (last 50 shown).</div>
        <div style={{ marginTop: 8 }}>
          {incidents.slice(0, 50).map((x) => (
            <div key={x._id} className="timeline-item">
              <span className={sevClass(x.severity)}>{x.severity}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700 }}>{x.service_name}</div>
                <div className="mono" style={{ color: "var(--muted)" }}>{x.probable_root_cause}</div>
              </div>
              <div className="mono" style={{ color: "var(--muted)" }}>{formatTime(x.timestamp)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
