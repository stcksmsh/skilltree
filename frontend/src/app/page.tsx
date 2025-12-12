"use client";

import React, { useEffect, useState } from "react";
import { apiGet, apiPost, API_BASE } from "@/lib/api";
import { GraphOut, NodeOut, GraphView } from "@/components/GraphView";

export default function Page() {
  const [graph, setGraph] = useState<GraphOut | null>(null);
  const [selected, setSelected] = useState<NodeOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      setGraph(await apiGet<GraphOut>("/api/graph"));
    } catch (e: any) {
      setError(e?.message ?? String(e));
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", height: "100vh" }}>
      <div style={{ minWidth: 0 }}>
        {graph ? <GraphView graph={graph} onSelect={setSelected} /> : <div style={{ padding: 16 }}>Loading…</div>}
      </div>

      <aside style={{ borderLeft: "1px solid #333", padding: 16, fontFamily: "sans-serif" }}>
        <div style={{ marginTop: 12, fontSize: 12, opacity: 0.85, lineHeight: 1.5 }}>
          <div><strong>Legend</strong></div>
          <div>→ solid arrow: requires</div>
          <div>→ dashed arrow: recommended (rank label)</div>
          <div>→ dotted line: related</div>
        </div>
        
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <h2 style={{ margin: 0 }}>Library of Alexandria</h2>
          <button
            onClick={async () => {
              setError(null);
              try {
                await apiPost("/api/admin/seed");
                await load();
                setSelected(null);
              } catch (e: any) {
                setError(e?.message ?? String(e));
              }
            }}
          >
            Reseed
          </button>
        </div>

        <div style={{ opacity: 0.7, marginTop: 6, fontSize: 12 }}>API: {API_BASE}</div>

        {error && (
          <pre style={{ whiteSpace: "pre-wrap", marginTop: 12, color: "tomato" }}>
            {error}
          </pre>
        )}

        <hr style={{ margin: "16px 0", opacity: 0.2 }} />

        {selected ? (
          <>
            <h3 style={{ margin: "0 0 6px 0" }}>{selected.title}</h3>
            <div style={{ opacity: 0.7, fontSize: 12, marginBottom: 10 }}>{selected.slug}</div>
            <div style={{ lineHeight: 1.4 }}>{selected.summary || "—"}</div>
          </>
        ) : (
          <div style={{ opacity: 0.8 }}>Click a node.</div>
        )}
      </aside>
    </div>
  );
}
