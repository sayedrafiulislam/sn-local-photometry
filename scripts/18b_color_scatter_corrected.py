"""
18b_color_scatter_corrected.py

Supersedes 18_color_scatter_corrected.py, which superseded scripts 13 and 14.
Same measurement -- robust scatter in instrumental local B-V colour as a
function of aperture radius -- with the statistics unchanged and the numbers,
input paths and flag handling brought up to date with the pipeline audit.

WHAT WAS WRONG IN SCRIPT 14, AND WHY IT MATTERED
------------------------------------------------
Unchanged from the previous version, and repeated here because it is the
methodological core of this script.

(1) SIGNIFICANCE THRESHOLD. Script 14 declared a radius "significantly worse"
    when the 16th percentile of the paired bootstrap difference exceeded zero.
    A 16-84th percentile interval is a ~68 per cent interval -- roughly one
    standard deviation. That is an error bar, not a significance threshold. Six
    of nineteen radii cleared it. At a conventional 95 per cent interval, none
    do.

(2) REFERENCE RADIUS SELECTED FROM THE DATA. Script 14 set REFERENCE_RADIUS =
    6.5 kpc because that was the point-estimate minimum from script 13 -- the
    reference was chosen by finding the smallest observed scatter, then every
    other radius was tested against it. The minimum of a set of noisy estimates
    is biased low (the winner's curse), which systematically inflates how many
    comparisons look unfavourable. Resampling confirms 6.5 kpc was the empirical
    minimum in only ~10 per cent of bootstrap replicates. This script
    pre-specifies the reference on external grounds: 4.0 kpc, the fiducial
    aperture of Kelsey et al. (2021). That converts a data-dredged comparison
    into a directed hypothesis test.

(3) NO MULTIPLE-COMPARISON CONTROL. Eighteen simultaneous comparisons with no
    correction. This script reports bootstrap p-values and applies a
    Benjamini-Hochberg false-discovery-rate correction.

ON THE P-VALUE
--------------
The p-value here is a confidence-interval inversion, not a permutation test:
the paired bootstrap distribution of the difference is centred near the observed
difference, and the p-value measures how far that distribution sits from zero
relative to its own width. It is consistent with the reported interval by
construction. A permutation test against a null in which radius carries no
information would be a stronger design, but is not straightforward here because
the radii are nested measurements of the same objects rather than exchangeable
labels.

BACKGROUND ANNULUS -- RESOLVED
------------------------------
An earlier version carried a warning that the 10-15 kpc background annulus used
by script 10 might be contaminated by host light, and that no aperture-radius
conclusion should be trusted until that was checked. It was checked, and the
warning was justified.

Running 10c_curve_of_growth_final.py at three annulus settings gives a median
background per pixel, across the 532 object-images usable at all three, of
1.6254 counts at 10-15 kpc, 0.4022 at 15-25 kpc and 0.1931 at 20-30 kpc: a fall
of 88 per cent. An exponential-plus-constant fit to those three points returns a
disk scale length of 5.05 kpc and a true sky level of 0.066 counts per pixel,
implying that roughly 95 per cent of what the innermost annulus recorded as
"background" was in fact galaxy light.

FLUX BIAS AND COLOUR BIAS ARE NOT THE SAME NUMBER
-------------------------------------------------
Because the subtracted quantity is (background per pixel) x (aperture area),
the error scales as r^2. At the 5 kpc fiducial it reaches 7.0 per cent of the
measured flux, or 79.3 millimag IN A SINGLE BAND.

That is NOT the bias on B-V. Both bands are measured through the same annulus,
on the same galaxy, at the same position, so their background errors are
correlated and largely cancel in the difference. Measured directly across the
202 objects with a defined colour under both annulus settings, the median shift
in B-V is 8.4 millimag, 95 per cent interval 4.4 to 13.4 -- that is, 89 per cent
of the single-band bias cancels. The previous version of this docstring quoted
the single-band figure and then discussed colour, which overstates the effect by
roughly a factor of seven.

The shift is also strongly flux-dependent: 2.5 millimag in the brightest flux
quartile and 33.2 in the faintest, correlating with enclosed flux at rho =
-0.605. It should not be quoted as one number.

WHY 20-30 kpc AND NOT WIDER
---------------------------
The same fit implies the 20-30 kpc annulus leaves about 6 millimag of residual
over-subtraction on the colour, negligible against the ~110 millimag per-object
uncertainty. Measured directly: the background contributes a median of 0.7 per
cent of the enclosed flux in B and 0.4 per cent in V at the fiducial radius.
A wider annulus is unnecessary, and would cost objects -- the guard already
fails on the three lowest-redshift hosts at this setting, where a 30 kpc annulus
subtends more sky than the detector covers.

19_annulus_sensitivity_driver.py confirms the null result holds at all three
settings, the largest disagreement between them being 0.0336 mag against a
typical bootstrap interval width of 0.0887 mag.

Note that 0.0336 mag is comparable to the total spread in scatter across the
radius grid itself. The aperture-radius question is bounded from two directions
at once -- statistical power and background systematics -- and both bounds
exceed the effect being sought.

INPUTS AND FLAGS
----------------
Reads the TAGGED colour file written by 11b and verifies its annulus_tag column
against ANNULUS_TAG below, so the input cannot silently be from a different
background setting.

Filters the calibrated catalogue on `flag_exclude`, the combined criterion
written by 16c (background fraction and quoted colour uncertainty). The previous
version filtered on `flag_low_flux`, which was script 16's single absolute-count
criterion and is retained by 16c for comparison only.

NOTE ON THE CATALOGUE CUTS AND THIS ANALYSIS
--------------------------------------------
`flag_exclude` is used here ONLY to derive the median per-object uncertainty for
scale. It is deliberately NOT applied to the colour profiles analysed below.

The reason: a large part of that flag is calibration quality, and this analysis
uses INSTRUMENTAL colours, in which the zero point is one additive constant per
object that cancels in every within-object comparison across radii. Objects
excluded from the calibrated catalogue for a poor zero point have perfectly good
instrumental colours -- some of them are the best-measured objects in the
sample, with fluxes above 10^6 counts. Excluding them here would discard
excellent data for a reason that does not apply.

The same argument applies to 09c and 09d.
"""

