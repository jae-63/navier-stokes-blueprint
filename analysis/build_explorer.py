"""Build the explorer page's data from the spine analysis.

Assigns each module to a paper section by name rules (the Lean sources cite an
earlier draft's numbering, so the mapping is inferred), keeps the dominator-tree
nodes that own at least MIN_WEIGHT source lines, and writes either a summary
(--report) or the final HTML page with the data inlined.

Usage:
  python3 -I build_explorer.py ns-cone.json --report
  python3 -I build_explorer.py ns-cone.json --template page.html --out index.html
"""

import argparse
import json
import re
from collections import Counter, defaultdict

COMMIT = "f9e8bc5b38b6e212696e8a30e3e91517af887bbd"
MIN_WEIGHT = 120
ROOT = "__ROOT__"

# (key, label, paper page, rules). First matching rule wins; rules match the
# module name without the `NavierStokes.` prefix.
SECTIONS = [
    ("s10", "§10 Compact forcing and breakdown", 116,
     [r"^R3\.", r"^R3[A-Z]", r"Uniqueness", r"^Comparator", r"^Periodic", r"PressureFlux",
      r"Energy(Absorption|Comparison)", r"^ProblemStatement", r"^ActualCandidate$",
      r"Localization", r"Breakdown"]),
    ("s5", "§5 Correcting the base to every order", 45,
     [r"Slow", r"Borel", r"BaseResidual", r"BaseEdge", r"AlignedBase", r"BaseContext",
      r"^HarmonicResidual", r"BaseChart", r"BasePhase", r"Base"]),
    ("s6", "§6 Auxiliary torus and separated supports", 62,
     [r"Torus", r"Band", r"Label", r"Dyadic", r"Partition", r"Periodized", r"Separat",
      r"Cover", r"Grid", r"Cell", r"Chart", r"Slot", r"ReservedPatch"]),
    ("s7", "§7 Oscillatory pulses and their stress", 73,
     [r"Phase", r"Frame", r"Pulse", r"GrowingMode", r"Primary", r"Covariance", r"Curl", r"Wave",
      r"Harmonic"]),
    ("s8", "§8 Compactly supported mean corrections", 88,
     [r"Mean", r"Gauge", r"PressureStream", r"Rank", r"MomentBalance", r"TransportPrimitive",
      r"Compatib", r"Volterra"]),
    ("s9", "§9 Correction cycles and the local field", 100,
     [r"Correction", r"Cycle", r"Particular", r"Signed", r"Initial", r"Stage", r"Candidate",
      r"Residual", r"Excluded", r"Request", r"Coherence", r"Physical"]),
    ("s4", "§4 + App. A–C Leading profile and stress cone", 24,
     [r"Profile", r"Cone", r"Axis", r"Heat", r"Terminal", r"Outgoing", r"Tail", r"Activation",
      r"Entrance", r"Modulat", r"Matching", r"Reference", r"Transition", r"Moment", r"Loop",
      r"Ramp", r"Reset", r"Stock", r"Debt", r"Repair", r"Shape", r"Nominal", r"Stress",
      r"Lag", r"Switch", r"Compensation", r"Annulus", r"History", r"Histories",
      r"Similarity", r"PressureDatum", r"Natural"]),
]
SHARED = ("sx", "Shared analysis tools", None)
SECTION_ORDER = ["s4", "s5", "s6", "s7", "s8", "s9", "s10", "sx"]


def section_of(module):
    short = module.removeprefix("NavierStokes.")
    for key, _, _, rules in SECTIONS:
        if any(re.search(r, short) for r in rules):
            return key
    return "sx"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cone")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--template")
    ap.add_argument("--out")
    args = ap.parse_args()

    c = json.load(open(args.cone))
    nodes = {n["id"]: n for n in c["nodes"]}
    mod_doc = {m["module"]: m["doc"] for m in c["modules"]}

    keep = {i for i, n in nodes.items() if n["domWeight"] >= MIN_WEIGHT} | set(c["roots"])
    # Keep ancestors so every kept node has a path to the root.
    for i in list(keep):
        p = nodes[i]["idom"]
        while p != ROOT and p not in keep:
            keep.add(p)
            p = nodes[p]["idom"]

    lines_by_section = Counter()
    for n in nodes.values():
        lines_by_section[section_of(n["module"])] += n["lines"]

    if args.report:
        total = sum(lines_by_section.values())
        print(f"kept nodes: {len(keep)} of {len(nodes)}")
        for k in SECTION_ORDER:
            print(f"  {k:4s} {lines_by_section[k] * 100 / total:5.1f}%")
        mods = Counter()
        for n in nodes.values():
            if section_of(n["module"]) == "sx":
                mods[n["module"]] += n["lines"]
        print("largest unassigned modules:")
        for m, l in mods.most_common(25):
            print(f"  {l:6d} {m}")
        return

    order = sorted(keep, key=lambda i: (-nodes[i]["domWeight"], i))
    idx = {i: k for k, i in enumerate(order)}
    modules = sorted({nodes[i]["module"] for i in keep})
    midx = {m: k for k, m in enumerate(modules)}

    # Aggregate what each kept node dominates but is not kept itself.
    hidden_lines = defaultdict(int)
    hidden_count = defaultdict(int)
    for i, n in nodes.items():
        if i in keep:
            continue
        p = n["idom"]
        if p in keep or p == ROOT:
            hidden_lines[p] += n["domWeight"]
            hidden_count[p] += n["domSize"]

    out_nodes = []
    for i in order:
        n = nodes[i]
        sig = n["signature"]
        out_nodes.append([
            n["name"],                                   # 0 name
            n["kind"],                                   # 1 kind
            midx[n["module"]],                           # 2 module index
            n["startLine"], n["endLine"],                # 3, 4
            n["domWeight"], n["domSize"], n["fanIn"],    # 5, 6, 7
            idx.get(n["idom"], -1),                      # 8 parent (-1 = root)
            n["doc"] or "",                              # 9
            sig if len(sig) <= 1500 else sig[:1500] + " …",  # 10
            sorted({idx[d] for d in n["deps"] if d in idx}),  # 11 uses (kept only)
            hidden_lines[i], hidden_count[i],            # 12, 13
            len(n["deps"]),                              # 14 total project deps
            n["lines"],                                  # 15 own lines
        ])

    def first_para(docs):
        text = "\n".join(docs or [])
        text = re.sub(r"^#+ .*$", "", text, flags=re.M).strip()
        return text.split("\n\n")[0].replace("\n", " ")[:400] if text else ""

    def title(docs):
        for d in docs or []:
            for line in d.splitlines():
                if line.startswith("# "):
                    return line[2:].strip()
        return ""

    out_modules = [[m, section_of(m), title(mod_doc.get(m)), first_para(mod_doc.get(m))]
                   for m in modules]
    sections = [[k, lbl, page] for k, lbl, page, _ in SECTIONS] + [list(SHARED)]
    data = {
        "commit": COMMIT,
        "totalDecls": c["totalDecls"], "coneDecls": c["coneDecls"],
        "coneLines": c["coneLines"], "minWeight": MIN_WEIGHT,
        "sections": sorted(sections, key=lambda s: SECTION_ORDER.index(s[0])),
        "sectionLines": {k: lines_by_section[k] for k in SECTION_ORDER},
        "modules": out_modules, "nodes": out_nodes,
        "rootHidden": [hidden_lines[ROOT], hidden_count[ROOT]],
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = open(args.template).read().replace("/*__DATA__*/null", payload)
    open(args.out, "w").write(html)
    print(f"wrote {args.out}: {len(out_nodes)} nodes, {len(html) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
