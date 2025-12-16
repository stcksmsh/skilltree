"use client";

import React, { useEffect, useMemo, useRef } from "react";
import cytoscape, { Core } from "cytoscape";
import dagre from "cytoscape-dagre";

import type { GraphOut, AbstractNodeOut } from "./types";
import { CY_STYLE, runRelayout } from "./cy/style";
import { makeRestoreAll } from "./cy/anim";
import { highlightRequiresChain } from "./cy/highlight";
import { installGraphEvents } from "./cy/events";

cytoscape.use(dagre);

type BundleKey = `${string}::${string}::${string}`;

export function GraphView({
  graph,
  onSelect,
  onCyReady,
  selectedId,
  highlightPrereqs,
}: {
  graph: GraphOut;
  onSelect: (n: AbstractNodeOut | null) => void;
  onCyReady?: (cy: Core) => void;
  selectedId?: string | null;
  highlightPrereqs?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);

  const restoreAllRef = useRef<(() => void) | null>(null);
  const highlightRef = useRef<((id: string) => void) | null>(null);

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
      // classes for styling (optional, but useful now)
      classes: [
        n.kind === "group" ? "kind-group" : "kind-concept",
        n.has_children ? "has-children" : "",
        n.has_variants ? "has-variants" : "",
      ]
        .filter(Boolean)
        .join(" "),
    }));

    // --- project + bundle impl edges into abstract edges
    // Bundle by srcAbs, dstAbs, type (keeps DAG view readable)
    const bundles = new Map<BundleKey, { count: number; rankMin: number | null }>();

    for (const e of graph.edges) {
      const srcAbs = implToAbs.get(e.src_impl_id);
      const dstAbs = implToAbs.get(e.dst_impl_id);
      if (!srcAbs || !dstAbs) continue;

      // optional: drop self after projection (variant-to-variant within same abstract)
      if (srcAbs === dstAbs) continue;

      const key: BundleKey = `${srcAbs}::${dstAbs}::${e.type}`;
      const prev = bundles.get(key);

      const rank = e.rank ?? null;
      if (!prev) {
        bundles.set(key, { count: 1, rankMin: rank });
      } else {
        prev.count += 1;
        // keep min rank for recommended (stable-ish)
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
          // optional: show count to debug
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

    if (cyRef.current) {
      cyRef.current.destroy();
      cyRef.current = null;
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: CY_STYLE,
      layout: { name: "preset" },
    });

    runRelayout(cy);

    cyRef.current = cy;
    onCyReadyRef.current?.(cy);

    const restoreAll = makeRestoreAll(cy);
    restoreAllRef.current = restoreAll;

    const highlight = (id: string) => highlightRequiresChain(cy, id);
    highlightRef.current = highlight;

    installGraphEvents({
      cy,
      onSelect: (n) => onSelectRef.current(n),
      restoreAll,
      highlightSelected: highlight,
      shouldHighlight: () => !!highlightEnabledRef.current,
    });

    return () => cy.destroy();
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
