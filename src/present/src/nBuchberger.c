/*****************************************************************************
       Copyright (C) 2009 David J. Green <david.green@uni-jena.de>

  Distributed under the terms of the GNU General Public License (GPL),
  version 2 or later (at your choice)

    This code is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
    General Public License for more details.

  The full text of the GPL is available at:

                  http://www.gnu.org/licenses/
*****************************************************************************/
/*
*  nBuchberger.c : Buchberger Algorithm variants
*  Author: David J Green
*  First version: 15 March 2000 from buchberger.c
*
* expDim info: rv->expDim = n is the assertion that all expansions of rv
*              have been performed which have dimension n or less.
* ngs->expDim should basically be the minimum of all rv->expDim's.
* The exception is during expansion, where ngs->expDim is incremented first,
* and then all rv's are brought up to this level.
*  If no Buchberger required, set ngs->expDim to NO_BUCHBERGER_REQUIRED. By
* default, ngs->expDim takes value NOTHING_TO_EXPAND, signifying no rv's
* have yet been recorded. If expDim takes neither of these values, than
* can assume the expDim slice has been precalculated, but cannot assume
* it is currently loaded.
*   Should probably unload and destroy current sweep slice at end of Aufnahme.
*/

#include "nDiag.h"
#include "slice_decls.h"
#include "urbild_decls.h"
#include "aufnahme_decls.h"


/******************************************************************************/
static void initializeCommonBuchStatus(ngs_t *ngs)
{
  ngs->prev_pnon = ngs->pnontips;
  ngs->unfruitful = 0;
  return;
}

/******************************************************************************
Simon King (2008-12): Try to define inline
static void recordCurrentSizeOfVisibleKernel(nRgs_t *nRgs)
{
  nRgs->prev_ker_pnon = nRgs->ker->ngs->pnontips;
  return;
}

******************************************************************************/
/******************************************************************************/
inline void recordCurrentSizeOfVisibleKernel(nRgs_t *nRgs) { nRgs->prev_ker_pnon = nRgs->ker->ngs->pnontips; return; }

/******************************************************************************/
static void updateCommonBuchStatus(ngs_t *ngs, group_t *group)
{
  if (ngs->pnontips < ngs->prev_pnon)
  {
    ngs->prev_pnon = ngs->pnontips;
    ngs->unfruitful = 0;
  }
  else ngs->unfruitful++;
  return;
}

/****
 * 1 on error
 ***************************************************************************/
static int nFgsExpandThisLevel(nFgs_t *nFgs, group_t *group)
{
  ngs_t *ngs = nFgs->ngs;
  register long nor = ngs->r + ngs->s;
  register long pat, blo, a;
  register long dim = ngs->expDim;
  modW_t *node;
  path_t *ext;
  register PTR w;
  register rV_t *rv;
  register gV_t *gv;
  for (blo = 0; blo < ngs->r; blo++)
  {
    for (pat = group->dS[dim]; pat < group->dS[dim+1]; pat++)
    {
      node = ngs->proot[blo] + pat;
      if (node->status == NO_DIVISOR) continue;
      if (node->divisor->expDim > dim) continue; /* has already been expanded */
      ext = group->root + node->qi;
      for (a = 0; a < group->arrows; a++)
      {
        if (!ext->child[a] || node->child[a]) continue;
        w = nodeVector(ngs, group, node);
        if (!w) return 1;
        gv = popGeneralVector(ngs);
        if (!gv) return 1;
        multiply(w, group->action[a], gv->w, nor);
        findLeadingMonomial(gv, ngs->r, group);
        if (gv->coeff != FF_ZERO)
        {
          if (makeVectorMonic(ngs, gv)) return 1;
          if (insertNewUnreducedVector(ngs,gv)) return 1; /* gv->radical true */
        }
        else pushGeneralVector(ngs, gv);
      }
    }
  }
  for (rv = ngs->firstReduced; rv; rv = rv->next)
    if (rv->expDim == dim) rv->expDim++;
  ngs->expDim++;
  return 0;
}

/*****
 * 1 on error
 **************************************************************************/
