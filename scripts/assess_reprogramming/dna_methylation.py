from methylation import loader, dmr, process
from plotting import clustering, common, venn
from stats import transformations
import pandas as pd
import numpy as np
import copy
import os
from utils import output, setops
import references
from scipy.stats import zscore
import numpy as np
import multiprocessing as mp
from matplotlib import pyplot as plt
import seaborn as sns


def construct_colour_array_legend_studies(meta):
    studies = {}
    cc = pd.DataFrame('gray', index=meta.index, columns=['Cell type', 'Study'])

    cc.loc[meta['type'] == 'FB', 'Cell type'] = '#fff89e'
    cc.loc[(meta['type'] == 'iPSC') & (meta['batch'] == 'Our data'), 'Cell type'] = 'blue'
    cc.loc[(meta['type'] == 'iPSC') & (meta['batch'] != 'Our data'), 'Cell type'] = '#96daff'
    cc.loc[meta['type'] == 'ESC', 'Cell type'] = 'green'
    cc.loc[meta['type'] == 'EPS', 'Cell type'] = '#7fc97f'
    cc.loc[(meta['type'] == 'iNSC') & (meta['batch'] == 'Our data'), 'Cell type'] = '#9e3900'  # chestnut
    cc.loc[meta['type'] == 'iNSC', 'Cell type'] = '#db7b00'  # orange
    cc.loc[meta['type'] == 'NPC', 'Cell type'] = '#db7b00'  # orange
    cc.loc[meta['type'] == 'NSC', 'Cell type'] = '#db7b00'  # orange
    cc.loc[(meta['type'] == 'NSC') & (meta.index.str.contains('fetal')), 'Cell type'] = '#ffaf47'  # light orange

    batches = meta.batch.unique()
    n_study = len(batches)
    study_colours = common.COLOUR_BREWERS[n_study]
    for i, c in enumerate(study_colours):
        cc.loc[meta['batch'] == batches[i], 'Study'] = c
        studies[batches[i]] = c

    return cc, studies


def load_methylation(pids, ref_names=None, norm_method='swan', ref_name_filter=None, units='beta'):
    """
    Load and prepare the Illumina methylation data
    """
    # patient data
    obj = loader.load_by_patient(pids, norm_method=norm_method)
    anno = loader.load_illumina_methylationepic_annotation()

    # reference data
    if ref_names is not None:
        ref_obj = loader.load_reference(ref_names, norm_method=norm_method)
        if ref_name_filter is not None:
            ref_obj.filter_by_sample_name(ref_name_filter, exact=True)
        obj = loader.loader.MultipleBatchLoader([obj, ref_obj])

    me_data = obj.data.dropna()
    if units == 'm':
        me_data = process.m_from_beta(me_data)

    # reduce anno and data down to common probes
    common_probes = anno.index.intersection(me_data.index)

    anno = anno.loc[common_probes]
    # dmr.add_merged_probe_classes(anno)
    me_data = me_data.loc[common_probes]
    obj.data = me_data

    return obj, anno


def pair_dmr(me_meta, me_data, dmr_clusters, pids, type1='iPSC', type2='FB', **dmr_params):
    res = {}

    for pid in pids:
        this = dmr_clusters.copy()
        the_idx1 = me_meta.index.str.contains(pid) & (me_meta.loc[:, 'type'] == type1)
        the_idx2 = me_meta.index.str.contains(pid) & (me_meta.loc[:, 'type'] == type2)
        the_idx = the_idx1 | the_idx2
        the_groups = me_meta.loc[the_idx, 'type'].values
        the_samples = me_meta.index[the_idx].groupby(the_groups)
        the_samples = [the_samples[type1], the_samples[type2]]

        this.test_clusters(
            me_data,
            samples=the_samples,
            n_jobs=dmr_params['n_jobs'],
            min_median_change=dmr_params['delta_m_min'],
            method=dmr_params['dmr_test_method'],
            alpha=dmr_params['alpha'],
            **dmr_params['test_kwargs']
        )
        res[pid] = this
    return dmr.DmrResultCollection(**res)

