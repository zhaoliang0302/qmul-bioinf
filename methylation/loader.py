from load_data import loader
import pandas as pd
import os
import gzip
import re
import multiprocessing as mp
import numpy as np
from settings import GIT_LFS_DATA_DIR, DATA_DIR

from utils import rinterface, log
from rpy2 import robjects
from rpy2.robjects import pandas2ri, r
pandas2ri.activate()
logger = log.get_console_logger(__name__)

NORM_METHODS = {
    None,
    'raw',
    'bmiq',
    'swan',
    'pbc',
    'funnorm'
}

METHYLATION_DIR = os.path.join(DATA_DIR, 'methylation')

project_dirs = {
    "2016-06-10_brandner": os.path.join(DATA_DIR, 'methylation', '2016-06-10_brandner'),
    "2016-09-21_dutt": os.path.join(DATA_DIR, 'methylation', '2016-09-21_dutt'),
    "2016-12-19_ucl_genomics": os.path.join(DATA_DIR, 'methylation', '2016-12-19_ucl_genomics'),
    "2017-01-17_brandner": os.path.join(DATA_DIR, 'methylation', '2017-01-17_brandner'),
    "2017-02-09_brandner": os.path.join(DATA_DIR, 'methylation', '2017-02-09_brandner'),
    "2017-05-12": os.path.join(DATA_DIR, 'methylation', '2017-05-12'),
    "2017-08-23": os.path.join(DATA_DIR, 'methylation', '2017-08-23'),
    "2017-09-19": os.path.join(DATA_DIR, 'methylation', '2017-09-19'),
    "2018-01-12": os.path.join(DATA_DIR, 'methylation', '2018-01-12'),
    "2018-03-19": os.path.join(DATA_DIR, 'methylation', '2018-03-19'),
    "2018-03-26": os.path.join(DATA_DIR, 'methylation', '2018-03-26'),
    "2018-04-09": os.path.join(DATA_DIR, 'methylation', '2018-04-09'),
    "2018-06-26": os.path.join(DATA_DIR, 'methylation', '2018-06-26'),
    "gse38216": os.path.join(DATA_DIR, 'methylation', 'GSE38216'),
    "gse65214": os.path.join(DATA_DIR, 'methylation', 'GSE65214'),
    "gse67283": os.path.join(DATA_DIR, 'methylation', 'GSE67283'),
    "gse31848": os.path.join(DATA_DIR, 'methylation', 'GSE31848'),
    "gse110544": os.path.join(DATA_DIR, 'methylation', 'GSE110544'),
    "E-MTAB-6194": os.path.join(DATA_DIR, 'methylation', 'E-MTAB-6194'),
    "encode_epic": os.path.join(DATA_DIR, 'methylation', 'ENCODE_EPIC'),
    "encode_450k": os.path.join(DATA_DIR, 'methylation', 'ENCODE_450k'),
    "gse92462_450k": os.path.join(DATA_DIR, 'methylation', 'GSE92462_450K'),
}

PATIENT_LOOKUP_FFPE = {
    '017': [
        ('NH15-1661', '2016-06-10_brandner')
    ],
    '018': [
        ('NH15-1877', '2016-06-10_brandner')
    ],
    '019': [
        ('NH15-2101', '2016-06-10_brandner')
    ],
    '026': [
        ('NH16-270', '2016-06-10_brandner')
    ],
    '030': [
        ('NH16-616', '2016-06-10_brandner')
    ],
    '031': [
        ('NH16-677', '2016-06-10_brandner')
    ],
    '044': [
        ('NH16-1574', '2016-09-21_dutt')
    ],
    '049': [
        ('NH16-1976', '2017-02-09_brandner')
    ],
    '050': [
        ('NH16-2063', '2017-01-17_brandner')
    ],
    '052': [
        ('NH16-2214', '2017-02-09_brandner')
    ],
    '054': [
        ('NH16-2255', '2017-02-09_brandner')
    ],
    '061': [
        ('NH16-2806', '2017-02-09_brandner')
    ],
}

