#Pipeline for Identification of Guanosine Positions Erroneously Notated
#PIGPEN

import argparse
import subprocess
import os
import sys
from snps import getSNPs, recordSNPs
from maskpositions import readmaskbed
from getmismatches import iteratereads_pairedend, getmismatches
from assignreads_salmon import getpostmasterassignments, assigntotxs, collapsetogene, readspergene, writeOutput

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='                    ,-,-----,\n    PIGPEN     **** \\ \\ ),)`-\'\n              <`--\'> \\ \\` \n              /. . `-----,\n    OINC! >  (\'\')  ,      @~\n              `-._,  ___  /\n-|-|-|-|-|-|-|-| (( /  (( / -|-|-| \n|-|-|-|-|-|-|-|- \'\'\'   \'\'\' -|-|-|-\n-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|\n\n   Pipeline for Identification \n      Of Guanosine Positions\n       Erroneously Notated', formatter_class = argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--samplenames', type = str, help = 'Comma separated list of samples to quantify.', required = True)
    parser.add_argument('--controlsamples', type = str, help = 'Comma separated list of control samples (i.e. those where no *induced* conversions are expected). May be a subset of samplenames. Required if SNPs are to be considered.')
    parser.add_argument('--gff', type = str, help = 'Genome annotation in gff format.')
    parser.add_argument('--genomeFasta', type = str, help = 'Genome sequence in fasta format. Required if SNPs are to be considered.')
    parser.add_argument('--nproc', type = int, help = 'Number of processors to use. Default is 1.', default = 1)
    parser.add_argument('--useSNPs', action = 'store_true', help = 'Consider SNPs?')
    parser.add_argument('--maskbed', help = 'Optional. Bed file of positions to mask from analysis.', default = None)
    parser.add_argument('--SNPcoverage', type = int, help = 'Minimum coverage to call SNPs. Default = 20', default = 20)
    parser.add_argument('--SNPfreq', type = float, help = 'Minimum variant frequency to call SNPs. Default = 0.2', default = 0.2)
    parser.add_argument('--onlyConsiderOverlap', action = 'store_true', help = 'Only consider conversions seen in both reads of a read pair?')
    parser.add_argument('--use_g_t', action = 'store_true', help = 'Consider G->T conversions?')
    parser.add_argument('--use_g_c', action = 'store_true', help = 'Consider G->C conversions?')
    parser.add_argument('--use_read1', action = 'store_true', help = 'Use read1 when looking for conversions?')
    parser.add_argument('--use_read2', action = 'store_true', help = 'Use read2 when looking for conversions?')
    parser.add_argument('--nConv', type = int, help = 'Minimum number of required G->T and/or G->C conversions in a read pair in order for conversions to be counted. Default is 1.', default = 1)
    args = parser.parse_args()

    #Take in list of samplenames to run pigpen on
    #Derive quant.sf, STAR bams, and postmaster bams
    samplenames = args.samplenames.split(',')
    salmonquants = [os.path.join(x, 'salmon', '{0}.quant.sf'.format(x)) for x in samplenames]
    starbams = [os.path.join(x, 'STAR', '{0}Aligned.sortedByCoord.out.bam'.format(x)) for x in samplenames]
    postmasterbams = [os.path.join(x, 'postmaster', '{0}.postmaster.bam'.format(x)) for x in samplenames]

    #Take in list of control samples, make list of their corresponding star bams for SNP calling
    controlsamples = args.controlsamples.split(',')
    controlindicies = []
    for ind, x in enumerate(samplenames):
        if x in controlsamples:
            controlindicies.append(ind)

    controlstarbams = []
    for x in controlindicies:
        controlstarbams.append(starbams[x])

    #We have to be either looking for G->T or G->C, if not both
    if not args.use_g_t and not args.use_g_c:
        print('We have to either be looking for G->T or G->C, if not both! Add argument --use_g_t and/or --use_g_c.')
        sys.exit()

    #We have to be using either read1 or read2 if not both
    if not args.use_read1 and not args.use_read2:
        print('We need to use read1 or read2, if not both! Add argument --use_read1 and/or --use_read2.')
        sys.exit()

    #If we want to only consider overlap, we have to be using both read1 and read2
    if args.onlyConsiderOverlap and (not args.use_read1 or not args.use_read2):
        print('If we are only going to consider overlap between paired reads, we must use both read1 and read2.')
        sys.exit()
    
    #Make vcf file for snps
    if args.useSNPs:
        if not os.path.exists('snps'):
            os.mkdir('snps')
        vcfFileNames = getSNPs(controlstarbams, args.genomeFasta, args.SNPcoverage, args.SNPfreq)
        for f in vcfFileNames:
            csi = f + '.csi'
            log = f[:-3] + '.log'
            #Move files to snps directory
            os.rename(f, os.path.join('snps', f))
            os.rename(csi, os.path.join('snps', csi))
            os.rename(log, os.path.join('snps', log))

        os.rename('merged.vcf', os.path.join('snps', 'merged.vcf'))
        os.rename('vcfconcat.log', os.path.join('snps', 'vcfconcat.log'))
        snps = recordSNPs(os.path.join('snps', 'merged.vcf'))
    
    elif not args.useSNPs:
        snps = None

    #Get positions to manually mask if given
    if args.maskbed:
        print('Getting positions to manually mask...')
        maskpositions = readmaskbed(args.maskbed)
    elif not args.maskbed:
        maskpositions = None

    #For each sample, identify conversions, assign conversions to transcripts,
    #and collapse transcript-level measurements to gene-level measurements.
    for ind, sample in enumerate(samplenames):
        print('Running PIGPEN for {0}...'.format(sample))
        starbam = starbams[ind]
        if args.nproc == 1:
            convs, readcounter = iteratereads_pairedend(starbam, args.onlyConsiderOverlap, args.use_g_t, args.use_g_c, args.use_read1, args.use_read2, args.nConv, snps, maskpositions, 'high')
        elif args.nproc > 1:
            convs = getmismatches(starbam, args.onlyConsiderOverlap, snps, maskpositions, args.nConv, args.nproc, args.use_g_t, args.use_g_c, args.use_read1, args.use_read2)

        print('Getting posterior probabilities from salmon alignment file...')
        postmasterbam = postmasterbams[ind]
        pprobs = getpostmasterassignments(postmasterbam)
        print('Assinging conversions to transcripts...')
        txconvs = assigntotxs(pprobs, convs)
        print('Collapsing transcript level conversion counts to gene level...')
        tx2gene, geneconvs = collapsetogene(txconvs, args.gff)
        print('Counting number of reads assigned to each gene...')
        salmonquant = salmonquants[ind]
        genecounts = readspergene(salmonquant, tx2gene)
        print('Writing output...')
        outputfile = sample + '.pigpen.txt'
        writeOutput(geneconvs, genecounts, outputfile, args.use_g_t, args.use_g_c)
        print('Done!')






        

