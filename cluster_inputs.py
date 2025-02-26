"""
This lists the information specific to the cluster you are running Kiwi-GA on.
This file is to be modified by end users to make sure a working job script can be generated by
pre_run_check.py.
Make sure the right settings are chosen and the correct modules are imported.
"""

username = "vsc36648"
codedir = "Kiwi-GA"
cores_per_node = 36
max_wall_time = "7"  # In hours, this has to be a string.
time_per_gen = 1.1  # in hours
scratch_loc = "/scratch/leuven/366/"
home_loc = "/data/leuven/366"

# For VSC Accounting and such, can leave empty if not applicable
extra_sbatch = """#SBATCH --account=lp_equation
#SBATCH --cluster=genius
#SBATCH --output=/scratch/leuven/366/vsc36648/%s_run.log
#SBATCH --error=/scratch/leuven/366/vsc36648/%s.log
"""

# For VSC
modules = """
module load cluster/genius/scientific_computing
module load intel/2023a
module load SciPy-bundle/2023.07-iimkl-2023a
module load matplotlib/3.7.2-iimkl-2023a
"""

# # For Snellius
# modules = """
# module load 2021
# module load foss/2021a
# module load Python/3.9.5-GCCcore-10.3.0
# """
