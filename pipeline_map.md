# Pipeline Notes — What I Built and Why

*My own record of the project, in the order I did it. Scripts are numbered 00
to 22 in true execution order -- the number is the run order, with no letter
suffixes and no exceptions. See `NUMBERING.md` for the map from the earlier
scheme, in which several numbers did not match the order they ran in.*

*Each entry lists what a script reads, what it writes, and what I learned from
running it Each entry lists what a script reads, what it writes, and what I learned from running it — since most of my scripts exist because of something the previous one told me.*

*Note on the audit: after completing scripts 00–19 I went back through the entire pipeline script by script, checking the reasoning and the outputs of each one against the actual files rather than against what I remembered. That audit found 54 separate corrections, replaced eight scripts, withdrew one published result, produced one new one, and left my headline number unchanged to within one millimagnitude. It was done with AI assistance; the pipeline, the measurements and the interpretation are mine. I'm recording it in full because the errors turned out to be the most useful part of what I learned.*

---

## Phase 0 — Finding out what I actually had

| # | Script | Reads | Writes | What I found |
|---|---|---|---|---|
| 00 | `00_inspect_headers.py` | Raw `.fits` images | `header_summary_full.csv` | Opened all 716 images to see what metadata they carry. **No filter label and no redshift stored anywhere in the headers.** All 716 readable, all with a usable WCS. |
| 06 | `01_audit_plate_scales.py` | FITS, `header_summary_full.csv` | `plate_scale_status.csv` | Read the pixel scale from every frame's own coordinate solution. **Three different values, not one.** |

This shaped everything after it. Since the filter wasn't recorded inside the files, I had to extract it from filenames. Since redshift wasn't there at all, I had to fetch it externally. Both became the next phase.

**⚠️ The mistake I made here, and didn't find until the audit.** My first run of script 00 used a `--limit` flag to sample a few files rather than all 716. Because the file listing is alphabetical, every file it sampled was a du Pont frame — `ASAS14ad`, `ASAS14hp`, `ASAS14hr`. They all had a plate scale of 0.230 arcsec/pixel, so I concluded the scale was uniform and hard-coded that number into three later scripts.

Running it properly over all 716 frames gives **0.230″ (585 frames), 0.430″ (119, all Swope V), and 0.159″ (12)**. Assuming 0.230 for a Swope frame makes every physical radius come out 1.87× too large.

The colours survived this, because script 11 uses du Pont only and du Pont really is 0.230″. The background measurements did not. This is the single most instructive thing I did wrong: a sampling shortcut that produced a wrong constant, which then propagated silently for months.

---

## Phase 1 — Building the catalogue and getting distances

| # | Script | Reads | Writes | What I found |
|---|---|---|---|---|
| 06 | `02_build_catalog.py` | Raw `.fits` filenames, NED | `sn_catalog.csv` | Parsed each filename (`ASAS14ad_B_comb_dup.fits` → object, filter, telescope) and queried NED for redshifts. **716 rows, 338 objects.** |
| 05 | `03_retry_failed_ned.py` | `sn_catalog.csv`, NED | `ned_retry_all.csv`, `sn_catalog_v2.csv` | Re-queried the failures with alternative name conventions. |
| 06 | `04_apply_redshift_cut.py` | `sn_catalog_v2.csv` | `sn_catalog_final.csv`, `excluded_objects_log.csv` | Separated objects with a usable redshift from those without. **Kept 266 objects; excluded 72, each with a logged reason.** |

**The problem I had to solve here:** NED only recognised about 37% of my object names at first. CSP filenames mix standard IAU designations, old two-digit-year shorthand, and internal names from other surveys (ASAS-SN, PTF, LSQ). I wrote a name-resolution step to translate between conventions, which raised the match rate to **79%** — more than doubling my usable sample.

**Why redshift was non-negotiable:** my method measures a circle of fixed *physical* size (kiloparsecs), but a telescope sees angles. Converting kpc into pixels requires distance, and redshift is how I get it. No redshift means no aperture and no measurement.

**Correction found in the audit.** My exclusion log gave a reason category of "CSP-internal designator, no IAU name" for 62 of the 72 excluded objects. That reason was assigned by string-matching the object's own name, not by anything NED actually returned — those 62 have an empty error field. Only `SN09J` was genuinely rejected by NED's name interpreter. The honest wording is that the query either returned no record, or returned a record carrying no redshift.

Nine further objects failed on a transient NED server error rather than a real absence of data, and still need re-querying.

---

## Phase 2 — Measuring image quality and the blur limit

