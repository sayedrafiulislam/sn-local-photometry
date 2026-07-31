"""
fix_docstrings.py

Repairs stale text left behind after the pipeline renumbering.

Three categories:

  1. Instructions naming scripts that no longer exist. The automatic rename
     missed these because they name SUPERSEDED scripts, which deliberately keep
     their original filenames.

  2. Bare step references such as "09c" without the ".py" extension. The rename
     matched full filenames only.

  3. Result values quoted inside docstrings that predate the aperture guard.
     Script 16 states the offset-colour result as +0.0197 mag across 98
     objects; the current values are +0.0220 across 101.

Historical statements ("Supersedes 10b_curve_of_growth_annulus_test.py") are
correct and are left alone.

Matching is line-by-line on distinctive substrings, so line endings and
surrounding whitespace do not matter.

    python fix_docstrings.py           # dry run
    python fix_docstrings.py --execute
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(r"D:\Thesis\My Work\sn-local-photometry")
SCRIPTS = REPO / "scripts"

# file : list of (substring to find, replacement for the whole line, reason)
FIXES = {
    "17_apply_zero_points.py": [
        ("Named 15c because 15b is already taken",
         "Runs at step 17. Its output feeds step 18 (quality flags), which in",
         "obsolete naming rationale"),
        ("Run 16_flag_low_flux_colors.py, then 15b_apply_galactic_extinction",
         "  Next: 18_flag_unreliable_colours.py, then 19_apply_galactic_extinction.py.",
         "instruction names superseded scripts"),
        ("in that order, despite the numbering",
         "",
         "numbering is no longer misleading"),
    ],

    "18_flag_unreliable_colours.py": [
        ("*** 15b_apply_galactic_extinction.py currently filters on flag_low_flux",
         "*** Steps 19 and 20 filter on flag_exclude. flag_low_flux is retained in",
         "warning already acted on"),
        ("*** must be changed to flag_exclude, or the new criteria will have no",
         "*** the output for comparison only and must not be filtered on.",
         "warning already acted on"),
        ("15b_apply_galactic_extinction.py currently filters on flag_low_flux and MUST",
         "Steps 19 and 20 already do this. flag_low_flux is retained in the output",
         "warning already acted on"),
        ("updated, or the calibration criterion will have no effect on the final",
         "for comparison only and must not be used as an exclusion criterion.",
         "warning already acted on"),
    ],

    "15_offset_colour_test.py": [
        ("--colors results\\\\phase4_aperture\\\\local_color_vs_radius.csv",
         "        --colors results\\\\phase4_aperture\\\\local_color_vs_radius_ann20-30.csv ^",
         "usage points at the untagged colour file"),
        ("--out-prefix results\\\\phase4_aperture\\\\nuclear_contamination",
         "        --out-prefix results\\\\phase4_aperture\\\\nuclear_contamination_ann20-30",
         "usage prefix lacks the annulus tag"),
    ],

    "16_offset_colour_permutation.py": [
        ("09c compared, for each object, the median colour",
         "Step 15 compared, for each object, the median colour at aperture radii below",
         "bare step reference"),
        ("Across 98 objects the median step was",
         "Across 101 objects the median step was",
         "pre-guard sample size"),
        ("+0.0197 mag,  95 per cent bootstrap CI [+0.0098, +0.0337]",
         "    +0.0220 mag,  95 per cent bootstrap CI [+0.0135, +0.0331]",
         "pre-guard result values"),
        ("09c's Test 2 predicted that objects with",
         "          slope of colour with radius. Step 15's Test 2 predicted that objects",
         "bare step reference"),
        ("# Kept identical to 09c so the observed statistic",
         "# Kept identical to step 15 so the observed statistic is reproduced exactly.",
         "bare step reference"),
        ("--colors results\\\\phase4_aperture\\\\local_color_vs_radius.csv",
         "        --colors results\\\\phase4_aperture\\\\local_color_vs_radius_ann20-30.csv ^",
         "usage points at the untagged colour file"),
        ("--out-prefix results\\\\phase4_aperture\\\\nuclear_permutation",
         "        --out-prefix results\\\\phase4_aperture\\\\nuclear_permutation_ann20-30",
         "usage prefix lacks the annulus tag"),
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true",
                    help="apply the changes; without this it is a dry run")
    args = ap.parse_args()

    mode = "EXECUTING" if args.execute else "DRY RUN - nothing will change"
    print()
    print("=" * 74)
    print(mode)
    print("=" * 74)

    if not SCRIPTS.is_dir():
        print(f"\nScripts folder not found: {SCRIPTS}")
        return 1

    total_applied = 0
    total_missed = 0

    for fname, rules in FIXES.items():
        path = SCRIPTS / fname
        if not path.exists():
            print(f"\nMISSING  {fname}")
            total_missed += len(rules)
            continue

        # newline='' preserves the file's own line endings on write-back
        with open(path, "r", encoding="utf-8", newline="") as fh:
            text = fh.read()

        # split keeping the terminators, so nothing is lost
        lines = text.splitlines(keepends=True)
        changed = []

        for find, replace, reason in rules:
            hit = False
            for i, line in enumerate(lines):
                if find in line:
                    # preserve this line's own terminator
                    stripped = line.rstrip("\r\n")
                    ending = line[len(stripped):]
                    if replace == "":
                        lines[i] = ""          # drop the line entirely
                    else:
                        lines[i] = replace + (ending if ending else "\n")
                    changed.append((reason, stripped.strip(), replace.strip()))
                    hit = True
                    break
            if not hit:
                total_missed += 1
                print(f"\n  MISS   {fname}")
                print(f"         looking for: {find[:60]}")

        if changed:
            print(f"\n{fname}")
            for reason, old, new in changed:
                total_applied += 1
                print(f"  - {reason}")
                print(f"      was: {old[:68]}")
                print(f"      now: {(new[:68] if new else '(line removed)')}")
            if args.execute:
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write("".join(lines))

    print()
    print("=" * 74)
    print(f"{mode} : {total_applied} applied, {total_missed} not found")
    print("=" * 74)

    if not args.execute:
        print("\nRe-run with  --execute  to apply.\n")
    else:
        print("\nVerify what remains:")
        print('  Select-String -Path .\\scripts\\*.py -Pattern "\\d\\d[b-e]_|09[b-e]"')
        print("\nExpect only 'Supersedes ...' lines, which are correct history.\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())