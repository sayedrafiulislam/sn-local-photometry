# PAPER_CORRECTIONS.md

Corrections found during the script-by-script audit of the pipeline, to be
applied when `main.tex` is rebuilt. Numbered C1–C54 in the order they were
found.

**Script names use the OLD numbering** — `10b`, `15c`, `16c` and so on. The
pipeline was renumbered 00–22 afterwards; see `RENAME_LOG.md` for the map. The
old names are kept here because they are how each correction identifies the file
it corrects, and those files still carry those names in `scripts/superseded/`.

---

## Index by status

**Applied to the rebuilt `main.tex`:** C1–C3, C12–C17, C20–C28, C31–C34,
C37, C39, C40, C42–C52

**Open — needs supervisor input:** C25 (CSP-I zero points), C26 (LSQ12gef),
C27 (uncertainty budget), C53 (supernova light — now partly resolved)

**Open — needs a decision:** C18b/C18c (flux threshold), C46 (quality thresholds)

**Withdrawn or superseded:** C5 → C22, C9 → C23, C38/C41 → C42, C45

**Methodological, for the discussion:** C19, C31, C54

---

## Section 2 — Data and sample

### C1 — Exclusion reasons were assigned by string-matching, not by NED
**Status:** FIXED

The exclusion log gave "CSP-internal designator, no IAU name" for 62 of the 72
excluded objects. That reason was assigned by matching the object's own name,
not by anything NED returned — those 62 have an empty error field. Only `SN09J`
was genuinely rejected by NED's name interpreter.

> Objects were excluded when no redshift could be retrieved from NED, either
> because the query returned no record or because the returned record carried
> no redshift value.

Nine further objects failed on a transient NED server error and still need
re-querying.

### C2 — The plate scale is not uniform
**Status:** FIXED, verified twice

Three values, read from every frame's own WCS: **0.230″ (585 frames), 0.430″
(119, all Swope V, SITe3 CCD), 0.159″ (12).** The original reconnaissance ran
with `--limit` and, because the file listing is alphabetical, sampled only du
Pont frames.

Verified independently in 10c against 07b's audited values: **541 frames, zero
disagreements above 0.02″.**

Colours are unaffected — script 11 selects du Pont only, and du Pont is 0.230″.
Background statistics were affected; see C13.

### C4 — No low-redshift cut is declared
**Status:** PARTLY RESOLVED by C21

The sample reaches z = 0.0037, where peculiar velocity contributes ~20 per cent
distance error and therefore ~20 per cent error in the physical aperture size.
Three such objects are removed incidentally by the annulus geometry (C21), but
that is a consequence rather than a stated criterion.

### C5 — WITHDRAWN, see C22
Stated that 222 of 266 objects had both B and V. **222 is a frame count.**

### C22 — Correction to C5: the object count is 220
**Status:** FIXED

| stage | objects with du Pont B and V |
|---|---|
| raw frame list | **220** |
| after annulus and aperture guards | **216** |
| with a defined colour at 5 kpc | **209** |

Frame counts: du Pont 223 B and 225 V; Swope 103 V and **zero B**. The
Swope exclusion in script 11 is therefore forced, not chosen. (`B_ZP_swo.dat`
exists and is unused.)

### C25 — The catalogue is CSP-II only  [LARGEST FINDING]
**Status:** OPEN — highest-value supervisor question

Of the 209 objects with a colour at 5 kpc, **91 have no du Pont zero point**:

| epoch | no zero point | has one |
|---|---|---|
| 2004–2009 (CSP-I) | **90** | 0 |
| 2011–2015 (CSP-II) | 1 | **111** |

The break falls exactly at 2010. `B_ZP_dup.dat` holds 177 objects and
`V_ZP_dup.dat` 180, against 266 in the imaging: the files were derived for
CSP-II. The single CSP-II-era exception is `ASAS14lq`.

This is the largest single cut in the pipeline and it is by **survey epoch**,
not data quality. CSP-I median z = 0.0235 against 0.0454 for CSP-II, so it
reshapes the redshift distribution rather than thinning it evenly.

> Photometric calibration is restricted to the 111 objects for which du Pont
> zero points are available. These are drawn entirely from CSP-II; the supplied
> files do not cover the CSP-I campaigns (2004–2009), which accounts for 90 of
> the 91 objects excluded at this stage.

**This is the 224 → 117 drop previously flagged as unexamined.**

### C43 — The CSP-I/CSP-II count difference is mostly redshift
**Status:** RECORDED

| | CSP-I | CSP-II |
|---|---|---|
| objects | 102 | 119 |
| median redshift | 0.0235 | 0.0454 |
| raw counts at 5 kpc, B | 240 422 | 22 265 |
| background per pixel, B | 0.193 | 0.110 |

Distance alone predicts (0.0454/0.0235)² = 3.7× more counts for CSP-I; observed
~11×, leaving ~3× against a factor of 2 inferred from the background levels.
Most of the difference is redshift; the remainder is exposure depth.

### C40 — No absolute count threshold is meaningful across both campaigns
**Status:** RECORDED — constrains all future cuts

Source counts and background do not scale together, so this is not a units or
exposure offset. Any cut on flux, background or signal-to-noise must be a ratio,
or applied within epoch. Bears on script 16's 1000-count threshold (C18b),
currently moot because the catalogue is CSP-II only.