| # | Script | Reads | Writes | What I found |
|---|---|---|---|---|
| 06 | `06_measure_psf_fwhm.py` | Raw `.fits` images | `psf_fwhm_per_star.csv`, `per_file_summary.csv` | Detected and fitted stars in every image to measure atmospheric blur. **~17,000 stars across 715 images.** |
| 07 | `07_flag_image_quality.py` | `per_file_summary.csv`, `plate_scale_status.csv` | `image_quality_flags_corrected.csv` | Flagged bad images, using thresholds scaled to **each frame's own plate scale**. |
| 10 | `08_summarise_psf.py` | `psf_fwhm_per_star.csv`, `plate_scale_status.csv` | `psf_fwhm_summary_corrected.csv` | Summarised blur per telescope and filter, with per-frame scales and a proper uncertainty. → **Paper Table 2** |
| 09 | `09_aperture_floor_per_object.py` | `psf_fwhm_summary_corrected.csv`, `sn_catalog_final.csv` | `aperture_floor_per_object_corrected.csv` | Combined blur with redshift to answer, per galaxy: what's the smallest circle I can trust here? |

**Why I measured blur per image instead of assuming one value:** Kelsey et al. worked with a uniformly processed stack and could use a single seeing value. My data comes from two telescopes with no such selection, so I had to measure it individually.

**The check that told me my pipeline was working:** my measured blur floor came out at 0.60 arcseconds for du Pont. Kelsey et al. report 0.55. Arriving at essentially their number by an independent route, on different telescopes, was my first strong evidence the method was sound.

**⚠️ Three things the audit corrected here.**

**Cosmic rays were being counted as stars.** 876 detections — 5.1% — are narrower than half the median width of their own frame. Those are cosmic rays and hot pixels, which pass a naive fit-quality check but are far too sharp to be real stars. Removing them shifts the du Pont B median FWHM by 0.032″, which is **larger than the error bar I was quoting on it**. A side effect: my `high_scatter` quality flag fell from 8 frames to 1 once they were gone, meaning that rule had in practice been a cosmic-ray detector rather than a seeing detector.

**My uncertainties were understated by a factor of 2.4–2.8.** I was treating the ~24 stars in one image as 24 independent measurements. They aren't — they share that image's atmosphere. Bootstrapping over *images* rather than stars gives the honest figure.

**My quality thresholds were in arcseconds, applied to FWHM values computed at the wrong plate scale.** So Swope was effectively being judged at a 1.07″ cut rather than the 2.0″ I intended.

**Corrected Table 2:**

| Telescope | Filter | Median FWHM | σ_min |
|---|---|---|---|
| du Pont | B | 1.096 ± 0.018″ | 0.599″ |
| du Pont | V | 1.063 ± 0.015″ | 0.595″ |
| Swope | V | 1.551 ± 0.026″ | 0.807″ |

The Swope value moved from 0.867″ to 1.551″, which restores physical sense — a 1 m telescope should not out-perform a 2.5 m under the same sky.

---

## Phase 3 — Supernova positions

| # | Script | Reads | Writes | What I found |
|---|---|---|---|---|
| 10 | `10_fetch_sn_coordinates.py` | `sn_catalog_final.csv`, NED | `sn_coordinates.csv` | Fetched precise sky positions. **All 266 resolved.** |
| 09 | `11_spotcheck_sn_coordinates.py` | `sn_coordinates.csv` + FITS | Inspection images | Overlaid positions on real images and checked by eye. |
| 12 | `12_verify_sn_positions.py` | `sn_coordinates.csv`, NED | `sn_position_verification.csv` | Checked the object type NED returns for every object, and measured each supernova's distance from its host centre. |

**Why step 12 mattered more than I expected.** Script 08 assumed the coordinates NED returns are the supernova site, not the galaxy centre. That assumption was never verified. It turns out to be correct — **all 266 objects are typed `SN`** — but it needed checking, since the entire premise of local photometry depends on it.

More usefully, step 12 measured the projected offset between each supernova and its host centre: **median 4.22 kpc, with 58% of objects within 5 kpc.** Since my fiducial aperture *is* 5 kpc, that means for more than half my sample the aperture already contains the host's inner regions. That observation became a result of its own in Phase 8.

**One object is broken.** `LSQ14bbv` puts its supernova position **outside the image** in both frames. It's the only such case in 551 frames, and it's independently corroborated by step 12 finding no catalogued galaxy within an arcminute.

**A diagnostic I wrote and had to retract.** `09e_verify_positions_in_pixels.py` flagged objects where the B and V centroids disagreed by more than 3.0 arcseconds, and objects with no detectable signal. Both used a fixed angular threshold across a sample spanning a factor of 37 in redshift, so they simply selected nearby galaxies. The centroid test also assumed B and V centroids should coincide — which presumes galaxies have no internal colour structure, the very thing this project measures.

---

## Phase 4 — The core measurement

| # | Script | Reads | Writes | What I found |
|---|---|---|---|---|
| 10 | `10_curve_of_growth.py` | FITS, aperture floor, coordinates | `curve_of_growth.csv` | Drew circles from 1–10 kpc around each supernova and measured the light inside each. **10,184 measurements.** **SUPERSEDED.** |
| 10b | `10b_curve_of_growth_annulus_test.py` | same | `curve_of_growth_ann{10-15,15-25,20-30}.csv` | Same measurement with three background rings instead of one. **SUPERSEDED.** |
| 13 | `13_curve_of_growth.py` | FITS, `aperture_floor_per_object_corrected.csv`, `sn_coordinates.csv` | same three files | **Current.** Per-file plate scales, aperture-level guards, real filenames. **541 object-images, 10,279 rows per setting.** |

