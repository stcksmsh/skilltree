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
  
  type FocusEntry = {
    id: string;
    fromNodeId?: string;
    anchorPos?: { x: number; y: number };
    anchorPan?: { x: number; y: number };
    anchorZoom?: number;
  };
  const pendingEnterRef = useRef<FocusEntry | null>(null);
  const [focusStack, setFocusStack] = useState<FocusEntry[]>([]);
  const focusId = focusStack.length ? focusStack[focusStack.length - 1].id : null;
  const focusTop = focusStack.length ? focusStack[focusStack.length - 1] : null;

  const cyRef = useRef<Core | null>(null);

  const [showRequires, setShowRequires] = useState(true);
  const [showRecommended, setShowRecommended] = useState(true);
  const [showRelated, setShowRelated] = useState(true);
  const [highlightPrereqs, setHighlightPrereqs] = useState(false);

  type PendingCamera = {
    pan: { x: number; y: number };
    zoom: number;
    centerNodeId?: string;
  };

  const [pendingCamera, setPendingCamera] = useState<PendingCamera | null>(null);


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

  async function drillEnterFocus(id: string, meta?: { fromNodeId?: string; fromRenderPos?: { x: number; y: number } }) {
    setSelected(null);

    const cy = cyRef.current;

    // record an anchor *only* (no animation here)
    if (cy) {
      const el = cy.getElementById(id);
      if (el.nonempty()) {
        // capture "back target" in the PARENT graph coordinates
        const anchorPan = cy.pan();
        const anchorZoom = cy.zoom();
        const anchorPos = meta?.fromRenderPos ?? el.renderedPosition();

        // Phase A: pre-zoom into the super-node (smooth + deterministic)
        cy.stop();

        // Fade the super-node a bit during the pre-zoom (cheap illusion; true fade comes later)
        try {
          el.animate({ style: { opacity: 0.25 } }, { duration: 240, easing: "ease-in-out-cubic" });
        } catch {}

        const nextZoom = Math.min(Math.max(anchorZoom * 1.35, 0.6), 3.0);
        const a = cy.animation(
          { center: { eles: el }, zoom: nextZoom },
          { duration: 420, easing: "ease-in-out-cubic" }
        );
        a.play();
        await a.promise("completed");

        pushFocus({ id, fromNodeId: id, anchorPos, anchorPan, anchorZoom });
        return;
      }
    }

    pushFocus({ id, fromNodeId: id });
  }

  function pushFocus(entry: FocusEntry) {
    setSelected(null);
    setFocusStack((s) => (s.at(-1)?.id === entry.id ? s : [...s, entry]));
  }


  function popFocus() {
    setSelected(null);

    const prevEntry = focusTop; // the focus we are leaving (contains parent camera snapshot)
    const goingBackTo = focusStack.length >= 2 ? focusStack[focusStack.length - 2] : null;

    if (prevEntry?.anchorPan && typeof prevEntry.anchorZoom === "number") {
      setPendingCamera({
        pan: prevEntry.anchorPan,
        zoom: prevEntry.anchorZoom,
        centerNodeId: prevEntry.fromNodeId ?? goingBackTo?.id ?? undefined,
      });
    } else {
      setPendingCamera(null);
    }
    
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
          <GraphView
            graph={graph}
            focusMeta={focusTop}
            pendingCamera={pendingCamera}
            onPendingCameraApplied={() => setPendingCamera(null)}
            onSelect={(n) => {
              setSelected(n);

              if (!n) return;

              const cy = cyRef.current;

              if (!cy) return;

              const el = cy.getElementById(n.id);

              if (!el.empty()) {
                const targetZoom = Math.max(cy.zoom(), VIEW_ANIM.center.minZoom);
                cy.animate(
                  { center: { eles: el }, zoom: targetZoom },
                  { duration: 400, easing: VIEW_ANIM.easing }
                );
              }
            }}
            onEnterFocus={async (id, meta) => {
              await drillEnterFocus(id, meta);
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