import os
import shutil
import datetime
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from astropy.stats import mad_std

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
# Must match scripts 11 and 15.
ANNULUS_TAG = "ann20-30"

APERTURE_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase4_aperture"
CALIB_DIR = r"D:\Thesis\My Work\sn-local-photometry\results\phase5_calibration"

COLOR_CSV = os.path.join(APERTURE_DIR, f"local_color_vs_radius_{ANNULUS_TAG}.csv")
CALIB_CSV = os.path.join(CALIB_DIR, "calibrated_color_5kpc_flagged.csv")
COG_CSV = os.path.join(APERTURE_DIR, f"curve_of_growth_{ANNULUS_TAG}.csv")
OUT_DIR = APERTURE_DIR

N_BOOT = 10000
RNG_SEED = 42

# Pre-specified on external grounds, NOT chosen from these data.
REFERENCE_RADIUS = 4.0          # Kelsey et al. (2021) fiducial aperture
CI_LOWER, CI_UPPER = 2.5, 97.5  # 95 per cent interval
FDR_ALPHA = 0.05
MIN_OBJECTS_PER_RADIUS = 5

# Largest disagreement in scatter between background-annulus settings, taken
# from 19_annulus_sensitivity_driver.py with BOTH guards applied. Reported below
# alongside the statistical bound, since the two are comparable in size. Update
# this if the annulus settings in 10c change and the driver is re-run.
ANNULUS_SYSTEMATIC_MAG = 0.0336


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def backup(path):
    """Rename an existing output out of the way. Nothing is ever deleted."""
    if os.path.exists(path):
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = f"{path}.bak_{stamp}"
        shutil.move(path, dest)
        print(f"  [backup] {os.path.basename(path)} -> {os.path.basename(dest)}")


