# Marino Lab processing pipelines for Next Gen Seq data
_Author: Gabriel Rosser_
_Last updated: 25/04/2018_

## Preamble
All `commands` can be run at a Linux terminal, providing the appropriate software has been installed and - in the case of Apocrita - `module load` has been called.

I've created some Python classes to automate running most of pipelines locally or on Apocrita. On Apocrita, jobs are always submitted in an array. The Python scripts are purely a convenience: it is always possible to generate a script and associated parameters file.

I organise files as follows. 

- Raw data (fastq files) are located in `<data_dir>/<experiment_type>/<project_id>/<lane_id>`.
- Where processing is lane-specific, files are located in the lane subdirectory, e.g. `<data_dir>/<experiment_type>/<project_id>/<lane_id>/trim_galore/`.
- Where processing combines multiple lanes, the files are located in a subdirectory within the project directory, e.g. `<data_dir>/<experiment_type>/<project_id>/human/star_alignment/`.
- Where processing is reference-specific, files are located in a subdirectory naming the reference, e.g. `<data_dir>/<experiment_type>/<project_id>/<lane_id>/mouse/bwa_alignment` (lane-specific) or `<data_dir>/<experiment_type>/<project_id>/mouse/bwa_alignment` (combined lanes).

## Downloading data

### Wellcome Trust Centre for Human Genetics (WTCHG)

The WTCHG always serves data over ftp. The ftp server requires a username and password, which are supplied in the URL they send by email. To download the entire directory from a URL, run 

```bash
wget -nH -np -r ftp://<username>:<password>@bsg-ftp.well.ox.ac.uk/<run_id>
```

The entire URL can just be copied from the email. This will create a directory called `run_id`.

The WTCHG facility typically run an alignment step on the raw fastq files (generating a BAM file), however this is not always generated following an appropriate pipeline. For example, the process for RNA-Seq does not used a gapped aligner. In practice, it is therefore often desirable to skip downloading these large and useless BAM files. This is achieved by adding the following flags to the `wget` call: `--reject bam,bai`.

### Barts Genome Centre

