//============================================================================//
//
// LPI 3D deck - Linearly polarized (in y) plane wave incident from left
//               boundary
//
// Adapted from Albright's Lightning 3D LPI deck.
//
// B. Albright, X-1-PTA; 28 Jan. 2007
// Lin Yin, X-1-PTA, 23 Feb 2009, for Cerrillos test
// B. Albright, XTD-PRI, 10 Jan. 2017, for Trinity test
// B. Albright, XTD-PRI, 30 Aug. 2017, for Coral II test
// B. Albright, XTD-PRI, 30 Nov. 2017, for Coral II test - redone for 3D
//
// Executable creates its own directory structure.  Remove the old with:
//
// rm -rf rundata ehydro Hhydro Hehydro restart poynting velocity particle
//        field
//============================================================================//

//----------------------------------------------------------------------------//
//
//----------------------------------------------------------------------------//

begin_globals
{
  int quota_check_interval;    // how often to check if quota exceeded
  int rtoggle;                 // enable save of last 2 restart files for safety
  int load_particles;          // were particles loaded?
  int mobile_ions;
  int H_present;
  int He_present;

  double e0;                   // peak amplitude of oscillating electric field
  double omega;                // angular freq. of the beam
  double quota_sec;            // run quota in sec
  double topology_x;           // domain topology needed to normalize Poynting diagnostic
  double topology_y;
  double topology_z;

  // Parameters for 3d Gaussian wave launch.
  double lambda;
  double waist;                // how wide the focused beam is
  double width;
  double zcenter;              // center of beam at boundary in z
  double ycenter;              // center of beam at boundary in y
  double xfocus;               // how far from boundary to focus
  double mask;                 // # gaussian widths from beam center where I is nonzero
};

//----------------------------------------------------------------------------//
//
//----------------------------------------------------------------------------//

