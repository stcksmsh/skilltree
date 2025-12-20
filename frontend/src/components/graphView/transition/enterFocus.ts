import type { Core } from "cytoscape";
import type { GraphOut } from "../types";

export async function enterFocusTransition(opts: {
  parentLayerKey: String;
  parentCy: Core;
  childGraph: GraphOut;
  layers: any[];
  setLayers: (l: any[]) => void;
  cyByKeyRef: React.MutableRefObject<Map<string, Core>>;
  registerCy: (key: string, cy: Core | null) => void;
  updateCamera: (pan: { x: number; y: number }, zoom: number) => void;
  onTopReady?: (cy: Core) => void;
}) {
  const {
    parentLayerKey,
    parentCy,
    childGraph,
    layers,
    setLayers,
    cyByKeyRef,
    updateCamera,
    onTopReady
  } = opts;

  const anchorZoom = parentCy.zoom();
  const anchorPan = parentCy.pan();

  const targetZoom = Math.min(anchorZoom * 1.4, 3);
  const incomingKey = `focus-${childGraph.root_id}-${Date.now()}`;

  // Mount incoming graph
  const nextLayers = [
    ...layers.map((l) => ({ ...l, active: false, opacity: 1 })),
    {
      key: incomingKey,
      graph: childGraph,
      opacity: 0,
      active: true,
    },
  ];

  setLayers(nextLayers);

  // Wait until the incoming layer actually registers its cy instance
  const waitForCy = async (key: string, maxFrames = 120): Promise<Core | null> => {
    for (let i = 0; i < maxFrames; i++) {
      await new Promise((r) => requestAnimationFrame(r));
      const cy = cyByKeyRef.current.get(key) ?? null;
      if (cy && !cy.destroyed()) {
        const c = cy.container();
        if (c && (c as any).isConnected) return cy;
      }
    }
    return null;
  };

  const incomingCy = await waitForCy(incomingKey);
  if (!incomingCy) return;

  // Collapse nodes to center
  const center = parentCy.extent();
  incomingCy.nodes().positions(() => ({
    x: (center.x1 + center.x2) / 2,
    y: (center.y1 + center.y2) / 2,
  }));

  // Camera animation (single authority)
  parentCy.stop();

  const anim = parentCy.animation(
    { zoom: targetZoom, pan: anchorPan },
    {
      duration: 700,
      easing: "ease-in-out-cubic",
      step: () => updateCamera(parentCy.pan(), parentCy.zoom()),
    }
  );
  anim.play();

  // Crossfade
  setLayers((ls) =>
    ls.map((l, i) =>
      i === ls.length - 1
        ? { ...l, opacity: 1 }
        : { ...l, opacity: 0 }
    )
  );

  // Dagre expansion
  incomingCy.layout({
    name: "dagre",
    fit: false,
    animate: true,
    animationDuration: 500,
    animationEasing: "ease-out-cubic",
  }).run();

  // Cleanup after camera finishes (no timeouts)
  await anim.promise("completed");

  // Keep only the incoming layer
  setLayers((ls) => ls.filter((l) => l.key === incomingKey).map((l) => ({ ...l, active: true, opacity: 1 })));

  // Ensure external cyRef points to the topmost active instance
  onTopReady?.(incomingCy);
}
