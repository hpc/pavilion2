#! /bin/bash 

version (){
   echo " 
 ${0/\.\/} v0.5:      Runscript for Intel MPI Benchmarks Suite
 Maintained at:       git@git.lanl.gov:hpctest/IMB.git                                               
 Files:                                                                             
    parseIMB.py       Parse output file emitted by IMB for key=value pair results output            
    IMB.xml           XML dashboard definition for results graphing within Splunk                                        
    imb.yaml          Pavilion imb configuration .yaml file                                
    IMB_2017.tgz      https://software.intel.com/sites/default/files/managed/a3/53/IMB_2017.tgz      
    README            Usage, disclaimers, and other information                                      
 Primary developer:   jgreen@lanl.gov                                                                
 Bugs & Suggestions:  hpctest@lanl.gov
"        
   exit 1
}

usage (){
  echo "Usage: $0 is intended to run a IMB Benchmark suite.
  Pass key=value arguments to the script in a standalone test instance
  inside of a batch job running on a TOSS cluster.
  Values dictate the build and runtime settings of the test.
  Keys permitted in this test are:
    compiler            --name and version of an available compiler in the form: intel/16.0.3
    mpi                 --name and version of an available mpi library in the form: openmpi/1.6.5
    imbtest             --name of a IMB benchmark to run
    tarball             --name of the source archive for the IMB test, e.g.: IMB_2017.tgz
    gettarball          --instruct the script to attempt to wget the tarball
    imbtest_options     --options you wish to pass to the IMB test
    mpirun_options      --options that are used by OpenMPIs mpirun command to control task and threading
                        --usage:  mpirun_options=map-by;core
    intelmpirun_options --options used by Intel MPI's mpirun command to control task and threading
    mpiruncmd           --which parallel launcher do you want to use (optional), e.g. mpirun, srun, aprun
    target              --which executable do you want to generate within the IMB test suite
    arch                --which architecture to run on.  Options are: 'mic-knl' and 'haswell' on trinitite.
    version             --information about this test 
"
  exit 1
}

if [[ $@ ]]; then 
  export PV_TEST_ARGS=$@
fi 

############################################
# Function definitions to keep stuff clean #
############################################
die () { 
  # Keeps error handling easy
  echo "<Results> FAILED"
  echo "Error: $1" 
  if [[ ! $DEBUG ]]; then 	
    exit 9
  fi 	
}

untar () {
  # Untar the IMB tarball if need be
  if [[ -e ${1} ]] ; then 
     tar -xzf ${1}
     if [[ $? != 0 ]] ; then
       die "untar failed"
     fi
  else
     die "ERROR: ${1} cannot be found" 
  fi 
}

moduleinit () {
  # Initialize Modulefiles Package
  if [ -e /usr/share/Modules/init/bash ] ; then 
    source /usr/share/Modules/init/bash &>/dev/null 
    echo $? 
  elif [ -e /usr/share/lmod/lmod/init/bash ] ; then 
    source /usr/share/lmod/lmod/init/bash &>/dev/null 
    echo $? 
  elif [ -e /opt/modules/default/init/bash ] ; then
    source /opt/modules/default/init/bash &>/dev/null
    echo $? 
  elif [[ $( which modulecmd ) || $( which module ) ]]; then 
    echo "Module is in my path" 
    echo $? 
  else 
    die "Module command isn't in my path, nor are init files found on the system. Exiting" 
  fi   
}

sysname () { 
  # set machine name
  if [[ -x /usr/projects/hpcsoft/utilities/bin/sys_name ]]; then
    machine=`/usr/projects/hpcsoft/utilities/bin/sys_name`
  else
    machine=`hostname -s`
  fi
}

sysos () {
  # set os name
  if [[ -x /usr/projects/hpcsoft/utilities/bin/sys_os ]] ; then
    os=`/usr/projects/hpcsoft/utilities/bin/sys_os`
  else
    os=`uname -smp|sed 's/ /-/g'`
  fi
} 