PATIENT_LOOKUP_CELL = {
    '017': [
        ('GBM017_P3', "2017-09-19"),
        ('GBM017_P4', "2017-09-19"),
        ('DURA017_NSC_N3C5_P4', "2017-09-19"),
        ('DURA017_FB_P7', '2018-01-12'),
    ],
    '018': [
        ('GBM018_P12', '2017-05-12'),
        ('GBM018_P10', '2016-12-19_ucl_genomics'),
        ('DURA018_NSC_N4_P4', '2017-05-12'),
        ('DURA018_NSC_N2_P6', '2016-12-19_ucl_genomics'),
        ('DURA018_NH15_1877_P6_15/05/2017', '2018-03-26'),
    ],
    '019': [
        ('GBM019_P4', '2016-12-19_ucl_genomics'),
        ('GBM019_P3n6', "2017-09-19"),
        ('DURA019_NSC_N8C_P2', '2016-12-19_ucl_genomics'),
        ('DURA019_NSC_N5C1_P2', '2018-01-12'),
        ('DURA019_FB_P7', '2018-01-12'),
        ('DURA019_OPC', '2018-03-19'),
        ('DURA019_IPSC_N8C_P13', '2018-03-19'),
        ('DURA019_IAPC_D20_N8C_B2', '2018-06-26'),
        ('DURA019_IAPC_D20_N8C_B3', '2018-06-26'),
        ('DURA019_IOPC_N8C_B2', '2018-06-26'),
    ],
    '026': [
        ('GBM026_P8', '2016-12-19_ucl_genomics'),
        ('GBM026_P3n4', '2017-05-12'),
        ('DURA026_NSC_N31D_P5', '2016-12-19_ucl_genomics'),
        ('DURA026_NH16_270_P8_15/05/2017', '2018-03-26'),
    ],
    '030': [
        ('GBM030_P9', "2017-09-19"),
        ('GBM030_P5', '2017-05-12'),
        ('DURA030_NSC_N16B6_P1', '2017-05-12'),
        ('DURA030_NSC_N9_P2', '2018-01-12'),
        ('DURA030_FB_P8', '2018-01-12'),
        ('DURA030_IPSC_N16B6_P13', '2018-03-19'),
    ],
    '031': [
        ('GBM031_P7', "2017-09-19"),
        ('GBM031_P4', '2016-12-19_ucl_genomics'),
        ('DURA031_NSC_N44B_P2', '2016-12-19_ucl_genomics'),
        ('DURA031_NSC_N44F_P3', '2018-01-12'),
        ('DURA031_FB_P7', '2018-01-12'),
        ('DURA031_OPC', '2018-03-19'),
        ('DURA031_IPSC_N44B_P10', '2018-03-19'),
        ('DURA031_IAPC_D20_N44B_B1', '2018-06-26'),
        ('DURA031_IAPC_D20_N44B_B2', '2018-06-26'),
        ('DURA031_IOPC_N44B_B2', '2018-06-26'),
    ],
    '044': [
        ('GBM044_P4', '2017-05-12'),
        ('GBM044_P8', '2017-05-12'),
        ('DURA044_NSC_N17_P3', '2017-05-12'),
        ('DURA044_NSC_N8_P2', '2017-05-12'),
        ('DURA044_OPC', '2018-03-19'),
        ('DURA044_IAPC_D20_N8_B1', '2018-06-26'),
        ('DURA044_IAPC_D20_N8_B2', '2018-06-26'),
        ('DURA044_IOPC_N8_B2', '2018-06-26'),
    ],
    '049': [
        ('GBM049_P4', "2017-08-23"),
        ('GBM049_P6', "2017-08-23"),
        ('DURA049_NSC_N19_P4', "2017-08-23"),
        ('DURA049_NSC_N5_P2', "2017-08-23"),
        ('DURA049_IPSC_ N5_P10', '2018-01-12'),
        ('DURA049_OPC', '2018-03-19'),
        ('GBM049_P7', '2018-03-19'),
        ('GBM049_P9', '2018-03-19'),
        ('DURA049_IAPC_D20_N19_B2', '2018-06-26'),
        ('DURA049_IAPC_D20_N19_B3', '2018-06-26'),
        ('DURA049_IOPC_N19_B2', '2018-06-26'),
    ],
    '050': [
        ('GBM050_P7n8', "2017-08-23"),
        ('GBM050_P9', "2017-08-23"),
        ('DURA050_NSC_N12_P3', "2017-08-23"),
        ('DURA050_NSC_N16_P4', "2017-08-23"),
        ('DURA050_IPSC_N12_P5', "2018-01-12"),
        ('DURA050_FB_P7', "2018-01-12"),
        ('DURA050_OPC', '2018-03-19'),
        ('DURA050_IAPC_D20_N12_B1', '2018-06-26'),
        ('DURA050_IAPC_D20_N12_B2', '2018-06-26'),
        ('DURA050_IOPC_N12_B2', '2018-06-26'),
    ],
    '052': [
        ('GBM052_P6n7', "2017-09-19"),
        ('GBM052_P4n5', "2017-09-19"),
        ('DURA052_NSC_N4_P3', "2017-09-19"),
        ('DURA052_NSC_N5_P2', "2017-09-19"),
        ('DURA052_OPC', '2018-03-19'),
        ('DURA052_IAPC_D20_N4_B2', '2018-06-26'),
        ('DURA052_IAPC_D20_N4_B3', '2018-06-26'),
        ('DURA052_IOPC_N4_B2', '2018-06-26'),
        ('DURA052_NH16_2214_P6_14/04/2017', '2018-03-26'),
    ],
    '054': [
        ('GBM054_P4', "2017-08-23"),
        ('GBM054_P6', "2017-08-23"),
        ('DURA054_NSC_N3C_P2', "2017-08-23"),
        ('DURA054_NSC_N2E_P1', "2017-08-23"),
        ('DURA054_IPSC_N3C_P11', '2018-01-12'),
        ('DURA054_FB_P5', '2018-01-12'),
    ],
    '061': [
        ('GBM061_P3', "2017-08-23"),
        ('GBM061_P5', "2017-08-23"),
        ('DURA061_NSC_N4_P2', "2017-08-23"),
        ('DURA061_NSC_N6_P4', "2017-08-23"),
        ('DURA061_NSC_N1_P3n4', "2018-04-09"),
    ],
    'GIBCO': [
        ('GIBCONSC_P4', '2017-05-12'),
    ],
    'ICb1299': [
        ('ICb1299_Scr', '2017-09-19'),
        ('ICb1299_shBMI1', '2017-09-19'),
        ('ICb1299_shCHD7', '2017-09-19'),
        ('ICb1299_shBMI1CHD7', '2017-09-19'),
        ('p62_3_shBmi1', '2018-03-26'),
        ('p62_3_shChd7', '2018-03-26'),
        ('p62_3_shB+C', '2018-03-26'),
        ('p62_3_Scr', '2018-04-09'),  # rerun
    ],
    '3021': [
        ('3021_1_Scr', '2018-01-12'),
        ('3021_1_shB', '2018-01-12'),
        ('3021_1_shC', '2018-01-12'),
        ('3021_1_shB+C', '2018-01-12'),
        ('S', '2018-03-19'),
        ('B', '2018-03-19'),
        ('C', '2018-03-19'),
        ('B+C', '2018-03-19'),
    ],

}


