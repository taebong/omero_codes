#!/bin/bash
#SBATCH -c 1
#SBATCH -N 1
#SBATCH -t 2-00:00
#SBATCH -p medium
#SBATCH --mem=1500
#SBATCH -o log/import_%j.out
#SBATCH -e log/import_%j.err
#SBATCH --mail-type=ALL
#SBATCH --mail-user=taeyeon_yoo@hms.harvard.edu

module load omero
omero import -- --exclude=clientpath --checksum-algorithm=CRC-32 ../TaxolMicronucleation/20180907 -d 4702