dirnameIMB () {
  # determine the top level directory the tarball unpacks
  tarball=${1}
  # dirname=$(tar tzf $tarball | head -1 | cut -f1 -d"/")
  dirname="imb"
} 

parallelLauncher () {
  mpi=${1}
  mpiruncmd=srun
#  if [[ ! ${mpiruncmd} ]] ; then
#    if  ([[ ${mpi} != mvapich2* ]] && [[ ${mpi} != cray-mpich* ]]); then
#      mpiruncmd=$( which mpirun )
#    elif [[ ${mpi} == mvapich2* ]] ; then
#      mpiruncmd=$( which srun ) 
#    elif [[ ${mpi} == cray-mpich* ]] ; then
#      mpiruncmd=$( which aprun )
#    else
#      die "Exhausted all parallel launcher options."
#    fi
#  fi   
}
           
# Variables with defaults in case the code is run outside of the scope of Pavilion
test_name=${PV_TESTNAME:-"imb"}
test_args=${PV_TEST_ARGS:-"imbtest=pingpong tarball=IMB_2017.tgz compiler=gcc mpi=openmpi mpiruncmd=srun"}
#test_args=${PV_TEST_ARGS:-"imbtest=alltoall tarball=IMB_2017.tgz compiler=intel mpi=openmpi mpiruncmd=mpirun DEBUG=True"}
runhome=${runhome:-$PWD}
declare -a MPIRUN_OPTIONS 
declare -a mpirun_parse_options
for element in ${test_args[@]}; do 
   if [ $BASH_VERSINFO -lt 4 ] ; then 
      element=$(echo $element|awk '{print tolower($0)}') 
   else
      element=${element,,}
   fi 
   case ${element} in
   imbtest=*) 
      imbtest=${element//imbtest=/}
      outfile=${imbtest}.out
      ;;
   compiler=*)
      compiler=${element//compiler=/}
      ;;
   mpi=*)
      mpi=${element//mpi=/}
      ;;
   arch=*)
      arch=${element//arch=/}
      ;;
   imbtest_options=*)
      imbtest_options=${element//imbtest_options=/}
      imbtest_options=${imbtest_options//;/ }
      ;;
   mpirun_options=*)
   ## goal is to provide the ability to pass multiple mpirun_options and deal with that
      mpirun_parse_options=( ${mpirun_parse_options[@]} ${element} ) 
      mpirun_options=${element//mpirun_options=/}
      mpirun_options=${mpirun_options//;/ }
      MPIRUN_OPTIONS=( ${MPIRUN_OPTIONS[@]} ${mpirun_options} )
      ;; 
   mpiruncmd=*)
   ## this permits a srun for OpenMPI if we want to test that functionality
      mpiruncmd=${element//mpiruncmd=/}
      ;;
   intelmpirun_options=*)
      intelmpirun_options=${element//intelmpirun_options=/}
      ;;
   target=*) 
   ## this arg will switch the Intel MPI benchmark executable.  Need to establish other fx here
      target=${element//target=/}
      ;; 
   debug*|DEBUG*)
      export DEBUG=True 
      ;; 
   *help*|*-h*)
      usage
      ;;
   version) 
      version
      ;;
   *) 
      echo "Error: $element isn't dealt with in this script; ignoring this test argument"
      ;;
   esac
done

if [[ $SLURM_JOBID ]] ; then 
   if [[ $SLURM_NTASKS ]] && [[ $SLURM_NNODES ]] ; then 
      nnodes=${PV_NNODES:-$SLURM_NNODES}
      npes=${PV_NPES:-$SLURM_NTASKS}
   elif [[ $SLURM_CPUS_ON_NODE ]] && [[ $SLURM_NNODES ]] ; then 
      nnodes=${PV_NNODES:-$SLURM_NNODES}
      npes=$(( SLURM_CPUS_ON_NODE * SLURM_NNODES )) 
   else
      die "Slurm environment doesn't define ntasks or nnodes properly"
   fi
