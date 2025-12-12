"use client";

import React, { useEffect, useMemo, useRef } from "react";
import cytoscape, { Core } from "cytoscape";

export type NodeOut = { id: string; slug: string; title: string; summary?: string | null };
export type EdgeOut = { id: string; source: string; target: string; type: "requires" | "recommended"; rank?: number | null };
export type RelatedOut = { a: string; b: string };
export type GraphOut = { nodes: NodeOut[]; edges: EdgeOut[]; related: RelatedOut[] };

export function GraphView({
  graph,
  onSelect,
}: {
  graph: GraphOut;
  onSelect: (n: NodeOut) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);

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
      style: [
        {
          selector: "node",
          style: {
            label: "data(title)",
            "text-wrap": "wrap",
            "text-max-width": 150,
            "font-size": 10,
            "border-width": 1,
          },
        },
        {
          selector: "edge.requires",
          style: { "curve-style": "bezier", width: 2, "target-arrow-shape": "triangle" },
        },
        {
          selector: "edge.recommended",
          style: {
            "curve-style": "bezier",
            width: 2,
            "target-arrow-shape": "triangle",
            "line-style": "dashed",
            label: "data(rank)",
            "font-size": 9,
          },
        },
        {
          selector: "edge.related",
          style: { "curve-style": "bezier", width: 1, "line-style": "dotted", "target-arrow-shape": "none" },
        },
        { selector: "node:selected", style: { "border-width": 3 } },
      ],
      layout: { name: "breadthfirst", directed: true, padding: 30 },
    });

    cy.on("tap", "node", (evt) => {
      const d = evt.target.data();
      onSelect({ id: d.id, slug: d.slug, title: d.title, summary: d.summary ?? null });
    });

    cyRef.current = cy;
    return () => cy.destroy();
  }, [elements, onSelect]);

  return <div ref={containerRef} style={{ height: "100%", width: "100%" }} />;
}
