'''
Script to demonstrate combinations of various ions.
It is recommended to run this in IPython
'''

import numpy as np
import matplotlib.pyplot as plt; plt.ion()
import omfit_eqdsk
import pickle as pkl
import scipy,sys,os
import time
from IPython import embed

# Make sure that package home is added to sys.path
import sys
sys.path.append('../')
import aurora

namelist = aurora.default_nml.load_default_namelist()

# test for C-Mod:
namelist['device'] = 'CMOD'
namelist['shot'] = 1101014030
namelist['time'] = 1250 # ms

gfile_name=f'g{namelist["shot"]}.{str(namelist["time"]).zfill(5)}'

if os.path.exists(gfile_name):
    # fetch local g-file if available
    geqdsk = omfit_eqdsk.OMFITgeqdsk(gfile_name)
    print('Fetched local g-file')
else:
    # attempt to construct it via omfit_eqdsk if not available locally
    geqdsk = omfit_eqdsk.OMFITgeqdsk('').from_mdsplus(
        device=namelist['device'],shot=namelist['shot'],
        time=namelist['time'], SNAPfile='EFIT01',
        fail_if_out_of_range=False,time_diff_warning_threshold=20
    )
    # save g-file locally:
    geqdsk.save(raw=True)
    print('Saved g-file locally')


# example kinetic profiles
kin_profs = namelist['kin_profs']

with open('./test_kin_profs.pkl','rb') as f:
    ne_profs,Te_profs = pkl.load(f)

kin_profs['ne']['vals'] = ne_profs['ne']*1e14  # 10^20 m^-3 --> cm^-3
kin_profs['ne']['times'] = ne_profs['t']
rhop = kin_profs['ne']['rhop'] = ne_profs['rhop']
kin_profs['Te']['vals'] = Te_profs['Te']*1e3  # keV --> eV
kin_profs['Te']['times'] = Te_profs['t']
kin_profs['Te']['rhop'] = Te_profs['rhop']
kin_profs['Te']['decay'] = np.ones(len(Te_profs['Te']))*1.0

# set no sources of impurities
namelist['source_type'] = 'const'
namelist['Phi0'] = 1e24 #1.0

# Set up for 2 different ions:
imp = namelist['imp'] = 'Ca' 
namelist['Z_imp'] = 20 
namelist['imp_a'] = 40.078 
aurora_dict_Ca = aurora.utils.aurora_setup(namelist, geqdsk=geqdsk)

# get charge state distributions from ionization equilibrium
atom_data = aurora.atomic.get_all_atom_data(imp,['acd','scd'])
ne_avg = np.mean(kin_profs['ne']['vals'],axis=0) # average over time
Te_avg = np.mean(kin_profs['Te']['vals'],axis=0)  # must be on the same radial basis as ne_avg

# get_frac_abundances takes inputs in m^-3 and eV
logTe, fz_Ca = aurora.atomic.get_frac_abundances(atom_data, ne_avg*1e6, Te_avg, rho=rhop)

imp = namelist['imp'] = 'Ar' 
namelist['Z_imp'] = 18. 
namelist['imp_a'] = 39.948 
aurora_dict_Ar = aurora.utils.aurora_setup(namelist, geqdsk=geqdsk)

# get charge state distributions from ionization equilibrium
atom_data = aurora.atomic.get_all_atom_data(imp,['acd','scd'])
ne_avg = np.mean(kin_profs['ne']['vals'],axis=0) # average over time
Te_avg = np.mean(kin_profs['Te']['vals'],axis=0)  # must be on the same radial basis as ne_avg

# get_frac_abundances takes inputs in m^-3 and eV
logTe, fz_Ar = aurora.atomic.get_frac_abundances(atom_data, ne_avg*1e6, Te_avg, rho=rhop)

############################################################

############################################################

# transform these fractional abundances to the r_V grid used by aurora
_rV = aurora.coords.rad_coord_transform(rhop, 'rhop','r_V', geqdsk)*1e2 # m --> cm (on kin profs grid)
cs = np.arange(aurora_dict_Ca['Z_imp']+1)
nz_init = scipy.interpolate.interp2d(_rV,cs, fz_Ca.T)(aurora_dict_Ca['radius_grid'], cs)

# Take definition of peaking as q(psi_n=0.2)/<q>, where <> is a volume average
nominal_peaking=1.3
nominal_volavg = 1e12 # cm^-3

nz_tot = np.sum(nz_init,axis=0)
indLCFS = np.argmin(np.abs(aurora_dict_Ca['rhop_grid'] - 1.0))
nz_tot_volavg = aurora.coords.vol_average(nz_tot[:indLCFS], aurora_dict_Ca['rhop_grid'][:indLCFS], geqdsk=geqdsk)[-1]
Psi_n = aurora.coords.rad_coord_transform(rhop, 'rhop','psin', geqdsk)
ind_psin02 = np.argmin(np.abs(Psi_n - 0.2))
peaking = nz_tot[ind_psin02]/nz_tot_volavg