### C21 — The low-redshift exclusion, named and derived
**Status:** RESOLVED

Four objects have du Pont B and V before the guards and none after:

| object | z | annulus radius | cause |
|---|---|---|---|
| SN10ae | 0.0037 | 1723 px | annulus exceeds the frame |
| SN2011iy | 0.0043 | 1469 px | annulus exceeds the frame |
| SN07af | 0.0050 | 1264 px | annulus exceeds the frame |
| LSQ14bbv | 0.0588 | 115 px | **position off the image (C11)** |

Frame geometry predicted this limit at **z ≈ 0.0051**, independently of the
data. The three geometric failures lie at z = 0.0037–0.0050, all below it.
**None reaches the final catalogue.**

The nine annulus failures balance exactly: 4 objects × 2 du Pont bands = 8, plus
SN2011iy's Swope V frame.

### C11 — LSQ14bbv: position off the image
**Status:** CONFIRMED three ways

Both frames place the supernova outside the image — the only such case in 551
frames. Corroborated by 09b finding no catalogued galaxy within one arcminute,
by 10c's 38 NaN rows (exactly this object's two frames × 19 radii), and by the
annulus guard.

### C53 — Observation epochs, and the supernova-light question
**Status:** PARTLY RESOLVED — supervisor confirmation still wanted

Observation dates extracted from all 716 frame headers (MJD in every case) and
compared against each object's discovery year.

| gap between observation and discovery year | |
|---|---|
| minimum | +0.35 yr |
| 5th percentile | +1.03 yr |
| **median** | **+1.77 yr** |
| maximum | +7.20 yr |

Frames within 0.5 yr: **5 of 715** (0.7%). Within 1.0 yr: 33 (4.6%). Of du Pont
frames belonging to catalogue objects, **2 of 230** fall within one year.

No frame precedes its supernova. A Type Ia fades several magnitudes below peak
within ~100 days and is undetectable on a 1–2.5 m stack within a year or two, so
this distribution is consistent with host reference imaging taken after the
supernova faded.

**Limitation.** Object designations give a discovery *year*, not a date, so the
gap is measured from 1 January. An object discovered in December with a frame
from the following February reads as a 1.1 yr gap when the true interval is two
months. This bounds rather than excludes residual supernova light in individual
frames.

> Observation epochs were extracted from the frame headers and compared against
> each object's discovery year. No frame precedes its supernova, the median
> interval is 1.8 yr, and only 5 of 715 frames fall within 0.5 yr — consistent
> with the combined images being host reference frames constructed after the
> supernova faded. Because object designations give only the discovery year,
> this bounds rather than excludes the possibility of residual supernova light
> in individual frames.

---

## Section 3 — Image quality and PSF

### C3 — Table 2 corrected
**Status:** FIXED

Per-frame plate scales, plus a cluster bootstrap over **images** rather than
stars for the uncertainty.

| Telescope | Filter | Median FWHM | 16th–84th | σ_min |
|---|---|---|---|---|
| du Pont | B | 1.096 ± 0.018″ | 0.81–1.41 | 0.599″ |
| du Pont | V | 1.063 ± 0.015″ | 0.82–1.40 | 0.595″ |
| Swope | V | 1.551 ± 0.026″ | 1.29–1.90 | 0.807″ |

Swope V moves from 0.867″ to 1.551″, restoring physical sense — a 1 m telescope
should not out-perform a 2.5 m under the same sky. The Kelsey σ_min ≈ 0.55″
agreement holds for du Pont (0.60″) but not Swope (0.81″).

The quoted error is a cluster bootstrap over images; a naive std/√n understates
it by **2.4–2.8×**, because ~24 stars share each image's atmosphere.

### C6 — Cosmic rays counted as stars
**Status:** FIXED

876 detections (5.1%) are narrower than half the median width of their own
frame. They bias the du Pont B median by **+0.032″, which exceeds the ±0.018″
error bar.** Fix: reject detections below 0.5× their own frame's median.

### C7 — Quality thresholds were scale-dependent
**Status:** FIXED

Thresholds in arcseconds applied to FWHM values computed at a single assumed
plate scale, so Swope was effectively judged at 1.07″ rather than the intended
2.0″. Also: du Pont B `high_scatter` falls from 8 frames to 1 once cosmic rays
are removed — the rule was in practice a cosmic-ray detector. The `FEW_STARS`
rule never fires, since the minimum star count (13) exceeds the threshold (8).

### C9 — WITHDRAWN, see C23
Stated that eight objects including `SN2011iy` might be recoverable under the
corrected cut.

### C23 — Correction to C9
**Status:** FIXED

Verified against `calibrated_color_5kpc_dered.csv`: **zero** of the four
guard-excluded objects appear in the published catalogue. `SN2011iy` does not.
`LSQ12gef` is also not recoverable — it cannot be calibrated at all (C26).

### C35 — KISS15m recovered, as predicted
**Status:** CONFIRMED

C9 predicted `KISS15m` would become recoverable under the corrected image
quality cut. It enters the calibrated catalogue for the first time via 07b's
corrected aperture-floor output. It arrives with a one-star B zero point and a
colour of −0.023 mag, and does not survive the quality cuts of C46.