def robust_scatter(values):
    """Median absolute deviation scatter, NaN-tolerant."""
    values = values[~np.isnan(values)]
    if len(values) < MIN_OBJECTS_PER_RADIUS:
        return np.nan
    return mad_std(values)


def benjamini_hochberg(pvals, alpha=FDR_ALPHA):
    """
    Benjamini-Hochberg step-up FDR control. Returns a boolean rejection mask
    and the adjusted p-values (q-values), both in the original input order.
    """
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order]
    q_ranked = np.minimum.accumulate((ranked * n / np.arange(1, n + 1))[::-1])[::-1]
    q_ranked = np.clip(q_ranked, 0, 1)
    q = np.empty(n)
    q[order] = q_ranked
    return q < alpha, q


# --------------------------------------------------------------------------
# Load and reshape
# --------------------------------------------------------------------------
if not os.path.exists(COLOR_CSV):
    legacy = os.path.join(APERTURE_DIR, "local_color_vs_radius.csv")
    if os.path.exists(legacy):
        print(f"[warn] tagged input not found:\n       {COLOR_CSV}\n"
              f"       falling back to the untagged {os.path.basename(legacy)}, "
              f"whose background\n       annulus cannot be verified from the "
              f"file itself.")
        COLOR_CSV = legacy
    else:
        raise SystemExit(f"Input not found:\n  {COLOR_CSV}\n"
                         f"Run 11b_local_color_vs_radius_corrected.py first.")

df = pd.read_csv(COLOR_CSV)

# Provenance check: the input must have been built with the annulus setting this
# script is configured for, or the colours analysed here do not correspond to
# the catalogue. Previously this could only be established from file timestamps.
if "annulus_tag" in df.columns:
    tags = sorted(set(df["annulus_tag"].dropna()))
    if tags != [ANNULUS_TAG]:
        raise SystemExit(
            f"\nAnnulus mismatch. This script is set to {ANNULUS_TAG}, but the "
            f"input\ncarries {tags}. Re-run 11b with a matching ANNULUS_TAG, or "
            f"change it here.\n")
    print(f"[ok] input provenance verified: annulus_tag = {ANNULUS_TAG}")
else:
    print("[warn] input has no annulus_tag column -- it predates 11b, so its "
          "background\n       setting cannot be verified.")

wide = df.pivot_table(index="object", columns="radius_kpc",
                      values="instrumental_B_minus_V")
radii = sorted(wide.columns.tolist())
data = wide[radii].to_numpy()          # (n_objects, n_radii)
n_objects, n_radii = data.shape

if REFERENCE_RADIUS not in radii:
    raise ValueError(f"Reference radius {REFERENCE_RADIUS} kpc is not in the grid {radii}")
ref_idx = radii.index(REFERENCE_RADIUS)

print(f"Annulus setting: {ANNULUS_TAG}")
print(f"Loaded {n_objects} objects x {n_radii} radii "
      f"({radii[0]}-{radii[-1]} kpc)")
print(f"Reference radius: {REFERENCE_RADIUS} kpc (pre-specified: Kelsey et al. 2021 fiducial)")
print(f"Bootstrap: {N_BOOT} paired resamples, {CI_LOWER}-{CI_UPPER}th percentile interval\n")

# Per-radius sample sizes. The bootstrap below is paired at the OBJECT level,
# but objects with a NaN at a given radius drop out of that radius only, so the
# pairing is imperfect where n_valid varies. Reported for transparency.
n_valid = np.array([np.sum(~np.isnan(data[:, j])) for j in range(n_radii)])


# --------------------------------------------------------------------------
# Paired bootstrap
# --------------------------------------------------------------------------
rng = np.random.default_rng(RNG_SEED)
boot = np.empty((N_BOOT, n_radii))

