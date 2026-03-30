"""
tests/test_checks.py - Unit tests for sleeve_checker/checks.py.

All checks are tested with mock data (no DXF files required), plus an
integration test against the real DXF output files.
"""

from __future__ import annotations

import os
import pytest

from sleeve_checker.models import (
    CheckResult,
    ColumnLine,
    DimLine,
    FloorData,
    GridLine,
    Sleeve,
    StepLine,
    WallLine,
)
from sleeve_checker.checks import (
    check_position_determinacy,
    check_column_wall_dim,
    check_diameter_label,
    check_dim_notation,
    check_dim_sum,
    check_discipline,
    check_fl_label,
    check_gradient,
    check_lower_wall,
    check_sleeve_center_dim,
    check_sleeve_number,
    check_step_dim,
    check_step_slab,
    run_all_checks,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_sleeve(**kwargs) -> Sleeve:
    defaults = dict(
        id="test",
        center=(0, 0),
        diameter=100,
        layer="[衛生]スリーブ",
        discipline="衛生",
    )
    defaults.update(kwargs)
    return Sleeve(**defaults)


def _first(results: list[CheckResult]) -> CheckResult:
    assert results, "Expected at least one result"
    return results[0]


# ---------------------------------------------------------------------------
# #2 check_discipline
# ---------------------------------------------------------------------------

class TestCheckDiscipline:
    def test_ok_has_label(self):
        s = _make_sleeve(label_text="SD φ100")
        r = _first(check_discipline(s))
        assert r.severity == "OK"
        assert r.check_id == 2

    def test_ng_no_label(self):
        s = _make_sleeve(label_text=None)
        r = _first(check_discipline(s))
        assert r.severity == "NG"

    def test_ng_empty_label(self):
        s = _make_sleeve(label_text="   ")
        r = _first(check_discipline(s))
        assert r.severity == "NG"


# ---------------------------------------------------------------------------
# #3 check_diameter_label
# ---------------------------------------------------------------------------

class TestCheckDiameterLabel:
    def test_ok_phi_prefix(self):
        s = _make_sleeve(label_text="φ150")
        r = _first(check_diameter_label(s))
        assert r.severity == "OK"

    def test_ok_phi_suffix(self):
        s = _make_sleeve(label_text="150φ")
        r = _first(check_diameter_label(s))
        assert r.severity == "OK"

    def test_ok_upper_phi(self):
        s = _make_sleeve(label_text="Φ200")
        r = _first(check_diameter_label(s))
        assert r.severity == "OK"

    def test_ok_with_space(self):
        s = _make_sleeve(label_text="φ 100")
        r = _first(check_diameter_label(s))
        assert r.severity == "OK"

    def test_ng_no_phi(self):
        s = _make_sleeve(label_text="150mm")
        r = _first(check_diameter_label(s))
        assert r.severity == "NG"

    def test_ng_none_label(self):
        s = _make_sleeve(label_text=None)
        r = _first(check_diameter_label(s))
        assert r.severity == "NG"


# ---------------------------------------------------------------------------
# #5 check_gradient
# ---------------------------------------------------------------------------

class TestCheckGradient:
    def test_ok_non_drain(self):
        s = _make_sleeve(label_text="CW φ100")
        r = _first(check_gradient(s))
        assert r.severity == "OK"

    def test_ok_drain_with_fl(self):
        s = _make_sleeve(label_text="SD φ100", fl_text="FL-300")
        r = _first(check_gradient(s))
        assert r.severity == "OK"

    def test_ok_drain_with_gradient_in_label(self):
        s = _make_sleeve(label_text="RD φ50 1/50")
        r = _first(check_gradient(s))
        assert r.severity == "OK"

    def test_warning_drain_no_fl(self):
        s = _make_sleeve(label_text="SD φ100", fl_text=None)
        r = _first(check_gradient(s))
        assert r.severity == "WARNING"

    def test_warning_japanese_drain_no_fl(self):
        s = _make_sleeve(label_text="排水 φ100")
        r = _first(check_gradient(s))
        assert r.severity == "WARNING"

    def test_ok_non_drain_no_fl(self):
        # Non-drain: no FL needed
        s = _make_sleeve(label_text="給水 φ75")
        r = _first(check_gradient(s))
        assert r.severity == "OK"


# ---------------------------------------------------------------------------
# #8 check_fl_label
# ---------------------------------------------------------------------------

class TestCheckFlLabel:
    def test_ok_fl_minus(self):
        s = _make_sleeve(fl_text="FL-750")
        r = _first(check_fl_label(s))
        assert r.severity == "OK"

    def test_ok_fl_plus(self):
        s = _make_sleeve(fl_text="FL+100")
        r = _first(check_fl_label(s))
        assert r.severity == "OK"

    def test_ok_fl_with_spaces(self):
        s = _make_sleeve(fl_text="FL - 300")
        r = _first(check_fl_label(s))
        assert r.severity == "OK"

    def test_ok_fl_plusminus(self):
        s = _make_sleeve(fl_text="FL±0")
        r = _first(check_fl_label(s))
        assert r.severity == "OK"

    def test_ng_missing(self):
        s = _make_sleeve(fl_text=None)
        r = _first(check_fl_label(s))
        assert r.severity == "NG"

    def test_ng_wrong_format(self):
        s = _make_sleeve(fl_text="floor level 750")
        r = _first(check_fl_label(s))
        assert r.severity == "NG"


# ---------------------------------------------------------------------------
# #14 check_sleeve_number
# ---------------------------------------------------------------------------

class TestCheckSleeveNumber:
    def test_ok_valid(self):
        s = _make_sleeve(pn_number="P-N-42")
        r = _first(check_sleeve_number(s))
        assert r.severity == "OK"

    def test_ok_triple_digit(self):
        s = _make_sleeve(pn_number="P-N-100")
        r = _first(check_sleeve_number(s))
        assert r.severity == "OK"

    def test_ng_wrong_prefix(self):
        s = _make_sleeve(pn_number="S-N-1")
        r = _first(check_sleeve_number(s))
        assert r.severity == "NG"

    def test_ng_none(self):
        s = _make_sleeve(pn_number=None)
        r = _first(check_sleeve_number(s))
        assert r.severity == "NG"

    def test_ng_partial_match(self):
        # fullmatch should reject partial strings
        s = _make_sleeve(pn_number="P-N-5-extra")
        r = _first(check_sleeve_number(s))
        assert r.severity == "NG"


# ---------------------------------------------------------------------------
# #6 check_lower_wall
# ---------------------------------------------------------------------------

class TestCheckLowerWall:
    def _make_wall(self, start, end, wtype="LGS"):
        return WallLine(start=start, end=end, layer="test", wall_type=wtype)

    def test_ok_far_wall(self):
        s = _make_sleeve(center=(0, 0), diameter=100)
        wall = self._make_wall((5000, 0), (5000, 1000), "LGS")
        results = check_lower_wall(s, [wall])
        assert all(r.severity == "OK" for r in results)

    def test_ng_close_wall_lgs(self):
        # sleeve at (0,0), diameter=100 → radius=50
        # LGS thickness=150 → threshold = 50 + 75 = 125
        # Wall at x=50 (horizontal) → distance = 50 < 125
        s = _make_sleeve(center=(0, 0), diameter=100)
        wall = self._make_wall((50, -500), (50, 500), "LGS")
        results = check_lower_wall(s, [wall])
        ng_results = [r for r in results if r.severity == "NG"]
        assert len(ng_results) >= 1

    def test_ng_close_rc_wall(self):
        # RC: threshold = diameter/2 = 50
        # Wall at x=30 → distance = 30 < 50
        s = _make_sleeve(center=(0, 0), diameter=100)
        wall = self._make_wall((30, -500), (30, 500), "RC壁")
        results = check_lower_wall(s, [wall])
        ng_results = [r for r in results if r.severity == "NG"]
        assert len(ng_results) >= 1

    def test_ok_no_walls(self):
        s = _make_sleeve(center=(0, 0), diameter=100)
        results = check_lower_wall(s, [])
        assert _first(results).severity == "OK"

    def test_ok_rc_wall_outside_threshold(self):
        # RC: threshold = 50, wall at x=100 → dist=100 > 50 → OK
        s = _make_sleeve(center=(0, 0), diameter=100)
        wall = self._make_wall((100, -500), (100, 500), "RC壁")
        results = check_lower_wall(s, [wall])
        assert all(r.severity == "OK" for r in results)


# ---------------------------------------------------------------------------
# #7 check_step_slab
# ---------------------------------------------------------------------------

class TestCheckStepSlab:
    def _make_step(self, start, end):
        return StepLine(start=start, end=end)

    def test_ok_no_threshold(self):
        s = _make_sleeve(center=(0, 0))
        r = _first(check_step_slab(s, [], None))
        assert r.severity == "OK"
        assert "スキップ" in r.message

    def test_ok_far_step(self):
        s = _make_sleeve(center=(0, 0))
        step = self._make_step((5000, 0), (5000, 1000))
        results = check_step_slab(s, [step], threshold=300.0)
        assert all(r.severity == "OK" for r in results)

    def test_warning_close_step(self):
        # sleeve at (0,0), step at x=100, threshold=300 → dist=100 < 300
        s = _make_sleeve(center=(0, 0))
        step = self._make_step((100, -500), (100, 500))
        results = check_step_slab(s, [step], threshold=300.0)
        warn = [r for r in results if r.severity == "WARNING"]
        assert len(warn) >= 1

    def test_ok_empty_steps_with_threshold(self):
        s = _make_sleeve(center=(0, 0))
        results = check_step_slab(s, [], threshold=300.0)
        assert all(r.severity == "OK" for r in results)


# ---------------------------------------------------------------------------
# #10 check_step_dim
# ---------------------------------------------------------------------------

class TestCheckStepDim:
    def _make_dim(self, dp1, dp2, dp3=None):
        return DimLine(layer="test", measurement=500.0, defpoint1=dp1, defpoint2=dp2,
                       defpoint3=dp3 if dp3 else (0.0, 0.0))

    def _make_step(self, start, end):
        return StepLine(start=start, end=end)

    def test_ok_not_on_step(self):
        sleeve = _make_sleeve(id="s1", center=(500, 0))
        dim = self._make_dim((0, 100), (0, 0), (500, 0))  # dp3 near sleeve, not on step
        step = self._make_step((1000, -500), (1000, 500))
        r = _first(check_step_dim(sleeve, [dim], [step]))
        assert r.severity == "OK"

    def test_ng_on_step(self):
        # dp2=(500, 0) matches sleeve centre AND lies on step line
        sleeve = _make_sleeve(id="s1", center=(500, 0))
        dim = self._make_dim((0, 100), (500, 0), (0, 0))  # dp2 near sleeve, on step
        step = self._make_step((500, -500), (500, 500))
        r = _first(check_step_dim(sleeve, [dim], [step]))
        assert r.severity == "NG"

    def test_ok_no_steps(self):
        sleeve = _make_sleeve(id="s1", center=(500, 0))
        dim = self._make_dim((0, 100), (500, 0), (0, 0))
        r = _first(check_step_dim(sleeve, [dim], []))
        assert r.severity == "OK"


# ---------------------------------------------------------------------------
# #11 check_sleeve_center_dim
# ---------------------------------------------------------------------------

class TestCheckSleeveCenterDim:
    def _make_dim(self, dp1, dp2):
        return DimLine(layer="test", measurement=500.0, defpoint1=dp1, defpoint2=dp2)

    def test_ok_no_match(self):
        s1 = _make_sleeve(id="s1", center=(0, 0))
        s2 = _make_sleeve(id="s2", center=(500, 0))
        dim = self._make_dim((100, 100), (400, 100))  # doesn't hit centers
        r = _first(check_sleeve_center_dim(dim, [s1, s2]))
        assert r.severity == "OK"

    def test_ng_spans_two_centers(self):
        s1 = _make_sleeve(id="s1", center=(0, 0))
        s2 = _make_sleeve(id="s2", center=(500, 0))
        dim = self._make_dim((0, 0), (500, 0))
        r = _first(check_sleeve_center_dim(dim, [s1, s2]))
        assert r.severity == "NG"

    def test_ok_only_one_center_match(self):
        s1 = _make_sleeve(id="s1", center=(0, 0))
        s2 = _make_sleeve(id="s2", center=(500, 0))
        dim = self._make_dim((0, 0), (250, 0))  # dp1 matches s1, dp2 matches nothing
        r = _first(check_sleeve_center_dim(dim, [s1, s2]))
        assert r.severity == "OK"

    def test_ok_empty_sleeves(self):
        dim = self._make_dim((0, 0), (500, 0))
        r = _first(check_sleeve_center_dim(dim, []))
        assert r.severity == "OK"


# ---------------------------------------------------------------------------
# #12 check_column_wall_dim
# ---------------------------------------------------------------------------

class TestCheckColumnWallDim:
    def _make_dim(self, dp1, dp2):
        return DimLine(layer="test", measurement=500.0, defpoint1=dp1, defpoint2=dp2)

    def _make_col(self, start, end):
        return ColumnLine(start=start, end=end)

    def test_ok_not_on_column(self):
        dim = self._make_dim((0, 0), (500, 0))
        col = self._make_col((1000, -500), (1000, 500))
        r = _first(check_column_wall_dim(dim, [col]))
        assert r.severity == "OK"

    def test_ng_on_column(self):
        # defpoint1=(500, 0) on vertical column line x=500
        dim = self._make_dim((500, 0), (1000, 0))
        col = self._make_col((500, -500), (500, 500))
        r = _first(check_column_wall_dim(dim, [col]))
        assert r.severity == "NG"

    def test_ok_no_columns(self):
        dim = self._make_dim((0, 0), (500, 0))
        r = _first(check_column_wall_dim(dim, []))
        assert r.severity == "OK"


# ---------------------------------------------------------------------------
# #4 check_dim_sum
# ---------------------------------------------------------------------------

class TestCheckDimSum:
    def test_ok_sums_match(self):
        # Two V grids at X=0 and X=1000 (span=1000)
        # Chain: 0→400 (400mm) + 400→1000 (600mm) = 1000
        grids = [
            GridLine(axis_label="A", direction="V", position=0),
            GridLine(axis_label="B", direction="V", position=1000),
        ]
        dims = [
            DimLine(layer="t", measurement=400.0,
                    defpoint1=(400, 500), defpoint2=(0, 500), defpoint3=(400, 500)),
            DimLine(layer="t", measurement=600.0,
                    defpoint1=(1000, 500), defpoint2=(400, 500), defpoint3=(1000, 500)),
        ]
        results = check_dim_sum(dims, grids)
        ok_results = [r for r in results if r.severity == "OK"]
        assert len(ok_results) >= 1

    def test_ng_sums_dont_match(self):
        # Two V grids at X=0 and X=1000 (span=1000)
        # Chain: 0→400 (400mm) + 400→900 (500mm) = 900 ≠ 1000
        grids = [
            GridLine(axis_label="A", direction="V", position=0),
            GridLine(axis_label="B", direction="V", position=1000),
        ]
        dims = [
            DimLine(layer="t", measurement=400.0,
                    defpoint1=(400, 500), defpoint2=(0, 500), defpoint3=(400, 500)),
            DimLine(layer="t", measurement=500.0,
                    defpoint1=(900, 500), defpoint2=(400, 500), defpoint3=(900, 500)),
        ]
        results = check_dim_sum(dims, grids)
        ng_results = [r for r in results if r.severity == "NG"]
        assert len(ng_results) >= 1

    def test_ok_no_grids(self):
        dims = [DimLine(layer="t", measurement=500.0,
                        defpoint1=(500, 0), defpoint2=(0, 0), defpoint3=(500, 0))]
        results = check_dim_sum(dims, [])
        ng_results = [r for r in results if r.severity == "NG"]
        assert len(ng_results) == 0


# ---------------------------------------------------------------------------
# #9 check_position_determinacy
# ---------------------------------------------------------------------------

class TestCheckPositionDeterminacy:
    def test_ok_grid_to_sleeve_both_axes(self):
        # Sleeve at (500, 500); grids at x=0 (V) and y=0 (H)
        s = _make_sleeve(id="s1", center=(500, 500))
        grids = [
            GridLine(axis_label="A", direction="V", position=0),
            GridLine(axis_label="1", direction="H", position=0),
        ]
        # Horizontal dim: grid x=0 → sleeve x=500
        # Vertical dim: grid y=0 → sleeve y=500
        dims = [
            DimLine(layer="t", measurement=500.0, defpoint1=(250, 600),
                    defpoint2=(0, 500), defpoint3=(500, 500), angle=0),
            DimLine(layer="t", measurement=500.0, defpoint1=(600, 250),
                    defpoint2=(500, 0), defpoint3=(500, 500), angle=90),
        ]
        results = check_position_determinacy([s], dims, grids, sleeve_margin=50.0, grid_tolerance=10.0)
        assert len(results) == 1
        assert results[0].severity == "OK"

    def test_ng_missing_y(self):
        # Only X dim, no Y dim
        s = _make_sleeve(id="s1", center=(500, 500))
        grids = [
            GridLine(axis_label="A", direction="V", position=0),
            GridLine(axis_label="1", direction="H", position=0),
        ]
        dims = [
            DimLine(layer="t", measurement=500.0, defpoint1=(250, 600),
                    defpoint2=(0, 500), defpoint3=(500, 500), angle=0),
        ]
        results = check_position_determinacy([s], dims, grids, sleeve_margin=50.0, grid_tolerance=10.0)
        assert results[0].severity == "NG"
        assert "Y" in results[0].message

    def test_ok_chain_via_inter_sleeve(self):
        # s1 has grid dim, s2 linked to s1 via inter-sleeve dim
        s1 = _make_sleeve(id="s1", center=(500, 500))
        s2 = _make_sleeve(id="s2", center=(1000, 500))
        grids = [
            GridLine(axis_label="A", direction="V", position=0),
            GridLine(axis_label="1", direction="H", position=0),
        ]
        dims = [
            # s1: grid→sleeve X
            DimLine(layer="t", measurement=500.0, defpoint1=(250, 600),
                    defpoint2=(0, 500), defpoint3=(500, 500), angle=0),
            # s1: grid→sleeve Y
            DimLine(layer="t", measurement=500.0, defpoint1=(600, 250),
                    defpoint2=(500, 0), defpoint3=(500, 500), angle=90),
            # s1↔s2 inter-sleeve X
            DimLine(layer="t", measurement=500.0, defpoint1=(750, 600),
                    defpoint2=(500, 500), defpoint3=(1000, 500), angle=0),
            # s2: grid→sleeve Y
            DimLine(layer="t", measurement=500.0, defpoint1=(1100, 250),
                    defpoint2=(1000, 0), defpoint3=(1000, 500), angle=90),
        ]
        results = check_position_determinacy([s1, s2], dims, grids, sleeve_margin=50.0, grid_tolerance=10.0)
        assert all(r.severity == "OK" for r in results)

    def test_ok_no_grids(self):
        s = _make_sleeve(id="s1", center=(500, 500))
        dims = [DimLine(layer="t", measurement=500.0, defpoint1=(0, 500), defpoint2=(500, 500))]
        results = check_position_determinacy([s], dims, [])
        assert all(r.severity == "OK" for r in results)


# ---------------------------------------------------------------------------
# #13 check_dim_notation
# ---------------------------------------------------------------------------

class TestCheckDimNotation:
    def test_ok_uniform_plain(self):
        dims = [
            DimLine(layer="t", measurement=500.0, defpoint1=(0, 0), defpoint2=(500, 0), text_override="500"),
            DimLine(layer="t", measurement=300.0, defpoint1=(0, 0), defpoint2=(300, 0), text_override="300"),
        ]
        r = _first(check_dim_notation(dims))
        assert r.severity == "OK"

    def test_ok_uniform_mm_suffix(self):
        dims = [
            DimLine(layer="t", measurement=500.0, defpoint1=(0, 0), defpoint2=(500, 0), text_override="500mm"),
            DimLine(layer="t", measurement=300.0, defpoint1=(0, 0), defpoint2=(300, 0), text_override="300mm"),
        ]
        r = _first(check_dim_notation(dims))
        assert r.severity == "OK"

    def test_warning_mixed_notation(self):
        dims = [
            DimLine(layer="t", measurement=500.0, defpoint1=(0, 0), defpoint2=(500, 0), text_override="500"),
            DimLine(layer="t", measurement=300.0, defpoint1=(0, 0), defpoint2=(300, 0), text_override="300mm"),
        ]
        r = _first(check_dim_notation(dims))
        assert r.severity == "WARNING"

    def test_ok_no_overrides(self):
        dims = [
            DimLine(layer="t", measurement=500.0, defpoint1=(0, 0), defpoint2=(500, 0)),
        ]
        r = _first(check_dim_notation(dims))
        assert r.severity == "OK"


# ---------------------------------------------------------------------------
# run_all_checks smoke test (mock data)
# ---------------------------------------------------------------------------

class TestRunAllChecks:
    def test_minimal_floor(self):
        """run_all_checks with a single sleeve and no geometry should not crash."""
        s = _make_sleeve(
            id="s1",
            center=(1000, 1000),
            label_text="SD φ100",
            fl_text="FL-300",
            pn_number="P-N-1",
        )
        floor = FloorData(sleeves=[s])
        results = run_all_checks(floor)
        assert len(results) > 0
        # All severities must be valid
        for r in results:
            assert r.severity in ("OK", "NG", "WARNING")

    def test_with_lower_floor(self):
        """run_all_checks with a lower floor wall should trigger #6."""
        s = _make_sleeve(center=(0, 0), diameter=100)
        # Wall very close to sleeve → should be NG for #6
        wall = WallLine(start=(20, -500), end=(20, 500), wall_type="LGS")
        floor_2f = FloorData(sleeves=[s])
        floor_1f = FloorData(wall_lines=[wall])
        results = run_all_checks(floor_2f, floor_1f)
        check6 = [r for r in results if r.check_id == 6]
        assert len(check6) > 0
        assert any(r.severity == "NG" for r in check6)


# ---------------------------------------------------------------------------
# Integration test against real DXF files
# ---------------------------------------------------------------------------

DXF_2F = os.path.join(os.path.dirname(__file__), "..", "dxf_output", "2階床スリーブ図.dxf")
DXF_1F = os.path.join(os.path.dirname(__file__), "..", "dxf_output", "1階床スリーブ図.dxf")


@pytest.mark.skipif(
    not os.path.exists(DXF_2F),
    reason="2F DXF file not found",
)
def test_run_all_checks_no_crash():
    from sleeve_checker.parser import parse_dxf

    floor_2f = parse_dxf(DXF_2F)
    floor_1f = parse_dxf(DXF_1F) if os.path.exists(DXF_1F) else None
    results = run_all_checks(floor_2f, floor_1f)
    assert len(results) > 0
    ng = sum(1 for r in results if r.severity == "NG")
    warn = sum(1 for r in results if r.severity == "WARNING")
    ok = sum(1 for r in results if r.severity == "OK")
    print(f"Results: NG={ng}, WARNING={warn}, OK={ok}, Total={len(results)}")
