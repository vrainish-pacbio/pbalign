#!/usr/bin/env python
###############################################################################
# Copyright (c) 2011-2013, Pacific Biosciences of California, Inc.
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
# * Neither the name of Pacific Biosciences nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# NO EXPRESS OR IMPLIED LICENSES TO ANY PARTY'S PATENT RIGHTS ARE GRANTED BY
# THIS LICENSE.  THIS SOFTWARE IS PROVIDED BY PACIFIC BIOSCIENCES AND ITS
# CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT
# NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL PACIFIC BIOSCIENCES OR
# ITS CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
###############################################################################

# Author: Yuan Li
"""This script defines class AlignService."""

from __future__ import absolute_import
import logging
from copy import copy
from pbalign.options import importDefaultOptions
from pbalign.utils.tempfileutil import TempFileManager
from pbalign.service import Service
from pbalign.utils.fileutil import getFileFormat, FILE_FORMATS


class AlignService (Service):
    """Super class for all alignment services.

        AlignService takes argument options as input and generates a SAM file
        as output.
        Non-abstract subclasses should define the following properties.
            name        : name of the subclass align service
            availability: availability of the subclass align service
            scoreSign   : score sign of the subclass align service
        Subclasses should override the following virtual methods.
            _preProcess :
            _toCmd()
            _postProcesss()
        If --algorithmOptions needs to be supported by a subclass, override
            _resolveAlgorithmOptions().

    """
    @property
    def scoreSign(self):
        """Align service score sign can be -1 or 1.
           -1: negative scores are better than positive ones.
           1: positive scores are better than negative ones.
        """
        raise NotImplementedError(
            "Virtual property scoreSign() for AlignService must be " +
            "overwritten.")

    def _resolveAlgorithmOptions(self, options, fileNames):
        """A virtual method to resolve options specified within
            --algorithmOptions and options parsed from the command-line
            (including the config file).
            Input:
                options: options parsed from a command-line and a config file.
                fileNames: an PBAlignFiles object.
            Output: new options
        """
        if options.algorithmOptions is None or options.algorithmOptions == "":
            return copy(options)

        raise NotImplementedError(
            "_resolveAlgorithmOptions() method for AlignService must be " +
            "overridden if --algorithmOptions is specified.")

    def __init__(self, options, fileNames, tempFileManager=None):
        """Initialize an AlignSerivce object.
            Need to resolve options specified within algorithmOptions;
                    patch default options if not specified by the user
                    inherit or initialize a tempory file manager
            Input:
                options        : options parsed from (a list of arguments and
                                 a config file if --configFile is specified).
                fileNames      : an object of PBAlignFiles
                tempFileManager: a temporary file manager. If it is None,
                                 create a new temporary file manager.
        """
        self._options = options

        # Verify and assign input & output files.
        self._fileNames = fileNames
        self._fileNames.SetInOutFiles(self._options.inputFileName,
                                      self._options.referencePath,
                                      self._options.outputFileName,
                                      self._options.regionTable,
                                      self._options.pulseFile)

        # Resolve options specified within --algorithmOptions with
        # options parsed from the argument list (e.g. the command-line)
        # or a config file.
        self._options = self._resolveAlgorithmOptions(self._options,
                                                      self._fileNames)

        # Patch PBalign default options if they havn't been specified yet.
        self._options = importDefaultOptions(self._options)[0]

        if tempFileManager is None:
            self._tempFileManager = TempFileManager(self._options.tmpDir)
        else:
            self._tempFileManager = tempFileManager
            self._tempFileManager.SetRootDir(self._options.tmpDir)
        # self.args is finalized.
        logging.debug("Parsed arguments considering configFile and " +
                      "algorithmOptions: " + str(self._options))

    @property
    def cmd(self):
        """String of a command line to align reads."""
        return self._toCmd(self._options,
                           self._fileNames,
                           self._tempFileManager)

    def _toCmd(self, options, fileNames, tempFileManager):
        """A virtual method to generate a command line string.

        Generate a command line of the aligner to use in bash based on
        options and PBAlignFiles.
            Input:
                options  : arguments parsed from the command-line, the
                           config file and --algorithmOptions.
                fileNames: an PBAlignFiles object.
                tempFileManager: temporary file manager.
            Output:
                a command-line string which can be used in bash.

        """
        raise NotImplementedError(
            "_toCmd() method for AlignService must be overridden")

    def _preProcess(self, inputFileName, referenceFile, regionTable,
                    noSplitSubreads, tempFileManager, isWithinRepository):
        """A virtual method to prepare inputs for the aligner.

           Input:
                inputFileName  : a PacBio BASE/PULSE/FOFN file.
                referenceFile  : a FASTA reference file.
                regionTable    : a region table RGN.H5/FOFN file.
                noSplitSubreads: whether to split subreads or not.
                tempFileManager: temporary file manager.
                isWithinRepository: whether or not the reference is within
                    a refererence repository.
            Output:
                String, a FASTA file which can be used by the aligner.

        """
        raise NotImplementedError(
            "_preProcess() method for AlignService must be overridden")

    def _postProcess(self):
        """A virtual method to post process the generated output file. """
        raise NotImplementedError(
            "_postProcess() method for AlignService must be overridden")

    def run(self):
        """AlignService starts to run. """
        logging.info(self.name + ": Align reads to references using " +
                     "{prog}.".format(prog=self.progName))
        # Prepare inputs for the aligner.
        self._fileNames.queryFileName = self._preProcess(
            self._fileNames.inputFileName,
            self._fileNames.targetFileName,
            self._fileNames.regionTable,
            self._options.noSplitSubreads,
            self._tempFileManager,
            self._fileNames.isWithinRepository)

        outFormat = getFileFormat(self._fileNames.outputFileName)
        suffix = ".bam" if (outFormat == FILE_FORMATS.BAM or
                            outFormat == FILE_FORMATS.XML) else ".sam"
        self._fileNames.alignerSamOut = self._tempFileManager.\
            RegisterNewTmpFile(suffix=suffix)

        # Generate and execute cmd.
        try:
            output, errCode, errMsg = self._execute()
        except RuntimeError as e:
            raise RuntimeError(str(e))

        # Post process the results.
        self._postProcess()

        return output, errCode, errMsg