**The result that redirected my whole approach.** I expected the light to plateau once my circle got big enough — that's what happens for a star, and it's the standard way to decide you've captured everything. **It never plateaued.** Three quarters of my galaxies are still getting brighter at 10 kpc.

That makes sense in hindsight: a star is a point, so a big enough circle catches all of it. A galaxy's light comes from billions of stars spread across real space with no hard edge, so there's always more outside whatever circle I draw.

This killed the obvious way to choose an aperture and forced me to find a different criterion. That became the central question of the project.

### The background problem

If galaxy light reaches past 10 kpc, then the 10–15 kpc ring I was using as "empty sky" wasn't empty either.

I tested it by measuring the same galaxies with three rings. A ring sampling genuine sky should read the same wherever you put it. Across the 532 object-images usable at all three settings:

```
10–15 kpc : 1.6254 counts/pixel
15–25 kpc : 0.4022
20–30 kpc : 0.1931
```

**An 88% drop.** Fitting an exponential disc plus a constant gives a disc scale length of 5.05 kpc and a true sky level of 0.066 counts/pixel — implying **about 95% of what I was calling "sky" was actually galaxy.**

This mattered because the subtracted amount scales with the circle's *area*, so my error grew as r² — exactly the shape of the effect I was trying to measure. It could have faked or hidden a real result.

**⚠️ And here is where I originally got the size of the problem wrong by a factor of seven.** I reported the error as **61 millimagnitudes on the colour**. It isn't. That figure is the error on the brightness *in one filter*.

B−V is a *difference*, and both filters take their background from the same ring on the same galaxy — so the error is common to both and largely cancels in the subtraction. Measuring the shift directly across the 202 objects with a colour under both settings: **the median shift in B−V is 8.4 millimagnitudes** (95% interval 4.4–13.4). **89% of the single-band bias cancels.**

The sign is a free check that this is right. Over-subtraction removes equal counts from both bands, but B is the fainter, so its fractional loss is larger and the colour reddens. The measured shift is positive, as predicted.

It's also strongly flux-dependent and shouldn't be quoted as one number: **2.5 mmag in the brightest flux quartile, 33.2 in the faintest** (ρ = −0.605 against flux).

### Two guards that didn't exist

`photutils` does not raise an error when a circle or a ring extends past the edge of the detector — it quietly returns statistics from whichever pixels remain. Meanwhile the background it subtracts uses the *full* geometric area. So a truncated aperture removes background for pixels that were never counted, and the deficit grows as r².

step 13 adds both checks:

- **`annulus_ok`** — is the background ring at least 80% on the detector? **9 object-images fail.**
- **`aperture_ok`** — is the measuring circle wholly on the detector and free of blank pixels? **162 individual measurements fail (1.6%).**

Neither had ever been checked for the aperture. The rows were used as though they were fine.

### Verification that the rewrites were clean

10b's 10–15 kpc setting was compared against script 10 row by row: **10,184 of 10,184 rows matched, maximum difference exactly zero** — from independently written code, since script 10 uses astropy's `ApertureStats` and 10b uses a hand-rolled equivalent. That confirmed the rewrite changed the ring choice and nothing else.

### One thing worth reporting on its own

With the clean 20–30 kpc ring, **background contributes a median of 0.7% of the enclosed flux in B and 0.4% in V** at the fiducial radius. Everything before this argued about how bad the old ring was; this says how good the new one is.

---

## Phase 5 — Turning light into colour

| # | Script | Reads | Writes | What I found |
|---|---|---|---|---|
| 11 | `11_local_color_vs_radius.py` | `curve_of_growth_ann20-30.csv` | `local_color_vs_radius.csv` | Converted light into colour at every radius: B−V = −2.5·log₁₀(F_B/F_V). **SUPERSEDED.** |
| 14 | `14_local_colour_vs_radius.py` | same | `local_color_vs_radius_ann20-30.csv` + untagged copy | **Current.** **4,154 rows, 209 objects with a colour at 5 kpc, median instrumental B−V = 0.9891.** |

**The most important line in this script is the telescope filter.** I use du Pont for both bands, never mixing telescopes. If I took B from du Pont and V from Swope, any instrumental difference between them would land directly in my subtraction and look exactly like a colour. Using one telescope for both makes every instrumental term common to B and V, so it cancels.

Checking the frame list, the choice turns out to be forced rather than preferred: **du Pont has 223 B and 225 V frames; Swope has 103 V and zero B.** A same-telescope Swope colour doesn't exist.

**And that's why the plate-scale error never reached my colours.** Swope is the telescope with the wrong assumed scale. This script discards Swope entirely.

