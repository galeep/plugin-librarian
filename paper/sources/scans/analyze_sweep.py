#!/usr/bin/env python3
r"""Threshold sweep: clusters, cluster rate, precision and recall per Jaccard threshold.

Reads the six archived scans `scan_20260314_threshold{70,75,80,85,90,95}_skillonly.json`
beside this script and reports, per threshold: total clusters, cluster memberships
(the scan's `files_in_clusters`, a sum of cluster sizes), membership rate, precision at
cluster size thresholds >=5, >=10, >=15 and >=20, recall against the hightower6eu skill
slugs, and scaffold cluster counts.

Supports Table 2 and Figure 1 (both Section 4.1, Ecosystem Characterization) and the
threshold-selection result of Section 3.3 (Similarity Analysis), which reports recall
over the hightower6eu subset holding constant across all six thresholds. Section 3.3
states that recall over the 352 slugs the scan indexed; the Recall column here divides
the same numerator by the 354 slugs `paper/iocs.json` records, so the two differ in
denominator and agree on the invariance. The Clusters, P@>=20 and P@>=10 columns of Table 2
are this script's Clusters, P@20 and P@10. Table 2's Files and % columns count distinct
clustered files (7,061 at 90%), which `table2_distinct_files.py` computes; this script's
"In clusters" and "Rate" columns count memberships (7,147 and 22.6% at 90%), which run
higher because clusters overlap.

A cluster counts as a true positive when any of its files has a path component equal
to one of the eleven attacker accounts listed in `paper/iocs.json`. Recall is the share
of the 354 hightower6eu slugs in `paper/iocs.json` (353 with payload, 1 without) whose
skill file appears in at least one cluster; Koi's full list has 341 slugs and its recall
is reported separately in Section 4.4.

Inputs: the six archived scans beside this script and `paper/iocs.json`. The script
does not read the corpus, does not use the network, and has no random component;
LIBRARIAN_CORPUS is not required.

Output: a per-threshold report and a summary table on stdout. Nothing is written to
disk.

Run from the repository root:
  python paper/sources/scans/analyze_sweep.py
"""

import json
import sys
from pathlib import Path

# The eleven attacker accounts of paper/iocs.json (clawhub_authors keys).
MALICIOUS_AUTHORS = {
    "hightower6eu", "sakaen736jih", "thiagoruss0", "zaycv",
    "jordanprater", "stveenli", "anisafifi", "timclawbot",
    "kenblive", "mupengi-bot", "moonshine-100rze",
}

# Recall denominator: the 354 hightower6eu slugs recorded in paper/iocs.json
# (Koi's full list, 341 slugs across all accounts, is reported in Section 4.4).
IOC_FILE = Path(__file__).parent.parent.parent / "iocs.json"


def load_ioc_slugs():
    """Return the hightower6eu skill slugs (with and without payload) from iocs.json."""
    with open(IOC_FILE) as f:
        data = json.load(f)
    authors = data["clawhub_authors"]  # dict keyed by ClawHub username
    h6 = authors.get("hightower6eu", {})
    slugs = set(h6.get("skill_slugs_with_payload", []))
    slugs.update(h6.get("skill_slugs_without_payload", []))
    return slugs


def is_malicious_cluster(cluster, file_index):
    """True when any file in the cluster sits under an attacker account.

    ClawHub paths have the form <account>/<slug>/SKILL.md, so the account is a path
    component. Both the location path and the file_index path are checked.
    """
    for loc in cluster.get("locations", []):
        marketplace = loc.get("marketplace", "")
        plugin = loc.get("plugin", "")
        path = loc.get("path", "")

        # Any path component equal to an attacker account marks the cluster.
        parts = path.split("/")
        for part in parts:
            if part in MALICIOUS_AUTHORS:
                return True

        # The file_index entry carries the resolved path; check it as well.
        fidx = loc.get("file_index")
        if fidx is not None and fidx < len(file_index):
            fi = file_index[fidx]
            fi_path = fi.get("path", "")
            fi_parts = fi_path.split("/")
            for part in fi_parts:
                if part in MALICIOUS_AUTHORS:
                    return True
    return False


