---
title: Viewport controls and finally dockerizing it
date: 2025-12-13
tags: [devlog, skilltree, docker]
---

Added path highlighting and proper viewport controls (pan/zoom that doesn't fight you), a reset for selection state, and cleaned up dismissing newly-added nodes. Then [split the page apart](https://github.com/stcksmsh/skilltree/commit/fd2cf2d669df8cf51b8c6980fdf7d74f72de0766) — toolbar and sidebar as their own components, and broke the graph view itself into separate Cytoscape modules instead of one growing file. A day later [made the whole thing actually run in Docker](https://github.com/stcksmsh/skilltree/commit/40f96346793f35380a9e010ee4201209a134f6f4) with a Makefile wrapping the common commands, plus a real README — up to then it was very much "works on my machine."
