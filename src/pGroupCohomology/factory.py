# -*- coding: utf-8 -*-

#*****************************************************************************
#
#    Sage Package "Modular Cohomology Rings of Finite Groups"
#
#    Copyright (C) 2009, 2013, 2015 Simon A. King <simon.king@uni-jena.de>
#
#    This file is part of p_group_cohomology.
#
#    p_group_cohomoloy is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 2 of the License, or
#    (at your option) any later version.
#
#    p_group_cohomoloy is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with p_group_cohomoloy.  If not, see <http://www.gnu.org/licenses/>.
#*****************************************************************************
r"""
A Factory for Modular Cohomology Rings of Finite Groups

AUTHORS:

- Simon King  <simon.king@uni-jena.de> (Cython and Python code, porting, maintainance)
- David Green <david.green@uni-jena.de> (underlying C code)

This module provides a constructor for modular cohomology rings of
finite groups, that takes care of caching. The constructor is an
instance :func:`~pGroupCohomology.CohomologyRing` of the class
:class:`CohomologyRingFactory`.

"""

from __future__ import print_function, absolute_import

from sage.all import SAGE_ROOT, DOT_SAGE, load
from sage.all import Integer
from pGroupCohomology.auxiliaries import coho_options, coho_logger, safe_save, _gap_reset_random_seed, gap, singular, Failure
from pGroupCohomology import barcode
from pGroupCohomology.cohomology import COHO

import re, os, sys
if (2, 8) < sys.version_info:
    unicode = str
elif str == unicode:
    raise RuntimeError("<str> is <unicode>, which is a bug. Please recompile.")

#~ import urllib.request, urllib.error
try:
    from urllib.error import URLError
except ImportError:
    URLError = OSError
try:
    from urllib.request import urlopen
except ImportError:
    from urllib import urlopen
import tarfile
import logging

##########
## A little regular expression that transforms any string into a valid GStem

_GStemMaker = re.compile(r'[^0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ]')

##########
## Transformation into latex
_index_match = re.compile('(_\d+)+')
_exp_match = re.compile('\^\d')
_name2latex = lambda t: _exp_match.sub(lambda m: '^{'+m.group()[1:]+'}', _index_match.sub(lambda m:'_{%s}'%','.join(m.group().split('_')[1:]),t).replace('**','^')).replace('*',' ')


##########
## A rather long unit test: Groups of order 64

def unit_test_64(**kwds):
    r"""
    Compare computation from scratch with data in the database.

    The cohomology rings for all groups of order 64 are computed
    from sratch and the results are compared with the data that
    are shipped with this package.

    NOTE:

    This test is likely to take between 30 and 60 minutes, depending
    on the computer.

    INPUT:

    - test_isomorphism (optional bool, default False): Whether to
      properly test for isomorphy (which may take a long time)
      instead of only testing for equality of generator degrees
      and of Poincaré series.
    - Optional keyword arguments for the creation of cohomology rings.

    OUTPUT:

    - A list of integers, giving the address of groups of order 64
      in the Small Groups library for which a cohomology computation
      yields (with the given keyword arguments) a ring that is not
      isomorphic to the corresponding entry of the database.
      So, this list should be empty.
    - A list of three real numbers, giving the total computation time
      (wall time), the Python CPU-time and the Singular CPU-time,
      in seconds.

    During the computation, there is some information on the progress
    of the test.

    TEST::

        sage: from pGroupCohomology.factory import unit_test_64

    By default, i.e., without providing an explicit value ``False`` for
    ``from_scratch``, the rings are computed from scratch, using a
    temporary directory created by the test function (it can be
    prescribed by providing an explicit value for ``root``). This is
    a serious test and may involve some isomorphism tests, as different
    package versions or different options may very well result in
    different but isomorphic ring sturctures.

    Since doctests are supposed to be much shorter, we allow here to
    retrieve the data from the local sources (``from_scratch=False``).
    By consequence, the cohomology rings are simply reloaded and we merely
    test that pickling works.
    ::

        sage: L, t = unit_test_64(from_scratch=False)    # long time
        #  1: Walltime   ... min
              CPU-time   ... min
              Singular   ... min
        ...
        #267: Walltime   ... min
              CPU-time   ... min
              Singular   ... min
        sage: L
        []

    """
    L = []
    CohomologyRing.reset()
    from sage.all import tmp_dir, walltime, cputime, singular, gap
    from pGroupCohomology.isomorphism_test import IsomorphismTest
    if 'root' in kwds:
        workspace = kwds['root']
        del kwds['root']
    else:
        workspace = tmp_dir()
    isomorphism_test = kwds.pop('isomorphicm_test', False)
    wt0 = walltime()
    ct0 = cputime()
    db_workspace = tmp_dir()
    st = int(singular.eval('timer'))
    #~ gt = int(gap.eval('Runtime()'))
    Method = {}
    Defect = {}
    if 'from_scratch' not in kwds:
        kwds['from_scratch'] = True
    for i in range(1,268):
        success = True
        CohomologyRing.set_workspace(workspace)
        H = CohomologyRing(64,i, **kwds)
        H.make()
        CohomologyRing.set_workspace(db_workspace)
        H_db = CohomologyRing(64,i)
        if H != H_db:
            if H.degvec!=H_db.degvec or H.poincare_series() != H_db.poincare_series():
                print("Example",i,"fails")
                success = False
                L.append(i)
            else:
                # First test for trivial isomorphy
                T = IsomorphismTest(H_db, H)
                T.set_images(tuple(x.name() for x in H.Gen))
                if (T.is_homomorphism() and T.is_isomorphism()):
                    print("Different presentation with equivalent relation ideal in example", i)
                elif isomorphism_test:
                    print("Testing isomorphy for example", i)
                    if H_db.is_isomorphic(H):
                        print("successful")
                    else:
                        print("Example",i,"fails")
                        success = False
                        L.append(i)
                else:
                    print("We skip isomorphism test for example %d, which we count as failure"%i)
                    L.append(i)
                    success = False
        if success:
            if H.knownDeg < H_db.knownDeg:
                print("###########################################")
                print("####### Improvement:",i)
                print("###########################################")
            elif H.knownDeg > H_db.knownDeg:
                print("###########################################")
                print("####### Regression:",i)
                print("###########################################")
        wt = walltime(wt0)
        ct = cputime(ct0)
        print("#%3d: Walltime %3d:%02d.%02d min"%(i, int(wt/60), int(wt%60),int((wt%1)*100)))
        print("      CPU-time %3d:%02d.%02d min"%(int(ct/60), int(ct%60),int((ct%1)*100)))
        ST = (int(singular.eval('timer'))-st)/1000.0
        print("      Singular %3d:%02d.%02d min"%(int(ST/60), int(ST%60),int((ST%1)*100)))
        #~ GT = (int(gap.eval('Runtime()'))-gt)/1000.0
        #~ print("      Gap-time %3d:%02d.%02d min"%(int(GT/60), int(GT%60),int((GT%1)*100)))
        print()
    return L,[wt,ct,ST]

############
##  An auxiliary function that creates symbolic links to data
##  in a potentially write protected database

def _symlink_to_database(publ, priv):
    """
    INPUT:

    - ``publ`` -- string, folder for a cohomology ring in a database
      that may be write protected.
    - ``priv`` -- string

    ASSUMPTIONS:

    - ``publ`` exists and is a readable folder.
    - It is permitted to create a folder ``priv``. It is assumed
      that this folder does not exist yet.

    OUTPUT:

    Create symbolic links in ``priv`` pointing to data in ``publ``.

    EXAMPLES:

    We link to an entry of the local sources.
    ::

        sage: from pGroupCohomology import CohomologyRing
        sage: tmp = tmp_dir()
        sage: from pGroupCohomology.factory import _symlink_to_database
        sage: os.mkdir(os.path.join(tmp,'8gp3'))
        sage: _symlink_to_database(os.path.join(CohomologyRing.get_local_sources(),'8gp3'), os.path.join(tmp,'8gp3'))
        sage: L = os.listdir(os.path.join(tmp, '8gp3'))
        sage: '8gp3.nontips' in L
        True
        sage: 'H8gp3.sobj' in L
        True
        sage: L = os.listdir(os.path.join(tmp,'8gp3','dat'))
        sage: 'A8gp3.sobj' in L
        True
        sage: 'Res8gp3d02.bin' in L
        True

    """
    #print "_symlink_to_database",publ,priv
    priv = os.path.realpath(priv)
    publ = os.path.realpath(publ)
    if not (os.access(publ,os.R_OK) and os.path.isdir(publ)):
        raise ValueError("%s is supposed to be a readable folder"%publ)
    if priv==publ:
        raise ValueError("Can not symlink %s to itself"%priv)
    if not os.path.isdir(priv):
        # priv should be a folder. If it is anything else, then unlink it.
        if os.access(priv, os.F_OK) or os.path.islink(priv):
            os.unlink(priv)
        os.makedirs(priv)

    # We use a recursive routine to create the symbolic links.
    L0 = os.listdir(publ) # these are potentially write-protected files
    for d in L0:
        publd = os.path.realpath(os.path.join(publ,d))
        if os.path.islink(os.path.join(priv,d)):
            if os.path.realpath(os.path.join(priv,d)) == publd:
                # the link has already been established
                #print os.path.join(priv,d),"already points to",publd
                continue
            else:
                os.unlink(os.path.join(priv,d))
        privd = os.path.join(priv,d) # realpath here?
        if os.path.isdir(publd):
            _symlink_to_database(publd, privd)
        else:
            if os.path.isdir(privd):
                # This should not happen.
                # Anyway, clean it up.
                os.rmdir(privd)
            elif os.access(privd, os.F_OK):
                os.unlink(privd)
            os.symlink(publd, privd)


############
## A framework for working with different cohomology databases

