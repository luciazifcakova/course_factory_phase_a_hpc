# Commit 004.8

## Commit message

```text
fix(execution): make planner output contracts authoritative

- separate planner-owned output_contracts from LLM-declared outputs
- never treat scripts/*.R as an R execution output
- make figures/* accept PNG or PDF only
- validate execution using actual files matched against planner contracts
- keep LLM expected_outputs as provenance/static metadata only
- allow repair to choose new concrete filenames inside fixed contracts
- prevent repair metadata from redefining workflow success
- detect implicit Rplots.pdf as failure to satisfy figures/*
- explicitly require every plot to be saved under figures/
- add LES-006 regression tests
```