---

## Section 4 — Photometry

### C12 — The aperture had no on-chip guard
**Status:** FIXED

Scripts 10 and 10b checked whether the background **annulus** landed on the
detector; neither checked the **aperture**. `photutils` returns the sum of
whichever pixels exist while `aperture.area` returns the full πr², so a
truncated aperture removes background for pixels never summed. The deficit grows
as r² — indistinguishable in form from a real radial trend.

**162 of 10 279 rows (1.6%)** were affected. The count is identical at all three
annulus settings, as it must be, which serves as a correctness check.

Pixels are **flagged, not masked**: masking replaces a visibly absent
measurement with a plausible-looking partial one.

> Apertures were required to lie wholly on the detector and to contain no
> non-finite pixels; 1.6 per cent of measurements failed one of these conditions
> and were excluded.

### C13 — The plate-scale error propagated into the background
**Status:** FIXED

For the 74 Swope frames (true scale 0.430″), radii were computed as θ/0.23,
placing each annulus 1.87× further out in physical terms than its label.

| annulus | before | after | change |
|---|---|---|---|
| 10–15 kpc | 1.351 | **1.577** | +16.7% |
| 15–25 kpc | 0.364 | **0.390** | +7.1% |
| 20–30 kpc | 0.189 | **0.193** | +2.1% |

The correction falls off monotonically with radius, as it must for an
exponential disc. Refit: scale length 5.19 → **4.94 kpc**, sky 0.0782 →
**0.0774**. A 17 per cent shift in the innermost measurement moves the fitted
scale length by 5 per cent — the physical inference is robust.

### C16 — A flux bias was reported as a colour bias  [FACTOR OF SEVEN]
**Status:** FIXED

The paper quoted **61 mmag** as the annulus effect on B−V. That figure is a
single-band **flux** bias. Both filters are measured through the same annulus on
the same galaxy, so their errors are correlated and largely cancel.

| quantity | value |
|---|---|
| single-band flux bias at 5 kpc | 7.0% = **79.3 mmag** |
| **measured bias on B−V** | **8.4 mmag**, 95% CI [4.4, 13.4] |
| removed by cancellation | **89%** |

The sign is an independent check: over-subtraction removes equal counts from
both bands, B is fainter, so its fractional loss is larger and the colour
reddens. Measured shift is positive.

> The 10–15 kpc annulus over-subtracts by 1.43 counts per pixel relative to
> 20–30 kpc, which at the 5 kpc fiducial is 7 per cent of the enclosed flux.
> Because the error is common to both filters it cancels to first order in B−V.
> Measured across the 202 objects with a colour under both settings, the median
> reddening is 8.4 mmag (95 per cent interval 4.4–13.4), so 89 per cent of the
> single-band bias cancels.

**Also corrected:** the statement that "the median instrumental B−V at 5 kpc
shifts by about −0.025 mag" is a *difference of medians*. The per-object median
shift is 8.4 mmag.

### C17 — The annulus systematic is flux-dependent
**Status:** MEASURED

| flux quartile | n | median shift |
|---|---|---|
| faintest | 51 | **33.2 mmag** |
| Q2 | 50 | 12.0 |
| Q3 | 50 | 8.6 |
| brightest | 51 | **2.5 mmag** |

Spearman ρ(|shift|, flux) = **−0.605**. The wrongly subtracted quantity is
independent of host brightness, so its effect as a *fraction* scales inversely
with flux. Aperture area contributes a weaker second term (ρ = −0.437 with area,
+0.437 with redshift).

Should not be quoted as one number. On the published catalogue: median 10.0 mmag,
**90th percentile 143.2 mmag** — one object in ten exceeds the quoted per-object
uncertainty.

### C14 — The annulus guard imposes a redshift-dependent selection
**Status:** DECLARE, no code change

| setting | frames failing | median z of failures |
|---|---|---|
| 10–15 kpc | 2 of 541 | 0.0588 |
| 20–30 kpc | 9 of 541 | **0.0050** |

A fixed physical annulus has a strongly redshift-dependent angular size, so the
guard fails on the nearest hosts. Superseded in detail by C21.

### C18b — Widening the annulus is strictly one-directional
**Status:** RESULT

| | count |
|---|---|
| object-images with B and V at 5 kpc | 221 |
| valid under ann10-15 | 202 |
| valid under ann20-30 | 209 |
| **lost to over-subtraction** | **7** |
| **present in contaminated only** | **0** |

> Widening the background annulus from 10–15 to 20–30 kpc recovers seven objects
> whose fluxes are driven non-positive by over-subtraction, and removes none.

### C18c — The measurement floor is located
**Status:** OPEN — feeds the script 16 threshold decision

The seven censored objects have a median enclosed B flux of **1417 counts**
against 72 156 for those retained — a factor of 51 fainter. That locates the
point at which the photometry ceases to be robust.

**Five of the seven are in the published catalogue.** Script 16's threshold is
1000 counts; these clear it by a few hundred and are demonstrably at the point
of failure.

> Five objects in the final catalogue cannot be measured at all under an equally
> defensible choice of background annulus.

Note: 12 of the 221 object-images have non-positive flux under *every* setting
and never enter the analysis. These are a separate category and belong in the
funnel.

