"""Map a parsed Rocket onto the club SolidWorks template's global variables (inches)."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field

from .ork import Rocket

M_TO_IN = 1 / 0.0254

# Club rules baked into the template (see docs/TEMPLATE_SPEC.md)
FIN_TAB_OVERHANG_IN = 0.25  # fin root overhangs the tab by 0.25" fore and aft
DEFAULT_TNUT_COUNT = 3


@dataclass
class TemplateParams:
    values: "OrderedDict[str, tuple]" = field(default_factory=OrderedDict)  # name -> (value, unit, comment)
    fin_points_in: list = field(default_factory=list)
    fin_kind: str = "trapezoid"
    notes: list = field(default_factory=list)

    def set(self, name, value, unit="in", comment=""):
        self.values[name] = (value, unit, comment)

    def get(self, name):
        return self.values[name][0]

    def as_dict(self):
        return {k: v[0] for k, v in self.values.items()}


def _in(m):
    return round(m * M_TO_IN, 4)


def build_params(r: Rocket, tnut_count: int = DEFAULT_TNUT_COUNT) -> TemplateParams:
    p = TemplateParams()
    if not r.body_tubes:
        raise ValueError("Design has no body tube")
    mt = r.motor_tube
    fins = r.fins[0] if r.fins else None

    # The fin can is the body tube that holds the motor tube (else the last tube).
    fin_can = next((t for t in r.body_tubes if mt and t.name == mt.parent), r.body_tubes[-1])
    others = [t for t in r.body_tubes if t is not fin_can]
    upper = others[-1] if others else None
    middle_break = 1 if upper is not None else 0

    p.set("middleBreak", middle_break, "", "1 = extra upper tube + coupler + bulkhead")
    p.set("bodyOD", _in(2 * fin_can.outer_radius), comment="airframe outer diameter")
    p.set("bodyID", _in(2 * fin_can.inner_radius), comment="airframe inner diameter")
    p.set("finCanLength", _in(fin_can.length), comment="aft (fin can) body tube length")
    p.set("upperTubeLength", _in(upper.length) if upper else 0.0, comment="forward tube, only with middleBreak")

    # Coupler + bulkhead at the middle break
    coupler = r.couplers[0] if r.couplers else None
    if coupler and upper:
        into_aft = max(0.0, min(coupler.bottom, fin_can.bottom) - max(coupler.top, fin_can.top))
        if upper.top > fin_can.top:  # unusual: break with upper tube aft of the fin can
            into_aft = coupler.length - into_aft
        p.set("couplerLength", _in(coupler.length), comment="coupler at the middle break")
        p.set("couplerOD", _in(2 * coupler.outer_radius))
        p.set("couplerID", _in(2 * coupler.inner_radius))
        p.set("couplerIntoFinCan", _in(into_aft), comment="coupler length inside the fin can tube")
    else:
        default_cpl = 1.0 * 2 * fin_can.outer_radius * M_TO_IN  # 1 caliber placeholder
        p.set("couplerLength", round(default_cpl, 4) if upper else 0.0,
              comment="placeholder 1 cal" if upper else "unused")
        p.set("couplerOD", _in(2 * fin_can.inner_radius))
        p.set("couplerID", _in(2 * fin_can.inner_radius) - 0.06)
        p.set("couplerIntoFinCan", round(p.get("couplerLength") / 2, 4))
        if upper:
            p.notes.append("Middle break found but no tube coupler in the .ork; coupler set to a 1 caliber placeholder.")
    bh = r.bulkheads[0] if r.bulkheads else None
    p.set("bulkheadThickness", _in(bh.length) if bh else 0.25)

    # Nose cone
    n = r.nose
    if n:
        p.set("noseLength", _in(n.length))
        p.set("noseWall", _in(n.thickness))
        p.set("noseShoulderLength", _in(n.shoulder_length))
        p.set("noseShoulderOD", _in(2 * n.shoulder_radius) if n.shoulder_radius else _in(2 * fin_can.inner_radius))

    # Motor tube + centering rings
    if mt:
        p.set("motorTubeOD", _in(2 * mt.outer_radius))
        p.set("motorTubeID", _in(2 * mt.inner_radius))
        p.set("motorTubeLength", _in(mt.length))
        p.set("motorTubeAftOverhang", _in(mt.bottom - fin_can.bottom), comment="+ = motor tube sticks out aft")
    rings = sorted([g for g in r.rings if g.parent == fin_can.name], key=lambda g: g.top)
    if rings:
        p.set("ringThickness", _in(rings[0].length))
    else:
        p.set("ringThickness", 0.25)
    if mt and rings:
        top_ring = rings[0]
        p.set("topRingFromMotorAft", _in(mt.bottom - top_ring.bottom),
              comment="aft face of top (U-bolt) ring, measured from motor tube aft end")
    elif mt:
        p.set("topRingFromMotorAft", round(_in(mt.length) - 0.25, 4))
    p.set("tNutCount", int(tnut_count), "", "t-nut holes in bottom ring (2-4)")

    # Fins
    if fins:
        p.fin_kind = fins.kind
        p.set("finCount", fins.count, "")
        p.set("finThickness", _in(fins.thickness))
        p.set("rootChord", _in(fins.root_chord))
        p.set("tipChord", _in(fins.tip_chord))
        p.set("sweepLength", _in(fins.sweep_length))
        p.set("finSpan", _in(fins.span))
        p.set("finAftOffset", _in(fin_can.bottom - fins.bottom), comment="fin trailing edge forward of airframe aft end")
        p.fin_points_in = [(round(x * M_TO_IN, 4), round(y * M_TO_IN, 4)) for x, y in fins.points]
        if fins.kind == "freeform" and len(fins.points) != 4:
            p.notes.append("Freeform fin with %d points: v1 template is trapezoid only." % len(fins.points))
        if fins.kind == "elliptical":
            p.notes.append("Elliptical fins are not supported. The v1 template is trapezoid only.")
    return p


def equations_text(p: TemplateParams, source_name="") -> str:
    """SolidWorks external equations file (Equations > Link to external file / macro input)."""
    lines = ["' Generated by ork2sw from %s. Do not edit by hand: re-export from OpenRocket." % source_name]
    for k, (v, unit, comment) in p.values.items():
        if isinstance(v, float):
            v = ("%.4f" % v).rstrip("0").rstrip(".") or "0"
        s = '"%s"= %s%s' % (k, v, unit)
        if comment:
            s += "   '" + comment
        lines.append(s)
    return "\r\n".join(lines) + "\r\n"


def sldcrv_text(p: TemplateParams) -> str:
    """Fin outline in SolidWorks 'Curve Through XYZ Points' format (x aft, y outward, inches)."""
    return "".join("%gin %gin 0in\r\n" % (x, y) for x, y in p.fin_points_in)
