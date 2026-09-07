#!/usr/bin/env python3
"""Generate Figure 2 (cluster size distribution) for Section 4.1.

Builds the committed figure from the archived
`scan_20260314_threshold90_skillonly.json`, reading cluster sizes as len(locations)
rather than hardcoding any series. Panel (a) is a log-y histogram over the bin edges
the committed figure uses (2,3,4,5,6,8,10,15,20,30,50); panel (b) is a grouped log-y
bar chart of cluster count by type over the size ranges 2, 3-5, 6-10, 11-20, 21-50.
`generate_figures.py` makes Figures 1 and 3, not this one.

Style note: this deliberately does NOT adopt generate_figures.py's serif / Okabe-Ito
rcParams. The committed PDF was drawn with matplotlib's stock sans-serif defaults,
tab10 colours and a full axes box; matching it keeps regeneration a no-op for the
paper's appearance. Structure follows that script.

Input: `../sources/scans/scan_20260314_threshold90_skillonly.json`. No corpus access,
no network.

Output: `cluster-distribution.pdf` and `cluster-distribution.png`, written beside this
script unless --outdir says otherwise, so it runs from anywhere.

The PDF is byte-reproducible. matplotlib stamps a creation date into the PDF info
dictionary unless SOURCE_DATE_EPOCH is set, so this module sets it from the scan's own
`metadata.generated_at` before matplotlib is imported: the figure's timestamp is the
input's timestamp, and two runs produce identical bytes.

Self-test (before the scan is read): a toy cluster list with hand-counted bin and
type/range occupancy, including the 20+ tail share, plus the SOURCE_DATE_EPOCH parse.
It exercises the binning and aggregation functions, not the drawing path.

Run:
  python paper/figures/generate_cluster_distribution.py [--outdir DIR]
"""
import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCAN = HERE.parent / 'sources' / 'scans' / 'scan_20260314_threshold90_skillonly.json'
STEM = 'cluster-distribution'


def scan_generated_at(path, probe_bytes=4096):
    """metadata.generated_at, read from the head of the scan rather than by
    parsing all 45MB of it. The key sits in the file's first object."""
    with path.open('r', encoding='utf-8') as fh:
        match = re.search(r'"generated_at"\s*:\s*"([^"]+)"', fh.read(probe_bytes))
    if not match:
        raise ValueError(f'no metadata.generated_at in the first {probe_bytes}'
                         f' bytes of {path}')
    return match.group(1)


def epoch_seconds(timestamp):
    return int(datetime.datetime.fromisoformat(timestamp).timestamp())


# Set before importing matplotlib: the PDF backend reads it when it builds the
# info dictionary, and setting it early keeps the dependency obvious.
os.environ.setdefault('SOURCE_DATE_EPOCH',
                      str(epoch_seconds(scan_generated_at(SCAN))))

import matplotlib  # noqa: E402
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# Bin edges of panel (a) in the committed figure: unit-wide up to 6, then
# widening, closing at 50 so the x axis ticks land on 10..50.
BINS = [2, 3, 4, 5, 6, 8, 10, 15, 20, 30, 50]
# Panel (b) ranges, inclusive on both ends.
RANGES = [('2', 2, 2), ('3-5', 3, 5), ('6-10', 6, 10),
          ('11-20', 11, 20), ('21-50', 21, 50)]
TYPES = ['cross-marketplace', 'internal', 'scaffold']
TYPE_COLORS = {'cross-marketplace': '#1f77b4', 'internal': '#ff7f0e',
               'scaffold': '#7f7f7f'}
FIGSIZE = (6.9, 2.7)
# The committed PDF's text is 0.75x matplotlib's stock 10pt; page box 496x194pt.
FONT_SIZE = 7.5


def cluster_sizes(scan):
    """Size of every cluster, taken as the number of member locations."""
    return [len(c['locations']) for c in scan['clusters']]


def sizes_by_type(scan):
    return {t: [len(c['locations']) for c in scan['clusters'] if c['type'] == t]
            for t in TYPES}


def range_counts(sizes):
    return [sum(1 for s in sizes if lo <= s <= hi) for _, lo, hi in RANGES]


def bin_counts(sizes, bins=BINS):
    """Histogram occupancy with half-open bins, last bin closed on the right."""
    return [sum(1 for s in sizes if lo <= s <= hi
                if i == len(bins) - 2 or s < hi)
            for i, (lo, hi) in enumerate(zip(bins, bins[1:]))]


def tail_share(sizes, cutoff=20):
    n = sum(1 for s in sizes if s >= cutoff)
    return n, len(sizes), 100.0 * n / len(sizes) if sizes else 0.0


