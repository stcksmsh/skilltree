import type cytoscape from "cytoscape";

export const HIGHLIGHT_ANIM = {
  duration: 220,
  easing: "ease-in-out" as const,
};

export function anim(col: cytoscape.CollectionReturnValue, style: any) {
  (col as any).stop(true, false).animate({ style }, HIGHLIGHT_ANIM);
}

export function makeRestoreAll(cy: cytoscape.Core) {
  return () => {
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
}
