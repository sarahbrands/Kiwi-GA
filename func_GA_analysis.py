# Functions for GA analysis script part of Kiwi-GA
# Created by Sarah Brands @ 29 July 2022

import os
import sys
import math
import numpy as np
import pandas as pd
import matplotlib
from scipy import stats
from matplotlib import pyplot as plt
import matplotlib.image as mpimg
import fastwind_wrapper as fw

def get_luminosity(Teff, radius):
    '''Calculate L in terms of log(L/Lsun), given Teff (K)
    and the radius in solar radii'''

    sigmaSB = 5.67051e-5
    Lsun = 3.9e33
    Rsun = 6.96e10

    radius_cm = radius * Rsun
    luminosity_cgs  = 4*math.pi * sigmaSB * Teff**4 * radius_cm**2
    luminosity = np.log10(luminosity_cgs / Lsun)

    return luminosity

def get_mass(logg, Rstar):
    ''' Gives Mstar in solar units, given logg and Rstar in solar units'''

    Msun = 1.99e33
    Rsun = 6.96e10
    Gcgs = 6.67259e-8

    g = 10**logg
    Rstar = Rstar*Rsun

    Mstar = g * Rstar**2 / Gcgs

    return Mstar / Msun

def get_fx(mdot, vinf):
    """ Estimates fx based on the Mdot and vinf, based on the
    power law of Kudritzki, Palsa, Feldmeier et al. (1996). This power law
    is extrapolated also outside where Kudritzki+96 have data points.
    """

    mdot = 10**mdot / 10**(-6)
    logmdotvinf = np.log10(mdot/vinf)

    # Relation from Kudritzki, Palsa, Feldmeier et al. (1996)
    logfx = -5.45 - 1.05*logmdotvinf
    # fx = 10**(logfx)

    return logfx

def get_Gamma_Edd(Lum, Mass, kappa_e=0.344):
    """
    * Lum = luminosity in solor luminosity (no log)
    * Mass = stellar mass in solar mass

    kappa_e default from Bestenlehner (2020) page 3942
    """

    Lsun = 3.9e33
    Msun = 1.99e33
    ccgs = 2.99792458*10**10 #cm/s
    Gcgs = 6.67259e-8

    Lum = Lum*Lsun
    Mass = Mass*Msun

    GammE = Lum * kappa_e / (4.*np.pi*ccgs*Gcgs*Mass)

    return GammE

def get_vesc_eff(mass, radius, GammE):
    Rsun = 6.96e10
    Msun = 1.99e33
    Gcgs = 6.67259e-8

    mass_eff = mass*(1-GammE)

    neg_idx = np.less_equal(mass_eff, 0)
    mass_eff[neg_idx] = 0

    vesc_cms = np.sqrt((2*Gcgs*mass_eff*Msun)/(radius*Rsun))
    vesc_kms = vesc_cms*1e-5

    return vesc_kms