### C39 — Background is under one per cent of enclosed flux
**Status:** RESULT

With the 20–30 kpc annulus, background as a fraction of enclosed flux at 5 kpc:

| filter | median | 90th percentile |
|---|---|---|
| B | **0.007** | 0.126 |
| V | **0.004** | 0.089 |

Reconciles independently with C13: `0.1931 × 3426 ÷ 74 672 = 0.9%` against 8 per
cent for the contaminated annulus. **The annulus choice now matters far less
than it did**, which is the strongest evidence the correction worked.

Two diagnostics were withdrawn during this work: one pooled B and V (the sky is
brighter in V, so V dominated the tail by construction), applied an absolute
threshold across two campaigns, and used MAD on a strongly skewed positive
quantity. A second normalised each flux drop by the *previous* point, which
approaches zero for faint objects and makes the ratio diverge.

### C38 — SUPERSEDED by C42
`SN2013hn` shows unambiguous contamination — background fourteen times its
enclosed flux, and non-monotonic raw counts. It does not enter the catalogue.

### C41 — SUPERSEDED by C42
Initial estimate of contamination scope.

### C42 — A search for source contamination found no catalogue case
**Status:** CLOSED

Raw enclosed counts were reconstructed and tested for decreases with radius,
normalised by each curve's own peak. Across 437 du Pont curves the drop has a
median of **+0.011** (increasing, as required).

**Ten curves exceed a 10 per cent drop; three reach the catalogue** —
`LSQ13dhj`, `LSQ13dqh`, `SN2012aq`. All ten are faint, peaking at 1 007 to
10 310 counts against a sample median of 22 265. The three catalogue members
peak at 1 574 to 2 189 — at or just above the ~1400 count floor (C18c).

**These are measurement-floor objects, not contaminated objects.**

`CSP13aam` was initially reported as contaminated and is **cleared**. Its profile
is monotonic once above noise; the flag came from dividing by a raw value of −27.
What it actually shows is the C24 effect in a single object — flat to 3.5 kpc,
then climbing steeply. Recommended as a figure.

> No masking of foreground stars or unrelated sources is applied, in contrast to
> Kelsey et al. (2021) and Mowla et al. (2022). Curves of growth were tested for
> non-monotonic enclosed counts: ten of 437 show a decrease exceeding 10 per
> cent of their own peak, and all ten are among the faintest in the sample.
> Three reach the final catalogue, all within a factor of two of the photometric
> floor. One object outside the catalogue, SN2013hn, shows unambiguous
> contamination. We find no evidence that source contamination affects the
> reported colours, while noting that the test is sensitive only to contaminants
> bright enough to alter the curve shape.

### C20 — Five defects in script 11
**Status:** FIXED

1. **The aperture guard was missing** — 162 rows flowed into the colours.
2. **The backup fired once and never again** — `if OUT exists AND no BACKUP
   exists` is permanently false after the first run.
3. **The output recorded no provenance** — read a tagged file, wrote an untagged
   one. Which background produced it could only be established from timestamps.
4. **The excluded-object count was understated** — reported 41, true figure 46.
   It missed five objects with du Pont data in only one band (`CSP13abm`,
   `SN05gj`, `SN08hv` in V; `SN06br`, `SN07ol` in B), which fell into a count
   labelled "non-positive flux" — they have no flux at all in that band.
5. **Duplicate frames would have been averaged silently** by `pivot_table`.
   Never occurred, but by luck rather than construction.

**Cross-validation:** 11b agrees with script 19 on four independently computed
quantities — 4154 rows, 241 undefined colours, 209 objects at 5 kpc, median
instrumental B−V 0.9891. The two implementations were written separately.

11b additionally splits the 241 undefined colours into **93 with a band absent
entirely** and **148 with non-positive flux**. Only the second is a statement
about the detection limit.

---

## Section 4 — Aperture radius and statistics

### C15 — Script 19 applied only one of the two guards
**Status:** FIXED

It predates 10c and dropped rows only on `annulus_ok`. Applying both:

| quantity | one guard | both |
|---|---|---|
| min p, ann10-15 | 0.154 | 0.108 |
| scatter spread, ann10-15 | 0.0450 | 0.0497 |
| **largest cross-setting disagreement** | 0.0330 | **0.0336** |

Spreads increase because the aperture guard removes rows preferentially at large
radii, where apertures reach the frame edge — a more honest representation.

**Action:** set `ANNULUS_SYSTEMATIC_MAG = 0.0336` in script 18.

### C31 — Scripts 12, 13 and 14 are superseded, and document three errors
**Status:** RETAIN as the record

**Script 12** — no uncertainty at all. Output read by nothing. Its docstring
quotes "~11% of points have undefined color"; the current figure is 5.8%.

**Script 13** — unpaired bootstrap. The same ~200 objects appear at every
radius, so their noise is shared and an independent-per-radius bootstrap cannot
see it, inflating the intervals. Overlapping error bars are also not a
significance test.

**Script 14** — the paired design is correct and survives into 18. Three faults:

