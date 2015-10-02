/*****************************************************************************
       Copyright (C) 2015 Simon A. King <simon.king@uni-jena.de>

  Distributed under the terms of the GNU General Public License (GPL),
  version 2 or later (at your choice)

    This code is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
    General Public License for more details.

  The full text of the GPL is available at:

                  http://www.gnu.org/licenses/
*****************************************************************************/

/**
 * This is the header for all C-functions of David Green that we want
 * to put into a library to be used for group cohomology computations.
 **/

#if !defined(__AUFLOESUNG_INCLUDED) /* Include only once */
#define __AUFLOESUNG_INCLUDED

#include "meataxe.h"
#include "nDiag.h"
#include "urbild_decls.h"
#include "nBuchberger_decls.h"
#include "slice_decls.h"

#define NUMPROJ_BASE 10
#define NUMPROJ_INCREMENT 5

struct resolutionRecord
{
  group_t *group;
  char *stem;
  char *moduleStem;
  long numproj, numproj_alloc;
  long *projrank; /* projrank[n] = free rank of nth projective */
  long *Imdim; /* Imdim[n] = dim of Im d_n (which is a submod of P_{n-1}) */
};
typedef struct resolutionRecord resol_t;


char *differentialFile(resol_t *resol, long n);
/* String returned must be used at once, never reused, never freed. */
/* Represents d_n : P_n -> P_{n-1} */

char *urbildGBFile(resol_t *resol, long n);
/* String returned must be used at once, never reused, never freed. */
/* Represents urbild Groebner basis for d_n : P_n -> P_{n-1} */

nRgs_t *nRgsStandardSetup(resol_t *resol, long n, PTR mat);
/* mat should be a block of length rankProj(resol, n-1) x rankProj(resol, n) */

resol_t *newResolWithGroupLoaded (char *RStem, char *GStem, long N);
void freeResolutionRecord(resol_t *resol);

int setRankProj(resol_t *resol, long n, long r);

Matrix_t *makeFirstDifferential(resol_t *resol);

nRgs_t *loadUrbildGroebnerBasis(resol_t *resol, long n);
int innerPreimages(nRgs_t *nRgs, PTR images, long noi, group_t *group,
  PTR preimages);

#endif