elif [[ $PBS_JOBID ]] ; then 
   npes=${PV_NPES:-$PBS_NP}
   nnodes=${PV_NNODES:-$PBS_NUM_NODES}
else
   die "JOBID is not defined; this script should be run inside an allocation"
fi 

target=${target:="IMB-MPI1"}
imbtest_options=${imbtest_options:="-iter 1000,10000"}
cd ${runhome}
sysname
sysos

# need to set compiler/mpi defaults if they're not handled already elsewhere
if [[ ! $compiler ]] ; then
   compiler=gcc
fi 

if [[ ! $mpi ]] ; then 
   mpi=openmpi
fi 

# need to set a default imbtest value if not already set by args
if [[ ! $imbtest ]] ; then 
   imbtest='imb'
fi

# call moduleinit
err=$(moduleinit)
if [[ ${err} != 0 ]] && [ $DEBUG ]; then 
   die "\$(moduleinit) failed"
fi 

# call moduleload 
if [[ ${os:0:3} == "cle" ]] ; then 
   for name in ${LOADEDMODULES//:/ }
   do
      echo "Checking module $name"
      if [ "$name" == "craype-haswell" ] || [ "$name" == "craype-mic-knl" ]
      then
         echo "Swapping craype-${arch} in for $name"
         module swap $name "craype-${arch}"
         if [ $? -ne 0 ]
         then
            exit 1
         fi
      fi
   done
   case "${compiler}" in
     *intel*)
     ENV_REQ=${compiler}
     COMP_MOD=intel
     PE_MOD=intel
     ;;
     *gcc*|*gnu*)
     ENV_REQ=${compiler}
     COMP_MOD=gcc
     PE_MOD=gnu
     ;;
     *)
     ENV_REQ=${compiler}
     COMP_MOD=${compiler}
     PE_MOD=${compiler}
     ;;
   esac
   if [[ $(echo $PE_ENV|awk '{print tolower($0)}') != ${PE_MOD} ]] ; then  
     PE_OLD="$( echo ${PE_ENV} | awk '{print tolower($0)}' )"
     module swap PrgEnv-${PE_OLD} PrgEnv-${PE_MOD} &>/dev/null
   fi 
   module load friendly-testing deprecated sandbox &>/dev/null
   module swap ${compiler%/*} ${compiler} &>/dev/null
   module swap ${mpi%/*} ${mpi} &>/dev/null
   #module load openmpi/2.1.1
   if [ $PE_ENV == "GNU" ]
   then
      compiler="gcc"
      compilerver=$GNU_VERSION
   fi
   if [ $PE_ENV == "INTEL" ]
   then
      compiler="intel"
      compilerver=$INTEL_VERSION
   fi
   if [ $PE_ENV == "CRAY" ]
   then
      compiler="cray"
      compilerver=$CRAY_CC_VERSION
   fi
   ENV_VER="${ENV_REQ/*\//}"
   module list &>loadedmodules.out 
else   
   module purge &>/dev/null 
   module load friendly-testing deprecated sandbox &>/dev/null
   module load ${compiler:=gcc} &>/dev/null
   module load ${mpi:=openmpi} &>/dev/null
   module list &>loadedmodules.out 
   compilerver="$LCOMPILERVER"
   mpiver="$LMPIVER"
fi 

if ! [[ $( grep $compiler loadedmodules.out) ]] ; then 
   die "$compiler didn't load"
fi
if ! [[ $( grep $mpi loadedmodules.out) ]] ; then 
   die "$mpi didn't load"
fi 

# call function to determine if $mpiruncmd is passed via PV_TEST_ARGS/cmd line, else defaults
parallelLauncher $mpi $mpiruncmd

outfile="${runhome}/${imbtest}.out"
errfile="${runhome}/${imbtest}.err" 
if [ ${os:0:3} == "cle" ]
then
   basedir="/usr/projects/hpctest/${os}/${machine}/${arch:=mic-knl}/imb/v0.2-${compiler}-${compilerver}-${mpi/\/*/}-${mpi/*\//}"
fi
if [ ${os:0:4} == "toss" ]
then
   basedir="/usr/projects/hpctest/${os}/${machine}/imb/v0.2-${compiler/\/*/}-${compilerver}-${mpi/\/*/}-${mpiver}"
fi
IMB_MPI1="${basedir}/IMB-MPI1"
IMB_EXT="${basedir}/IMB-EXT"
IMB_IO="${basedir}/IMB-IO"
IMB_NBC="${basedir}/IMB-NBC"
IMB_RMA="${basedir}/IMB-RMA"

if [[ $DEBUG ]]; then
  echo "Executing $0 from $PWD" 
  echo "\$machine is $machine"
  echo "\$os is $os"
  echo "\$dirname is $dirname"
  echo "\$IMB_MPI1 is $IMB_MPI1" 
  echo "\$mpiruncmd is $mpiruncmd"
  echo "\$imbtest $imbtest"
  echo "\$imbtest_options $imbtest_options" 
  echo "\$MPIRUN_OPTIONS are ${MPIRUN_OPTIONS[@]}" 
  echo "\${npes} ${npes}"
  echo "\${runhome} ${runhome}" 
fi

case "${target}" in 
"imb-mpi1")
   ${mpiruncmd} -n ${npes} ${MPIRUN_OPTIONS[@]} ${IMB_MPI1} ${imbtest} ${imbtest_options} > ${outfile} 2> ${errfile} 
   ;;
"IMB-EXT")
   ${mpiruncmd} -n ${npes} ${MPIRUN_OPTIONS[@]} ${IMB_EXT} ${imbtest} ${imbtest_options} > ${outfile} 2> ${errfile} 
   ;;
"IMB_IO")
   ${mpiruncmd} -n ${npes} ${MPIRUN_OPTIONS[@]} ${IMB_IO} ${imbtest} ${imbtest_options} > ${outfile} 2> ${errfile} 
   ;;
"IMB_NBC")
   ${mpiruncmd} -n ${npes} ${MPIRUN_OPTIONS[@]} ${IMB_NBC} ${imbtest} ${imbtest_options} > ${outfile} 2> ${errfile} 
   ;;
"IMB_RMA")
   ${mpiruncmd} -n ${npes} ${MPIRUN_OPTIONS[@]} ${IMB_RMA} ${imbtest} ${imbtest_options} > ${outfile} 2> ${errfile} 
   ;;
*)
   die "Target ${target} unrecognized in $tarball"
   ;;
esac

if [[ -s $outfile ]] ; then 
  if $(grep ! $outfile) ; then
    if [[ -s $errfile ]] ; then 
       cat $errfile
       die "$outfile contains errors and $errfile has contents" 
    fi
    die "$outfile contains errors!" 
  else
    splunkfile=${runhome}/"my.splunkdata"
    splunkdir="/usr/projects/splunk/results/${USER}/${machine}"
    splunklog=${splunkdir}/"splunkdata.log"
    if [[ -d ${splunkdir} ]] ; then 
       if [[ ! -e $splunklog ]] ; then
          touch $splunklog
       fi
    else
       mkdir -p ${splunkdir} 
       touch ${splunklog}
    fi 
    ./parseIMB.py --infile "$outfile" --outfile "$splunkfile"
    echo "<results> PASSED"
  fi 
elif [[ -s $errfile ]] ; then 
    echo "\$outfile: ${outfile}, is empty; \$errfile: ${errfile} contains:" 
    cat ${errfile}
else
  echo "\$errfile: $errfile and \$outfile: $outfile are missing"
  echo "Try again passing debug to the script either on the command line or in \$PV_TEST_ARGS"
  echo "Otherwise, set the environment variable \$DEBUG=True for verbose output"
  usage 
fi

exit 