**(a) The reference radius was selected from the data.**
```python
REFERENCE_RADIUS = 6.5  # the point-estimate minimum from script 13
```
Being chosen for being extreme, it will appear better than its neighbours
whether or not any difference exists. Resampling confirms 6.5 kpc was the
empirical minimum in only **~10 per cent** of bootstrap replicates.

**(b) A 68 per cent interval used as a significance threshold.** The 16th–84th
percentile is ~1σ and fires by chance about one time in three. Six of eighteen
radii cleared it; **none clear 95 per cent.**

**(c) No multiplicity control** across 18 simultaneous comparisons.

Together these turned a null result into an apparent discovery. **This is the
most instructive error sequence in the project and belongs in the methods.**

### C30 — Script 13 is absent from disk
**Status:** OPEN

Present in project knowledge but not in the working repository, while its
outputs remain in `results/archive/`. Results no script can regenerate are not
reproducible. Recreate it or delete the orphans.

### C29 — Script 12 is superseded and read by nothing
**Status:** DONE — renamed and moved

---

## Section 3 — Calibration

### C26 — LSQ12gef carries a zero point built from zero reference stars
**Status:** OPEN — supervisor

Both du Pont files record `zp = inf`, `zp_err = inf`, `n_ref_stars = 0`. Script
15 computed `inf − 2.5log₁₀(flux) = inf`, then `inf − inf = NaN`, and the object
vanished through NaN arithmetic rather than by any stated rule.

`n_ref_stars` ranges from 0 to 28 with a median of 8. **Is there a minimum below
which a zero point should not be trusted?**

### C27 — The quoted per-object uncertainty is a lower bound
**Status:** OPEN — needs injection–recovery

`B_minus_V_err` is the two zero-point terms in quadrature plus the 16 per cent
SFD map term. It omits photon noise, background-estimation uncertainty,
flat-field error, and the flux-dependent annulus systematic (C17). Across the
catalogue: median **0.109 mag**, maximum **0.487**.

Mowla et al. (2022) §3.1 injection–recovery would measure the total uncertainty
empirically without needing detector gain or read noise. Their ">99 per cent
flux recovery" criterion does not transfer — that applies to point sources with
a well-defined total flux, whereas here the source is extended and the aperture
defines the measurement.

**This limits the most interesting result in the paper** (C51).

### C28 — Script 15 defects
**Status:** FIXED

Aperture guard not applied; the one-shot backup bug (second instance); no
`annulus_tag` written; no duplicate guard; stale docstring numbers; and the C16
flux-versus-colour confusion repeated.

### C37 — The old catalogue contained four placeholder rows
**Status:** RESOLVED

Script 15 computed magnitudes with a validity mask but wrote **every** row.

```
old:  115 rows  =  111 measured  +  4 placeholders
new:  112 rows  =  112 measured
```

The placeholders were `LSQ12gzm`, `LSQ13dby`, `LSQ14ip`, `SN2013hn`. **The
catalogue grew from 111 to 112**, gaining `KISS15m` — it did not shrink from 115.

The clean sample of 101 is unaffected: all four fall within the 14 objects
`flag_low_flux` catches. But **"115 objects" must not be quoted as a count of
measurements**; the correct figure is 111.

### C34 — Unphysical colours arise from failed zero points, not low flux
**Status:** MEASURED

| object | B−V | ZP_B − ZP_V | deviation | flux_B |
|---|---|---|---|---|
| ASAS14mf | −0.029 | −0.711 | −4.3 MAD | **53 121** |
| KISS13l | −0.168 | −0.688 | −4.1 MAD | 836 |
| KISS15m | −0.023 | −0.525 | −2.5 MAD | 1 718 |

**`ASAS14mf` carries 53 121 counts** — thirty times the measurement floor. No
flux threshold at any value can remove it.

Supporting: ρ(colour error, n_ref_stars) = **−0.470**; 11.6 per cent of the
catalogue has an uncertainty above 0.25 mag; three objects rest on a single
reference star (`ASAS14ad`, `ASAS14my`, `KISS15m`).

### C45 — The ZP_B − ZP_V outlier test was proposed, tested and rejected
**Status:** REJECTED as a criterion; RETAINED as a diagnostic

**The proposal.** A zero point depends on the instrument, not the galaxy, so
`ZP_B − ZP_V` should be nearly constant. Objects far from the median would be
failed calibrations.

**Why it fails — the distribution is intrinsically broad:**

| beyond | observed | Gaussian |
|---|---|---|
| 2 MAD | 13.1% | 4.6% |
| 3 MAD | **6.8%** | 0.3% |
| 5 MAD | **2.8%** | 0.00006% |

**Why it fails — validation against the zero-point-free instrumental colours.**
Of 8 objects flagged: only **3** showed a genuine calibration failure; **4** had
entirely normal calibrated colours; and `SN2011iv` has an instrumental colour of
1.858 (+3.1σ) with a calibrated colour of 0.916 — **the zero point is correcting
that object, not corrupting it.**

**Why it fails — weak corroboration.** Flagged objects have median `zp_err_B` of
0.0975 against 0.0683, and 6 reference stars against 8.

Twelve objects lie beyond 3 MAD: `ASAS14jg`, `ASAS14mf`, `CSP13N`, `CSP14aaw`,
`CSP14abf`, `CSP14acy`, `KISS13l`, `LSQ11pn`, `SN2011iv`, `SN2011jh`, `SN2012G`,
`SN2012fr`. Reported as a diagnostic and raised with the supervisor.