static int nRgsExpandThisLevel(nRgs_t *nRgs, group_t *group)
{
  ngs_t *ngs = nRgs->ngs;
  long nor = ngs->r + ngs->s;
  register long pat;
  long blo;
  register long a;
  long dim = ngs->expDim;
  modW_t *node;
  path_t *ext;
  register PTR w;
  register gV_t *gv;
  register rV_t *rv;
  for (blo = 0; blo < ngs->r; blo++)
  {
    for (pat = group->dS[dim]; pat < group->dS[dim+1]; pat++)
    {
      node = ngs->proot[blo] + pat;
      if (node->status == NO_DIVISOR) continue;
      if (node->divisor->expDim > dim) continue; /* has already been expanded */
      ext = group->root + node->qi;
      for (a = 0; a < group->arrows; a++)
      {
        if (!ext->child[a] || node->child[a]) continue;
        w = nodeVector(ngs, group, node);
        if (!w) return 1;
        gv = popGeneralVector(ngs);
        if (!gv) return 1;
        multiply(w, group->action[a], gv->w, nor);
        findLeadingMonomial(gv, ngs->r, group);
        if (gv->coeff != FF_ZERO)
        {
          if (makeVectorMonic(ngs, gv)) return 1;
          if (insertNewUnreducedVector(ngs,gv)) return 1;
        }
        else
        {
          possiblyNewKernelGenerator(nRgs, gv->w, group);
          pushGeneralVector(ngs, gv);
        }
      }
    }
  }
  for (rv = ngs->firstReduced; rv; rv = rv->next)
    if (rv->expDim == dim) rv->expDim++;
  ngs->expDim++;
  return 0;
}

/******************************************************************************/
static boolean easyCorrectRank(ngs_t *ngs, group_t *group)
{
  if (ngs->targetRank == RANK_UNKNOWN) return false;
  return (ngs->targetRank + ngs->pnontips == ngs->r * group->nontips) ?
    true : false;
}

/****
 * -1 on error
 ***************************************************************************/
