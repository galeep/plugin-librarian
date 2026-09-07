#!/usr/bin/env python3
"""Recompute the default-seed baseline clustering and diff it against the archive.

Reproduces the archived clustering from the pinned corpus, then reports where the
recomputed clusters and the archived ones disagree: clusters present in only one of
them, and every file whose cluster membership differs.

Reuses `order_permutation.py`'s loader, signature and greedy code, so this recompute is
the same procedure the seed-robustness and order-permutation runs use.

Inputs. LIBRARIAN_CORPUS (required) names the pinned March corpus; see
paper/supplementary/repository-commits.md. `order_permutation.require_corpus()` stops
the run at import time when it is unset or names no directory. The file list is the
`file_index` of `scan_20260314_threshold90_skillonly.json`.

Output: the diff report on stdout, which is the result. `sigs.pkl` and
`clusterings.pkl` are written to CLUSTER_GAP_OUT (default: the current directory) so a
second analysis need not recompute the signatures; they are intermediates, not results,
and are safe to delete.

Runtime is dominated by signature computation over 31,634 files.

Run:
  LIBRARIAN_CORPUS=$LIBRARIAN_CORPUS CLUSTER_GAP_OUT=out python \
    paper/sources/scans/cluster_gap_recompute.py | tee cluster-gap.txt
"""
import json, os, pickle, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "paper" / "sources" / "scans"))
sys.path.insert(0, str(REPO))
# The corpus comes from LIBRARIAN_CORPUS; order_permutation.require_corpus() stops
# the run at this import when it is unset or names no directory. No default here:
# a path from the author's machine would silently cluster the wrong tree.
import order_permutation as op
from datasketch import MinHashLSH
OUT = Path(os.environ.get("CLUSTER_GAP_OUT", ".")).expanduser()

scan = json.loads(op.SCAN.read_text())
files = op.load_files(scan)
print("files", len(files), "corpus", op.CORPUS, flush=True)
sigs, skipped = op.signatures(files)
print("sigs", len(sigs), "skipped", skipped, flush=True)
with open(OUT / "sigs.pkl", "wb") as fh:
    pickle.dump({"sigs": sigs, "skipped": skipped}, fh)
lsh = MinHashLSH(threshold=op.THRESHOLD, num_perm=op.NUM_PERM)
for i, m in sigs.items():
    lsh.insert(str(i), m)
keys = sorted(sigs)
base = op.greedy(lsh, sigs, keys)
print("recomputed clusters", len(base), "slots", sum(len(c) for c in base),
      "distinct", len({x for c in base for x in c}), flush=True)

arch = [frozenset(l["file_index"] for l in c["locations"]) for c in scan["clusters"]]
print("archived clusters", len(arch), "slots", sum(len(c) for c in arch),
      "distinct", len({x for c in arch for x in c}), flush=True)

bset, aset = set(base), set(arch)
only_arch = [c for c in arch if c not in bset]
only_new = [c for c in base if c not in aset]
print("only in archive:", len(only_arch))
print("only in recompute:", len(only_new))
fi = {e["file_index"]: e for e in scan["file_index"]}
def show(label, cl):
    for c in cl:
        print(f"\n[{label}] size={len(c)}")
        for i in sorted(c):
            e = fi[i]
            print(f"   {i}  {e['marketplace']}/{e['path']}")
show("ARCHIVE-ONLY", only_arch)
show("RECOMPUTE-ONLY", only_new)

# membership diff per file
ma = {}
for k, c in enumerate(arch):
    for x in c: ma.setdefault(x, set()).add(k)
mb = {}
for k, c in enumerate(base):
    for x in c: mb.setdefault(x, set()).add(k)
diff_files = sorted({x for x in set(ma) | set(mb)
                     if frozenset(map(lambda k: arch[k], ma.get(x, ())))
                     != frozenset(map(lambda k: base[k], mb.get(x, ())))})
print("\nfiles whose cluster membership differs:", len(diff_files))
for x in diff_files:
    e = fi[x]
    print(f"  {x} {e['marketplace']}/{e['path']}  archive_sets={[sorted(arch[k]) for k in sorted(ma.get(x,()))]}"
          f" recompute_sets={[sorted(base[k]) for k in sorted(mb.get(x,()))]}")
with open(OUT / "clusterings.pkl", "wb") as fh:
    pickle.dump({"base": base, "arch": arch}, fh)