for i in range(N_BOOT):
    idx = rng.integers(0, n_objects, size=n_objects)  # one draw, reused at every radius
    resampled = data[idx, :]
    for j in range(n_radii):
        boot[i, j] = robust_scatter(resampled[:, j])
    if (i + 1) % 2000 == 0:
        print(f"  bootstrap {i + 1}/{N_BOOT}")

point_estimate = np.array([robust_scatter(data[:, j]) for j in range(n_radii)])
band_lo = np.nanpercentile(boot, CI_LOWER, axis=0)
band_hi = np.nanpercentile(boot, CI_UPPER, axis=0)

# Paired difference against the pre-specified reference
diff = boot - boot[:, [ref_idx]]
diff_point = point_estimate - point_estimate[ref_idx]
diff_lo = np.nanpercentile(diff, CI_LOWER, axis=0)
diff_hi = np.nanpercentile(diff, CI_UPPER, axis=0)

# Two-sided bootstrap p-value: proportion of replicates on the far side of zero,
# doubled. Floored at 1/N_BOOT since a bootstrap cannot resolve below its own
# resolution.
frac_below = np.nanmean(diff < 0, axis=0)
p_two_sided = 2.0 * np.minimum(frac_below, 1.0 - frac_below)
p_two_sided = np.clip(p_two_sided, 1.0 / N_BOOT, 1.0)
p_two_sided[ref_idx] = 1.0  # reference against itself is not a test

# FDR correction across the 18 non-reference comparisons
test_mask = np.ones(n_radii, dtype=bool)
test_mask[ref_idx] = False
reject_sub, q_sub = benjamini_hochberg(p_two_sided[test_mask], alpha=FDR_ALPHA)
significant = np.zeros(n_radii, dtype=bool)
q_values = np.ones(n_radii)
significant[test_mask] = reject_sub
q_values[test_mask] = q_sub

# Uncorrected 95% CI verdict, for direct comparison with script 14's method
sig_uncorrected = (diff_lo > 0) | (diff_hi < 0)
sig_uncorrected[ref_idx] = False


# --------------------------------------------------------------------------
# Effect size against measurement uncertainty
# --------------------------------------------------------------------------
spread = np.nanmax(point_estimate) - np.nanmin(point_estimate)

median_sigma = np.nan
n_catalogue = None
median_color = np.nan
if os.path.exists(CALIB_CSV):
    calib = pd.read_csv(CALIB_CSV)
    # flag_exclude is 16c's combined criterion (background fraction AND quoted
    # colour uncertainty). flag_low_flux is script 16's superseded absolute
    # count cut, retained by 16c for comparison only.
    if "flag_exclude" in calib.columns:
        flag_col = "flag_exclude"
    elif "flag_low_flux" in calib.columns:
        flag_col = "flag_low_flux"
        print("[warn] catalogue has no flag_exclude column -- it predates 16c. "
              "Falling back\n       to flag_low_flux, which applies only the "
              "old absolute-count criterion.")
    else:
        flag_col = None
    keep = calib[~calib[flag_col].astype(bool)] if flag_col else calib
    keep = keep[keep["B_minus_V"].notna()]
    median_sigma = float(np.nanmedian(keep["B_minus_V_err"]))
    n_catalogue = len(keep)
    median_color = float(np.nanmedian(keep["B_minus_V"]))