def _idat_files_to_beta(
        idat_dir,
        meta_fn,
        outdir=None,
        samples=None,
        array_type='EPIC',
        name_col='sample',
        annotation=None
):
    """
    Using embedded R, load raw idat files and process to generate beta values.
    :param annotation: Can use this to force the annotation to use. It should be a dictionary containing the keys
    `array` and `annotation`. Not currently implemented.
    :param outdir: If supplied, write CSV files (gzipped) to this directory
    """
    if annotation is not None:
        raise NotImplementedError("Haven't implemented force setting annotation yet (see comments).")

    njob = mp.cpu_count()

    # get the idat file basenames
    flist = []
    for root, dirnames, filenames in os.walk(idat_dir):
        for fn in filenames:
            se = os.path.splitext(fn)
            if se[1].lower() == '.idat' and re.search(r'_Red$', se[0]):
                flist.append(os.path.join(root, se[0].replace('_Red', '')))

    # load meta
    meta = pd.read_csv(meta_fn, header=0, index_col=None)
    meta.index = ['%s_%s' % (t.Sentrix_ID, t.Sentrix_Position) for _, t in meta.iterrows()]

    ## TODO: apply sample filtering at this stage to avoid loading unnecessary data

    beta = {}

    rg_set = r("read.metharray")(flist, extended=True)

    ## TODO (?) implement force setting annotation?
    # rgSet@annotation <- c(array="IlluminaHumanMethylationEPIC",annotation="ilm10b2.hg19")

    mset = r("preprocessRaw")(rg_set)
    det_pval = r("detectionP")(rg_set)

    raw_beta = r("getBeta")(mset, "Illumina")

    # ensure everything is in the same order
    meta = meta.loc[list(raw_beta.colnames)]
    det_pval = det_pval.rx(True, raw_beta.colnames)  # True means everything in that axis

    # set the column names based on meta
    snames = robjects.StrVector(meta[name_col].values)
    raw_beta.colnames = snames
    det_pval.colnames = snames
    mset.colnames = snames

    # filter samples if requested (see TODO above)
    if samples is not None:
        if len(pd.Index(samples).difference(meta.index)) > 0:
            logger.warn(
                "Some of the requested sample names were not found: %s",
                ', '.join(pd.Index(samples).difference(meta.index).tolist())
            )
        keep = meta.index[meta.index.isin(samples)]
        meta = meta.loc[keep]
        raw_beta = raw_beta.rx(True, robjects.StrVector(keep))
        det_pval = det_pval.rx(True, robjects.StrVector(keep))

    logger.info("Applying initial ChAMP filtering")
    champ = r("champ.filter")(raw_beta, detP=det_pval, pd=pandas2ri.py2ri(meta), arraytype=array_type)

    beta['raw'] = pandas2ri.ri2py_dataframe(champ.rx('beta'))
    logger.info("Computed raw beta values.")
    if outdir is not None:
        with gzip.open(os.path.join(outdir, "beta_raw.csv.gz"), 'wb') as fout:
            beta['raw'].to_csv(fout)

    try:
        logger.info("Computing BMIQ normalised beta values...")
        b = r("champ.norm")(beta=champ.rx('beta'), method='BMIQ', arraytype=array_type, cores=njob)
        beta['bmiq'] = pandas2ri.ri2py_dataframe(b)
        logger.info("Done.")
        if outdir is not None:
            with gzip.open(os.path.join(outdir, "beta_bmiq.csv.gz"), 'wb') as fout:
                beta['bmiq'].to_csv(fout)
    except Exception:
        logger.exception("BMIQ norming failed")

    try:
        logger.info("Computing PBC normalised beta values...")
        b = r("champ.norm")(beta=champ.rx('beta'), method='PBC', arraytype=array_type)
        beta['pbc'] = pandas2ri.ri2py_dataframe(b)
        logger.info("Done.")
        if outdir is not None:
            with gzip.open(os.path.join(outdir, "beta_pbc.csv.gz"), 'wb') as fout:
                beta['pbc'].to_csv(fout)
    except Exception:
        logger.exception("PBC norming failed")

    try:
        logger.info("Computing Swan normalised beta values...")
        mset_swan = r("preprocessSWAN")(rg_set, mSet = mset)
        b = r("getBeta")(mset_swan)
        b = b.rx(champ.rx('beta').rownames, True)
        beta['swan'] = pandas2ri.ri2py_dataframe(b)
        logger.info("Done.")
        if outdir is not None:
            with gzip.open(os.path.join(outdir, "beta_swan.csv.gz"), 'wb') as fout:
                beta['swna'].to_csv(fout)
    except Exception:
        logger.exception("Swan norming failed")

    if array_type == 'EPIC':
        try:
            logger.info("Computing funnorm normalised beta values (EPIC only)...")
            rgset_funnorm = r("preprocessFunnorm")(rg_set)
            b = r("getBeta")(rgset_funnorm)
            b = b.rx(champ.rx('beta').rownames, True)

            snames = robjects.StrVector(meta.loc[list(b.colnames), name_col].values)
            b.colnames = snames

            beta['funnorm'] = pandas2ri.ri2py_dataframe(b)
            logger.info("Done.")
            if outdir is not None:
                with gzip.open(os.path.join(outdir, "beta_funnorm.csv.gz"), 'wb') as fout:
                    beta['funnorm'].to_csv(fout)
        except Exception:
            logger.exception("Funnorm norming failed")

    return beta


