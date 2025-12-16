// cy/style.ts
import type cytoscape from "cytoscape";
import type { StylesheetStyle } from "cytoscape";
import { VIEW_ANIM } from "@/components/graph/constants";
import { routeCurvedEdgesAvoidingNodes } from "./route";

// cy/style.ts
export const CY_STYLE: StylesheetStyle[] = [
  {
    selector: "node",
    style: {
      width: 44,
      height: 44,
      padding: "2px",
      label: "data(short_title)",
      "font-size": 9,
      "min-zoomed-font-size": 7,
      "text-max-width": "110px",
      "text-wrap": "ellipsis",
      "text-valign": "center",
      "text-halign": "center",
      "border-width": 1,
      "z-index": 10,
    },
  },
  {
    selector: "node.kind-group",
    style: {
      "shape": "round-rectangle",
      "border-width": 2,
      "font-size": 10,
    },
  },
  {
    selector: "node.has-variants",
    style: {
      "border-style": "dashed",
    },
  },
  {
    selector: "edge",
    style: {
      "curve-style": "unbundled-bezier",
      "control-point-weights": [0.5],         // single mid control point
      "control-point-step-size": 40,          // smoother
      "target-arrow-shape": "triangle",
      width: 2,
    },
  },
  { selector: "edge.requires", style: { width: 2.4 } },

  {
    selector: "edge.recommended",
    style: {
      "line-style": "dashed",
      label: "data(rank)",
      "font-size": 8,
      "text-rotation": "autorotate",
      opacity: 0.7,
      "line-opacity": 0.7,
    },
  },
  {
    selector: "edge.related",
    style: {
      "target-arrow-shape": "none",
      "line-style": "dotted",
      opacity: 0.35,
      "line-opacity": 0.35,
    },
  },
  { selector: ".hidden", style: { display: "none" } },
];


// Visible requires edges only (so edge toggles affect leveling)
const REQUIRES_VISIBLE = "edge.requires:visible";

export function computeRoots(cy: cytoscape.Core): cytoscape.CollectionReturnValue {
  // roots = nodes with NO incoming requires edges
  return cy.nodes().filter((n) => n.incomers(REQUIRES_VISIBLE).length === 0);
}

export function makeBreadthfirstLayout(cy: cytoscape.Core): cytoscape.LayoutOptions {
  const roots = computeRoots(cy);

  return {
    name: "breadthfirst",
    directed: true,

    // IMPORTANT: breadthfirst uses `orientation`, not `direction`
    orientation: "vertical", // top -> bottom levels

    // roots as Collection is supported; avoids weirdness with ids
    roots,

    // these are the main readability knobs:
    spacingFactor: VIEW_ANIM.layout.spacing_factor * 2.2, // <-- bump hard
    padding: VIEW_ANIM.layout.padding + 50,

    // reduce accidental overlap
    avoidOverlap: true,
    nodeDimensionsIncludeLabels: true,

    // keep deterministic-ish output
    circle: false,

    animate: true,
    animationDuration: VIEW_ANIM.layout.duration,
    animationEasing: VIEW_ANIM.easing,
  };
}


export function animateFitVisible(cy: cytoscape.Core) {
  const visible = cy.elements(":visible");
  if (visible.empty()) return;

  cy.animate(
    { fit: { eles: visible, padding: VIEW_ANIM.fit.padding } },
    { duration: VIEW_ANIM.fit.duration, easing: VIEW_ANIM.easing }
  );
}

export function runRelayout(cy: cytoscape.Core) {
  const layout = cy.layout({
    name: "dagre",

    // if requires arrows are prereq -> dependent, and you want basics at bottom:
    // BT puts sources lower and arrows generally flow upward.
    rankDir: "BT",

    // spacing knobs (these are the important ones)
    rankSep: 130, // distance between levels
    nodeSep: 70,  // distance between nodes in same level
    edgeSep: 20,  // distance between parallel edges

    // nicer long-edge routing
    ranker: "network-simplex",

    // animate
    animate: true,
    animationDuration: VIEW_ANIM.layout.duration,
    animationEasing: VIEW_ANIM.easing,

    // padding
    padding: VIEW_ANIM.layout.padding,
  } as any);

  layout.run();

  layout.one("layoutstop", () => {
    animateFitVisible(cy);
  });

  layout.one("layoutstop", () => {
    routeCurvedEdgesAvoidingNodes(cy, {
      onlySelector: "edge.requires:visible",
      nodePadding: 14,
      minBend: 40,
      maxBend: 240,
      bendStep: 20,
    });
    animateFitVisible(cy);
  });
}
