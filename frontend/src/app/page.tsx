"use client";

import React, { useEffect, useRef, useState } from "react";
import type { Core } from "cytoscape";

import { apiGet, apiPost } from "@/lib/api";
import { GraphOut, AbstractNodeOut, ImplOut, GraphView } from "@/components/graphView/index";

import { VIEW_ANIM } from "@/components/graph/constants";
import { GraphToolbar } from "@/components/graph/GraphToolbar";
import { Sidebar } from "@/components/graph/GraphSidebar";

import { layoutStyles } from "@/components/graph/styles";



export default function Page() {
  const [graph, setGraph] = useState<GraphOut | null>(null);
  const [selected, setSelected] = useState<AbstractNodeOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [focusStack, setFocusStack] = useState<string[]>([]);
  const [focusId, setFocusId] = useState<string | null>(null);

  const cyRef = useRef<Core | null>(null);

  const [showRequires, setShowRequires] = useState(true);
  const [showRecommended, setShowRecommended] = useState(true);
  const [showRelated, setShowRelated] = useState(true);
  const [highlightPrereqs, setHighlightPrereqs] = useState(false);

  const [creating, setCreating] = useState(false);
  const [newSlug, setNewSlug] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [newSummary, setNewSummary] = useState("");

  async function load(id: string | null = focusId) {
    setError(null);
    try {
      if (id) {
        setGraph(await apiGet<GraphOut>(`/api/graph/focus/${id}`));
      } else {
        setGraph(await apiGet<GraphOut>("/api/graph"));
      }
    } catch (e: any) {
      setError(e?.message ?? String(e));
    }
  }

  async function popFocus() {
    setError(null);
    setFocusStack((stack) => {
      const next = stack.slice(0, -1);
      const newFocus = next.length ? next[next.length - 1] : null;
      setFocusId(newFocus);
      load(newFocus);
      return next;
    });
  }

  async function createNode() {
    setError(null);
    try {
      const created = await apiPost<AbstractNodeOut>("/api/nodes", {
        slug: newSlug,
        title: newTitle,
        summary: newSummary || null,
      });

      await load();
      setSelected(created);

      setCreating(false);
      setNewSlug("");
      setNewTitle("");
      setNewSummary("");
    } catch (e: any) {
      setError(e?.message ?? String(e));
    }
  }

  useEffect(() => {
    load(null);
  }, []);

  // toggle edges visibility
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

    cy.fit(undefined, 30);
  }, [showRequires, showRecommended, showRelated]);

  return (
    <div style={layoutStyles.page}>
      <div style={layoutStyles.graphPane}>
        <GraphToolbar cyRef={cyRef} selectedId={selected?.id ?? null} focusId={focusId} popFocus={popFocus} />

        { graph && graph.boundary_hints.length > 0 && 
          (
            <div className="boundary-panel">
              <h4>External dependencies</h4>
              {graph.boundary_hints.map((h) => (
                <div
                  key={`${h.group_id}-${h.type}`}
                  className={`boundary-hint ${h.type}`}
                  onClick={() => {
                    // navigate OUT to that group
                    setFocusStack((s) => [...s, h.group_id]);
                    setFocusId(h.group_id);
                    load(h.group_id);
                  }}
                >
                  {h.short_title} ({h.count})
                </div>
              ))}
            </div>
          )
        }

        {graph ? (
          <GraphView
            graph={graph}
            onSelect={(n) => {
              setSelected(n);

              if (!n) {
                setCreating(false);
                return;
              }

              const cy = cyRef.current;
              if (cy) {
                const el = cy.getElementById(n.id);
                if (!el.empty()) {
                  const targetZoom = Math.max(cy.zoom(), VIEW_ANIM.center.minZoom);
                  cy.animate(
                    { center: { eles: el }, zoom: targetZoom },
                    { duration: 400, easing: VIEW_ANIM.easing }
                  );
                }
              }

              // ENTER FOCUS if expandable
              if (n.has_children) {
                setTimeout(async () => {
                  setFocusStack((s) => [...s, n.id]);
                  setFocusId(n.id);
                  await load(n.id);
                  setSelected(null);
                }, 420); // let animation finish
              }
            }}
            onCyReady={(cy) => {
              cyRef.current = cy;
            }}
            selectedId={selected?.id ?? null}
            highlightPrereqs={highlightPrereqs}
          />
        ) : (
          <div style={{ padding: 16 }}>Loading…</div>
        )}
      </div>

      <Sidebar
        error={error}
        onReseed={async () => {
          setError(null);
          try {
            await apiPost("/api/admin/seed");
            await load();
            setSelected(null);
          } catch (e: any) {
            setError(e?.message ?? String(e));
          }
        }}
        showRequires={showRequires}
        showRecommended={showRecommended}
        showRelated={showRelated}
        onChangeRequires={setShowRequires}
        onChangeRecommended={setShowRecommended}
        onChangeRelated={setShowRelated}
        creating={creating}
        newTitle={newTitle}
        newSlug={newSlug}
        newSummary={newSummary}
        onToggleNew={() => {
          setCreating((v) => !v);
          setError(null);
        }}
        onChangeNewTitle={setNewTitle}
        onChangeNewSlug={setNewSlug}
        onChangeNewSummary={setNewSummary}
        onCreateNode={createNode}
        highlightPrereqs={highlightPrereqs}
        onToggleHighlightPrereqs={setHighlightPrereqs}
        onClearSelection={() => {
          setSelected(null);
          setHighlightPrereqs(false);
        }}
        selected={selected}
      />
    </div>
  );
}

