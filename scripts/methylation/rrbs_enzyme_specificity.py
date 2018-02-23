import os
import collections
import numpy as np
import re
from settings import DATA_DIR_NON_GIT, LOCAL_DATA_DIR, GIT_LFS_DATA_DIR
import pysam
from matplotlib import pyplot as plt
import pandas as pd
import multiprocessing as mp
from utils import log
logger = log.get_console_logger(__name__)


if __name__ == "__main__":
    basedir = os.path.join(DATA_DIR_NON_GIT, 'rrbseq', 'GC-CV-7163')
    fq1_fn = os.path.join(basedir, 'GC-CV-7163-1_S1_L001_1.fastq.gz')
    fq2_fn = os.path.join(basedir, 'GC-CV-7163-1_S1_L001_2.fastq.gz')
    ncpu = mp.cpu_count()


    indir = os.path.join(basedir, 'mouse/bismark/GC-CV-7163-1_S1')
    bam_fn = os.path.join(indir, 'GC-CV-7163-1_S1_pe.sorted.bam')
    s = pysam.AlignmentFile(bam_fn, 'rb')
    chroms = [str(t) for t in range(1, 20)]
    reads = {}
    for c in chroms:
        reads[c] = []
        it = s.fetch(c)
        for seg in it:
            if seg.flag == 99 or seg.flag == 163:
                # 99: properly mapped in pair, first in pair, forward strand
                # 163: properly mapped in pair, second in pair, forward strand
                if seg.tlen > 0:
                    reads[c].append(seg)

    # read.get_forward_sequence() returns the ORIGINAL sequence, as it appears in the fq file.
    # read.seq returns the ALIGNED sequence
    # this will be the reverse complement if the read mapped to the reverse strand
    # this will be the same if the read mapped to the forward strand

    # Here's an educational example
    c = '19'
    rd_a = reads[c][0]
    rd_b = s.mate(rd_a)
    if rd_a.is_read1:
        rd1 = rd_a
        rd2 = rd_b
    else:
        rd1 = rd_b
        rd2 = rd_a
    if rd1.is_reverse:
        print "Read 1 (%s) is reversed." % rd1.qname
    else:
        print "Read 1 (%s) is not reversed." % rd1.qname

    if rd2.is_reverse:
        print "Read 2 (%s) is reversed." % rd2.qname
    else:
        print "Read 2 (%s) is not reversed." % rd2.qname


    # get the sequences from the reference
    fa_fn = os.path.join(
        LOCAL_DATA_DIR,
        'reference_genomes',
        'mouse',
        'ensembl',
        'GRCm38.p5.r88',
        'fa',
        'Mus_musculus.GRCm38.dna.primary_assembly.fa'
    )
    fa_reader = pysam.FastaFile(fa_fn)

    # now we just want to check the equivalence of an aligned read and the reference sequence
    # TODO

    # for each fragment: does it contain a CCGG site?
    contains_ccgg = []
    contains_ccgg_template = []
    for c in chroms:
        this_ref = fa_reader[c]
        print "Chromosome %s" % c
        for rd in reads[c]:
            if rd.is_proper_pair and not rd.is_reverse:
                ref_seq = this_ref[rd.reference_start:rd.reference_start + rd.template_length]
                if 'CCGG' in ref_seq:
                    contains_ccgg.append(rd)
                    contains_ccgg_template.append(ref_seq)
                # print "F read seq: %s" % rd.seq
                # print "Ref seq: %s" % this_ref[rd.reference_start:rd.reference_start + rd.reference_length]
                # print "*********"

    nc = sum([len(v) for v in reads.values()])
    print "%d / %d fragments contain CCGG (%.2f%%)" % (
        len(contains_ccgg),
        nc,
        len(contains_ccgg) / float(nc) * 100
    )

    chrom_ct = collections.Counter()
    coords = {}
    for rd in contains_ccgg:
        chrom_ct[rd.reference_name] += 1
        coords.setdefault(rd.reference_name, []).append(rd.reference_start)
    all_coords = reduce(lambda x, y: x + y, coords.values())

    # get location of every CpG
    cpg_coords = {}
    n_cpg = 0
    for c in chroms:
        this_ref = fa_reader[c]
        it = re.finditer(r'CG', this_ref)
        cpg_coords[c] = [t.start() for t in it]
        n_cpg += len(cpg_coords[c])

    # get coverage of every CpG
    cpg_cov = {}
    for c in chroms:
        print "Chromosome %s" % c
        cov = s.count_coverage(c)
        cova = [cov[0][i] for i in cpg_coords[c]]
        covc = [cov[1][i] for i in cpg_coords[c]]
        covg = [cov[2][i] for i in cpg_coords[c]]
        covt = [cov[3][i] for i in cpg_coords[c]]
        sa = sum(cova)
        sc = sum(covc)
        sg = sum(covg)
        st = sum(covt)
        pr = (sa + sg) / float(sa + sg + sc + st)
        if pr > 0.01:
            print "Warning: chromosome %s has a high proportion of A and G bases where we expect C or T (%.2f)" % (
                c, pr
            )
        cpg_cov[c] = covc + covt

    cpg_cov_all_nz = np.array(reduce(lambda x, y: x + y, [[t for t in x if t > 0] for x in cpg_cov.values()]))

    # make an inverse CDF (is that called a CEDF?)
    # cc = np.sort(cpg_cov_all_nz)[::-1]
    cov = []
    ecdf = []
    for x in np.unique(cpg_cov_all_nz):
        cov.append(x)
        ecdf.append((cpg_cov_all_nz >= x).sum())
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.bar(cov[:25], ecdf[:25])
    ax.set_xticks(cov[:25])
    ax.set_xlabel('Minimum coverage')
    ax.set_ylabel('Number of CpG sites')

    fig = plt.figure(figsize=(8.5, 5))
    ax1 = fig.add_subplot(111)
    ax1.bar(cov[:25], np.array(ecdf[:25]) / float(n_cpg) * 100)
    ax1.set_xticks(cov[:25])
    ax1.set_xlabel('Minimum coverage')
    ax1.set_ylabel('% CpG sites')
    ax2 = ax1.twinx()
    h = ax2.plot(cov[:25], np.array(ecdf[:25]) / 1e6, 'x')
    ax2.set_ylim(np.array(ax1.get_ylim()) / 100 * n_cpg / 1e6)
    ax2.set_ylabel("Number of CpG sites (millions)")
    h[0].set_visible(False)
    fig.tight_layout()

    cpg_tsv_fn = os.path.join(GIT_LFS_DATA_DIR, 'mouse_cpg_island', 'grcm38_cpgisland.tsv')

    # load tsv
    cpg_regions = pd.read_csv(cpg_tsv_fn, sep='\t', header=0)
    region_pad = 2000

    cov_cpg_islands = []
    from scripts.methylation import rrbs_get_coverage

    if ncpu > 1:
        pool = mp.Pool(ncpu)
        jobs = {}

    for i, row in cpg_regions.iterrows():
        region = (row.chrom, row.chromStart, row.chromEnd)
        kwds = {'region_pad': region_pad}
        if ncpu > 1:
            jobs[i] = pool.apply_async(
                rrbs_get_coverage.get_one_coverage,
                args=(bam_fn, region),
                kwds=kwds
            )
        else:
            res = rrbs_get_coverage.get_one_coverage(bam_fn, region, **kwds)
            cov_cpg_islands.append(res)

    if ncpu > 1:
        pool.close()
        for i, row in cpg_regions.iterrows():
            try:
                res = jobs[i].get(1e6)
                cov_cpg_islands.append(res)
            except Exception:
                logger.exception("Failed to extract region %s:%d-%d.", row.chrom, row.chromStart, row.chromEnd)
