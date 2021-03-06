import collections
import multiprocessing as mp
import os
import pickle

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt, colors
from scipy import stats

from integrator import rnaseq_methylationarray
from methylation import dmr, annotation_gene_to_ensembl
from plotting import bar, common, venn
from rnaseq import loader as rnaseq_loader
from scripts.dmr_direction_bias_story import same_process_applied_to_de as same_de
from scripts.hgic_final import analyse_dmrs_s1_direction_distribution as addd
from scripts.hgic_final import two_strategies_grouped_dispersion as tsgd, two_strategies_combine_de_dmr as tscd, consts
from scripts.methylation import dmr_values_to_bigwig
from settings import HGIC_LOCAL_DIR, LOCAL_DATA_DIR, INTERMEDIATE_DIR
from stats import basic
from utils import output, setops, genomics, log, dictionary, reference_genomes

logger = log.get_console_logger()


def de_dmr_concordance_scatter(de, dm, groups, de_edge=None, dm_edge=None,
                               group_colours=consts.METHYLATION_DIRECTION_COLOURS):
    """

    :param de:
    :param dm:
    :param groups:
    :param de_edge, dm_edge: If supplied, both must be specified. These provide a subset of the data in de and dm
    that will be highlighted on the plots with a black outline. Typically used to highlight DMR / TSS overlap.
    :param group_colours:
    :return:
    """
    a = de_edge is None
    b = dm_edge is None
    if a != b:
        raise AttributeError("Must specify either both of de_edge and dm_edge or neither.")

    ncol = max([len(t) for t in groups.values()])
    nrow = len(groups)

    fig, axs = plt.subplots(nrows=nrow, ncols=ncol, sharex=True, sharey=True, figsize=(1.14 * ncol, 1.8 * nrow))
    big_ax = common.add_big_ax_to_subplot_fig(fig)

    xmin = xmax = ymin = ymax = 0

    subplots_filled = set()
    for i, grp in enumerate(groups):
        for j, pid in enumerate(groups[grp]):
            subplots_filled.add((i, j))
            ax = axs[i, j]
            x = de[pid]
            y = dm[pid]
            xmin = min(xmin, x.min())
            xmax = max(xmax, x.max())
            ymin = min(ymin, y.min())
            ymax = max(ymax, y.max())

            ax.scatter(
                x,
                y,
                c=group_colours[grp.lower()],
                alpha=0.6
            )
            if not a:
                xm = de_edge[pid]
                ym = dm_edge[pid]
                ax.scatter(
                    xm,
                    ym,
                    c='none',
                    edgecolor='k',
                    linewidth=0.5,
                    alpha=0.6
                )
            ax.axhline(0., c='k', linestyle='--')
            ax.axvline(0., c='k', linestyle='--')
            ax.set_title(pid)
    big_ax.set_xlabel(r'DE logFC')
    big_ax.set_ylabel(r'DMR median $\Delta M$')
    fig.subplots_adjust(left=0.08, right=0.99, bottom=0.15, top=0.93, hspace=0.2, wspace=0.05)

    for i in range(2):
        for j in range(6):
            if (i, j) not in subplots_filled:
                axs[i, j].set_visible(False)
    axs[0, 0].set_xlim([np.floor(xmin * 1.05), np.ceil(xmax * 1.05)])
    axs[0, 0].set_ylim([np.floor(ymin), np.ceil(ymax)])

    return fig, axs


def scatterplot_pvalues_concordance(
        pvals,
        concords,
        pct_to_size_func=None,
        cmap=plt.get_cmap('Reds'),
        vmin=None,
        vmax=None,
        ax=None,
):
    """
    Plot summarising pvalue and concordance level simultaneously using marker size (concordance) and colour (pval).
    :param pvals: DataFrame. Index and columns will be used for ticklabels. Suggest using -log10
    :param concords: DataFrame, must match pvals
    :param pct_to_size_func:
    :param cmap: cmap used to represent
    :param vmin: For pvalue shading. If not supplied, min of data will be used
    :param vmax: For pvalue shading. If not supplied, max of data will be used
    :return:
    """
    if sorted(pvals.index) != sorted(concords.index):
        raise AttributeError("Index of pvals and concords must match")
    if sorted(pvals.columns) != sorted(concords.columns):
        raise AttributeError("Columns of pvals and concords must match")

    concords = concords.loc[pvals.index, pvals.columns]

    if pct_to_size_func is None:
        pct_to_size_func = lambda t: t ** 2 / 20.

    if vmin is None:
        vmin = pvals.values.min()
    if vmax is None:
        vmax = pvals.values.max()

    ny, nx = pvals.shape

    if ax is None:
        figsize = (nx, ny * 0.5)
        fig, ax = plt.subplots(figsize=figsize)
        ax_supplied = False
    else:
        ax_supplied = True
        fig = ax.figure

    plogp_norm = colors.Normalize(vmin=vmin, vmax=vmax)
    plogp_sm = plt.cm.ScalarMappable(cmap=cmap, norm=plogp_norm)

    x = np.tile(np.arange(nx), (ny, 1)).flatten()
    y = np.tile(np.arange(ny)[:, None], (1, nx)).flatten()

    c = [plogp_sm.to_rgba(t) for t in pvals.values.flatten()]
    s = [pct_to_size_func(t) for t in concords.values.flatten()]

    ax.scatter(x, y, c=c, s=s, edgecolor='k')
    ax.grid('off')
    ax.set_facecolor('w')
    ax.set_ylim([-.5, ny - .5])
    ax.set_xlim([-.5, nx - .5])
    ax.set_xticks(range(nx))
    ax.set_yticks(range(ny))

    ax.set_xticklabels(pvals.columns, fontsize=12, rotation=90)
    ax.set_yticklabels(pvals.index, fontsize=12)

    plogp_sm.set_array(pvals)
    cbar = fig.colorbar(plogp_sm)
    if not ax_supplied:
        ax.xaxis.tick_top()
        fig.tight_layout()

    return {
        'fig': fig,
        'ax': ax,
        'cbar': cbar
    }


