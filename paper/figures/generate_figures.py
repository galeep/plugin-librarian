#!/usr/bin/env python3
r"""Generate Figures 1 and 3 of the paper.

Figure 1 (Section 4.1, Ecosystem Characterization (RQ1)): "P@$\geq$20 and P@$\geq$10
versus Jaccard threshold. Recall (hightower6eu subset: 351/354) is invariant at
99.2\%; precision generally increases with threshold." The plotted series are the
P@$\geq$20 and P@$\geq$10 columns of Table 2 ("Threshold sensitivity on 31,634
\texttt{SKILL.md} files.", Section 4.1) plus the constant recall line.

Figure 3 (Section 5.2, Comparison with Simple Baselines): "Similarity method
comparison on 31,634 \texttt{SKILL.md} files. (a)~Cluster-level precision; all
methods achieve $\geq$99.7\% recall (not shown). (b)~Wall-clock runtime (8-core
i9-9880H)." The bars are the MinHash, TF-IDF and sentence-embedding precision and
runtime values stated in Section 5.2.

Figure 2, the cluster size distribution, is made by
`generate_cluster_distribution.py`. Table 2 itself is produced by
`paper/sources/scans/analyze_sweep.py` (Clusters, P@$\geq$20, P@$\geq$10) and
`paper/sources/scans/table2_distinct_files.py` (Files, %).

Inputs: none. Both figures plot literal series defined in the functions below. The
values are the published ones; the scripts that recompute them are
`paper/sources/scans/analyze_sweep.py` (Figure 1, from the archived threshold scans)
and `paper/sources/scans/tfidf_comparison.py` and
`paper/sources/scans/embedding_comparison.py` (Figure 3 baselines, from the corpus).
Because the series are literals, a recompute does not change this script. The script
reads no corpus, uses no network or environment variables, and has no randomized step.

Outputs, written to the current working directory: `threshold-sensitivity.pdf`,
`threshold-sensitivity.png`, `method-comparison.pdf`, `method-comparison.png`. The
paper includes `figures/threshold-sensitivity.pdf` and
`figures/method-comparison.pdf`, so run the script from `paper/figures/`. No PDF or
PNG ships in this artifact.

Style: Okabe-Ito colorblind-safe palette, redundant encoding (color plus marker plus
line style), serif fonts, 300 DPI, vector PDF as the primary output.

Run:
  cd paper/figures && python generate_figures.py
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Okabe-Ito colorblind-safe palette
OI_BLUE = '#0072B2'
OI_ORANGE = '#E69F00'
OI_GREEN = '#009E73'
OI_VERMILLION = '#D55E00'
OI_PURPLE = '#CC79A7'
OI_SKY = '#56B4E9'
OI_BLACK = '#000000'

# Figure style shared by both figures
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times', 'Times New Roman', 'DejaVu Serif'],
    'font.size': 8,
    'axes.labelsize': 9,
    'axes.titlesize': 9,
    'xtick.labelsize': 7,
    'ytick.labelsize': 7,
    'legend.fontsize': 7,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.02,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.linewidth': 0.6,
    'xtick.major.width': 0.6,
    'ytick.major.width': 0.6,
    'lines.linewidth': 1.2,
    'lines.markersize': 4,
})

TEXT_WIDTH = 4.817   # figure width in inches (122.36 mm); scaled to column width on inclusion


def fig_threshold_sensitivity():
    """Figure 1: precision at each Jaccard threshold, recall constant.

    Plots P@>=20 and P@>=10 against threshold with recall flat at 99.2%; P@>=5 is
    omitted, as the caption states. Redundant encoding: each series has a distinct
    color, marker and line style. The dotted vertical line marks the 90% threshold
    the paper selects.
    """
    thresholds = [70, 75, 80, 85, 90, 95]
    p_at_20 = [69.2, 89.5, 88.2, 88.2, 100.0, 100.0]
    p_at_10 = [33.7, 48.3, 69.0, 68.3, 78.9, 81.2]
    recall = [99.2] * 6

    fig, ax = plt.subplots(figsize=(TEXT_WIDTH, 2.8))

    # Redundant encoding: color + marker + linestyle
    ax.plot(thresholds, p_at_20, color=OI_BLUE, marker='o', linestyle='-',
            label=r'P@$\geq$20', zorder=3)
    ax.plot(thresholds, p_at_10, color=OI_VERMILLION, marker='s', linestyle='--',
            label=r'P@$\geq$10', zorder=3)
    ax.plot(thresholds, recall, color=OI_GREEN, marker='D', linestyle='-',
            label='Recall', alpha=0.6, zorder=2)

    # Mark the selected 90% threshold
    ax.axvline(x=90, color='#888888', linestyle=':', linewidth=0.6, alpha=0.6)
    ax.annotate('selected\nthreshold', xy=(90, 45), fontsize=6, color='#666666',
                ha='center', va='center', style='italic')

    ax.set_xlabel('Jaccard similarity threshold (%)')
    ax.set_ylabel('Percentage')
    ax.set_xlim(68, 97)
    ax.set_ylim(0, 108)
    ax.set_xticks(thresholds)
    ax.legend(loc='lower right', frameon=True, framealpha=0.95,
              edgecolor='#cccccc', fancybox=False)
    ax.grid(True, alpha=0.15, linewidth=0.4)

    fig.savefig('threshold-sensitivity.pdf')
    fig.savefig('threshold-sensitivity.png')
    plt.close(fig)
    print('Saved threshold-sensitivity.pdf/.png')


def fig_method_comparison():
    """Figure 3: method comparison, precision and runtime.

    Two-panel figure at TEXT_WIDTH. (a) Grouped bars for P@>=20 and P@>=10; recall
    is omitted because all three methods reach near-identical values, as Section 5.2
    states. (b) Wall-clock runtime bars in seconds.
    """
    methods = ['MinHash\n(this work)', 'TF-IDF', 'Sentence\nembeddings']
    p_at_20 = [100.0, 75.0, 92.9]
    p_at_10 = [78.9, 41.1, 62.8]
    runtime = [305, 465, 924]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(TEXT_WIDTH, 2.8),
                                    gridspec_kw={'width_ratios': [1.5, 1]})

    x = np.arange(len(methods))
    width = 0.32

    # Panel (a): precision only; recall is reported in the caption
    bars1 = ax1.bar(x - width/2, p_at_20, width, label=r'P@$\geq$20',
                     color=OI_BLUE, edgecolor='white', linewidth=0.3)
    bars2 = ax1.bar(x + width/2, p_at_10, width, label=r'P@$\geq$10',
                     color=OI_ORANGE, edgecolor='white', linewidth=0.3)

    # Value labels above bars
    for bars in [bars1, bars2]:
        for bar in bars:
            h = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2, h + 1.5,
                     f'{h:.0f}%', ha='center', va='bottom', fontsize=6)

    ax1.set_ylabel('Precision (%)')
    ax1.set_ylim(0, 118)
    ax1.set_xticks(x)
    ax1.set_xticklabels(methods, fontsize=7)
    ax1.legend(loc='upper right', frameon=True, framealpha=0.95,
               edgecolor='#cccccc', fancybox=False)
    ax1.grid(True, axis='y', alpha=0.15, linewidth=0.4)
    ax1.set_title('(a) Precision', fontsize=8, pad=6)

    # Panel (b): runtime
    colors_rt = [OI_BLUE, OI_ORANGE, OI_VERMILLION]
    bars_rt = ax2.bar(x, runtime, 0.55, color=colors_rt,
                       edgecolor='white', linewidth=0.3)
    for bar in bars_rt:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2, h + 18,
                 f'{h:,}s', ha='center', va='bottom', fontsize=6)

    ax2.set_ylabel('Wall time (seconds)')
    ax2.set_ylim(0, 1100)
    ax2.set_xticks(x)
    ax2.set_xticklabels(methods, fontsize=7)
    ax2.grid(True, axis='y', alpha=0.15, linewidth=0.4)
    ax2.set_title('(b) Runtime', fontsize=8, pad=6)

    fig.tight_layout(w_pad=3)
    fig.savefig('method-comparison.pdf')
    fig.savefig('method-comparison.png')
    plt.close(fig)
    print('Saved method-comparison.pdf/.png')


if __name__ == '__main__':
    fig_threshold_sensitivity()
    fig_method_comparison()
