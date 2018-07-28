import pandas as pd
from utils.david import client
from ast import literal_eval as make_tuple
from settings import OUTPUT_DIR
import os
import requests


if __name__ == "__main__":
    indir = os.path.join(OUTPUT_DIR, 'assess_reprogramming_dmr')
    pids = ['019', '030', '031', '050', '054']
    api_url = "http://david.abcc.ncifcrf.gov/api.jsp?type={type}&ids={ids}&tool={tool}&annot={annot}"

    for pid in pids:
    # pid = '019'

        fn = os.path.join(indir, '%s_residual_hypo_dmrs.csv' % pid)

        df = pd.read_csv(fn, header=0, index_col=0)

        # alphabetically sorted list of uniquely deregulated genes
        genes = sorted(set(df.genes.apply(make_tuple).sum()))

        print pid
        print '\n'.join(genes)

        # cl = client.WSDLApi()
        # cl.introspection()

        annot_list = [
            'GOTERM_BP_DIRECT',  # biological process
            'KEGG_PATHWAY',
            'OMIM_DISEASE'
        ]
        david_tool = 'chartReport'

        gene_str = ','.join(genes)
        id_type= 'OFFICIAL_GENE_SYMBOL'
        # print cl.client.service.addList(inputIds, idType, listName, listType)

        for annot in annot_list:
            this_url = api_url.format(
                type=id_type,
                ids=gene_str,
                tool=david_tool,
                annot=annot
            )
            print "*** PID %s, annotation %s ***" % (pid, annot)
            print this_url


