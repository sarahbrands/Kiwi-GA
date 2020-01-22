import __future__
import os
import sys
import numpy as np
import collections
import argparse
import functools
from schwimmbad import MPIPool

import paths as paths
import population as pop
import fastwind_wrapper as fw

"""
***************************** #FIXME *****************************

- Add a restart option: always save the last generation (population
  parameters and fitness values) into a textfile that can be read
  in in case of restarting.

******************************************************************

"""

''' INITIALIZE / SET UP '''
# #FIXME with sys there's no help but also no extra package required.

# Read command line arguments and exit if no input is found.
parser = argparse.ArgumentParser(description='Run pika2')
parser.add_argument('runname', help='Specify run name')
parser.add_argument('-c', action='store_true', help=('Continues
a run, using fitnessess/parameters of the last generation.'))
args = parser.parse_args()
inputdir = paths.inputdir + args.runname + '/'
fw.check_indir(inputdir)

# Initial setup of directories and file paths
outputdir = paths.outputdir + args.runname + '/'
fd = fw.make_file_dict(inputdir, outputdir)
fw.mkdir(paths.outputdir)
fw.mkdir(outputdir)
outdir, rundir, savedir, indir = fw.init_setup(outputdir)
fw.copy_input(fd,indir)
fw.remove_old_output(fd)

# Read control parameters
# #FIXME: many functions have specific lookups into this
# dictionary as an input, this can be replaced by calling this
# dictionary only once, and then within the function looking
# up the values.
cdict = fw.read_control_pars(fd["control_in"])

if not args.c:
    fw.remove_old_output(fd)

''' READ INPUT PARAMETERS AND DATA '''

# Read input files and data
the_paramspace = fw.read_paramspace(fd["paramspace_in"])
param_names, param_space, fixed_names, fixed_pars = the_paramspace
radinfo = np.genfromtxt(fd["radinfo_in"], comments='#', dtype='str')
defnames, defvals = fw.get_defvals(fd["defvals_in"], param_names, fixed_names)
all_pars = [param_names, fixed_pars, fixed_names, defvals, defnames, radinfo]
dof = len(param_names)
lineinfo = fw.read_data(fd["linelist_in"], fd["normspec_in"])

if args.c:
    # read output from the last generation. 

''' PREPARE FASTWIND '''

# Create a FORMAL_INPUT file containing the relevant lines.
fw.create_FORMAL_INPUT(cdict['inicalcdir'], lineinfo[0])

# Initialise the fitness function with parameters that are
# the same for every model.
eval_fitness = functools.partial(fw.evaluate_fitness, cdict["inicalcdir"],
    rundir, savedir, all_pars, cdict["modelatom"], cdict["fw_timeout"],
    lineinfo, dof, cdict["fitmeasure"], fd["chi2_out"], param_names)

''' THE GENETIC ALGORITHM STARTS HERE '''

# #FIXME Feature that you can pick up an old run is missing
gencount = 0

# Pick first generation of models. The amount of individuals can
# be more than a typical generation.
nind_first_gen = cdict["f_gen1"]*cdict["nind"]
generation = pop.init_pop(nind_first_gen, param_space, fd["dupl_out"])
modnames = fw.gen_modnames(gencount, nind_first_gen)

pool = MPIPool()
if not pool.is_master():
    pool.wait()
    sys.exit(0)

names_genes = []
for mname, gene in zip(modnames, generation):
    names_genes.append([mname, gene])

#FIXME remove line
# fitnesses = list(pool.map(eval_fitness, modnames, generation))
fitnesses = list(pool.map(eval_fitness, names_genes))

# If the first generation is larger than the typical generation,
# The top nind fittest individuals of this generation are selected.
if cdict["f_gen1"] > 1:
    topfit = pop.get_top_x_fittest(generation, fitnesses, cdict["nind"])
    generation, fitnesses = topfit

# The fittest individual is selected
genbest, best_fitness = pop.get_fittest(generation, fitnesses)
pop.store_lowestchi2(fd["bestchi2_out"], best_fitness, 0)
pop.print_report(gencount, best_fitness, np.median(fitnesses),
    cdict["be_verbose"])

mutation_rate = cdict["mut_rate_init"] # initial mutation rate

for agen in range(cdict["ngen"]):

    gencount = gencount + 1
    pop.store_mutation(fd["mutation_out"], mutation_rate, agen)

    if cdict["mut_adjust_type"] == 'doerr':
        print('Doerr not implemented yet, exiting.')
        sys.exit()

    elif cdict["mut_adjust_type"] == 'carbonneau':
        mutation_rate = pop.adjust_mutation_rate_carbonneau(mutation_rate,
            fitnesses, cdict["mut_rate_factor"], cdict["mut_rate_min"],
            cdict["mut_rate_max"], cdict["fit_cutoff_min_carb"],
            cdict["fit_cutoff_min_carb"])

    elif cdict["mut_adjust_type"] == 'genvariety':
        gen_variety = pop.assess_variation(generation, param_space, genbest)
        mean_gen_variety = np.mean(gen_variety)
        mutation_rate = pop.adjust_mutation_genvariety(mutation_rate,
            cdict["cutoff_decrease_genv"], cdict["cutoff_increase_genv"],
            cdict["mut_rate_factor"], cdict["mut_rate_min"],
            cdict["mut_rate_max"], mean_gen_variety, param_space)

    # Reproduce and asses fitness
    generation = pop.reproduce(generation, fitnesses, mutation_rate,
        cdict["clone_fraction"], param_space, fd["dupl_out"])
    modnames = fw.gen_modnames(gencount, nind_first_gen)

    names_genes = []
    for mname, gene in zip(modnames, generation):
        names_genes.append([mname, gene])

    #FIXME remove line
    # fitnesses = list(pool.map(eval_fitness, modnames, generation))
    fitnesses = list(pool.map(eval_fitness, names_genes))

    #FIXME remove line
    # fitnesses = list(pool.map(eval_fitness, modnames, generation))

    # The fittest individual of the run always survives.
    generation, fitnesses = pop.reincarnate(generation, fitnesses,
        genbest, best_fitness)
    genbest, best_fitness = pop.get_fittest(generation, fitnesses)
    pop.store_lowestchi2(fd["bestchi2_out"], best_fitness, agen)

    pop.print_report(gencount, best_fitness, np.median(fitnesses),
        cdict["be_verbose"])


pool.close()




#
