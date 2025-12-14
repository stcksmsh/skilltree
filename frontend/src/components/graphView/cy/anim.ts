import type cytoscape from "cytoscape";

export const HIGHLIGHT_ANIM = {
  duration: 220,
  easing: "ease-in-out" as const,
};

type Animatable = {
  stop: (clearQueue?: boolean, jumpToEnd?: boolean) => any;
  animate: (props: any, params?: any) => any;
};

export function anim(col: Animatable, style: any) {
  col.stop(true, false).animate({ style }, HIGHLIGHT_ANIM);
}

export function makeRestoreAll(cy: cytoscape.Core) {
  return () => {
    cy.batch(() => {
      anim(cy.nodes() as unknown as Animatable, {
        opacity: 1,
        "text-opacity": 1,
        "background-opacity": 1,
        "border-opacity": 1,
        "border-width": 1,
      });

      anim(cy.edges() as unknown as Animatable, { opacity: 1, width: 2 });
    });
  };
}