begin_initialization
{
  // System of units.
  double ec         = 4.8032e-10;          // stat coulomb
  double c_vac      = 2.99792458e10;       // cm/sec
  double m_e        = 9.1094e-28;          // g
  double k_b        = 1.6022e-12;          // erg/eV
  double mec2       = m_e*c_vac*c_vac/k_b;
  double mpc2       = mec2*1836.0;

  double cfl_req    = 0.98;                // How close to Courant should we try to run
  double damp       = 0;                   // How much radiation damping
  double iv_thick   = 2;                   // Thickness of impermeable vacuum (in cells)

  // Experimental parameters.

  double t_e               = 600;          // electron temperature, eV
  double t_i               = 150;          // ion temperature, eV
  double n_e_over_n_crit   = 0.05;         // n_e/n_crit
  double vacuum_wavelength = 527 * 1e-7;   // third micron light (cm)
  double laser_intensity   = 2.5e15 * 1e7; // in ergs/cm^2 (note: 1 W = 1e7 ergs)

  // Simulation parameters.

  double nppc               = {{vpic_input.nppc}};        // Average number of particles/cell in ea. species
  int load_particles        = 1;                   // Flag to turn on/off particle load
  int mobile_ions           = {{vpic_input.mobile_ions}}; // Whether or not to push ions

  int He_present            = 1;
  int H_present             = 1;

  double f_He               = 0.5;                 // Ratio of number density of He to total ion density
  if (f_He == 1) H_present  = 0;

  double f_H                = 1-f_He;              // Ratio of number density of H  to total ion density
  if (f_H == 1 ) He_present = 0;

  // Here _He is actually N3+ to match Montgomery's Trident laser lpi experiment.

  // Precompute some useful variables.
  double A_H                = 1;
  double Z_H                = 1;
  double mic2_H             = mpc2*A_H;
  double mime_H             = mic2_H /mec2;
  double uthi_H             = sqrt(t_i/mic2_H);   // vthi/c for H

  double A_He               = 14;
  double Z_He               = 3;
  double mic2_He            = mpc2*A_He;
  double mime_He            = mic2_He/mec2;
  double uthi_He            = sqrt(t_i/mic2_He);  // vthi/c for He

  double uthe               = sqrt(t_e/mec2);     // vthe/c

  // Plasma skin depth in cm.
  double delta = (vacuum_wavelength / (2*M_PI) ) / sqrt( n_e_over_n_crit );

  double n_e   = c_vac*c_vac*m_e/(4*M_PI*ec*ec*delta*delta); // electron density in cm^-3
  double debye = uthe*delta;                      // electron Debye length (cm)
  double omega = sqrt( 1/n_e_over_n_crit );       // laser beam freq. in wpe

  // Box size for a single node.
  double box_size_x        = {{vpic_input.nx_sn}} * ( 0.06 * 120.0 * 1e-4 /  6.0 ) / 96;
  double box_size_y        = {{vpic_input.ny_sn}} * ( 0.06 * 120.0 * 1e-4 / 24.0 ) / 24;
  double box_size_z        = {{vpic_input.nz_sn}} * ( 0.06 * 120.0 * 1e-4 / 24.0 ) / 24;

  // Scale box size for single node to adjust single node memory footprint.
  box_size_x              *= {{vpic_input.ssize_x}};
  box_size_y              *= {{vpic_input.ssize_y}};
  box_size_z              *= {{vpic_input.ssize_z}};

  // Scale box size for multiple nodes.
  box_size_x              *= {{vpic_input.snodes_x}};
  box_size_y              *= {{vpic_input.snodes_y}};
  box_size_z              *= {{vpic_input.snodes_z}};

  // Grid size for a single node.
  double nx                = {{vpic_input.nx_sn}};
  double ny                = {{vpic_input.ny_sn}};
  double nz                = {{vpic_input.nz_sn}};

  // Scale grid size for single node to adjust single node memory footprint.
  nx                      *= {{vpic_input.ssize_x}};
  ny                      *= {{vpic_input.ssize_y}};
  nz                      *= {{vpic_input.ssize_z}};

  // Scale grid size for multiple nodes.
  nx                      *= {{vpic_input.snodes_x}};
  ny                      *= {{vpic_input.snodes_y}};
  nz                      *= {{vpic_input.snodes_z}};

  // Topology for a single node.
  double topology_x        = {{vpic_input.nranks_x}};
  double topology_y        = {{vpic_input.nranks_y}};
  double topology_z        = {{vpic_input.nranks_z}};

  // Scale topology for multiple nodes.
  topology_x              *= {{vpic_input.snodes_x}};
  topology_y              *= {{vpic_input.snodes_y}};
  topology_z              *= {{vpic_input.snodes_z}};

  double hx                = box_size_x / ( delta * nx ); // in c/wpe
  double hy                = box_size_y / ( delta * ny );
  double hz                = box_size_z / ( delta * nz );

  double cell_size_x       = hx * delta / debye;  // Cell size in Debye lengths
  double cell_size_y       = hy * delta / debye;
  double cell_size_z       = hz * delta / debye;

  double Lx                = nx * hx;           // in c/wpe
  double Ly                = ny * hy;
  double Lz                = nz * hz;

  double f_number          = 6;                   // f/# of beam
  double lambda            = vacuum_wavelength/delta; // vacuum wavelength in c/wpe
  double waist             = f_number*lambda;     // width of beam at focus in c/wpe
  double xfocus            = Lx/2;                // in c/wpe
  double ycenter           = 0;                   // center of spot in y on lhs boundary
  double zcenter           = 0;                   // center of spot in z on lhs boundary
  double mask              = 1.5;                 // set drive I=0 outside r>mask*width at lhs boundary
  double width = waist*sqrt( 1 + (lambda*xfocus/(M_PI*waist*waist))*(lambda*xfocus/(M_PI*waist*waist)));

  // Peak instantaneous E field in "natural units"
  double e0                = sqrt( 2*laser_intensity / (m_e*c_vac*c_vac*c_vac*n_e) );
  e0                       = e0*(waist/width);     // at entrance (3D Gaussian)
//e0                       = e0*sqrt(waist/width); // at entrance (2D Gaussian)

  double dt                = cfl_req*courant_length(Lx,Ly,Lz,nx,ny,nz); // in 1/wpe; n.b. c=1 in nat. units
  double nsteps_cycle      = trunc_granular(2*M_PI/(dt*omega),1)+1;
  dt                       = 2*M_PI/omega/nsteps_cycle; // nsteps_cycle time steps in one laser cycle

  double t_stop            = {{vpic_input.nstep}}*dt + 0.001*dt; // Runtime in 1/wpe

  int quota_check_interval = 20;
  double quota_sec         = 23.7*3600;           // Run quota in sec.

  // Work through this to make sure I understand it.
  double N_e               = nppc*nx*ny*nz;       // Number of macro electrons in box
  double Np_e              = Lx*Ly*Lz;            // "Number" of "physical" electrons in box (nat. units)
  double q_e               = -Np_e/N_e;           // Charge per macro electron
  double N_i               = N_e;                 // Number of macro ions of each species in box
  double Np_i              = Np_e/(Z_H*f_H+Z_He*f_He); // "Number" of "physical" ions of each sp. in box
  double qi_H              = Z_H *f_H *Np_i/N_i;  // Charge per H  macro ion
  double qi_He             = Z_He*f_He*Np_i/N_i;  // Charge per He macro ion
//double qi_He             = Np_i/N_i;            // Charge per He macro ion

  // Print simulation parameters.

  sim_log( "***** Simulation parameters *****" );
  sim_log( "* Processors:                     " << nproc() );
  sim_log( "* Topology:                       " << topology_x << " " << topology_y << " " << topology_z );
  sim_log( "* nsteps_cycle =                  " << nsteps_cycle );
  sim_log( "* Time step, max time, nsteps:    " << dt << " " << t_stop << " " << int( t_stop / (dt) ) );
  sim_log( "* Debye length, XYZ cell sizes:   " << debye << " " << cell_size_x << " " << cell_size_y << " " << cell_size_z );
  sim_log( "* Real cell sizes (in Debyes):    " << hx/uthe << " " << hy/uthe << " " << hz/uthe );
  sim_log( "* Lx, Ly, Lz =                    " << Lx << " " << Ly << " " << Lz );
  sim_log( "* nx, ny, nz =                    " << nx << " " << ny << " " << nz );
  sim_log( "* Charge/macro electron =         " << q_e );
  sim_log( "* Average particles/processor:    " << N_e / nproc() );
  sim_log( "* Average particles/cell:         " << nppc );
  sim_log( "* Omega_0, Omega_pe:              " << omega << " " << 1 );
  sim_log( "* Plasma density, ne/nc:          " << n_e << " " << n_e_over_n_crit );
  sim_log( "* Vac wavelength (nm):            " << vacuum_wavelength * 1e7 );
  sim_log( "* I_laser (W/cm^2):               " << laser_intensity / 1e7 );
  sim_log( "* T_e, T_i (eV)                   " << t_e << " " << t_i );
  sim_log( "* m_e, m_H, m_He                  " << "1 " << mime_H << " " << mime_He );
  sim_log( "* Radiation damping:              " << damp );
  sim_log( "* Fraction of courant limit:      " << cfl_req );
  sim_log( "* vthe/c:                         " << uthe );
  sim_log( "* vthi_H /c:                      " << uthi_H );
  sim_log( "* vthi_He/c:                      " << uthi_He );
  sim_log( "* emax at entrance:               " << e0 );
  sim_log( "* emax at waist:                  " << e0 / ( waist / width ) );
  sim_log( "* num vacuum edge grids:          " << iv_thick );
  sim_log( "* width, waist, xfocus:           " << width << " " << waist << " " << xfocus );
  sim_log( "* ycenter, zcenter, mask:         " << ycenter << " " << zcenter << " " << mask );
  sim_log( "* quota check interval:           " << quota_check_interval );
  sim_log( "* Number macro eons:              " << N_e );
  sim_log( "* Number macro ions, each:        " << N_i );
  sim_log( "* Number physical eons:           " << Np_e );
  sim_log( "* Number physical ions, each:     " << Np_i );
  sim_log( "* Charge per macro eon:           " << q_e );
  sim_log( "* Charge per macro ion, H:        " << qi_H );
  sim_log( "* Charge per macro ion, He:       " << qi_He );
  sim_log( "*********************************" );

  // Set up high level simulation parameters.

  sim_log( "Setting up high-level simulation parameters." );
  num_step             = int( t_stop / (dt) );

  status_interval      = {{vpic_input.status_interval}};
  sync_shared_interval = {{vpic_input.sync_shared_interval}};
  clean_div_e_interval = {{vpic_input.clean_div_e_interval}};
  clean_div_b_interval = {{vpic_input.clean_div_b_interval}};

  // status_interval      = 200;
  // sync_shared_interval = status_interval/1;
  // clean_div_e_interval = status_interval/1;
  // clean_div_b_interval = status_interval/10;

  // For maxwellian reinjection, we need more than the default number of
  // passes (3) through the boundary handler
  // Note:  We have to adjust sort intervals for maximum performance on Cell.
  // Note: On 1 PE fails after 2094 steps. Increasing num_comm_round to 10
  // allows it to run > 25,000 steps.
  num_comm_round = 6;

  global->e0                     = e0;
  global->omega                  = omega;
  global->quota_check_interval   = quota_check_interval;
  global->quota_sec              = quota_sec;
  global->rtoggle                = 0;
  global->load_particles         = load_particles;
  global->mobile_ions            = mobile_ions;
  global->H_present              = H_present;
  global->He_present             = He_present;
  global->topology_x             = topology_x;
  global->topology_y             = topology_y;
  global->topology_z             = topology_z;
  global->xfocus                 = xfocus;
  global->ycenter                = ycenter;
  global->zcenter                = zcenter;
  global->mask                   = mask;
  global->waist                  = waist;
  global->width                  = width;
  global->lambda                 = lambda;

  // Set up the species. Allow additional local particles in case of
  // non-uniformity.

  // Set up grid.
  sim_log( "Setting up computational grid." );

  grid->dx       = hx;
  grid->dy       = hy;
  grid->dz       = hz;
  grid->dt       = dt;
  grid->cvac     = 1;
  grid->eps0     = 1;

  sim_log( "Setting up periodic mesh." );

  define_periodic_grid( 0,         -0.5*Ly,    -0.5*Lz,         // Low corner
                        Lx,         0.5*Ly,     0.5*Lz,         // High corner
                        nx,         ny,         nz,             // Resolution
                        topology_x, topology_y, topology_z );   // Topology

  int use_maxwellian_reflux_bc = {{vpic_input.maxwellian_reflux_bc}};

  if ( use_maxwellian_reflux_bc == 1 )
  {
    // From grid/partition.c: used to determine which domains are on edge.

    #define RANK_TO_INDEX(rank,ix,iy,iz) BEGIN_PRIMITIVE {                  \
      int _ix, _iy, _iz;                                                    \
      _ix  = (rank);                        /* ix = ix+gpx*( iy+gpy*iz ) */ \
      _iy  = _ix/int(global->topology_x);   /* iy = iy+gpy*iz            */ \
      _ix -= _iy*int(global->topology_x);   /* ix = ix                   */ \
      _iz  = _iy/int(global->topology_y);   /* iz = iz                   */ \
      _iy -= _iz*int(global->topology_y);   /* iy = iy                   */ \
      (ix) = _ix;                                                           \
      (iy) = _iy;                                                           \
      (iz) = _iz;                                                           \
    } END_PRIMITIVE

    // Override and make field absorbing grid on boundaries.

    int ix, iy, iz;                    // Domain location in mesh.

    RANK_TO_INDEX( int( rank() ), ix, iy, iz ); 

    if ( ix == 0 )                     // Left boundary.
    {
      set_domain_field_bc( BOUNDARY(-1,0,0), absorb_fields );
    }

    if ( ix == topology_x - 1 )        // Right boundary.
    {
      set_domain_field_bc( BOUNDARY( 1,0,0), absorb_fields );
    }

    if ( iy == 0 )                     // Front boundary.
    {
      set_domain_field_bc( BOUNDARY(0,-1,0), absorb_fields );
    }

    if ( iy == topology_y - 1 )        // Back boundary.
    {
      set_domain_field_bc( BOUNDARY(0, 1,0), absorb_fields );
    }

    if ( iz == 0 )                     // Top boundary.
    {
      set_domain_field_bc( BOUNDARY(0,0,-1), absorb_fields );
    }

    if ( iz == topology_z - 1 )        // Bottom boundary.
    {
      set_domain_field_bc( BOUNDARY(0,0, 1), absorb_fields );
    }
  }

  sim_log( "Setting up species." );

  // double max_local_np = 1.5 * N_e / nproc();

  double max_local_np = ({{vpic_input.max_local_np_scale}} * N_e) / nproc();

  double max_local_nm = max_local_np / 10.0;

  species_t *electron = define_species( "electron",
					-1,
					1,
					max_local_np,
					max_local_nm,
					{{vpic_input.eon_sort_interval}},
					{{vpic_input.eon_sort_method}} );

  // Start with two ion species.  We have option to go to Xe and Kr gas fills if
  // we need a higher ion/electron macroparticle ratio.

  species_t *ion_H, *ion_He;

  if ( mobile_ions )
  {
    if ( H_present )
    {
      ion_H  = define_species( "H",
			       Z_H,
			       mime_H,
			       max_local_np,
			       max_local_nm,
			       {{vpic_input.ion_sort_interval}},
			       {{vpic_input.ion_sort_method}} );
    }

    if ( He_present )
    {
      ion_He = define_species( "He",
			       Z_He,
			       mime_He,
			       max_local_np,
			       max_local_nm,
			       {{vpic_input.ion_sort_interval}},
			       {{vpic_input.ion_sort_method}} );
    }
  }

  particle_bc_t *maxwellian_reinjection;
  if ( use_maxwellian_reflux_bc == 1 )
  {
    // Turn on maxwellian reinjection particle boundary condition.

    sim_log( "Overriding x boundaries to absorb fields." );

    // Set up Maxwellian reinjection B.C.

    sim_log( "Setting up Maxwellian reinjection boundary condition." );

    // particle_bc_t *maxwellian_reinjection =
    //   define_particle_bc( maxwellian_reflux( species_list, entropy ) );

    maxwellian_reinjection =
      define_particle_bc( maxwellian_reflux( species_list, entropy ) );

    set_reflux_temp( maxwellian_reinjection,
		     electron,
		     uthe,
		     uthe );

    if ( mobile_ions )
    {
      if ( H_present )
      {
	set_reflux_temp( maxwellian_reinjection,
			 ion_H,
			 uthi_H,
			 uthi_H );
      }

      if ( He_present )
      {
	set_reflux_temp( maxwellian_reinjection,
			 ion_He,
			 uthi_He,
			 uthi_He );
      }
    }
  }

  // Set up materials.

  sim_log( "Setting up materials." );

  define_material( "vacuum", 1 );

  define_field_array( NULL, damp );

  if ( use_maxwellian_reflux_bc == 1 )
  {
    // Turn on impermeable vacuum layer.

    // Paint the simulation volume with materials and boundary conditions.

    #define iv_region ( x <         hx*iv_thick || \
                        x >  Lx   - hx*iv_thick || \
                        y < -Ly/2 + hy*iv_thick || \
       	                y >  Ly/2 - hy*iv_thick || \
                        z < -Lz/2 + hz*iv_thick || \
                        z >  Lz/2 - hz*iv_thick ) // All boundaries are i.v.

    set_region_bc( iv_region,
		   maxwellian_reinjection,
		   maxwellian_reinjection,
		   maxwellian_reinjection );
  }

  // Load particles.

  if ( load_particles )
  {
    sim_log( "Loading particles." );

    // Fast load of particles. Do not bother fixing artificial domain correlations.

    double xmin = grid->x0, xmax = grid->x1;
    double ymin = grid->y0, ymax = grid->y1;
    double zmin = grid->z0, zmax = grid->z1;

    repeat( N_e / ( topology_x * topology_y * topology_z ) )
    {
      double x = uniform( rng(0), xmin, xmax );
      double y = uniform( rng(0), ymin, ymax );
      double z = uniform( rng(0), zmin, zmax );

      if ( use_maxwellian_reflux_bc == 1 )
      {
	if ( iv_region )    // Particle fell in iv_region.  Do not load.
        {
	  continue;
	}
      }

      // Third to last arg is "weight", a positive number.

      inject_particle( electron,
		       x,
		       y,
		       z,
                       normal( rng(0), 0, uthe ),
                       normal( rng(0), 0, uthe ),
                       normal( rng(0), 0, uthe ),
		       -q_e,
		       0,
		       0 );

      if ( mobile_ions )
      {
        if ( H_present )  // Inject an H macroion on top of macroelectron.
	{
          inject_particle( ion_H,
			   x,
			   y,
			   z,
                           normal( rng(0), 0, uthi_H ),
                           normal( rng(0), 0, uthi_H ),
                           normal( rng(0), 0, uthi_H ),
			   qi_H,
			   0,
			   0 );
	}

        if ( He_present ) // Inject an He macroion on top of macroelectron.
	{
          inject_particle( ion_He,
			   x,
			   y,
			   z,
                           normal( rng(0), 0, uthi_He ),
                           normal( rng(0), 0, uthi_He ),
                           normal( rng(0), 0, uthi_He ),
			   qi_He,
			   0,
			   0 );
	}
      }
    }
  }

  //--------------------------------------------------------------------------//
  // Wrapup initialization.
  //--------------------------------------------------------------------------//

  sim_log( "*** Finished with user-specified initialization. ***" );

  //--------------------------------------------------------------------------//
  // Upon completion of the initialization, the following occurs:
  //
  // - The synchronization error (tang E, norm B) is computed between domains
  //   and tang E / norm B are synchronized by averaging where discrepancies
  //   are encountered.
  // - The initial divergence error of the magnetic field is computed and
  //   one pass of cleaning is done (for good measure)
  // - The bound charge density necessary to give the simulation an initially
  //   clean divergence e is computed.
  // - The particle momentum is uncentered from u_0 to u_{-1/2}
  // - The user diagnostics are called on the initial state
  // - The physics loop is started
  //
  // The physics loop consists of:
  //
  // - Advance particles from x_0,u_{-1/2} to x_1,u_{1/2}
  // - User particle injection at x_{1-age}, u_{1/2} (use inject_particles)
  // - User current injection (adjust field(x,y,z).jfx, jfy, jfz)
  // - Advance B from B_0 to B_{1/2}
  // - Advance E from E_0 to E_1
  // - User field injection to E_1 (adjust field(x,y,z).ex,ey,ez,cbx,cby,cbz)
  // - Advance B from B_{1/2} to B_1
  // - (periodically) Divergence clean electric field
  // - (periodically) Divergence clean magnetic field
  // - (periodically) Synchronize shared tang e and norm b
  // - Increment the time step
  // - Call user diagnostics
  // - (periodically) Print a status message
  //--------------------------------------------------------------------------//
}

