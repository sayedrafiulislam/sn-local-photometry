# Pipeline audit — complete summary

Script-by-script audit of the SN local photometry pipeline, run order 00 to 19.
Every script examined; every correction logged in `PAPER_CORRECTIONS.md` as
C1–C54.

---

## 1. The headline: the result did not change

| quantity | before the audit | after |
|---|---|---|
| **median local B−V (dereddened)** | 0.65 mag | **0.6494 mag** |
| null result on aperture radius | 0 of 18 significant | **0 of 18, smallest q = 0.665** |
| offset-colour signal (C10/C24) | +0.0197 mag, p = 0.0018 | **+0.0220 mag, p = 0.0012** |

**The median moved by one millimagnitude.** Every correction below was real and
worth making, and none of them changed the conclusion. The audit changed what
can be defended, not what was concluded.

---

## 2. Final numbers

### Sample funnel

| stage | objects |
|---|---|
| initial CSP-I/II catalogue | 338 |
| redshift resolved via NED | 266 |
| du Pont B and V imaging | 220 |
| after annulus and aperture guards | 216 |
| colour defined at 5 kpc | 209 |
| **zero-point coverage (CSP-II only)** | **112** |
| after quality cuts | **85** |

The 209 → 112 step is a cut by **survey epoch**, not by data quality. See §4.

### Local colour

| quantity | value |
|---|---|
| sample | 85 objects, CSP-II only |
| median B−V, dereddened | **0.6494 mag**, 95% CI [0.5904, 0.7055] |
| median B−V, observed | 0.6866 mag |
| extinction correction | −0.0372 mag |
| 16th–84th percentile | 0.4481 – 0.8980 mag |
| robust scatter (σ_MAD) | 0.2667 mag |
| median per-object error | 0.1094 mag (**lower bound**) |
| scatter / error | 2.44 → intrinsic scatter ≤ 0.243 mag |

### Aperture radius (the null result)

| quantity | value |
|---|---|
| objects analysed | 212 |
| reference radius | 4.0 kpc, pre-specified (Kelsey et al. 2021) |
| significant, uncorrected 95% | 0 / 18 |
| significant after BH-FDR | 0 / 18 |
| smallest raw p | 0.077 |
| **smallest q** | **0.665** |
| scatter range | 0.2302 – 0.2748 mag |
| spread | 0.0446 mag |
| annulus systematic | 0.0336 mag |
| **spread ÷ per-object uncertainty** | **0.43** |

### Background annulus

| quantity | value |
|---|---|
| median background/pixel, 10–15 / 15–25 / 20–30 kpc | 1.6254 / 0.4022 / 0.1931 |
| fall across settings | 88 per cent |
| fitted disk scale length | 5.05 kpc |
| fitted true sky | 0.066 counts/pixel |
| galaxy light in the 10–15 kpc ring | ~95 per cent |
| **flux bias at 5 kpc (single band)** | 7.0 per cent = **79.3 mmag** |
| **colour bias on B−V** | **8.4 mmag** [4.4, 13.4] — 89% cancels |
| background as a fraction of enclosed flux, 20–30 kpc | 0.007 (B), 0.004 (V) |

### Offset-colour result (C24)

| quantity | value |
|---|---|
| objects | 186 with profile and offset; 101 qualifying |
| median colour step | **+0.0220 mag** [+0.0135, +0.0331] |
| permutation p | **0.0012** (z = +3.16) |
| offset/slope correlation | +0.2892, p = 0.0005 |
| fixed-split control | +0.0042 mag |
| **offset-driven component** | **+0.0178 mag** |

The decomposition is invariant: the nuisance term moved by a factor of 2.5
between pipeline versions while the physical term moved by 0.0002 mag.

---

## 3. What was actually wrong

Grouped by class rather than by script number.

### Background over-subtraction
The 10–15 kpc annulus sat inside the host light — ~95 per cent of what it
recorded as "background" was galaxy. Because the subtracted quantity is
`background × aperture area`, the error grows as r², which is the same
functional form as a real radial colour trend. Corrected by measuring three
annuli and adopting 20–30 kpc.

### Silent geometric failures
`photutils` returns statistics from a partially off-image aperture or annulus
without raising. Script 10b guarded the annulus but never the aperture: 162
measurements (1.6 per cent) were made with a truncated or NaN-contaminated
aperture and used regardless.

### The plate scale
Three scales exist (0.230, 0.430, 0.159 arcsec/pixel); one was assumed
throughout. Colours were unaffected because script 11 selects du Pont only, but
every background statistic was, and the guard behaviour was too.