def more_parameters(df, param_names, fix_names, fix_vals):
    fix_dict = dict(zip(fix_names, fix_vals))

    # List of parameters that are plotted in the extra parameter fitness plot
    # Always plot Q-parameters, luminosity, radius and spectroscopic mass, Gamma
    plist = ['logL', 'radius', 'Mspec', 'Gamma_Edd', 'vesc_eff',
        'logq0', 'logQ0', 'logq1', 'logQ1', 'logq2', 'logQ2']

    for par in ['logq0', 'logQ0', 'logq1', 'logQ1', 'logq2', 'logQ2']:
        if par not in df.columns:
            plist.remove(par)

    # Always get the luminosity and spectroscopic mass and Eddington factor
    if 'teff' in df.columns:
        df['logL'] = get_luminosity(df['teff'], df['radius'])
    else:
        df['logL'] = get_luminosity(fix_dict['teff'], df['radius'])

    if 'logg' in df.columns:
        df['Mspec'] = get_mass(df['logg'], df['radius'])
    else:
        df['Mspec'] = get_mass(fix_dict['logg'], df['radius'])

    df['Gamma_Edd'] = get_Gamma_Edd(10**df['logL'], df['Mspec'])
    df['vesc_eff'] = get_vesc_eff(df['Mspec'], df['radius'],df['Gamma_Edd'])

    # If X-rays are given then include them
    if 'xlum' in df.columns:
        the_xlum = df['xlum'].values
        nan_logx = np.less_equal(the_xlum,0)
        the_xlum[nan_logx] = 1e-20
        the_logxlum = np.log10(the_xlum)
        the_logxlum[nan_logx] = math.nan
        df['logxlum'] = the_logxlum
        plist.append('logxlum')

    if ('fx' not in df.columns) and (fix_dict['fx'] > 1000.0):
        if 'mdot' in df.columns:
            the_mdot = df['mdot']
        else:
            the_mdot = fix_dict['mdot']
        if 'vinf' in df.columns:
            the_vinf = df['vinf']
        elif 'vinf' in fix_dict.keys():
            the_vinf = fix_dict['vinf']
        else:
            the_vinf = 2.6*df['vesc_eff']
            print('WARNING: known BUG: assuming vinf = 2.6 vesc for all Teffs')
        df['logfx'] = get_fx(the_mdot, the_vinf)
        plist.append('logfx')

    # Other derived parameters are only computed when relevant.
    if 'vinf' in df.columns:
        df['vinf_vesc'] = df['vinf']/df['vesc_eff']
        plist.append('vinf_vesc')

    if 'windturb' in df.columns and 'vinf' in df.columns:
        df['windturb_kms'] = df['windturb'] * df['vinf']
        plist.append('windturb_kms')

    return df, plist

def calculateP(chi2, degreesFreedom, normalize):
    """
    Based on the chi2 value of a model, compute the P-value
    Before this is done, all chi2 values are normalised by the lowest
    chi2 value of the run.
    """
    if normalize:
        scaling = np.min(chi2)
    else:
        scaling = degreesFreedom

    # In principle, don't use this correction factor (keep set to 1.0)
    # Can be used to make error bars artificially larger
    correction_factor = 1.0
    if correction_factor != 1.0:
        print("!"*70)
        print("\n\n\n       WARNING!!!!!!!! chi2 correction\n\n\n")
        print("!"*70)
        print("chi2 of all models artificially lowered in order to enlarge")
        print("uncertainties\n\n\n")

    chi2 = correction_factor * (chi2 * degreesFreedom) / scaling
    probs = np.zeros_like(chi2)
    try:
        for i in range(len(chi2)):
            probs[i] = stats.chi2.sf(chi2[i], degreesFreedom)
    except:
        chi2 = chi2.values
        for i in range(len(chi2)):
            probs[i] = stats.chi2.sf(chi2[i], degreesFreedom)
    return probs

def calculateP_noncent(chi2, degreesFreedom, lambda_nc):
    """
    Based on the chi2 value of a model, compute the P-value assuming a
    non-central chi2 distribution
    """

    # scaling = np.min(chi2)
    # chi2 = chi2 /scaling * degreesFreedom

    probs = np.zeros_like(chi2)
    try:
        for i in range(len(chi2)):
            probs[i] = stats.ncx2.sf(chi2[i], degreesFreedom, lambda_nc)
    except:
        chi2 = chi2.values
        for i in range(len(chi2)):
            probs[i] = stats.ncx2.sf(chi2[i], degreesFreedom, lambda_nc)
    return probs

