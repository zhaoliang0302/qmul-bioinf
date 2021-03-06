import multiprocessing as mp
import os

import pandas as pd

from microarray.process import aggregate_by_probe_set
from settings import DATA_DIR
from utils.log import get_console_logger

logger = get_console_logger(__name__)
MICROARRAY_DIR = os.path.join(DATA_DIR, 'microarray', 'allen_human_brain_atlas')
RNASEQ_DIR = os.path.join(DATA_DIR, 'rnaseq', 'allen_human_brain_atlas')

# structure IDs
CEREBELLUM_STRUCT_ID = 4696

def get_structure_ids_by_parent(parent_id):
    """
    Recurse through the DataFrame ontol, retrieving structure IDs that are directly beneath parent_id in the
    nested hierarchy
    :param parent_id: The parent structure ID
    :return: set of structure IDs
    """
    # load ontology library
    ontol_fn = os.path.join(MICROARRAY_DIR, 'Ontology.csv')
    ontol = pd.read_csv(ontol_fn, index_col=0)
    if parent_id is None:
        # return everything
        return set(ontol.index)

    struct_ids = {parent_id}
    this_set = {parent_id}
    while True:
        filt = ontol[ontol.parent_structure_id.isin(this_set)]
        if filt.empty:
            break
        else:
            struct_ids.update(filt.index)
            this_set = set(filt.index)
    return struct_ids



def load_one_microarray_donor(
        donor_num,
        probes,
        struct_ids=None,
        mask_nonsig=False
):
    INDIR = os.path.join(MICROARRAY_DIR, 'microarray')
    indir = os.path.join(INDIR, "donor%d" % donor_num)
    expre_fn = os.path.join(indir, 'MicroarrayExpression.csv.gz')
    sampl_fn = os.path.join(indir, 'SampleAnnot.csv.gz')
    pacal_fn = os.path.join(indir, 'PACall.csv.gz')

    sampl = pd.read_csv(sampl_fn)

    # set sample IDs
    sampl_idx = pd.Index(['%d_%d' % (donor_num, i) for i in range(sampl.shape[0])])
    sampl.index = sampl_idx

    expre = pd.read_csv(expre_fn, header=None, index_col=0)
    expre.columns = sampl_idx
    # filter sample annotation and expression for recognized probes
    expre = expre.loc[probes.index]

    if mask_nonsig:
        pacal = pd.read_csv(pacal_fn, header=None, index_col=0).astype(bool)
        pacal.columns = sampl_idx
        pacal = pacal.loc[probes.index]
        # filter expression by PA call
        # this replaces all non-significant results with NaN
        expre = expre[pacal]

    if struct_ids is not None:
        # filter sample annotation by ontology
        sampl_idx = sampl[sampl.structure_id.isin(struct_ids)].index
        expre = expre[sampl_idx]
        sampl = sampl.loc[sampl_idx]

    sampl['donor_id'] = donor_num

    return expre, sampl



def load_microarray_reference_data(
        parent_struct_id=None,
        mask_nonsig=False,
        ann_field=('entrez_id', 'gene_symbol'),
        agg_method=None):
    """
    Load and process the Allen microarray data from the raw source format residing on disk.
    :param parent_struct_id: If supplied, restrict to this structure and its children. e.g. cerebellum is 4696
    :param mask_nonsig: If True, replace any values considered to be below statistical significance with NA
    :param ann_field: If supplied, annotate probe sets with this attribute from the probes annotation file. Examples:
        'entrez_id' (Entrez gene ID)
        'gene_symbol' (approved gene symbol)
    If None, no annotation is added.
    If an iterable, multiple annotation columns are added.
    This must be a single string if agg_method is supplied, as it is the field used for aggregation.
    :param agg_method: This string specifies the method used to aggregate over probe sets, grouping by the ann_field
    column.
    Options are None, 'min', 'max', 'mediam', 'mean'. If None, no aggregation is carried out.
    """
    # sanity check inputs
    if agg_method is not None:
        if hasattr(ann_field, '__iter__') or ann_field is None:
            raise ValueError("When agg_method is not None, ann_field must be a string.")

    DONOR_NUMBERS = [
        9861,
        10021,
        12876,
        14380,
        15496,
        15697
    ]

    # load probe library
    probe_fn = os.path.join(MICROARRAY_DIR, 'Probes.csv')
    probes = pd.read_csv(probe_fn, index_col=0)
    # keep only those probes with an Entrez ID
    probes = probes.dropna(axis=0, subset=['entrez_id'])

    struct_ids = get_structure_ids_by_parent(parent_struct_id)

    expression = pd.DataFrame()
    sample_meta = pd.DataFrame()

    p = mp.Pool()
    p_kwds = {'struct_ids': struct_ids if parent_struct_id else None, 'mask_nonsig': mask_nonsig}
    jobs = {}

    for dn in DONOR_NUMBERS:
        jobs[dn] = p.apply_async(load_one_microarray_donor, args=(dn, probes), kwds=p_kwds)
    p.close()

    for dn, j in jobs.items():
        logger.info("Processing donor %d", dn)
        expre, sampl = j.get(1e12)
        expression = pd.concat([expression, expre], axis=1)
        sample_meta = sample_meta.append(sampl)
        logger.info("Completed donor %d", dn)


    if ann_field is not None:
        # prepend gene symbol and entrez ID to the total expression dataframe
        expression = pd.concat([probes.loc[expression.index, ann_field], expression], axis=1)

    if agg_method is not None:
        # aggregate by the annotation field
        expression = aggregate_by_probe_set(expression, method=agg_method, groupby=ann_field)

    return expression, sample_meta


