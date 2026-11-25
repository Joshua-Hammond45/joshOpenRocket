"""Read an OpenRocket .ork file into a small, CAD-oriented rocket model.

OpenRocket stores everything in SI (meters, kg). This module keeps SI internally
and converts to inches only at export time.

An .ork file is either a zip archive containing ``rocket.ork`` (the normal case)
or the bare XML itself (older versions / "save uncompressed").
"""
from __future__ import annotations

import io
import math
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass
class Material:
    name: str = ""
    density: Optional[float] = None


@dataclass
class NoseCone:
    shape: str = "ogive"
    length: float = 0.0
    aft_radius: float = 0.0
    thickness: float = 0.0
    shoulder_radius: float = 0.0
    shoulder_length: float = 0.0
    shoulder_thickness: float = 0.0
    shape_parameter: Optional[float] = None
    material: Material = field(default_factory=Material)


@dataclass
class Tube:
    """Body tube, inner (motor) tube or tube coupler."""
    name: str = ""
    kind: str = "bodytube"
    length: float = 0.0
    outer_radius: float = 0.0
    thickness: float = 0.0
    top: float = 0.0  # absolute position of forward end, from nose tip
    material: Material = field(default_factory=Material)
    is_motor_mount: bool = False
    parent: Optional[str] = None

    @property
    def inner_radius(self) -> float:
        return self.outer_radius - self.thickness

    @property
    def bottom(self) -> float:
        return self.top + self.length


@dataclass
class Ring:
    """Centering ring or bulkhead."""
    name: str = ""
    kind: str = "centeringring"
    length: float = 0.0  # thickness along the rocket axis
    outer_radius: float = 0.0
    inner_radius: float = 0.0
    top: float = 0.0
    material: Material = field(default_factory=Material)
    parent: Optional[str] = None

    @property
    def bottom(self) -> float:
        return self.top + self.length


@dataclass
class FinSet:
    kind: str = "trapezoid"  # trapezoid | freeform | elliptical
    count: int = 0
    thickness: float = 0.0
    root_chord: float = 0.0
    tip_chord: float = 0.0
    sweep_length: float = 0.0
    span: float = 0.0
    tab_height: float = 0.0
    tab_length: float = 0.0
    tab_front: float = 0.0  # tab leading edge measured aft from root leading edge
    points: list = field(default_factory=list)  # freeform (x, y), x aft, y outward
    top: float = 0.0  # absolute position of root leading edge
    cant: float = 0.0
    material: Material = field(default_factory=Material)
    parent: Optional[str] = None

    @property
    def bottom(self) -> float:
        return self.top + self.root_chord


@dataclass
class Parachute:
    name: str = ""
    diameter: float = 0.0
    deploy_events: list = field(default_factory=list)  # e.g. ["apogee"]
    deploy_altitude: Optional[float] = None
    parent: Optional[str] = None


@dataclass
class ShockCord:
    name: str = ""
    length: float = 0.0
    material: Material = field(default_factory=Material)
    parent: Optional[str] = None


@dataclass
class Motor:
    designation: str = ""
    manufacturer: str = ""
    diameter: Optional[float] = None
    length: Optional[float] = None
    delay: Optional[str] = None


@dataclass
class SimResult:
    name: str = ""
    status: str = ""
    max_altitude: Optional[float] = None
    max_velocity: Optional[float] = None
    max_acceleration: Optional[float] = None
    ground_hit_velocity: Optional[float] = None
    launch_rod_velocity: Optional[float] = None
    stability_at_rod: Optional[float] = None
    min_stability: Optional[float] = None


@dataclass
class Rocket:
    name: str = ""
    nose: Optional[NoseCone] = None
    body_tubes: list = field(default_factory=list)
    inner_tubes: list = field(default_factory=list)
    couplers: list = field(default_factory=list)
    rings: list = field(default_factory=list)  # centering rings
    bulkheads: list = field(default_factory=list)
    fins: list = field(default_factory=list)
    parachutes: list = field(default_factory=list)
    shock_cords: list = field(default_factory=list)
    motors: list = field(default_factory=list)
    sims: list = field(default_factory=list)
    stage_count: int = 1
    unsupported: list = field(default_factory=list)  # component tags we ignore
    or_version: str = ""
    or_creator: str = ""

    @property
    def length(self) -> float:
        ends = [t.bottom for t in self.body_tubes]
        if self.nose:
            ends.append(self.nose.length)
        return max(ends) if ends else 0.0

    @property
    def motor_tube(self) -> Optional[Tube]:
        for t in self.inner_tubes:
            if t.is_motor_mount:
                return t
        return self.inner_tubes[0] if self.inner_tubes else None