def get_uncertainties(df, dof_tot, npspec, param_names, param_space,
    deriv_pars, incl_deriv=True):

    if np.min(df['rchi2']) > 1.0:
        which_statistic = 'RMSEA' # 'Pval_chi2' or 'Pval_ncchi2' or 'RMSEA'
    else:
        which_statistic = 'Pval_chi2'

    # Assign P-vaues and compute inverse reduced chi2
    df['invrchi2'] = 1./df['rchi2']
    df['norm_rchi2'] = df['rchi2']/np.min(df['rchi2'])

    df['RMSEA'] = np.sqrt((df['chi2']-dof_tot)/(dof_tot*(npspec-1)))
    minRMSEA = np.min(df['RMSEA'])
    # closefit_RMSEA = minRMSEA + 0.005
    closefit_RMSEA = minRMSEA
    lambda_nc = (closefit_RMSEA)**2 * dof_tot*(npspec-1)

    if which_statistic == 'Pval_ncchi2':
        df['P-value'] = calculateP_noncent(df['chi2'], dof_tot, lambda_nc)
    else:
        df['P-value'] = calculateP(df['chi2'], dof_tot, normalize=True) # ORIGINAL P-VALUE

    # Store the best fit parameters and 1 and 2 sig uncertainties in a dictionary
    params_error_1sig = {}
    params_error_2sig = {}

    xbest = pd.Series.idxmax(df['P-value'])
    if which_statistic in ('Pval_ncchi2', 'Pval_chi2'):
        min_p_1sig = 0.317
        min_p_2sig = 0.0455
        ind_1sig = df['P-value'] >= min_p_1sig
        ind_2sig = df['P-value'] >= min_p_2sig
    elif which_statistic == 'RMSEA':
        min_p_1sig = minRMSEA*1.05
        min_p_2sig = minRMSEA*1.10
        ind_1sig = df['RMSEA'] <= min_p_1sig
        ind_2sig = df['RMSEA'] <= min_p_2sig

    for i, aspace in zip(param_names, param_space):
        the_step_size = aspace[2]
        params_error_1sig[i] = [min(df[i][ind_1sig])-the_step_size,
            max(df[i][ind_1sig])+the_step_size, df[i][xbest]]
        params_error_2sig[i] = [min(df[i][ind_2sig])-the_step_size,
            max(df[i][ind_2sig])+the_step_size, df[i][xbest]]
    if incl_deriv:
        deriv_params_error_1sig = {}
        deriv_params_error_2sig = {}
        for i in (deriv_pars):
            deriv_params_error_1sig[i] = [min(df[i][ind_1sig]),
                max(df[i][ind_1sig]), df[i][xbest]]
            deriv_params_error_2sig[i] = [min(df[i][ind_2sig]),
                max(df[i][ind_2sig]), df[i][xbest]]

    # Read best model names (for plotting of line profiles)
    best_model_name = df['run_id'][xbest]
    bestfamily_name = df['run_id'][ind_2sig].values

    if incl_deriv:
        best_uncertainty = (best_model_name, bestfamily_name, params_error_1sig,
            params_error_2sig, deriv_params_error_1sig, deriv_params_error_2sig,
            which_statistic)
    else:
        best_uncertainty = (best_model_name, bestfamily_name, params_error_1sig,
            params_error_2sig, which_statistic)

    return df,best_uncertainty