//----------------------------------------------------------------------------//
// Definition of user_diagnostics function.
//----------------------------------------------------------------------------//

begin_diagnostics
{
  //--------------------------------------------------------------------------//
  // Begin diagnostics.
  //--------------------------------------------------------------------------//

  if ( step()%200 == 0 )
  {
    sim_log( "Time step: " << step() );
  }

  //--------------------------------------------------------------------------//
  // Shut down simulation when wall clock time exceeds global->quota_sec.
  // Note that the mp_elapsed() is guaranteed to return the same value for all
  // processors (i.e., elapsed time on proc #0), and therefore the abort will
  // be synchronized across processors. Note that this is only checked every
  // few timesteps to eliminate the expensive mp_elapsed call from every
  // timestep. mp_elapsed has an ALL_REDUCE in it.
  //--------------------------------------------------------------------------//

  if ( ( step() > 0 &&
	 global->quota_check_interval > 0 &&
	 ( step() % global->quota_check_interval ) == 0 ) )
  {
    if ( uptime() > global->quota_sec )
    {
      sim_log( "Allowed runtime exceeded for this job. Terminating." );

      mp_barrier(); // Just to be safe

      halt_mp();

      exit(0);
    }
  }

  //--------------------------------------------------------------------------//
  // Done with diagnostics.
  //--------------------------------------------------------------------------//
}