Barts Genome Centre transfer data using [Illumina's BaseSpace](https://basespace.illumina.com/) web service. It is possible to download data directly from the web interface, but this is not practical for large runs and not straightforward to run from Apocrita. Instead, I have used the [BaseSpace BaseMount](https://basemount.basespace.illumina.com/) tool (Linux only), which allows you to browse and copy files from BaseSpace as if they were mounted on your local machine.

## FastQC

Always run `fastqc` on the raw fastq files first. If desirable, the reports can be aggregated into a single summary HTML file using `multiqc`.

On Apocrita: `module load fastqc`. MultiQC should be installed in a Python virtual environment.

```bash
fastqc --noextract -t <num_threads> -o <output_dir> <file.fastq.gz>
```
To automate on Apocrita, the following will run `fastqc` on  all fastq files in the current directory: 
```bash
python bioinf/pyscript/apocrita/fastqc.py
```

## Small RNA-Seq
### Typical experimental parameters
- 51 bp reads
- Single end
- 30mi reads per sample
- Split over a large number of lanes (6 - 8)?
- WTCHG usually run their own trim - align - feature count pipeline, which is in a subdirectory `miRNA`. I don't trust it, but keep it for reference.
### Process
This has not been used enough to be fully automated. First load modules if on Apocrita:
```bash
module load trimgalore
module load bwa
module load samtools
```

sRNA-Seq reads always need trimming to remove adapters:
```bash
trimgalore --length 15  -o <output_dir> file.fastq.gz
```

The argument `--length 15` lowers the default minimum read length from 20bp to 15bp. The `trim_galore` documentation refers to a sRNA-Seq-specific argument, `--small_rna`. I have tested this found it resulted in the wrong adapter sequence being used.

The files output by `trim_galore` have the naming convention `original-name_trimmed.fq.gz`. This is a bit inconvenient for the rest of my scripts, so I prefer to rename them. This snippet works for `.fastq` and `fastq.gz` files:

```bash
for i in *_trimmed.fq.gz; do 
	nn=$(echo $i | sed 's/_trimmed.fq/.fastq/')
	CMD="mv $i $nn"
	echo $CMD
	eval $CMD
done
```


I have created a file to automate running `trim_galore` on all valid files in the current directory. This also handles renaming and is called as follows:
```bash
python bioinf/pyscript/apocrita/trim_galore_se.py --length 15  # for SE reads
```

Now we can align using an **ungapped** aligner like `bwa`. WE should be fairly strict about disallowing gaps and mismatches.

Before we can run `bwa`, we need to build an indexed reference genome. Start with a reference file (in fasta format) - I have been using Ensembl GrCh38 for all human work:
```bash
bwa index /path/to/reference.fa
```
This dumps some extra files in the same directory as the `.fa` file. Now we can use this to align the raw sequencing data:
```bash
bwa aln -n 1 -o 0 -e 0 -k 1 -t 2 /path/to/reference.fa reads.fastq.gz > reads.sai
bwa samse /path/to/reference.fa reads.fastq.gz reads.sai reads.fastq.gz | samtools view -hb - > reads.bam
samtools sort -@ <num_threads> reads.bam > reads.sorted.bam
rm reads.sai reads.bam
```

This is implemented in a Python script:
```bash
python bioinf/pyscript/apocrita/bwa_se.py -i /path/to/reference.fa -p <num_threads> --srna -o <output_dir>
```
Running this script from within a directory will submit an alignment job for every fastq and fastq.gz file in that directory.

At present, I run this separately for each lane. This means we end up with `n` reads.sorted.bam files (where `n` is the number of lanes) for every sample. We need to merge these at the end. For WTCHG,  the common ID linking each sample is the final number (e.g. `WTCHG_xxxxxx_101.bam`, where `xxxxxx` is specific to the lane and 101 is the sample ID). I'm assuming that you have a subdirectory `/human/bwa_alignment` in the project directory, a subdirectory `trim_galore/human/bwa_alignment` in each of the lane subdirectories and that the lane IDs all start with the number 1:

```bash
arr=(101 102 ... 201) # all of the sample IDs
for i in "${arr[@]}"; do
	echo $i
	samtools merge human/bwa_alignment/$i.sorted.bam 1*/trim_galore/human/bwa_alignment/*_$i.sorted.bam
done
```

This generates sorted bam files (by coordinate), as the output name suggests.

Since BWA is light on logging, we might want to generate our own reports about the alignment success:

```bash
samtools flagstat <alignment.bam>
```

Now we need to run `featureCounts` using a `miRBase` annotation file to count against known miRNA transcripts. The annotation file can be obtained in `.gff3` format from the [site](http://www.mirbase.org/ftp.shtml). I found I had to convert this to `.gtf` first, which can be achieved using the R package `rtracklayer`:
```r
library(rtracklayer)
gff <- import("path/to/file.gff3")
export(gff, "path/to/file.gtf", "gtf")
```
The chromosome names in this `gtf` file _must_ match those in the original reference fasta sequence (and the version must be the same). If you are using an Ensembl reference, you may need to rename chromosomes in the `gtf` file to remove the prefix `chr`:
```bash
sed 's/chr\([1-9XY]*\)/\1/' annotation.chr.gtf > annotation.gtf
```
Finally, we run `featureCounts`:
```bash
featureCounts -a path/to/annotation.gtf -o featurecounts_output -t miRNA -T <num_threads> -g ID sample1.bam sample2.bam ... sampleN.bam
```
Note that this can accept a list of bam files separated by a space. If run in this way, all the results are included in a single output file. A summary file, named `featurecounts_output.summary` gives an overview of the number of reads assigned to features.

**NB** The default operation mode in `featureCounts` assumes that the reads are *unstranded*, which they probably are in single read mode(?). However, if using this for paired end data an additional parameter `-s 0/1/2` allows different configurations.

## Reduced representation bisulphite sequencing (RRBS-Seq)
### Typical experimental parameters
- 76 bp reads
- Paired end
- 30mi reads per sample
- Split over several lanes (4 in last batch)
- Only raw reads received
### Process
This pipeline has only been applied twice, so it is only partially automated. First load modules if on Apocrita:
```bash
module load trimgalore
module load bismark
module load samtools
```

The raw reads may not have a very high adapter content, but we need to trim them anyway because otherwise the first few bases introduce a very large bias in the inferred methylation state. `trim_galore` has a preset for this operation (--rrbs):

```bash
trim_galore -o <output_dir> read_1.fastq.gz read_2.fastq.gz --rrbs --paired
```

For convenience, it is possible to supply multiple fastq filenames to this command, space separated in the order `lane1_1 lane1_2 lane2_1 lane2_2` etc.

As for other pipelines, it is convenient to rename the outputs here so that they have the extension `.fastq.gz`:

```bash
for i in *.fq.gz; do 
	nn=$(echo $i | sed 's/_val_[12].fq/.fastq/')
	CMD="mv $i $nn"
	echo $CMD
	eval $CMD
done
```

The trimming and renaming operations are automated in a `python` script that will run the process on all PE `fastq.gz` files in the directory:
```bash
python bioinf/pyscript/apocrita/trim_galore_pe.py --rrbs
```

Now we run `bismark`, an application developed for working with bisulphite sequencing data. There are three stages in the standard process: prepare the reference (run only once), alignment (that uses `bowtie2` behind the scenes), and extracting methylation data. 

Preparing the reference:
```bash
bismark_genome_preparation path/to/fasta_dir
```

Note that we point to the containing directory, not the fasta file itself. This will generate a subdirectory with the name `Bisulfite_Genome` in the fasta directory.

Aligning to the reference is performed as follows. This can be passed fastq files from multiple lanes in one go, in which case it works on all of them to generate a single bam file.

```bash
bismark path/to/fasta_dir -o <output_dir> -p <num_threads> -B <output_prefix> -1 /path/to/lane_1/read_1.fastq[.gz],/path/to/lane2/read_1.fastq[.gz],... -2 /path/to/lane_1/read_2.fastq[.gz],/path/to/lane_2/read_2.fastq[.gz],...
```

The output files for each pair of reads will be located in a subdirectory, `output_dir/output_prefix`. Each subdirectory will contain a bam file. 

**Warning: I have experienced problems with this approach, in which `bismark` seems to generate a bam file for just one of the lanes, despite reporting that it will use all of them. For this reason, I recommend running it separately on each lane.**

Finally, we will extract the actual methylation state estimates:

```bash
bismark_methylation_extractor --parallel <num_threads> --no_header --gzip --bedGraph sample1.bam
```

This generates a number of files in the same directory as the bam file. The most useful is probably the file with the extension `.bismark.cov`, which lists the coverage and % methylation of every CpG site.

Also important is the `M-bias.txt` file, which tells us whether we should have trimmed more bases from the ends of the reads. A nice way to visualise these is using `multiqc`. Run the following in the output directory:

```bash
multiqc .
```

And open `multicq_report.html` in a browser.

It's a bit annoying that we only find out about problems at this stage, because it leaves us with no option but to re-run the final step, ignoring reads from relevant ends. For example, I found that read 2 was very biased at the first and final two bp. I therefore re-ran with

```bash
bismark_methylation_extractor --parallel <num_threads> --no_header --gzip --bedGraph --ignore_r2 2 --ignore_3prime_r2 2 sample1.bam
```

The two steps (`bismark` followed by `bismark_methylation_extractor`) are automated in the following python scripts. This one to run on individual lanes (recommended):

```bash
python bioinf/pyscript/apocrita/bismark_pe.py --ignore_3prime 2 --ignore_3prime_r2 4 -i /path/to/fasta
```

or this one to run on multiple lanes in one shot (see my earlier caveat):

```bash
python bioinf/pyscript/apocrita/bismark_multilane_pe.py --ignore_3prime 2 --ignore_3prime_r2 4 -i /path/to/fasta
```

The path to the fasta files points to a *directory* not a file. This script also accepts the optional arguments `--ignore <int>` and `--ignore_r2 <int>` to ignore the 5 prime ends or read 1 and 2, respectively. 

If only the second step (`bismark_methylation_extractor`) is required, this can be specified using the argument `--extract_only`, in which case it is assumed that bam files have already been generated.

#### Optional: merge bams

If `bismark` was run on each lane separately, at this point we can merge bams corresponding to multiple lanes of the same run. `samtools cat` is a quick option that preserves the order.

```bash
samtools cat sample1_lane1.bam sample1_lane2.bam ... > sample1.bam
```

Alternatively, `samtools merge -n` sorts by read name, but this isn't necessary. **NB**: `samtools merge` without the `-n` flag will result in an error from the final step when we run `bismark_methylation_extractor`. These operations have been automated for Barts Genome Centre data in the following `python` scripts:

```bash
python bioinf/pyscript/apocrita/cat_bams_barts_multilane.py /path/to/bam/top_level
python bioinf/pyscript/apocrita/merge_bam_barts_multilane.py /path/to/bam/top_level -n
```

The path above just needs to point to the top level directory containing all bam files. The files themselves can be located in subdirectories, as the script searches exhaustively. However, all bam files in the path specified must be compatible with the naming scheme: `<sample_name>_L<lane_number>[_pe].bam`.


## ChIP-Seq
### Typical experimental parameters
- 75 bp reads
- Paired end
- 30mi reads per sample
- Split over a number of lanes
- WTCHG usually run their own pipeline on the data, mainly for QC purposes. However, they use an old reference so I prefer to re-run everything from scratch.
- Typically, each sample is ChIPped for one or more markers and also processed with no immunoprecipitation step (known as _input_, or _control_). The input sample is used as a negative control; any peaks identified here are simply due to the inherent biases of the process.

### Process
This has not been used enough to be fully automated. First load modules if on Apocrita:
```bash
module load bowtie2
```
Our first step is to align the data to the reference genome. This should be carried out with an ungapped aligner, as the input sample is DNA and shouldn't have splice junctions. I use `bowtie2` for this purpose; it is also possible to use `bwa` and probably others. `bowtie2` outputs a SAM file by default, but I prefer to convert this to BAM directly to save space and time. I also sort it, as this is required by various downstream processes:
```bash
bowtie2 -p <num_threads> -x path/to/bt2_index \
-1 /path/to/sample_1_read_1_lane_a.fastq.gz,/path/to/sample_1_read_1_lane_b.fastq.gz,... \
-2 /path/to/sample_1_read_2_lane_a.fastq.gz,/path/to/sample_1_read_2_lane_b.fastq.gz,... \
| samtools view -b > sample_1.bam
samtools sort -@ <num_threads> sample_1.bam > sample_1.sorted.bam
rm sample_1.bam
```
We should now have aligned BAM files. 

Based on Rob Lowe's suggestion, there are a number of analyses that can be carried out directly on the BAM files, for example using `samtools depth` to get coverage around TSSs. These are not detailed here, as they are quite involved. Scripts can be found at `bioinf/scripts/chipseq/{tss_from_gtf.py,chipseq_tss_enrichment.py}`.

We can now call peaks using the BAM files. This process detects peaks that are statistically significantly enriched in a ChIP sample versus the corresponding input sample. It is also possible to call peaks without any input sample, but this is less reliable. There are many published and commercial software packages for peak calling. A well-established method is called [`MACS`](https://github.com/taoliu/MACS) (NB. version 2 supercedes the original release). This is easy to install as a `python` package. The syntax (using default parameters) is as follows:
```bash
macs2 callpeak -t /path/to/target.bam [-z /path/to/input.bam] -n <output_filestem> --outdir /path/to/output_dir/ -B -g 3.0e9 -f BAMPE
```
Note that the control sample isn't required, but should be supplied with the `-z` argument if it is available. Other arguments:
- `-B` requests the output of a `bedgraph` file for both the target and control (if supplied). This will be used downstream to generate an enrichment track for visualisation purposes. 
- `-g` specifies the effective size of the reference genome. The default option here is for hg19 (2.7e9), but the Ensembl reference is slightly larger - hence specifying it as an input. In practice, it probably makes no real difference, but would certainly do so for other species.
- `-f` tells `macs2` the format of the input file(s) - paired end BAM.

There are many other options that can be supplied to `macs callpeaks` (see [the website](https://github.com/taoliu/MACS) the website for details). One significant option is `--broad`, which results in multiple narrow peaks being merged to generate broad peaks. I'm still working on the optimal parameters for different histone marks and will put a table in here when I have decided.

This has been automated in a Python script that runs it on all BAMs in the directory (note that you still have to specify variables)
```bash
python bioinf/pyscript/apocrita/macs2_callpeaks.py -c /path/to.config_file.csv -f BAMPE -g 3.0e9 --out_dir /path/to/out_dir -B [--broad]
```
All the arguments have the same syntax as the original `macs` call, except for `-c`, which specifies the path to a CSV file that specifies the comparisons we want to make. This file _must_ have the following columns
- `name` (used for the `-n` argument to name output files)
- `target` (filename of the target BAM)
- `control` (filename of the control BAM, can be left blank if not present)
Any other arguments supplied are just passed on to `macs`.


The `macs callpeaks` routine generates several output files:
- <sample_name\>_peaks.xls
- <sample_name\>_peaks.narrowPeak (default) or broadPeak (`--broad`)
- <sample_name\>_control_lambda.bdg (if control supplied)
- <sample_name\>_treat_pileup.bdg

The `Excel` file is actually a CSV (weird choice of naming convention). It's convenient to rename these files:
```bash
for i in *.xls; do
	nn=$(echo $i | sed 's/xls$/csv/')
	mv $i $nn
done
```

The `.narrowPeak` and `.broadPeak` files are explained on the website, but are basically in the BED format.

The `.bdg` files are in `bedgraph` format and can be used to generate an enrichment trace, which we can use for visualisation. This is essentially a plot that quantifies the enrichment of the ChIPped sample over the control. We do this as follows:
```bash
macs2 bdgcmp -t /path/to/target.bdg -c /path/to.control.bdg --outdir /path/to/out_dir --o-prefix <output_filestem> -m <method>
```
where `<method\>` is one of the options given when you run `macs bdgcmp -h`. I use `qpois`, which means enrichment is given as `-log10(adj Pval).`

This has also beenn a Python script, which runs it on all valid pairs of `.bdg` files:
```bash
python bioinf/pyscript/apocrita/macs2_bdgcmp.py -m <method>
```
The `macs bdgcmp` routine generates a single bedgraph file with the name `output_filestem_method.bdg`.

We can visualise the resulting enrichment trace on IGV, but we get much better performance if we first convert it to the `bigwig` (binary) format. this can be achieved using the UCSC tool `wigToBigWig`, available in a precompiled binary [here](http://hgdownload.soe.ucsc.edu/admin/exe/linux.x86_64/). Ensuring this file is executable and available on the `PATH` environment variable, we can use the following to convert all the relevant `.bdg` files to `.bw`:
```bash
for i in *_qpois.bdg; do 
	outfn=$(echo $i | sed 's/bdg$/bw/')
	CMD="wigToBigWig $i /path/to/reference.fa.fai $outfn"
	echo $CMD
	eval $CMD
done
```
where we need to pass in the full path to a fasta index file (generate this using `samtools faidx` if not available already).

#### Two notes on bedgraph files
1) These files are very inefficient and easily compressed. If storing them on Apocrita, I recommend gzipping them. The python script `macs2_bdgcmp.py` supports gzipped inputs.
2) The Ensembl reference I use names chromosomes by letter or number _only_: 1, X, etc., while the related hg38 genome used by some browsers such as WashU names them with the prefix `chr`: chr1, chrX, etc. It is therefore necessary to rename chromosomes in bed and bedgraph files before attempting to import them into WashU. An example script to perform this operation on the `.narrowPeak` files:
```bash
for i in *_peaks.narrowPeak; do 
	nn=$(echo $i | sed 's/\.narrowPeak/.chr.narrowPeak.bed/')
	echo "$i -> $nn"
	cat $i | sed 's/^/chr/' > $nn
done
```
A similar process can be carried out as required on the .bdg files.
