# #
# Copyright 2009-2019 Ghent University
#
# This file is part of EasyBuild,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://www.vscentrum.be),
# Flemish Research Foundation (FWO) (http://www.fwo.be/en)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# https://github.com/easybuilders/easybuild
#
# EasyBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# EasyBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with EasyBuild.  If not, see <http://www.gnu.org/licenses/>.
# #
"""
EasyBuild support for install the Intel C/C++ compiler suite, implemented as an easyblock

@author: Stijn De Weirdt (Ghent University)
@author: Dries Verdegem (Ghent University)
@author: Kenneth Hoste (Ghent University)
@author: Pieter De Baets (Ghent University)
@author: Jens Timmerman (Ghent University)
@author: Ward Poelmans (Ghent University)
@author: Fokko Masselink
"""

import os
import re
import shutil
from distutils.version import LooseVersion

from easybuild.framework.easyconfig import CUSTOM
from easybuild.framework.easyblock import EasyBlock
from easybuild.easyblocks.generic.intelbase import IntelBase, ACTIVATION_NAME_2012, COMP_ALL
from easybuild.easyblocks.generic.intelbase import LICENSE_FILE_NAME_2012
from easybuild.easyblocks.t.tbb import get_tbb_gccprefix
from easybuild.tools.run import run_cmd
from easybuild.tools.systemtools import get_shared_lib_ext


def get_icc_version():
    """Obtain icc version string via 'icc --version'."""
    cmd = "icc --version"
    (out, _) = run_cmd(cmd, log_all=True, simple=False)

    ver_re = re.compile("^icc \(ICC\) (?P<version>[0-9.]+) [0-9]+$", re.M)
    version = ver_re.search(out).group('version')

    return version