def titlepage(df, runname, params_error_1sig, params_error_2sig,
    the_pdf, param_names, maxgen, nind, linedct, which_sigma,
    deriv_params_error_1sig, deriv_params_error_2sig, deriv_pars):
    """
    Make a page with best fit parameters and errors
    """

    ncrash = len(df.copy()[df['chi2'] == 999999999])
    ntot = len(df)
    perccrash = round(100.0*ncrash/ntot,1)
    minrchi2 = round(np.min(df['rchi2']),2)
    nlines = len(linedct['name'])

    fig, ax = plt.subplots(2,2,figsize=(12.5, 12.5),
        gridspec_kw={'height_ratios': [0.5, 3], 'width_ratios': [2, 8]})

    if os.path.isfile('kiwi.jpg'):
        ax[0,0].imshow(mpimg.imread('kiwi.jpg'))
    ax[0,0].axis('off')
    ax[0,1].axis('off')
    ax[1,0].axis('off')
    ax[1,1].axis('off')

    boldtext = {'ha':'left', 'va':'top', 'weight':'bold'}
    normtext = {'ha':'left', 'va':'top'}
    offs = 0.12
    yvalmax = 0.9
    ax[0,1].text(0.0, yvalmax, 'Run name', **boldtext)
    ax[0,1].text(0.25, yvalmax, runname, **normtext)
    ax[0,1].text(0.0, yvalmax-1*offs, 'Best rchi2', **boldtext)
    ax[0,1].text(0.25, yvalmax-1*offs, str(minrchi2), **normtext)
    ax[0,1].text(0.0, yvalmax-2*offs, 'Generations', **boldtext)
    ax[0,1].text(0.25, yvalmax-2*offs, str(maxgen), **normtext)
    ax[0,1].text(0.0, yvalmax-3*offs, 'Individuals per gen', **boldtext)
    ax[0,1].text(0.25, yvalmax-3*offs, str(nind), **normtext)
    ax[0,1].text(0.0, yvalmax-4*offs, 'Total # models', **boldtext)
    ax[0,1].text(0.25, yvalmax-4*offs, str(ntot), **normtext)
    ax[0,1].text(0.0, yvalmax-5*offs, 'Crashed models', **boldtext)
    ax[0,1].text(0.25, yvalmax-5*offs, str(perccrash) + '%', **normtext)
    ax[0,1].text(0.0, yvalmax-6*offs, 'Number of lines', **boldtext)
    ax[0,1].text(0.25, yvalmax-6*offs, str(nlines), **normtext)

    if which_sigma == 2:
        psig = params_error_2sig
        deriv_psig = deriv_params_error_2sig
    else:
        psig = params_error_1sig
        deriv_psig = deriv_params_error_1sig



    offs = 0.02
    yvalmax = 1.0
    secndcol = 0.15
    ax[1,1].text(0.0, yvalmax, 'Parameter', weight='bold')
    ax[1,1].text(secndcol, yvalmax, 'Best', weight='bold')
    ax[1,1].text(secndcol*2, yvalmax, '-' + str(which_sigma)
        + r'$\mathbf{\sigma}$', weight='bold')
    ax[1,1].text(secndcol*3, yvalmax, '+' + str(which_sigma)
        + r'$\mathbf{\sigma}$', weight='bold')
    ax[1,1].text(secndcol*4, yvalmax,
        r'Min (' + str(which_sigma) + r'$\mathbf{\sigma}$)', weight='bold')
    ax[1,1].text(secndcol*5, yvalmax,
        r'Max (' + str(which_sigma) + r'$\mathbf{\sigma}$)', weight='bold')
    for paramname in param_names:
        yvalmax = yvalmax - offs
        ax[1,1].text(0.0, yvalmax, paramname)
        ax[1,1].text(secndcol, yvalmax,
            round(psig[paramname][2],3))
        ax[1,1].text(secndcol*2, yvalmax,
            round(psig[paramname][2]-psig[paramname][0],3))
        ax[1,1].text(secndcol*3, yvalmax,
            round(psig[paramname][1]-psig[paramname][2],3))
        ax[1,1].text(secndcol*4, yvalmax,
            round(psig[paramname][0],3))
        ax[1,1].text(secndcol*5, yvalmax,
            round(psig[paramname][1],3))

    yvalmax = yvalmax - offs
    for paramname in deriv_pars:
        yvalmax = yvalmax - offs
        ax[1,1].text(0.0, yvalmax, paramname)
        ax[1,1].text(secndcol, yvalmax,
            round(deriv_psig[paramname][2],3))
        ax[1,1].text(secndcol*2, yvalmax,
            round(deriv_psig[paramname][2]-deriv_psig[paramname][0],3))
        ax[1,1].text(secndcol*3, yvalmax,
            round(deriv_psig[paramname][1]-deriv_psig[paramname][2],3))
        ax[1,1].text(secndcol*4, yvalmax,
            round(deriv_psig[paramname][0],3))
        ax[1,1].text(secndcol*5, yvalmax,
            round(deriv_psig[paramname][1],3))

    plt.tight_layout()
    the_pdf.savefig(dpi=150)
    plt.close()

    return the_pdf


