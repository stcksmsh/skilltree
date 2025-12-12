"use client";

import React, { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, API_BASE } from "@/lib/api";
import { GraphOut, NodeOut, GraphView } from "@/components/GraphView";

export default function Page() {
  const [graph, setGraph] = useState<GraphOut | null>(null);
  const [selected, setSelected] = useState<NodeOut | null>(null);
  const [error, setError] = useState<string | null>(null);

    const cyRef = useRef<import("cytoscape").Core | null>(null);

    const [showRequires, setShowRequires] = useState(true);
    const [showRecommended, setShowRecommended] = useState(true);
    const [showRelated, setShowRelated] = useState(true);

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

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    const setHidden = (selector: string, hidden: boolean) => {
      const els = cy.elements(selector);
      if (hidden) els.addClass("hidden");
      else els.removeClass("hidden");
    };

    setHidden("edge.requires", !showRequires);
    setHidden("edge.recommended", !showRecommended);
    setHidden("edge.related", !showRelated);

    // optional: re-fit after toggles to keep view nice
    cy.fit(undefined, 30);
  }, [showRequires, showRecommended, showRelated]);


  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", height: "100vh" }}>
      <div style={{ minWidth: 0, position: "relative" }}>
        {/* Toolbar overlay */}
        <div
          style={{
            position: "absolute",
            top: 12,
            left: 12,
            zIndex: 10,
            display: "flex",
            gap: 8,
            padding: 8,
            border: "1px solid #333",
            borderRadius: 8,
            background: "rgba(0,0,0,0.6)",
            backdropFilter: "blur(6px)",
            fontFamily: "sans-serif",
            fontSize: 12,
          }}
        >
          <button onClick={() => cyRef.current?.fit(undefined, 30)}>Fit</button>

          <button
            onClick={() => {
              const cy = cyRef.current;
              if (!cy) return;
              cy.zoom({
                level: cy.zoom() * 1.15,
                renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
              });
            }}
          >
            +
          </button>

          <button
            onClick={() => {
              const cy = cyRef.current;
              if (!cy) return;
              cy.zoom({
                level: cy.zoom() / 1.15,
                renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
              });
            }}
          >
            -
          </button>

          <button
            onClick={() => {
              const cy = cyRef.current;
              if (!cy) return;
              cy.layout({ name: "breadthfirst", directed: true, padding: 30 }).run();
            }}
          >
            Re-layout
          </button>

          <button
            onClick={() => {
              const cy = cyRef.current;
              if (!cy || !selected) return;
              const n = cy.getElementById(selected.id);
              if (!n.empty()) {
                cy.center(n);
                cy.zoom({
                  level: Math.max(cy.zoom(), 1.1),
                  renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
                });
              }
            }}
            disabled={!selected}
          >
            Center
          </button>
        </div>

        {graph ? (
          <GraphView
            graph={graph}
            onSelect={(n) => {
              setSelected(n);
              const cy = cyRef.current;
              if (cy) {
                const el = cy.getElementById(n.id);
                if (!el.empty()) cy.center(el);
              }
            }}
            onCyReady={(cy) => {
              cyRef.current = cy;
            }}
          />
        ) : (
          <div style={{ padding: 16 }}>Loading…</div>
        )}
      </div>


      <aside style={{ borderLeft: "1px solid #333", padding: 16, fontFamily: "sans-serif" }}>
        <div style={{ marginTop: 12, fontSize: 12, opacity: 0.85, lineHeight: 1.5 }}>
          <div><strong>Legend</strong></div>
          <div>→ solid arrow: requires</div>
          <div>→ dashed arrow: recommended (rank label)</div>
          <div>→ dotted line: related</div>
        </div>

        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 8 }}>Edges</div>

          <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12 }}>
            <input
              type="checkbox"
              checked={showRequires}
              onChange={(e) => setShowRequires(e.target.checked)}
            />
            requires
          </label>

          <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12 }}>
            <input
              type="checkbox"
              checked={showRecommended}
              onChange={(e) => setShowRecommended(e.target.checked)}
            />
            recommended
          </label>

          <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12 }}>
            <input
              type="checkbox"
              checked={showRelated}
              onChange={(e) => setShowRelated(e.target.checked)}
            />
            related
          </label>
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