### C44 — Script 16's central empirical claim is false
**Status:** SUPERSEDED by 16c

It states the most implausible colours "all come from objects with low absolute
flux". The two failure modes are disjoint and sit at opposite ends of the
brightness distribution:

| criterion | n | median flux_B |
|---|---|---|
| high background | 13 | ~1 540 |
| calibration-limited | 8 | ~150 000 (one at 1.2 × 10⁷) |
| **both** | **0** | |

**A single flux cut could not have worked.**

### C46 — The two criteria adopted
**Status:** OPEN — thresholds need supervisor agreement

**A. Background fraction** at the fiducial radius, `(bkg × area) / raw`. A ratio,
so exposure time, units and campaign cancel. Sample medians 0.008 (B) and 0.006
(V). Threshold **0.10**. Tested on `|bkg_frac|` — a large negative fraction is as
wrong as a positive one. **16 objects.**

**B. The object's own quoted uncertainty.** Threshold **0.25 mag**, half the
retained 16th–84th spread. Preferred to the ZP test because it is not circular
(it never inspects the colour value), self-declared, and conservative (a lower
bound). **13 objects.**

**Only 2 objects fail both. 27 excluded, 85 retained. No unphysical colour
survives** (retained range +0.14 to +1.26).

**The thresholds are demonstrably immaterial.** Across a 5×5 grid spanning
retained sample sizes from **63 to 112**, including no cut at all, the median
moves between 0.671 and 0.717 mag — a range of **0.046 mag**, smaller than the
median per-object uncertainty of 0.117.

**One known miss:** `LSQ11pn` survives both criteria and is the maximum of the
retained sample at B−V = 1.391, with independent evidence its calibration is
suspect. Should be named in the text.

### C47 — Downstream wiring
**Status:** FIXED

16c writes `flag_exclude` as the combined criterion and retains `flag_low_flux`
for comparison only. Steps 19, 20 filter on `flag_exclude`.

### C36 — Note on the exclusion log
`calibrated_color_5kpc_exclusions.csv` holds 155 entries for 154 objects;
`LSQ12gef` is logged at two stages. Deduplicate before quoting as a funnel count.

### C32 — The SF11 recalibration is applied correctly
**Status:** CORRECT — recorded so the reasoning is defensible

Schlafly & Finkbeiner (2011) coefficients for R_V = 3.1, `A_B = 3.626 E(B−V)`
and `A_V = 2.742 E(B−V)`, applied to the **unmodified** SFD98 map. Their
difference is **0.884**, so the colour excess applied is 0.884 × E(B−V)_SFD.

This is deliberate. SF11 established that SFD98 overestimates E(B−V) by ~14 per
cent, with a recalibration factor of 0.86. Applying their per-band coefficients
to the raw map reproduces that automatically. **The text must say the
recalibration enters through the coefficients**, or a reader will look for a 0.86
that is not there.

Presentational: `ebv_applied` holds A_B − A_V, not E(B−V); rename to
`colour_excess_BV`. `EBV_FRAC_ERR = 0.16` is the SFD98 map uncertainty and is
uncited.

### C33 — Script 15b defects
**Status:** FIXED

The one-shot backup bug (**third instance** — when a bug appears three times
independently it is a house style); execution order contradicting the numbering;
a two-line docstring for a step that shifts the headline by 0.037 mag; an
undocumented numpy monkey-patch restoring aliases removed in numpy 1.24 for
`sfdmap`; and no `annulus_tag` propagated.

**Correct, and worth affirming:** script 18 does not need re-running after
extinction, for two independent reasons — extinction is one additive constant
per object and cancels in any within-object comparison, and script 18 operates
on instrumental colours which never receive the correction.

### C49 — The scatter does not decrease on dereddening, and that is expected
**Status:** RESOLVED

σ_MAD goes 0.2644 → 0.2667. What matters is the correction's **object-to-object
spread**, roughly ±0.023 mag, which removes 0.001 mag from a 0.264 mag scatter in
quadrature. Undetectable in 85 objects.

**Galactic extinction contributes negligibly to the observed spread at these
latitudes** — a statement about the sample, not a failure.

Note the standard deviation does fall (0.2461 → 0.2287) while the MAD rises: one
object with E(B−V) = 0.4309 receives a 0.38 mag correction, pulling in the tail
without affecting the core.

### C50 — The residual dust correlation
**Status:** REPORT with its caveat

| | ρ | p |
|---|---|---|
| before correction | +0.313 | 0.0035 |
| after correction | +0.218 | 0.045 |
| excluding \|b\| < 20° (8 objects) | +0.141 | 0.22 |

> A weak residual correlation between E(B−V) and the dereddened colour persists
> (ρ = +0.22, p = 0.045). It is not significant once the eight objects at
> |b| < 20° are excluded (ρ = +0.14, p = 0.22), consistent with field crowding
> at low Galactic latitude, though the sample is too small to establish this.

Sample spans |b| = 5.1° to 82.2°.

---

## Section 5 — Results

### C48 — The headline result is unchanged
**Status:** RESULT