# --------------------------------------------------------------------------- #
# XML helpers
# --------------------------------------------------------------------------- #
def _txt(el, tag, default=None):
    if el is None:
        return default
    c = el.find(tag)
    if c is None or c.text is None:
        return default
    return c.text.strip()


def _num(el, tag, default=None):
    """Read a number; values like 'auto 0.0394' return 0.0394, bare 'auto' -> None."""
    t = _txt(el, tag)
    if t is None:
        return default
    return _parse_auto(t, default)


def _parse_auto(t, default=None):
    t = t.strip()
    if t.lower().startswith("auto"):
        rest = t[4:].strip()
        if not rest:
            return None
        t = rest
    try:
        v = float(t)
    except ValueError:
        return default
    return None if math.isnan(v) else v


def _is_auto(el, tag):
    t = _txt(el, tag)
    return t is not None and t.lower().startswith("auto")


def _material(el):
    m = el.find("material") if el is not None else None
    if m is None:
        return Material()
    d = m.get("density")
    return Material(name=(m.text or "").strip(), density=float(d) if d else None)


def _axial(el):
    """Return (method, offset). Handles both <axialoffset method=> and old <position type=>."""
    a = el.find("axialoffset")
    if a is not None:
        return (a.get("method") or "top").lower(), _parse_auto(a.text or "0", 0.0) or 0.0
    p = el.find("position")
    if p is not None:
        return (p.get("type") or "top").lower(), _parse_auto(p.text or "0", 0.0) or 0.0
    return "after", 0.0


def _place(method, offset, comp_len, parent_top, parent_len):
    """Absolute top position of an internal component (or fin set)."""
    if method == "top":
        return parent_top + offset
    if method == "bottom":
        return parent_top + parent_len - comp_len + offset
    if method == "middle":
        return parent_top + (parent_len - comp_len) / 2 + offset
    if method == "absolute":
        return offset
    # "after" is only meaningful for body components; treat as top.
    return parent_top + offset


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_xml_bytes(path_or_bytes) -> bytes:
    if isinstance(path_or_bytes, (bytes, bytearray)):
        data = bytes(path_or_bytes)
    else:
        with open(path_or_bytes, "rb") as f:
            data = f.read()
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = z.namelist()
            pick = next((n for n in names if n.lower().endswith(".ork")), None)
            if pick is None:
                pick = next((n for n in names if n.lower().endswith(".xml")), names[0])
            return z.read(pick)
    if data[:2] == b"\x1f\x8b":  # some versions gzip instead of zip
        import gzip
        return gzip.decompress(data)
    return data


def parse(path_or_bytes) -> Rocket:
    root = ET.fromstring(load_xml_bytes(path_or_bytes))
    if root.tag != "openrocket":
        raise ValueError("Not an OpenRocket file (root element is <%s>)" % root.tag)
    r = Rocket(or_version=root.get("version", ""), or_creator=root.get("creator", ""))
    rk = root.find("rocket")
    if rk is None:
        raise ValueError("No <rocket> element found")
    r.name = _txt(rk, "name", "Rocket")
    stages = rk.findall("./subcomponents/stage")
    r.stage_count = len(stages)
    if not stages:
        raise ValueError("Rocket has no stages")
    _parse_stage(stages[0], r)
    _resolve_auto_radii(r)
    _parse_sims(root, r)
    return r


def _parse_stage(stage, r: Rocket):
    pos = 0.0  # running absolute position of body components
    pending_auto = []
    for comp in stage.findall("./subcomponents/*"):
        tag = comp.tag
        if tag == "nosecone":
            n = NoseCone(
                shape=_txt(comp, "shape", "ogive"),
                length=_num(comp, "length", 0.0),
                aft_radius=_num(comp, "aftradius") or 0.0,
                thickness=_num(comp, "thickness", 0.0),
                shoulder_radius=_num(comp, "aftshoulderradius", 0.0),
                shoulder_length=_num(comp, "aftshoulderlength", 0.0),
                shoulder_thickness=_num(comp, "aftshoulderthickness", 0.0),
                shape_parameter=_num(comp, "shapeparameter"),
                material=_material(comp),
            )
            r.nose = n
            pos += n.length
            _parse_inner(comp, r, "nosecone", 0.0, n.length, n.aft_radius)
        elif tag == "bodytube":
            t = Tube(
                name=_txt(comp, "name", "Body tube"),
                kind="bodytube",
                length=_num(comp, "length", 0.0),
                outer_radius=_num(comp, "radius") or 0.0,
                thickness=_num(comp, "thickness", 0.0),
                top=pos,
                material=_material(comp),
            )
            if _is_auto(comp, "radius") and not t.outer_radius:
                pending_auto.append(t)
            r.body_tubes.append(t)
            pos += t.length
            _parse_inner(comp, r, t.name, t.top, t.length, t.outer_radius - t.thickness, owner=t)
        elif tag == "transition":
            r.unsupported.append("transition")
            pos += _num(comp, "length", 0.0)
        else:
            r.unsupported.append(tag)


