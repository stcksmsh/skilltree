import type { Stylesheet } from "cytoscape";

export const CY_STYLE: Stylesheet[] = [
  {
    selector: "node",
    style: {
      label: "data(title)",
      "text-wrap": "wrap",
      "text-max-width": 150,
      "font-size": 10,
      "border-width": 1,
      "transition-property": "opacity, text-opacity, background-opacity, border-opacity, border-width",
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
  { selector: ".hidden", style: { display: "none" } },
];

export const CY_LAYOUT = { name: "breadthfirst", directed: true, padding: 30 } as const;
