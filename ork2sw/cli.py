"""Command line: python -m ork2sw MyRocket.ork [-o outdir]"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .checks import run_checks, has_errors, ERROR, WARN, INFO, OK
from .ork import parse
from .params import build_params, equations_text, sldcrv_text, DEFAULT_TNUT_COUNT

ICON = {ERROR: "[X]", WARN: "[!]", INFO: "[i]", OK: "[ok]"}
ORDER = {ERROR: 0, WARN: 1, INFO: 2, OK: 3}


def report_text(rocket, findings, params, src):
    lines = ["ork2sw %s design check: %s" % (__version__, os.path.basename(src)),
             "Rocket: %s   length %.1f in   %s" % (rocket.name, rocket.length / 0.0254,
                                                    "middle break" if params.get("middleBreak") else "single tube"),
             ""]
    for f in sorted(findings, key=lambda f: ORDER[f.level]):
        lines.append("%-5s %s" % (ICON[f.level], f.message))
    for n in params.notes:
        lines.append("[i]   " + n)
    lines.append("")
    n_err = sum(f.level == ERROR for f in findings)
    n_warn = sum(f.level == WARN for f in findings)
    lines.append("%d error(s), %d warning(s)." % (n_err, n_warn))
    if n_err:
        lines.append("Fix the errors in OpenRocket and export again (or use --force).")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ork2sw", description=__doc__)
    ap.add_argument("ork", help="OpenRocket design file (.ork)")
    ap.add_argument("-o", "--out", help="output folder (default: <name>_sw next to the .ork)")
    ap.add_argument("--tnuts", type=int, default=DEFAULT_TNUT_COUNT, help="t-nut holes in the bottom ring (2-4)")
    ap.add_argument("--force", action="store_true", help="write outputs even if there are errors")
    ap.add_argument("--json", action="store_true", help="also print parameters as JSON")
    a = ap.parse_args(argv)

    rocket = parse(a.ork)
    findings = run_checks(rocket)
    params = build_params(rocket, tnut_count=max(2, min(4, a.tnuts)))
    rep = report_text(rocket, findings, params, a.ork)
    sys.stdout.write(rep)

    if has_errors(findings) and not a.force:
        return 2
    base = os.path.splitext(os.path.basename(a.ork))[0]
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.ork)), base + "_sw")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "rocket_params.txt"), "w", newline="") as f:
        f.write(equations_text(params, os.path.basename(a.ork)))
    with open(os.path.join(out, "fin_points.sldcrv"), "w", newline="") as f:
        f.write(sldcrv_text(params))
    with open(os.path.join(out, "design_check.txt"), "w") as f:
        f.write(rep)
    with open(os.path.join(out, "rocket_params.json"), "w") as f:
        json.dump({"source": os.path.basename(a.ork), "finKind": params.fin_kind,
                   "params": params.as_dict(), "finPointsIn": params.fin_points_in,
                   "findings": [f.__dict__ for f in findings]}, f, indent=2)
    if a.json:
        print(json.dumps(params.as_dict(), indent=2))
    print("Wrote %s" % out)
    return 0