def line_plot_pvalues_concordance(
        pvals,
        concords,
        cmap=plt.get_cmap('Reds'),
        vmin=None,
        vmax=None,
):
    """
    Plot summarising pvalue and concordance level simultaneously using position (concordance) and colour (pval).
    Hard coded into vertical orientation (TODO: make this a parameter??)
    :param pvals: DataFrame. Index and columns will be used for ticklabels. Suggest using -log10
    :param concords: DataFrame, must match pvals
    :param pct_to_size_func:
    :param cmap: cmap used to represent
    :param vmin: For pvalue shading. If not supplied, min of data will be used
    :param vmax: For pvalue shading. If not supplied, max of data will be used
    :return:
    """
    if sorted(pvals.index) != sorted(concords.index):
        raise AttributeError("Index of pvals and concords must match")
    if sorted(pvals.columns) != sorted(concords.columns):
        raise AttributeError("Columns of pvals and concords must match")

    concords = concords.loc[pvals.index, pvals.columns]

    if vmin is None:
        vmin = pvals.values.min()
    if vmax is None:
        vmax = pvals.values.max()

    ny, nx = pvals.shape
    markers = common.get_best_marker_map(nx)

    gs = plt.GridSpec(nrows=nx, ncols=1, height_ratios=[1, 19])
    fig = plt.figure(figsize=(1.5 * nx, .5 * ny))
    ax = fig.add_subplot(gs[1])
    ax.invert_yaxis()

    cax = fig.add_subplot(gs[0])

    plogp_norm = colors.Normalize(vmin=vmin, vmax=vmax)
    plogp_sm = plt.cm.ScalarMappable(cmap=cmap, norm=plogp_norm)

    for i, col in enumerate(concords.columns):
        ax.scatter(
            concords[col],
            range(ny),
            c=[plogp_sm.to_rgba(t) for t in pvals[col].values],
            s=60,
            edgecolor='k',
            marker=markers[i]
        )

    ax.set_xlabel('% concordance', fontsize=12)
    ax.set_yticks(range(ny))
    ax.set_yticklabels(pvals.index, fontsize=12)
    ax.set_xlim([50, 100])
    plogp_sm.set_array(pvals)
    fig.colorbar(plogp_sm, cax=cax, orientation='horizontal')
    cax.xaxis.set_label_position('top')
    cax.set_xlabel(r'$-\log_{10}(p)$')

    type_attrs = {
        'class': 'line',
        'linestyle': 'none',
        'markeredgecolor': 'k',
        'markeredgewidth': 1.,
        'markerfacecolor': 'none',
        'markersize': 8
    }

    leg_dict = {}
    for i, col in enumerate(pvals.columns):
        leg_dict[col] = dict(type_attrs)
        leg_dict[col].update({'marker': markers[i]})

    common.add_custom_legend(ax, leg_dict, loc_outside=True, loc_outside_horiz='right')
    gs.update(left=0.2, bottom=0.1, right=0.72, top=0.95, hspace=0.12)

    return {
        'fig': fig,
        'ax': ax,
        'gs': gs,
        'cax': cax
    }