idat_files_to_beta = rinterface.RFunctionDeferred(
    _idat_files_to_beta,
    imports=['ChAMP'],
    redirect_stderr=True,
    redirect_stdout=True
)


def load_illumina_methylationepic_annotation(split_genes=True):
    """

    :param split_genes: If True (default), the RefGene name column will be split into a set - useful for
    many downstream applications
    :return:
    """
    fn = os.path.join(DATA_DIR, 'methylation', 'annotation', 'epic', 'MethylationEPIC_v-1-0_B3.csv.gz')

    usecols = [
        'Name', 'CHR', 'MAPINFO', 'Strand', 'UCSC_RefGene_Name',
        'UCSC_RefGene_Group', 'Relation_to_UCSC_CpG_Island'
    ]
    dtype = dict(
        Name=str,
        CHR=str,
        MAPINFO=str,  # should be int but there are some NA entries
        Strand=str,
        UCSC_RefGene_Name=str,
        UCSC_RefGene_Group=str,
        Relation_to_UCSC_CpG_Island=str
    )
    dat = pd.read_csv(
        fn, skiprows=7, usecols=usecols, dtype=dtype, header=0, index_col=0
    )
    # remove calibration probes
    dat = dat.loc[~dat.loc[:, 'MAPINFO'].isnull()]
    dat.loc[:, 'MAPINFO'] = dat.loc[:, 'MAPINFO'].astype(int)

    # correct gene symbols - look up what these should be - some kind of Excel fail?
    correction = {
        '1-Mar': 'MARCH1',
        '1-Sep': 'SEPT1',
        '10-Mar': 'MARCH10',
        '11-Mar': 'MARCH11',
        '11-Sep': 'SEPT11',
        '13-Sep': 'SEPT13',
        '2-Mar': 'MARCH2',
        '3-Mar': 'MARCH3',
        '4-Mar': 'MARCH4',
        '5-Sep': 'SEPT5',
        '6-Mar': 'MARCH6',
        '7-Mar': 'MARCH7',
        '8-Mar': 'MARCH8',
        '9-Sep': 'SEPT9',
    }
    regex = re.compile('|'.join(correction.keys()))
    corr_idx = dat.loc[:, 'UCSC_RefGene_Name'].dropna().str.contains(regex)
    corr_idx = corr_idx.index[corr_idx]
    dat.loc[corr_idx, 'UCSC_RefGene_Name'] = dat.loc[corr_idx, 'UCSC_RefGene_Name'].apply(lambda x: correction[x])

    if split_genes:
        dat.loc[:, 'UCSC_RefGene_Name'] = \
            dat.UCSC_RefGene_Name.str.split(';').apply(lambda x: x if isinstance(x, list) else [])
        dat.loc[:, 'UCSC_RefGene_Group'] = \
            dat.UCSC_RefGene_Group.str.split(';').apply(lambda x: x if isinstance(x, list) else [])
        # collapse these down to unique pairs
        gene_type = [list(set(zip(*t))) for t in zip(dat.loc[:, 'UCSC_RefGene_Name'], dat.loc[:, 'UCSC_RefGene_Group'])]
        gene, rel = zip(*[zip(*t) if len(t) else [(), ()] for t in gene_type])
        dat.loc[:, 'UCSC_RefGene_Name'] = gene
        dat.loc[:, 'UCSC_RefGene_Group'] = rel
    return dat