class CohomologyRingFactory:
    r"""
    A factory for creating modular cohomology rings of finite p-groups as unique parent structures

    Please use :func:`~pGroupCohomology.CohomologyRing`, which is an
    instance of this class, and is provided with a documentation of
    the available options.

    TESTS::

        sage: from pGroupCohomology import CohomologyRing
        sage: CohomologyRing.doctest_setup()       # reset, block web access, use temporary workspace
        sage: H0 = CohomologyRing(8,3)   #indirect doctest
        sage: print(H0)
        Cohomology ring of Dihedral group of order 8 with coefficients in GF(2)
        <BLANKLINE>
        Computation complete
        Minimal list of generators:
        [c_2_2: 2-Cocycle in H^*(D8; GF(2)),
         b_1_0: 1-Cocycle in H^*(D8; GF(2)),
         b_1_1: 1-Cocycle in H^*(D8; GF(2))]
        Minimal list of algebraic relations:
        [b_1_0*b_1_1]

    """
    def __init__(self):
        """
        EXAMPLE::

            sage: from pGroupCohomology.factory import CohomologyRingFactory
            sage: CR = CohomologyRingFactory()   #indirect doctest
            sage: CR.doctest_setup()
            sage: H = CR(8,3)
            sage: print(H)
            Cohomology ring of Dihedral group of order 8 with coefficients in GF(2)
            <BLANKLINE>
            Computation complete
            Minimal list of generators:
            [c_2_2: 2-Cocycle in H^*(D8; GF(2)),
             b_1_0: 1-Cocycle in H^*(D8; GF(2)),
             b_1_1: 1-Cocycle in H^*(D8; GF(2))]
            Minimal list of algebraic relations:
            [b_1_0*b_1_1]

        """
        ###########
        ## Cohomology rings will be unique parent structures
        from weakref import WeakValueDictionary
        self._cache = WeakValueDictionary({})
        self._create_local_sources = False

    def reset(self):
        """Reset the cohomology ring machinery's initial state.

        We mainly use this to avoid side effects of doctests affecting
        other doctest.

        EXAMPLES::

            sage: from pGroupCohomology import CohomologyRing
            sage: CohomologyRing.reset()
            sage: sorted(CohomologyRing.global_options().items())
            [('NrCandidates', 1000),
             ('SingularCutoff', 70),
             ('autolift', 1),
             ('autoliftElAb', 0),
             ('reload', True),
             ('save', True),
             ('sparse', False),
             ('useMTX', True),
             ('use_web', True)]
            sage: CohomologyRing.global_options('sparse', 'nosave', autolift=4)
            sage: sorted(CohomologyRing.global_options().items())
            [('NrCandidates', 1000),
             ('SingularCutoff', 70),
             ('autolift', 4),
             ('autoliftElAb', 0),
             ('reload', True),
             ('save', False),
             ('sparse', True),
             ('useMTX', True),
             ('use_web', True)]
            sage: CohomologyRing.reset()
            sage: sorted(CohomologyRing.global_options().items())
            [('NrCandidates', 1000),
             ('SingularCutoff', 70),
             ('autolift', 1),
             ('autoliftElAb', 0),
             ('reload', True),
             ('save', True),
             ('sparse', False),
             ('useMTX', True),
             ('use_web', True)]

        """
        CohomologyRing.logger.setLevel(logging.WARN)
        from pGroupCohomology.auxiliaries import stream_handler, CohoFormatter
        stream_handler.setFormatter(CohoFormatter())
        CohomologyRing._cache.clear()
        self.set_local_sources(True)  # use the default location of the local sources
        self.set_local_sources(False) # make the local sources read-only
        self.set_workspace(None)      # use the default location of the workspace
        self.set_remote_sources(None) # use the default location of the remote sources
        from pGroupCohomology.auxiliaries import default_options, coho_options
        coho_options.clear()
        coho_options.update(default_options)
        singular.quit()
        singular.option('noqringNF')
        _gap_reset_random_seed()

    def doctest_setup(self):
        """Block web access and put the workspace into a temporary directory.

        This is essential when doctesting computations that would
        access web repositories of cohomology data.

        EXAMPLES::

            sage: from pGroupCohomology import CohomologyRing
            sage: CohomologyRing.reset()
            sage: from pGroupCohomology.cohomology import COHO
            sage: COHO.remote_sources
            ('http://cohomology.uni-jena.de/db/',)
            sage: CohomologyRing.doctest_setup()
            sage: COHO.remote_sources
            ()

        """
        self.reset()
        self.set_remote_sources(())  # we don't want to access the web in tests
        from sage.misc.temporary_file import tmp_dir
        self.set_workspace(tmp_dir()) # we don't want that tests alter the user's workspace

    def global_options(self, *args, **kwds):
        """Set global options for cohomology computations.

        INPUT:

        - arbitrary strings, as positional arguments.
        - optional keyword arguments that provide values to be assigned to an option.

        There are the special string values "warn", "info" and "debug", that set
        the logging level accordingly, and moreover "walltime" (the walltime spent
        since setting this option will be added to the log), "cputime" (the cputime
        spent since setting this option will be added to the log), "time" (the log
        will include both walltime and cputime). With "notime", "nowalltime" and
        "nocputime", the corresponding logging option can be switched off.

        For any other string that does not start start with `"no"`,
        the option with that name is set to ``True``. If it is of the
        form ``"no"+X``, then the option with the name ``X`` is set to
        ``False``. If there is no input, a copy of the dictionary of
        options is returned.

        EXAMPLES::

            sage: from pGroupCohomology import CohomologyRing
            sage: CohomologyRing.reset()
            sage: sorted(CohomologyRing.global_options().items())
            [('NrCandidates', 1000),
             ('SingularCutoff', 70),
             ('autolift', 1),
             ('autoliftElAb', 0),
             ('reload', True),
             ('save', True),
             ('sparse', False),
             ('useMTX', True),
             ('use_web', True)]
            sage: CohomologyRing.global_options('sparse', 'nosave', autolift=4)
            sage: sorted(CohomologyRing.global_options().items())
            [('NrCandidates', 1000),
             ('SingularCutoff', 70),
             ('autolift', 4),
             ('autoliftElAb', 0),
             ('reload', True),
             ('save', False),
             ('sparse', True),
             ('useMTX', True),
             ('use_web', True)]
            sage: CohomologyRing.reset()

        """
        from pGroupCohomology.auxiliaries import coho_options, stream_handler, CohoFormatter
        if not kwds and (not args or (len(args)==1 and not args[0])):
            return dict(coho_options)
        for opt in args:
            if isinstance(opt, (str,unicode)):
                opt = str(opt)
                if opt == 'warn':
                    coho_logger.setLevel(logging.WARN)
                    coho_logger.handlers[0].formatter.reset()
                    coho_logger.setLevel(logging.WARN)
                elif opt == 'info':
                    coho_logger.setLevel(logging.WARN)
                    coho_logger.handlers[0].formatter.reset()
                    coho_logger.setLevel(logging.INFO)
                elif opt == 'debug':
                    coho_logger.setLevel(logging.WARN)
                    coho_logger.handlers[0].formatter.reset()
                    coho_logger.setLevel(logging.DEBUG)
                elif opt == 'cputime':
                    stream_handler.setFormatter(CohoFormatter(walltime=coho_logger.handlers[0].formatter.walltime, cputime=True))
                elif opt == 'nocputime':
                    stream_handler.setFormatter(CohoFormatter(walltime=coho_logger.handlers[0].formatter.walltime, cputime=False))
                elif opt == 'walltime':
                    stream_handler.setFormatter(CohoFormatter(walltime=True, cputime=coho_logger.handlers[0].formatter.cputime))
                elif opt == 'nowalltime':
                    stream_handler.setFormatter(CohoFormatter(walltime=False, cputime=coho_logger.handlers[0].formatter.cputime))
                elif opt == 'time':
                    stream_handler.setFormatter(CohoFormatter(walltime=True, cputime = True))
                elif opt == 'notime':
                    stream_handler.setFormatter(CohoFormatter())
                elif len(opt)>1 and opt[:2]=='no':
                    coho_options[opt[2:]] = False
                else:
                    coho_options[opt] = True
            else:
                raise TypeError("option must be a string")
        coho_options.update(kwds)

    def get_local_sources(self):
        """
        Return the location of the current local sources.

        EXAMPLE::

            sage: from pGroupCohomology import CohomologyRing
            sage: CohomologyRing.reset()
            sage: try:
            ....:     from sage.env import SAGE_SHARE
            ....: except ImportError:
            ....:     try:
            ....:         from sage.misc.misc import SAGE_SHARE
            ....:     except ImportError:
            ....:         from sage.misc.misc import SAGE_DATA as SAGE_SHARE
            sage: CohomologyRing.get_local_sources().startswith(os.path.realpath(SAGE_SHARE))
            True
            sage: tmp = tmp_dir()
            sage: CohomologyRing.set_local_sources(tmp)
            sage: CohomologyRing.get_local_sources().startswith(os.path.realpath(tmp))
            True

        """
        return COHO.local_sources

    def get_workspace(self):
        """
        Return the location of the current workspace.

        EXAMPLE::

            sage: from pGroupCohomology import CohomologyRing
            sage: CohomologyRing.reset()
            sage: CohomologyRing.get_workspace().startswith(os.path.realpath(DOT_SAGE))
            True
            sage: tmp = tmp_dir()
            sage: CohomologyRing.set_workspace(tmp)
            sage: CohomologyRing.get_workspace().startswith(os.path.realpath(tmp))
            True

        """
        return COHO.workspace

    def set_local_sources(self, folder=True):
        """
        Define which local sources to be used.

        INPUT:

        ``folder`` - (optional, default ``True``) a bool or a string

        OUTPUT:

        - If ``folder`` is a non-empty string, it will be used as the root
          directory of local sources in subsequent cohomology computations.
        - If the user has write permissions in this folder, it is actually
          used to create rings. Otherwise, it is only used to read existing
          cohomology data, but all new computations will still be done in
          the user's workspace.
        - If ``folder`` is ``True`` then the default location of the local
          sources is reset; this is a sub-directory of ``SAGE_SHARE``.
        - If ``bool(folder)`` is ``False`` then the user's workspace will
          be used to create new data in subsequent computations, even if
          the user has write permission for the local sources.

        EXAMPLES::

            sage: from pGroupCohomology import CohomologyRing
            sage: CohomologyRing.doctest_setup()       # reset, block web access, use temporary workspace
            sage: tmp_priv = tmp_dir()
            sage: tmp_publ = tmp_dir()
            sage: CohomologyRing.set_workspace(tmp_priv)

        If the local sources are set by the user to a location
        for which s/he has write permissions, then it is used
        for creating a cohomology ring::

            sage: CohomologyRing.set_local_sources(tmp_publ)
            sage: H1 = CohomologyRing(8,3)
            sage: H1.root.startswith(os.path.realpath(tmp_publ))
            True

        After unsetting it, the workspace is used instead::

            sage: CohomologyRing.set_local_sources(False)
            sage: H2 = CohomologyRing(8,3)
            sage: H2.root.startswith(os.path.realpath(tmp_priv))
            True

        ``CohomologyRing.set_local_sources(False)`` did not reset the
        default local sources (that by default are read-only); but
        ``CohomologyRing.set_local_sources(True)`` does::

            sage: CohomologyRing.set_local_sources(True)
            sage: from sage.env import SAGE_SHARE
            sage: CohomologyRing.get_local_sources().startswith(os.path.realpath(SAGE_SHARE))
            True

        """
        if folder:
            self._create_local_sources = True
            if not isinstance(folder, (str,unicode)):
                try:
                    from sage.env import SAGE_SHARE
                except ImportError:
                    try:
                        from sage.misc.misc import SAGE_SHARE
                    except ImportError:
                        from sage.misc.misc import SAGE_DATA as SAGE_SHARE
                folder = os.path.realpath(os.path.join(SAGE_SHARE,'pGroupCohomology'))
            else:
                folder = os.path.realpath(str(folder))
            if os.path.exists(folder):
                if os.path.isdir(folder):
                    if not os.access(folder,os.W_OK):
                       coho_logger.warning("WARNING: '%s' is not writeable", None, folder)
                       self._create_local_sources = False
                else:
                    raise OSError("'%s' is no folder"%folder)
            else:
                os.makedirs(folder)  # may produce an error
            COHO.local_sources = folder
        else:
            self._create_local_sources = False

    def from_local_sources(self, *args, **kwds):
        """
        Retrieve/create a cohomology ring in the local sources

        NOTE:

        - The local sources can be chosen using :meth:`set_local_sources`.
        - Write permissions to the local sources are required in this method.
        - All subsequent computations will modify data in the local sources,
          until ``CohomologyRing.set_local_sources(False)`` is used.

        EXAMPLES::

            sage: from pGroupCohomology import CohomologyRing
            sage: CohomologyRing.doctest_setup()       # reset, block web access, use temporary workspace
            sage: tmp_priv = tmp_dir()
            sage: tmp_publ = tmp_dir()
            sage: CohomologyRing.set_workspace(tmp_priv)

        We demonstrate how to put data into the local sources::

            sage: CohomologyRing.set_local_sources(tmp_publ)
            sage: H1 = CohomologyRing(8,3)
            sage: H1.root.startswith(os.path.realpath(tmp_publ))
            True

        After unsetting it, the user's workspace is used instead::

            sage: CohomologyRing.set_local_sources(False)
            sage: H2 = CohomologyRing(8,4)
            sage: H2.root.startswith(os.path.realpath(tmp_priv))
            True

        But it is possible to access the local sources directly::

            sage: H3 = CohomologyRing.from_local_sources(8,2)
            sage: H3.root.startswith(os.path.realpath(tmp_publ))
            True

        """
        create_local_sources = self._create_local_sources
        if not self._create_local_sources:
            self.set_local_sources(self.get_local_sources())
        try:
            return self(*args,**kwds)
        finally:
            self._create_local_sources = create_local_sources

    def gstem(self, G, GStem=None, GroupName=None, GroupId=None):
        """
        Return a group identifier that is used to create file names.

        INPUT:

        - ``G`` -- A list, either containing a single group in GAP
          or two integers providing an address in the SmallGroups
          library.
        - ``GStem`` -- (optional string) if provided, it will be used.
        - ``GroupName`` -- (optional string) if provided, if ``G``
          contains a single group and no other optional arguments
          are provided, it is used.
        - ``GroupId`` -- (optional pair of integers) If ``G`` contains
          a single group, ``GroupId`` is supposed to be its address
          in the SmallGroups library.

        OUTPUT:

        - A normalised version of ``GStem``, if it is provided.
        - ``<q>gp<n>``, if the SmallGroups address is provided by
          either ``G`` or ``GroupId``.
        - A normalised version of ``GroupName``, if it is provided.
        - If ``G`` contains a single group that has been given a
          custom name in GAP, a normalised version of this Name
          is returned.
        - Otherwise, an error is raised.

        EXAMPLES::

            sage: from pGroupCohomology import CohomologyRing
            sage: CohomologyRing.gstem([8,3])
            '8gp3'
            sage: CohomologyRing.gstem([8,3],GStem='DihedralGroup(8)')
            'DihedralGroup_8_'
            sage: CohomologyRing.gstem([libgap.eval('DihedralGroup(8)')],GroupName='DG(8)')
            'DG_8_'
            sage: CohomologyRing.gstem([libgap.eval('DihedralGroup(8)')],GroupName='DG(8)',GroupId=[8,3])
            '8gp3'
            sage: G = libgap.eval('DihedralGroup(8)')
            sage: G.SetName("DG_8")
            sage: CohomologyRing.gstem([G])
            'DG_8'
            sage: CohomologyRing.gstem([libgap.eval('DihedralGroup(8)')])
            Traceback (most recent call last):
            ...
            ValueError: Cannot infer a short group identifier. Please provide one of the optional arguments ``GStem`` or ``GroupName``

        """
        # Explicitly provided gstem has the highest rank.
        if GStem:
            return _GStemMaker.sub('_',GStem)
        # A small group has a canonical gstem
        if len(G)==2:
            return "%dgp%d"%(G[0],G[1])
        if GroupId:
            return "%dgp%d"%(GroupId[0],GroupId[1])
        # If there is no proper gstem, derive one from the groupname
        if GroupName:
            return _GStemMaker.sub('_',GroupName)
        try:
            g = G[0]
            gap = g.parent()
            if g.HasName():
                return _GStemMaker.sub('_', g.Name().sage())
        except (AttributeError,IndexError):
            pass
        raise ValueError("Cannot infer a short group identifier. Please provide one of the optional arguments ``GStem`` or ``GroupName``")

    def group_name(self, G, GroupName=None):
        """
        Determine a name for the given group.

        NOTE:

        This is just an auxiliary method and could as well be directly
        written in the code.

        INPUT:

        - ``G`` -- a list, either comprised by two integers that form the
          address of a group in the SmallGroups library, or by a group in
          the libGAP interface.
        - ``GroupName`` -- an optional string, a name provided by the user.

        If ``GroupName`` is provided, it will be used. Otherwise, if the
        group is given by its SmallGroup address, ``None`` is returned.
        Otherwise, if the group is provided with a custom name in GAP,
        it will be used. Otherwise, ``None`` is returned.

        NOTE:

        This package has a list of custom names for certain groups in
        the SmallGroups library. However, this list is only used in the
        initialisation of :class:`~pGroupCohomology.cohomology.COHO`.

        EXAMPLE::

            sage: from pGroupCohomology import CohomologyRing
            sage: G = libgap.eval('DihedralGroup(8)')
            sage: CohomologyRing.group_name((8,3))
            sage: CohomologyRing.group_name((8,3),'D8')
            'D8'
            sage: CohomologyRing.group_name([G],'D8')
            'D8'
            sage: CohomologyRing.group_name([G])
            sage: G.SetName("DihedralGroup_8")
            sage: CohomologyRing.group_name([G])
            'DihedralGroup_8'
            sage: CohomologyRing.group_name([G],'D8')
            'D8'

        """
        if GroupName:
            return GroupName
        if len(G)==2:
            return None
        try:
            g = G[0]
            if g.HasName():
                return g.Name().sage()
        except (AttributeError, IndexError):
            pass
        # It is not always needed to have a group name, so, we do not
        # raise an error but return None

    def create_group_key(self, G, GroupId=None, GroupDefinition=None):
        """
        Return data that allow to determine a given group up to equivalence.

        NOTE:

        For our package, a group is always supposed to be provided with
        a fixed list of generators. Two groups are *equivalent* if there
        exists a group homomorphism that sends the list of generators
        of one group to an initial segment of the list of generators of
        the other group. The ring presentation of a cohomology ring of
        a group, as computed with this package, only depends on the group's
        equivalence class.

        This is nothing more than an auxiliary method.

        INPUT:

        - ``G`` - a list, either formed by two integers representing an
          address in the SmallGroups library, or formed by a group in
          the libGAP interface.
        - ``GroupId`` - optional list of two integers, that is supposed
          to provide the address of a group in the SmallGroups library
          equivalent to the group given by ``G``.
        - ``GroupDefinition`` - optional string, that is supposed to be
          evaluated in the libGAP interface, yielding a group that is
          equivalent to the group given by ``G``

        OUTPUT:

        - If ``GroupDefinition`` is provided, it is returned.
        - If the given group is equivalent to a group in the SmallGroups
          library whose address is either given or can be determined by
          GAP, then this address (a pair of integers) is returned.
        - Otherwise, if the group is not a permutation group, it is
          transformed into an equivalent permutation group (using the
          regular permutation action). Then, a string representation of
          that permutation group is returned.

        EXAMPLES::

            sage: from pGroupCohomology import CohomologyRing
            sage: CohomologyRing.doctest_setup()       # reset, block web access, use temporary workspace
            sage: H = CohomologyRing(8,3)
            sage: H.group()
            Group([ (1,2)(3,8)(4,6)(5,7), (1,3)(2,5)(4,7)(6,8) ])
            sage: CohomologyRing.create_group_key([H.group()])
            (8, 3)

        By consequence, the cohomology rings of ``SmallGroup(8,3)`` and
        the permutation group above are identic::

            sage: H is CohomologyRing(libgap.eval('SmallGroup(8,3)'))
            True
            sage: H is CohomologyRing(H.group())
            True

        However, defining the dihedral group differently, we
        obtain a different equivalence class, and thus a different
        result::

            sage: CohomologyRing.create_group_key([libgap.eval('DihedralGroup(8)')])
            ('Group([(1,2)(3,8)(4,6)(5,7),(1,3,4,7)(2,5,6,8)])',)

        So, the given group is transformed into an equivalent
        permutation group. If we start with a big transformation
        group, a string representation obtained from its list of
        generators is returned::

            sage: CohomologyRing.create_group_key([libgap.eval('SymmetricGroup(8)')])
            ('Group([(1,2,3,4,5,6,7,8),(1,2)])',)

        It is possible to provide a reasonable string representation
        or a SmallGroups address. However, it is the user's responsibility
        to choose values that match the given group - this is not
        verified, as can be seen in the final example::

            sage: CohomologyRing.create_group_key([libgap.eval('SymmetricGroup(8)')],GroupDefinition='SymmetricGroup(8)')
            'SymmetricGroup(8)'
            sage: CohomologyRing.create_group_key([libgap.eval('SymmetricGroup(8)')],GroupId=[20,2])
            (20, 2)

        TEST:

        It is important that the group key is not formed by two integers in
        the libGAP interface. Namely, when storing the resulting ring, it could
        not easily be unpickled (actually it *can* be unpickled, but this
        involves some trickery, and it is certainly better to not rely on
        trickery). Here, we demonstrate that the given keys are correctly converted::

            sage: CohomologyRing.set_workspace(tmp_dir())
            sage: X = CohomologyRing(libgap(8),libgap(3), from_scratch=True)
            sage: type(X._key[0][0])
            <type 'sage.rings.integer.Integer'>

        """
        if GroupDefinition:
            return GroupDefinition
        if len(G)==2:
            return (Integer(G[0]),Integer(G[1]))
        if GroupId:
            return (Integer(GroupId[0]),Integer(GroupId[1]))
        # Try to determine a key from GAP
        g = G[0]
        if not hasattr(g,'parent'):
            raise TypeError("First argument should describe a group in GAP")
        gap = g.parent()
        # test if we can look g up in the Small Groups library
        try:
            gId = g.IdGroup().sage()
            gs = gap.SmallGroup(gId)
            if g.canonicalIsomorphism(gs) != Failure:
                return Integer(gId[0]), Integer(gId[1])
        except ValueError:
            pass
        if g.IsPermGroup():
            KEY = ('Group('+g.GeneratorsOfGroup().String().sage()+')',)
            # there might be line breaks or blanks. Remove them
            KEY = (''.join([t.strip() for t in KEY[0].split()]),)
        else:
            coho_logger.info("Computing an equivalent permutation group", None)
            # The key should be concise, therefore we do not use the regular
            # permutation action of the group on itself, which may have a huge
            # string representation that cannot be evaluated by libgap
            #~ KEY = (g.asPermgroup().String().sage(),)
            #~ KEY = (''.join([t.strip() for t in KEY[0].split()]),)
            KEY = (('Group(['+','.join([t.String().sage() for t in g.asPermgroup().GeneratorsOfGroup()])+'])').replace('\n','').replace(' ',''),)
        return KEY

    def check_arguments(self, args, minimal_generators=None, GroupId=None):
        """
        Return group order and a group in GAP with generating set suitable for the computations

        INPUT:

        - ``args``: A list, either formed by a group in GAP or by two integers,
          providing an address in the SmallGroups library.
        - ``minimal_generators``: (optional bool) If it is true, it is asserted
          by the user that an initial segment of the given list of generators
          of the group froms a minimal generating set.
        - ``GroupId``: (optional) Pair of numbers, providing the address of the
          given group in the SmallGroups library, if this happens to be known
          to the user.

        OUTPUT:

        - The group order, and

        NOTE:

        - It only matters in the case of prime power groups whether or not the
          given list of generators starts with a minimal generating set.
        - If the optional argument ``GroupId`` is provided, it is verified
          whether the group from the SmallGroups library is equivalent to the
          given group.

        EXAMPLE::

            sage: from pGroupCohomology import CohomologyRing
            sage: CohomologyRing.check_arguments([8,3])
            (8, <pc group of size 8 with 3 generators>)
            sage: CohomologyRing.check_arguments([libgap.eval('DihedralGroup(8)')])
            (8, Group([ (1,2)(3,8)(4,6)(5,7), (1,3,4,7)(2,5,6,8) ]))
            sage: CohomologyRing.check_arguments([libgap.eval('DihedralGroup(8)')], GroupId=[8,3])
            Traceback (most recent call last):
            ...
            ValueError: The given group generators are not canonically isomorphic to SmallGroup(8,3)

        """
        if len(args)<1 or len(args)>2:
            raise ValueError("The p-Group must be described by one or two parameters")
        if len(args)==2:
            q,n = args
            if (GroupId is not None) and ((q,n)!=GroupId):
                raise ValueError("``GroupId=(%d,%d)`` incompatible with the given SmallGroups entry (%d,%d)"%(GroupId[0],GroupId[1],q,n))
            _gap_reset_random_seed()
            try:
                max_n = gap.NumberSmallGroups(q).sage()
            except RuntimeError:
                raise ValueError("SmallGroups library not available for order %d"%q)
            if not 1 <= n <= max_n:
                raise ValueError("Second argument must be between 1 and %d"%max_n)
            return Integer(q), gap.SmallGroup(args[0],args[1])
        g = args[0]
        if not hasattr(g,'parent'):
            raise TypeError("Group in GAP expected")
        GAP = g.parent()
        _gap_reset_random_seed()
        if GroupId and g.canonicalIsomorphism(GAP.SmallGroup(GroupId[0], GroupId[1])) == GAP.eval('fail'):
            raise ValueError("The given group generators are not canonically isomorphic to SmallGroup(%d,%d)"%(GroupId[0],GroupId[1]))
        if GroupId: # compatibility was already checked
            q = Integer(GroupId[0])
        else:
            coho_logger.debug( "Computing group order", None)
            q = g.Order().sage()
        coho_logger.info("The group is of order %d", None, q)
        if q==1:
            raise ValueError("We don't consider the trivial group")
        if minimal_generators or not q.is_prime_power():
            return Integer(q), g
        else:
            # we require that the generating set starts with a minimal
            # generating set.
            coho_logger.debug("Trying to verify that the generator list starts with a minimal generating set", None)
            PhiP = g.admissibleGroup()
            if PhiP != GAP.eval('fail'):
                return q, PhiP.Range()
            else:
                raise ValueError("The first generators of the group must form a minimal generating set")

    def _check_compatibility(self, CacheKey, R):
        """
        Test whether a given expression is essentially equivalent to the cache key of a given cohomology ring.

        INPUT:

        - ``CacheKey``: an expression that is supposed to be a key for
          the cache of cohomology rings.
        - ``R``: a cohomology ring.

        OUTPUT:

        If the group description yield by ``CacheKey`` is compatible
        with the group description of ``R`` then ``R`` is returned. A
        warning is logged if ``CacheKey`` and ``R`` provide different
        (yet equivalent) group descriptions. An error is raised if the
        two groups are not equivalent.

        NOTE:

        It is not verified whether the locations of data storage yield by
        the two arguments coincide.

        TESTS::

            sage: from pGroupCohomology import CohomologyRing
            sage: CohomologyRing.doctest_setup()       # reset, block web access, use temporary workspace
            sage: H = CohomologyRing(8,3)
            sage: CohomologyRing._check_compatibility(H._key,H)
            H^*(D8; GF(2))
            sage: CohomologyRing._check_compatibility(((repr(H.group()),),H._key[1]), H)
            _check_compatibility:
                WARNING: The given key and ring describe different groups, but they are equivalent
            H^*(D8; GF(2))
            sage: CohomologyRing._check_compatibility(((8,4),H._key[1]), H)
            Traceback (most recent call last):
            ...
            ValueError: The ring H^*(D8; GF(2)) does not match the given key

        """
        if not isinstance(R, COHO):
            raise TypeError('The second argument must be a Cohomology ring')
        if self._create_local_sources:
            root_workspace = COHO.local_sources # SAGE_SHARE+'pGroupCohomology'
        else:
            root_workspace = COHO.workspace #DOT_SAGE+'pGroupCohomology/db/'
        # test if R is compatible with the key CacheKey.
        # May print a warning or raise an error,
        # and if it succeeds, return R
        similarity = _IsKeyEquivalent(CacheKey,R._key)
        if similarity == 1:
            coho_logger.warning('WARNING: The given key and ring describe different groups, but they are equivalent', None)
            return R
        elif similarity == 0:
            raise ValueError('The ring %s does not match the given key'%repr(R))
        return R

    def _get_p_group_from_cache_or_db(self, GStem, KEY, **kwds):
        """
        Try to find a certain cohomology ring of a `p`-group either in the cache or in a database.

        INPUT:

        - ``GStem``, a string that determines the filename for data associated with
          the cohomology ring of a finite `p`-group.
        - ``KEY``, a descriptor for the equivalence class of a group (see :meth:`create_group_key`)
        - ``from_scratch`` -- (optional bool) If ``True``, it is not attempted to
          copy data from local or remote sources, and an error is raised if the requested
          cohomology ring is not in the cache but already exists in the user's workspace.
        - ``websource`` -- (optional) provides the location of an alternative cohomology
          repository from which data will be downloaded if they can not be found in the cache,
          the workspace or the local sources.
        - Further keyword arguments will be assigned to properties of the cohomology ring,
          overriding previous values. Note that the new value of the property will be stored
          when pickling the cohomology ring.

        OUTPUT:

        The cohomology ring associated with the given arguments, or ``None``, if it can
        not be found in the cache, the workspace, or the local or remote sources.

        TESTS::

            sage: from pGroupCohomology import CohomologyRing
            sage: CohomologyRing.doctest_setup()       # reset, block web access, use temporary workspace

        Since the cohomology of the dihedral group of order 8 is shipped with this
        package, it can be taken from the local sources::

            sage: H = CohomologyRing._get_p_group_from_cache_or_db('8gp3',(8,3)); H
            H^*(D8; GF(2))

        Even when we request a computation from scratch, the ring is now taken from
        the cache::

            sage: H is CohomologyRing._get_p_group_from_cache_or_db('8gp3',(8,3), from_scratch=True)
            True

        However, if we remove the ring from the cache and request a computation from
        scratch again, an error is raise because the data for ``H`` can still be found
        on disk in the workspace::

            sage: import os
            sage: del CohomologyRing._cache[H._key]
            sage: CohomologyRing._get_p_group_from_cache_or_db('8gp3',(8,3), from_scratch=True, option='debug')
            Traceback (most recent call last):
            ...
            RuntimeError: You requested a computation from scratch. Please remove .../8gp3

        Let us put `H` back into the cache::

            sage: CohomologyRing._cache[H._key] = H
            sage: H is CohomologyRing._get_p_group_from_cache_or_db('8gp3',(8,3), from_scratch=True)
            True

        If the location of the local sources is explicitly set and write permission
        is granted (which is the case here), it is attempted to get the data from there.
        If this is impossible and remote sources are not being used, ``None`` is returned::

            sage: CohomologyRing.set_local_sources(tmp_dir())
            sage: CohomologyRing._get_p_group_from_cache_or_db('8gp3',(8,3), websource=False) is None
            True

        We test against a bug that was fixed in version 3.0::

            sage: CohomologyRing.set_workspace(tmp_dir())
            sage: H = CohomologyRing(8,1,options='info',from_scratch=True)
            _get_p_group_from_scratch:
                We compute this cohomology ring from scratch
                Computing basic setup for Small Group number 1 of order 2
                Computing basic setup for Small Group number 2 of order 4
                Computing basic setup for Small Group number 1 of order 8
            H^*(SmallGroup(8,1); GF(2)):
                Initialising maximal p-elementary abelian subgroups
            sage: CohomologyRing._cache.clear()
            sage: del H
            sage: H = CohomologyRing(8,1,options='info')
            H^*(SmallGroup(8,1); GF(2)):
                Import monomials
            _get_p_group_from_cache_or_db:
                Checking compatibility of SmallGroups library and stored cohomology ring

        """
        # If data for the given GStem and KEY are available,
        # they are returned, otherwise None.
        ####################
        ## Since v2.1, we insist on always using the user's workspace,
        ## but it may be that we have to link to the local sources
        GStem = str(GStem)
        root_local_sources = COHO.local_sources
        if self._create_local_sources:
            root_workspace = COHO.local_sources
        else:
            root_workspace = COHO.workspace
        file_name = os.path.join(GStem,'H%s.sobj'%GStem)
        OUT = None
        from_scratch = kwds.pop('from_scratch', None)
        websource = kwds.pop('websource', None)
        if from_scratch:
            coho_options['use_web'] = False

        ## 1. Cache
        CacheKey = (KEY, os.path.join(root_workspace,GStem,'dat','State'))
        if CacheKey in self._cache:
            OUT = self._cache[CacheKey]
            if os.access(OUT.autosave_name(), os.R_OK):
                coho_logger.debug("Got %r from cache", None, OUT)
                return OUT
            coho_logger.error("Found in cache, but not on disk. Removing cache item %s", OUT, CacheKey[1])
            del self._cache[CacheKey]
            OUT = None
        ## 2. Directly load from workspace
        if os.access(os.path.join(root_workspace,file_name), os.R_OK):
            coho_logger.debug("Data found at %s", None, os.path.join(root_workspace,file_name))
            if from_scratch:
                raise RuntimeError("You requested a computation from scratch. Please remove %s"%(os.path.join(root_workspace,GStem)))
            try:
                coho_options['@use_this_root@'] = root_workspace
                OUT = load(os.path.join(root_workspace,file_name)) # realpath here?
                if '@use_this_root@' in coho_options:
                    del coho_options['@use_this_root@']
            except BaseException as msg:
                if '@use_this_root@' in coho_options:
                    del coho_options['@use_this_root@']
                raise IOError("Saved data at %s are not readable: %s"%(os.path.join(root_workspace,file_name), msg))
        ## 3. Link with local sources and load from there
        elif root_local_sources and os.access(os.path.join(root_local_sources,file_name), os.R_OK) and not from_scratch:
            coho_logger.debug("Local data found at %s", None, os.path.join(root_local_sources,file_name))
            try:
                coho_logger.debug('Creating symbolic links from %s to %s', None, os.path.join(root_workspace,GStem), os.path.join(root_local_sources,GStem))
                _symlink_to_database(os.path.join(root_local_sources,GStem), os.path.join(root_workspace,GStem))
            except BaseException:
                raise ValueError("Can not create a symbolic link to the local sources. Please remove %s"%(os.path.join(root_workspace,GStem)))
            # now try to load from the new entry in the database
            try:
                coho_options['@use_this_root@'] = root_workspace
                OUT = load(os.path.join(root_workspace,file_name)) # realpath here?
                if '@use_this_root@' in coho_options:
                    del coho_options['@use_this_root@']
            except BaseException as msg:
                if '@use_this_root@' in coho_options:
                    del coho_options['@use_this_root@']
                raise IOError("Saved data at %s are not readable: %s"%(os.path.join(root_local_sources,file_name), msg))
        ## 4. Search web repository
        elif websource!=False and (not from_scratch):
            try:
                if isinstance(websource, (str, unicode)):
                    OUT = self.from_remote_sources(GStem, websource=websource)
                else:
                    OUT = self.from_remote_sources(GStem)
            except URLError as msg:
                if "HTTP Error 404" in str(msg):
                    coho_logger.info("Cohomology ring can not be found in web repository.", None)
                else:
                    coho_logger.debug("Websource %r is not available.", None, kwds.get('websource', 'http://cohomology.uni-jena.de/db/'))
            except (ValueError, RuntimeError):
                coho_logger.info("Cohomology ring can not be found in web repository.", None)
            except KeyboardInterrupt:
                coho_logger.warning("Access to websource was interrupted.", None)
        if OUT is not None:
            GAP = OUT.group().parent()
            _gap_reset_random_seed()
            try:
                OUT.GenS._check_valid()
            except ValueError:
                OUT.reconstruct_singular()
            if len(KEY)==2:
                coho_logger.info('Checking compatibility of SmallGroups library and stored cohomology ring', None)
                if OUT.group().canonicalIsomorphism(gap.SmallGroup(KEY[0],KEY[1])) == Failure:
                    raise ValueError("Stored group data for SmallGroup(%d,%d) incompatible with data in the SmallGroups library"%(KEY[0],KEY[1]))
            for k,v in kwds.items():
                OUT.setprop(k, v)
        return OUT

    def _get_p_group_from_scratch(self, KEY, q, GStem, GroupName, **kwds):
        """
        Initialise the cohomology ring of a finite `p`-group.

        INPUT:

        - ``KEY``: the identifier using which the group will be known
          in the cache.
        - ``q``: The order (integer) of the group
        - ``GStem``: A string that determines filenames for storing data
          associated with the cohomology ring
        - GroupName: A string, used as the name of the group.
        - optional arguments that will be passed to the init method
          of :class:`~pGroupCohomology.cohomology.COHO` or
          :class:`~pGroupCohomology.modular_cohomology.MODCOHO`.

        OUTPUT:

        - A cohomology ring for the given data.

        TESTS::

            sage: from pGroupCohomology import CohomologyRing
            sage: CohomologyRing.doctest_setup()       # reset, block web access, use temporary workspace
            sage: H1 = CohomologyRing._get_p_group_from_scratch((8,3), 8, '8gp3', 'Group1'); H1
            H^*(Group1; GF(2))
            sage: H2 = CohomologyRing._get_p_group_from_scratch(('DihedralGroup(8)',), 8, 'D8', 'Group2'); H2
            H^*(Group2; GF(2))
            sage: H2._key
            (('DihedralGroup(8)',), '.../D8/dat/State')
            sage: CohomologyRing._cache[H2._key] is H2
            True
            sage: H1 is CohomologyRing(8,3)
            True

        """
        from pGroupCohomology.auxiliaries import gap
        coho_logger.info('We compute this cohomology ring from scratch', None)
        if self._create_local_sources:
            root_workspace = COHO.local_sources # SAGE_SHARE+'pGroupCohomology'
        else:
            root_workspace = COHO.workspace #DOT_SAGE+'pGroupCohomology/db/'
        CacheKey = (KEY, os.path.join(root_workspace,GStem,'dat','State'))
        extras = {}
        for k in kwds.items():
            extras[k[0]] = k[1]
        extras['GroupName'] = GroupName
        extras['GStem'] = GStem
        extras['key'] = CacheKey
        extras['root'] = root_workspace
        if len(KEY)==1:
            extras['gap_input'] = q # we must specify the group order
            if isinstance(KEY[0], (str,unicode)):
                OUT = COHO(gap.eval(KEY[0]), **extras)
            else:
                OUT = COHO(gap(KEY[0]), **extras)
        else:
            OUT = COHO(KEY[0],KEY[1], **extras)
        _gap_reset_random_seed()
        try:
            # The original data have to be on disc, since otherwise
            # we'd later assume that the cache is corrupted
            if OUT.knownDeg==0:
                safe_save(OUT, OUT.autosave_name())
        except:
            coho_logger.error("Unable to save basic ring setup", OUT, exc_info=1)
        return OUT

    def _get_non_p_group_from_db(self, GStem, pr, **kwds):
        """
        Try to find a certain cohomology ring of a non-primepower group in a database.

        INPUT:

        - ``GStem``: A string that determines the filename under which the cohomology
          ring is stored
        - ``pr``: A prime number, the modulus of the cohomology ring
        - ``from_scratch``: (optional bool) If ``True``, raise a ``RuntimeError`` if
          data for that ring are already stored in the workspace.
        - ``websource``: (optional string or ``False``) Determines the location of a
          web repository of cohomology rings, or disables the use of a web repository.

        OUTPUT:

        The cohomology ring for the given data, or ``None`` if that ring can not be found.

        NOTE:

        It is not attempted to directly search the cohomology cache, since the computation
        of the key associated with the cohomology ring of a non-primepower group involves
        the computation of certain subgroups and can be very difficult.

        However, *if* data for that ring are in the cache, then they are usually in the
        workspace as well. Since the file in the workspace provides the information
        needed to create the key, caching is possible, as seen in the examples below.

        TESTS::

            sage: from pGroupCohomology import CohomologyRing
            sage: CohomologyRing.doctest_setup()       # reset, block web access, use temporary workspace
            sage: H1 = CohomologyRing(18,3,prime=2)
            sage: H1.make(); H1
            H^*(SmallGroup(18,3); GF(2))
            sage: CohomologyRing._get_non_p_group_from_db('18gp3',2) is H1
            True

        Just for fun, we create a ring in such a way that it can not be loaded from
        a file, and demonstrate that the method under consideration does not use
        the cohomology cache::

            sage: H2 = CohomologyRing(18,4,prime=2,from_scratch=True, options='nosave')
            sage: H2.make(); H2
            H^*(SmallGroup(18,4); GF(2))
            sage: print(CohomologyRing._get_non_p_group_from_db('18gp4',2))
            None

        """
        root_local_sources = COHO.local_sources
        if self._create_local_sources:
            root_workspace = COHO.local_sources # SAGE_SHARE+'pGroupCohomology'
        else:
            root_workspace = COHO.workspace #DOT_SAGE+'pGroupCohomology/db/'
        file_name = 'H%smod%d.sobj'%(GStem,pr)
        OUT = None
        from_scratch = kwds.get('from_scratch')

        ## 1. Directly load from workspace
        if os.access(os.path.join(root_workspace,file_name), os.R_OK):
            if from_scratch:
                raise RuntimeError("You requested a computation from scratch. Please remove %s"%(os.path.join(root_workspace,file_name)))
            try:
                coho_options['@use_this_root@'] = root_workspace
                OUT = load(os.path.join(root_workspace,file_name)) # realpath here?
                if '@use_this_root@' in coho_options:
                    del coho_options['@use_this_root@']
            except BaseException:
                if '@use_this_root@' in coho_options:
                    del coho_options['@use_this_root@']
                raise IOError("Saved data at %s are not readable"%(os.path.join(root_workspace,file_name)))
        ## 2. Link with local sources and load from there
        elif root_local_sources and os.access(os.path.join(root_local_sources,file_name), os.R_OK) and not from_scratch:
            os.symlink(os.path.join(root_local_sources,file_name), os.path.join(root_workspace,file_name))
            # now try to load from the new entry in the database
            try:
                coho_options['@use_this_root@'] = root_workspace
                OUT = load(os.path.join(root_workspace,file_name))  # realpath here?
                if '@use_this_root@' in coho_options:
                    del coho_options['@use_this_root@']
            except BaseException as msg:
                if '@use_this_root@' in coho_options:
                    del coho_options['@use_this_root@']
                raise IOError("%. Saved data at %s are not readable"%(msg, os.path.join(root_local_sources,file_name)))
        # 3. Unless the user forbids it, try to obtain it from some web source
        elif kwds.get('websource')!=False and not kwds.get('from_scratch'):
            try:
                if isinstance(kwds.get('websource'), (str, unicode)):
                    OUT = self.from_remote_sources(GStem, websource=str(kwds.get('websource')))
                else:
                    OUT = self.from_remote_sources(GStem)
            except:
                coho_logger.info("No cohomology ring found in web repository.", None)
        if OUT is not None:
            _gap_reset_random_seed()
            try:
                OUT.GenS._check_valid()
            except ValueError:
                OUT.reconstruct_singular()
        return OUT

    def from_subgroup_tower(self, *args, **kwds):
        """
        Given a tower of subgroups starting with a Sylow subgroup, compute
        a cohomology ring with stability conditions associated with that subgroup.

        INPUT:

        - Some nested groups ascendingly sorted starting with a prime power group
        - Keyword arguments similar to the ones of :class: ~pGroupCohomology.factory.CohomologyRingFactory`.

        OUTPUT:

        The cohomology of the last of the given subgroups (without computing
        the ring structure).

        EXAMPLES:

        Notmally, we compute the mod-`p` cohomology of a finite non-primepower
        group `G` as a subring of the cohomology ring of `N_G(Z(Syl_p(G)))`, which
        in turn is computed as a subring of the cohomology ring of `Syl_p(G)`.
        If one wants to compute the cohomology of `G` using a different subgroup
        tower, this method can be used. The computation of the mod-`2` cohomology
        of the third Conway group, for example, was possible using a tower of
        four subgroups, which reduced the total number of stability conditions to
        `11`. In the following example, we do the opposite and compute the cohomology
        ring of the alternating group of rank `8` without an intermediate subgroup.

        But first, we compute the cohomology in the default way::

            sage: from pGroupCohomology import CohomologyRing
            sage: CohomologyRing.doctest_setup()
            sage: A8 = libgap.AlternatingGroup(8)
            sage: SylA8 = A8.SylowSubgroup(2).MinimalGeneratingSet().Group()
            sage: HA8 = CohomologyRing(A8, prime=2, GroupName="A_8")
            sage: HA8.make()

        Here is the non-standard way::

            sage: HA8_direct = CohomologyRing.from_subgroup_tower(SylA8, A8, GroupName="A8", GroupDescr='AlternatingGroup(8)')
            sage: HA8_direct.make()

        Apparently, the ring structures thus computed look different::

            sage: print(HA8)
            Cohomology ring of A_8 with coefficients in GF(2)
            <BLANKLINE>
            Computation complete
            Minimal list of generators:
            [b_2_0: 2-Cocycle in H^*(A_8; GF(2)),
             c_4_1: 4-Cocycle in H^*(A_8; GF(2)),
             b_6_1: 6-Cocycle in H^*(A_8; GF(2)),
             b_6_2: 6-Cocycle in H^*(A_8; GF(2)),
             b_3_0: 3-Cocycle in H^*(A_8; GF(2)),
             b_3_1: 3-Cocycle in H^*(A_8; GF(2)),
             b_5_2: 5-Cocycle in H^*(A_8; GF(2)),
             b_7_5: 7-Cocycle in H^*(A_8; GF(2)),
             b_7_6: 7-Cocycle in H^*(A_8; GF(2))]
            Minimal list of algebraic relations:
            [b_3_0*b_3_1,
             b_3_0*b_5_2,
             b_2_0*b_7_5,
             b_2_0*b_7_6,
             b_6_1*b_3_0,
             b_6_2*b_3_0,
             b_3_0*b_7_5,
             b_3_0*b_7_6,
             b_3_1*b_7_5,
             b_3_1*b_7_6,
             b_5_2^2+b_2_0*b_3_1*b_5_2+b_2_0^2*b_6_2+c_4_1*b_3_1^2,
             b_6_1*b_6_2+b_6_1^2+b_2_0^2*b_3_1*b_5_2+b_2_0^3*b_6_2+c_4_1*b_3_1*b_5_2+b_2_0*c_4_1*b_3_1^2+b_2_0*c_4_1*b_6_2,
             b_5_2*b_7_5,
             b_5_2*b_7_6,
             b_6_1*b_7_6+b_6_1*b_7_5,
             b_6_2*b_7_5+b_6_1*b_7_5,
             b_7_5*b_7_6+b_7_5^2]
            sage: print(HA8_direct)
            Cohomology ring of AlternatingGroup(8) with coefficients in GF(2)
            <BLANKLINE>
            Computation complete
            Minimal list of generators:
            [b_2_0: 2-Cocycle in H^*(A8; GF(2)),
             c_4_1: 4-Cocycle in H^*(A8; GF(2)),
             b_6_3: 6-Cocycle in H^*(A8; GF(2)),
             b_6_5: 6-Cocycle in H^*(A8; GF(2)),
             b_3_0: 3-Cocycle in H^*(A8; GF(2)),
             b_3_1: 3-Cocycle in H^*(A8; GF(2)),
             b_5_1: 5-Cocycle in H^*(A8; GF(2)),
             b_7_5: 7-Cocycle in H^*(A8; GF(2)),
             b_7_6: 7-Cocycle in H^*(A8; GF(2))]
            Minimal list of algebraic relations:
            [b_3_0*b_3_1,
             b_3_1*b_5_1,
             b_2_0*b_7_5,
             b_2_0*b_7_6,
             b_6_3*b_3_1+b_2_0*c_4_1*b_3_1,
             b_6_5*b_3_1,
             b_3_0*b_7_5,
             b_3_0*b_7_6,
             b_3_1*b_7_5,
             b_3_1*b_7_6,
             b_5_1^2+b_2_0*b_3_0*b_5_1+b_2_0^2*b_6_5+c_4_1*b_3_0^2,
             b_3_0^4+b_6_5*b_3_0^2+b_6_3*b_6_5+b_6_3^2+b_2_0^2*b_3_0*b_5_1+b_2_0^3*b_6_5+c_4_1*b_3_0*b_5_1+b_2_0*c_4_1*b_3_0^2+b_2_0^2*c_4_1^2,
             b_5_1*b_7_5,
             b_5_1*b_7_6,
             b_6_3*b_7_6+b_6_3*b_7_5,
             b_6_5*b_7_5+b_6_3*b_7_5,
             b_7_5*b_7_6+b_7_5^2]

        But of course the two rings are isomorphic::

            sage: HA8.is_isomorphic(HA8_direct)
            ('1*b_2_0',
             '1*c_4_1',
             '1*b_3_0^2+1*b_6_3+1*b_2_0*c_4_1',
             '1*b_6_5',
             '1*b_3_1',
             '1*b_3_0',
             '1*b_5_1',
             '1*b_7_5',
             '1*b_7_6')

        The default way of computation is in fact more efficient, since less
        stability conditions are involved::

            sage: len(HA8._PtoPcapCPdirect)
            4
            sage: len(HA8.subgroup_cohomology()._PtoPcapCPdirect)
            1
            sage: len(HA8_direct._PtoPcapCPdirect)
            18

        """
        assert len(args)>1, "At least two groups must be provided."
        G0 = args[0]
        q = G0.Order().sage()
        assert q.is_prime_power(), "The first argument must be a prime power group"
        p = q.factor()[0][0]
        GroupName = kwds.pop('GroupName', None)
        if isinstance(GroupName, (list,tuple)):
            assert len(GroupName)==len(args), "Number of group names does not coincide with the height of the subgroup tower"
            GroupNames = GroupName
        elif GroupName is not None:
            GroupNames = ['Syl_{}_{}'.format(p, GroupName)]
            for i in range(1, len(args)-1):
                GroupNames.append('Subgp_{}_{}'.format(i, GroupName))
            GroupNames.append(GroupName)
        else:
            GroupNames = [None]*len(args)
        GroupDescr = kwds.pop('GroupDescr', None)
        if isinstance(GroupDescr, (list,tuple)):
            assert len(GroupDescr)==len(args), "Number of group names does not coincide with the height of the subgroup tower"
            GroupDescrs = GroupDescr
        elif GroupDescr is not None:
            GroupDescrs = ['Sylow {}-subgroup of {}'.format(p, GroupDescr)]
            for i in range(1, len(args)-1):
                GroupDescrs.append('{} intermediate subgroup of {}'.format(ZZ(i).ordinal_str(), GroupDescr))
            GroupDescrs.append(GroupDescr)
        else:
            GroupDescrs = [None]*len(args)
        for i in range(len(args)-1):
            assert args[i+1].IsSubgroup(args[i]), "{} argument has to be a subgroup of the {} argument".format(Integer(i+1).ordinal_str(), Integer(i).ordinal_str())
        assert (args[-1].Order().sage()/q)%p, "First given group must be a Sylow {}-subgroup of the last given group".format(p)
        H0 = CohomologyRing(G0, GroupName = GroupNames.pop(0), GroupDescr = GroupDescrs.pop(0), **kwds)
        H0.make()
        H0._verify_consistency_of_dimensions()
        while i in range(1,len(args)-1):
            G1 = args[i]
            H1 = CohomologyRing(G1, SubgpCohomology=H0, Subgroup=G0, prime=p, from_scratch=True, GroupName = GroupNames.pop(0), GroupDescr = GroupDescrs.pop(0), **kwds)
            H1.make()
            H0 = H1
            G0 = G1
            H0._verify_consistency_of_dimensions()
        return CohomologyRing(args[-1], SubgpCohomology=H0, Subgroup=G0, prime=p, GroupName = GroupNames.pop(0), GroupDescr = GroupDescrs.pop(0), from_scratch=True, **kwds)

    def __call__ (self, *args, **kwds):
        """
        Create the mod-p cohomology ring of a finite groups

        Of course, isomorphic p-Groups have isomorphic cohomology
        rings.  However, the presentation of the cohomology rings as
        obtained by our package depends on the choice of a minimal
        generating set of the p-group.

        If a `p`-group `G` is given by its position in the SmallGroups
        library, then this position, perhaps together with a custom
        name provided by the user, forms a unique key for the
        cohomology ring.

        If `G` is given as a group in the libgap interface, then it is
        required that the first items on the list of generators of `G`
        forms a minimal generating set. If this is not the case, an
        error is raised. We transform `G` into a permutation group
        whose generators correspond to a minimal generating set of
        `G`. The description of that permutation group, perhaps
        together with a custom name, forms a unique key for the
        cohomology ring.

        The unique key also depends on the chosen folders containing
        data of the ring.

        TESTS::

            sage: from pGroupCohomology import CohomologyRing
            sage: CohomologyRing.doctest_setup()       # reset, block web access, use temporary workspace

        Since the cohomology of the dihedral group of order 8 is
        part of the local sources, the ring is complete::

            sage: H0 = CohomologyRing(8,3) # indirect doctest
            sage: print(H0)
            Cohomology ring of Dihedral group of order 8 with coefficients in GF(2)
            <BLANKLINE>
            Computation complete
            Minimal list of generators:
            [c_2_2: 2-Cocycle in H^*(D8; GF(2)),
             b_1_0: 1-Cocycle in H^*(D8; GF(2)),
             b_1_1: 1-Cocycle in H^*(D8; GF(2))]
            Minimal list of algebraic relations:
            [b_1_0*b_1_1]

        Choosing a different root directory results in another copy
        of the same ring::

            sage: CohomologyRing.set_workspace(tmp_dir())
            sage: H1 = CohomologyRing(8,3)
            sage: H0 is H1
            False
            sage: H0 == H1
            True

        Creating a third location, we can ask that the ring will
        not be loaded from either local or remote sources.
        By consequence, the returned ring is not complete yet and
        is therefor not equal to the previous rings, unless we
        complete it::

            sage: CohomologyRing.set_workspace(tmp_dir())
            sage: H2 = CohomologyRing(8,3,from_scratch=True)
            sage: H0 == H2
            False
            sage: H2.make()
            sage: H0 == H2
            True

        If the group order is smaller than 128, then the cohomology
        ring is not downloaded from a remote source::

            sage: CohomologyRing.reset()
            sage: CohomologyRing.set_workspace(tmp_dir())
            sage: H = CohomologyRing(125,3,options='info')
            _get_p_group_from_scratch:
                We compute this cohomology ring from scratch
                Computing basic setup for Small Group number 1 of order 5
                Computing basic setup for Small Group number 2 of order 25
                Computing basic setup for Small Group number 3 of order 125
            ...
            sage: print(H)
            Cohomology ring of Extraspecial 5-group of order 125 and exponent 5 with coefficients in GF(5)
            <BLANKLINE>
            Computed up to degree 0
            Minimal list of generators:
            []
            Minimal list of algebraic relations:
            []

        """
        from pGroupCohomology.modular_cohomology import MODCOHO
        import os
        global coho_options
        root_local_sources = COHO.local_sources
        if self._create_local_sources:
            root_workspace = COHO.local_sources # SAGE_SHARE+'pGroupCohomology'
        else:
            root_workspace = COHO.workspace #DOT_SAGE+'pGroupCohomology/db/'
        # Basic idea:
        # The key shall both be a unique pointer to the data in the file
        # system and a descriptor of the group-with-minimal-generators.
        # Hence, it is the root directory plus the stem name plus [either
        # the position in the SmallGroups library or a permutation group
        # presentation].
        # The GroupName and other properties are extra arguments


        # If cohomology options are required, they are provided now.
        # Note that these are valid for any subsequent computations with
        # any cohomology ring: The options are not associated with the
        # ring that we are returning below.
        if 'root' in kwds:
            raise ValueError("The syntax for ``CohomologyRing`` has changed. Don't provide the ``root`` keyword, but use the ``set_workspace`` method instead")
        opts = kwds.get('options')
        if opts is not None:
            if isinstance(opts, (str,unicode)):
                self.global_options(str(opts))
            elif isinstance(opts, dict):
                coho_options.update(opts)
            else:
                self.global_options(*opts)
        if kwds.get('from_scratch'):
            coho_options['use_web'] = False

        # CHECK ADMISSIBILITY OF THE INPUT
        from pGroupCohomology.resolution import coho_options
        # _gap_reset_random_seed is done inside check_arguments
        GapName = None
        if len(args)==1 and args[0].HasName():
            GapName = args[0].Name().sage()
        q, Hfinal = self.check_arguments(args,minimal_generators=kwds.get('minimal_generators'),GroupId=kwds.get('GroupId'))
        KEY = self.create_group_key(args, GroupId=kwds.get('GroupId'), GroupDefinition=kwds.get('GroupDefinition'))
        gap = Hfinal.parent()
        if len(KEY) == 2:
            args = [KEY[0],KEY[1]]
        else:
            args = [Hfinal]

        # In the non prime power case, we need to be provided
        # with a prime modulus.
        pr = None
        if not q.is_prime_power():
            pr = kwds.get('prime')
            if pr is None:
                raise ValueError("The parameter `prime` must be provided")
            try:
                pr = Integer(pr)
                if not pr.is_prime():
                    raise ValueError
            except:
                raise ValueError("The parameter `prime=%s` must provide a prime number"%repr(pr))
            if not pr.divides(q):
                raise ValueError("The parameter `prime=%d` must divide the group order %d"%(pr,q))

        ############
        # Take care of GStem and GroupName.
        GStem = self.gstem(args, GStem=kwds.get('GStem'), GroupName=kwds.get('GroupName') or GapName, GroupId=kwds.get('GroupId'))
        GroupName = self.group_name(args, GroupName=kwds.get('GroupName'))

        # KEY now either provides the coordinates (q,n) of a group in the small
        # groups library, or is of the form (s,) with a string s such
        # that libgap.eval(s) defines a group with an appropriate generating set.
        # It can be hashed.
        # Moreover the stem name (GStem) is set up, and we may have
        # a different GroupName (or None).
        extras ={}
        for k,v in kwds.items():
            if k not in ['pr','GStem','KEY','GroupName','q']:
                extras[k] = v

        if q.is_prime_power():
            CacheKey = (KEY, os.path.join(root_workspace,GStem,'dat','State'))
            if q < 128:
                extras['websource'] = False
            OUT = self._check_compatibility(CacheKey, self._get_p_group_from_cache_or_db(GStem, KEY, **extras) or self._get_p_group_from_scratch(KEY, q, GStem, GroupName, **extras))
            return OUT

        # For non prime power groups, we need a sufficiently large subgroup.
        # Hfinal is available (even if KEY==(q,n))
        ## 1. Try to load the result, knowing GStem and KEY The KEY
        ## does not contain information on the subgroup, and can thus
        ## not be used to directly access the _cache. But *IF* it
        ## can be loaded then the _cache is used, if possible. So,
        ## this will work, unless the user did not want to save the
        ## cohomology ring on disk.
        OUT = self._get_non_p_group_from_db(GStem, pr, **extras)
        if OUT is not None:
            # Test if the group is OK
            if Hfinal.canonicalIsomorphism(OUT.group()) == Failure:
                raise ValueError("The stored cohomology ring %r does not match the given group"%(OUT))

        ## If a subgroup or its cohomology is given, test consistency
        Subgroup = kwds.get('Subgroup')
        SubgpId = kwds.get('SubgpId')
        HP = kwds.get('SubgpCohomology')
        SylowSubgroup = kwds.get('SylowSubgroup')
        HSyl = kwds.get('SylowSubgpCohomology')
        ## 1. consistency with OUT, the stored ring
        if OUT is not None:
            # consistency vs. subgroup
            if (HP is not None) and (HP is not OUT._HP):
                raise ValueError("The stored cohomology ring %r is not defined as a subring of %r"%(OUT, HP))
            if (Subgroup is not None) and Subgroup.canonicalIsomorphism(OUT.subgroup()) == Failure:
                raise ValueError("The stored cohomology ring %r is not computed using the given subgroup"%(OUT))
            # consistency vs. Sylow subgroup
            if (HSyl is not None) and (HSyl is not OUT._HSyl):
                raise ValueError("The stored cohomology ring %r is not defined as a subring of %r"%(OUT, HP))
            if (SylowSubgroup is not None) and (SylowSubgroup.canonicalIsomorphism(OUT.sylow_subgroup()) == Failure):
                raise ValueError("The stored cohomology ring %r is not computed using the given Sylow subgroup"%(OUT))
            ## These were enough consistency checks!
            return OUT

        ## At this point, we need to do the hard work and compute the
        ## cohomology from scratch. The given subgroups may help,
        ## but have to be consistent.
        # 1. check HP and HSyl
        if HP is not None:
            if not isinstance(HP,COHO):
                raise TypeError("`SubgpCohomology` must be %s"%COHO)
            HSyl = HP._HSyl or HP # ignore the keyword argument for HSyl
        if HSyl is not None:
           if not isinstance(HSyl,COHO):
               raise TypeError("The given cohomology of a Sylow subgroup is not a cohomology ring")
           if isinstance(HSyl,MODCOHO):
               raise TypeError("The given cohomology of a Sylow subgroup does in fact not belong to a prime power group")
        # 2. check subgroup
        if Subgroup is not None:
            if not Hfinal.IsSubgroup(Subgroup):
                raise ValueError("The given subgroup is in fact not a subgroup")
            if pr.divides(Hfinal.Index(Subgroup).sage()):
                raise ValueError("The given subgroup must contain a Sylow %d-subgroup"%pr)