if __name__ == '__main__':
    """
    Use the DMR bias results to lookup into DE results (and vice versa?)
    """
    outdir = output.unique_output_dir()
    de_res_fn = os.path.join(HGIC_LOCAL_DIR, 'current/core_pipeline/rnaseq', 'full_de_syngeneic_only.xlsx')
    pids = consts.PIDS

    DE_LOAD_DIR = os.path.join(INTERMEDIATE_DIR, 'de')
    de_params = consts.DE_PARAMS

    norm_method_s1 = 'swan'
    dmr_params = consts.DMR_PARAMS
    dmr_params['n_jobs'] = mp.cpu_count()
    DMR_LOAD_DIR = os.path.join(INTERMEDIATE_DIR, 'dmr')

    # should we add 'chr' prefix to bigwig output?
    chr_prefix = True

    relations_tss = ['TSS1500', 'TSS200']

    groups = {
        'Hypo': ['019', '030', '031', '017'],
        'Hyper': ['018', '050', '054', '061', '026', '052']
    }
    group_ind = setops.groups_to_ind(pids, groups)

    subgroups = consts.SUBGROUPS
    subgroups_ind = setops.groups_to_ind(pids, subgroups)

    # load gene expression values
    rna_obj = rnaseq_loader.load_by_patient(pids, include_control=False)
    rna_obj.filter_samples(rna_obj.meta.index.isin(consts.S1_RNASEQ_SAMPLES))
    tmp = rna_obj.data
    rna_cpm = tmp.divide((tmp + 1).sum(axis=0), axis=1) * 1e6

    # load DE results
    the_hash = tscd.de_results_hash(rna_obj.meta.index.tolist(), de_params)
    filename = 'de_results_paired_comparison.%d.pkl' % the_hash
    fn = os.path.join(DE_LOAD_DIR, filename)

    if os.path.isfile(fn):
        logger.info("Reading S1 DE results from %s", fn)
        with open(fn, 'rb') as f:
            de_res_full_s1 = pickle.load(f)
    else:
        raise AttributeError("Unable to load pre-computed DE results, expected at %s" % fn)

    de_res_s1 = dict([(k, v.loc[v.FDR < de_params['fdr']]) for k, v in de_res_full_s1.items()])

    # load methylation data
    me_obj, anno = tsgd.load_methylation(pids, norm_method=norm_method_s1, patient_samples=consts.S1_METHYL_SAMPLES)
    me_data = me_obj.data
    me_meta = me_obj.meta
    me_meta.insert(0, 'patient_id', me_meta.index.str.replace(r'(GBM|DURA)(?P<pid>[0-9]{3}).*', '\g<pid>'))

    # load chromosome lengths
    chroms = [str(t) for t in range(1, 23)]
    fa_fn = os.path.join(
        LOCAL_DATA_DIR,
        'reference_genomes',
        'human/ensembl/GRCh38.release87/fa/Homo_sapiens.GRCh38.dna.primary_assembly.fa'
    )
    cl = genomics.feature_lengths_from_fasta(fa_fn, features=chroms)

    chrom_length = collections.OrderedDict()
    for k in chroms:
        if chr_prefix:
            new_k = "chr%s" % k
        else:
            new_k = k
        chrom_length[new_k] = cl[k]

    # We load pre-computed results if a file with the correct filename is found
    # Otherwise this is written after computing the results

    # use a hash on the PIDs and parameters to ensure we're looking for the right results
    dmr_hash_dict = dict(dmr_params)
    dmr_hash_dict['norm_method'] = norm_method_s1

    # load DMR results
    the_hash = tsgd.dmr_results_hash(me_obj.meta.index.tolist(), dmr_hash_dict)
    filename = 'dmr_results_paired_comparison.%d.pkl' % the_hash
    fn = os.path.join(DMR_LOAD_DIR, filename)

    if os.path.isfile(fn):
        logger.info("Loading pre-computed DMR results from %s", fn)
        dmr_res_s1 = dmr.DmrResultCollection.from_pickle(fn, anno=anno)
    else:
        logger.info("Unable to locate pre-existing results. Computing from scratch (this can take a while).")
        dmr_res_s1 = tsgd.paired_dmr(me_data, me_meta, anno, pids, dmr_params)
        # Save DMR results to disk
        dmr_res_s1.to_pickle(fn, include_annotation=False)
        logger.info("Saved DMR results to %s", fn)

    # extract full (all significant) results
    dmr_res_all = dmr_res_s1.results_significant

    # look at the direction distribution of genes that correspond to a DMR (full and specific lists)
    joint_de_dmr_s1 = rnaseq_methylationarray.compute_joint_de_dmr(dmr_res_s1, de_res_s1)

    # run through DE genes (per patient) and look at direction distribution
    # full list
    de_linked = dict([
        (
            pid,
            de_res_s1[pid].loc[de_res_s1[pid]['Gene Symbol'].isin(joint_de_dmr_s1[pid].gene)]
        ) for pid in pids
    ])

    de_by_direction = same_de.count_de_by_direction(de_linked)

    plt_dict = same_de.bar_plot(de_linked, pids, figsize=(3, 4))
    plt_dict['fig'].tight_layout()
    plt.setp(common.get_children_recursive(plt_dict['fig'], plt.Text), fontsize=12)
    plt_dict['fig'].savefig(os.path.join(outdir, "de_linked_syngeneic_full_list_directions.png"), dpi=200)

    # full list linked through TSS
    de_linked = dict([
        (
            pid,
            de_res_s1[pid].loc[de_res_s1[pid]['Gene Symbol'].isin(joint_de_dmr_s1[pid].loc[joint_de_dmr_s1[pid][['dmr_%s' % t for t in relations_tss]].any(axis=1)].gene)]
        ) for pid in pids
    ])

    de_by_direction = same_de.count_de_by_direction(de_linked)

    plt_dict = same_de.bar_plot(de_linked, pids, figsize=(3, 4))
    plt_dict['fig'].tight_layout()
    plt.setp(common.get_children_recursive(plt_dict['fig'], plt.Text), fontsize=12)
    plt_dict['fig'].savefig(os.path.join(outdir, "de_linked_syngeneic_full_list_tss_directions.png"), dpi=200)

    # patient-specific DMRs linked to DE genes

    spec_ix = setops.specific_features(*[dmr_res_all[pid].keys() for pid in pids])
    dm_specific = dict([
        (
            pid,
            dict([
                (
                    k,
                    dmr_res_all[pid][k]
                ) for k in s
            ])
        ) for pid, s in zip(pids, spec_ix)
    ])

    # manually link these
    dm_specific_genes = {}
    for pid in pids:
        cl_ids = dm_specific[pid].keys()
        dm_specific_genes[pid] = setops.reduce_union(*[[t[0] for t in dmr_res_s1.clusters[c].genes] for c in cl_ids])

    de_linked_spec = dict([
        (
            pid,
            de_res_s1[pid].loc[de_res_s1[pid]['Gene Symbol'].isin(dm_specific_genes[pid])]
        ) for pid in pids
    ])

    de_by_direction_spec = same_de.count_de_by_direction(de_linked_spec)

    plt_dict = same_de.bar_plot(de_linked_spec, pids, figsize=(3, 4))
    plt.setp(common.get_children_recursive(plt_dict['fig'], plt.Text), fontsize=12)
    plt_dict['fig'].tight_layout()
    plt_dict['fig'].savefig(os.path.join(outdir, "de_specific_linked_syngeneic_full_list_directions.png"), dpi=200)


    # assess concordance: full list, DE and DMR
    ct_all = {}
    fisher_all = pd.DataFrame(index=pids, columns=['odds', 'p'])
    corr_all = {}
    for_plot_all = {}

    ct_tss = {}
    fisher_tss = pd.DataFrame(index=pids, columns=['odds', 'p'])
    corr_tss = {}
    for_plot_tss = {}

    for pid in pids:
        this_joint = joint_de_dmr_s1[pid]
        x = this_joint.de_logFC
        y = this_joint.dmr_median_delta

        for_plot_all[pid] = (x, y)

        # fishers test
        ct_all[pid] = basic.construct_contingency(x.values, y.values)
        fisher_all.loc[pid] = stats.fisher_exact(ct_all[pid])
        corr_all[pid] = stats.spearmanr(x.values, y.values)

        ix = (this_joint[['dmr_%s' % t for t in relations_tss]]).any(axis=1)
        for_plot_tss[pid] = (x.loc[ix], y.loc[ix])

        # fishers test
        ct_tss[pid] = basic.construct_contingency(x.loc[ix].values, y.loc[ix].values)
        fisher_tss.loc[pid] = stats.fisher_exact(ct_tss[pid])
        corr_tss[pid] = stats.spearmanr(x.loc[ix].values, y.loc[ix].values)

    fig, axs = de_dmr_concordance_scatter(
        dict([(pid, for_plot_all[pid][0]) for pid in pids]),
        dict([(pid, for_plot_all[pid][1]) for pid in pids]),
        groups,
        de_edge=dict([(pid, for_plot_tss[pid][0]) for pid in pids]),
        dm_edge=dict([(pid, for_plot_tss[pid][1]) for pid in pids]),
    )

    fig.savefig(os.path.join(outdir, "de_dmr_scatter.png"), dpi=200)

    pvals = pd.DataFrame(index=pids, columns=['All', 'TSS'])
    pvals.loc[:, 'All'] = -np.log10(fisher_all['p'].astype(float))
    pvals.loc[:, 'TSS'] = -np.log10(fisher_tss['p'].astype(float))

    concords = pd.DataFrame(index=pids, columns=['All', 'TSS'])
    concords.loc[:, 'All'] = pd.Series(dict([
        (pid, (ct_all[pid][1, 0] + ct_all[pid][0, 1]) / float(ct_all[pid].sum()) * 100.) for pid in pids
    ]))
    concords.loc[:, 'TSS'] = pd.Series(dict([
        (pid, (ct_tss[pid][1, 0] + ct_tss[pid][0, 1]) / float(ct_tss[pid].sum()) * 100.) for pid in pids
    ]))

    plt_dict = scatterplot_pvalues_concordance(pvals, concords, vmin=0., vmax=40.)
    plt_dict['cbar'].set_label(r'$-\log_{10}(p)$')
    plt_dict['fig'].tight_layout()
    plt_dict['fig'].savefig(os.path.join(outdir, "fisher_p_concordance_scatter_full_dmr_de_genes.png"), dpi=200)

    plt_dict = line_plot_pvalues_concordance(pvals, concords, vmin=0., vmax=40.)
    plt_dict['fig'].savefig(os.path.join(outdir, "fisher_p_concordance_line_full_dmr_de_genes.png"), dpi=200)



    # same again for patient-specific DE and DMR

    venn_set_dedmr, venn_ct_dedmr = setops.venn_from_arrays(*[joint_de_dmr_s1[pid].index for pid in pids])
    specific_sets = setops.specific_sets(pids)

    ct_all_specific = {}
    ct_tss_specific = {}
    fisher_all_specific = pd.DataFrame(index=pids, columns=['odds', 'p'])
    fisher_tss_specific = pd.DataFrame(index=pids, columns=['odds', 'p'])

    for_plot_specific_all = {}
    for_plot_specific_tss = {}

    for pid in pids:
        this_joint = joint_de_dmr_s1[pid].loc[venn_set_dedmr[specific_sets[pid]]]
        x = this_joint.de_logFC
        y = this_joint.dmr_median_delta
        for_plot_specific_all[pid] = (x, y)

        ct_all_specific[pid] = basic.construct_contingency(x.values, y.values)
        fisher_all_specific.loc[pid] = stats.fisher_exact(ct_all_specific[pid])

        ix = (this_joint[['dmr_%s' % t for t in relations_tss]]).any(axis=1)
        for_plot_specific_tss[pid] = (x.loc[ix], y.loc[ix])

        ct_tss_specific[pid] = basic.construct_contingency(x.loc[ix].values, y.loc[ix].values)
        fisher_tss_specific.loc[pid] = stats.fisher_exact(ct_tss_specific[pid])

    fig, axs = de_dmr_concordance_scatter(
        dict([(pid, for_plot_specific_all[pid][0]) for pid in pids]),
        dict([(pid, for_plot_specific_all[pid][1]) for pid in pids]),
        groups,
        de_edge=dict([(pid, for_plot_specific_tss[pid][0]) for pid in pids]),
        dm_edge=dict([(pid, for_plot_specific_tss[pid][1]) for pid in pids]),
    )

    fig.savefig(os.path.join(outdir, "de_dmr_specific_scatter.png"), dpi=200)

    pvals = pd.DataFrame(index=pids, columns=['All', 'TSS'])
    pvals.loc[:, 'All'] = -np.log10(fisher_all_specific['p'].astype(float))
    pvals.loc[:, 'TSS'] = -np.log10(fisher_tss_specific['p'].astype(float))

    concords = pd.DataFrame(index=pids, columns=['All', 'TSS'])
    concords.loc[:, 'All'] = pd.Series(dict([
        (pid, (ct_all_specific[pid][1, 0] + ct_all_specific[pid][0, 1]) / float(ct_all_specific[pid].sum()) * 100.) for pid in pids
    ]))
    concords.loc[:, 'TSS'] = pd.Series(dict([
        (pid, (ct_tss_specific[pid][1, 0] + ct_tss_specific[pid][0, 1]) / float(ct_tss_specific[pid].sum()) * 100.) for pid in pids
    ]))

    plt_dict = scatterplot_pvalues_concordance(pvals, concords, vmin=0., vmax=5.)
    plt_dict['cbar'].set_label(r'$-\log_{10}(p)$')
    plt_dict['fig'].tight_layout()
    plt_dict['fig'].savefig(os.path.join(outdir, "fisher_p_concordance_scatter_specific_dmr_de_genes.png"), dpi=200)

    plt_dict = line_plot_pvalues_concordance(pvals, concords, vmin=0., vmax=5.)
    plt_dict['fig'].savefig(os.path.join(outdir, "fisher_p_concordance_line_specific_dmr_de_genes.png"), dpi=200)


    # upset plotting colours
    subgroup_set_colours = {
        'Hypo full': '#427425',
        'Hyper full': '#b31500',
        'Hypo partial': '#c5e7b1',
        'Hyper partial': '#ffa599',
        'Expanded core': '#4C72B0',
        'Specific': '#f4e842',
    }

    # start with an UpSet to represent this
    dmr_by_member = [dmr_res_all[pid].keys() for pid in pids]
    venn_set, venn_ct = setops.venn_from_arrays(*dmr_by_member)

    # add null set manually from full DMR results
    dmr_id_all = setops.reduce_union(*venn_set.values())
    k_null = ''.join(['0'] * len(pids))
    venn_set[k_null] = list(set(dmr_res_s1.clusters.keys()).difference(dmr_id_all))
    venn_ct[k_null] = len(venn_set[k_null])

    upset = venn.upset_plot_with_groups(
        dmr_by_member,
        pids,
        group_ind,
        subgroup_set_colours,
        min_size=10,
        n_plot=30,
        default_colour='gray'
    )
    upset['axes']['main'].set_ylabel('Number of DMRs in set')
    upset['axes']['set_size'].set_xlabel('Number of DMRs in single comparison')
    upset['figure'].savefig(os.path.join(outdir, "upset_dmr_by_direction_group.png"), dpi=200)

    # export DMR data to bigwig
    venn_sets_by_group = setops.full_partial_unique_other_sets_from_groups(pids, groups)
    dmr_groups = {}
    genes_from_dmr_groups = {}
    for grp in groups:
        # generate bar chart showing number / pct in each direction (DM)
        this_sets = venn_sets_by_group['full'][grp] + venn_sets_by_group['partial'][grp]
        this_dmrs = sorted(setops.reduce_union(*[venn_set[k] for k in this_sets]))
        dmr_groups[grp] = this_dmrs

        this_results = {}
        for pid in groups[grp]:
            this_results[pid] = dict([(t, dmr_res_all[pid][t]) for t in this_dmrs if t in dmr_res_all[pid]])
            # where are these DMRs? write bigwig
            fn = os.path.join(outdir, "%s_%s_dmrs.bw" % (grp, pid))
            dmr_values_to_bigwig.write_bigwig(
                this_results[pid],
                dmr_res_s1.clusters,
                chrom_length,
                fn,
                chr_prefix=chr_prefix
            )

        # combine with DE to assess bias (if any)
        this_genes = sorted(
            set(
                [u[0] for u in setops.reduce_union(*[dmr_res_s1.clusters[t].genes for t in this_dmrs])]
            )
        )
        genes_from_dmr_groups[grp] = this_genes

        this_results = {}
        for pid in pids:
            this_results[pid] = de_res_s1[pid].loc[de_res_s1[pid]['Gene Symbol'].isin(this_genes)]
        plt_dict = same_de.bar_plot(this_results, keys=pids)
        plt_dict['fig'].savefig(os.path.join(outdir, "de_direction_by_dm_group_%s.png" % grp), dpi=200)

        # same again, but density
        fig, axs = plt.subplots(nrows=1, ncols=len(groups[grp]), sharex=True, figsize=(11 / 6. * len(groups[grp]), 2.5))
        for i, pid in enumerate(groups[grp]):
            xi, y = addd.direction_kde(this_results[pid].logFC)
            axs[i].fill_between(xi[xi < 0], y[xi < 0], facecolor=consts.METHYLATION_DIRECTION_COLOURS['hypo'], edgecolor='k', alpha=0.6)
            axs[i].fill_between(xi[xi > 0], y[xi > 0], facecolor=consts.METHYLATION_DIRECTION_COLOURS['hyper'], edgecolor='k', alpha=0.6)
            axs[i].axvline(0., color='k', linestyle=':')
            # axs[i].yaxis.set_visible(False)
            axs[i].set_yticks([])
            axs[i].set_title(pid)
        axs[0].set_ylabel('Density')
        fig.tight_layout()
        fig.savefig(os.path.join(outdir, "de_genes_from_dmr_groups_logfc_kde.png"), dpi=200)

    # grouped bar chart showing dmr direction (in one figure)
    colours = pd.Series(
        {
            'Hyper': consts.METHYLATION_DIRECTION_COLOURS['hyper'],
            'Hypo': consts.METHYLATION_DIRECTION_COLOURS['hypo']
        }
    )
    group_order = pd.Series([len(t) for t  in groups.values()], index=groups.keys()).sort_values(ascending=False).index

    fig = plt.figure(figsize=(5, 5))
    gs = plt.GridSpec(nrows=2, ncols=2, width_ratios=[len(groups[grp]) for grp in group_order])
    sharey = None

    for i, grp in enumerate(group_order):
        this_sets = venn_sets_by_group['full'][grp] + venn_sets_by_group['partial'][grp]
        this_dmrs = sorted(setops.reduce_union(*[venn_set[k] for k in this_sets]))
        this_results = {}
        for pid in groups[grp]:
            this_results[pid] = dict([(t, dmr_res_all[pid][t]) for t in this_dmrs if t in dmr_res_all[pid]])

        for_plot = addd.count_dm_by_direction(this_results, pids=groups[grp])
        for_plot_pct = for_plot.divide(for_plot.sum(), axis=1) * 100.

        ax = fig.add_subplot(gs[1, i], sharey=sharey)
        if sharey is None:
            sharey = ax
        if i == 0:
            ax.set_ylabel('Number DMRs')
        else:
            ax.yaxis.set_visible(False)

        bar.stacked_bar_chart(for_plot, colours=colours, width=0.8, legend=False, ax=ax)
        ax = fig.add_subplot(gs[0, i])
        bar.stacked_bar_chart(for_plot_pct, colours=colours, width=0.8, legend=False, ax=ax)
        if i == 0:
            ax.set_ylabel('% DMRs')
        else:
            ax.yaxis.set_visible(False)

    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "dmr_direction_all_groups.png"), dpi=200)
    fig.savefig(os.path.join(outdir, "dmr_direction_all_groups.tiff"), dpi=200)

    # is there much overlap in the gene sets between the two groups?
    fig = plt.figure(figsize=(5, 3))
    ax = fig.add_subplot(111)
    venn.venn_diagram(genes_from_dmr_groups['Hyper'], genes_from_dmr_groups['Hypo'], set_labels=['Hyper', 'Hypo'], ax=ax)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "genes_from_dmr_groups_venn.png"), dpi=200)

    # no, but if we look at the intersection genes, are they in different directions (DE) between the two groups?
    groups_inv = dictionary.complement_dictionary_of_iterables(groups, squeeze=True)
    in_both = setops.reduce_intersection(*genes_from_dmr_groups.values())
    in_both_ens = reference_genomes.gene_symbol_to_ensembl(in_both)

    # some of these will have no DE results
    tmp = {}
    for pid in pids:
        tmp[pid] = de_res_s1[pid].reindex(in_both_ens).logFC.dropna()
    in_both_ens = in_both_ens[in_both_ens.isin(pd.DataFrame(tmp).index)]

    fig = plt.figure(figsize=(10.5, 4.))
    ax = fig.add_subplot(111)
    for pid in pids:
        this_grp = groups_inv[pid].lower()
        this_de = de_res_s1[pid].reindex(in_both_ens).logFC
        x = np.arange(len(in_both_ens)) + 0.1 * (-1 if this_grp == 'hypo' else 1)
        ax.scatter(x, this_de, c=consts.METHYLATION_DIRECTION_COLOURS[this_grp])
    ax.set_xticks(np.arange(len(in_both_ens)))
    ax.set_xticklabels(in_both_ens.index, rotation=90)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "de_logfc_genes_from_dmr_group_intersection.png"), dpi=200)

    # this is for DMR groups

    # generate scatter plots of joint DE and DMR for the two DMR groups
    # run fisher's test at the same time
    ct_gs_all = {}
    ct_gs_tss = {}
    fisher_gs_all = pd.DataFrame(index=pids, columns=['odds', 'p'])
    fisher_gs_tss = pd.DataFrame(index=pids, columns=['odds', 'p'])

    for_plot_gs_all = {}
    for_plot_gs_tss = {}

    for pid in pids:
        this_grp = groups_inv[pid]
        this_joint = joint_de_dmr_s1[pid].loc[joint_de_dmr_s1[pid].cluster_id.isin(dmr_groups[this_grp])]
        x = this_joint.de_logFC
        y = this_joint.dmr_median_delta
        for_plot_gs_all[pid] = (x, y)

        # fishers test
        ct_gs_all[pid] = basic.construct_contingency(x.values, y.values)
        fisher_gs_all.loc[pid] = stats.fisher_exact(ct_gs_all[pid])

        ix = (this_joint[['dmr_%s' % t for t in relations_tss]]).any(axis=1)
        for_plot_gs_tss[pid] = (x.loc[ix], y.loc[ix])

        # fishers test
        ct_gs_tss[pid] = basic.construct_contingency(x.loc[ix].values, y.loc[ix].values)
        fisher_gs_tss.loc[pid] = stats.fisher_exact(ct_gs_tss[pid])

    fig, axs = de_dmr_concordance_scatter(
        dict([(pid, for_plot_gs_all[pid][0]) for pid in pids]),
        dict([(pid, for_plot_gs_all[pid][1]) for pid in pids]),
        groups,
        de_edge=dict([(pid, for_plot_gs_tss[pid][0]) for pid in pids]),
        dm_edge=dict([(pid, for_plot_gs_tss[pid][1]) for pid in pids]),
    )
    fig.savefig(os.path.join(outdir, "de_dmr_scatter_from_dmr_groups.png"), dpi=200)

    pvals = pd.DataFrame(index=pids, columns=['All', 'TSS'])
    pvals.loc[:, 'All'] = -np.log10(fisher_gs_all['p'].astype(float))
    pvals.loc[:, 'TSS'] = -np.log10(fisher_gs_tss['p'].astype(float))

    concords = pd.DataFrame(index=pids, columns=['All', 'TSS'])
    concords.loc[:, 'All'] = pd.Series(dict([
        (pid, (ct_gs_all[pid][1, 0] + ct_gs_all[pid][0, 1]) / float(ct_gs_all[pid].sum()) * 100.) for pid in pids
    ]))
    concords.loc[:, 'TSS'] = pd.Series(dict([
        (pid, (ct_gs_tss[pid][1, 0] + ct_gs_tss[pid][0, 1]) / float(ct_gs_tss[pid].sum()) * 100.) for pid in pids
    ]))

    plt_dict = scatterplot_pvalues_concordance(pvals, concords, vmin=0., vmax=2.)
    plt_dict['cbar'].set_label(r'$-\log_{10}(p)$')
    plt_dict['fig'].tight_layout()
    plt_dict['fig'].savefig(os.path.join(outdir, "fisher_p_concordance_scatter_gs_dmr_de_genes.png"), dpi=200)

    plt_dict = line_plot_pvalues_concordance(pvals, concords, vmin=0., vmax=2.)
    plt_dict['fig'].savefig(os.path.join(outdir, "fisher_p_concordance_line_gs_dmr_de_genes.png"), dpi=200)


    # rather than requiring DMR and DE, will we get a better idea working with DMR and looking at logFC
    # (regardless of whether the gene is DE or not)

    specific_sets = setops.specific_sets(pids)
    vs, vc = setops.venn_from_arrays(*[dmr_res_all[pid].keys() for pid in pids])
    specific_features = dict([
        (pid, sorted(vs[specific_sets[pid]])) for pid in pids
    ])

    logfc_vs_median_delta_all = {}
    logfc_vs_median_delta_tss = {}

    logfc_vs_median_delta_specific_all = {}
    logfc_vs_median_delta_specific_tss = {}

    def get_logfc_vs_median_delta(dmr_res, de_res, dmr_relations=None):
        if dmr_relations is not None and not hasattr(dmr_relations, '__iter__'):
            dmr_relations = [dmr_relations]
        if dmr_relations is not None:
            # filter to include only the provided relations
            dmr_res = dmr_res.loc[dmr_res[dmr_relations].any(axis=1)]

        ens_ix = annotation_gene_to_ensembl.gene_to_ens(dmr_res.gene)
        x = de_res.reindex(ens_ix.dropna().values)['logFC']
        y = dmr_res.loc[~ens_ix.isnull().values].median_delta
        y = y[~x.isnull().values]
        x = x.dropna()

        return x, y

    for pid in pids:
        tbl = dmr_res_s1[pid].to_table(include='significant', expand=True)
        logfc_vs_median_delta_all[pid] = get_logfc_vs_median_delta(tbl, de_res_full_s1[pid])
        logfc_vs_median_delta_tss[pid] = get_logfc_vs_median_delta(tbl, de_res_full_s1[pid], dmr_relations=relations_tss)
        logfc_vs_median_delta_specific_all[pid] = get_logfc_vs_median_delta(
            tbl.loc[tbl.cluster_id.isin(specific_features[pid])],
            de_res_full_s1[pid]
        )
        logfc_vs_median_delta_specific_tss[pid] = get_logfc_vs_median_delta(
            tbl.loc[tbl.cluster_id.isin(specific_features[pid])],
            de_res_full_s1[pid],
            dmr_relations=relations_tss
        )

    fig, axs = de_dmr_concordance_scatter(
        dict([(pid, logfc_vs_median_delta_all[pid][0]) for pid in pids]),
        dict([(pid, logfc_vs_median_delta_all[pid][1]) for pid in pids]),
        groups,
        de_edge=dict([(pid, logfc_vs_median_delta_tss[pid][0]) for pid in pids]),
        dm_edge=dict([(pid, logfc_vs_median_delta_tss[pid][1]) for pid in pids]),
    )
    fig.savefig(os.path.join(outdir, "logfc_dmr_scatter.png"), dpi=200)

    fig, axs = de_dmr_concordance_scatter(
        dict([(pid, logfc_vs_median_delta_specific_all[pid][0]) for pid in pids]),
        dict([(pid, logfc_vs_median_delta_specific_all[pid][1]) for pid in pids]),
        groups,
        de_edge=dict([(pid, logfc_vs_median_delta_specific_tss[pid][0]) for pid in pids]),
        dm_edge=dict([(pid, logfc_vs_median_delta_specific_tss[pid][1]) for pid in pids]),
    )

    fig.savefig(os.path.join(outdir, "logfc_dmr_specific_scatter.png"), dpi=200)

    # are the genes associated with patient-specific DMRs significantly more concordant than the full list?
    # base our analysis on permutations and concordance %

    ## TODO: move this to a function and run it also on DE/DMR analysis (this is all gene/DMR analysis)

    n_iter = 1000
    logfc_vs_median_perm = {}
    logfc_vs_median_actual = {}
    n_samples = dict([
        (pid, len(logfc_vs_median_delta_specific_all[pid][0])) for pid in pids
    ])
    for pid in pids:
        x1, y1 = logfc_vs_median_delta_specific_all[pid]
        n = x1.size
        # ct1 = basic.construct_contingency(x1.values, y1.values)
        # logfc_vs_median_actual[pid] = basic.odds_ratio(ct1)
        logfc_vs_median_actual[pid] = ((x1 < 0).values != (y1 < 0).values).sum() / float(n)
        ix = range(logfc_vs_median_delta_all[pid][0].size)
        logfc_vs_median_perm[pid] = []
        for i in range(n_iter):
            this_ix = np.random.permutation(ix)[:n]
            x2 = logfc_vs_median_delta_all[pid][0].iloc[this_ix]
            y2 = logfc_vs_median_delta_all[pid][1].iloc[this_ix]
            # this_ct = basic.construct_contingency(x2.values, y2.values)
            # logfc_vs_median_perm[pid].append(basic.odds_ratio(this_ct))
            logfc_vs_median_perm[pid].append(((x2 < 0).values != (y2 < 0).values).sum() / float(n))

    # plot it
    fig, axs = plt.subplots(ncols=1, nrows=len(pids), sharex=True, figsize=(3.5, 6.))
    big_ax = common.add_big_ax_to_subplot_fig(fig)
    for i, pid in enumerate(pids):
        ax = axs[i]
        ax.hist(
            logfc_vs_median_perm[pid],
            np.linspace(0, 1, n_samples[pid]),
            color=consts.METHYLATION_DIRECTION_COLOURS[groups_inv[pid].lower()]
        )
        ax.axvline(logfc_vs_median_actual[pid], c='k', linestyle='--')
        ax.yaxis.set_ticks([])
        ax.set_ylabel(pid)
    axs[-1].set_xlabel('Concordance')
    big_ax.set_ylabel('Density')
    fig.subplots_adjust(bottom=0.1, left=0.15, top=0.98, right=0.98, hspace=0.13)
    fig.savefig(os.path.join(outdir, "concordance_specific_vs_all_permutation.png"), dpi=200)

    # permutation test: pick # specific DMRs from the list at random
    dmr_res_tbl = dict([
        (pid, dmr_res_s1[pid].to_table(include='all', skip_geneless=False, expand=False)) for pid in pids
    ])
    n_cluster = dmr_res_tbl.values()[0].shape[0]
    n_iter = 1000

    dmr_spec_direction_perm = []
    for i in range(n_iter):
        # reassign DMR cluster IDs
        new_ix = np.random.permutation(n_cluster) + 1
        this_perm = {}
        for pid in pids:
            this_tbl = dmr_res_tbl[pid].copy()
            this_tbl.index = new_ix
            this_perm[pid] = this_tbl.loc[specific_features[pid], 'median_delta'].values
        dmr_spec_direction_perm.append(this_perm)

    dmr_spec_direction_actual = dict([
        (pid, dmr_res_tbl[pid].loc[specific_features[pid], 'median_delta'].values) for pid in pids
    ])

    # plot it and calculate p values
    dmr_spec_direction_perm_pvals = {}
    pct_hyper_func = lambda pid: [(x[pid] > 0).sum() / float(x[pid].size) * 100. for x in dmr_spec_direction_perm]

    fig, axs = plt.subplots(ncols=1, nrows=len(pids), sharex=True, figsize=(3.5, 6.))
    big_ax = common.add_big_ax_to_subplot_fig(fig)
    for i, pid in enumerate(pids):
        u = dmr_spec_direction_actual[pid]
        n = u.size
        t = pct_hyper_func(pid)
        u = (u > 0).sum() / float(n) * 100.

        p_lo = (np.array(t) <= u).sum() / float(n_iter)
        p_hi = (np.array(t) >= u).sum() / float(n_iter)
        dmr_spec_direction_perm_pvals[pid] = min(p_lo, p_hi)

        ax = axs[i]
        k = stats.gaussian_kde(t)
        x = np.linspace(0, 100, 200)
        y = k.evaluate(x)
        ax.fill_between(
            x,
            y,
            facecolor=consts.METHYLATION_DIRECTION_COLOURS[groups_inv[pid].lower()],
            edgecolor='k',
            linewidth=1.,
        )
        ax.axvline(u, c='k', linestyle='--')
        ax.yaxis.set_ticks([])
        ax.set_ylabel(pid)
    axs[-1].set_xlabel('% DMRs hypermethylated')
    axs[-1].set_xlim([0, 100])
    big_ax.set_ylabel('Density')
    fig.subplots_adjust(bottom=0.1, left=0.15, top=0.98, right=0.95, hspace=0.13)
    fig.savefig(os.path.join(outdir, "specific_dmr_direction_permutations.png"), dpi=200)