def self_test():
    toy = {'clusters': [
        {'type': 'cross-marketplace', 'locations': [0] * 2},
        {'type': 'cross-marketplace', 'locations': [0] * 4},
        {'type': 'internal', 'locations': [0] * 2},
        {'type': 'internal', 'locations': [0] * 7},
        {'type': 'scaffold', 'locations': [0] * 20},
        {'type': 'scaffold', 'locations': [0] * 50},
    ]}
    sizes = cluster_sizes(toy)
    if sizes != [2, 4, 2, 7, 20, 50]:
        sys.exit(f'self-test FAILED: sizes {sizes}')
    got = bin_counts(sizes)
    # bins 2-3, 3-4, 4-5, 5-6, 6-8, 8-10, 10-15, 15-20, 20-30, 30-50(closed)
    want = [2, 0, 1, 0, 1, 0, 0, 0, 1, 1]
    if got != want:
        sys.exit(f'self-test FAILED: bin counts {got}, want {want}')
    by_type = sizes_by_type(toy)
    want_rows = {'cross-marketplace': [1, 1, 0, 0, 0],
                 'internal': [1, 0, 1, 0, 0],
                 'scaffold': [0, 0, 0, 1, 1]}
    for t in TYPES:
        row = range_counts(by_type[t])
        if row != want_rows[t]:
            sys.exit(f'self-test FAILED: {t} ranges {row}, want {want_rows[t]}')
    n, total, pct = tail_share(sizes)
    if (n, total, round(pct, 2)) != (2, 6, 33.33):
        sys.exit(f'self-test FAILED: tail share {(n, total, pct)}')
    got_epoch = epoch_seconds('2026-03-14T18:10:26.003911+00:00')
    if got_epoch != 1773511826:
        sys.exit(f'self-test FAILED: epoch {got_epoch}, want 1773511826')
    print('self-test PASS: toy sizes [2,4,2,7,20,50] bin as '
          f'{want}, split by type as {want_rows}, 2/6 clusters at 20+ '
          f'(33.33%); SOURCE_DATE_EPOCH parse gives {got_epoch}')


def draw(scan, outdir):
    sizes = cluster_sizes(scan)
    by_type = sizes_by_type(scan)

    plt.rcParams.update({'font.size': FONT_SIZE})
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=FIGSIZE)

    ax1.hist(sizes, bins=BINS, color=TYPE_COLORS['cross-marketplace'],
             edgecolor='white', linewidth=0.5)
    ax1.set_yscale('log')
    ax1.set_xlim(BINS[0], BINS[-1])
    ax1.set_xlabel('Cluster size (files)')
    ax1.set_ylabel('Number of clusters')
    ax1.set_title('(a) Cluster size distribution', fontweight='bold')

    x, width = np.arange(len(RANGES)), 0.27
    for i, t in enumerate(TYPES):
        ax2.bar(x + (i - 1) * width, range_counts(by_type[t]), width, label=t,
                color=TYPE_COLORS[t])
    ax2.set_yscale('log')
    ax2.set_xticks(x)
    ax2.set_xticklabels([label for label, _, _ in RANGES])
    ax2.set_xlabel('Cluster size range')
    ax2.set_ylabel('Number of clusters')
    ax2.set_title('(b) Clusters by type and size', fontweight='bold')
    ax2.legend()

    fig.tight_layout()
    outdir.mkdir(parents=True, exist_ok=True)
    for ext in ('pdf', 'png'):
        fig.savefig(outdir / f'{STEM}.{ext}', bbox_inches='tight', dpi=300)
    plt.close(fig)
    print(f'Saved {STEM}.pdf/.png to {outdir}')

    n, total, pct = tail_share(sizes)
    print(f'Panel (a) bin counts {bin_counts(sizes)}')
    for t in TYPES:
        print(f'Panel (b) {t}: {range_counts(by_type[t])}')
    print(f'Clusters of 20+ files: {n} of {total} ({pct:.2f}%), caption says 0.4%')


def main():
    ap = argparse.ArgumentParser(description='Regenerate Figure 2.')
    ap.add_argument('--outdir', default=str(HERE),
                    help='directory to write the PDF and PNG into '
                         '(default: paper/figures/, beside this script)')
    args = ap.parse_args()
    self_test()
    scan = json.loads(SCAN.read_text(encoding='utf-8'))
    draw(scan, Path(args.outdir).resolve())
    return 0


if __name__ == '__main__':
    sys.exit(main())
