export type AbstractNodeOut = { 
  id: string;
  slug: string;
  title: string;
  short_title: string;
  summary: string | null;
  body_md: string | null;

  kind: string;
  parent_id: string | null;

  has_children: boolean;
  has_variants: boolean;

  default_impl_id: string | null;
  impls: ImplOut[];
};

export type ImplOut = {
  id: string;
  abstract_id: string;
  variant_key: string;
  contract_md: string | null;
};

export type EdgeOut = {
  id: string;
  src_impl_id: string;
  dst_impl_id: string;
  type: "requires" | "recommended";
  rank?: number | null;
};

export type RelatedEdgeOut = {
  a_id: string;
  b_id: string;
};

export type BoundaryHintOut = {
  group_id: string;
  title: string;
  short_title: string;
  type: "requires" | "recommended";
  count: number;
};

export type GraphOut = {
  abstract_nodes: AbstractNodeOut[];
  impl_nodes: ImplOut[];
  edges: EdgeOut[];
  related_edges: RelatedEdgeOut[];
  boundary_hints: BoundaryHintOut[];
};