# --------------------------------------------------------------------------
# Curve-of-growth diagnostic
#
# This is a description of the host light profile, not a warning. Enclosed flux
# that keeps climbing out to 10 kpc means host light extends past 10 kpc, which
# is precisely why the background annulus had to be moved outward (see the
# docstring). The two facts are reported together so they stay attached.
# --------------------------------------------------------------------------
frac_still_rising = np.nan
median_bkg = np.nan
n_annulus_dropped = None
if os.path.exists(COG_CSV):
    cog = pd.read_csv(COG_CSV)
    keys = ["object", "telescope", "filter"]
    if "annulus_ok" in cog.columns:
        per_meas = cog.drop_duplicates(subset=keys)
        n_annulus_dropped = int((~per_meas["annulus_ok"]).sum())
        cog = cog[cog["annulus_ok"]]
    if "bkg_per_pixel" in cog.columns and len(cog):
        median_bkg = float(np.nanmedian(
            cog.drop_duplicates(subset=keys)["bkg_per_pixel"]))
    piv = cog.pivot_table(index=keys, columns="radius_kpc", values="flux_bkgsub")
    if 5.0 in piv.columns and 10.0 in piv.columns:
        ratio = (piv[10.0] / piv[5.0]).replace([np.inf, -np.inf], np.nan).dropna()
        if len(ratio):
            frac_still_rising = float((ratio > 1.5).mean())
else:
    print(f"[warn] curve-of-growth file not found, skipping profile diagnostic:\n"
          f"       {COG_CSV}")


# --------------------------------------------------------------------------
# Output table
# --------------------------------------------------------------------------
result = pd.DataFrame({
    "radius_kpc": radii,
    "n_valid": n_valid,
    "scatter": point_estimate,
    "scatter_ci_lo": band_lo,
    "scatter_ci_hi": band_hi,
    "diff_vs_ref": diff_point,
    "diff_ci_lo": diff_lo,
    "diff_ci_hi": diff_hi,
    "p_value": p_two_sided,
    "q_value_bh": q_values,
    "sig_uncorrected_95": sig_uncorrected,
    "sig_after_fdr": significant,
})

os.makedirs(OUT_DIR, exist_ok=True)
out_csv = os.path.join(OUT_DIR, "color_scatter_corrected.csv")
backup(out_csv)
result.to_csv(out_csv, index=False)

pd.set_option("display.width", 200)
print("\n" + result.round(4).to_string(index=False))

print("\n" + "=" * 78)
print("SUMMARY")
print("=" * 78)
print(f"Annulus setting                       : {ANNULUS_TAG}")
if n_annulus_dropped is not None:
    print(f"  object-images excluded by the guard : {n_annulus_dropped}")
if np.isfinite(median_bkg):
    print(f"  median background per pixel         : {median_bkg:.4f} counts")
print(f"Reference radius (pre-specified)      : {REFERENCE_RADIUS} kpc")
print(f"Radii significant at uncorrected 95%  : {int(sig_uncorrected.sum())} / {n_radii - 1}")
print(f"Radii significant after BH-FDR (a={FDR_ALPHA}) : {int(significant.sum())} / {n_radii - 1}")
print(f"Smallest p-value in the grid          : {np.nanmin(p_two_sided[test_mask]):.3f}")
print()
print(f"Scatter range across all radii        : {np.nanmin(point_estimate):.4f} - "
      f"{np.nanmax(point_estimate):.4f} mag  (spread {spread:.4f} mag)")
if np.isfinite(median_sigma):
    print(f"Median per-object colour uncertainty  : {median_sigma:.4f} mag "
          f"(zero-point term only; a lower bound)")
    print(f"  -> radius-to-radius spread is {spread / median_sigma:.2f}x the single-measurement "
          f"uncertainty")
print(f"Background-annulus systematic         : {ANNULUS_SYSTEMATIC_MAG:.3f} mag "
      f"(19_annulus_sensitivity_driver.py)")
print(f"  -> comparable to the {spread:.3f} mag radius spread itself; the aperture question")
print(f"     is bounded by systematics as well as by statistical power.")
if n_catalogue is not None:
    print()
    print(f"Final catalogue                       : {n_catalogue} objects, "
          f"median B-V = {median_color:.4f} mag")
print()

