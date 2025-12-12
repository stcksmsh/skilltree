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
  onCyReady,
}: {
  graph: GraphOut;
  onSelect: (n: NodeOut) => void;
  onCyReady?: (cy: Core) => void;
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

            // ✅ animate fade/highlight
            "transition-property":
              "opacity, text-opacity, background-opacity, border-opacity, border-width",
            "transition-duration": "200ms",
            "transition-timing-function": "ease-in-out",
          },
        },

        // ✅ base edge selector so all edges animate opacity/width
        {
          selector: "edge",
          style: {
            "transition-property": "opacity, width",
            "transition-duration": "200ms",
            "transition-timing-function": "ease-in-out",
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
          style: {
            "curve-style": "bezier",
            width: 1,
            "line-style": "dotted",
            "target-arrow-shape": "none",
          },
        },
        {
          selector: "node:selected",
          style: { "border-width": 3 },
        },
        {
          selector: ".hidden",
          style: {
            display: "none",
          },
        },
      ],
      layout: { name: "breadthfirst", directed: true, padding: 30 },
    });

    onCyReady?.(cy);

    cy.on("tap", "node", (evt) => {
      const d = evt.target.data();
      onSelect({ id: d.id, slug: d.slug, title: d.title, summary: d.summary ?? null });
    });

    let hoveredId: string | null = null;
    let clearTimer: any = null;

    // tune these
    const DURATION = 220;
    const EASING: any = "ease-in-out"; // cytoscape supports common easing names
    const OP_REST = 0.12;
    const OP_NEIGHBOR = 0.75;
    const OP_FOCUS = 1.0;

    const W_EDGE_REST = 1;
    const W_EDGE_FOCUS = 3;

    const BW_REST = 1;
    const BW_NEIGHBOR = 2;
    const BW_FOCUS = 3;

    // Helper: animate a collection to a style target, canceling in-flight animations.
    const anim = (col: cytoscape.CollectionReturnValue, style: any) => {
      // stop queued + current animations, but do not jump to end-state
      (col as any).stop(true, false).animate(
        { style },
        { duration: DURATION, easing: EASING }
      );
    };

    const applyVisualState = (focusId: string | null) => {
      cy.batch(() => {
        const allNodes = cy.nodes();
        const allEdges = cy.edges();

        if (!focusId) {
          // restore defaults
          anim(allNodes, {
            opacity: 1,
            "text-opacity": 1,
            "background-opacity": 1,
            "border-opacity": 1,
            "border-width": BW_REST,
          });
          anim(allEdges, {
            opacity: 1,
            width: 2, // your default-ish edge width; choose 1/2
          });
          return;
        }

        const focus = cy.getElementById(focusId);
        if (focus.empty()) return;

        const hood = focus.closedNeighborhood();
        const hoodNodes = hood.nodes();
        const hoodEdges = hood.edges();

        // neighbors are the hood nodes excluding focus
        const neighborNodes = hoodNodes.not(focus);

        // everything else
        const restNodes = allNodes.not(hoodNodes);
        const restEdges = allEdges.not(hoodEdges);

        // REST: fade hard
        anim(restNodes, {
          opacity: OP_REST,
          "text-opacity": OP_REST,
          "background-opacity": OP_REST,
          "border-opacity": OP_REST,
          "border-width": BW_REST,
        });
        anim(restEdges, {
          opacity: OP_REST,
          width: W_EDGE_REST,
        });

        // NEIGHBORS: medium emphasis
        anim(neighborNodes, {
          opacity: OP_NEIGHBOR,
          "text-opacity": OP_NEIGHBOR,
          "background-opacity": OP_NEIGHBOR,
          "border-opacity": 1,
          "border-width": BW_NEIGHBOR,
        });

        // HOOD EDGES: medium emphasis (or full if you prefer)
        anim(hoodEdges, {
          opacity: OP_NEIGHBOR,
          width: 2,
        });

        // FOCUS: full emphasis
        anim(focus, {
          opacity: OP_FOCUS,
          "text-opacity": OP_FOCUS,
          "background-opacity": OP_FOCUS,
          "border-opacity": 1,
          "border-width": BW_FOCUS,
        });

        // Focus-adjacent edges: stronger
        const focusEdges = focus.connectedEdges();
        anim(focusEdges, {
          opacity: OP_FOCUS,
          width: W_EDGE_FOCUS,
        });
      });
    };

    cy.on("mouseover", "node", (evt) => {
      if (clearTimer) {
        clearTimeout(clearTimer);
        clearTimer = null;
      }
      const id = evt.target.id();
      if (hoveredId === id) return;
      hoveredId = id;
      applyVisualState(hoveredId);
    });

    cy.on("mouseout", "node", () => {
      // delay prevents micro out/in when crossing label/shape boundary
      clearTimer = setTimeout(() => {
        hoveredId = null;
        applyVisualState(null);
      }, 80);
    });


    cyRef.current = cy;
    return () => cy.destroy();
  }, [elements, onSelect]);

  return <div ref={containerRef} style={{ height: "100%", width: "100%" }} />;
}
