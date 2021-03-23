##
# Copyright 2009-2017 Ghent University
#
# This file is part of EasyBuild,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://www.vscentrum.be),
# Flemish Research Foundation (FWO) (http://www.fwo.be/en)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# http://github.com/hpcugent/easybuild
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
##
"""
General EasyBuild support for software with a binary installer

@author: Stijn De Weirdt (Ghent University)
@author: Dries Verdegem (Ghent University)
@author: Kenneth Hoste (Ghent University)
@author: Pieter De Baets (Ghent University)
@author: Jens Timmerman (Ghent University)
"""

import shutil
import os
import stat

from easybuild.framework.easyblock import EasyBlock
from easybuild.framework.easyconfig import CUSTOM
from easybuild.tools.build_log import EasyBuildError
from easybuild.tools.filetools import mkdir, rmtree2
from easybuild.tools.run import run_cmd
from easybuild.easyblocks.generic.binary import Binary

class EB_SingularityImage(Binary):
    """
    Support for installing software that comes in binary form.
    Just copy the sources to the install dir, or use the specified install command.
    """

    @staticmethod
    def extra_options(extra_vars=None):
        """Extra easyconfig parameters specific to Binary easyblock."""
        extra_vars = Binary.extra_options(extra_vars)
        extra_vars.update({
            'deffile': [None, "Definition (spec) file used to build the container.", CUSTOM],
            'use_gpu': [False, "Use GPU for running container applications.", CUSTOM], 
        })
        return extra_vars

    def __init__(self, *args, **kwargs):
        """Initialize Binary-specific variables."""
        super(EB_SingularityImage, self).__init__(*args, **kwargs)

        #self.actual_installdir = None
        #if self.cfg['staged_install']:
        #    self.actual_installdir = self.installdir
        #    self.installdir = os.path.join(self.builddir, 'staged')
        #    mkdir(self.installdir, parents=True)
        #    self.log.info("Performing staged installation via %s" % self.installdir)
        
        container_run_cmd ='singularity run'
        if self.cfg['use_gpu']:
            container_run_cmd = 'singularity run --nv'
        containerfile = self.cfg['sources'][0]
        for srcfile in self.cfg['sources']:
            if srcfile != self.cfg['deffile']:
                containerfile = srcfile 
        msg = "Before using this container for the FIRST time, copy it to your personal home (or /scratch) directory using this command:\n"
        msg+= "cp $CONTAINERDIR/%s /home/$USER\n\n" % containerfile
        msg+= "To execute the default application inside the container, run this command:\n"
        msg+= "%s /home/$USER/%s\n\n" % (container_run_cmd,containerfile)
        if self.cfg['modloadmsg']:
            msg += self.cfg['modloadmsg']
        self.cfg['modloadmsg'] = msg
        self.log.debug(self.cfg['modloadmsg'])
        

    def post_install_step(self):
        """Copy installation to actual installation directory in case of a staged installation."""
        if self.cfg['staged_install']:
            staged_installdir = self.installdir
            self.installdir = self.actual_installdir
            try:
                # copytree expects target directory to not exist yet
                if os.path.exists(self.installdir):
                    rmtree2(self.installdir)
                shutil.copytree(staged_installdir, self.installdir)
            except OSError, err:
                raise EasyBuildError("Failed to move staged install from %s to %s: %s",
                                     staged_installdir, self.installdir, err)

        deffile = self.cfg['deffile']
        if deffile is not None:
            easybuilddir = os.path.join(self.installdir, 'easybuild')
            try:
                os.makedirs(easybuilddir)
                shutil.copy(os.path.join(self.cfg['start_dir'], deffile), easybuilddir)
            except OSError, err:
                raise EasyBuildError("Failed to copy %s to %s: %s", self.cfg['deffile'], easybuilddir, err)

        super(Binary, self).post_install_step()


    def make_module_extra(self):
        """Add the install directory to the PATH."""
        txt = super(EB_SingularityImage, self).make_module_extra()
        txt += self.module_generator.set_environment("CONTAINERDIR", self.installdir)
        self.log.debug("make_module_extra added this: %s" % txt)
        self.log.debug(self.cfg)
        return txt
