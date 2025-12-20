"use client";

import React, { useEffect, useMemo, useRef } from "react";
import cytoscape, { Core } from "cytoscape";
import dagre from "cytoscape-dagre";

import type { GraphOut, AbstractNodeOut } from "./types";
import { CY_STYLE, runRelayout } from "./cy/style";
import { installGraphEvents } from "./cy/events";

cytoscape.use(dagre);

type BundleKey = `${string}::${string}::${string}`;

export function GraphViewLayer({
  layerKey,
  graph,
  opacity,
  active,
  onCyInstance,
  onSelect,
  onEnterFocus,
  onCyReady,
  initialFrame,
  onInitialFrameDone,
  selectedId,
  highlightPrereqs,
}: {
  layerKey: string;
  graph: GraphOut;
  opacity: number;
  active: boolean;
  onCyInstance: (cy: Core | null) => void;
  onSelect: (n: AbstractNodeOut | null) => void;
  onEnterFocus: (
    id: string,
    meta?: { fromNodeId?: string; fromRenderPos?: { x: number; y: number } }
  ) => void;
  onCyReady?: (cy: Core) => void;

  // Option A: initial fit once (only for initial root mount)
  initialFrame?: boolean;
  onInitialFrameDone?: () => void;

  selectedId?: string | null;
  highlightPrereqs?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);

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
    const container = containerRef.current;
    if (!container) return;

    const cy = cytoscape({
      container,
      elements,
      style: CY_STYLE,
      layout: { name: "preset" },
    });

    onCyInstance(cy);
    onCyReady?.(cy);

    installGraphEvents({
      cy,
      onSelect,
      onEnterFocus,
      restoreAll: () => {},
      highlightSelected: () => {},
      shouldHighlight: () => !!highlightPrereqs,
    });

    let raf = 0;
    let cancelled = false;

    const tryLayout = () => {
      if (cancelled || cy.destroyed()) return;

      const w = container.clientWidth;
      const h = container.clientHeight;
      if (w === 0 || h === 0) {
        raf = requestAnimationFrame(tryLayout);
        return;
      }

      cy.resize();

      if (cy.width() === 0 || cy.height() === 0) {
        raf = requestAnimationFrame(tryLayout);
        return;
      }

      runRelayout(cy);

      // Option A: initial framing once (NOT during transitions)
      if (initialFrame) {
        const visible = cy.elements(":visible");
        if (visible.nonempty()) {
          cy.fit(visible, 30);
        }
        onInitialFrameDone?.();
      }
    };

    raf = requestAnimationFrame(tryLayout);

    return () => {
      cancelled = true;
      if (raf) cancelAnimationFrame(raf);
      onCyInstance(null);
      cy.destroy();
    };
    // initialFrame should be captured on mount only; do not re-run effect on change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [elements]);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        opacity,
        pointerEvents: active ? "auto" : "none",
        transition: "opacity 300ms ease",
      }}
      ref={containerRef}
    />
  );
}
