# Navier–Stokes Blueprint

Reading aids for OpenAI's 2026 Lean proof of Navier–Stokes blowup: a dependency
blueprint and plain-language statements, toward a human-readable proof.

**View the pages:** https://jae-63.github.io/navier-stokes-blueprint/

## Background

In 2026 OpenAI released
["Finite time blowup for Navier–Stokes"](https://cdn.openai.com/pdf/32d9f210-8b73-45e0-91bc-82a30aef8a9a/navier-stokes.pdf)
together with a Lean 4 formalization in
[openai/NavierStokesAndEuler](https://github.com/openai/NavierStokesAndEuler). The
formalization proves alternatives (C) and (D) of the Clay Millennium problem
statement: for every viscosity there is a smooth force for which no global smooth
solution exists, on ℝ³ and on the torus. The proof is machine-checked, but it is
about 230,000 lines of Lean spread over roughly 600 modules, which no person reads
end to end.

Long proofs usually become understood the same way: someone finds the one or two key
ideas, restructures the argument around them, and lays out which results depend on
which. Large Lean projects do this with a *blueprint*, a human-readable dependency
graph of the main definitions and theorems. This repository starts that work for
the Navier–Stokes formalization.

## The pages

- **[Blueprint](https://jae-63.github.io/navier-stokes-blueprint/blueprint.html)**:
  75 key declarations, from the two Clay statements down to the axisymmetric base
  flow. Each has a one-line informal statement, its Lean name and location, and its
  dependencies. It also summarizes the proof's one central idea and what the Lean
  statement does and does not certify.
- **[Proof Atlas](https://jae-63.github.io/navier-stokes-blueprint/atlas.html)**:
  the dominator tree of the whole proof. A declaration *dominates* another when every
  dependency chain from the main theorems to the second passes through the first, so
  the tree shows which parts of the code exist only to support which results.

## What we found so far

- **The top of the proof is a clean chain.** Clay statements → Theorem 1.1 at every
  viscosity (by scaling) → a uniqueness argument → one constructed solution at
  viscosity 1. These layers are under 5% of the code.
- **Below that it branches.** The construction splits into five cooperating parts:
  the base flow, the leading oscillatory waves, a correction iteration, the infinite
  sum of corrections, and localization to a compact force. About 48% of all lines are
  machinery shared by several of these branches.
- **What is certified.** The witness has zero initial velocity; a smooth force,
  compactly supported in space and in positive time, does all the work. "Blowup" means
  pointwise speed is unbounded as t → 1. The excluded competitors are any smooth global
  solutions with the same force and data (with bounded energy on ℝ³; on the torus not
  even that).

## Next steps

The plan for a refactored Lean proof is in [ROADMAP.md](ROADMAP.md).

## Caveats

- The informal statements were written by an AI model (Claude) from each
  declaration's Lean signature and docstring. They are paraphrases for orientation,
  not verified mathematics. Corrections are welcome.
- The Lean comments cite an earlier draft of the paper, so the paper section numbers
  shown on both pages were matched by content and are approximate.
- The choice of the 75 blueprint nodes is a judgment call guided by the dominator
  tree; a different selection would show the same structure at a different grain.

## Repository layout

| Path | Contents |
|---|---|
| `extract/Extract.lean` | Declaration-graph extractor, run inside the built Lean project. Adapted from [uda-lab/leray-hopf](https://github.com/uda-lab/leray-hopf)'s `ExtractNotes.lean` (Apache-2.0). |
| `data/ns-decls.json.xz` | Full extraction at commit `f9e8bc5`: 32,730 declarations with signatures, docstrings, source locations and dependencies (101 MB uncompressed). Checksums in `data/SHA256SUMS`. |
| `data/module-list.txt` | The modules the extraction covered. |
| `analysis/spine.py` | Restricts to the dependency cone of the two main theorems and computes the dominator tree (needs `networkx`). |
| `analysis/build_explorer.py`, `analysis/atlas-template.html` | Build the Proof Atlas. |
| `analysis/blueprint/nodes.py` | The hand-picked blueprint nodes and their informal statements. Edit this to change the blueprint. |
| `analysis/blueprint/build_blueprint.py`, `template.html` | Build the Blueprint. |
| `scripts/build_site.sh` | Rebuild both pages into `docs/`. |
| `docs/` | The published site (GitHub Pages). |

## Rebuilding

From the saved extraction (a minute or two, Python 3 with `networkx`):

```sh
xz -dk data/ns-decls.json.xz
(cd data && shasum -a 256 -c SHA256SUMS)   # optional integrity check
python3 -I analysis/spine.py data/ns-decls.json data/ns-cone.json
./scripts/build_site.sh
```

Re-extracting from Lean is slow: it needs a full build of
openai/NavierStokesAndEuler (Lean 4.34.0-rc2 and Mathlib), plenty of memory, and
about 15 minutes for the extraction itself:

```sh
cd NavierStokesAndEuler
lake exe cache get && lake build
lake env lean --run /path/to/extract/Extract.lean -- \
  --root NavierStokes.ComparatorSolution --prefix NavierStokes --out ns-decls.json
```

On macOS 27 the pinned toolchain's `lake` crashes, so this was run in a Linux VM.
Building from a virtiofs-shared folder there fails with "Too many open files"; build
on the VM's own disk.

## License

Apache-2.0. The analyzed proof is OpenAI's work and is licensed separately in its own repository.