def load_illumina_methylation450_annotation():
    fn = os.path.join(DATA_DIR, 'methylation', 'annotation', '450', 'GPL13534_HumanMethylation450_15017482_v.1.1.csv.gz')
    usecols = [
        'Name', 'CHR', 'MAPINFO', 'Strand', 'UCSC_RefGene_Name',
        'UCSC_RefGene_Group', 'Relation_to_UCSC_CpG_Island'
    ]
    dtype = dict(
        Name=str,
        CHR=str,
        MAPINFO=str,  # should be int but there are some NA entries
        Strand=str,
        UCSC_RefGene_Name=str,
        UCSC_RefGene_Group=str,
        Relation_to_UCSC_CpG_Island=str
    )
    dat = pd.read_csv(
        fn, skiprows=7, usecols=usecols, dtype=dtype, header=0, index_col=0
    )
    # remove calibration probes
    dat = dat.loc[~dat.loc[:, 'MAPINFO'].isnull()]
    dat.loc[:, 'MAPINFO'] = dat.loc[:, 'MAPINFO'].astype(int)

    return dat


class IlluminaHumanMethylationLoader(loader.SingleFileLoader):
    row_indexed = True

    def __init__(self, *args, **kwargs):
        super(IlluminaHumanMethylationLoader, self).__init__(*args, **kwargs)

    def load_one_file(self, fn):
        return pd.read_csv(fn, header=0, index_col=0)


