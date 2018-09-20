#!/bin/bash
#SBATCH -c 1
#SBATCH -N 1
#SBATCH -t 2-00:00
#SBATCH -p medium
#SBATCH --mem=4000
#SBATCH -o log/combine_%j.out
#SBATCH -e log/combine_%j.err
#SBATCH --mail-type=ALL
#SBATCH --mail-user=taeyeon_yoo@hms.harvard.edu

module load python
python combineImages.py