def fitnessplot(df, yval, params_error_1sig, params_error_2sig,
    the_pdf, param_names, param_space, maxgen,
    which_cmap=plt.cm.viridis, save_jpg=False, df_tot=[]):

    """
    Plot the fitness as a function of each free parameter. This function
    can be used for plotting the P-value, 1/rchi2 of all lines combined,
    or for the fitness of individual lines (1/rchi2)
    """

    # Only consider models that have not crashed
    df = df[df['chi2'] < 999999999]

    # Prepare colorbar
    cmap = which_cmap
    bounds = np.linspace(0, maxgen+1, maxgen+2)
    norm = matplotlib.colors.BoundaryNorm(bounds, int(cmap.N*0.8))

    # Set up figure dimensions and subplots
    ncols = 5
    # nrows len(param_names)+1 to ensure space for the colorbar
    nrows =int(math.ceil(1.0*(len(param_names)+1)/ncols))
    nrows =max(nrows, 2)
    ccol = ncols - 1
    crow = -1
    figsizefact = 2.5
    fig, ax = plt.subplots(nrows, ncols,
        figsize=(figsizefact*ncols, figsizefact*nrows),
        sharey=True)

    # Loop through parameters
    for i in range(ncols*nrows):

        if ccol == ncols - 1:
            ccol = 0
            crow = crow + 1
        else:
            ccol = ccol + 1

        if i >= len(param_names):
            ax[crow,ccol].axis('off')
            continue

        # Make actual plots
        ax[crow,ccol].set_title(param_names[i])
        if len(param_space) > 0:
            ax[crow,ccol].set_xlim(param_space[i][0], param_space[i][1])
        elif param_names[i] == 'Gamma_Edd':
            ax[crow,ccol].set_xlim(0,1.0)
        elif param_names[i] == 'vinf_vesc':
            ax[crow,ccol].set_xlim(0,10.0)
        scat0 = ax[crow,ccol].scatter(df[param_names[i]], df[yval], c=df['gen'],
            cmap=cmap, norm=norm, s=10)

        min1sig = params_error_1sig[param_names[i]][0]
        max1sig = params_error_1sig[param_names[i]][1]
        min2sig = params_error_2sig[param_names[i]][0]
        max2sig = params_error_2sig[param_names[i]][1]
        bestfit = params_error_2sig[param_names[i]][2]
        # if not save_jpg:
        ax[crow,ccol].axvline(bestfit, color='orangered', lw=1.5)
        ax[crow,ccol].axvspan(min1sig, max1sig, color='gold',
            alpha=0.70, zorder=0)
        ax[crow,ccol].axvspan(min2sig, max2sig, color='gold',
            alpha=0.25, zorder=0)

        # Set y-labels
        if ccol == 0:
            if yval == 'P-value':
                ax[crow,ccol].set_ylabel('P-value')
            else:
                ax[crow,ccol].set_ylabel(r'1/$\chi^2_{\rm red}$')

        if len(df_tot) > 0:
            ax[crow,ccol].set_ylim(-0.05*np.max(df_tot[yval]), np.max(df_tot[yval])*1.10)
        else:
            ax[crow,ccol].set_ylim(-0.05*np.max(df[yval]), np.max(df[yval])*1.10)
        ax[crow,ccol].set_rasterized(True)


    # Colorbar
    cbar = plt.colorbar(scat0, orientation='horizontal')
    cbar.ax.set_title('Generation')

    # Set title
    if yval in ('invrchi2', 'P-value'):
        if len(param_space) > 0:
            plt.suptitle('All lines')
        else:
            plt.suptitle('All lines (derived parameters)')
    else:
        if len(param_space) > 0:
            plt.suptitle(yval)
        else:
            plt.suptitle(yval + ' (derived parameters)')

    # Tight layout and save plot
    plt.tight_layout()
    if nrows == 2:
        plt.subplots_adjust(0.07, 0.07, 0.93, 0.85)
    else:
        plt.subplots_adjust(0.07, 0.07, 0.93, 0.90)
    if not save_jpg:
        if yval in ('invrchi2', 'P-value'):
            the_pdf.savefig(dpi=150)
        else:
            the_pdf.savefig(dpi=100)
        plt.close()

        return the_pdf
    else:
        return fig, ax

