"use client";

import React, { useEffect, useRef, useState } from "react";
import type { Core } from "cytoscape";

import { apiGet, apiPost } from "@/lib/api";
import { GraphOut, AbstractNodeOut, GraphStage, GraphStageHandle } from "@/components/graphView/index";

import { GraphToolbar } from "@/components/graph/GraphToolbar";
import { Sidebar } from "@/components/graph/GraphSidebar";
import { BoundaryPanel } from "@/components/graph/BoundaryPanel";

import { layoutStyles } from "@/components/graph/styles";



export default function Page() {
  const [graph, setGraph] = useState<GraphOut | null>(null);
  const [selected, setSelected] = useState<AbstractNodeOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  type FocusEntry = {
    id: string;
    fromNodeId?: string;
    anchorPos?: { x: number; y: number };
    anchorPan?: { x: number; y: number };
    anchorZoom?: number;
  };
  const [focusStack, setFocusStack] = useState<FocusEntry[]>([]);
  const focusId = focusStack.length ? focusStack[focusStack.length - 1].id : null;  

  const cyRef = useRef<Core | null>(null);

  const [showRequires, setShowRequires] = useState(true);
  const [showRecommended, setShowRecommended] = useState(true);
  const [showRelated, setShowRelated] = useState(true);
  const [highlightPrereqs, setHighlightPrereqs] = useState(false);

  const stageRef = useRef<GraphStageHandle | null>(null);

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

  function pushFocus(entry: FocusEntry) {
    setSelected(null);
    setFocusStack((s) => (s.at(-1)?.id === entry.id ? s : [...s, entry]));
  }

  async function popFocus() {
    setSelected(null);

    // If no focus, nothing to pop
    if (focusStack.length === 0) return;

    const leaving = focusStack[focusStack.length - 1];
    const target = focusStack.length >= 2 ? focusStack[focusStack.length - 2] : null;

    // Load the graph we’re returning to
    const parentGraph = await apiGet<GraphOut>(
      target ? `/api/graph/focus/${target.id}` : "/api/graph"
    );

    // Animate exit first (so we don't swap the "graph" prop mid-animation)
    await stageRef.current?.exitFocus({
      parentGraph,
      targetCamera:
        leaving?.anchorPan && typeof leaving.anchorZoom === "number"
          ? { pan: leaving.anchorPan, zoom: leaving.anchorZoom }
          : null,
    });

    // Now commit nav state
    setFocusStack((s) => s.slice(0, -1));
    setGraph(parentGraph);
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
  }, [showRequires, showRecommended, showRelated]);

  return (
    <div style={layoutStyles.page}>
      <div style={layoutStyles.graphPane}>
        <GraphToolbar cyRef={cyRef} selectedId={selected?.id ?? null} focusId={focusId} popFocus={popFocus} />

        {graph && (
            <BoundaryPanel
              graph={graph}
              onJump={(groupId) => {
                pushFocus({id: groupId});
              }}
            />
          )
        }

        {graph ? (
          <GraphStage
            ref={stageRef}
            graph={graph}
            onEnterFocus={async (id: string) => {
              const g = await apiGet<GraphOut>(`/api/graph/focus/${id}`);
              return g;
            }}
            onDidEnterFocus={(entry) => {
              setFocusStack((s) => (s.at(-1)?.id === entry.id ? s : [...s, entry]));
            }}
            onSelect={setSelected}
            onCyReady={(cy: Core) => (cyRef.current = cy)}
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
            await load(null);
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

