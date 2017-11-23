#!/usr/bin/env python
import os
import re
import subprocess
import argparse
import sys
import datetime
import csv

# add root of project dir to the path
sys.path.append(os.path.dirname(__file__) + '/../../')

from utils import sge, output


if __name__ == "__main__":
    now_str = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    parser = argparse.ArgumentParser()
    optional = parser._action_groups.pop()
    required = parser.add_argument_group('required arguments')

    optional.add_argument("--read_dir", help="Directory containing reads", default='./')
    optional.add_argument("-o", "--out_dir", help="Output directory")
    optional.add_argument("-p", "--threads", help="Number of threads", default='1')
    optional.add_argument("--library_type", help="Library type", default='ISR')

    required.add_argument("-i", "--index_dir", help="Directory of pre-computed Salmon index", required=True)

    # all extra args got to extra
    args, extra = parser.parse_known_args()

    if args.out_dir is None:
        # if no output_dir specified, create one in the reads directory
        args.out_dir = os.path.join(args.read_dir, 'salmon')
        if not os.path.exists(args.out_dir):
            os.makedirs(args.out_dir)
        sys.stderr.write("Output directory not specified, using default: %s\n" % args.out_dir)

    obj = sge.SalmonIlluminaPESgeJob(*extra, **args.__dict__)
    obj.create_submission_script()
    obj.submit()