def lineprofiles(df, spectdct, linedct, savedmoddir,
    best_model_name, bestfamily_name, the_pdf, plotlineprofdir,
    save_jpg=False):
    """
    Create plot with line profiles of best fitting models.
    In the background, plot the data.
    """

    nlines = len(linedct['name'])

    # Untar best fitting models.
    plotmoddirlist = []
    for amod in bestfamily_name:
        moddir = savedmoddir + amod.split('_')[0] + '/' + amod + '/'
        modtar = savedmoddir + amod.split('_')[0] + '/' + amod + '.tar.gz'
        if not os.path.isdir(moddir):
            os.system('mkdir -p ' + moddir)
            os.system('tar -xzf ' + modtar + ' -C ' + moddir + '/.')
        plotmoddirlist.append(moddir)

    bestmoddir = savedmoddir + best_model_name.split('_')[0] + '/' + best_model_name +  '/'

    # Set up figure dimensions and subplots
    ncols = 5
    nrows =int(math.ceil(1.0*nlines/ncols))
    nrows =max(nrows, 2)
    ccol = ncols - 1
    crow = -1
    figsizefact = 2.5
    fig, ax = plt.subplots(nrows, ncols,
        figsize=(figsizefact*ncols, 0.7*figsizefact*nrows))

    # Loop through parameters
    for i in range(ncols*nrows):

        if ccol == ncols - 1:
            ccol = 0
            crow = crow + 1
        else:
            ccol = ccol + 1

        if i >= nlines:
            ax[crow,ccol].axis('off')
            continue

        # Read data per line
        keep_idx = [(spectdct['wave'] > linedct['left'][i]) &
            (spectdct['wave'] < linedct['right'][i])]
        wave_tmp = spectdct['wave'][tuple(keep_idx)]
        flux_tmp = spectdct['flux'][tuple(keep_idx)]
        err_tmp = spectdct['err'][tuple(keep_idx)]

        # Read profile of best fitting model
        best_prof_file = bestmoddir + linedct['name'][i] + '.prof.fin'
        bestmodwave, bestmodflux = np.genfromtxt(best_prof_file).T

        # Read profiles of best fitting family of models
        lineflux_min = np.copy(bestmodflux)
        lineflux_max = np.copy(bestmodflux)
        if len(plotmoddirlist) > 0:
            for asig_mod in plotmoddirlist:
                fam_prof_file = asig_mod + linedct['name'][i] + '.prof.fin'
                smwave, smflux = np.genfromtxt(fam_prof_file).T

                lineflux_min = np.min(np.array([lineflux_min, smflux]), axis=0)
                lineflux_max = np.max(np.array([lineflux_max, smflux]), axis=0)

        lineprof_arr = np.array([bestmodwave, bestmodflux, lineflux_min,
            lineflux_max]).T
        lineprof_arr_head = 'wave bestflux minflux maxflux'
        np.savetxt(plotlineprofdir + linedct['name'][i] + '.txt', lineprof_arr,
            header=lineprof_arr_head)

        # Make actual plots
        ax[crow,ccol].set_title(linedct['name'][i])
        ax[crow,ccol].axhline(1.0, color='black', lw=0.8)
        ax[crow,ccol].errorbar(wave_tmp, flux_tmp, yerr=err_tmp,
            fmt='o', color='black', ms=0)
        ax[crow,ccol].fill_between(bestmodwave, lineflux_min, lineflux_max,
            color='#8cd98c', alpha=0.7)
        ax[crow,ccol].plot(bestmodwave, bestmodflux, color='#1ca641', lw=2.4,
            alpha=1.0)
        ax[crow,ccol].set_xlim(linedct['left'][i], linedct['right'][i])

    # Tight layout and save plot
    plt.tight_layout()

    if not save_jpg:
        the_pdf.savefig(dpi=150)
        plt.close()
        return the_pdf
    else:
        return fig, ax