def load_by_patient(
        patient_ids,
        type='cell_culture',
        norm_method='swan',
        include_control=True,
        samples=None,
        reduce_to_common_probes=True,
):
    """
    Load all RNA-Seq count data associated with the patient ID(s) supplied
    :param patient_ids: Iterable or single int or char
    :param source:
    :param include_control: If True (default) include Gibco reference NSC
    :return:
    """

    if type == "cell_culture":
        LOOKUP = PATIENT_LOOKUP_CELL
    elif type == "ffpe":
        LOOKUP = PATIENT_LOOKUP_FFPE
    else:
        raise NotImplementedError()

    cls = IlluminaHumanMethylationLoader

    # ensure patient IDs are in correct form
    if patient_ids == 'all':
        patient_ids = [t for t in LOOKUP.keys() if t != 'GIBCO']
    elif hasattr(patient_ids, '__iter__'):
        patient_ids = [t if isinstance(t, str) or isinstance(t, unicode) else ('%03d' % t) for t in patient_ids]
    else:
        if isinstance(patient_ids, str):
            patient_ids = [patient_ids]
        else:
            patient_ids = ['%03d' % patient_ids]

    if include_control and type == 'cell_culture':
        patient_ids += ['GIBCO']

    # precompute the loaders required to avoid reloading multiple times
    # we'll also take a note of the order for later reordering
    sample_order = []
    by_loader = {}
    for pid in patient_ids:
        d = LOOKUP[pid]
        for s, ldr in d:
            if samples is not None:
                if s in samples:
                    by_loader.setdefault(ldr, []).append(s)
                    sample_order.append(s)
            else:
                by_loader.setdefault(ldr, []).append(s)
                sample_order.append(s)

    objs = []
    for ldr, smp in by_loader.items():
        base_dir = os.path.join(project_dirs[ldr], 'beta')
        data_fn = os.path.join(base_dir, 'beta_%s.csv.gz' % ('raw' if norm_method is None else norm_method))
        meta_fn = os.path.join(project_dirs[ldr], 'sources.csv')

        objs.append(
            cls(
                # base_dir=base_dir,
                data_fn=data_fn,
                meta_fn=meta_fn,
                samples=smp,
                norm_method=norm_method,
                batch_id=ldr
            )
        )

    if len(objs) > 1:
        # retain missing probes here for accountability - we can drop them later
        res = loader.MultipleBatchLoader(objs, intersection_only=False)
    else:
        res = objs[0]

    # apply original ordering
    res.reorder_samples(sample_order)

    if samples is not None:
        res.filter_by_sample_name(samples, exact=True)

    # check for missing data and warn if too substantial
    if reduce_to_common_probes:
        n_init = res.data.shape[0]
        dat = res.data.dropna()
        n_after = dat.shape[0]
        if (n_init - n_after) / float(n_init) > 0.05:
            logger.warn(
                "Dropping probes with null values results in %d probes being lost (%.2f%%). Number remaining: %d.",
                n_init - n_after,
                (n_init - n_after) / float(n_init) * 100.,
                n_after
            )
        res.data = dat

    return res


def load_by_sample_name(
    samples,
    type='cell_culture',
    norm_method='swan',
):
    """
    Load all methylation data from the samples requested
    :param patient_ids: Iterable or single int or char
    :param source:
    :param include_control: If True (default) include Gibco reference NSC
    :return:
    """

    if not hasattr(samples, '__iter__'):
        samples = [samples]

    samples_remaining = set(samples)

    if type == "cell_culture":
        LOOKUP = PATIENT_LOOKUP_CELL
    elif type == "ffpe":
        LOOKUP = PATIENT_LOOKUP_FFPE
    else:
        raise NotImplementedError()

    cls = IlluminaHumanMethylationLoader

    # precompute the loaders required to avoid reloading multiple times
    # we'll also take a note of the order for later reordering
    sample_order = []
    by_loader = {}
    for pid, arr in LOOKUP.items():
        for sn, ldr in arr:
            if sn in samples_remaining:
                by_loader.setdefault(ldr, []).append(sn)
                sample_order.append(sn)
                samples_remaining.remove(sn)

    if len(samples_remaining) > 0:
        logger.warn("Found %d of the %d samples requested.", len(sample_order), len(samples_remaining))
        logger.warn("Samples missing: %s", ", ".join(sorted(samples_remaining)))

    objs = []
    for ldr, smp in by_loader.items():
        base_dir = os.path.join(project_dirs[ldr], 'beta')
        meta_fn = os.path.join(project_dirs[ldr], 'sources.csv')

        objs.append(
            cls(
                base_dir=base_dir,
                meta_fn=meta_fn,
                samples=smp,
                norm_method=norm_method,
                batch_id=ldr
            )
        )

    if len(objs) > 1:
        # retain missing probes here for accountability - we can drop them later
        res = loader.MultipleBatchLoader(objs, intersection_only=False)
    else:
        res = objs[0]

    # apply original ordering
    res.reorder_samples([t for t in samples if t in sample_order])

    # check for missing data and warn if too substantial
    n_init = res.data.shape[0]
    dat = res.data.dropna()
    n_after = dat.shape[0]
    if (n_init - n_after) / float(n_init) > 0.05:
        logger.warn(
            "Dropping probes with null values results in %d probes being lost (%.2f%%). Number remaining: %d.",
            n_init - n_after,
            (n_init - n_after) / float(n_init) * 100.,
            n_after
        )
    res.data = dat

    return res