##            if HP is not None:
##                if gap.eval('canonicalIsomorphism(%s,%s)'%(Subgroup.name(),HP.group().name()))=='fail':
##                    raise ValueError, "The given subgroup does not match its given cohomology ring"
        ## 3. check Sylow subgroup
        if SylowSubgroup is not None:
            if not Hfinal.IsSubgroup(SylowSubgroup):
                raise ValueError("The given Sylow subgroup is in fact not a subgroup")
            if pr.divides(Hfinal.Index(SylowSubgroup).sage()):
                raise ValueError("The index of the given Sylow %d-subgroup is not coprime to %d"%(pr,pr))
            if not pr.divides(SylowSubgroup.Order().sage()):
                raise ValueError("The given Sylow subgroup's order is indivisible by %d"%pr)
            if Subgroup is not None:
                if not Subgroup.IsSubgroup(SylowSubgroup):
                    raise ValueError("The given subgroup must contain the given Sylow subgroup")
##            if HSyl is not None:
##                if gap.eval('canonicalIsomorphism(%s,%s)'%(SylowSubgroup.name(),HSyl.group().name()))=='fail':
##                    raise ValueError, "The given subgroup does not match its given cohomology ring"

        ##################################
        # Begin to construct the basic data
        # First step: Get the (Sylow) subgroup related with the given cohomology
        phiSub = None
        phiSyl = None
        SubgroupTested = False
        SylowTested = False
        # 1a) Try to match with a given cohomology ring
        if Subgroup is None:
            if HP is not None:
                try:
                    #~ phiSub=gap('IsomorphicSubgroups(%s,%s:findall:=false)'%(HP.group().name(),Hfinal.name()))[1]
                    phiSub = HP.group().OneIsomorphicSubgroup(Hfinal)
                    #~ Subgroup = gap('Group(List([1..Length(GeneratorsOfGroup(%s))], x -> Image(%s, GeneratorsOfGroup(%s)[x])))'%(HP.group().name(),phiSub.name(),HP.group().name()))
                    Subgroup = gap.Group([phiSub.Image(g) for g in HP.group().GeneratorsOfGroup()])
                except TypeError:
                    raise ValueError("Unable to find a subgroup compatible with the argument `SubgpCohomology`")
                SubgroupTested = True
        else:
            if HP is not None:
                phiSub = HP.group().canonicalIsomorphism(Subgroup)
                if phiSub == Failure:
                    raise ValueError("The arguments `Subgroup` and `SubgpCohomology` don't match")
                SubgroupTested=True
        # 1b) dito for the Sylow subgroup
        if SylowSubgroup is None:
            if (HP is not None) and (phiSub is not None):
                #~ SylowSubgroup = gap('Group(List([1..Length(GeneratorsOfGroup(%s))], x -> Image(%s, GeneratorsOfGroup(%s)[x])))'%((HP.sylow_subgroup or HP.group)().name(),phiSub.name(),(HP.sylow_subgroup or HP.group)().name()))
                SylowSubgroup = gap.Group([phiSub.Image(g) for g in (HP.sylow_subgroup or HP.group)().GeneratorsOfGroup()])
                SylowTested = True
            elif HSyl is not None:
                try:
                    SylowSubgroup = (Hfinal if Subgroup is None else Subgroup).SylowSubgroup(pr)
                    phiSyl = HSyl.group().IsomorphismGroups(SylowSubgroup.name())
                    SylowSubgroup = gap.Group([phiSyl.Image(g) for g in HSyl.group().GeneratorsOfGroup()])
                except:
                    raise ValueError("Unable to find a Sylow subgroup compatible with the given arguments `SubgpCohomology` or `SylowSubgpCohomology`")
                SylowTested = True
        else:
            if HSyl is not None:
                phiSub = HSyl.group().canonicalIsomorphism(SylowSubgroup)
                if phiSub == Failure:
                    raise ValueError("The arguments `SylowSubgroup` and `SylowSubgpCohomology` don't match")
                SylowTested=True


        #####
        # Second step: Get the cohomology of the subgroups
        if SylowSubgroup is None:
            coho_logger.info( "Try to compute a Sylow %d-subgroup", None, pr)
            SylowSubgroup = (Hfinal if Subgroup is None else Subgroup).SylowSubgroup(pr)
            # We are free in choosing generators, since apparently HSyl was not given
        if HSyl is None:
            try:
                coho_logger.debug( "Try to find the SmallGroups address of the Sylow subgroup", None)
                SylowId = SylowSubgroup.IdGroup().sage()
            except BaseException as msg:
                if not ("group identification" in str(msg)):
                    raise msg
                coho_logger.warning( "SmallGroups address not available. Computing the order", None)
                SylowId = [Integer(SylowSubgroup.Order()),0]
            if SylowId[1]>0:
                phiSyl = gap.SmallGroup(SylowId[0],SylowId[1]).IsomorphismGroups(SylowSubgroup)
                SylowSubgroup = gap.Group([phiSyl.Image(g) for g in phiSyl.Source().GeneratorsOfGroup()])
                HSyl = CohomologyRing(SylowId[0],SylowId[1], useElimination=kwds.get('useElimination'), auto=kwds.get('auto'), useFactorization=kwds.get('useFactorization'))
            else:
                coho_logger.info("Try to find a minimal generating set", None)
                SylowSubgroup = SylowSubgroup.MinimalGeneratingSet().Group()
                HSyl = CohomologyRing(SylowSubgroup,useElimination=kwds.get('useElimination'), auto=kwds.get('auto'), useFactorization=kwds.get('useFactorization'), GroupName='SylowSubgroup(%s,%d)'%(GroupName or GStem,pr))
        # By now, we have HSyl and SylowSubgroup

        if kwds.get('OneStep'):
            Subgroup = SylowSubgroup
            HP = HSyl
            SubgpComputedFromScratch = False
        if Subgroup is None:
            coho_logger.info("Computing intermediate subgroup", None)
            Subgroup = Hfinal.Normalizer(SylowSubgroup.Centre())
            qP = Integer(Subgroup.Order())
            if qP==q or qP.is_prime_power():
                # Subgroup=Hfinal or =SylowSubgroup
                # In both cases, we are reduced to the OneStep case
                Subgroup = SylowSubgroup
                HP = HSyl
                SubgpComputedFromScratch = False
            else:
                SubgpComputedFromScratch = True
        else:
            SubgpComputedFromScratch = False

        if HP is None:
            try:
                coho_logger.info( "Try to find the SmallGroups address of the intermediate subgroup",None)
                SubgpId = Subgroup.IdGroup().sage()
            except BaseException as msg:
                if not ("group identification" in str(msg)):
                    raise msg
                coho_logger.info( "SmallGroups address not available. Computing the order", None)
                SubgpId = [Integer(Subgroup.Order()),0]
            if SubgpId[1]>0: # SmallGroup name is better than my custom names
                phiSub = gap.SmallGroup(SubgpId[0],SubgpId[1]).IsomorphismGroups(Subgroup)
                Subgroup = gap.Group([phiSub.Image(g) for g in phiSub.Source().GeneratorsOfGroup()])
                #~ gap('Group(List([1..Length(GeneratorsOfGroup(Source(%s)))],x->Image(%s,GeneratorsOfGroup(Source(%s))[x])))'%(phiSub.name(),phiSub.name(),phiSub.name()))
                HP = CohomologyRing(Subgroup,SubgpId=SubgpId,prime=pr,SylowSubgroup=SylowSubgroup,SylowSubgpCohomology=HSyl,GStem='%dgp%d'%(SubgpId[0],SubgpId[1]), useElimination=kwds.get('useElimination'),useFactorization=kwds.get('useFactorization'))
            elif SubgpComputedFromScratch:
                # no minimal generating set needed
                SubgpId=None
                HP = CohomologyRing(Subgroup, prime=pr, SylowSubgpCohomology=HSyl, SylowSubgroup=SylowSubgroup, OneStep=True, GroupName='Normalizer(%s,Centre(SylowSubgroup(%s,%d)))'%(GroupName or GStem, GroupName or GStem,pr), useElimination=kwds.get('useElimination'),useFactorization=kwds.get('useFactorization'))
            else:
                HP = CohomologyRing(Subgroup, prime=pr, SylowSubgpCohomology=HSyl, SylowSubgroup=SylowSubgroup, OneStep=True, GroupName='IntermediateSubgroup(%s,%d)'%(GroupName or GStem,pr), useElimination=kwds.get('useElimination'),useFactorization=kwds.get('useFactorization'))

        ############
        # By now, we have both subgroups and their cohomology rings.
        if not HP.completed:
            HP.make()
        # not needed for HSyl, since it was computed when we
        # initialised HP

        ############
        # By now, SylowSubgroup is equal to HP.sylow_subgroup() under the canonical map from Subgroup to HP.group().
        # However, it is not necessarily true that their GENERATING SETS are related by the canonical map.
        # This will be taken care of in MODCOHO.__init__.

        ##################################
        #
        # Extending the group key, so that we can finally see if it is
        # cached.
        #
        # We try to find the cohomology ring in the cache.
        # It is already tested that it is not on disk

        CacheKey = (KEY, GStem, HP._key, pr)
        OUT = self._cache.get(CacheKey)

        if OUT is not None:
            if OUT._key != CacheKey:
                similarity = _IsKeyEquivalent(CacheKey,OUT._key)
                if similarity:
                    if similarity == 1:
                        coho_logger.warning('Stored cohomology data have a different group description, but they seem to be equivalent', OUT)
                    return OUT
                else:
                    raise ValueError("Cohomology ring cache is broken for %s"%repr(OUT))
            else:
                return OUT
        # If we have no GroupId, we have already computed permutation representations
        if len(KEY)==1:
            if not Hfinal.IsPermGroup():
                GPerm = gap.eval(KEY[0])
                tmpPhi = Hfinal.GroupHomomorphismByImages(GPerm, Hfinal.GeneratorsOfGroup(), GPerm.GeneratorsOfGroup())
                PPerm = gap.Group([ tmpPhi.Image(g) for g in Subgroup.GeneratorsOfGroup() ])
                #~ tmpPhi = gap('GroupHomomorphismByImages(%s,%s,GeneratorsOfGroup(%s),GeneratorsOfGroup(%s))'%(Hfinal.name(),GPerm.name(),Hfinal.name(),GPerm.name()))
                #~ PPerm = gap('Group(List([1..Length(GeneratorsOfGroup(%s))], x->Image(%s,GeneratorsOfGroup(%s)[x])))'%(Subgroup.name(),tmpPhi.name(),Subgroup.name()))
            else:
                GPerm = Hfinal
                PPerm = Subgroup
                tmpPhi = None

        if len(KEY)==1:
            OUT = MODCOHO(Hfinal, pr, HP, Subgroup, GroupName=GroupName, GStem=GStem, GroupDescr=kwds.get('GroupDescr'), SubgpId=SubgpId, SubgpPerm=PPerm, GPerm=GPerm, useElimination=kwds.get('useElimination'),useFactorization=kwds.get('useFactorization'))
        else:
            OUT = MODCOHO(Hfinal, pr, HP, Subgroup, GroupName=GroupName, GStem=GStem, GroupDescr=kwds.get('GroupDescr'), SubgpId=SubgpId, GroupId=KEY, useElimination=kwds.get('useElimination'),useFactorization=kwds.get('useFactorization'))
        if OUT._key != CacheKey:
            if len(OUT._key[0])==1:
                GKEY = ''.join([t.strip() for t in OUT._key[0][0].split()])
                tmpKey = list(OUT._key)
                tmpKey[0] = (GKEY,)
                OUT.setprop('_key',tuple(tmpKey))
            if OUT._key != CacheKey:
                raise RuntimeError("Cache keys are corrupted")
            else:
                coho_logger.info( "Trying to update data on disk", OUT)
                safe_save(OUT,OUT.autosave_name())
        #self._cache[CacheKey] = OUT # not necessary, since MODCOHO.__init__ inserts into the cache
        _gap_reset_random_seed()
        try:
            # The original data have to be on disc, since otherwise
            # we'd later assume that the cache is corrupted
            if OUT.knownDeg==0:
                safe_save(OUT, OUT.autosave_name())
        except:
            coho_logger.error("Unable to save basic ring setup", OUT, exc_info=1)
        return OUT

    def set_workspace(self, s = None):
        """
        Define the location of the user's workspace.

        INPUT:

        ``s``, a string providing a folder name, or ``None``.

        OUTPUT:

        If ``s`` is a string, a cohomology database in the folder
        ``s`` will be activated as the user's workspace. Write permission
        for that folder is required. If it is ``None``, a workspacee in
        a default location will be activated.

        NOTE:

        If necessary, the folder will be created as soon as data from
        ``s`` are requested.

        EXAMPLES::

            sage: from pGroupCohomology import CohomologyRing
            sage: CohomologyRing.doctest_setup()       # reset, block web access, use temporary workspace
            sage: tmp_root = tmp_dir()
            sage: CohomologyRing.set_workspace(tmp_root)
            sage: H = CohomologyRing(8,3)
            sage: H.root.startswith(os.path.realpath(tmp_root))
            True

        """
        import os
        if s is None:
            s = os.path.realpath(os.path.join(DOT_SAGE,'pGroupCohomology','db'))
        if not isinstance(s, (str,unicode)):
            raise TypeError("String (pathname) expected")
        s = str(s)
        if os.path.exists(s):
            if not os.path.isdir(s):
                raise OSError("There is a file %s that we won't overwrite"%s)
            if not os.access(s,os.W_OK):
                raise OSError("The folder %s is not writeable"%s)
        else:
            os.makedirs(s)
        COHO.workspace = s

    def from_workspace(self,*args, **kwds):
        """
        Retrieve a cohomology ring from the workspace.

        NOTE:

        By default, the user's current workspace is hosting the
        computation anyway. However, it is possible that the data is in
        fact copied from local sources outside of the workspace. This
        method temporarily disallows the use of other local or remote
        sources, so that it is guaranteed that only "fresh" data in the
        workspace are used.

        EXAMPLES::

            sage: from pGroupCohomology import CohomologyRing
            sage: CohomologyRing.doctest_setup()       # reset, block web access, use temporary workspace
            sage: H = CohomologyRing.from_workspace(8,3)
            sage: print(H)
            Cohomology ring of Dihedral group of order 8 with coefficients in GF(2)
            <BLANKLINE>
            Computed up to degree 0
            Minimal list of generators:
            []
            Minimal list of algebraic relations:
            []

        """
        create_local_sources = self._create_local_sources
        old_local_sources = COHO.local_sources
        COHO.local_sources = None
        old_remote_sources = COHO.remote_sources
        COHO.remote_sources = ()
        self.set_local_sources(False)
        try:
            return self(*args, **kwds)
        finally:
            self._create_local_sources = create_local_sources
            COHO.local_sources = old_local_sources
            COHO.remote_sources = old_remote_sources

    def set_remote_sources(self, URLs = None):
        """
        Redefine the default locations of web repositories for cohomology rings

        INPUT:

        ``URLs``, a tuple of strings providing a URLs, or ``None``.

        If ``URLs`` is a tuple, then cohomology rings will be sought
        in the repositories denoted by the URLs (in the order given).
        In particular, if the tuple is empty, no web repositories will
        be used.
        If it is ``None``, the locations are reset to some default.

        EXAMPLES::

            sage: from pGroupCohomology import CohomologyRing
            sage: from sage.env import SAGE_SHARE
            sage: CohomologyRing.doctest_setup()       # reset, block web access, use temporary workspace

        During package installation, internet access is impossible.
        Therefore, we simulate the use of a web repository by accessing
        local files that are available during package installation::

            sage: CohomologyRing.set_remote_sources(('file://'+os.path.join(os.path.realpath(os.path.curdir),'test_data'),))
            sage: H = CohomologyRing.from_remote_sources('8gp3')
            sage: print(H)
            Cohomology ring of Dihedral group of order 8 with coefficients in GF(2)
            <BLANKLINE>
            Computation complete
            Minimal list of generators:
            [c_2_2: 2-Cocycle in H^*(D8; GF(2)),
             b_1_0: 1-Cocycle in H^*(D8; GF(2)),
             b_1_1: 1-Cocycle in H^*(D8; GF(2))]
            Minimal list of algebraic relations:
            [b_1_0*b_1_1]

        """
        if URLs is None:
            URLs = ('http://cohomology.uni-jena.de/db/',)
        if isinstance(URLs, tuple):
            COHO.remote_sources = URLs
        else:
            raise TypeError("Tuple expected")


    # TODO: non prime power groups
    def from_remote_sources(self, GStem, websource = None, prime=None):
        """
        Import a cohomology ring from a web source.

        NOTE:

        Usually this function would not be directly used. It is
        automatically called by
        :func:`~pGroupCohomology.CohomologyRing` if a cohomology ring
        can not be found in a local folder.

        INPUT:

        - ``GStem``, a string so that ``GStem+'.tar.gz'`` can be found
          in the web source, if it is a prime power group, or
          ``'H'+GStem+'mod%d.sobj'%prime`` otherwise.
        - ``websource``: If ``None`` (default), the currently known
          URLs of web repositories (those provided by
          :meth:`~pGroupCohomology.factory.CohomologyRingFactory.set_remote_sources`)
          are chosen. If ``False``, no remote source is used. Otherwise, it
          should be a single URL (string) or tuple of URLs.
        - ``prime``: An optional prime, the modulus of the cohomology
          ring. It must be provided if ond *only* if the group is not
          a prime power group.

        NOTE:

        During doctests, the web access is usually switched off,

        TESTS:

        We choose a low logging level, so that it is visible what happens
        behind the scenes.
        ::

            sage: from pGroupCohomology import CohomologyRing
            sage: from sage.env import SAGE_SHARE
            sage: CohomologyRing.doctest_setup()       # reset, block web access, use temporary workspace
            sage: CohomologyRing.global_options('info')

        During package installation, and thus also during its doctests,
        web access is blocked. Therefore, we simulate a data base using
        local files that are available during package installation::

            sage: H = CohomologyRing.from_remote_sources('8gp3', websource='file://'+os.path.join(os.path.realpath(os.path.curdir),'test_data'))
            from_remote_sources:
                Accessing web
                Press Ctrl-c to interrupt web access.
                Downloading and extracting archive file
                Trying to read downloaded data
            Resolution of GF(2)[8gp3]:
                Differential reloaded
                > rk P_02 =   3
                Differential reloaded
                > rk P_03 =   4
            H^*(D8; GF(2)):
                Import monomials
            sage: print(H)
            Cohomology ring of Dihedral group of order 8 with coefficients in GF(2)
            <BLANKLINE>
            Computation complete
            Minimal list of generators:
            [c_2_2: 2-Cocycle in H^*(D8; GF(2)),
             b_1_0: 1-Cocycle in H^*(D8; GF(2)),
             b_1_1: 1-Cocycle in H^*(D8; GF(2))]
            Minimal list of algebraic relations:
            [b_1_0*b_1_1]

        """
        import os
        from pGroupCohomology.resolution import coho_options
        if not coho_options.get('use_web'):
            return None
        if self._create_local_sources:
            root = COHO.local_sources
        else:
            root = COHO.workspace
        if websource is None:
            websource = COHO.remote_sources
            if not websource:
                return None
        else:
            if not websource:
                return None
            if not websource.endswith('/'):
                websource = websource + '/'
            websource = (websource,)

        coho_logger.info("Accessing web", None)
        # First step: Download the tar file from the web and unpack it to root
        coho_logger.info("Press Ctrl-c to interrupt web access.", None)
        OUT = None
        for URL in websource:
            if not URL.endswith('/'):
                URL = URL + '/'
            if prime is None:
                coho_logger.debug( "Accessing "+URL, None)
                f = urlopen(URL + GStem + '.tar.gz')
                coho_logger.info( "Downloading and extracting archive file", None)
                T = tarfile.open(fileobj=f, mode='r|*')
                T.extractall(path=root)
            else:
                if not (hasattr(prime,'is_prime') and prime.is_prime()):
                    raise ValueError('``prime`` must be a prime number')
                coho_logger.debug( "Accessing "+URL + 'H'+GStem + 'mod%d.sobj'%prime, None)
                f = urlopen(URL + 'H'+GStem + 'mod%d.sobj'%prime)
                coho_options['@use_this_root@'] = root
                try:
                    coho_logger.info( "Downloading and reading cohomology ring", None)
                    OUT = loads(f.read())
                except:
                    OUT = None
                if isinstance(OUT,COHO):
                    GStemList = GStem.split('gp')
                    if len(GStemList)==2:
                        if GStemList[0].isdigit() and GStemList[1].isdigit():
                            q = int(GStemList[0])
                            n = int(GStemList[1])
                            if (q,n) in OUT.GroupNames:
                                if OUT.GroupName!=OUT.GroupNames[q,n][0] or OUT.GroupDescr!=OUT.GroupNames[q,n][1]:
                                    OUT.setprop('GroupName',OUT.GroupNames[q,n][0])
                                    OUT.setprop('GroupDescr',OUT.GroupNames[q,n][1])
                    if coho_options.get('save', True):
                        safe_save(OUT,os.path.join(root,'H'+GStem + 'mod%d.sobj'%prime))
                    _gap_reset_random_seed()
                    return OUT
                else:
                    coho_logger.debug("Cohomology ring H*({}, GF({})) not found in {}".format(GStem, prime, URL), None)
                    continue
                    # raise RuntimeError("No cohomology ring found in "+URL + 'H'+GStem + 'mod%d.sobj'%prime)

            ## Second step: load the cohomology ring and return it
            ## It is now the prime power case.
            coho_logger.info("Trying to read downloaded data", None)
            coho_options['@use_this_root@'] = root
            try:
                OUT = load(os.path.join(root, GStem, 'H'+GStem))  # realpath here?
                r = OUT.root # this line may have the side-effect to change the unpacked data
                             # to make them match the name of the current workspace
            except:
                OUT = None
            if isinstance(OUT,COHO):
                GStemList = GStem.split('gp')
                if len(GStemList)==2:
                    if GStemList[0].isdigit() and GStemList[1].isdigit():
                        q = int(GStemList[0])
                        n = int(GStemList[1])
                        if (q,n) in OUT.GroupNames:
                            if OUT.GroupName!=OUT.GroupNames[q,n][0] or OUT.GroupDescr!=OUT.GroupNames[q,n][1]:
                                OUT.setprop('GroupName',OUT.GroupNames[q,n][0])
                                OUT.setprop('GroupDescr',OUT.GroupNames[q,n][1])
                                if coho_options.get('save', True):
                                    safe_save(OUT, OUT.autosave_name())
            else:
                coho_logger.debug("No cohomology ring H*({}) not found in {}".format(GStem, URL), None)
                continue
        if OUT is None:
            raise RuntimeError("The requested cohomology ring could not be found in any repository")
        _gap_reset_random_seed()
        try:
            # The original data have to be on disc, since otherwise
            # we'd later assume that the cache is corrupted
            if OUT.knownDeg==0:
                safe_save(OUT, OUT.autosave_name())
        except:
            coho_logger.error("Unable to save basic ring setup", OUT, exc_info=1)
        return OUT