def correlationplot(the_pdf, df, corrpars):
    """
    Create a correlation plot of the parameters in the list corrpars.
    """

    orig_corrpar = corrpars.copy()

    for par in orig_corrpar:
        if par not in df.columns:
            corrpars.remove(par)

    dfs = df.sort_values(by=['invrchi2'])

    # Set up figure dimensions and subplots
    ncols = len(corrpars)
    nrows = ncols
    hratios = 30*np.ones(ncols)
    wratios = 30*np.ones(ncols)
    hratios[0] = 1.0
    wratios[-1] = 1.0
    figsizefact = 2.0
    fig, ax = plt.subplots(nrows, ncols,
        figsize=(figsizefact*ncols, figsizefact*nrows), sharex='col', sharey='row',
            gridspec_kw={'height_ratios': hratios, 'width_ratios': wratios})

    # Loop through parameters to create correlation plot
    pairlist = []
    for ccol in range(ncols):
        for crow in range(nrows):
            pc1 = corrpars[ccol]
            pc2 = corrpars[crow]
            pair = [pc1, pc2]
            if (pc1 == pc2) or (pair in pairlist):
                ax[crow,ccol].axis('off')
            else:
                ax[crow,ccol].scatter(dfs[pc1], dfs[pc2],
                    c=dfs['invrchi2'],s=10)
                pairlist.append(pair)
                pairlist.append(pair[::-1])
            ax[crow,ccol].set_rasterized(True)
            ax[crow,ccol].set_xlim(np.min(dfs[pc1]), np.max(dfs[pc1]))
            ax[crow,ccol].set_ylim(np.min(dfs[pc2]), np.max(dfs[pc2]))
    # Label axes
    for i in range(0, ncols-1):
        ax[-1,i].set_xlabel(corrpars[i])
        ax[i+1, 0].set_ylabel(corrpars[i+1])

    # Tight layout and save plot
    plt.tight_layout()
    the_pdf.savefig(dpi=150)
    plt.close()

    return the_pdf

def get_fwmaxtime(controlfile):
    dct = fw.read_control_pars(controlfile)
    timeoutstr = dct['fw_timeout']
    if timeoutstr.endswith('m'):
        timeout = float(timeoutstr[:-1])*60
    else:
        print('Timeout string not given in minutes, exiting')
        sys.exit()
    return timeout

def fw_performance(the_pdf, df, controlfile):
    """
    Show maximum interations, convergence and run time of FW models.
    """

    # Pick up fastwind timeout to assign a number to the runs that ran to maximum
    fw_timeout = get_fwmaxtime(controlfile)
    fw_timeout_min = 1.0*fw_timeout/60.0
    df.loc[(df['cputime'] == 99999.9), 'cputime'] = fw_timeout

    # Only consider models that can generate line profiles
    df = df[df['chi2'] < 999999999]
    df = df[df['maxcorr'] > 0.0]
    df['cputime_min'] = 1.0*df['cputime'].values/60.0

    nb = 101
    bins_maxit = np.linspace(0, 100, nb)
    bins_maxco = np.linspace(-3, 1.5, nb)
    bins_ticpu = np.linspace(0, fw_timeout_min, nb)

    fig, ax = plt.subplots(2,3, figsize=(12,6.5))
    ax[0,0].hist(df['maxit'], bins_maxit, color='#2b0066', alpha=0.7)
    ax[0,1].hist(np.log10(df['maxcorr']), bins_maxco, color='#009c60', alpha=0.7)
    ax[0,2].hist(df['cputime_min'], bins_ticpu, color='#b5f700', alpha=0.7)

    ax[0,0].set_xlabel('Maximum iteration')
    ax[0,1].set_xlabel('log(Maximum correction)')
    ax[0,2].set_xlabel('CPU-time (minutes)')
    ax[0,0].set_ylabel('Count')
    ax[0,1].set_ylabel('Count')
    ax[0,2].set_ylabel('Count')

    sct1 = ax[1,0].scatter(np.log10(df['maxcorr']), df['maxit'], s=6, c=df['cputime']/60.0)
    ax[1,0].set_xlabel('log(Maximum correction)')
    ax[1,0].set_ylabel('Maximum iteration')
    cbar1 = plt.colorbar(sct1, ax=ax[1,0])
    cbar1.ax.set_title(r'CPU-time (min)', fontsize=9)

    sct2 = ax[1,1].scatter(np.log10(df['maxcorr']), df['cputime']/60.0, s=6, c=df['maxit'])
    ax[1,1].set_xlabel('log(Maximum correction)')
    ax[1,1].set_ylabel('CPU-time (minutes)')
    cbar2 = plt.colorbar(sct2, ax=ax[1,1])
    cbar2.ax.set_title(r'Max. iteration', fontsize=9)

    sct3 = ax[1,2].scatter(df['cputime']/60.0, df['maxit'], s=4, c=np.log10(df['maxcorr']))
    ax[1,2].set_xlabel('CPU-time (minutes)')
    ax[1,2].set_ylabel('Maximum iteration')
    cbar3 = plt.colorbar(sct3, ax=ax[1,2])
    cbar3.ax.set_title(r'log(Max. corr.)', fontsize=9)

    ax[0,0].set_rasterized(True)
    ax[0,1].set_rasterized(True)
    ax[0,2].set_rasterized(True)
    ax[1,0].set_rasterized(True)
    ax[1,1].set_rasterized(True)
    ax[1,2].set_rasterized(True)

    # Tight layout and save plot
    plt.tight_layout()
    the_pdf.savefig(dpi=150)
    plt.close()

    return the_pdf

