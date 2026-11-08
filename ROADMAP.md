# Roadmap: toward a refactored Lean proof

Status as of 2026-11-08. Goal: a refactored Lean proof of the Navier–Stokes blowup
theorems that combines human insight (expert explanations, the paper's structure) with
the machine analysis already in this repository, and that a person can follow.

## Where things stand

- **Done:** extraction of the full declaration graph (`data/ns-decls.json.xz`), the
  dominator-tree analysis, and two reading aids: the
  [Blueprint](https://jae-63.github.io/navier-stokes-blueprint/blueprint.html) and the
  [Proof Atlas](https://jae-63.github.io/navier-stokes-blueprint/atlas.html).
- **Not started:** any change to the Lean proof itself.
- **Next human input:** watch the videos mathematicians have made explaining the
  proof, and note which ideas they treat as central. Their framing should decide
  which intermediate statements get names in the refactor.

## What the data is, and is not

`ns-decls.json` is a map of the proof, not the proof. For each of 32,730
declarations it records the name, statement, docstring, file and line, and
dependencies. It contains no proof terms or tactic scripts; those live in the Lean
source of [openai/NavierStokesAndEuler](https://github.com/openai/NavierStokesAndEuler)
(commit `f9e8bc5`). A refactor edits that source; the data and the blueprint tell you
where to cut.

## The anchor that keeps a refactor honest

The two top-level statements are fixed: `navier_stokes_breakdown_R3` and
`navier_stokes_breakdown_periodic`, copied verbatim from DeepMind's
formal-conjectures (Fefferman's alternatives (C) and (D)). Whatever is restructured,
the result must still prove exactly these, and `#print axioms` must stay clean
(only Lean's standard axioms). Lean rechecks everything after each change, so every
step is either verified or rejected.

## Plan, in order of payoff

### 1. A readable interface theorem in the middle

The paper's **Theorem 3.1** is the natural interface: local fields near the singular
point with (i) a divergence-free representation u = curl A + B e_θ, (ii) bounded
derivatives up to t = 1 away from the origin, (iii) a residual flat to every order at
the singular point, and (iv) the growth asymptotic (3.6).

The Lean proof has no theorem matching it. The closest is
`GermCandidateAssembly.exists_candidate_witness_of_finite_stages`, whose statement
runs to dozens of lines. Plan:

- State Theorem 3.1 cleanly in Lean.
- Split the proof into:
  - **(a) Theorem 3.1 ⇒ Clay (C)/(D):** localization, force extension, uniqueness,
    periodization. Small (a few percent of the code) and human-checkable.
  - **(b) Theorem 3.1:** the construction.

This turns "trust 230k lines" into "trust one readable statement plus a construction".

### 2. Remove what the main theorems don't use

About 8,900 of the 32,730 extracted declarations lie outside the dependency cone of
the two main theorems. Some are deliberate (`PaperResults` holds extra results from
the paper); others are likely leftovers. The cone in `data/ns-cone.json` (rebuild with
`analysis/spine.py`) lists exactly what is used.

### 3. Collapse wrapper layers

Module families such as `Actual*`, `Germ*` and `Mixed*` look like a general theorem
restated through several layers to fit the specific construction, which is typical of
AI-written proofs. The dominator tree (Proof Atlas) shows which layers carry real
content and which only restate.

### 4. Separate general analysis from Navier–Stokes-specific work

About 48% of the code is machinery shared by several branches of the construction
(see the Blueprint's ownership chart). Much of it is probably general analysis that
could become standalone lemmas, possibly suitable for Mathlib. Classifying it needs a
human expert.

## Practical notes

- **Where to work:** in a fork of openai/NavierStokesAndEuler. Keep this repository as
  the map, and regenerate the blueprint as the structure changes.
- **Building:** Lean 4.34.0-rc2 and Mathlib. On macOS 27 the pinned toolchain's `lake`
  crashes, so builds run in a Linux VM (Lima) with about 10 GB of memory, on the VM's
  own disk (a virtiofs-shared folder fails with "Too many open files"). Full rebuilds
  are slow, so restructure module by module.
- **Workflow template:** the agent-team setup in
  [uda-lab/leray-hopf](https://github.com/uda-lab/leray-hopf) (architect, planner,
  coder, prover roles; rules such as "never weaken a statement" and "no new axioms")
  fits this work almost unchanged.

## Suggested first session

1. Confirm the VM build of openai/NavierStokesAndEuler still succeeds.
2. Draft the Theorem 3.1 statement in Lean, matching the paper's (i)–(iv).
3. Plan the split (a)/(b), identifying which existing declarations feed each side.
