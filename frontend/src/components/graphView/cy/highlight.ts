import type cytoscape from "cytoscape";
import { anim } from "./anim";

/**
 * Highlights the "requires chain" upstream of startId.
 *
 * IMPORTANT:
 * - This implementation uses incoming requires edges and sources().
 * - That matches your current code (and your "works now" state).
 */
export function highlightRequiresChain(cy: cytoscape.Core, startId: string) {
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

    // edges-only (IMPORTANT): incomers() includes nodes; filter still works
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

  console.log("[requires-chain] focus=", focus.id(), "nodes=", pathNodes.size(), "edges=", pathEdges.size());

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
}
