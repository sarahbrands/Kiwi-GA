import __future__
import os
import sys
import numpy as np
import collections
import argparse
import functools
# from schwimmbad import MultiPool

import control as ctrl
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
# #FIXME Setup should be done on all nodes

# Read command line arguments and exit if no input is found.
parser = argparse.ArgumentParser(description='Run pika2')
parser.add_argument('runname', help='Specify run name')
args = parser.parse_args()
inputdir = ctrl.inputdir + args.runname + '/'
fw.check_indir(inputdir)

# Initial setup of directories and file paths
outputdir = ctrl.outputdir + args.runname + '/'
fw.mkdir(outputdir)
fd = fw.make_file_dict(inputdir, outputdir)
outdir, rundir, savedir, indir = fw.init_setup(outputdir)
fw.copy_input(fd,indir)
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

''' PREPARE FASTWIND '''

# Create a FORMAL_INPUT file containing the relevant lines.
fw.create_FORMAL_INPUT(ctrl.inicalcdir, lineinfo[0])

# Initialise the fitness function with parameters that are
# the same for every model.
eval_fitness = functools.partial(fw.evaluate_fitness, ctrl.inicalcdir, rundir,
    savedir, all_pars, ctrl.modelatom, ctrl.fw_timeout, lineinfo, dof,
    ctrl.fitmeasure, fd["chi2_out"], param_names)

''' THE GENETIC ALGORITHM STARTS HERE '''

# #FIXME Feature that you can pick up an old run is missing
gencount = 0

# Pick first generation of models. The amount of individuals can
# be more than a typical generation.
nind_first_gen = ctrl.f_gen1*ctrl.nind
generation = pop.init_pop(nind_first_gen, param_space, fd["dupl_out"])
modnames = fw.gen_modnames(gencount, nind_first_gen)

fitnesses = map(eval_fitness, modnames, generation)

# If the first generation is larger than the typical generation,
# The top nind fittest individuals of this generation are selected.
if ctrl.f_gen1 > 1:
    topfit = pop.get_top_x_fittest(generation, fitnesses, ctrl.nind)
    generation, fitnesses = topfit

# The fittest individual is selected
genbest, best_fitness = pop.get_fittest(generation, fitnesses)
pop.store_lowestchi2(fd["bestchi2_out"], best_fitness, 0)
pop.print_report(gencount, best_fitness, np.median(fitnesses), ctrl.be_verbose)

mutation_rate = ctrl.mut_rate_init # initial mutation rate

for agen in xrange(ctrl.ngen):

    gencount = gencount + 1
    pop.store_mutation(fd["mutation_out"], mutation_rate, agen)

    if ctrl.mut_adjust_type == 'doerr':
        print('Doerr not implemented yet, exiting.')
        sys.exit()

    elif ctrl.mut_adjust_type == 'carbonneau':
        mutation_rate = pop.adjust_mutation_rate_carbonneau(mutation_rate,
            fitnesses, ctrl.mut_rate_factor, ctrl.mut_rate_min,
            ctrl.mut_rate_max, ctrl.fit_cuttof_min_carb,
            ctrl.fit_cuttof_min_carb)

    elif ctrl.mut_adjust_type == 'genvariety':
        gen_variety = pop.assess_variation(generation, param_space, genbest)
        mean_gen_variety = np.mean(gen_variety)
        mutation_rate = pop.adjust_mutation_genvariety(mutation_rate,
            ctrl.cuttof_decrease_genv, ctrl.cuttof_increase_genv,
            ctrl.mut_rate_factor, ctrl.mut_rate_min, ctrl.mut_rate_max,
            mean_gen_variety, param_space)

    # Reproduce and asses fitness
    generation = pop.reproduce(generation, fitnesses, mutation_rate,
        ctrl.clone_fraction, param_space, fd["dupl_out"])
    modnames = fw.gen_modnames(gencount, nind_first_gen)

    fitnesses = map(eval_fitness, modnames, generation)

    # The fittest individual of the run always survives.
    generation, fitnesses = pop.reincarnate(generation, fitnesses,
        genbest, best_fitness)
    genbest, best_fitness = pop.get_fittest(generation, fitnesses)
    pop.store_lowestchi2(fd["bestchi2_out"], best_fitness, agen)

    pop.print_report(gencount, best_fitness, np.median(fitnesses),
        ctrl.be_verbose)







#