After the corrected annulus, per-file plate scales, both guards, the CSP-II
restriction and two new quality criteria — sample 101 → 85 — the median is:

**0.6494 mag, 95 per cent CI [0.5904, 0.7055]**

Against 0.65 before. **A shift of one millimagnitude.**

| quantity | value |
|---|---|
| sample | 85 objects, CSP-II only |
| median, dereddened | **0.6494 mag** |
| median, observed | 0.6866 mag |
| extinction correction | −0.0372 mag |
| 16th–84th percentile | 0.4481 – 0.8980 |
| interquartile range | 0.4968 – 0.8436 |
| robust scatter σ_MAD | 0.2667 mag |
| full range | +0.140 to +1.260 |
| median per-object error | 0.1094 mag (lower bound) |

**Superseded numbers:**

| quantity | old | current |
|---|---|---|
| sample size | 101 | **85** |
| extinction shift | ~0.08 mag | **0.0372** |
| residual dust correlation | ρ ≈ +0.29 | **+0.218** |
| median B−V | 0.65 | 0.6494 |

### C51 — Most of the observed spread is intrinsic
**Status:** RESULT, with a required caveat

```
observed scatter    0.2667 mag
measurement error   0.1094 mag
ratio               2.44
implied intrinsic   sqrt(0.2667² − 0.1094²) = 0.243 mag
```

Roughly **83 per cent of the variance is real variation between host
environments.** This is the bridge to the Hubble-residual work: if local colour
varied only within the errors it could carry no information about the supernova.

**Caveat.** The quoted errors are lower bounds (C27), so 0.243 mag is an **upper
bound** on the intrinsic scatter. Report the ratio and say "at least partly
intrinsic"; do not quote 0.243 as a measurement.

### C52 — Figure resolution is limited by sample size, not measurement quality
**Status:** FIXED

Adopted bin width **0.158 mag** (Freedman–Diaconis) against a median per-object
uncertainty of 0.109. **More objects would sharpen the figure; better zero points
would not.**

Script 17 previously used `bins=15`, giving 0.083 mag bins — narrower than the
per-object uncertainty, so every object was smeared across more than one bin and
any apparent structure was unresolvable.

**No Kelsey comparison line is possible.** Kelsey et al. measure rest-frame U−R,
not B−V. Drawing their value on a B−V axis would compare two different
quantities sharing units. The comparison is methodological and belongs in prose.

### C8 — Script 17 plotted the pre-extinction catalogue
**Status:** FIXED

It read `calibrated_color_5kpc_flagged.csv` and histogrammed `B_minus_V`. The
dereddened output was read by nothing, while the paper quoted the dereddened
median. The two differ by 0.037 mag.

### C24 — The offset–colour result, confirmed after the aperture guard
**Status:** CONFIRMED — supersedes all earlier C10 numbers

C10 was computed from a colour file built before 10c existed, and the 162
compromised rows concentrate at **large radii** — where the signal lives.

| quantity | pre-guard | post-guard |
|---|---|---|
| objects with profile and offset | 179 | **186** |
| qualifying for the step test | 98 | **101** |
| median colour step | +0.0197 mag | **+0.0220 mag** |
| bootstrap 95% CI | [+0.0098, +0.0337] | **[+0.0135, +0.0331]** |
| permutation p, step | 0.0018 | **0.0012** (z = +3.16) |
| offset/slope correlation | +0.278 | **+0.2892** (z = +4.04) |
| fixed-split control | +0.0017 mag | **+0.0042 mag** |

**The interval narrowed while the sample grew.**

**The decomposition is invariant:**
```
pre-guard :  observed +0.0197  −  baseline +0.0017  =  +0.0180
post-guard:  observed +0.0220  −  baseline +0.0042  =  +0.0178
```
The nuisance term changed by a factor of 2.5; the offset-driven term by
**0.0002 mag**. An effect arising from profile shape would have tracked the
baseline. Two independent controls agree on the baseline: fixed-split +0.0042,
permutation null mean +0.0035.

**By offset bin:**

| SN offset | n | ρ(colour, radius) | interpretation |
|---|---|---|---|
| 0–2 kpc | 51 | **−0.586** | inner light enclosed throughout, diluted outward |
| 2–5 kpc | 55 | −0.039 | transition |
| 5–10 kpc | 54 | **+0.626** | flat, then reddens as the inner galaxy enters |
| 10–45 kpc | 26 | +0.021 | entry radius mostly beyond the grid |

The 0–2 and 5–10 kpc bins move in **opposite directions**. No additive background
error or calibration offset can produce that.

**The cross-object test remains null** (median ρ = +0.076, 47 per cent reddening
inward). The effect appears only in the within-object design, where each galaxy
is its own control. Instrumental colours are used deliberately: the zero point
cancels identically, so **the result is independent of the entire calibration
chain.**

> Local colours measured in apertures that reach the host's inner regions are
> systematically redder by 0.022 mag (95 per cent interval 0.014–0.033 mag). The
> effect scales with the supernova's projected galactocentric distance and is
> significant at p = 0.001 against a permutation null that breaks the pairing
> between colour profiles and offsets. A fixed-radius control split reproduces
> only 0.004 mag of the step.

**Do not describe it as nuclear contamination** — that names a mechanism which
has not been isolated. What was measured is a dependence on projected offset.