def _parse_inner(parent_el, r, parent_name, parent_top, parent_len, parent_inner_r, owner=None):
    for comp in parent_el.findall("./subcomponents/*"):
        tag = comp.tag
        method, off = _axial(comp)
        if tag in ("innertube", "tubecoupler"):
            length = _num(comp, "length", 0.0)
            t = Tube(
                name=_txt(comp, "name", tag),
                kind=tag,
                length=length,
                outer_radius=_num(comp, "outerradius") or 0.0,
                thickness=_num(comp, "thickness", 0.0),
                top=_place(method, off, length, parent_top, parent_len),
                material=_material(comp),
                is_motor_mount=comp.find("motormount") is not None,
                parent=parent_name,
            )
            (r.inner_tubes if tag == "innertube" else r.couplers).append(t)
            mm = comp.find("motormount")
            if mm is not None:
                for m in mm.findall("motor"):
                    r.motors.append(Motor(
                        designation=_txt(m, "designation", ""),
                        manufacturer=_txt(m, "manufacturer", ""),
                        diameter=_num(m, "diameter"),
                        length=_num(m, "length"),
                        delay=_txt(m, "delay"),
                    ))
            # couplers can hold bulkheads etc.
            _parse_inner(comp, r, t.name, t.top, t.length, t.inner_radius)
            for b in r.bulkheads + r.rings:  # rings inside a coupler belong to the coupler
                if b.parent == t.name:
                    b.parent = parent_name if tag == "innertube" else t.name
        elif tag in ("centeringring", "bulkhead"):
            length = _num(comp, "length", 0.0)
            ring = Ring(
                name=_txt(comp, "name", tag),
                kind=tag,
                length=length,
                outer_radius=_num(comp, "outerradius") or 0.0,
                inner_radius=(_num(comp, "innerradius") or 0.0) if tag == "centeringring" else 0.0,
                top=_place(method, off, length, parent_top, parent_len),
                material=_material(comp),
                parent=parent_name,
            )
            (r.rings if tag == "centeringring" else r.bulkheads).append(ring)
        elif tag in ("trapezoidfinset", "freeformfinset", "ellipticalfinset"):
            f = _parse_fins(comp, tag)
            f.parent = parent_name
            f.top = _place(method, off, f.root_chord, parent_top, parent_len)
            r.fins.append(f)
        elif tag == "parachute":
            events = [e.text.strip() for e in comp.iter("deployevent") if e.text]
            r.parachutes.append(Parachute(
                name=_txt(comp, "name", "Parachute"),
                diameter=_num(comp, "diameter", 0.0),
                deploy_events=sorted(set(events)),
                deploy_altitude=_num(comp, "deployaltitude"),
                parent=parent_name,
            ))
        elif tag == "shockcord":
            r.shock_cords.append(ShockCord(
                name=_txt(comp, "name", "Shock cord"),
                length=_num(comp, "cordlength", 0.0),
                material=_material(comp),
                parent=parent_name,
            ))
        elif tag in ("masscomponent", "streamer", "launchlug", "railbutton", "engineblock"):
            if tag == "engineblock":
                r.unsupported.append(tag)
            # mass items, lugs and buttons are not modeled in the v1 template
        else:
            r.unsupported.append(tag)