def cerebellum_microarray_reference_data(agg_field=None, agg_method=None):
    """
    Get the reference microarray data from the Allen Human Brain Atlas samples.
    :param agg_field: If supplied, this is a string referring to the field used to aggregate.
    :param agg_method: If supplied, this string refers to the method used to aggregate over agg_field
    """
    if (agg_method is not None and agg_field is None) or (agg_method is None and agg_field is not None):
        raise ValueError("Must supply either both agg_field and agg_method, or neither.")

    infile_meta = os.path.join(MICROARRAY_DIR, 'cerebellum_meta.csv')

    # form input filename for expression data
    if agg_field is None:
        infile_expr = os.path.join(MICROARRAY_DIR, 'cerebellum_expression.csv.gz')
    else:
        infile_expr = os.path.join(MICROARRAY_DIR, 'cerebellum_expression.by_%s.agg_%s.csv.gz' % (agg_field, agg_method))

    bload = True
    if not os.path.exists(infile_expr):
        logger.info("Unable to find pre-prepared CSV file %s. Recomputing.", infile_expr)
        bload = False
    if not os.path.exists(infile_meta):
        logger.info("Unable to find pre-prepared CSV file %s. Recomputing.", infile_meta)
        bload = False

    if bload:
        expr = pd.read_csv(infile_expr, index_col=0, header=0)
        meta = pd.read_csv(infile_meta, index_col=0, header=0)

    else:
        expr, meta = load_microarray_reference_data(
            parent_struct_id=CEREBELLUM_STRUCT_ID,
            ann_field=agg_field,
            agg_method=agg_method
        )
        logger.info("Saving expression results to %s", infile_expr)
        expr.to_csv(infile_expr, compression='gzip')

        logger.info("Saving meta info to %s", infile_meta)
        meta.to_csv(infile_meta)

    return expr, meta


def save_cerebellum_microarray_data_by_entrez_id(method='median'):
    """
    Convenience function since this dataset is required in R.
    :param method:
    :return:
    """
    expr, meta = cerebellum_microarray_reference_data(agg_field='entrez_id', agg_method=method)



def load_rnaseq_reference_data(
        parent_struct_id=None,
        units='counts',
):
    if units not in ('counts', 'tpm'):
        raise ValueError("Supported units are 'counts' and 'tpm'.")

    DONOR_NUMBERS = [
        9861,
        10021
    ]

    if parent_struct_id is None:
        struct_ids = None
    else:
        struct_ids = get_structure_ids_by_parent(parent_struct_id)

    # load gene library
    # unnecessary unless we want Entrez IDs
    # genes_fn = os.path.join(INDIR, 'Genes.csv')
    # genes = pd.read_csv(genes_fn, header=0, index_col=0)

    reads = pd.DataFrame()
    sample_meta = pd.DataFrame()

    for dn in DONOR_NUMBERS:
        logger.info("Processing donor %d", dn)
        this_dir = os.path.join(RNASEQ_DIR, "donor%d" % dn)
        if units == 'counts':
            dat_fn = os.path.join(this_dir, 'RNAseqCounts.csv.gz')
        else:
            dat_fn = os.path.join(this_dir, 'RNAseqTPM.csv.gz')

        sampl_fn = os.path.join(this_dir, 'SampleAnnot.csv.gz')


        sampl = pd.read_csv(sampl_fn)
        dat = pd.read_csv(dat_fn, header=None, index_col=0)

        # set sample IDs
        sampl_idx = pd.Index(['%d_%d' % (dn, i) for i in range(sampl.shape[0])])
        sampl.index = sampl_idx

        dat.columns = sampl_idx

        if struct_ids is not None:
            # filter sample annotation by ontology
            sampl_idx = sampl[sampl.ontology_structure_id.isin(struct_ids)].index
            dat = dat[sampl_idx]
            sampl = sampl.loc[sampl_idx]

        # concatenate along axis 1
        reads = pd.concat([reads, dat], axis=1)

        # add sample metadata to the list
        sampl['donor_id'] = dn
        sample_meta = sample_meta.append(sampl)

        logger.info("Completed donor %d", dn)

    return reads, sample_meta