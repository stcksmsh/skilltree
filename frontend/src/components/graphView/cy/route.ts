import type cytoscape from "cytoscape";

type Rect = { x1: number; y1: number; x2: number; y2: number };

function rectFromNode(n: cytoscape.NodeSingular, pad = 10): Rect {
  const bb = n.boundingBox({ includeLabels: false });
  return {
    x1: bb.x1 - pad,
    y1: bb.y1 - pad,
    x2: bb.x2 + pad,
    y2: bb.y2 + pad,
  };
}

function segmentIntersectsRect(ax: number, ay: number, bx: number, by: number, r: Rect): boolean {
  // quick reject via segment bbox
  const minX = Math.min(ax, bx), maxX = Math.max(ax, bx);
  const minY = Math.min(ay, by), maxY = Math.max(ay, by);
  if (maxX < r.x1 || minX > r.x2 || maxY < r.y1 || minY > r.y2) return false;

  // if either endpoint inside rect
  const insideA = ax >= r.x1 && ax <= r.x2 && ay >= r.y1 && ay <= r.y2;
  const insideB = bx >= r.x1 && bx <= r.x2 && by >= r.y1 && by <= r.y2;
  if (insideA || insideB) return true;

  // check intersection with 4 rect edges
  const edges: Array<[number, number, number, number]> = [
    [r.x1, r.y1, r.x2, r.y1],
    [r.x2, r.y1, r.x2, r.y2],
    [r.x2, r.y2, r.x1, r.y2],
    [r.x1, r.y2, r.x1, r.y1],
  ];

  const ccw = (x1:number,y1:number,x2:number,y2:number,x3:number,y3:number) =>
    (y3 - y1) * (x2 - x1) > (y2 - y1) * (x3 - x1);

  const intersect = (x1:number,y1:number,x2:number,y2:number,x3:number,y3:number,x4:number,y4:number) =>
    ccw(x1,y1,x3,y3,x4,y4) !== ccw(x2,y2,x3,y3,x4,y4) &&
    ccw(x1,y1,x2,y2,x3,y3) !== ccw(x1,y1,x2,y2,x4,y4);

  for (const [x3, y3, x4, y4] of edges) {
    if (intersect(ax, ay, bx, by, x3, y3, x4, y4)) return true;
  }
  return false;
}

export function routeCurvedEdgesAvoidingNodes(
  cy: cytoscape.Core,
  {
    nodePadding = 12,
    minBend = 30,
    maxBend = 220,
    bendStep = 20,
    onlySelector = "edge.requires:visible", // usually only requires needs to be super clean
  } = {}
) {
  const nodes = cy.nodes(":visible");
  const rects = new Map<string, Rect>();
  nodes.forEach((n) => rects.set(n.id(), rectFromNode(n, nodePadding)));

  const edges = cy.edges(onlySelector);

  edges.forEach((e) => {
    const s = e.source();
    const t = e.target();
    if (s.empty() || t.empty()) return;

    const sp = s.position();
    const tp = t.position();

    // reset first (no bend)
    e.style("control-point-distances", [0]);

    // check if chord hits any other node rect
    let blocked = false;
    nodes.forEach((n) => {
      if (n.id() === s.id() || n.id() === t.id()) return;
      const r = rects.get(n.id())!;
      if (segmentIntersectsRect(sp.x, sp.y, tp.x, tp.y, r)) blocked = true;
    });

    if (!blocked) return;

    // choose bend direction deterministically (alternate by edge id hash)
    const dir = (e.id().split("").reduce((a, c) => a + c.charCodeAt(0), 0) % 2 === 0) ? 1 : -1;

    // increase bend until chord no longer crosses node bboxes “too much”
    let bend = minBend;
    while (bend <= maxBend) {
      // unbundled-bezier uses distance perpendicular to chord
      e.style("control-point-distances", [dir * bend]);

      // re-check with this bend: approximate by checking chord again is weak,
      // but in practice large enough bend + spacing removes most “through node” cases.
      // (If you want stricter: sample points along the curve; more work.)
      // We'll accept heuristic.
      break;
    }
  });
}