def _parse_fins(el, tag) -> FinSet:
    kind = {"trapezoidfinset": "trapezoid", "freeformfinset": "freeform",
            "ellipticalfinset": "elliptical"}[tag]
    f = FinSet(
        kind=kind,
        count=int(_num(el, "fincount", 0) or 0),
        thickness=_num(el, "thickness", 0.0),
        tab_height=_num(el, "tabheight", 0.0),
        tab_length=_num(el, "tablength", 0.0),
        cant=_num(el, "cant", 0.0),
        material=_material(el),
    )
    if kind == "trapezoid":
        f.root_chord = _num(el, "rootchord", 0.0)
        f.tip_chord = _num(el, "tipchord", 0.0)
        f.sweep_length = _num(el, "sweeplength", 0.0)
        f.span = _num(el, "height", 0.0)
        f.points = [(0.0, 0.0), (f.sweep_length, f.span),
                    (f.sweep_length + f.tip_chord, f.span), (f.root_chord, 0.0)]
    elif kind == "elliptical":
        f.root_chord = _num(el, "rootchord", 0.0)
        f.span = _num(el, "height", 0.0)
    else:
        pts = [(float(p.get("x")), float(p.get("y"))) for p in el.findall("./finpoints/point")]
        f.points = pts
        if pts:
            xs = [p[0] for p in pts]
            f.root_chord = max(xs) - min(xs)
            f.span = max(p[1] for p in pts)
            # best-effort trapezoid equivalent for templates that only take 4 numbers
            if len(pts) == 4:
                f.sweep_length = pts[1][0] - pts[0][0]
                f.tip_chord = pts[2][0] - pts[1][0]
    tp = el.find("tabposition")
    tab_off = _parse_auto(tp.text or "0", 0.0) if tp is not None else 0.0
    rel = (tp.get("relativeto") if tp is not None else "front") or "front"
    rel = rel.lower()
    if rel in ("front", "top"):
        f.tab_front = tab_off
    elif rel in ("center", "middle"):
        f.tab_front = (f.root_chord - f.tab_length) / 2 + tab_off
    else:  # end / bottom
        f.tab_front = f.root_chord - f.tab_length + tab_off
    return f


def _resolve_auto_radii(r: Rocket):
    # Body tubes with bare "auto" radius take the nose cone / neighbor radius.
    known = r.nose.aft_radius if r.nose and r.nose.aft_radius else 0.0
    for t in r.body_tubes:
        if t.outer_radius:
            known = t.outer_radius
    for t in r.body_tubes:
        if not t.outer_radius:
            t.outer_radius = known
    if r.nose and not r.nose.aft_radius and r.body_tubes:
        r.nose.aft_radius = r.body_tubes[0].outer_radius
    # Rings with auto radii: outer = owning tube ID, inner = motor tube OD.
    mt = r.motor_tube
    for c in r.couplers:
        owner = next((t for t in r.body_tubes if t.name == c.parent), None)
        if owner and (c.outer_radius <= 0 or c.outer_radius > owner.inner_radius + 1e-9):
            c.outer_radius = owner.inner_radius
    for ring in r.rings + r.bulkheads:
        owner = next((t for t in r.body_tubes + r.couplers if t.name == ring.parent), None)
        if owner and (ring.outer_radius <= 0 or ring.outer_radius > owner.inner_radius + 1e-9):
            ring.outer_radius = owner.inner_radius
        if ring.kind == "centeringring" and not ring.inner_radius and mt:
            ring.inner_radius = mt.outer_radius


def _parse_sims(root, r: Rocket):
    for sim in root.findall("./simulations/simulation"):
        s = SimResult(name=_txt(sim, "name", ""), status=sim.get("status", ""))
        fd = sim.find("flightdata")
        if fd is None:
            r.sims.append(s)
            continue

        def a(k):
            v = fd.get(k)
            try:
                v = float(v)
                return None if math.isnan(v) else v
            except (TypeError, ValueError):
                return None

        s.max_altitude = a("maxaltitude")
        s.max_velocity = a("maxvelocity")
        s.max_acceleration = a("maxacceleration")
        s.ground_hit_velocity = a("groundhitvelocity")
        s.launch_rod_velocity = a("launchrodvelocity")
        br = fd.find("databranch")
        if br is not None:
            types = [t.strip() for t in (br.get("types") or "").split(",")]
            col = next((i for i, t in enumerate(types) if t.lower().startswith("stability margin")), None)
            tcol = types.index("Time") if "Time" in types else 0
            rod_t = None
            for ev in br.findall("event"):
                if ev.get("type") in ("launchrod", "LAUNCHROD"):
                    rod_t = float(ev.get("time"))
            if col is not None:
                vals = []
                for dp in br.findall("datapoint"):
                    parts = (dp.text or "").split(",")
                    try:
                        tt = float(parts[tcol])
                        v = float(parts[col])
                    except (ValueError, IndexError):
                        continue
                    if not math.isnan(v):
                        vals.append((tt, v))
                if vals:
                    if rod_t is not None:
                        s.stability_at_rod = min(vals, key=lambda p: abs(p[0] - rod_t))[1]
                    else:
                        s.stability_at_rod = vals[0][1]
                    # min stability during the powered/coast ascent, ignoring the tail
                    s.min_stability = min(v for _, v in vals[: max(1, len(vals) // 2)])
        r.sims.append(s)
