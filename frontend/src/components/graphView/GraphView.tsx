"use client";

import React, { useEffect, useMemo, useRef } from "react";
import cytoscape, { Core } from "cytoscape";
import dagre from "cytoscape-dagre";

import type { GraphOut, AbstractNodeOut } from "./types";
import { CY_STYLE, runRelayout, runRelayoutAsync } from "./cy/style";
import { makeRestoreAll } from "./cy/anim";
import { highlightRequiresChain } from "./cy/highlight";
import { EnterFocusMeta, installGraphEvents } from "./cy/events";

cytoscape.use(dagre);

type BundleKey = `${string}::${string}::${string}`;

export type FocusMeta = {
  id?: string;
  fromNodeId?: string;
  anchorPos?: { x: number; y: number };
  anchorPan?: { x: number; y: number };
  anchorZoom?: number;
};

export function GraphView({
  graph,
  focusMeta,
  pendingCamera,
  onPendingCameraApplied,
  onSelect,
  onEnterFocus,
  onCyReady,
  selectedId,
  highlightPrereqs,
}: {
  graph: GraphOut;
  focusMeta?: {
    id: string;
    fromNodeId?: string;
    anchorPos?: { x: number; y: number };
    anchorPan?: { x: number; y: number };
    anchorZoom?: number;
  } | null;
  pendingCamera?: { pan: { x: number; y: number }; zoom: number; centerNodeId?: string } | null;
  onPendingCameraApplied?: () => void;
  onSelect: (n: AbstractNodeOut | null) => void;
  onEnterFocus?: (id: string, meta?: EnterFocusMeta) => void;
  onCyReady?: (cy: Core) => void;
  selectedId?: string | null;
  highlightPrereqs?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);

  const focusMetaRef = useRef(focusMeta);
  useEffect(() => { focusMetaRef.current = focusMeta; }, [focusMeta]);

  const pendingCameraRef = useRef(pendingCamera);
  useEffect(() => { pendingCameraRef.current = pendingCamera; }, [pendingCamera]);

  const onPendingCameraAppliedRef = useRef(onPendingCameraApplied);
  useEffect(() => { onPendingCameraAppliedRef.current = onPendingCameraApplied; }, [onPendingCameraApplied]);

  const restoreAllRef = useRef<(() => void) | null>(null);
  const highlightRef = useRef<((id: string) => void) | null>(null);

  const onEnterFocusRef = useRef(onEnterFocus);

  // keep callbacks stable without re-creating cytoscape
  const onSelectRef = useRef(onSelect);
  const onCyReadyRef = useRef(onCyReady);
  const highlightEnabledRef = useRef<boolean>(!!highlightPrereqs);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    onCyReadyRef.current = onCyReady;
  }, [onCyReady]);

  useEffect(() => {
    highlightEnabledRef.current = !!highlightPrereqs;
  }, [highlightPrereqs]);

  useEffect(() => {
    onEnterFocusRef.current = onEnterFocus;
  }, [onEnterFocus]);

  const elements = useMemo(() => {
    // --- impl_id -> abstract_id mapping
    const implToAbs = new Map<string, string>();
    for (const impl of graph.impl_nodes) {
      implToAbs.set(impl.id, impl.abstract_id);
    }

    // --- abstract nodes
    const ns = graph.abstract_nodes.map((n) => ({
      data: {
        id: n.id,
        slug: n.slug,
        title: n.title,
        short_title: n.short_title,
        summary: n.summary ?? "",
        kind: n.kind,
        parent_id: n.parent_id ?? "",
        has_children: n.has_children,
        has_variants: n.has_variants,
        default_impl_id: n.default_impl_id ?? "",
      },
      classes: [
        n.kind === "group" ? "kind-group" : "kind-concept",
        n.has_children ? "has-children" : "",
        n.has_variants ? "has-variants" : "",
      ]
        .filter(Boolean)
        .join(" "),
    }));

    // --- project + bundle impl edges into abstract edges
    const bundles = new Map<BundleKey, { count: number; rankMin: number | null }>();

    for (const e of graph.edges) {
      const srcAbs = implToAbs.get(e.src_impl_id);
      const dstAbs = implToAbs.get(e.dst_impl_id);
      if (!srcAbs || !dstAbs) continue;
      if (srcAbs === dstAbs) continue;

      const key: BundleKey = `${srcAbs}::${dstAbs}::${e.type}`;
      const prev = bundles.get(key);

      const rank = e.rank ?? null;
      if (!prev) {
        bundles.set(key, { count: 1, rankMin: rank });
      } else {
        prev.count += 1;
        if (rank != null) prev.rankMin = prev.rankMin == null ? rank : Math.min(prev.rankMin, rank);
      }
    }

    const es = Array.from(bundles.entries()).map(([key, v]) => {
      const [source, target, type] = key.split("::");
      const id = `bundle-${type}-${source}-${target}`;
      return {
        data: {
          id,
          source,
          target,
          type,
          count: v.count,
          rank: v.rankMin ?? "",
        },
        classes: type,
      };
    });

    // --- related edges (abstract<->abstract)
    const rs = graph.related_edges.map((r, idx) => ({
      data: {
        id: `rel-${idx}`,
        source: r.a_id,
        target: r.b_id,
        type: "related",
      },
      classes: "related",
    }));

    return [...ns, ...es, ...rs];
  }, [graph]);

  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements: [],
      style: CY_STYLE,
      layout: { name: "preset" },
    });

    cyRef.current = cy;
    onCyReadyRef.current?.(cy);

    const restoreAll = makeRestoreAll(cy);
    restoreAllRef.current = restoreAll;
    highlightRef.current = (id: string) => highlightRequiresChain(cy, id);


    // also do a one-shot on next frame (initial mount sizing)
    requestAnimationFrame(() => {
      cy.resize();
    });

    installGraphEvents({
      cy,
      onSelect: (n) => onSelectRef.current(n),
      onEnterFocus: (id, meta) => onEnterFocusRef.current?.(id, meta),
      restoreAll,
      highlightSelected: highlightRef.current,
      shouldHighlight: () => !!highlightEnabledRef.current,
    });

    return () => cy.destroy();
  }, []);

  function runRelayoutNoFit(cy: Core) {
    // Important: no fit, no camera meddling. Layout just positions nodes.
    const layout = cy.layout({
      name: "dagre",
      rankDir: "LR",
      nodeSep: 22,
      edgeSep: 10,
      rankSep: 70,
      fit: false,
      animate: false,
      spacingFactor: 1.15,
    } as any);

    layout.run();
  }

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    // 1. Stop everything
    cy.stop();

    // 2. Swap elements
    cy.batch(() => {
      cy.elements().remove();
      cy.add(elements);
    });

    // 3. Layout (instant)
    runRelayout(cy);

    // 4. Camera resolution (exactly one path)

    // A) BACK / POP takes priority
    if (pendingCameraRef.current) {
      const { pan, zoom, centerNodeId } = pendingCameraRef.current;
      const el = centerNodeId ? cy.getElementById(centerNodeId) : null;

      cy.animate(
        el && el.nonempty()
          ? { center: { eles: el }, pan, zoom }
          : { pan, zoom },
        {
          duration: 520,
          easing: "ease-in-out-cubic",
          complete: () => {
            onPendingCameraAppliedRef.current?.();
          },
        }
      );

      return;
    }

    // B) ENTER / DRILL: after layout, fit to the new graph contents
    const meta = focusMetaRef.current
    if (meta?.id) {
      const vis = cy.elements(":visible");
      if (vis.nonempty()) {
        cy.animate(
          { fit: { eles: vis, padding: 60 } },
          { duration: 520, easing: "ease-in-out-cubic" }
        );
        return
      }
    }


    // C) Fallback
    cy.fit(cy.elements(":visible"), 30);

  }, [elements]);


  // external toggle / selection changes
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    if (!highlightPrereqs) {
      restoreAllRef.current?.();
      return;
    }
    if (!selectedId) {
      restoreAllRef.current?.();
      return;
    }

    restoreAllRef.current?.();
    highlightRef.current?.(selectedId);
  }, [highlightPrereqs, selectedId]);

  return <div ref={containerRef} style={{ height: "100%", width: "100%" }} />;
}


function clamp(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v));
}

function computePanFromAnchor(opts: {
  cy: cytoscape.Core;
  anchorPos: { x: number; y: number };
  anchorPan: { x: number; y: number };
}) {
  const { cy, anchorPos, anchorPan } = opts;

  const w = cy.width();
  const h = cy.height();

  const dx = w / 2 - anchorPos.x;
  const dy = h / 2 - anchorPos.y;

  return {
    x: anchorPan.x + dx,
    y: anchorPan.y + dy,
  };
}
