"use client";

import React, { useEffect, useMemo, useRef } from "react";
import cytoscape, { Core } from "cytoscape";

import type { GraphOut, NodeOut } from "./types";
import { CY_LAYOUT, CY_STYLE } from "./cy/style";
import { makeRestoreAll } from "./cy/anim";
import { highlightRequiresChain } from "./cy/highlight";
import { installGraphEvents } from "./cy/events";

export function GraphView({
  graph,
  onSelect,
  onCyReady,
  selectedId,
  highlightPrereqs,
}: {
  graph: GraphOut;
  onSelect: (n: NodeOut | null) => void;
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
    const ns = graph.nodes.map((n) => ({
      data: { id: n.id, slug: n.slug, title: n.title, summary: n.summary ?? "" },
    }));

    const es = graph.edges.map((e) => ({
      data: { id: e.id, source: e.source, target: e.target, type: e.type, rank: e.rank ?? "" },
      classes: e.type,
    }));

    const rs = graph.related.map((r, idx) => ({
      data: { id: `rel-${idx}`, source: r.a, target: r.b, type: "related" },
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
      layout: CY_LAYOUT,
    });

    cyRef.current = cy;
    onCyReadyRef.current?.(cy);

    console.log("[GraphView] cy ready", { nodes: cy.nodes().size(), edges: cy.edges().size() });

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

    // OFF always restores
    if (!highlightPrereqs) {
      restoreAllRef.current?.();
      console.log("[GraphView] highlight OFF -> restored");
      return;
    }

    // ON but no selection should also restore (prevents “stuck faded” state)
    if (!selectedId) {
      restoreAllRef.current?.();
      console.log("[GraphView] highlight ON but no selection -> restored");
      return;
    }

    // ON + selected -> apply highlight
    restoreAllRef.current?.();
    highlightRef.current?.(selectedId);
    console.log("[GraphView] highlight ON -> re-applied", { selectedId });
  }, [highlightPrereqs, selectedId]);

  return <div ref={containerRef} style={{ height: "100%", width: "100%" }} />;
}
