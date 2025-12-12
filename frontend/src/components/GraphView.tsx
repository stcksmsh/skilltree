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
  selectedId,
  highlightPrereqs,
}: {
  graph: GraphOut;
  onSelect: (n: NodeOut) => void;
  onCyReady?: (cy: Core) => void;
  selectedId?: string | null;
  highlightPrereqs?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);

  const restoreAllRef = useRef<(() => void) | null>(null);
  const highlightUnderRef = useRef<((id: string) => void) | null>(null);

  // avoid re-initializing cy because of unstable function props
  const onSelectRef = useRef(onSelect);
  const onCyReadyRef = useRef(onCyReady);
  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);
  useEffect(() => {
    onCyReadyRef.current = onCyReady;
  }, [onCyReady]);

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

    // create cy only when elements change
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
            "transition-property":
              "opacity, text-opacity, background-opacity, border-opacity, border-width",
            "transition-duration": "200ms",
            "transition-timing-function": "ease-in-out",
          },
        },
        {
          selector: "edge",
          style: {
            "transition-property": "opacity, width",
            "transition-duration": "200ms",
            "transition-timing-function": "ease-in-out",
          },
        },
        { selector: "edge.requires", style: { "curve-style": "bezier", width: 2, "target-arrow-shape": "triangle" } },
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
        { selector: "edge.related", style: { "curve-style": "bezier", width: 1, "line-style": "dotted", "target-arrow-shape": "none" } },
        { selector: ".hidden", style: { display: "none" } },
      ],
      layout: { name: "breadthfirst", directed: true, padding: 30 },
    });

    cyRef.current = cy;
    onCyReadyRef.current?.(cy);

    // LOG: proves GraphView mounted + cy exists
    console.log("[GraphView] cy ready", { nodes: cy.nodes().size(), edges: cy.edges().size() });

    const HIGHLIGHT_ANIM = {
      duration: 220,
      easing: "ease-in-out" as const,
    };

    const anim = (col: cytoscape.CollectionReturnValue, style: any) => {
      (col as any).stop(true, false).animate({ style }, HIGHLIGHT_ANIM);
    };

    const restoreAll = () => {
      cy.batch(() => {
        anim(cy.nodes(), {
          opacity: 1,
          "text-opacity": 1,
          "background-opacity": 1,
          "border-opacity": 1,
          "border-width": 1,
        });
        anim(cy.edges(), { opacity: 1, width: 2 });
      });
    };

    restoreAllRef.current = restoreAll;

    // "UNDER" == downstream dependents (unlocks)
    // Assumption: requires edges are PREREQ -> TOPIC
    const highlightUnder = (startId: string) => {
      const focus = cy.getElementById(startId);
      if (focus.empty()) return;

      // caps to prevent “everything” if you click a root node
      const MAX_DEPTH = 3;
      const MAX_VISITED = 200;

      const visited = new Set<string>();
      const queue: Array<{ id: string; depth: number }> = [{ id: focus.id(), depth: 0 }];

      let pathNodes = cy.collection().union(focus);
      let pathEdges = cy.collection();

      visited.add(focus.id());

      while (queue.length > 0) {
        const { id: curId, depth } = queue.shift()!;
        if (depth >= MAX_DEPTH) continue;
        if (visited.size >= MAX_VISITED) break;

        const cur = cy.getElementById(curId);

        // edges-only, downstream
        // edges-only (IMPORTANT): incomers() includes nodes; incoming() returns edges
        const reqEdges = cur.incomers("edge.requires").not(".hidden");
        const nextNodes = reqEdges.sources(); // nodes on the other end of incoming edges

        pathEdges = pathEdges.union(reqEdges);
        pathNodes = pathNodes.union(nextNodes);


        nextNodes.forEach((n) => {
          const nid = n.id();
          if (!visited.has(nid)) {
            visited.add(nid);
            queue.push({ id: nid, depth: depth + 1 });
          }
        });
      }

      console.log("[under] focus=", focus.id(), "nodes=", pathNodes.size(), "edges=", pathEdges.size());

      const otherNodes = cy.nodes().not(pathNodes);
      const otherEdges = cy.edges().not(pathEdges);

      cy.batch(() => {
        anim(otherNodes, {
          opacity: 0.35,
          "text-opacity": 0.35,
          "background-opacity": 0.35,
          "border-opacity": 0.35,
          "border-width": 1,
        });
        anim(otherEdges, { opacity: 0.35, width: 1 });

        anim(pathNodes, {
          opacity: 1,
          "text-opacity": 1,
          "background-opacity": 1,
          "border-opacity": 1,
          "border-width": 2,
        });
        anim(pathEdges, { opacity: 1, width: 3 });

        anim(focus, {
          opacity: 1,
          "text-opacity": 1,
          "background-opacity": 1,
          "border-opacity": 1,
          "border-width": 4,
        });
      });
    };

    highlightUnderRef.current = highlightUnder;

    // click handler: always selects; optionally highlights path immediately
    cy.on("tap", "node", (evt) => {
      cy.$("node").unselect();
      evt.target.select();
      const d = evt.target.data();
      const node: NodeOut = { id: d.id, slug: d.slug, title: d.title, summary: d.summary ?? null };
      onSelectRef.current(node);

      // LOG: proves tap is firing
      console.log("[tap] node", d.id, "highlightUnder?", !!highlightPrereqs);

      if (highlightPrereqs) {
        restoreAll();
        highlightUnder(d.id);
      }
    });

    return () => cy.destroy();
  }, [elements]); // IMPORTANT: only depends on elements

  // when toggling checkbox off or clearing selection, restore
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    if (!highlightPrereqs) {
      restoreAllRef.current?.();
      console.log("[GraphView] highlightUnder OFF -> restored");
      return;
    }

    // highlightPrereqs is ON
    if (selectedId) {
      restoreAllRef.current?.();
      highlightUnderRef.current?.(selectedId);
      console.log("[GraphView] highlightUnder ON -> re-applied", { selectedId });
    } else {
      console.log("[GraphView] highlightUnder ON (no selection yet)");
    }
  }, [highlightPrereqs, selectedId]);

  return <div ref={containerRef} style={{ height: "100%", width: "100%" }} />;
}
