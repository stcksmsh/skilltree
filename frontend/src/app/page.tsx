"use client";

import React, { useEffect, useRef, useState } from "react";
import type { Core } from "cytoscape";

import { apiGet, apiPost } from "@/lib/api";
import { GraphOut, AbstractNodeOut, ImplOut, GraphView } from "@/components/graphView/index";

import { VIEW_ANIM } from "@/components/graph/constants";
import { GraphToolbar } from "@/components/graph/GraphToolbar";
import { Sidebar } from "@/components/graph/GraphSidebar";
import { BoundaryPanel } from "@/components/graph/BoundaryPanel";

import { layoutStyles } from "@/components/graph/styles";



export default function Page() {
  const [graph, setGraph] = useState<GraphOut | null>(null);
  const [selected, setSelected] = useState<AbstractNodeOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  type FocusEntry = { id: string };
  const [focusStack, setFocusStack] = useState<FocusEntry[]>([]);
  const focusId = focusStack.length ? focusStack[focusStack.length - 1].id : null;

  const cyRef = useRef<Core | null>(null);

  const [showRequires, setShowRequires] = useState(true);
  const [showRecommended, setShowRecommended] = useState(true);
  const [showRelated, setShowRelated] = useState(true);
  const [highlightPrereqs, setHighlightPrereqs] = useState(false);

  function applyEdgeVisibility(cy: Core, opts: {
    showRequires: boolean;
    showRecommended: boolean;
    showRelated: boolean;
  }) {
    const setHidden = (selector: string, hidden: boolean) => {
      const els = cy.elements(selector);
      if (hidden) els.addClass("hidden");
      else els.removeClass("hidden");
    };

    setHidden("edge.requires", !opts.showRequires);
    setHidden("edge.recommended", !opts.showRecommended);
    setHidden("edge.related", !opts.showRelated);
  }
  
  // prevents overriding manual user toggles repeatedly
  const autoDefaultsAppliedRef = useRef<"baseline" | "focus" | null>(null);

  useEffect(() => {
    const mode: "baseline" | "focus" = focusId ? "focus" : "baseline";
    if (autoDefaultsAppliedRef.current === mode) return;

    setShowRequires(true);
    if (mode === "baseline") {
      setShowRecommended(false);
      setShowRelated(false);
    } else {
      setShowRecommended(true);
      setShowRelated(true);
    }

    autoDefaultsAppliedRef.current = mode;
  }, [focusId]);

  const [creating, setCreating] = useState(false);
  const [newSlug, setNewSlug] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [newSummary, setNewSummary] = useState("");

  async function load(id: string | null) {
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

  function pushFocus(id: string) {
    setSelected(null);
    setFocusStack((s) => (s.at(-1)?.id === id ? s : [...s, { id }]));
  }

  function popFocus() {
    setSelected(null);
    setFocusStack((s) => s.slice(0, -1));
  }

  useEffect(() => { if (focusId) load(focusId); else load(null); }, [focusId]);

  // toggle edges visibility
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    applyEdgeVisibility(cy, {
      showRequires,
      showRecommended,
      showRelated,
    });

    cy.fit(undefined, 30);
  }, [showRequires, showRecommended, showRelated]);

  return (
    <div style={layoutStyles.page}>
      <div style={layoutStyles.graphPane}>
        <GraphToolbar cyRef={cyRef} selectedId={selected?.id ?? null} focusId={focusId} popFocus={popFocus} />

        {graph && (
            <BoundaryPanel
              graph={graph}
              onJump={(groupId) => {
                pushFocus(groupId);
                load(groupId);
                setSelected(null);
              }}
            />
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
            }}
            onEnterFocus={ async (id) => {
              pushFocus(id);
              await load(id);
              setSelected(null);

              // 4) detail: fit after graph switches
              requestAnimationFrame(() => {
                const cy = cyRef.current;
                if (!cy) return;
                const visible = cy.elements(":visible");
                if (visible.nonempty()) cy.fit(visible, 30);
              });
            }}
            onCyReady={(cy) => {
              cyRef.current = cy;
              applyEdgeVisibility(cy, {
                showRequires,
                showRecommended,
                showRelated,
              });
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

