---
title: Nodes vs implementations, and the first focused views
date: 2025-12-16
tags: [devlog, skilltree, graph]
---

Split the data model: nodes are now abstract concepts with separate "impl" rows underneath them, plus [an `impl_contexts` table](https://github.com/stcksmsh/skilltree/commit/d9327d040d7c5032c57712f8624b338ea9e24af4) for which implementations apply in which context. That split is what makes a "focused" graph view possible — instead of always rendering the whole DAG, you can load a nested view centered on one node and its immediate context. Also [gave vertices a `short_title`](https://github.com/stcksmsh/skilltree/commit/b3868f0b65caeb1bc196563dbdc4807c651a24d5) for on-graph labels (the full titles were overlapping the connection lines, which looked exactly as bad as it sounds) and fixed a bug where focused views weren't correctly resolving which prerequisite impl to point an edge at.
