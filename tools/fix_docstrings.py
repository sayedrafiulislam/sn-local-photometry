"""
fix_docstrings.py

Repairs stale text left after the pipeline renumbering.

The automatic rename only matched full filenames. Prose refers to scripts by
bare token -- "09c", "11b", "16c" -- and those were missed. Some docstrings
also quote result values that predate the aperture guard.

Three passes:

  1. Specific phrases that need rewording, not just renaming.
  2. Bare tokens for CURRENT scripts, mapped to their step number.
  3. Result values in script 16 that predate the aperture guard.

Tokens for SUPERSEDED scripts (10b, 15b, 16b, 09e) are left alone: sentences
like "Supersedes 10b_curve_of_growth_annulus_test.py" are correct history.

    python tools\\fix_docstrings.py
    python tools\\fix_docstrings.py --execute
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(r"D:\Thesis\My Work\sn-local-photometry")
SCRIPTS = REPO / "scripts"

# ---------------------------------------------------------------------------
# Pass 1 -- whole phrases. Applied before the token pass, longest first.
# ---------------------------------------------------------------------------
PHRASES = [
    # obsolete naming rationale
    ("Named 15c because 15b is already taken by 15b_apply_galactic_extinction.py.",
     "Runs at step 17. Its output feeds step 18, then step 19."),
    ("Named 15d because 15b is the original of this script and 15c is the corrected",
     "Runs at step 19, after step 18 has written the quality flags. See"),
    ("zero-point script.",
     "NUMBERING.md for the full order."),

    # run-order sentences that named superseded scripts
    ("Run 16_flag_low_flux_colors.py, then 15b_apply_galactic_extinction.py --",
     "  Next: 18_flag_unreliable_colours.py, then 19_apply_galactic_extinction.py."),
    ("in that order, despite the numbering.", ""),
    ("order is 15c -> 16c -> 15d -> 17b. Anyone reading the repository will assume",
     "order is step 17 -> 18 -> 19 -> 20. Script numbers now match run order; see"),
    ("15 -> 15b -> 16 and be wrong.", "NUMBERING.md."),
    ("(Order is 15c -> 16c -> 15d -> 17b, despite the numbering.)",
     "(Order is step 17 -> 18 -> 19 -> 20.)"),

    # a warning that has already been acted on
    ("*** 15b_apply_galactic_extinction.py currently filters on flag_low_flux and",
     "*** Steps 19 and 20 filter on flag_exclude. flag_low_flux is retained in the"),
    ("*** must be changed to flag_exclude, or the new criteria will have no effect.",
     "*** output for comparison only and must not be filtered on."),
    ("15b_apply_galactic_extinction.py currently filters on flag_low_flux and MUST be",
     "Steps 19 and 20 already do this. flag_low_flux is retained in the output"),
    ("updated, or the calibration criterion will have no effect on the final sample.",
     "for comparison only and must not be used as an exclusion criterion."),

    # stale script-range references
    ("for scripts 12-18 and 09c/09d", "for steps 15 to 22"),
    ("(identical; for scripts 12-18 and 09c/09d)", "(identical; for steps 15 to 22)"),

    # usage examples pointing at the untagged colour file
    ("local_color_vs_radius.csv ^", "local_color_vs_radius_ann20-30.csv ^"),
    ("nuclear_contamination\n", "nuclear_contamination_ann20-30\n"),
    ("nuclear_permutation\n", "nuclear_permutation_ann20-30\n"),

    # result values predating the aperture guard (script 16)
    ("Across 98 objects the median step was", "Across 101 objects the median step was"),
    ("+0.0197 mag,  95 per cent bootstrap CI [+0.0098, +0.0337]",
     "+0.0220 mag,  95 per cent bootstrap CI [+0.0135, +0.0331]"),
]

# ---------------------------------------------------------------------------
# Pass 2 -- bare tokens for CURRENT scripts. Not followed by an underscore or
# a word character, so filenames like 10b_curve_of_growth... are untouched.
# ---------------------------------------------------------------------------
TOKENS = {
    "09b": "step 12",
    "09c": "step 15",
    "09d": "step 16",
    "10c": "step 13",
    "11b": "step 14",
    "15c": "step 17",
    "15d": "step 19",
    "16c": "step 18",
    "17b": "step 20",
    "18b": "step 21",
}

# Files to process. Superseded scripts are excluded entirely.
TARGETS = sorted(SCRIPTS.glob("[0-9][0-9]_*.py"))


def apply_phrases(text: str) -> tuple[str, list[str]]:
    notes = []
    for old, new in PHRASES:
        if old and old in text:
            text = text.replace(old, new)
            notes.append(f"phrase: {old[:56]}")
    return text, notes


def apply_tokens(text: str) -> tuple[str, list[str]]:
    notes = []
    for tok, rep in TOKENS.items():
        # bare token: not part of a filename, not part of a longer word
        pattern = re.compile(r"(?<![\w])" + tok + r"(?![\w_])")
        text, n = pattern.subn(rep, text)
        if n:
            notes.append(f"token: {tok} -> {rep}  ({n}x)")
    return text, notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    mode = "EXECUTING" if args.execute else "DRY RUN - nothing will change"
    print(f"\n{'=' * 74}\n{mode}\n{'=' * 74}")

    if not SCRIPTS.is_dir():
        print(f"\nScripts folder not found: {SCRIPTS}")
        return 1
    if not TARGETS:
        print(f"\nNo numbered scripts found in {SCRIPTS}")
        return 1

    total = 0
    for path in TARGETS:
        with open(path, "r", encoding="utf-8", newline="") as fh:
            original = fh.read()

        text, n1 = apply_phrases(original)
        text, n2 = apply_tokens(text)
        notes = n1 + n2

        if text != original:
            total += len(notes)
            print(f"\n{path.name}")
            for note in notes:
                print(f"  - {note}")
            if args.execute:
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(text)

    print(f"\n{'=' * 74}\n{mode} : {total} change(s) across "
          f"{len(TARGETS)} scripts\n{'=' * 74}")

    if not args.execute:
        print("\nRe-run with  --execute  to apply.\n")
    else:
        print("\nVerify:")
        print('  Select-String -Path .\\scripts\\*.py -Pattern '
              '"09[bcd]\\b|10c\\b|11b\\b|15[cd]\\b|16c\\b|17b\\b|18b\\b"')
        print("\nExpect nothing. Remaining 10b / 15b / 16b hits are correct "
              "history.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())