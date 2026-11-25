import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pytest
import make_fixtures as fx
from ork2sw.ork import parse
from ork2sw.params import build_params, equations_text
from ork2sw.checks import run_checks, ERROR


def codes(findings, level=ERROR):
    return {f.code for f in findings if f.level == level}


def test_single_tube_params():
    r = parse(fx.ork().encode())
    p = build_params(r).as_dict()
    assert p["middleBreak"] == 0
    assert p["bodyOD"] == pytest.approx(3.1) and p["bodyID"] == pytest.approx(3.0)
    assert p["finCanLength"] == pytest.approx(36)
    assert p["motorTubeOD"] == pytest.approx(1.62) and p["motorTubeLength"] == pytest.approx(12)
    assert p["rootChord"] == pytest.approx(6) and p["finSpan"] == pytest.approx(3.5)
    assert p["finCount"] == 4 and p["finAftOffset"] == pytest.approx(0)
    assert p["topRingFromMotorAft"] == pytest.approx(11.75)
    assert not codes(run_checks(r))


def test_middle_break_params():
    r = parse(fx.ork(break_=True).encode())
    p = build_params(r).as_dict()
    assert p["middleBreak"] == 1
    assert p["upperTubeLength"] == pytest.approx(30) and p["finCanLength"] == pytest.approx(24)
    assert p["couplerLength"] == pytest.approx(6) and p["couplerIntoFinCan"] == pytest.approx(3)
    assert p["couplerOD"] == pytest.approx(3.0)
    assert p["bulkheadThickness"] == pytest.approx(0.25)
    assert not codes(run_checks(r))


def test_bad_design_caught():
    r = parse(fx.ork(chute_event="ejection", stab=0.7, ghv=11.0).encode())
    c = codes(run_checks(r))
    assert {"recovery.apogee", "sim.stability", "sim.groundhit"} <= c


def test_zipped_file(tmp_path):
    p = fx.write("tmp_test.ork", fx.ork())
    try:
        assert parse(p).name == "Test L1"
    finally:
        os.remove(p)


def test_equations_format():
    txt = equations_text(build_params(parse(fx.ork().encode())))
    assert '"bodyOD"= 3.1in' in txt and '"finCount"= 4' in txt
