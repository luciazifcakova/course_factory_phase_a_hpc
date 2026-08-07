# Commit 004.7

## Commit message

```text
fix(figures): restrict outputs to PNG/PDF and make execution repair tolerant

- allow only PNG/PDF figure outputs
- prefer PNG for slide-ready figures
- prohibit SVG/svglite-dependent figure generation
- discourage fabricated ggplot2 helpers such as coord_log10()
- guide logarithmic axes toward scale_x_log10()/scale_y_log10()
- allow repair to drop unsupported figure formats such as SVG
- preserve original output contracts when repair returns []
- forbid repair from inventing unrelated output paths
- require at least one usable PNG/PDF figure after repair
- add regression tests for both observed HPC failures
```