def convergence(the_pdf, df_orig, dof_tot, npspec, param_names, param_space,
    deriv_pars, maxgen):

    evol_list = []
    evol_list_best = []
    evol_list_1sig_up = []
    evol_list_1sig_down = []
    evol_list_2sig_up = []
    evol_list_2sig_down = []
    for apar in param_names:
        evol_list_best.append([])
        evol_list_1sig_up.append([])
        evol_list_1sig_down.append([])
        evol_list_2sig_up.append([])
        evol_list_2sig_down.append([])

    for the_max in range(1,maxgen):
        df_tmp = df_orig.copy()[df_orig['gen'] < the_max]

        # Compute uncertainties
        df_tmp, best_uncertainty = get_uncertainties(df_tmp, dof_tot,
            npspec, param_names, param_space, deriv_pars, incl_deriv=False)

        # Unpack all computed values
        best_model_name, bestfamily_name, params_error_1sig, \
            params_error_2sig, which_statistic = best_uncertainty

        for ipar in range(len(param_names)):
            pname = param_names[ipar]
            evol_list_best[ipar].append(params_error_1sig[pname][2])
            evol_list_1sig_up[ipar].append(params_error_1sig[pname][1])
            evol_list_1sig_down[ipar].append(params_error_1sig[pname][0])
            evol_list_2sig_up[ipar].append(params_error_2sig[pname][1])
            evol_list_2sig_down[ipar].append(params_error_2sig[pname][0])

    x_gen = range(len(evol_list_best[0]))
    # fig, ax = plt.subplots(1, len(param_names))

    # Set up figure dimensions and subplots
    ncols = 3
    nrows =int(math.ceil(1.0*(len(param_names))/ncols))
    nrows =max(nrows, 2)
    ccol = ncols - 1
    crow = -1
    figsizefact = 4.0
    fig, ax = plt.subplots(nrows, ncols,
        figsize=(figsizefact*ncols, 0.3*figsizefact*nrows), sharex=True)

    # Loop through parameters
    for i in range(ncols*nrows):

        if ccol == ncols - 1:
            ccol = 0
            crow = crow + 1
        else:
            ccol = ccol + 1
        if crow == nrows -1:
            ax[crow,ccol].set_xlabel('Generation')

        if i >= len(param_names):
            ax[crow,ccol].axis('off')
            continue

        ax[crow,ccol].plot(x_gen, evol_list_best[i], color='red')
        ax[crow,ccol].fill_between(x_gen, evol_list_1sig_down[i], evol_list_1sig_up[i],
            color='gold', alpha=0.70)
        ax[crow,ccol].fill_between(x_gen, evol_list_2sig_down[i], evol_list_2sig_up[i],
            color='gold', alpha=0.25)
        ax[crow,ccol].set_ylim(param_space[i][0], param_space[i][1])
        ax[crow,ccol].set_ylabel(param_names[i])

    plt.tight_layout()
    the_pdf.savefig(dpi=150)
    plt.close()

    return the_pdf




















#