**⚠️ Five defects the audit found.**

**The aperture guard was missing** — 11 predates step 13, so those 162 compromised rows flowed straight into my colours.

**The backup would fire once and never again.** The condition was `if the output exists AND no backup exists`. The first run creates a backup; from then on that condition is permanently false and every later run overwrote my results unprotected. I was about to re-run this script when it was found.

**The output recorded no provenance.** It read a file whose name says which background ring produced it, and wrote a file whose name says nothing. Which ring produced my colours could only be established by comparing file timestamps.

**The excluded-object count was wrong.** It reported 41. The real figure is **46** — it missed 5 objects that have du Pont data in only one band (`CSP13abm`, `SN05gj`, `SN08hv` in V; `SN06br`, `SN07ol` in B). Those got swept into a count labelled "non-positive flux", which they aren't; they have no flux at all in one band.

This also corrected my own notes, where I'd written that 222 of 266 objects had both B and V. **222 is the number of du Pont B *frames*.** The object count is **220**.

**Duplicates would have been averaged silently.** `pivot_table` averages duplicate rows without saying so. It never happened — all 541 rows are unique — but that was luck, not design.

**The funnel now balances.** step 14 prints a checksum, and it reads **266 of 266**:

```
216  du Pont B and V, after guards
  4  lost to the guards
 41  Swope V only
  5  du Pont, one band
────
266
```

The four lost to the guards are named: `SN10ae`, `SN2011iy` and `SN07af` at z = 0.0037–0.0050, where a 30 kpc ring covers more sky than the detector; and `LSQ14bbv`, which fails for the unrelated reason that its position is off the image. **My own notes had predicted the ring would stop fitting at z ≈ 0.0051 from frame geometry alone, and all three geometric failures fall below that.** None of the four reaches the final catalogue.

---

## Phase 6 — Choosing the aperture (first attempt)

| # | Script | Reads | Writes | What I found |
|---|---|---|---|---|
| 12 | `12_color_scatter_vs_radius.py` | `local_color_vs_radius.csv` | `color_scatter_summary.csv` + PNG | Measured how much my galaxies disagree about colour at each radius. **SUPERSEDED.** |
| 13 | `13_color_scatter_bootstrap.py` | same | `color_scatter_bootstrap.csv` + PNG | Added uncertainties by resampling. **SUPERSEDED — and missing from disk.** |
| 14 | `14_color_scatter_paired_bootstrap.py` | same | `color_scatter_paired_bootstrap.csv` + PNG | Used the *same* resampled galaxies at every radius so galaxy-to-galaxy noise cancels. **SUPERSEDED.** |

**My reasoning:** since the plateau method was unavailable, I asked a different question — at which circle size do all my galaxies give the most *consistent* colours? Stable colours suggest a radius measuring something real; wild scatter suggests noise.

**What each one contributed.** Script 12 computed the spread but had no way to say whether the wobbles in it were real. Script 13 added error bars, but resampled each radius independently — which is wrong, since it's the same ~200 galaxies at every radius, and treating the draws as unrelated inflates the uncertainty on any comparison. Script 14 fixed that with a **paired bootstrap**: one draw of objects reused at all 19 radii, so their shared noise cancels in the subtraction. That design was right and survives into script step 21 unchanged.

**⚠️ This is where I made my most serious mistake — three errors, compounding.**

**1. I chose my comparison baseline from my own data.**

```python
REFERENCE_RADIUS = 6.5  # the point-estimate minimum from script 13
```

I picked whichever radius happened to give the lowest scatter and used it as the reference for judging all the others. The minimum of 19 noisy values is most likely the one whose random wobble pointed downward, so the reference is biased low and everything compared against it looks worse. Resampling later confirmed 6.5 kpc was the empirical minimum in only **about 10% of bootstrap replicates** — nine times in ten a different radius would have won.

**2. My significance threshold was a 68% interval.** The 16th–84th percentile is a one-standard-deviation error bar, not a significance test. It's cleared by chance roughly one time in three. Six of eighteen radii cleared it; at the standard 95% interval, none do.

**3. I made 18 comparisons with no correction.** At a threshold firing one time in three, you'd expect about six false positives from nothing at all.

**It reported six.**

Fixing all three removed the result entirely. What I had reported was: significantly elevated colour scatter across 1.5–4.5 kpc, a range straddling the 4 kpc Kelsey et al. use, presented as a preliminary tension with their aperture choice. **That result is withdrawn.**

I'm keeping all three scripts rather than deleting them. They document the errors and how they were found, and none of the three is exotic — choosing the best-looking baseline, using an error bar as a threshold, and forgetting you ran many tests are the three commonest statistical mistakes in observational astronomy.

---

## Phase 7 — Calibration and the final catalogue

