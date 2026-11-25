# ork2sw: OpenRocket → club SolidWorks template

Turns a member's OpenRocket `.ork` into a ready SolidWorks assembly built from the club's master template, so the stuff people get wrong (t-nut side, ring clocking, fin tabs, units, broken file references) is already right.

## Use

```
python -m ork2sw MyRocket.ork          # checks the design, writes MyRocket_sw/
```

Then in SolidWorks: **Tools > Macro > Run > Ork2SW.swp** and pick `MyRocket_sw/rocket_params.txt`. The macro copies the master template into `MyRocket_sw/CAD/`, sets every dimension, picks single tube or middle break, and rebuilds.

The export stops if the design check finds an error (chute not at apogee, stability under 1.0 cal, ground hit over 30 ft/s, short shock cord, ...). Fix it in OpenRocket, re-run the sim, save, export again. `--force` overrides.

Outputs in `MyRocket_sw/`:
- `rocket_params.txt`: SolidWorks equations-format global variables (inches)
- `design_check.txt`: the check report
- `fin_points.sldcrv`: fin outline (Curve Through XYZ Points format)
- `rocket_params.json`: everything above, for other tools

Python 3.8+, no dependencies. Tests: `python -m pytest tests`.

## Layout

- `ork2sw/ork.py`: .ork reader (zip or bare XML, OR file formats 1.x)
- `ork2sw/params.py`: maps the design onto template variables
- `ork2sw/checks.py`: lecture rules as checks
- `solidworks/Ork2SW.bas`: the SolidWorks macro (import into a .swp once)
- `docs/TEMPLATE_SPEC.md`: how to build the master template
