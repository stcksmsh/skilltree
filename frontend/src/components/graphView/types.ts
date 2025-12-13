export type NodeOut = { id: string; slug: string; title: string; summary?: string | null };

export type EdgeOut = {
  id: string;
  source: string;
  target: string;
  type: "requires" | "recommended";
  rank?: number | null;
};

export type RelatedOut = { a: string; b: string };

export type GraphOut = { nodes: NodeOut[]; edges: EdgeOut[]; related: RelatedOut[] };