# Smallest radii versus the mid-radius band -- the pattern script 14's
# narrative could not account for.
small = [r for r in radii if r <= 2.0]
mid = [r for r in radii if 2.5 <= r <= 4.5]
if small and mid:
    small_vals = [point_estimate[radii.index(r)] for r in small]
    mid_min = float(np.nanmin([point_estimate[radii.index(r)] for r in mid]))
    print("Smallest apertures tested:")
    for r, v in zip(small, small_vals):
        print(f"  {r:4.1f} kpc : {v:.4f} mag")
    print(f"Lowest value anywhere in 2.5-4.5 kpc  : {mid_min:.4f} mag")
    if all(v < mid_min for v in small_vals):
        print("  -> every one of the smallest apertures is better behaved than any radius in")
        print("     the 2.5-4.5 kpc band. No monotonic seeing- or resolution-driven mechanism")
        print("     predicts that, which argues against reading the shallow structure in the")
        print("     scatter-radius relation as physical.")
    print()

if np.isfinite(frac_still_rising):
    print(f"Objects with flux(10 kpc)/flux(5 kpc) > 1.5 : {100 * frac_still_rising:.0f}%")
    print("  Host light extends well past 10 kpc for most of the sample. This is why the")
    print("  background annulus sits at 20-30 kpc rather than 10-15 kpc (see docstring):")
    print("  it is a property of the galaxies, not an outstanding problem.")
print("=" * 78)


# --------------------------------------------------------------------------
# Figure
# --------------------------------------------------------------------------
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.5, 8.0), sharex=True,
                               gridspec_kw={"height_ratios": [1.4, 1]})

ax1.fill_between(radii, band_lo, band_hi, alpha=0.25, color="#4C72B0",
                 label=f"{int(CI_UPPER - CI_LOWER)}% bootstrap interval")
ax1.plot(radii, point_estimate, marker="o", color="#1F3B73", linewidth=1.8,
         markersize=5, label="Robust scatter ($\\sigma_{\\rm MAD}$)")
ax1.axvline(REFERENCE_RADIUS, color="#C44E52", linestyle="--", linewidth=1.5,
            label=f"Reference: {REFERENCE_RADIUS:g} kpc (Kelsey et al. 2021)")
if np.isfinite(median_sigma):
    y0 = np.nanmin(band_lo)
    ax1.errorbar(radii[-1] - 0.3, y0 + 0.5 * median_sigma, yerr=0.5 * median_sigma,
                 fmt="none", ecolor="#555555", capsize=4, linewidth=1.5)
    ax1.text(radii[-1] - 0.55, y0 + 0.5 * median_sigma,
             "median single-object\nuncertainty", fontsize=8, ha="right",
             va="center", color="#555555")
ax1.set_ylabel("Scatter in instrumental $B-V$ (mag)")
ax1.set_title(f"Local colour scatter vs. aperture radius "
              f"({ANNULUS_TAG.replace('ann', '')} kpc background annulus)")
ax1.legend(fontsize=9, loc="upper right")

ax2.axhline(0, color="#C44E52", linestyle="--", linewidth=1.5)
ax2.fill_between(radii, diff_lo, diff_hi, alpha=0.25, color="#55A868")
ax2.plot(radii, diff_point, marker="o", color="#2C6B45", linewidth=1.8, markersize=5)
sig_pts = result[result["sig_after_fdr"]]
if len(sig_pts) > 0:
    ax2.scatter(sig_pts["radius_kpc"], sig_pts["diff_vs_ref"], color="red",
                zorder=5, s=60, label="Significant after FDR")
    ax2.legend(fontsize=9)
else:
    ax2.text(0.5, 0.06, "No radius differs significantly from the reference "
             "after multiple-comparison correction",
             transform=ax2.transAxes, ha="center", fontsize=9.5, style="italic",
             color="#333333")
ax2.set_xlabel("Aperture radius (kpc)")
ax2.set_ylabel(f"$\\Delta$ scatter vs. {REFERENCE_RADIUS:g} kpc (mag)")

fig.tight_layout()
out_png = os.path.join(OUT_DIR, "color_scatter_corrected.png")
backup(out_png)
fig.savefig(out_png, dpi=150)
print(f"\nSaved: {out_csv}")
print(f"Saved: {out_png}")