class EB_intel(IntelBase):
    """Support for installing icc

    - tested with 11.1.046
        - will fail for all older versions (due to newer silent installer)
    """

    @staticmethod
    def extra_options():
        """Add extra easyconfig parameters for Intel."""
        extra_vars = {
            'official_version': [None, "Official Intel version XXXX.X.XXX", CUSTOM],
            'hide_mpi': [True, "LD_LIBRARY_PATH, CPATH, PATH are not including any reference to MPI libs or headers", CUSTOM],
        }
        return IntelBase.extra_options(extra_vars)


    def __init__(self, *args, **kwargs):
        """Constructor, initialize class variables."""
        super(EB_intel, self).__init__(*args, **kwargs)

        self.debuggerpath = None

        self.comp_libs_subdir = None

        if LooseVersion(self.cfg['official_version']) >= LooseVersion('2016'):

            self.comp_libs_subdir = os.path.join('compilers_and_libraries_%s' % self.cfg['official_version'], 'linux')

            if self.cfg['components'] is None:
                # we need to use 'ALL' by default,
                # using 'DEFAULTS' results in key things not being installed (e.g. bin/icc)
                self.cfg['components'] = [COMP_ALL]
                self.log.debug("Nothing specified for components, but required for version 2016, using %s instead",
                               self.cfg['components'])
    
    
    def install_step(self):
        """
        Actual installation
        - create silent cfg file
        - execute command
        """
        silent_cfg_names_map = None

        if LooseVersion(self.cfg['official_version']) < LooseVersion('2013_sp1'):
            # since icc v2013_sp1, silent.cfg has been slightly changed to be 'more standard'

            silent_cfg_names_map = {
                'activation_name': ACTIVATION_NAME_2012,
                'license_file_name': LICENSE_FILE_NAME_2012,
            }

        super(EB_intel, self).install_step(silent_cfg_names_map=silent_cfg_names_map)
        shutil.copy(self.license_file, os.path.join(self.installdir, '../'))


    def sanity_check_step(self):
        """Custom sanity check paths for icc."""

        binprefix = 'bin/intel64'
        libprefix = 'lib/intel64'
        if LooseVersion(self.cfg['official_version']) >= LooseVersion('2011'):
            if LooseVersion(self.cfg['official_version']) <= LooseVersion('2011.3.174'):
                binprefix = 'bin'
            elif LooseVersion(self.cfg['official_version']) >= LooseVersion('2013_sp1'):
                binprefix = 'bin'
            else:
                libprefix = 'compiler/lib/intel64'

        binfiles = ['icc', 'icpc']
        if LooseVersion(self.cfg['official_version']) < LooseVersion('2014'):
            binfiles += ['idb']

        binaries = [os.path.join(binprefix, f) for f in binfiles]
        libraries = [os.path.join(libprefix, 'lib%s' % l) for l in ['iomp5.a', 'iomp5.%s' % get_shared_lib_ext()]]
        sanity_check_files = binaries + libraries
        if LooseVersion(self.cfg['official_version']) > LooseVersion('2015'):
            sanity_check_files.append('include/omp.h')

        custom_paths = {
            'files': sanity_check_files,
            'dirs': [],
        }

        # make very sure that expected 'compilers_and_libraries_<VERSION>/linux' subdir is there for recent versions,
        # since we rely on it being there in make_module_req_guess
        if self.comp_libs_subdir:
            custom_paths['dirs'].append(self.comp_libs_subdir)

        custom_commands = ["which icc"]

        super(EB_intel, self).sanity_check_step(custom_paths=custom_paths, custom_commands=custom_commands)

    def make_module_req_guess(self):
        """
        Additional paths to consider for prepend-paths statements in module file
        """
        prefix = None
        docpath = 'documentation_%s' % self.cfg['official_version'].split('.')[0]
        # guesses per environment variables
        # some of these paths only apply to certain versions, but that doesn't really matter
        # existence of paths is checked by module generator before 'prepend-paths' statements are included
        
        guesses = {
            'CLASSPATH': ['daal/lib/daal.jar'],
            # 'include' is deliberately omitted, including it causes problems, e.g. with complex.h and std::complex
            # cfr. https://software.intel.com/en-us/forums/intel-c-compiler/topic/338378
            'CPATH': ['ipp/include', 'mkl/include', 'mkl/include/fftw', 'tbb/include'],
            'DAALROOT': ['daal'],
            'IPPROOT': ['ipp'],
            'LD_LIBRARY_PATH': ['lib'],
            'MANPATH': ['debugger/gdb/intel64/share/man', 'man/common', 'man/en_US', 'share/man'],
            'PATH': ['tbb/bin', 'mkl/bin'],
            'TBBROOT': ['tbb'],
            'MKLROOT': ['mkl'],
            'PSTLROOT': ['pstl'],
            'INFOPATH': [docpath],
            'PKG_CONFIG_PATH': ['mkl/bin/pkgconfig']
        }

        if self.cfg['m32']:
            # 32-bit toolchain
            guesses['PATH'].extend(['bin/ia32', 'tbb/bin/ia32'])
            # in the end we set 'LIBRARY_PATH' equal to 'LD_LIBRARY_PATH'
            guesses['LD_LIBRARY_PATH'].append('lib/ia32')

        else:
            # 64-bit toolkit
            guesses['PATH'].extend([
                'bin/intel64',
                'debugger/gdb/intel64/bin',
                'ipp/bin/intel64',
                'tbb/bin/emt64',
                'tbb/bin/intel64',
            ])

            # in the end we set 'LIBRARY_PATH' equal to 'LD_LIBRARY_PATH'
            guesses['LD_LIBRARY_PATH'].extend([
                'tbb/lib/intel64/%s' % get_tbb_gccprefix(),
                'mkl/lib/intel64',
                'ipp/lib/intel64',
                'debugger/ipt/intel64/lib',
                'compiler/lib/intel64',
            ])
            guesses['MIC_LD_LIBRARY_PATH'] = [
                'compiler/lib/mic',
                'debugger/ipt/lib/mic',
                'ipp/lib/mic',
                'mkl/lib/mic',
                'tbb/lib/mic',
            ]


            if not self.cfg['hide_mpi']:
                guesses['LD_LIBRARY_PATH'].append('mpi/mic/lib', 'mpi/intel64/lib')
                guesses['MIC_LD_LIBRARY_PATH'].append('/mpi/mic/lib')
                guesses['PATH'].append('mpi/intel64/bin')
                guesses['CPATH'].append('mpi/intel64/include')
            if LooseVersion(self.cfg['official_version']) < LooseVersion('2016'):
                prefix = 'composer_xe_%s' % self.cfg['official_version']
                # for some older versions, name of subdirectory is slightly different
                if not os.path.isdir(os.path.join(self.installdir, prefix)):
                    cand_prefix = 'composerxe-%s' % self.cfg['official_version']
                    if os.path.isdir(os.path.join(self.installdir, cand_prefix)):
                        prefix = cand_prefix

                # debugger is dependent on $INTEL_PYTHONHOME since version 2015 and newer
                if LooseVersion(self.cfg['official_version']) >= LooseVersion('2015'):
                    self.debuggerpath = os.path.join(prefix, 'debugger')

            else:
                # new directory layout for Intel Parallel Studio XE 2016
                # https://software.intel.com/en-us/articles/new-directory-layout-for-intel-parallel-studio-xe-2016
                prefix = self.comp_libs_subdir
                # Debugger requires INTEL_PYTHONHOME, which only allows for a single value
                self.debuggerpath = 'debugger_%s' % self.cfg['official_version'].split('.')[0]

                guesses['LD_LIBRARY_PATH'].extend([
                    os.path.join(self.debuggerpath, 'libipt/intel64/lib'),
                    'daal/lib/intel64_lin',
                ])

            # 'lib/intel64' is deliberately listed last, so it gets precedence over subdirs
            guesses['LD_LIBRARY_PATH'].append('lib/intel64') 

        # set up advisor and inspector
         
        # set debugger path
        if self.debuggerpath:
            guesses['PATH'].append(os.path.join(self.debuggerpath, 'gdb', 'intel64', 'bin'))

        # in recent Intel compiler distributions, the actual binaries are
        # in deeper directories, and symlinked in top-level directories
        # however, not all binaries are symlinked (e.g. mcpcom is not)
        # we only need to include the deeper directories (same as compilervars.sh)
        if prefix and os.path.isdir(os.path.join(self.installdir, prefix)):
            for key, subdirs in guesses.items():
                guesses[key] = [os.path.join(prefix, subdir) for subdir in subdirs]

            # The for loop above breaks libipt library loading for gdb - this fixes that
            guesses['LD_LIBRARY_PATH'].extend([
                'daal/lib/intel64_lin',
                # 'advisor/lib64',
                # 'advisor_xe/lib64'
                # 'inspector_xe/lib64',  # causes problems with libiomp5.so
                # 'inspector/lib64',  # causes problems with libiomp5.so
                ])
            guesses['CPATH'].extend([
                # 'daal/include',
                # 'advisor/include',
                # 'advisor_xe/include',
                # 'inspector/include',
                # 'inspector_xe/include',
                ])
            guesses['PATH'].extend([
                'daal/bin',
                'advisor/bin64',
                'advisor_xe/bin64',
                'inspector/bin64',
                'inspector_xe/bin64'])
            guesses['MANPATH'].extend([
                'man/common',
                '%s/en/debugger//gdb-mic/man' % docpath,
                '%s/en/debugger//gdb-igfx/man' % docpath,
                '%s/en/debugger//gdb-ia/man' % docpath,])
            guesses['INFOPATH'].extend([
                '%s/en/debugger//gdb-mic/info' % docpath,
                '%s/en/debugger//gdb-ia/info' % docpath,
                '%s/en/debugger//gdb-igfx/info' % docpath])
            if self.debuggerpath:
                guesses['LD_LIBRARY_PATH'].extend([
                    os.path.join(self.debuggerpath, 'libipt/intel64/lib'),
                    os.path.join(self.debuggerpath, 'iga/lib')])
                guesses['GDB_CROSS'] = [
                    os.path.join(self.debuggerpath, 'gdb/intel64_mic/bin/gdb-mic'),
                    os.path.join(self.debuggerpath, 'gdb/intel64/bin/gdb-ia')]
                for gdb in guesses['GDB_CROSS']:
                    if os.path.isfile(os.path.join(self.installdir, gdb)):
                        # pick first existing one and reset list
                        guesses['GDB_CROSS'] = [gdb]
                        break
                guesses['GDBSERVER_MIC'] = [
                    os.path.join(self.debuggerpath, 'gdb/targets/intel64/x200/bin/gdbserver'),
                    os.path.join(self.debuggerpath, 'gdb/targets/mic/bin/gdbserver'),]

        # only set $IDB_HOME if idb exists
        idb_home_subdir = 'bin/intel64'
        if os.path.isfile(os.path.join(self.installdir, idb_home_subdir, 'idb')):
            guesses['IDB_HOME'] = [idb_home_subdir]
        
        guesses['LIBRARY_PATH'] = guesses['LD_LIBRARY_PATH']

        return guesses


    def make_module_extra(self, *args, **kwargs):
        """Additional custom variables for icc: $INTEL_PYTHONHOME."""
        txt = super(EB_intel, self).make_module_extra(*args, **kwargs)

        if self.debuggerpath:
            intel_pythonhome = os.path.join(self.installdir, self.debuggerpath, 'python', 'intel64')
            if os.path.isdir(intel_pythonhome):
                txt += self.module_generator.set_environment('INTEL_PYTHONHOME', intel_pythonhome)
        
        # use licence file in installdir/../
        self.license_file = os.path.join(self.installdir, '..', os.path.basename(self.license_file))
        
        # on Debian/Ubuntu, /usr/include/x86_64-linux-gnu needs to be included in $CPATH for icc
        out, ec = run_cmd("gcc -print-multiarch", simple=False, log_all=False, log_ok=False)
        multiarch_inc_subdir = out.strip()
        if ec == 0 and multiarch_inc_subdir:
            multiarch_inc_dir = os.path.join('/usr', 'include', multiarch_inc_subdir)
            self.log.info("Adding multiarch include path %s to $CPATH in generated module file", multiarch_inc_dir)
            # system location must be appended at the end, so use append_paths
            txt += self.module_generator.append_paths('CPATH', [multiarch_inc_dir], allow_abs=True)

        return txt
