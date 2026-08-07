# Commit 004.2

## Commit message

```text
fix(outputs): allow multiple figures per R lesson

- change figure workflow contracts from one fixed PNG to figures/*.png
- treat workflow outputs as glob-style artifact contracts
- allow generated R scripts to declare multiple concrete figure files
- require every declared figure to satisfy a workflow output contract
- require every workflow output contract to have at least one match
- keep execution validation exact for the concrete files actually declared
- preserve self-healing execution for any missing concrete output
- keep artifact discovery lesson-specific through isolated task directories
- update R prompts to explicitly allow multiple figures
- add regression tests for multi-figure generation
```

A lesson such as "Scatter plots and line charts" may now generate:

```text
figures/scatter_plot.png
figures/line_chart.png
```

instead of being forced into:

```text
figures/LES-002.png
```

The execution report registers both outputs separately so downstream
slide generation can choose the appropriate figure for each slide.
