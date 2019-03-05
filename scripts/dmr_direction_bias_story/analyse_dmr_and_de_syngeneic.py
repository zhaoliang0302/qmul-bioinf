from plotting import bar, common, venn
from methylation import dmr
from rnaseq import loader as rnaseq_loader
import pandas as pd
from utils import output, setops, genomics, log, dictionary
import multiprocessing as mp
import os
import collections
import numpy as np
import pickle
import references
from scipy import stats
from matplotlib import pyplot as plt, colors, gridspec
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
import seaborn as sns
from sklearn.neighbors import KernelDensity
from scripts.hgic_final import two_strategies_grouped_dispersion as tsgd, two_strategies_combine_de_dmr as tscd, consts
from scripts.hgic_final import analyse_dmrs_s1_direction_distribution as addd
from scripts.dmr_direction_bias_story import same_process_applied_to_de as same_de
from scripts.methylation import dmr_values_to_bigwig
from integrator import rnaseq_methylationarray

from settings import HGIC_LOCAL_DIR, LOCAL_DATA_DIR
logger = log.get_console_logger()


def dm_direction_bar_plot(res, keys=None):
    from scripts.hgic_final import analyse_dmrs_s1_direction_distribution as addd

    if keys is None:
        keys = sorted(res.keys())

    # bar plot showing balance of DMR direction
    fig, axs = plt.subplots(nrows=2, sharex=True, figsize=(5.5, 5.5))

    addd.direction_of_dm_bar_plot(
        res,
        pids=keys,
        as_pct=True,
        ax=axs[0],
        legend=False
    )
    axs[0].set_ylabel('% DMRs')
    addd.direction_of_dm_bar_plot(
        res,
        pids=keys,
        as_pct=False,
        ax=axs[1],
        legend=False
    )
    axs[1].set_ylabel('Number DMRs')
    plt.setp(axs[1].xaxis.get_ticklabels(), rotation=90)

    return {
        'axs': axs,
        'fig': fig
    }


if __name__ == '__main__':
    """
    Use the DMR bias results to lookup into DE results (and vice versa?)
    """
    outdir = output.unique_output_dir()
    de_res_fn = os.path.join(HGIC_LOCAL_DIR, 'current/core_pipeline/rnaseq', 'full_de_syngeneic_only.xlsx')
    pids = consts.PIDS

    DE_LOAD_DIR = os.path.join(output.OUTPUT_DIR, 'de')
    de_params = consts.DE_PARAMS

    norm_method_s1 = 'swan'
    dmr_params = consts.DMR_PARAMS
    dmr_params['n_jobs'] = mp.cpu_count()
    DMR_LOAD_DIR = os.path.join(output.OUTPUT_DIR, 'dmr')

    # should we add 'chr' prefix to bigwig output?
    chr_prefix = True

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

    plt_dict = same_de.bar_plot(de_linked, pids)
    plt_dict['fig'].tight_layout()
    plt_dict['fig'].savefig(os.path.join(outdir, "de_linked_syngeneic_full_list_directions.png"), dpi=200)

    # patient-specific DMRs linked to genes
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

    plt_dict = same_de.bar_plot(de_linked_spec, pids)
    plt_dict['fig'].tight_layout()
    plt_dict['fig'].savefig(os.path.join(outdir, "de_specific_linked_syngeneic_full_list_directions.png"), dpi=200)

    # hypo/hyper DMRs in the hypo group linked (SEPARATELY) to DE

    groups = {
        'Hypo': ['019', '030', '031', '017'],
        'Hyper': ['018', '050', '054', '061', '026', '052']
    }
    group_ind = setops.groups_to_ind(pids, groups)
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

    # now take all DMRs in the hypo (full OR partial) group (and ditto hyper) and merge with DE
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

        plt_dict = dm_direction_bar_plot(this_results, groups[grp])
        plt_dict['fig'].savefig(os.path.join(outdir, "dmr_direction_by_group_%s.png" % grp), dpi=200)

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

    # is there much overlap in the gene sets between the two groups?
    fig = plt.figure(figsize=(5, 3))
    ax = fig.add_subplot(111)
    venn.venn_diagram(genes_from_dmr_groups['Hyper'], genes_from_dmr_groups['Hypo'], set_labels=['Hyper', 'Hypo'], ax=ax)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "genes_from_dmr_groups_venn.png"), dpi=200)

    # no, but if we look at the intersection genes, are they in different directions (DE) between the two groups?
    groups_inv = dictionary.complement_dictionary_of_iterables(groups, squeeze=True)
    in_both = setops.reduce_intersection(*genes_from_dmr_groups.values())
    in_both_ens = references.gene_symbol_to_ensembl(in_both)

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


    # generate scatter plots of joint DE and DMR for the two DMR groups
    # FIXME: this is hard coded to the number of patients in each group. Sloppy.
    fig, axs = plt.subplots(nrows=2, ncols=6, sharex=True, sharey=True)
    big_ax = common.add_big_ax_to_subplot_fig(fig)

    subplots_filled = set()
    for i, grp in enumerate(groups):
        for j, pid in enumerate(groups[grp]):
            subplots_filled.add((i, j))
            ax = axs[i, j]
            this_joint = joint_de_dmr_s1[pid].loc[joint_de_dmr_s1[pid].cluster_id.isin(dmr_groups[grp])]
            ax.scatter(this_joint.de_logFC, this_joint.dmr_median_delta, c=consts.METHYLATION_DIRECTION_COLOURS[grp.lower()])
            ax.axhline(0., c='k', linestyle='--')
            ax.axvline(0., c='k', linestyle='--')
            ax.set_title(pid)
    big_ax.set_xlabel(r'DE logFC')
    big_ax.set_ylabel(r'DMR median $\Delta M$')
    fig.tight_layout()

    for i in range(2):
        for j in range(6):
            if (i, j) not in subplots_filled:
                axs[i, j].set_visible(False)
    axs[0,0].set_ylim([-7, 7])
    fig.savefig(os.path.join(outdir, "de_dmr_scatter_from_dmr_groups.png"), dpi=200)