def _IsKeyEquivalent(k1, k2):
    """
    Test equivalence of keys of cohomology rings

    INPUT:

    ``k1``, ``k1``: Keys of cohomology rings

    OUTPUT:

    - 0, if the keys are essentially different,
    - 1 if they are equivalent,
    - 2 if they are equal (up to file location)

    NOTE:

    If the keys are equivalent, the ring presentations of the cohomology ring
    should be equal.

    EXAMPLES::

        sage: from pGroupCohomology import CohomologyRing
        sage: CohomologyRing.doctest_setup()       # reset, block web access, use temporary workspace
        sage: from pGroupCohomology.factory import _IsKeyEquivalent
        sage: G = libgap.eval('SymmetricGroup(6)')
        sage: G.IdGroup()
        [ 720, 763 ]
        sage: H1 = CohomologyRing(G,prime=2,GroupName='Sym6')
        sage: H2 = CohomologyRing(720,763,prime=2)
        sage: _IsKeyEquivalent(H1._key,H2._key)
        0

    In fact, mapping the generators of ``H1.group()`` to the generators
    of ``H2.group()`` does not result in a group isomorphism. This is tested as
    follows::

        sage: H1.group().canonicalIsomorphism(H2.group())
        fail

    So, we chose a different generating system for ``G``. In order to
    have a reproducible doc test, we choose an explicit group isomorphism::

        sage: phiG = libgap.eval('GroupHomomorphismByImages( Group([(1,2),(1,2,3,4,5,6)]), SymmetricGroup([ 1 .. 6 ]), [(1,2),(2,3,5,6,4)], [(5,6),(1,2,3,4,5)])')
        sage: Gnew = libgap.Group([ phiG.Image(g) for g in H2.group().GeneratorsOfGroup() ])
        sage: H1new = CohomologyRing(Gnew, prime=2, GroupName='Sym6New')

    Now, the group keys are in fact essentially equal, since the
    program realises that the generators of Gnew correspond to those
    of ``SmallGroup(720,763)`` and thus identifies both rings::

        sage: _IsKeyEquivalent(H1new._key, H2._key)
        2
        sage: H2 is H1new
        True

    Now, we do the opposite and chose a generating set for
    ``SmallGroup(720,763)`` equivalent to the generating set for
    ``G``. Again, we define the isomorphism explicitly::

        sage: G2 = libgap.eval('SmallGroup(720,763)')
        sage: phiG2 = libgap.eval('GroupHomomorphismByImages( SymmetricGroup([ 1 .. 6 ]), Group([(1,2),(1,2,3,4,5,6)]), [(5,6),(1,2,3,4,5)], [(1,2),(2,6,3,4,5)])')
        sage: G2new = libgap.Group([ phiG2.Image(g) for g in G.GeneratorsOfGroup() ])
        sage: H2new = CohomologyRing(G2new, prime=2, GroupName='Sym6New2')

    Now the keys of the cohomology ring are equivalent, but not equal::

        sage: _IsKeyEquivalent(H2new._key, H1._key)
        1
        sage: H2new._key
        (('Group([(1,6,3,4,5,2),(3,6)])',), 'Sym6New2', ((16, 11), '.../16gp11/dat/State'), 2)
        sage: H1._key
        (('Group([(1,2,3,4,5,6),(1,2)])',), 'Sym6', ((16, 11), '.../16gp11/dat/State'), 2)

    """
    from pGroupCohomology.auxiliaries import gap
    if len(k1)!=len(k2):
        return 0
    if k1[0]==k2[0]:
        similarity = 2
    else:
        if len(k1[0])==1:
            G1 = gap.eval(k1[0][0])
        else:
            G1 = gap.SmallGroup(k1[0][0],k1[0][1])
        if len(k2[0])==1:
            G2 = gap.eval(k2[0][0])
        else:
            G2 = gap.SmallGroup(k2[0][0],k2[0][1])
        if G1.canonicalIsomorphism(G2) == Failure:
            return 0
        else:
            similarity = 1
    if len(k1)==3:
        return min(similarity, _IsKeyEquivalent(k1[-1], k2[-1]))
    return similarity