def load_reference(ref_names, norm_method='pbc', samples=None):
    if not hasattr(ref_names, '__iter__'):
        ref_names = [ref_names]

    objs = []
    for rid in ref_names:
        base_dir = os.path.join(METHYLATION_DIR, rid)
        if not os.path.isdir(base_dir):
            raise ValueError("Directory %s for ref %s does not exist." % (base_dir, rid))

        meta_fn = os.path.join(base_dir, 'sources.csv')
        data_fn = os.path.join(base_dir, 'beta', 'beta_%s.csv.gz' % norm_method)
        ldr = IlluminaHumanMethylationLoader(
            data_fn,
            meta_fn=meta_fn,
            batch_id=rid,
        )
        objs.append(ldr)

    if len(objs) > 1:
        res = loader.MultipleBatchLoader(objs)
    else:
        res = objs[0]

    if samples is not None:
        res.filter_by_sample_name(samples)

    return res


def e_mtab_6194(norm_method='raw', samples=None):
    base_dir = os.path.join(DATA_DIR, 'methylation', 'E-MTAB-6194')
    beta_dir = os.path.join(base_dir, 'beta')
    meta_fn = os.path.join(base_dir, 'sources.csv')
    return IlluminaHumanMethylationLoader(
        base_dir=beta_dir,
        meta_fn=meta_fn,
        batch_id="E-MTAB-6194",
        norm_method=norm_method,
        samples=samples
    )



def gse92462_epic(norm_method='raw', samples=None):
    base_dir = os.path.join(DATA_DIR, 'methylation', 'GSE92462_EPIC')
    beta_dir = os.path.join(base_dir, 'beta')
    meta_fn = os.path.join(base_dir, 'sources.csv')
    return IlluminaHumanMethylationLoader(
        base_dir=beta_dir,
        meta_fn=meta_fn,
        batch_id="GSE92462_EPIC",
        norm_method=norm_method,
        samples=samples
    )


def gse92462_450k(norm_method='raw', samples=None):
    base_dir = os.path.join(DATA_DIR, 'methylation', 'GSE92462_450K')
    beta_dir = os.path.join(base_dir, 'beta')
    meta_fn = os.path.join(base_dir, 'sources.csv')
    return IlluminaHumanMethylationLoader(
        base_dir=beta_dir,
        meta_fn=meta_fn,
        batch_id="GSE92462_450K",
        norm_method=norm_method,
        samples=samples
    )


def gse110544(norm_method='raw', samples=None):
    base_dir = os.path.join(DATA_DIR, 'methylation', 'GSE110544')
    beta_dir = os.path.join(base_dir, 'beta')
    meta_fn = os.path.join(base_dir, 'sources.csv')
    return IlluminaHumanMethylationLoader(
        base_dir=beta_dir,
        meta_fn=meta_fn,
        batch_id="GSE110544",
        norm_method=norm_method,
        samples=samples
    )


def gse60274(norm_method='raw', samples=None):
    base_dir = os.path.join(DATA_DIR, 'methylation', 'GSE60274')
    beta_dir = os.path.join(base_dir, 'beta')
    meta_fn = os.path.join(base_dir, 'sources.csv')
    return IlluminaHumanMethylationLoader(
        base_dir=beta_dir,
        meta_fn=meta_fn,
        batch_id="GSE60274",
        norm_method=norm_method,
        samples=samples
    )


def gse31848(norm_method='raw', samples=None):
    base_dir = os.path.join(DATA_DIR, 'methylation', 'GSE31848')
    beta_dir = os.path.join(base_dir, 'beta')
    meta_fn = os.path.join(base_dir, 'sources.csv')
    data_fn = os.path.join(beta_dir, 'beta_%s.csv.gz' % norm_method)
    return IlluminaHumanMethylationLoader(
        data_fn=data_fn,
        meta_fn=meta_fn,
        batch_id="GSE31848",
        norm_method=norm_method,
        samples=samples
    )


def gse38216(norm_method='bmiq', samples=None):
    base_dir = os.path.join(DATA_DIR, 'methylation', 'GSE38216')
    beta_dir = os.path.join(base_dir, 'beta')
    meta_fn = os.path.join(base_dir, 'sources.csv')
    return IlluminaHumanMethylationLoader(
        base_dir=beta_dir,
        meta_fn=meta_fn,
        batch_id="GSE38216",
        norm_method=norm_method,
        samples=samples
    )


