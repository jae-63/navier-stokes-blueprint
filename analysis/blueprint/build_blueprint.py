"""Build the blueprint page from the dependency cone.

Reads the cone written by `analysis/spine.py`, keeps the hand-picked nodes in
`nodes.py`, connects them through the declarations in between (an edge A -> B
means B is reachable from A without passing another blueprint node, after
transitive reduction), measures each node's dependency cone in source lines,
and attributes every declaration to its nearest blueprint node in the
dominator tree. The data is inlined into `template.html`.

Usage (from the repository root):
  python3 -I analysis/blueprint/build_blueprint.py data/ns-cone.json \
      --template analysis/blueprint/template.html --out docs/blueprint.html \
      [--json data/blueprint.json]

Takes about a minute; most of it is the transitive cone sizes.
"""

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nodes import NODES  # noqa: E402

# The ν = 1 candidate dominates the code that several branches share; lines it
# owns directly are reported as shared machinery rather than as one branch.
SHARED = "NavierStokesR3.ActualCandidate.selected_candidate_one_with_initial_rest"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cone")
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--json")
    args = ap.parse_args()

    data = json.load(open(args.cone, encoding="utf-8"))
    N = {n["id"]: n for n in data["nodes"]}
    ch = {i: [c for c in set(n["deps"]) | set(n["typeDeps"]) if c in N and c != i]
          for i, n in N.items()}

    # Transitive cone of every declaration, as bitsets, then its size in lines.
    ids = list(N)
    idx = {i: k for k, i in enumerate(ids)}
    sys.setrecursionlimit(100000)
    memo = {}

    def cone(i):
        if i in memo:
            return memo[i]
        memo[i] = 0
        b = 1 << idx[i]
        for c in ch[i]:
            b |= cone(c)
        memo[i] = b
        return b

    lines = [N[i]["lines"] for i in ids]

    def cone_lines(i):
        b, s = cone(i), 0
        while b:
            low = b & -b
            s += lines[low.bit_length() - 1]
            b ^= low
        return s

    def full(q):
        for c in ("NavierStokes." + q, q):
            if c in N:
                return c
        sys.exit(f"blueprint node not found in cone: {q}")

    sel = [full(n[0]) for n in NODES]
    S = set(sel)

    # Edges between blueprint nodes through non-blueprint declarations.
    edges = {}
    for i in sel:
        out, seen, st = set(), {i}, list(ch[i])
        while st:
            c = st.pop()
            if c in seen:
                continue
            seen.add(c)
            if c in S:
                out.add(c)
            else:
                st.extend(ch[c])
        edges[i] = out
    reach = {}

    def R(i):
        if i not in reach:
            s = set()
            for c in edges[i]:
                s |= {c} | R(c)
            reach[i] = s
        return reach[i]

    for i in sel:
        R(i)
    reduced = {i: {c for c in edges[i] if not any(c in reach[d] for d in edges[i] if d != c)}
               for i in sel}

    # Ownership: nearest blueprint ancestor in the dominator tree.
    group = {full(n[0]): n[2] for n in NODES}
    own_memo = {}

    def owner(i):
        if i in own_memo:
            return own_memo[i]
        if i == SHARED:
            o = "Shared machinery"
        elif i in group:
            o = group[i]
        else:
            p = N[i]["idom"]
            o = "Theorem 1.1 & corollary" if (not p or p not in N) else owner(p)
        own_memo[i] = o
        return o

    ownership = Counter()
    for i, n in N.items():
        ownership[owner(i)] += n["lines"]

    out = []
    for spec, i in zip(NODES, sel):
        x = N[i]
        out.append(dict(
            id=i, name=i.replace("NavierStokes.", ""), label=spec[1], group=spec[2],
            paper=spec[3], stmt=spec[4], kind=x["kind"], file=x["file"], line=x["startLine"],
            cone=cone_lines(i), own=x["domWeight"],
            deps=sorted(reduced[i], key=sel.index)))
    result = dict(nodes=out, totalLines=data["coneLines"], totalDecls=data["coneDecls"],
                  ownership=dict(sorted(ownership.items(), key=lambda kv: (-kv[1], kv[0]))))

    if args.json:
        json.dump(result, open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    html = open(args.template, encoding="utf-8").read().replace(
        "__DATA__", json.dumps(result, ensure_ascii=False))
    open(args.out, "w", encoding="utf-8").write(html)
    print(f"{len(out)} nodes, {sum(len(o['deps']) for o in out)} edges -> {args.out}")


if __name__ == "__main__":
    main()