| # | Script | Reads | Writes | What I found |
|---|---|---|---|---|
| 17 | `17_apply_zero_points.py` | `curve_of_growth_ann20-30.csv`, `B_ZP_dup.dat`, `V_ZP_dup.dat` | `calibrated_color_5kpc.csv`, exclusions log | Converted counts into magnitudes. **112 objects — and a discovery about which ones.** |
| 18 | `18_flag_unreliable_colours.py` | above + curve of growth + ZP files | `calibrated_color_5kpc_flagged.csv` | Flagged unreliable colours on **two** criteria instead of one. **27 excluded, 85 retained.** |
| 22 | `19_apply_galactic_extinction.py` | flagged catalogue, `sn_coordinates.csv`, SFD maps | `calibrated_color_5kpc_dered.csv` | Removed Milky Way dust reddening. **Median moved 0.687 → 0.649 mag.** |
| 20 | `20_plot_bv_distribution.py` | dereddened catalogue | `bv_distribution.png`, summary txt | Final histogram. → **Paper Figure 2** |

**Run order note:** despite the numbering, **step 18 runs before step 19**, because step 19 needs the flag column step 18 creates. The correct sequence is step 14 → step 17 → step 18 → step 19 → step 20 → step 21.

### ⚠️ The largest single finding of the whole audit

My catalogue had 115 rows. **209 objects have a colour at 5 kpc.** Where did half of them go?

Script 15 reported it as one line: *"91 objects had flux measurements but no matching zero-point."* Technically accurate. Completely uninformative.

Splitting those 209 by the year in the object name:

| epoch | no zero point | has one |
|---|---|---|
| **2004–2009 (CSP-I)** | **90** | 0 |
| **2011–2015 (CSP-II)** | 1 | **111** |

**The break falls exactly at 2010** — the gap between the two CSP campaigns. `B_ZP_dup.dat` holds 177 objects and `V_ZP_dup.dat` 180, against 266 in my imaging. **The supplied zero points cover CSP-II and do not cover CSP-I.** The single CSP-II-era exception is `ASAS14lq`.

**This is the 224 → 117 drop I had flagged in my notes as the largest in the funnel and never examined.** It is not a quality cut. It is missing calibration data, cutting by survey epoch.

The consequence is that **my catalogue is a CSP-II sample described as CSP-I/II**. The two campaigns differ in target selection and redshift reach — median z = 0.0235 for the excluded CSP-I objects against 0.0454 for CSP-II — so this reshapes my redshift distribution rather than thinning it evenly. It affects comparability with Kelsey et al. and it affects the planned Hubble-residual work.

**This is now my top question for my supervisor.** If CSP-I zero points exist, my sample roughly doubles and every number changes.

### Other things step 17 fixed

**No validity check on the zero points.** `LSQ12gef` carries `zp = inf`, `zp_err = inf`, `n_ref_stars = 0` in both bands — a calibration built from no reference stars. It was disappearing through `inf − inf = NaN` rather than by any stated rule. (My own C9 note lists it as recoverable under the corrected quality cut; it isn't, because it can't be calibrated at all.)

**Invalid rows were being written.** Of the old 115 rows, **4 had `B_minus_V = NaN`** — the script computed magnitudes with a validity mask, then wrote every row anyway. So the real count was 111, and the corrected pipeline **grew it to 112** (gaining `KISS15m`, which my C9 note had predicted would become recoverable). "115 objects" should never have been quoted as a count of measurements.

Plus the same one-shot backup bug as script 11, the missing aperture guard, no provenance column, and no duplicate guard.

### Two failure modes, not one

Script 16 flagged colours below 1000 counts, on the reasoning that bad colours come from faint objects.

**That reasoning is false.** `ASAS14mf` has an impossible colour of **B−V = −0.029** — bluer than an O star — with **53,121 counts**, one of my brighter objects. Its problem is the zero point, not the photometry. No flux threshold at any value can remove it.

So there are two independent ways a colour goes wrong, and step 18 tests for both:

**Criterion A — background fraction.** What proportion of the enclosed flux was sky rather than galaxy? A ratio, so exposure time and campaign cancel. Threshold 0.10, against sample medians of 0.008 in B and 0.006 in V. **16 objects.**

**Criterion B — the object's own quoted uncertainty.** If the calibration says its own colour is uncertain by more than 0.25 mag, it can't constrain a distribution whose 16th–84th spread is 0.50 mag. **13 objects.**

**Only 2 objects fail both** — and the two populations sit a factor of a hundred apart in brightness (median flux ~1,500 against ~150,000). That's the proof a single flux cut could never have worked.

**All three unphysical colours are removed, each by the appropriate criterion**, and the retained sample runs +0.14 to +1.26.

**A criterion I proposed, tested, and withdrew.** I first tried flagging objects whose `ZP_B − ZP_V` was more than 3 MAD from the sample median, reasoning that a zero point depends on the telescope rather than the galaxy, so the difference should be nearly constant. I tested it against the instrumental colours, which never touch a zero point: of the 8 objects it flagged, only **3** showed a genuine calibration failure. `SN2011iv` was genuinely red *before* calibration and perfectly normal after — the zero point was correcting it, not corrupting it. The underlying assumption was also wrong: the distribution is intrinsically broad, with 6.8% of objects beyond 3 MAD against 0.3% expected. **Rejected as a criterion, retained as a printed diagnostic.**