# choose transport coefficients
D_eff = 1e4 #cm^2/s
v_eff = -2e2 #cm/s

# # set transport coefficients to the right format
D_z = np.ones((len(aurora_dict_Ca['radius_grid']),1)) * D_eff
V_z = np.ones((len(aurora_dict_Ca['radius_grid']),1)) * v_eff
times_DV = [1.0]  # dummy

# set initial charge state distributions to ionization equilibrium (no transport)
out = aurora.utils.run_aurora(aurora_dict_Ca, times_DV, D_z, V_z) #, nz_init=nz_init.T)
nz, N_wall, N_div, N_pump, N_ret, N_tsu, N_dsu, N_dsul, rcld_rate, rclw_rate = out
res_Ca = {'nz': nz, 'time': aurora_dict_Ca['time_out'], 'rV': aurora_dict_Ca['radius_grid'], 
       'rhop': aurora_dict_Ca['rhop_grid'], 'ne':aurora_dict_Ca['ne'], 'Te':aurora_dict_Ca['Te']}
res_Ca['rad'] = aurora.radiation.compute_rad('Ca', res_Ca['rhop'], res_Ca['time'], res_Ca['nz'], 
                                            res_Ca['ne'],res_Ca['Te'], prad_flag=True, thermal_cx_rad_flag=False, 
                                            spectral_brem_flag=False, sxr_flag=False, 
                                            main_ion_brem_flag=False)

out = aurora.utils.run_aurora(aurora_dict_Ar, times_DV, D_z, V_z) #, nz_init=nz_init.T)
nz, N_wall, N_div, N_pump, N_ret, N_tsu, N_dsu, N_dsul, rcld_rate, rclw_rate = out
res_Ar = {'nz': nz, 'time': aurora_dict_Ar['time_out'], 'rV': aurora_dict_Ar['radius_grid'], 
       'rhop': aurora_dict_Ar['rhop_grid'], 'ne':aurora_dict_Ar['ne'], 'Te':aurora_dict_Ar['Te']}
res_Ar['rad'] = aurora.radiation.compute_rad('Ar', res_Ar['rhop'], res_Ar['time'], res_Ar['nz'], 
                                            res_Ar['ne'],res_Ar['Te'], prad_flag=True, thermal_cx_rad_flag=False, 
                                            spectral_brem_flag=False, sxr_flag=False, 
                                            main_ion_brem_flag=False)


# ----------------------
# plot charge state distributions over radius and time
aurora.plot_tools.slider_plot(res_Ar['rV'], res_Ar['time'], res_Ar['nz'].transpose(1,2,0), xlabel=r'$r_V$ [cm]', ylabel='time [s]', zlabel='nz [A.U.]', labels=[fr'Ar$^{{{i}}}$$^+$' for i in np.arange(0,res_Ar['nz'].shape[1])], plot_sum=True, x_line=aurora_dict_Ca['rvol_lcfs'])

aurora.plot_tools.slider_plot(res_Ca['rV'], res_Ca['time'], res_Ca['nz'].transpose(1,2,0), xlabel=r'$r_V$ [cm]', ylabel='time [s]', zlabel='nz [A.U.]', labels=[fr'Ca$^{{{i}}}$$^+$' for i in np.arange(0,res_Ca['nz'].shape[1])], plot_sum=True)


# plot radiation profiles over radius and time
aurora.plot_tools.slider_plot(res_Ca['rV'], res_Ca['time'], res_Ca['rad']['impurity_radiation'].transpose(1,2,0)[:nz.shape[1],:,:], xlabel=r'$r_V$ [cm]', ylabel='time [s]', zlabel='Total radiation [A.U.]', labels=['Ca'+str(i) for i in np.arange(0,nz.shape[1])], plot_sum=True, x_line=aurora_dict_Ca['rvol_lcfs'])


# Peaking factor
nz_Ca_tot = np.sum(res_Ca['nz'][-1],axis=0)
indLCFS = np.argmin(np.abs(aurora_dict_Ca['rhop_grid'] - 1.0))
nz_Ca_tot_volavg = aurora.coords.vol_average(nz_Ca_tot[:indLCFS], aurora_dict_Ca['rhop_grid'][:indLCFS], geqdsk=geqdsk)[-1]
Psi_n = aurora.coords.rad_coord_transform(rhop, 'rhop','psin', geqdsk)
ind_psin02 = np.argmin(np.abs(Psi_n - 0.2))
peaking = nz_Ca_tot[ind_psin02]/nz_Ca_tot_volavg