def analyze_scan(scan_path):
    """Compute the per-threshold row for one archived scan file."""
    with open(scan_path) as f:
        data = json.load(f)

    meta = data["metadata"]
    summary = data["summary"]
    clusters = data.get("clusters", [])
    file_index = data.get("file_index", [])

    threshold = meta["similarity_threshold"]
    total_files = summary["total_files_scanned"]
    files_in_clusters = summary["files_in_clusters"]
    num_clusters = summary["unique_clusters"]
    by_type = summary.get("by_type", {})

    # Recall denominator (354 hightower6eu slugs).
    ioc_slugs = load_ioc_slugs()

    # Slugs whose file appears in at least one cluster.
    found_ioc_slugs = set()
    for c in clusters:
        for loc in c.get("locations", []):
            fidx = loc.get("file_index")
            if fidx is not None and fidx < len(file_index):
                fi = file_index[fidx]
                plugin = fi.get("plugin", "")
                path = fi.get("path", "")
                if "hightower6eu" in path:
                    # Slug is the component after the account: hightower6eu/<slug>/SKILL.md
                    parts = path.split("/")
                    for i, p in enumerate(parts):
                        if p == "hightower6eu" and i + 1 < len(parts):
                            found_ioc_slugs.add(parts[i + 1])

    # Precision at cluster size thresholds; Table 2 reports >=20 and >=10.
    size_thresholds = [5, 10, 15, 20]
    precision_results = {}

    for min_size in size_thresholds:
        large_clusters = [c for c in clusters if c["size"] >= min_size]
        if not large_clusters:
            precision_results[min_size] = {"precision": None, "count": 0, "malicious": 0}
            continue
        mal_count = sum(1 for c in large_clusters if is_malicious_cluster(c, file_index))
        precision_results[min_size] = {
            "precision": mal_count / len(large_clusters) * 100,
            "count": len(large_clusters),
            "malicious": mal_count,
        }

    # Scaffold clusters (type "scaffold" in the scan output).
    scaffold_clusters = [c for c in clusters if c.get("type") == "scaffold"]
    scaffold_mal = sum(1 for c in scaffold_clusters if is_malicious_cluster(c, file_index))

    recall = len(found_ioc_slugs) / len(ioc_slugs) * 100 if ioc_slugs else 0

    return {
        "threshold": threshold,
        "total_files": total_files,
        "files_in_clusters": files_in_clusters,
        "cluster_rate": files_in_clusters / total_files * 100,
        "num_clusters": num_clusters,
        "by_type": {k: v["clusters"] for k, v in by_type.items()},
        "ioc_recall": recall,
        "ioc_found": len(found_ioc_slugs),
        "ioc_total": len(ioc_slugs),
        "precision": precision_results,
        "scaffold_total": len(scaffold_clusters),
        "scaffold_malicious": scaffold_mal,
    }


def main():
    scan_dir = Path(__file__).parent
    scans = sorted(scan_dir.glob("scan_*_threshold*_skillonly.json"))

    if not scans:
        print("No scan files found.")
        sys.exit(1)

    print(f"Found {len(scans)} scan files\n")
    print("=" * 80)

    results = []
    for scan_path in scans:
        print(f"\nAnalyzing: {scan_path.name}")
        try:
            r = analyze_scan(scan_path)
            results.append(r)
            print(f"  Threshold: {r['threshold']:.0%}")
            print(f"  Clusters: {r['num_clusters']}")
            print(f"  Files in clusters: {r['files_in_clusters']} ({r['cluster_rate']:.1f}%)")
            print(f"  By type: {r['by_type']}")
            print(f"  IOC recall: {r['ioc_found']}/{r['ioc_total']} ({r['ioc_recall']:.1f}%)")
            print(f"  Scaffold: {r['scaffold_malicious']}/{r['scaffold_total']} malicious")
            print(f"  Precision by size threshold:")
            for sz, p in r["precision"].items():
                if p["precision"] is not None:
                    print(f"    >= {sz}: {p['precision']:.1f}% ({p['malicious']}/{p['count']})")
                else:
                    print(f"    >= {sz}: N/A (0 clusters)")
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    # Summary table. Clusters, P@20 and P@10 are Table 2 columns; In clusters and Rate
    # count memberships, not the distinct files Table 2 reports (see module docstring).
    if results:
        print("\n" + "=" * 80)
        print("\nSUMMARY TABLE (In clusters and Rate count memberships)")
        print(f"{'Threshold':>10} {'Clusters':>10} {'In clusters':>12} {'Rate':>8} {'Recall':>8} {'P@20':>8} {'P@10':>8} {'P@5':>8}")
        print("-" * 80)
        for r in sorted(results, key=lambda x: x["threshold"]):
            p20 = r["precision"].get(20, {}).get("precision")
            p10 = r["precision"].get(10, {}).get("precision")
            p5 = r["precision"].get(5, {}).get("precision")
            fmt = lambda v: f"{v:.1f}%" if v is not None else "N/A"
            print(f"{r['threshold']:>9.0%} {r['num_clusters']:>10} {r['files_in_clusters']:>12} "
                  f"{r['cluster_rate']:>7.1f}% {r['ioc_recall']:>7.1f}% "
                  f"{fmt(p20):>8} {fmt(p10):>8} {fmt(p5):>8}")


if __name__ == "__main__":
    main()