static int allExpansionsDone(ngs_t *ngs, group_t *group)
{
  if (ngs->expDim == NO_BUCHBERGER_REQUIRED)
  { MTX_ERROR1("invalid expDim: %E", MTX_ERR_INCOMPAT);
    return -1
  if (ngs->expDim == NOTHING_TO_EXPAND)
    return 1;
  return (ngs->expDim <= group->maxlength) ? 0 : 1;
}

/*****
 * -1 on error
 **************************************************************************/
static int hardCorrectRank(nFgs_t *nFgs, group_t *group)
{
  ngs_t *ngs = nFgs->ngs;
  if (easyCorrectRank(ngs, group)) return true;
  if (nFgs->nRgsUnfinished) return false;
  if (ngs->unreducedHeap) return false;
  return allExpansionsDone(ngs, group);
}

/****
 * -1 on error
 ***************************************************************************/
static int nFgsBuchbergerFinished(nFgs_t *nFgs, group_t *group)
{
  ngs_t *ngs = nFgs->ngs;
  int hCR = hardCorrectRank(nFgs, group);
  swith (hCR)
  { case -1: return -1;
    case 0: return 0;
    default: return (dimensionOfDeepestHeady(ngs) <= ngs->expDim) ? 1 : 0;
  }
}

/******************************************************************************/
static boolean appropriateToPerformHeadyBuchberger(nRgs_t *nRgs, group_t *group)
{
  register ngs_t *ngs = nRgs->ngs;
  register nFgs_t *ker = nRgs->ker;
  if (!easyCorrectRank(ngs, group)) return false;
  if (!ker->nRgsUnfinished || ngs->unfruitful == nRgs->overshoot) return true;
  if (ngs->unfruitful < nRgs->overshoot) return false;
  return (ker->ngs->pnontips < nRgs->prev_ker_pnon) ? true : false;
}

/****
 * 0 on error
 ***************************************************************************/
static int checkRanksCorrect(nRgs_t *nRgs)
{
  ngs_t *ngs = nRgs->ngs;
  ngs_t *ker_ngs = nRgs->ker->ngs;
  if (ngs->targetRank == RANK_UNKNOWN) return;
  if (ker_ngs->pnontips != ngs->targetRank)
  {
     MTX_ERROR("Theoretical error: rank differs from expected value.");
     return 0;
  }
  return 1;
}

/******************************************************************************/
static void assertMinimalGeneratorsFound(nFgs_t *nFgs)
{
  nFgs->finished = true;
  return;
}

/******************************************************************************/
static inline boolean shouldFetchMoreGenerators(nFgs_t *nFgs, group_t *group)
{
  ngs_t *ngs = nFgs->ngs;
  if (!nFgs->nRgsUnfinished) return false;
  if (ngs->unfruitful < nFgs->max_unfruitful) return false;
  if (easyCorrectRank(ngs, group)) return false;
  // return (headyDim(nFgs) <= ngs->expDim) ? true : false;
  return (dimensionOfDeepestHeady(nFgs->ngs) <= ngs->expDim) ? true : false;
}

/****
 * 1 on error
 ***************************************************************************/
int nFgsBuchberger(nFgs_t *nFgs, group_t *group)
{
  register ngs_t *ngs = nFgs->ngs;
  if (nFgsAufnahme (nFgs, group)) return 1;
  initializeCommonBuchStatus(ngs);
  int allExpDone;
  int BuchFinished = nFgsBuchbergerFinished(nFgs, group);
  if (BuchFinished==-1) return 1;
  if (BuchFinished) /* Can happen on reentry */
    assertMinimalGeneratorsFound(nFgs);
  else while (allExpDone=allExpansionsDone(ngs, group) == 0)
  {
    /* Can assume expDim slice precalculated; cannot assume preloaded */
    if (loadExpansionSlice(ngs, group)) return 1;
    if (nFgsExpandThisLevel(nFgs, group)) return 1; /* increments ngs->expDim */
    if (incrementSlice(ngs, group)) return 1;
    if (nFgsAufnahme (nFgs, group)) return 1;
    updateCommonBuchStatus(ngs, group);
    if (BuchFinished=nFgsBuchbergerFinished(nFgs, group))
    {
      if (BuchFinished==-1) return 1;
      assertMinimalGeneratorsFound(nFgs);
      break;
    }
    if (shouldFetchMoreGenerators(nFgs, group))
    {
      break;
    }
  }
  if (allExpDone==-1) return 1;
  if (nFgs->finished) destroyExpansionSliceFile(ngs);
  return 0;
}

/*****
 * 1 on error
 **************************************************************************/
int nRgsBuchberger(nRgs_t *nRgs, group_t *group)
{
  register ngs_t *ngs = nRgs->ngs;
  register nFgs_t *ker = nRgs->ker;
  ker->nRgsUnfinished = true;
  if (nRgsAufnahme (nRgs, group)) return 1;
  initializeCommonBuchStatus(ngs);
  int allExpDone, allExpDone2;
  while (allExpDone = allExpansionsDone(ngs, group) == 0)
  {
    recordCurrentSizeOfVisibleKernel(nRgs);
    /* Can assume expDim slice precalculated; cannot assume preloaded */
    if (loadExpansionSlice(ngs, group)) return 1;
    if (nRgsExpandThisLevel(nRgs, group)) return 1; /* increments ngs->expDim */
    if (incrementSlice(ngs, group)) return 1;
    if (nRgsAufnahme (nRgs, group)) return 1; /* Now certain no slice loaded */
    allExpDone2 = allExpansionsDone(ngs, group);
    if (allExpDone2==1) ker->nRgsUnfinished = false;
    if (allExpDone2==-1) return 1;
    updateCommonBuchStatus(ngs, group);
    if (nFgsAufnahme (ker, group)) return 1;
    if (appropriateToPerformHeadyBuchberger(nRgs, group))
    {
      if (nFgsBuchberger(ker, group)) return 1;
      if (ker->finished) break;
    }
  }
  if (allExpDone==-1) return 1;
  /* If targetRank known, then nFgsBuchberger guaranteed already finished. */
  /* So next line should only apply if unknown. NB nRgsUnfinished now false. */
  if (!ker->finished)
  { if (nFgsBuchberger(ker, group)) return 1;}
  int r = checkRanksCorrect(nRgs); /* 0 on error */
  destroyExpansionSliceFile(ngs);
  return 1-r;
}