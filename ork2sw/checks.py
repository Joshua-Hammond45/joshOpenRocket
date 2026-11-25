"""Design checks: the common mistakes from the club lectures, caught before CAD."""
from __future__ import annotations

from dataclasses import dataclass

from .ork import Rocket
from .params import M_TO_IN, FIN_TAB_OVERHANG_IN

ERROR, WARN, INFO, OK = "ERROR", "WARN", "INFO", "OK"
TOL_IN = 0.02  # dimensional tolerance when comparing to club standards


@dataclass
class Finding:
    level: str
    code: str
    message: str


def _in(m):
    return m * M_TO_IN


def run_checks(r: Rocket) -> list:
    out = []

    def add(level, code, msg):
        out.append(Finding(level, code, msg))

    # ---- scope -------------------------------------------------------------
    if r.stage_count > 1:
        add(ERROR, "scope.stages", "Multi-stage rockets are outside the L1 template. Only the first stage was read.")
    if len(r.body_tubes) > 2:
        add(ERROR, "scope.tubes", "%d body tubes found. The template supports 1, or 2 with a middle break." % len(r.body_tubes))
    for tag in sorted(set(r.unsupported)):
        add(WARN, "scope.unsupported", "<%s> is not in the template and will be ignored." % tag)
    if r.body_tubes:
        ods = {round(_in(2 * t.outer_radius), 3) for t in r.body_tubes}
        if len(ods) > 1:
            add(ERROR, "scope.diameters", "Body tubes have different diameters %s. The template needs one airframe diameter." % sorted(ods))

    # ---- recovery (Lecture 1 slide 26: most common HPR mistake) -------------
    if not r.parachutes:
        add(ERROR, "recovery.nochute", "No parachute in the design.")
    for c in r.parachutes:
        ev = [e.lower() for e in c.deploy_events]
        if ev and all(e == "apogee" for e in ev):
            add(OK, "recovery.apogee", "%s deploys at apogee." % c.name)
        elif not ev:
            add(WARN, "recovery.apogee", "%s: deploy event not found in file. Set it to apogee." % c.name)
        else:
            add(ERROR, "recovery.apogee",
                "%s deploys on '%s'. Set Deploys at: Apogee (unless it's a fixed-delay AE motor)." % (c.name, ", ".join(c.deploy_events)))
        d = _in(c.diameter)
        if d and not (24 - 1 <= d <= 36 + 1):
            add(INFO, "recovery.chutesize", "%s is %.0f\" diameter. L1 guidance is 24\" to 36\"; check ground-hit velocity." % (c.name, d))
    length_in = _in(r.length)
    if not r.shock_cords:
        add(WARN, "recovery.nocord", "No shock cord in the design. Add one (Kevlar or nylon, 3x rocket length).")
    for s in r.shock_cords:
        L = _in(s.length)
        if L < 3 * length_in - 1:
            add(ERROR, "recovery.cordlength",
                "%s is %.0f\" long; rule of thumb is 3x rocket length = %.0f\"." % (s.name, L, 3 * length_in))
        else:
            add(OK, "recovery.cordlength", "Shock cord %.0f\" >= 3x rocket length." % L)

    # ---- simulation ----------------------------------------------------------
    sims = [s for s in r.sims if s.stability_at_rod is not None or s.ground_hit_velocity is not None]
    if not sims:
        add(WARN, "sim.none", "No simulation results saved. Run a simulation in OpenRocket and save before exporting.")
    for s in sims:
        if s.status and s.status.lower() == "outdated":
            add(WARN, "sim.outdated", "Simulation '%s' is outdated. Re-run it after your last design change." % s.name)
        if s.stability_at_rod is not None:
            st = s.stability_at_rod
            if st < 1.0:
                add(ERROR, "sim.stability", "'%s': stability %.2f cal off the rod. Need >= 1.0; enlarge fins or add nose weight." % (s.name, st))
            elif st > 2.0:
                add(WARN, "sim.stability", "'%s': stability %.2f cal is above 2.0 (overstable, weathercocks)." % (s.name, st))
            else:
                add(OK, "sim.stability", "'%s': stability %.2f cal." % (s.name, st))
        if s.ground_hit_velocity is not None:
            fps = s.ground_hit_velocity / 0.3048
            if fps > 30:
                add(ERROR, "sim.groundhit", "'%s': ground hit %.1f ft/s exceeds TRA 30 ft/s limit." % (s.name, fps))
            elif not (18 <= fps <= 22):
                add(INFO, "sim.groundhit", "'%s': ground hit %.1f ft/s (aim for 18-22)." % (s.name, fps))
            else:
                add(OK, "sim.groundhit", "'%s': ground hit %.1f ft/s." % (s.name, fps))

    # ---- motor mount ---------------------------------------------------------
    mt = r.motor_tube
    if mt is None:
        add(ERROR, "mount.none", "No inner (motor) tube.")
    else:
        if not mt.is_motor_mount:
            add(WARN, "mount.flag", "Inner tube is not marked as a motor mount (Motors & Configuration tab).")
        for m in r.motors:
            if m.length and m.length > mt.length:
                add(ERROR, "mount.short", "Motor %s (%.2f\") is longer than the motor tube (%.2f\")."
                    % (m.designation, _in(m.length), _in(mt.length)))
            if m.diameter and abs(_in(m.diameter) - _in(2 * mt.inner_radius)) > 0.1:
                add(WARN, "mount.dia", "Motor %s is %.2f\" but motor tube ID is %.2f\"."
                    % (m.designation, _in(m.diameter), _in(2 * mt.inner_radius)))
        if not r.motors:
            add(WARN, "mount.nomotor", "No motor selected.")
        fin_can = next((t for t in r.body_tubes if t.name == mt.parent), None)
        if fin_can and abs(_in(mt.bottom - fin_can.bottom)) > TOL_IN:
            add(INFO, "mount.flush", "Motor tube aft end is %.2f\" from the airframe aft end; template default is flush."
                % _in(mt.bottom - fin_can.bottom))

    # ---- centering rings (Lecture 1 slide 17) --------------------------------
    rings = sorted(r.rings, key=lambda g: g.top)
    if len(rings) < 2:
        add(ERROR, "rings.count", "%d centering ring(s). The template uses 3 (top U-bolt ring, middle, bottom t-nut ring)." % len(rings))
    for g in rings:
        if abs(_in(g.length) - 0.25) > TOL_IN:
            add(WARN, "rings.thick", "%s is %.3f\" thick; club standard is 0.25\"." % (g.name, _in(g.length)))
        if "plywood" not in g.material.name.lower() and "birch" not in g.material.name.lower():
            add(WARN, "rings.material", "%s is '%s'; club standard is plywood." % (g.name, g.material.name or "?"))
        if mt and (g.top < mt.top - 1e-6 or g.bottom > mt.bottom + 1e-6):
            add(ERROR, "rings.offtube", "%s sits outside the motor tube." % g.name)

    # ---- fins (Lecture 1 slides 18-20, Lecture 2 slide 22) -------------------
    if not r.fins:
        add(ERROR, "fins.none", "No fin set.")
    if len(r.fins) > 1:
        add(ERROR, "fins.many", "%d fin sets; the template supports one." % len(r.fins))
    for f in r.fins[:1]:
        if f.count < 3:
            add(ERROR, "fins.count", "%d fins; use at least 3 (4 is most common)." % f.count)
        if f.kind == "freeform" and len(f.points) != 4:
            add(ERROR, "fins.freeform", "Freeform fin with %d points. The v1 template is trapezoid only; "
                "use a trapezoidal fin set in OpenRocket." % len(f.points))
        if f.kind == "elliptical":
            add(ERROR, "fins.elliptical", "Elliptical fins are not supported. The v1 template is trapezoid only.")
        if abs(_in(f.thickness) - 0.25) > TOL_IN:
            add(WARN, "fins.thick", "Fins are %.3f\" thick; club standard is 0.25\"." % _in(f.thickness))
        if "plywood" not in f.material.name.lower() and "birch" not in f.material.name.lower():
            add(WARN, "fins.material", "Fins are '%s'; club standard is plywood." % (f.material.name or "?"))
        if abs(f.cant) > 1e-6:
            add(WARN, "fins.cant", "Fins are canted; the template builds straight fins.")
        want_tab = _in(f.root_chord) - 2 * FIN_TAB_OVERHANG_IN
        if abs(_in(f.tab_length) - want_tab) > TOL_IN or abs(_in(f.tab_front) - FIN_TAB_OVERHANG_IN) > TOL_IN:
            add(INFO, "fins.tab",
                "OpenRocket fin tab is %.2f\" long starting %.2f\" aft of the leading edge. The template forces "
                "root chord - 0.5\" = %.2f\" centered; update OpenRocket to match so mass is right."
                % (_in(f.tab_length), _in(f.tab_front), want_tab))
        if mt and r.body_tubes:
            fin_can = next((t for t in r.body_tubes if t.name == f.parent), r.body_tubes[-1])
            want_h = _in(fin_can.inner_radius - mt.outer_radius)
            if abs(_in(f.tab_height) - want_h) > TOL_IN:
                add(INFO, "fins.tabheight", "Fin tab height %.3f\" should reach the motor tube (%.3f\"). Template uses %.3f\"."
                    % (_in(f.tab_height), want_h, want_h))
            if abs(_in(fin_can.bottom - f.bottom)) > TOL_IN:
                add(WARN, "fins.position", "Fin trailing edge is %.2f\" forward of the airframe aft end; template puts it flush."
                    % _in(fin_can.bottom - f.bottom))
            # fin tab should land on the bottom ring and under the middle ring
            if len(rings) >= 2:
                bottom_ring, middle_ring = rings[-1], rings[-2]
                tab_top = f.top + f.tab_front
                tab_bot = tab_top + f.tab_length
                if tab_bot > bottom_ring.top + 1e-3 or tab_top < middle_ring.bottom - 1e-3:
                    add(INFO, "fins.rings", "In OpenRocket the fin tab overlaps a centering ring. The template spaces "
                        "the bottom and middle rings with the tab; move the middle ring to sit on the tab.")

    # ---- middle break --------------------------------------------------------
    if len(r.body_tubes) == 2:
        if not r.couplers:
            add(ERROR, "break.coupler", "Middle break with no tube coupler. Add a coupler (about 1 caliber) at the joint.")
        else:
            c = r.couplers[0]
            cal = _in(c.length) / _in(2 * r.body_tubes[0].outer_radius)
            if cal < 1.0:
                add(WARN, "break.couplerlen", "Coupler is %.2f caliber; use at least 1 caliber (half in each tube)." % cal)
        if not r.bulkheads:
            add(WARN, "break.bulkhead", "Middle break with no bulkhead. The template adds one in the coupler.")
    return out


def has_errors(findings) -> bool:
    return any(f.level == ERROR for f in findings)