**And the thresholds are demonstrably immaterial.** Across a 5×5 grid spanning retained sample sizes from **63 to 112**, including no cut at all, the median moves between 0.671 and 0.717 mag — a range of **0.046 mag**, smaller than the median per-object uncertainty of 0.117 mag.

### Galactic extinction

Dust in our own galaxy scatters blue light more than red, so everything arrives redder than it left. Since B−V is literally a measure of redness, that foreground adds directly to my numbers.

**One subtlety worth being able to defend.** I use Schlafly & Finkbeiner (2011) coefficients, `A_B = 3.626 E(B−V)` and `A_V = 2.742 E(B−V)`, applied to the raw SFD98 map. Their difference is **0.884**, so the correction applied is 0.884 × E(B−V)_SFD rather than 1.0 ×. That's deliberate — SF11 found SFD98 overestimates reddening by about 14%, with a recalibration factor of 0.86, and applying their per-band coefficients to the unmodified map reproduces that automatically. **There is no explicit 0.86 anywhere in my code, and a careful reader will look for one.**

**The median moves 0.687 → 0.649 mag. The scatter does not decrease** (σ_MAD 0.2644 → 0.2667), and the script originally reported that as a warning. It isn't one: what matters for scatter is the object-to-object *spread* of the correction, about ±0.023 mag, which removes 0.001 mag from a 0.264 mag scatter in quadrature. Undetectable. **Galactic dust contributes almost nothing to the spread at these latitudes.**

A weak residual correlation between dust and colour persists (ρ = +0.22, p = 0.045) and disappears once the 8 objects at |b| < 20° are removed (ρ = +0.14, p = 0.22), consistent with field crowding near the Galactic plane — though 8 objects is too few to prove it.

### The figure

**⚠️ Script 17 plotted the wrong file.** It read the flagged catalogue and histogrammed the **pre-extinction** colours. The dereddened catalogue was read by nothing at all. So my paper quoted 0.649 as the headline while the figure showed a distribution centred on 0.687.

**And its bins were finer than my measurement.** `bins=15` over a 1.24 mag range gives 0.083 mag bins, against a median per-object uncertainty of 0.117 mag. Every galaxy was smeared across more than a bin's width, so every bump in that histogram was unresolvable — but a reader would see structure and believe it.

step 20 sets the bin width to whichever is larger, the statistically sensible width or the median uncertainty. It came out at **0.158 mag**, set by sample size rather than uncertainty — which tells me more galaxies would sharpen that figure, but better zero points wouldn't.

---

## Phase 8 — The corrected aperture test

| # | Script | Reads | Writes | What I found |
|---|---|---|---|---|
| 21 | `21_colour_scatter_vs_radius.py` | `local_color_vs_radius_ann20-30.csv`, flagged catalogue | `color_scatter_corrected.csv`, `.png` | **Replaces 12, 13 and 14.** **0 of 18 radii significant.** → **Paper Figure 3** |
| 22 | `22_annulus_sensitivity.py` | all three `curve_of_growth_ann*.csv` | `annulus_sensitivity_summary.csv`, `.png` | Ran the full chain once per background ring and compared. **The null held at all three.** |