//----------------------------------------------------------------------------//
//
//----------------------------------------------------------------------------//

begin_field_injection
{
// Turn off field injection for performance testing.

#if 0 // 3D
  // Inject a light wave from lhs boundary with E aligned along y. Use scalar
  // diffraction theory for the Gaussian beam source. (This is approximate).
  //
  // For quiet startup (i.e., so that we don't propagate a delta-function
  // noise pulse at time t=0) we multiply by a constant phase term exp(i phi)
  // where:
  //   phi = k*global->xfocus+atan(h)    (3d)
  //
  // Inject from the left a field of the form ey = e0 sin( omega t )

# define DY    ( grid->y0 + (iy-0.5)*grid->dy - global->ycenter )
# define DZ    ( grid->z0 + (iz-1  )*grid->dz - global->zcenter )
# define R2    ( DY*DY + DZ*DZ )
# define PHASE ( global->omega*t + h*R2/(global->width*global->width) )
# define MASK  ( R2<=pow(global->mask*global->width,2) ? 1 : 0 )

  if ( grid->x0 == 0 )               // Node is on left boundary
  {
    double alpha      = grid->cvac*grid->dt/grid->dx;
    double emax_coeff = (4/(1+alpha))*global->omega*grid->dt*global->e0;
    double prefactor  = emax_coeff*sqrt(2/M_PI);
    double t          = grid->dt*step();

    // Compute Rayleigh length in c/wpe
    double rl         = M_PI*global->waist*global->waist/global->lambda;

    double pulse_shape_factor = 1;
    float pulse_length        = 70;                // units of 1/wpe
    float sin_t_tau           = sin( 0.5 * t * M_PI / pulse_length );
    pulse_shape_factor        = ( t < pulse_length ? sin_t_tau : 1 );
    double h                  = global->xfocus/rl; // Distance / Rayleigh length

    // Loop over all Ey values on left edge of this node
    for( int iz = 1; iz <= grid->nz + 1; ++iz )
    {
      for( int iy = 1; iy <= grid->ny; ++iy )
      {
        field( 1, iy, iz ).ey += prefactor
                                 * cos(PHASE)
                                 * exp( -R2 / ( global->width*global->width ) )
                                 * MASK * pulse_shape_factor;
      }
    }
  }
#endif

#if 0 // 2D
  // Inject a light wave from lhs boundary with E aligned along y. Use scalar
  // diffraction theory for the Gaussian beam source. (This is approximate).
  //
  // For quiet startup (i.e., so that we don't propagate a delta-function
  // noise pulse at time t=0) we multiply by a constant phase term exp(i phi)
  // where:
  //   phi = k*global->xfocus+atan(h)    (3d)
  //
  // Inject from the left a field of the form ey = e0 sin( omega t )

# define DY    ( grid->y0 + (iy-0.5)*grid->dy - global->ycenter )
# define DZ    ( grid->z0 + (iz-1  )*grid->dz - global->zcenter )
# define R2Z   ( DZ*DZ )
# define PHASE ( -global->omega*t + h*R2Z/(global->width*global->width) )
# define MASK  ( R2Z<=pow(global->mask*global->width,2) ? 1 : 0 )

  if ( grid->x0 == 0 )               // Node is on left boundary
  {
    double alpha      = grid->cvac*grid->dt/grid->dx;
    double emax_coeff = (4/(1+alpha))*global->omega*grid->dt*global->e0;
    double prefactor  = emax_coeff*sqrt(2/M_PI);
    double t          = grid->dt*step();

    // Compute Rayleigh length in c/wpe
    double rl         = M_PI*global->waist*global->waist/global->lambda;

    double pulse_shape_factor = 1;
    float pulse_length        = 70;                // units of 1/wpe
    float sin_t_tau           = sin( 0.5 * t * M_PI / pulse_length );
    pulse_shape_factor        = ( t < pulse_length ? sin_t_tau : 1 );
    double h                  = global->xfocus/rl; // Distance / Rayleigh length

    // Loop over all Ey values on left edge of this node
    for( int iz = 1; iz <= grid->nz + 1; ++iz )
    {
      for( int iy = 1; iy <= grid->ny; ++iy )
      {
        field( 1, iy, iz ).ey += prefactor
                                 * cos(PHASE)
                                 * exp( -R2Z / ( global->width*global->width ) ) // 2D
                                 * MASK * pulse_shape_factor;
      }
    }
  }
#endif
}

//----------------------------------------------------------------------------//
//
//----------------------------------------------------------------------------//

begin_particle_injection
{
  // No particle injection for this simulation.
}

//----------------------------------------------------------------------------//
//
//----------------------------------------------------------------------------//

begin_current_injection
{
  // No current injection for this simulation.
}

//----------------------------------------------------------------------------//
//
//----------------------------------------------------------------------------//

begin_particle_collisions
{
  // No particle collisions for this simulation.
}