### Statistics
Three errors in script 14, all corrected in 18: a reference radius chosen from
the data being tested (winner's curse), a 68 per cent interval used as a
significance threshold, and eighteen simultaneous comparisons with no
multiplicity control. Together they converted a null result into an apparent
discovery.

### Flux bias reported as colour bias
The paper quoted 61 mmag as the annulus effect on B−V. That figure was a
single-band **flux** bias. Because both filters share the same annulus on the
same galaxy, 89 per cent cancels in the difference. The real colour bias is
8.4 mmag — an overstatement by a factor of seven.

### Provenance
Scripts read tagged files and wrote untagged ones, so which background produced
a given result could only be recovered from file timestamps. All current
scripts write an `annulus_tag` column and 18b verifies it on input.

### Backups that stopped working
`if os.path.exists(OUT) and not os.path.exists(BACKUP)` appeared in three
scripts independently. Once the backup existed the condition was permanently
false and every later run overwrote results unprotected. All current scripts use
timestamped backups.

### Sample accounting
Counts that did not balance; a catalogue of 115 rows containing 4 placeholders;
"222 of 266 objects" that was a count of frames, not objects. 11b now checksums
its funnel at 266 of 266 and 15c writes an exclusion log.

---

## 4. The largest single finding: the catalogue is CSP-II only

Of 209 objects with a colour at 5 kpc, 91 have no du Pont zero point:

| epoch | no zero point | has one |
|---|---|---|
| 2004–2009 (CSP-I) | **90** | 0 |
| 2011–2015 (CSP-II) | 1 | **111** |

The break falls exactly at 2010. `B_ZP_dup.dat` holds 177 objects against 266
in the imaging: the supplied files were derived for CSP-II.

This is the largest cut in the pipeline and it is by survey epoch, not data
quality. CSP-I median z = 0.0235, CSP-II = 0.0454 — the cut reshapes the
redshift distribution rather than thinning it evenly, which bears on
comparability with Kelsey et al. and on the planned Hubble-residual work.

**Highest-value outstanding question for the supervisor.** If CSP-I zero points
exist, the calibrated sample roughly doubles.

---

## 5. The recurring error pattern

**A threshold in fixed units applied to a sample spanning a wide range of
scales.** Found six times:

| where | threshold | applied across |
|---|---|---|
| C6 | `sigma > 0.5 px` fit floor | frames of differing sharpness |
| C7 | quality cuts in arcsec | three plate scales |
| 09e (retracted) | 3.0″ centroid agreement | ×38 in redshift |
| 10b | `MIN_ANNULUS_PIXELS = 200` | never fired; the rule was dead |
| script 16 | 1000-count flux floor | ×38 in aperture area, two campaigns |
| audit diagnostic | absolute background threshold | two campaigns, both filters |

The correction each time is to make the threshold relative to something the
object itself supplies. **The sixth instance was in a diagnostic written during
this audit**, which is worth reporting: the pattern is a property of the problem,
not of any one author's carelessness.

A second pattern: **aggregate statistics hide structure.** The group median FWHM
looked acceptable while individual frames were wrong by 1.87×; population B/V
seeing looked matched at 0.033″ apart while 44 per cent of pairs differed by
more than 0.1″; the annulus systematic looked like 8.4 mmag while spanning 2.5
to 33 mmag across flux quartiles.

---

## 6. Hypotheses proposed and refuted

Recorded because a rejected hypothesis with its refutation attached is stronger
evidence of care than a claim that happened to hold.

| hypothesis | test | outcome |
|---|---|---|
| Surface brightness predicts the annulus systematic better than total flux | Spearman against both | **Refuted.** ρ = −0.555 vs −0.605 |
| Shift statistics are heavily censored by objects going non-positive | direct count | **Refuted.** 7 objects, 3.3 per cent |
| Source contamination is widespread | non-monotonic enclosed counts | **Refuted.** No clear case in the catalogue |
| ZP_B − ZP_V outliers identify failed calibrations | validated against instrumental colours | **Refuted.** Only 3 of 8 justified; the distribution is intrinsically broad |
| The small-radius scatter dip is survivorship | common-sample comparison | **Refuted.** Dip persists on a fixed 173-object sample |
| The small-radius dip is a seeing artefact | `seeing_safe` split | **Refuted.** 99–100 per cent seeing-safe at every radius |

The last two leave the shallow structure in the scatter–radius relation without
an identified mechanism — which does not matter, because it is not detectable
(smallest q = 0.665).

One test that **succeeded**: the objects failing at 1 kpc have a scatter of
0.4252 mag at 6.5 kpc against 0.2336 for everyone else — 1.8× noisier where they
are well measured. Independent confirmation that the quality cuts target the
right population, by a route using neither flux nor zero points.

---

## 7. Predictions confirmed

| prediction | source | outcome |
|---|---|---|
| The 20–30 kpc annulus stops fitting near z ≈ 0.0051 | frame geometry | Confirmed: fails at z = 0.0037, 0.0043, 0.0050 and nowhere above |
| `KISS15m` becomes recoverable under the corrected quality cut | C9 | Confirmed — enters the catalogue |
| 10b reproduces script 10 exactly | design intent | Confirmed: 10 184 of 10 184 rows, maximum difference zero |
| `LSQ14bbv` fails because its position is off-image | C11 | Confirmed by three independent routes |

---

## 8. Current scripts

The pipeline was renumbered after the audit so that **the number is the run
order** — no letter suffixes, no exceptions:

```
00  01  02  03  04  05  06  07  08  09  10  11
12  13  14  15  16  17  18  19  20  21  22
```

Three scripts genuinely ran out of order under the old scheme and were the
reason renumbering was necessary rather than cosmetic: `09c` and `09d` consume
step 14's output, and `15d` reads what `16c` writes. See `RENAME_LOG.md` for the
full old-to-new map and `NUMBERING.md` for the step table.

Superseded and retained as the record: 05, 06, 07, 10, 10b, 11, 12, 14, 15, 15b,
16, 16b, 17, 18. Retracted: 09e. Missing from disk and to be recreated: 13.

---

## 9. What stands between here and a rebuilt `main.tex`

**Requires the supervisor**

1. **CSP-I zero points** — do they exist? Doubles the sample if so.
2. **Sample size 101 → 85** — needs sign-off. Supported by a sensitivity grid
   showing the median varies by only 0.046 mag across thresholds spanning
   sample sizes 63 to 112.
3. **Supernova light in the stacks** — script 04's masking was never enabled and
   could not have been, since coordinates arrive at script 08.
4. **Aperture choice** — given that no radius is statistically preferred, is
   adopting Kelsey's 4.0 kpc preferable to selecting 5.0 kpc from this data?

**Decisions**

5. **Injection–recovery error budget** (Mowla et al. 2022 §3.1) — the only route
   to a complete uncertainty. Currently `B_minus_V_err` omits photon noise,
   background uncertainty, flat-field error and the flux-dependent annulus
   systematic. This limits the most interesting result in the paper: that
   ~83 per cent of the observed colour variance is intrinsic.

**Mechanical**

6. Rebuild `main.tex` from C1–C54.
7. Recreate script 13, or delete its orphaned outputs.
8. Relabel 18b's "Final catalogue median" as observed, not dereddened.
9. Soften 15d's "scatter did not decrease" message — the expected reduction is
   0.001 mag, below detectability, which is a statement about the sample rather
   than a warning.

**Not required**

- No re-run of the photometry. Source masking was searched for and is not needed
  at this sample's precision.
- No change to scripts 09c, 09d, 18b, 19 for the catalogue quality cuts: those
  analyses use instrumental colours, in which the zero point is one additive
  constant per object and cancels within objects across radii. Several objects
  excluded from the calibrated catalogue for poor zero points are among the
  best-measured in the sample.

---

## 10. Observation epochs — the supernova-light question, partly answered

Added after the audit. Dates extracted from all 716 frame headers and compared
against each object's discovery year.

| gap between observation and discovery year | |
|---|---|
| minimum | +0.35 yr |
| 5th percentile | +1.03 yr |
| **median** | **+1.77 yr** |
| maximum | +7.20 yr |

Frames within 0.5 yr: **5 of 715** (0.7%). Of du Pont frames belonging to
catalogue objects, **2 of 230** fall within one year.

No frame precedes its supernova, and the distribution is inconsistent with these
being light-curve epochs. It is consistent with host reference imaging.

**Limitation.** Object names give a year, not a date, so the gap is measured
from 1 January. This bounds rather than excludes residual supernova light in
individual frames. Supervisor confirmation is still wanted; failing that,
retrieving actual discovery dates would close it.

Logged as C53.

---

## 11. Repository state

| | |
|---|---|
| pipeline scripts | 23, numbered 00–22 in execution order |
| superseded scripts | 16, original names, in `scripts/superseded/` |
| retracted | 1 (`09e`, fixed angular threshold across ×37 in redshift) |
| diagnostics | 26 read-only checks |
| documents | 9 |
| all outputs | present and fresh |

Every cross-reference inside the scripts was rewritten to the new numbering and
verified clean. `PAPER_CORRECTIONS.md` deliberately retains the old numbering,
because its entries identify the files they correct and those files keep their
original names.