**What changed from script 14:** the paired bootstrap is identical. Only three things differ — the reference radius is pre-specified at **4.0 kpc** (Kelsey's fiducial, fixed independently of my data), the interval is **95%** rather than 68%, and eighteen comparisons are corrected with **Benjamini–Hochberg**.

**The result:**

```
objects analysed              : 212
significant, uncorrected 95%  : 0 / 18
significant after BH-FDR      : 0 / 18
smallest raw p-value          : 0.077
smallest q-value              : 0.665
```

The q-value is the number to quote. My best comparison would occur 7.7% of the time by chance *on its own* — but it's the best of 18 attempts, and adjusted for that, luck produces something this good about **two-thirds of the time**.

**Why nothing is detectable.** Two independent bounds, both larger than the effect:

| | |
|---|---|
| scatter varies across the grid by | 0.0446 mag |
| uncertainty on one object's colour | 0.1049 mag |
| **ratio** | **0.43** |
| shift from changing the background ring | 0.0336 mag |

The entire variation across 19 radii is **43% of the error bar on a single galaxy**, and comparable to how much the curve moves when I change a methodological choice I had to make anyway.

**How I state it now.** Not "aperture radius doesn't matter", but: any dependence is smaller than this sample can resolve, and the question is bounded from two directions at once — statistical power and background systematics — both of which exceed the effect being sought. That tells a future reader exactly what they'd need: more objects, a smaller error budget, or both.

**Script 19 as an independent check.** It reimplements step 14's colour calculation and step 21's statistics from scratch rather than importing them, and agrees with step 14 on four separate quantities — 4,154 rows, 241 undefined colours, 209 objects at 5 kpc, and a median instrumental B−V of 0.9891. Two independently written pieces of code agreeing to four decimal places is a meaningful validation, so I've deliberately not refactored 19 to share code.

---

## Phase 9 — The result I didn't expect

| # | Script | Reads | Writes | What I found |
|---|---|---|---|---|
| 15 | `15_offset_colour_test.py` | `local_color_vs_radius_ann20-30.csv`, `sn_position_verification.csv` | per-object CSV + profile PNG | **Colour depends on how far the supernova sat from its host's centre.** |
| 16 | `16_offset_colour_permutation.py` | same | permutation results + null PNG | Tested it against a null built by shuffling the pairing. **p = 0.0012.** |

*(Numbered 09 because that's when I wrote them; they run after step 14, since they consume its colours.)*

### The question

My apertures are centred on the **supernova**, not the galaxy nucleus. That's the whole point of local photometry. But it has a consequence I hadn't considered.

A supernova 1 kpc from its galaxy's centre has the nucleus inside *every* aperture I draw. One 8 kpc out has it inside none of the small ones — until the radius passes 8 kpc, when it suddenly enters. And galaxy centres are redder.

So **"local colour" isn't equally local for every object**, and the effect should depend on each galaxy's own supernova offset. From step 12: median offset 4.22 kpc, **58% within 5 kpc**. For more than half my sample the fiducial aperture already contains the inner regions.

### Why the obvious test failed

Comparing colours *across* objects gave **ρ = −0.031**. Nothing. Because galaxies differ from one another far more than the effect does: the typical within-object colour range is 0.130 mag, the object-to-object scatter is 0.231 mag, and the effect is about 0.02.

### The design that worked

Use each galaxy as **its own control**. I have 19 radii per object, so I can ask "does *this* galaxy's colour change as *its own* aperture grows, and does that depend on *its own* supernova offset?" Galaxy-to-galaxy variance cancels completely.

I used **instrumental** colours deliberately. The zero point is one additive constant per object, so it appears identically at every radius and cancels in any within-object comparison. **This result is therefore independent of my entire calibration chain** — which matters, because it means the unresolved CSP-I question can't touch it.

### What it found

Binning the 186 objects with both a colour profile and a measured offset:

| SN offset | n | ρ(colour, radius) | what it means |
|---|---|---|---|
| **0–2 kpc** | 51 | **−0.586** | nucleus inside from the start, diluted outward |
| 2–5 kpc | 55 | −0.039 | transition |
| **5–10 kpc** | 54 | **+0.626** | flat, then reddens as the nucleus enters |
| 10–45 kpc | 26 | +0.021 | entry radius mostly past the grid |

**The two extreme bins move in opposite directions.** No background error and no calibration offset can produce that, since either would push every object the same way.

Direct step test across the 101 objects whose entry radius falls inside my grid: **+0.0220 mag**, 95% interval [+0.0135, +0.0331].

### The control

Script step 16 keeps every colour profile intact and **shuffles the offsets between objects**, 5,000 times. Every profile is real, every offset is real — only the pairing is destroyed.

```
observed        : +0.0220
null 95% range  : [−0.0076, +0.0148]
p-value         : 0.0012
```

A separate fixed-split control, cutting every object at the same radius rather than at its own offset, reproduces only **+0.0042 mag**. The permutation null mean independently gives **+0.0035**. Two methods, neither aware of the other, agreeing on the nuisance level.

**So the decomposition is:** observed +0.0220 = profile-shape baseline +0.0042 + **offset-driven signal +0.0178**.

**And the strongest evidence I have is that this decomposition is stable.** Between two versions of the pipeline — before and after the aperture guard removed 162 measurements — the baseline changed by a factor of 2.5 while the offset-driven term changed by **0.0002 mag**. If the effect came from profile shape, it would have tracked the baseline.

### Why it matters

My fiducial 5 kpc radius was originally chosen by minimising population colour scatter. But a larger aperture reduces scatter partly **because** it encloses more of the host's inner regions — that is, **by becoming less local**. Scatter minimisation and locality are competing objectives, not complementary ones, and this puts a number on the trade.

It also matters for the planned Hubble-residual work: a systematic correlating with the supernova's position within its host can, in a residual analysis, look exactly like a host-property dependence — the very thing local-colour methods exist to isolate.

**How I state it.** Not "nuclear contamination", which names a mechanism I haven't isolated. What I measured is a dependence on projected galactocentric offset.

---

## Diagnostic scripts (not in the paper)

| Script | What I used it for |
|---|---|
| `check_annulus_diagnostics.py` | Confirming 10b reproduced script 10 exactly, and locating the remaining negatives |
| `check_background_bias_millimag.py` | Recomputing the annulus bias per object |
| `check_colour_shift_vs_flux.py` | Showing the annulus systematic is flux-dependent, 2.5 → 33 mmag across quartiles |
| `check_systematic_on_final_catalogue.py` | The systematic on my published objects specifically |
| `check_lowflux_cut_effectiveness.py` | Testing whether the flux cut targets the right variable |
| `check_annulus_censoring.py` | Counting objects lost to over-subtraction, and locating the measurement floor at ~1400 counts |
| `check_catalogue_delta.py`, `check_lost_four.py`, `check_vanished_objects.py` | Naming every object the corrected pipeline gains or loses |
| `check_zp_flag_validity.py` | The test that refuted my zero-point-difference criterion |
| `check_cut_sensitivity.py` | Showing the median is insensitive to my quality thresholds |
| `check_contamination_v2.py`, `_v3.py` | Searching for foreground-star contamination |
| `check_scatter_common_sample.py`, `check_seeing_vs_scatter.py` | Two attempts to explain the small-radius scatter dip — both refuted |
| `check_aperture_overlay.py`, `check_curve_shapes.py`, `check_color_shapes.py` | Visual confirmation the apertures and curves behave sensibly |

**Why I left these out of the paper:** they're quality control. They convinced *me* the pipeline was behaving, which is a different job from advancing the argument for a reader. I've kept them in case anyone asks whether I checked something specific.

---

## My data chain

```
raw .fits images  (716 frames, 3 plate scales)
   │
   ├─[00,01]→ header_summary_full.csv, plate_scale_status.csv
   │
   ├─[02,03]→ sn_catalog_v2.csv               338 objects
   │             └─[06]→ sn_catalog_final.csv         266 objects
   │                       └─[10]→ sn_coordinates.csv
   │                                 ├─[11]  visual spot-check
   │                                 └─[12]→ sn_position_verification.csv
   │                                            (all 266 typed SN; median offset 4.22 kpc)
   │
   ├─[06]→ psf_fwhm_per_star.csv, per_file_summary.csv
   │         ├─[07]→ image_quality_flags_corrected.csv
   │         ├─[10]→ psf_fwhm_summary_corrected.csv      → PAPER TABLE 2
   │         └─[11]→ aperture_floor_per_object_corrected.csv
   │
   └─[13]→ curve_of_growth_ann{10-15,15-25,20-30}.csv    541 object-images
              │        (+ annulus_ok, aperture_ok guards)
              │
              ├─[14]→ local_color_vs_radius_ann20-30.csv     209 objects @ 5 kpc
              │          ├─[15,16]→ offset–colour result    +0.0220 mag, p=0.0012
              │          └─[21]→ color_scatter_corrected.csv → PAPER FIG 3
              │                     (0 of 18 significant, q = 0.665)
              │
              ├─[17]→ calibrated_color_5kpc.csv          112 objects, CSP-II only
              │          └─[18]→ ..._flagged.csv               85 retained
              │                     └─[22]→ ..._dered.csv      median 0.6494
              │                                └─[20]→ bv_distribution.png → PAPER FIG 2
              │
              └─[22]→ annulus_sensitivity_summary.csv
                        (null result held at all three rings)
```

---

## Summary of what happened

I started by discovering the images didn't carry the metadata I needed, which forced me into filename parsing and database lookup. Fixing a name-convention mismatch doubled my usable sample. I then measured the blur in every image and independently reproduced Kelsey's seeing floor, which was my first sign the pipeline was sound.

The core measurement revealed that galaxy light never plateaus, which killed the obvious way to choose an aperture and forced me to invent a scatter-based criterion. That criterion gave me an exciting result — until I audited the statistics and found three errors that had produced it. Correcting them replaced the finding with an honest null.

A separate check showed my background ring was 95% galaxy light, so I re-measured everything with a clean ring at 20–30 kpc. The null survived that too. It also emerged that I had been quoting the size of that background error as a colour bias when it was a single-band flux bias — an overstatement by a factor of seven, since B and V share the error and 89% of it cancels.

Then a full script-by-script audit found the thing I should have found first: **my catalogue contains no CSP-I objects at all**, because the supplied zero points don't cover that campaign. That's the largest cut in my pipeline and it had been reported as a one-line warning about missing files.

Along the way I proposed six explanations for various anomalies and had to abandon four of them after testing — including a quality criterion of my own that would have deleted a correctly-calibrated object. I also found the same class of error six separate times: **a threshold in fixed units applied to a sample spanning a wide range of scales**. Once in an image-quality cut, once in a fit-quality floor, once in a position check, once in a background guard, once in a flux cut, and once in a diagnostic written during the audit itself.

What I ended up with is a calibrated, extinction-corrected local B−V catalogue for **85 CSP-II host galaxies with a median of 0.649 mag**; a properly bounded **null result** on the aperture question; and one new finding — that **local colours measured in apertures reaching the host's inner regions are 0.022 mag redder, scaling with the supernova's galactocentric offset, at p = 0.001**.

And the thing that reassures me most: after all of it, the headline number moved from 0.65 to 0.6494. Every correction was real and worth making, and none of them changed the answer. **The audit changed what I can defend, not what I concluded.**