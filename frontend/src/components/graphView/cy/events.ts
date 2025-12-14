import type cytoscape from "cytoscape";
import type { NodeOut } from "@/components/graphView/types";

export function installGraphEvents(opts: {
  cy: cytoscape.Core;
  onSelect: (n: NodeOut | null) => void;
  restoreAll: () => void;
  highlightSelected: (id: string) => void;
  shouldHighlight: () => boolean;
}) {
  const { cy, onSelect, restoreAll, highlightSelected, shouldHighlight } = opts;

  // node click
  cy.on("tap", "node", (evt) => {
    cy.$("node").unselect();
    evt.target.select();

    const d = evt.target.data();
    const node: NodeOut = { id: d.id, slug: d.slug, title: d.title, summary: d.summary ?? null };
    onSelect(node);

    console.log("[tap] node", d.id, "highlight?", shouldHighlight());

    if (shouldHighlight()) {
      restoreAll();
      highlightSelected(d.id);
    }
  });

  // background click
  cy.on("tap", (evt) => {
    if (evt.target !== cy) return;

    cy.$("node").unselect();
    onSelect(null);

    // if highlight mode is on, still restore visuals on deselect
    restoreAll();

    console.log("[tap] background -> cleared selection");
  });
}