**Consequence for aperture choice.** A larger aperture reduces scatter partly
*because* it encloses more of the host's inner regions — by becoming less local.
Scatter minimisation and locality are competing objectives, and this quantifies
the trade. It also bears on the Hubble-residual extension: a systematic
correlating with host galactocentric position can masquerade as the host-mass
step.

**Figures.** Use `nuclear_contamination_ann20-30_profiles.png` and
`nuclear_permutation_ann20-30_null.png`. The untagged versions are labelled with
the old +0.0197 value.

**Sample accounting.** 250 offsets measured, 239 retained within 0.05–45.0 kpc,
186 with both a usable profile and an offset. Typical within-object colour range
0.130 mag; object-to-object scatter 0.231 mag (MAD) — which is why the
cross-object test cannot detect a 0.022 mag effect.

---

## Discussion

### C19 — A recurring class of error, found six times
**Status:** METHODOLOGICAL — worth a paragraph in its own right

**A threshold in fixed units, applied to a sample spanning a wide range of
scales.**

| where | threshold | applied across |
|---|---|---|
| C6 | `sigma > 0.5 px` fit floor | frames of differing sharpness |
| C7 | quality cuts in arcsec | three plate scales |
| 09e (retracted) | 3.0″ centroid agreement | ×37 in redshift |
| 10b | `MIN_ANNULUS_PIXELS = 200` | never fired; the rule was dead |
| script 16 | 1000-count flux floor | ×37 in aperture area, two campaigns |
| audit diagnostic | absolute background threshold | two campaigns, both filters |

In every case the correction was to make the threshold relative to a quantity
the object itself supplies. **The sixth instance was in a diagnostic written
during this audit**, which is worth reporting: the pattern is a property of the
problem, not of any one author's carelessness.

**A second pattern: aggregate statistics conceal structure.** The group median
FWHM looked acceptable while individual frames were wrong by 1.87×; the
population B/V seeing looked matched at 0.033″ apart while 44 per cent of pairs
differed by more than 0.1″; the annulus systematic looked like 8.4 mmag while
spanning 2.5 to 33 across flux quartiles.

### C54 — Hypotheses proposed and refuted
**Status:** METHODOLOGICAL — present as a group

| hypothesis | test | outcome |
|---|---|---|
| Surface brightness predicts the annulus systematic better than total flux | Spearman against both | **Refuted.** −0.555 vs −0.605 |
| Shift statistics are heavily censored | direct count | **Refuted.** 7 objects, 3.3% |
| Source contamination is widespread | non-monotonic enclosed counts | **Refuted.** No catalogue case |
| ZP_B − ZP_V outliers identify failed calibrations | validation against instrumental colours | **Refuted.** 3 of 8 justified |
| The small-radius scatter dip is survivorship | common-sample comparison | **Refuted.** Dip persists on a fixed 173-object sample |
| The small-radius dip is a seeing artefact | `seeing_safe` split | **Refuted.** 99–100% seeing-safe at every radius |

The last two leave the shallow structure in the scatter–radius relation without
an identified mechanism — which does not matter, because it is not detectable
(smallest q = 0.665).

**One test succeeded on the way past:** the 26 objects that fail at 1 kpc have a
scatter of **0.4252 mag** at 6.5 kpc against **0.2336** for everyone else — 1.8×
noisier where they are well measured. Independent confirmation that the quality
cuts target the right population, by a route using neither flux nor zero points.

### Predictions confirmed

| prediction | source | outcome |
|---|---|---|
| The 20–30 kpc annulus stops fitting near z ≈ 0.0051 | frame geometry | Confirmed: fails at z = 0.0037, 0.0043, 0.0050 and nowhere above |
| `KISS15m` becomes recoverable | C9 | Confirmed |
| 10b reproduces script 10 exactly | design intent | Confirmed: 10 184 of 10 184 rows, maximum difference zero |
| `LSQ14bbv` fails because its position is off-image | C11 | Confirmed by three independent routes |

---

## Aperture radius: the corrected result

**0 of 18 radii significant. Smallest raw p = 0.077. Smallest q = 0.665.**

| quantity | value |
|---|---|
| objects analysed | 212 |
| reference radius | 4.0 kpc, pre-specified (Kelsey et al.) |
| scatter range | 0.2302 – 0.2748 mag |
| spread | **0.0446 mag** |
| median per-object uncertainty | **0.1049 mag** |
| **ratio** | **0.43** |
| annulus systematic | **0.0336 mag** |

**Numbers to change in the draft:** spread 0.041 → **0.0446**; per-object
uncertainty 0.115 → **0.1049**; annulus systematic 0.039 → **0.0336**.

**The relationship inverted.** Previously the systematic (0.039) roughly equalled
the spread (0.041). Now the systematic is *smaller* — 0.034 against 0.045. So
"smaller too than" becomes **"comparable to"**.

> The scatter varies across the whole radius grid by 0.045 mag, which is 43 per
> cent of the 0.105 mag per-object colour uncertainty, and is comparable to the
> 0.034 mag by which the relation shifts under a change of background annulus.
> The question is bounded from two directions at once, by statistical power and
> by background systematics, and both bounds exceed the effect being sought.