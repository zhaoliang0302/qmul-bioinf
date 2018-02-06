from load_data import loader
import pandas as pd
import os
from settings import GIT_LFS_DATA_DIR, DATA_DIR_NON_GIT
from utils.log import get_console_logger
from utils import setops


NORM_METHODS = {
    None,
    'raw',
    'bmiq',
    'swan',
    'pbc',
    'funnorm'
}

project_dirs = {
    "2016-06-10_brandner": os.path.join(DATA_DIR_NON_GIT, 'methylation', '2016-06-10_brandner'),
    "2016-09-21_dutt": os.path.join(DATA_DIR_NON_GIT, 'methylation', '2016-09-21_dutt'),
    "2016-12-19_ucl_genomics": os.path.join(DATA_DIR_NON_GIT, 'methylation', '2016-12-19_ucl_genomics'),
    "2017-01-17_brandner": os.path.join(DATA_DIR_NON_GIT, 'methylation', '2017-01-17_brandner'),
    "2017-02-09_brandner": os.path.join(DATA_DIR_NON_GIT, 'methylation', '2017-02-09_brandner'),
    "2017-05-12": os.path.join(DATA_DIR_NON_GIT, 'methylation', '2017-05-12'),
    "2017-08-23": os.path.join(DATA_DIR_NON_GIT, 'methylation', '2017-08-23'),
    "2017-09-19": os.path.join(DATA_DIR_NON_GIT, 'methylation', '2017-09-19'),
    "2018-01-12": os.path.join(DATA_DIR_NON_GIT, 'methylation', '2018-01-12'),
}

PATIENT_LOOKUP_FFPE = {}  # TODO?

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
    ],
    '019': [
        ('GBM019_P4', '2016-12-19_ucl_genomics'),
        ('GBM019_P3n6', "2017-09-19"),
        ('DURA019_NSC_N8C_P2', '2016-12-19_ucl_genomics'),
        ('DURA019_NSC_N5C1_P2', '2018-01-12'),
        ('DURA019_FB_P7', '2018-01-12')
    ],
    '026': [
        ('GBM026_P8', '2016-12-19_ucl_genomics'),
        ('GBM026_P3n4', '2017-05-12'),
        ('DURA026_NSC_N31D_P5', '2016-12-19_ucl_genomics'),
    ],
    '030': [
        ('GBM030_P9', "2017-09-19"),
        ('GBM030_P5', '2017-05-12'),
        ('DURA030_NSC_N16B6_P1', '2017-05-12'),
        ('DURA030_NSC_N9_P2', '2018-01-12'),
        ('DURA030_FB_P8', '2018-01-12'),
    ],
    '031': [
        ('GBM031_P7', "2017-09-19"),
        ('GBM031_P4', '2016-12-19_ucl_genomics'),
        ('DURA031_NSC_N44B_P2', '2016-12-19_ucl_genomics'),
        ('DURA031_NSC_N44F_P3', '2018-01-12'),
        ('DURA031_FB_P7', '2018-01-12'),
    ],
    '044': [
        ('GBM044_P4', '2017-05-12'),
        ('GBM044_P8', '2017-05-12'),
        ('DURA044_NSC_N17_P3', '2017-05-12'),
        ('DURA044_NSC_N8_P2', '2017-05-12'),
    ],
    '049': [
        ('GBM049_P4', "2017-08-23"),
        ('GBM049_P6', "2017-08-23"),
        ('DURA049_NSC_N19_P4', "2017-08-23"),
        ('DURA049_NSC_N5_P2', "2017-08-23"),
        ('DURA049_IPSC_ N5_P10', '2018-01-12'),
    ],
    '050': [
        ('GBM050_P7n8', "2017-08-23"),
        ('GBM050_P9', "2017-08-23"),
        ('DURA050_NSC_N12_P3', "2017-08-23"),
        ('DURA050_NSC_N16_P4', "2017-08-23"),
        ('DURA050_IPSC_N12_P5', "2018-01-12"),
        ('DURA050_FB_P7', "2018-01-12"),
    ],
    '052': [
        ('GBM052_P6n7', "2017-09-19"),
        ('GBM052_P4n5', "2017-09-19"),
        ('DURA052_NSC_N4_P3', "2017-09-19"),
        ('DURA052_NSC_N5_P2', "2017-09-19"),
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
    ],
    'GIBCO': [
        ('GIBCONSC_P4', '2017-05-12'),
    ]
}


def load_illumina_methylationepic_annotation(split_genes=True):
    """

    :param split_genes: If True (default), the RefGene name column will be split into a set - useful for
    many downstream applications
    :return:
    """
    fn = os.path.join(GIT_LFS_DATA_DIR, 'annotation', 'methylation', 'infinium-methylationepic-v1-0-b3-manifest-file-csv.zip')
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

    if split_genes:
        dat.loc[:, 'UCSC_RefGene_Name'] = \
            dat.UCSC_RefGene_Name.str.split(';').apply(lambda x: set(x) if isinstance(x, list) else None)

    # TODO: correct gene symbols - look up what these should be - some kind of Excel fail?
    ['1-Mar',
     '1-Sep',
     '10-Mar',
     '11-Mar',
     '11-Sep',
     '13-Sep',
     '2-Mar',
     '3-Mar',
     '4-Mar',
     '5-Sep',
     '6-Mar',
     '7-Mar',
     '8-Mar',
     '9-Sep',
     ]

    return dat


def load_illumina_methylation450_annotation():
    fn = os.path.join(GIT_LFS_DATA_DIR, 'annotation', 'methylation', 'GPL13534_HumanMethylation450_15017482_v.1.1.csv.gz')
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
    def __init__(self, norm_method='swan', *args, **kwargs):
        self.norm_method = norm_method
        super(IlluminaHumanMethylationLoader, self).__init__(*args, **kwargs)

    def get_inputs(self):
        if self.norm_method is None:
            self.input_files = os.path.join(self.base_dir, 'beta_raw.csv.gz')
        elif self.norm_method.lower() in NORM_METHODS:
            self.input_files = os.path.join(self.base_dir, 'beta_%s.csv.gz' % self.norm_method.lower())
        else:
            raise AttributeError("Unrecognised norm_method %s. Options are (%s)." % (
                self.norm_method,
                ', '.join(str(t) for t in NORM_METHODS)
            ))

    def load_one_file(self, fn):
        return pd.read_csv(fn, header=0, index_col=0)


def load_by_patient(
        patient_ids,
        type='cell_culture',
        norm_method='swan',
        include_control=True
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
        patient_ids = [t if isinstance(t, str) else ('%03d' % t) for t in patient_ids]
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
            by_loader.setdefault(ldr, []).append(s)
            sample_order.append(s)

    objs = []
    for ldr, samples in by_loader.items():
        base_dir = os.path.join(project_dirs[ldr], 'beta')
        meta_fn = os.path.join(project_dirs[ldr], 'sources.csv')

        objs.append(
            cls(
                base_dir=base_dir,
                meta_fn=meta_fn,
                samples=samples,
                norm_method=norm_method,
                batch_id=ldr
            )
        )

    if len(objs) > 1:
        res = loader.MultipleBatchLoader(objs)
    else:
        res = objs[0]

    # apply original ordering
    res.meta = res.meta.loc[sample_order]
    res.data = res.data.loc[:, res.meta.index]

    return res