def gse67283(norm_method='bmiq', samples=None):
    base_dir = os.path.join(DATA_DIR, 'methylation', 'GSE67283')
    beta_dir = os.path.join(base_dir, 'beta')
    meta_fn = os.path.join(base_dir, 'sources.csv')
    return IlluminaHumanMethylationLoader(
        base_dir=beta_dir,
        meta_fn=meta_fn,
        batch_id="GSE67283",
        norm_method=norm_method,
        samples=samples
    )


def gse65214(norm_method='bmiq', samples=None):
    base_dir = os.path.join(DATA_DIR, 'methylation', 'GSE65214')
    beta_dir = os.path.join(base_dir, 'beta')
    meta_fn = os.path.join(base_dir, 'sources.csv')
    return IlluminaHumanMethylationLoader(
        base_dir=beta_dir,
        meta_fn=meta_fn,
        batch_id="GSE65214",
        norm_method=norm_method,
        samples = samples
    )


def encode_epic(norm_method='bmiq', samples=None):
    base_dir = os.path.join(DATA_DIR, 'methylation', 'ENCODE_EPIC')
    beta_dir = os.path.join(base_dir, 'beta')
    meta_fn = os.path.join(base_dir, 'sources.csv')
    return IlluminaHumanMethylationLoader(
        base_dir=beta_dir,
        meta_fn=meta_fn,
        batch_id="Encode EPIC",
        norm_method=norm_method,
        samples=samples
    )


def encode_450k(norm_method='bmiq', samples=None):
    base_dir = os.path.join(DATA_DIR, 'methylation', 'ENCODE_450k')
    beta_dir = os.path.join(base_dir, 'beta')
    meta_fn = os.path.join(base_dir, 'sources.csv')
    return IlluminaHumanMethylationLoader(
        base_dir=beta_dir,
        meta_fn=meta_fn,
        batch_id="Encode 450k",
        norm_method=norm_method,
        samples=samples
    )


def hipsci(norm_method='bmiq', array_type='all', n_sample=None):
    """
    Load HipSci methylation array data.
    :param norm_method:
    :param n_sample: If supplied, use this to limit the number of samples loaded.
    :return:
    """
    if array_type.lower() not in {'all', '450k', 'epic'}:
        raise AttributeError("array_type %s is not supported" % array_type)
    base_dir = os.path.join(DATA_DIR, 'methylation', 'hipsci_ipsc')
    beta_fn = os.path.join(base_dir, 'beta', array_type.lower(), 'beta_%s.csv.gz' % norm_method)
    if not os.path.isfile(beta_fn):
        raise AttributeError("Unable to find file %s, are you sure you chose a valid norm_method?" % beta_fn)
    meta_fn = os.path.join(base_dir, 'sources.csv')
    meta = pd.read_csv(meta_fn, header=0, index_col=0)

    if array_type != 'all':
        meta = meta.loc[meta.array_type.str.lower() == array_type]

    if n_sample is None:
        data = pd.read_csv(beta_fn, header=0, index_col=0)
        data = data.loc[:, meta.index]
    else:
        usecols = meta.index[:n_sample]
        data = pd.read_csv(beta_fn, header=0, index_col=None, usecols=usecols)
        row_names = pd.read_csv(beta_fn, header=0, index_col=0, usecols=[0])
        data.index = row_names.index
        # not sure if this is necessary
        data = data.loc[:, usecols]
        meta = meta.loc[usecols]

    if array_type == 'all':
        meta.insert(1, 'batch', 'HipSci')
        batch_id = 'HipSci'
    elif array_type == 'epic':
        meta.insert(1, 'batch', 'HipSci (EPIC)')
        batch_id = 'HipSci (EPIC)'
    elif array_type == '450k':
        meta.insert(1, 'batch', 'HipSci (450K)')
        batch_id = 'HipSci (450K)'
    else:
        raise AttributeError("array_type %s is not supported" % array_type)
    data = data.dropna().astype(float)

    class HipsciMethylationLoader(object):
        extra_df_attributes = tuple()
        tax_id = 9606
        row_indexed = True
        meta_is_linked = True

    obj = HipsciMethylationLoader()
    obj.data = data
    obj.meta = meta
    obj.batch_id = batch_id

    return obj

    # return meta, data