if __name__ == "__main__":
    outdir = output.unique_output_dir("assess_reprogramming_methylation")
    pids = ['019', '030', '031', '050', '054']

    # these are the only two norming methods available in all data sets
    # norm_method = 'raw'
    norm_method = 'bmiq'
    # norm_method = 'pbc'

    min_val = 0.75  # value above which a probe is definitely methylated
    n_above_min = 3

    dmr_params = {
        'd_max': 400,
        'n_min': 6,
        'delta_m_min': 1.4,
        'alpha': 0.01,
        'dmr_test_method': 'mwu',  # 'mwu', 'mwu_permute'
        'test_kwargs': {},
        'n_jobs': mp.cpu_count(),
    }

    # our data
    me_obj, anno = load_methylation(pids, norm_method=norm_method)
    our_data = me_obj.data
    our_meta = me_obj.meta

    # discard unneeded samples
    our_meta = our_meta.loc[our_meta.type.isin(['iPSC', 'FB'])]
    our_data = our_data.loc[:, our_meta.index]
    our_meta.loc[:, 'batch'] = 'Our data'

    # ref data
    refs = [
        ('Kim et al.', loader.gse38216(norm_method=norm_method, samples=['H9 ESC 1', 'H9 ESC 2', 'H9 NPC 1', 'H9 NPC 2'])),
        ('Zimmerlin et al.', loader.gse65214(norm_method=norm_method)),
        ('Encode EPIC', loader.encode_epic(norm_method=norm_method)),
        ('Encode 450k', loader.encode_450k(norm_method=norm_method)),
    ]
    for bid, r in refs:
        r.batch_id = bid
        r.meta.index = ["%s_%s" % (t, bid) for t in r.meta.index]
        r.data.columns = r.meta.index
    ref_obj = loader.loader.MultipleBatchLoader([t[1] for t in refs])

    ref_meta = ref_obj.meta
    ref_data = ref_obj.data.dropna()

    # drop unneeded ref data
    ref_meta = ref_obj.meta.loc[ref_obj.meta.index.str.contains('ESC')]
    ref_data = ref_data.loc[:, ref_meta.index]

    # HipSci data
    hip_meta, hip_data = loader.hipsci(norm_method=norm_method, n_sample=30)

    # clustering genome-wide

    # iPSC, FB, ESC
    dat = pd.concat(
        (our_data, ref_data, hip_data),
        axis=1,
        join='inner'
    )
    meta = pd.concat(
        (our_meta, ref_meta, hip_meta),
        axis=0
    )
    meta.loc[meta.type == 'PSC', 'type'] = 'ESC'

    # plot distribution of beta values (our data only)
    xi = np.linspace(0, 1, 101)
    xc = xi[:-1] + 0.5 * (xi[1] - xi[0])
    color_scalars = np.linspace(0, 1, our_data.shape[1])
    fig = plt.figure()
    ax = fig.add_subplot(111)
    color_scalars = np.linspace(0, 1, our_data.shape[1])
    for i, (c, ser) in enumerate(our_data.iteritems()):
        yh, _ = np.histogram(ser, xi, normed=True)
        ax.plot(xc, yh, label=c, color=plt.cm.jet(color_scalars[i]))
    ax.set_xlabel('Beta')
    ax.set_ylabel('Density')
    ax.legend(loc='upper right')
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "edf_our_data_%s.png" % norm_method), dpi=200)


    # plot distribution of beta values (all data)
    leg_marker = set()
    plt_colours = {
        'IPSC': {'color': 'black'},
        'HPS': {'color': '#70a6ff', 'alpha': 0.6},
        'ESC': {'color': '#f77e7e'},
        'FB': {'color': '#a3d838'},
    }
    fig = plt.figure()
    ax = fig.add_subplot(111)
    color_scalars = np.linspace(0, 1, dat.shape[1])
    for i, (c, ser) in enumerate(dat.iteritems()):
        kwds = {}
        for patt, d in plt_colours.items():
            if patt in c:
                kwds = d
                if patt not in leg_marker:
                    kwds['label'] = patt  # TODO: make this more flexible
                    leg_marker.add(patt)
                else:
                    kwds['label'] = None
                break
        yh, _ = np.histogram(ser, xi, normed=True)
        ax.plot(xc, yh, **kwds)
    ax.set_xlabel('Beta')
    ax.set_ylabel('Density')
    fig.tight_layout()
    ax.legend(loc='upper right')
    fig.savefig(os.path.join(outdir, "edf_all_data_%s.png" % norm_method), dpi=200)

    # filter data (include only probes meth. in at least n samples)
    dat = dat.loc[(dat > min_val).sum(axis=1) >= n_above_min]

    cc, st = construct_colour_array_legend_studies(meta)
    leg_dict = {
        'Cell type': {
            'FB': '#fff89e',
            'iPSC (this study)': 'blue',
            'iPSC': '#96daff',
            'ESC': 'green',
            'Enhanced PSC': '#7fc97f',
        },
        'Study': st,
    }

    dend = clustering.dendrogram_with_colours(dat, cc, vertical=True, legend_labels=leg_dict, fig_kws={'figsize': [14, 6]})
    dend['fig'].savefig(os.path.join(outdir, "cluster_ipsc_esc_fb_all_probes.png"), dpi=200)

    # Run DMR: iPSC vs matched FB

    # include all probes again
    dat = pd.concat(
        (our_data, ref_data, hip_data),
        axis=1,
        join='inner'
    )
    # convert to M values
    dat_m = process.m_from_beta(dat)
    # drop any infinite valued probes (should be very few)
    inft = (~np.isfinite(dat_m)).sum(axis=1) > 0

    if inft.any():
        dat_m = dat_m.loc[~inft]
        print "Dropped %d probes with infinite M values" % inft.sum()

    this_anno = anno.loc[dat_m.index]
    clusters = []
    cid = 0

    for cc in this_anno.CHR.unique():
        coords = this_anno.loc[anno.CHR == cc, 'MAPINFO'].sort_values()
        this_clust = dmr.identify_cluster(coords, dmr_params['n_min'], dmr_params['d_max'])

        for cl in this_clust.values():
            clusters.append(
                dmr.ProbeCluster(cl, this_anno, cluster_id=cid, chr=cc)
            )
            cid += 1
    dmr_clusters = dmr.DmrResults(clusters=clusters, anno=this_anno)

    # DMRs: iPSC vs matched parental FB
    dmr_res = pair_dmr(meta, dat_m, dmr_clusters, pids, **dmr_params)

    # DMRs: iPSC vs ESC
    # Let's use H7 and H9 by Zimmerlin for this purpose
    res_s2 = {}
    suff = ' hESC_Zimmerlin et al.'
    for pid in pids:
        for r in ['H9', 'H7']:
            this = dmr_clusters.copy()
            the_idx1 = meta.index.str.contains(pid) & (meta.loc[:, 'type'] == 'iPSC')
            the_idx2 = meta.index == (r + suff)
            the_idx = the_idx1 | the_idx2
            the_groups = meta.loc[the_idx, 'type'].values
            the_samples = meta.index[the_idx].groupby(the_groups)
            the_samples = [the_samples['iPSC'], the_samples['ESC']]

            this.test_clusters(
                dat_m,
                samples=the_samples,
                n_jobs=dmr_params['n_jobs'],
                min_median_change=dmr_params['delta_m_min'],
                method=dmr_params['dmr_test_method'],
                alpha=dmr_params['alpha'],
                **dmr_params['test_kwargs']
            )
            res_s2["%s-%s" % (pid, r)] = this
    dmr_res_s2 = dmr.DmrResultCollection(**res_s2)

    # for each PID, define the core DMRs (shared by both ref comparisons)
    core_dmr_our_ipsc_ref_esc = {}
    for pid in pids:
        this_sets = []
        for r in ['H9', 'H7']:
            this_res = dmr_res_s2['%s-%s' % (pid, r)]
            this_sets.append(this_res.results_significant.keys())
        core_cids = setops.reduce_intersection(*this_sets)
        tbls = []
        for r in ['H9', 'H7']:
            this_res = dmr_res_s2['%s-%s' % (pid, r)]
            ## FIXME: this ugly hack is necessary if classes are not defined (make it not so) to run to_table
            this_res._classes = []
            this_tbl = this_res.to_table(include='significant', skip_geneless=False).loc[core_cids]
            this_tbl.columns = ["%s_%s" % (t, r) for t in this_tbl.columns]
            tbls.append(this_tbl)
        this_comb = pd.concat(tbls, axis=1)
        for col in ['chr', 'genes', 'median_1']:
            this_comb.insert(0, col, this_comb['%s_H9' % col])
            this_comb.drop('%s_H9' % col, axis=1, inplace=True)
            this_comb.drop('%s_H7' % col, axis=1, inplace=True)
        core_dmr_our_ipsc_ref_esc[pid] = this_comb

    # for each PID, plot the Venn diag
    fig, axs = plt.subplots(nrows=len(pids), figsize=(3, 11))
    for i, pid in enumerate(pids):
        ax = axs[i]
        this_sets = []
        for r in ['H9', 'H7']:
            this_res = dmr_res_s2['%s-%s' % (pid, r)]
            this_sets.append(this_res.results_significant.keys())
        venn.venn_diagram(*this_sets, set_labels=['H9', 'H7'], ax=ax)
        ax.set_title(pid)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "venn_overlap_dmrs_our_ipsc_vs_ref.png"), dpi=200)

    # starting with core DMRs, split into hyper and hypo and check agreement between refs
    our_ipsc_ref_esc_direction = {}
    for pid, v in core_dmr_our_ipsc_ref_esc.items():
        disagree_ix = np.sign(v.median_delta_H7) != np.sign(v.median_delta_H9)
        n_disagree = disagree_ix.sum()
        print "Patient %s. Of the %d DMRs (iPSC - ref. ESC), %d do not agree in direction." % (
            pid, v.shape[0], n_disagree
        )
        this_med_delta = v.loc[~disagree_ix].median_delta_H9
        our_ipsc_ref_esc_direction[pid] = {
            'hypo': (this_med_delta < 0).sum(),
            'hyper': (this_med_delta > 0).sum(),
        }
    our_ipsc_ref_esc_direction = pd.DataFrame.from_dict(our_ipsc_ref_esc_direction)
    ax = our_ipsc_ref_esc_direction.transpose().plot.bar()
    ax.figure.savefig(os.path.join(outdir, "our_ipsc_esc_ref_dmr_direction.png"), dpi=200)


    # DMRs: iPSC (HipSci) vs ESC
    # Let's use H7 and H9 by Zimmerlin for this purpose
    res_hipsci_esc = {}
    suff = ' hESC_Zimmerlin et al.'
    hip_ids = hip_meta.index[:12]
    for pid in hip_ids:
        for r in ['H9', 'H7']:
            this = dmr_clusters.copy()
            the_idx1 = meta.index.str.contains(pid) & (meta.loc[:, 'type'] == 'iPSC')
            the_idx2 = meta.index == (r + suff)
            the_idx = the_idx1 | the_idx2
            the_groups = meta.loc[the_idx, 'type'].values
            the_samples = meta.index[the_idx].groupby(the_groups)
            the_samples = [the_samples['iPSC'], the_samples['ESC']]

            this.test_clusters(
                dat_m,
                samples=the_samples,
                n_jobs=dmr_params['n_jobs'],
                min_median_change=dmr_params['delta_m_min'],
                method=dmr_params['dmr_test_method'],
                alpha=dmr_params['alpha'],
                **dmr_params['test_kwargs']
            )
            res_hipsci_esc["%s-%s" % (pid, r)] = this
    dmr_res_hipsci_esc = dmr.DmrResultCollection(**res_hipsci_esc)

    # for each PID, define the core DMRs (shared by both ref comparisons)
    core_dmr_hipsci_ref_esc = {}
    for pid in hip_ids:
        this_sets = []
        for r in ['H9', 'H7']:
            this_res = dmr_res_hipsci_esc['%s-%s' % (pid, r)]
            this_sets.append(this_res.results_significant.keys())
        core_cids = setops.reduce_intersection(*this_sets)
        tbls = []
        for r in ['H9', 'H7']:
            this_res = dmr_res_hipsci_esc['%s-%s' % (pid, r)]
            ## FIXME: this ugly hack is necessary if classes are not defined (make it not so) to run to_table
            this_res._classes = []
            this_tbl = this_res.to_table(include='significant', skip_geneless=False).loc[core_cids]
            this_tbl.columns = ["%s_%s" % (t, r) for t in this_tbl.columns]
            tbls.append(this_tbl)
        this_comb = pd.concat(tbls, axis=1)
        for col in ['chr', 'genes', 'median_1']:
            this_comb.insert(0, col, this_comb['%s_H9' % col])
            this_comb.drop('%s_H9' % col, axis=1, inplace=True)
            this_comb.drop('%s_H7' % col, axis=1, inplace=True)
        core_dmr_hipsci_ref_esc[pid] = this_comb

    # for each PID, plot the Venn diag
    fig, axs = plt.subplots(nrows=3, ncols=4, figsize=(9, 8))
    for i, pid in enumerate(hip_ids):
        ax = axs.flat[i]
        this_sets = []
        for r in ['H9', 'H7']:
            this_res = dmr_res_hipsci_esc['%s-%s' % (pid, r)]
            this_sets.append(this_res.results_significant.keys())
        venn.venn_diagram(*this_sets, set_labels=['H9', 'H7'], ax=ax)
        ax.set_title(pid)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "venn_overlap_dmrs_hipsci_ipsc_vs_ref.png"), dpi=200)

    # starting with core DMRs, split into hyper and hypo and check agreement between refs
    hipsci_ref_esc_direction = {}
    for pid, v in core_dmr_hipsci_ref_esc.items():
        disagree_ix = np.sign(v.median_delta_H7) != np.sign(v.median_delta_H9)
        n_disagree = disagree_ix.sum()
        print "HipSci %s. Of the %d DMRs (iPSC - ref. ESC), %d do not agree in direction." % (
            pid, v.shape[0], n_disagree
        )
        this_med_delta = v.loc[~disagree_ix].median_delta_H9
        hipsci_ref_esc_direction[pid] = {
            'hypo': (this_med_delta < 0).sum(),
            'hyper': (this_med_delta > 0).sum(),
        }
    hipsci_ref_esc_direction = pd.DataFrame.from_dict(hipsci_ref_esc_direction)
    ax = hipsci_ref_esc_direction.transpose().plot.bar()
    ax.figure.tight_layout()
    ax.figure.savefig(os.path.join(outdir, "hipsci_esc_ref_dmr_direction.png"), dpi=200)
