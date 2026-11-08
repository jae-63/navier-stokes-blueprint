"""Find the proof spine of the Navier–Stokes formalization.

Reads the extractor's JSON, restricts to the dependency cone of the main theorems,
and computes the dominator tree under a virtual root: declaration A dominates B when
every dependency chain from the main theorems down to B passes through A. Subtree
weights (source lines) show which declarations own large parts of the proof.

Usage: python3 -I spine.py decls.json out.json [--roots NAME ...]
"""

import argparse
import json
from collections import defaultdict

import networkx as nx

DEFAULT_ROOTS = [
    "NavierStokes.Comparator.navier_stokes_breakdown_R3",
    "NavierStokes.Comparator.navier_stokes_breakdown_periodic",
]
ROOT = "__ROOT__"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("decls")
    ap.add_argument("out")
    ap.add_argument("--roots", nargs="+", default=DEFAULT_ROOTS)
    args = ap.parse_args()

    data = json.load(open(args.decls))
    decls = {d["id"]: d for d in data["decls"]}
    modules = {m["module"]: m for m in data["modules"]}

    g = nx.DiGraph()
    g.add_nodes_from(decls)
    for d in decls.values():
        for dep in d["deps"]:
            if dep in decls:
                g.add_edge(d["id"], dep)
    for r in args.roots:
        if r not in decls:
            raise SystemExit(f"root not found: {r}")
        g.add_edge(ROOT, r)

    cone = nx.descendants(g, ROOT)
    sub = g.subgraph(cone | {ROOT})
    idom = nx.immediate_dominators(sub, ROOT)

    children = defaultdict(list)
    for n, p in idom.items():
        if n != ROOT:
            children[p].append(n)

    def lines(n):
        d = decls[n]
        return d["endLine"] - d["startLine"] + 1

    # Dominator-subtree weight, iteratively (the tree can be deep).
    weight, size = {}, {}
    order = list(nx.dfs_preorder_nodes(nx.DiGraph([(p, c) for p, cs in children.items() for c in cs]), ROOT))
    for n in reversed(order):
        w = 0 if n == ROOT else lines(n)
        s = 0 if n == ROOT else 1
        for c in children[n]:
            w += weight[c]
            s += size[c]
        weight[n], size[n] = w, s

    fan_in = {n: sum(1 for p in sub.predecessors(n) if p != ROOT) for n in cone}
    depth = {ROOT: 0}
    for n in order[1:]:
        depth[n] = depth[idom[n]] + 1

    nodes = []
    for n in sorted(cone):  # sorted: set order varies between runs
        d = decls[n]
        nodes.append({
            "id": n, "name": d["name"], "kind": d["kind"], "module": d["module"],
            "file": d["file"], "startLine": d["startLine"], "endLine": d["endLine"],
            "lines": lines(n), "signature": d["signature"], "doc": d["doc"],
            "typeDeps": [x for x in d["typeDeps"] if x in cone],
            "deps": [x for x in d["deps"] if x in cone],
            "mathlibDeps": d["mathlibDeps"],
            "idom": idom[n], "domDepth": depth[n], "domWeight": weight[n],
            "domSize": size[n], "fanIn": fan_in[n],
        })

    cone_mods = sorted({decls[n]["module"] for n in cone})
    total = weight[ROOT]
    out = {
        "roots": args.roots,
        "totalDecls": len(decls), "coneDecls": len(cone), "coneLines": total,
        "nodes": nodes,
        "modules": [modules[m] for m in cone_mods if m in modules],
    }
    json.dump(out, open(args.out, "w"))

    print(f"declarations: {len(decls)}  in cone: {len(cone)}  "
          f"cone lines: {total}  cone modules: {len(cone_mods)}")
    print("\nDominator tree (subtrees >= 1% of cone lines):")

    def show(n, indent):
        kids = sorted(children[n], key=lambda c: -weight[c])
        for c in kids:
            if weight[c] < total * 0.01:
                continue
            d = decls[c]
            print(f"{'  ' * indent}{weight[c] * 100 / total:5.1f}%  {d['name']}  "
                  f"[{d['kind']}, {d['module'].removeprefix('NavierStokes.')}]")
            show(c, indent + 1)

    show(ROOT, 0)

    print("\nMost-used declarations in the cone (infrastructure):")
    for n in sorted(cone, key=lambda n: -fan_in[n])[:15]:
        print(f"  {fan_in[n]:5d}  {decls[n]['name']}")


if __name__ == "__main__":
    main()