CohomologyRing = CohomologyRingFactory()
CohomologyRing.logger = coho_logger
CohomologyRing.__doc__ = r"""
Constructor for modular cohomology rings of finite groups.

This constructor is an instance of
:class:`~pGroupCohomology.factory.CohomologyRingFactory`.  See there
and see :mod:`pGroupCohomology` for more examples.

The constructor can be called directly. Then, it is first checked
whether the completely computed cohomology ring of the given group is
part of some database, or whether it can be downloaded. If this is
not the case, a new cohomology ring is created, being part of the user's
workspace.

Using :meth:`~pGroupCohomology.factory.CohomologyRingFactory.set_workspace`, the
location of the user's workspace can be changed. By
:meth:`~pGroupCohomology.factory.CohomologyRingFactory.from_workspace`, one can
explicitly ask for taking data from the workspace. The
input formats for calling :func:`~pGroupCohomology.CohomologyRing` and
for calling :meth:`~pGroupCohomology.factory.CohomologyRingFactory.from_workspace`
or :meth:`~pGroupCohomology.factory.CohomologyRingFactory.from_local_sources` are the same.

INPUT:

**Parameters describing the group**

- A finite group `G` , either

  * given by an integer ``q`` and a positive number ``n``, determining
    an entry of the SmallGroups library, or
  * given as an object in the libgap interface
- ``GroupName`` (optional string): a name for the group. If the
  group `G` is given in the Gap interface and if it is not provided with
  a custom name (using libGap's ``SetName``) then ``GroupName`` *must* be
  provided.
- ``GroupDescr`` (optional string): a description of the group. This can be
  any string, and is used when printing the cohomology ring or creating a
  web-site for it.
- If the group is not of prime power order, the optional parameter ``prime``
  must be set to a prime number.

**Parameters describing the database**

- ``websource``: If it is ``False``, it is not attempted to download data
  from a web repository. If it is a URL (string) or tuple of URLs
  providing the location(s) of a database in the web, then it is attempted
  to download the data from there. If ``websource`` is not given then first
  it is tried to look up data in the local file system, and if this fails
  then it is attempted to download the data from some default location in the
  web.
- ``from_scratch`` (default ``False``): If it is ``True``, this cohomology
  ring may be taken from the cache or from the workspace, but will
  not be copied from local or remote sources. Note that this will only
  take effect on this single ring; cohomology rings of subgroups,
  occuring during the computation, will still be loaded.

**Parameters modifying the algorithm**

- ``useElimination`` (optional, default ``None``): If ``True``, the
  elimination method is used for trying to construct the Dickson classes.
  If ``False``, the linear algebra method is used for that purpose. By
  default, the linear algebra method is chosen, unless there is a Dickson
  class in degree greater than 18 (for prime power groups) or 20 (for non
  prime power groups).
- ``DicksonExp`` (optional integer, default = 3): If the elimination
  method for finding the Dickson classes is used, it is needed to set a
  bound for the power to which the Dickson classes might be raised: If
  `G` is a `p`-group and `n` is the given ``DicksonExp``, then the
  Dickson classes of the elementary abelian sub-groups of `G` are raised
  to the power of `p^0,p^1,...,p^n` before trying to simultaneously lift
  them to `G`. We do not know any example in which the default value would
  not suffice.
- ``useFactorization`` (optional boolean, default True): Try to replace
  the Dickson classes of `G` by their minimal non-constant factors. This
  may simplify some computations, but there are rare examples in which the
  factorisation is a bigger problem than a high degree bound.
- ``auto`` (optional integer, default = 2 for abelian groups, and = 4
  otherwise): Only applies to the case of prime power groups. A quick but
  potentially memory consuming method for lifting chain maps will be
  used in degree at most ``auto``. For prime power groups up to orders
  around 500, the default value seems to be heuristically best.
- ``useSlimgb`` / ``useStd`` (optinal boolean): Use Singular's ``slimgb``
  (resp. ``std``) for computing the Groebner basis of the relation ideal.
  If not specified, Singular's ``groebner`` method is chosen, which uses
  a heuristics to find the best algorithm for the computation of the
  Groebner basis.

**Global options**

- ``options`` (optional string or list of strings): set/unset global options,
  or a dictionary that the global options are updated with.


There are various global options---they apply to *all* cohomology rings.
Each option is set by a string, and unset by prepending ``'no'`` to that string.

  **Available options**

  * ``'warn'`` [default], ``'info'``, ``'debug'``, logging level
  * ``'useMTX'`` [default], use :class:`~sage.matrix.matrix_gfpn_dense.Matrix_gfpn_dense`
    matrices for linear algebra over finite fields, which rely on
    `SharedMeatAxe <https://users.fmi.uni-jena.de/~king/SharedMeatAxe/>`_.
    Note that the resolutions will always be computed using the SharedMeatAxe. By
    consequence, if ``useMTX`` is turned off, time is wasted for
    conversions between different matrix types.
  * ``'save'`` [default], automatically save ring approximations,
    which comes in very handy when a long computation needs to be
    interrupted at some point; that's why it is the default. Note
    that many data, including a minimal projective resolution for
    prime power groups, will *always* be stored on disk.
  * ``'sparse'`` [not default], remove temporarily unneeded data on
    the resolution from memory. With that option, the computation
    of very large examples becomes more feasible.

  Further options have a numerical value:

  * ``autolift`` [default=1]: Degree up to which cochains are lifted
    using the autolift (as opposed to the Urbild Gröbner basis) method.
    Only applies to groups that are not elementary abelian.
  * ``autoliftElAb`` [default=0]: The same as ``autolift``, but for
    elementary abelian groups.
  * ``SingularCutoff`` [default=70]: This determines how commands for
    Singular are cut into pieces, in order to reduce the overhead of
    the pexpect interface.
  * ``NrCandidates`` [default=1000]: Maximal number of candidates that are
    considered when trying to find special elements (e.g., parameters)
    by enumeration.

In experiments with :func:`~pGroupCohomology.factory.unit_test_64`,
the different options had the following effect:

* With ``options="nouseMTX"``, the computation time slightly increases.
* With ``options="sparse"``, the computation time increases.
* With ``options="nosave"``, the computation time decreases.

The options can also be (un)set later, by using the method
:meth:`~pGroupCohomology.factory.CohomologyRingFactory.global_options`.

"""
