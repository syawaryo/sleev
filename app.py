"""
app.py - Streamlit UI for the sleeve checker (plotly version).
"""

from __future__ import annotations

import os
import re
import tempfile
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from sleeve_checker.parser import parse_dxf
from sleeve_checker.checks import run_all_checks
from sleeve_checker.models import FloorData, CheckResult, Sleeve

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="スリーブチェッカー", layout="wide")

# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------

st.title("スリーブチェッカー")

# ---------------------------------------------------------------------------
# Sidebar settings
# ---------------------------------------------------------------------------

st.sidebar.header("設定")

st.sidebar.subheader("壁厚 (mm)")
wall_thickness = {
    "LGS":    st.sidebar.number_input("LGS",    value=150, step=10),
    "ALC":    st.sidebar.number_input("ALC",    value=150, step=10),
    "PCa":    st.sidebar.number_input("PCa",    value=200, step=10),
    "パネル": st.sidebar.number_input("パネル",  value=100, step=10),
    "不明":   st.sidebar.number_input("不明",    value=200, step=10),
}


# ---------------------------------------------------------------------------
# File input section
# ---------------------------------------------------------------------------

use_local = st.checkbox("ローカルファイルを使用 (開発用)", value=False)

if use_local:
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        local_path_2f = st.text_input(
            "2F DXF パス",
            value="dxf_output/2階床スリーブ図.dxf",
        )
    with col_p2:
        local_path_1f = st.text_input(
            "1F DXF パス (任意)",
            value="dxf_output/1階床スリーブ図.dxf",
        )
    file_2f = None
    file_1f = None
    run_btn_disabled = False
else:
    local_path_2f = ""
    local_path_1f = ""
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        file_2f = st.file_uploader("2F DXF ファイル (必須)", type=["dxf"])
    with col_up2:
        file_1f = st.file_uploader("1F DXF ファイル (任意: #6 下階壁チェック用)", type=["dxf"])
    run_btn_disabled = file_2f is None

# ---------------------------------------------------------------------------
# Check button
# ---------------------------------------------------------------------------

run_btn = st.button("チェック実行", type="primary", disabled=run_btn_disabled)

# ---------------------------------------------------------------------------
# Helper: parse a file — either from upload or local path
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _parse_local(path: str) -> FloorData:
    return parse_dxf(path)


def _parse_uploaded(uploaded_file) -> FloorData:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name
    try:
        floor_data = parse_dxf(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return floor_data


# ---------------------------------------------------------------------------
# Run checks on button press — store in session_state
# ---------------------------------------------------------------------------

if run_btn:
    # --- 2F ---
    with st.spinner("2F DXF を解析中… (最大 20 秒かかる場合があります)"):
        if use_local:
            floor_2f_data = _parse_local(local_path_2f)
        else:
            floor_2f_data = _parse_uploaded(file_2f)
    st.session_state["floor_2f"] = floor_2f_data

    # --- 1F (optional) ---
    floor_1f_data: Optional[FloorData] = None
    if use_local and local_path_1f.strip():
        with st.spinner("1F DXF を解析中… (最大 20 秒かかる場合があります)"):
            try:
                floor_1f_data = _parse_local(local_path_1f)
            except Exception as e:
                st.warning(f"1F DXF 読み込みエラー (スキップ): {e}")
    elif not use_local and file_1f is not None:
        with st.spinner("1F DXF を解析中… (最大 20 秒かかる場合があります)"):
            floor_1f_data = _parse_uploaded(file_1f)
    st.session_state["floor_1f"] = floor_1f_data

    # --- Run checks ---
    with st.spinner("チェック実行中…"):
        results = run_all_checks(
            floor_2f_data,
            floor_1f=floor_1f_data,
            wall_thickness=wall_thickness,
        )
    st.session_state["results"] = results

# ---------------------------------------------------------------------------
# Display results if available in session_state
# ---------------------------------------------------------------------------

if "results" not in st.session_state:
    st.info("DXF ファイルを指定して「チェック実行」ボタンを押してください。")
    st.stop()

results: list[CheckResult] = st.session_state["results"]
floor_2f: FloorData = st.session_state["floor_2f"]
floor_1f: Optional[FloorData] = st.session_state.get("floor_1f")

# ---------------------------------------------------------------------------
# Results summary metrics
# ---------------------------------------------------------------------------

ng_count      = sum(1 for r in results if r.severity == "NG")
warning_count = sum(1 for r in results if r.severity == "WARNING")
ok_count      = sum(1 for r in results if r.severity == "OK")

m1, m2, m3 = st.columns(3)
m1.metric("NG",      ng_count)
m2.metric("WARNING", warning_count)
m3.metric("OK",      ok_count)

# ---------------------------------------------------------------------------
# Determine worst severity per sleeve
# ---------------------------------------------------------------------------

sleeve_worst: dict[str, str] = {}
sleeve_results: dict[str, list[CheckResult]] = {}

for r in results:
    if r.sleeve:
        sid = r.sleeve.id
        # Accumulate all results per sleeve
        sleeve_results.setdefault(sid, []).append(r)
        # Track worst severity
        if sid not in sleeve_worst:
            sleeve_worst[sid] = r.severity
        elif r.severity == "NG":
            sleeve_worst[sid] = "NG"
        elif sleeve_worst[sid] != "NG" and r.severity == "WARNING":
            sleeve_worst[sid] = "WARNING"

_SEVERITY_ORDER = {"NG": 0, "WARNING": 1, "OK": 2}

# Bucket sleeves by worst severity
sleeves_by_sev: dict[str, list[Sleeve]] = {"NG": [], "WARNING": [], "OK": []}
for sleeve in floor_2f.sleeves:
    worst = sleeve_worst.get(sleeve.id, "OK")
    sleeves_by_sev[worst].append(sleeve)

# ---------------------------------------------------------------------------
# Hover text builder
# ---------------------------------------------------------------------------

def _make_hover(sleeve: Sleeve) -> str:
    lines = [
        f"<b>{sleeve.pn_number or sleeve.id}</b>",
        f"径: {sleeve.diameter:.0f} mm" if sleeve.diameter > 0 else "径: 不明",
        f"ラベル: {sleeve.label_text or '—'}",
        f"口径: {sleeve.diameter_text or '—'}",
        f"FL: {sleeve.fl_text or '—'}",
    ]
    # Append check results for this sleeve
    for r in sleeve_results.get(sleeve.id, []):
        icon = "🔴" if r.severity == "NG" else ("🟠" if r.severity == "WARNING" else "🟢")
        lines.append(f"{icon} #{r.check_id} {r.check_name}: {r.message}")
    return "<br>".join(lines)

# ---------------------------------------------------------------------------
# Plotly figure builder
# ---------------------------------------------------------------------------

_COLOR_SLEEVE = {"NG": "red", "WARNING": "orange", "OK": "green"}

_DEFAULT_RANGE_X = (-5000, 85000)
_DEFAULT_RANGE_Y = (-5000, 40000)


def _add_grid_traces(fig: go.Figure, floor: FloorData, showlegend: bool = True) -> None:
    """Add 通り芯 (grid line) traces."""
    first = True
    for gl in floor.grid_lines:
        if gl.direction == "V":
            xs = [gl.position, gl.position]
            ys = list(_DEFAULT_RANGE_Y)
        else:
            xs = list(_DEFAULT_RANGE_X)
            ys = [gl.position, gl.position]
        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="lines",
            line=dict(color="lightgray", dash="dash", width=0.5),
            name="通り芯",
            legendgroup="grid",
            showlegend=(showlegend and first),
            hoverinfo="skip",
        ))
        first = False


def _add_wall_traces(fig: go.Figure, floor: FloorData, name: str = "壁線",
                     color: str = "gray", showlegend: bool = True) -> None:
    """Add wall line traces (one trace per wall for performance; batch via None gaps)."""
    xs: list[Optional[float]] = []
    ys: list[Optional[float]] = []
    for wl in floor.wall_lines:
        xs += [wl.start[0], wl.end[0], None]
        ys += [wl.start[1], wl.end[1], None]
    if xs:
        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="lines",
            line=dict(color=color, width=0.5),
            name=name,
            legendgroup=name,
            showlegend=showlegend,
            hoverinfo="skip",
        ))


def _add_step_traces(fig: go.Figure, floor: FloorData, showlegend: bool = True) -> None:
    """Add 段差線 traces."""
    xs: list[Optional[float]] = []
    ys: list[Optional[float]] = []
    for sl in floor.step_lines:
        xs += [sl.start[0], sl.end[0], None]
        ys += [sl.start[1], sl.end[1], None]
    if xs:
        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="lines",
            line=dict(color="#a0522d", width=1.2),  # brown/sienna
            name="段差線",
            legendgroup="step",
            showlegend=showlegend,
            hoverinfo="skip",
        ))


def _add_sleeve_traces(
    fig: go.Figure,
    sleeves: list[Sleeve],
    severity: str,
    custom_hover: Optional[list[str]] = None,
    showlegend: bool = True,
) -> None:
    """Add sleeve scatter traces for a given severity bucket."""
    if not sleeves:
        return
    color = _COLOR_SLEEVE[severity]
    hover = custom_hover if custom_hover is not None else [_make_hover(s) for s in sleeves]
    fig.add_trace(go.Scatter(
        x=[s.center[0] for s in sleeves],
        y=[s.center[1] for s in sleeves],
        mode="markers+text",
        marker=dict(
            size=10,
            color="rgba(0,0,0,0)",  # transparent fill
            symbol="circle",
            line=dict(color=color, width=2),
        ),
        text=[s.pn_number or s.id or "" for s in sleeves],
        textfont=dict(size=7, color=color),
        textposition="top center",
        hovertext=hover,
        hoverinfo="text",
        name=f"スリーブ {severity}",
        legendgroup=f"sleeve_{severity}",
        showlegend=showlegend,
    ))


def _base_layout() -> dict:
    return dict(
        height=800,
        yaxis=dict(
            scaleanchor="x",
            scaleratio=1,
            range=list(_DEFAULT_RANGE_Y),
        ),
        xaxis=dict(range=list(_DEFAULT_RANGE_X)),
        legend=dict(orientation="h", y=-0.05),
        margin=dict(l=40, r=20, t=40, b=60),
        hovermode="closest",
    )


# ---------------------------------------------------------------------------
# View: 全体ビュー
# ---------------------------------------------------------------------------

def build_overview_fig() -> go.Figure:
    fig = go.Figure()
    _add_grid_traces(fig, floor_2f)
    _add_wall_traces(fig, floor_2f)
    if floor_2f.step_lines:
        _add_step_traces(fig, floor_2f)
    for sev in ("NG", "WARNING", "OK"):
        _add_sleeve_traces(fig, sleeves_by_sev[sev], sev)
    fig.update_layout(title="全体ビュー", **_base_layout())
    return fig


# ---------------------------------------------------------------------------
# View: #6 下階壁干渉
# ---------------------------------------------------------------------------

def build_check6_fig() -> go.Figure:
    fig = go.Figure()
    _add_grid_traces(fig, floor_2f)
    if floor_1f is not None:
        _add_wall_traces(fig, floor_1f, name="1F 壁線", color="#6666aa")
    _add_wall_traces(fig, floor_2f, name="2F 壁線")

    # Classify sleeves by #6 result
    sev6: dict[str, str] = {}
    for r in results:
        if r.check_id == 6 and r.sleeve:
            sid = r.sleeve.id
            if sid not in sev6:
                sev6[sid] = r.severity
            elif r.severity == "NG":
                sev6[sid] = "NG"

    by_sev: dict[str, list[Sleeve]] = {"NG": [], "WARNING": [], "OK": []}
    for s in floor_2f.sleeves:
        by_sev[sev6.get(s.id, "OK")].append(s)

    for sev in ("NG", "WARNING", "OK"):
        _add_sleeve_traces(fig, by_sev[sev], sev)

    fig.update_layout(title="#6 下階壁干渉チェック", **_base_layout())
    return fig


# ---------------------------------------------------------------------------
# View: #7 段差スラブ
# ---------------------------------------------------------------------------

def build_check7_fig() -> go.Figure:
    fig = go.Figure()
    _add_grid_traces(fig, floor_2f)
    _add_step_traces(fig, floor_2f)

    sev7: dict[str, str] = {}
    for r in results:
        if r.check_id == 7 and r.sleeve:
            sid = r.sleeve.id
            if sid not in sev7:
                sev7[sid] = r.severity
            elif r.severity == "NG":
                sev7[sid] = "NG"
            elif sev7[sid] != "NG" and r.severity == "WARNING":
                sev7[sid] = "WARNING"

    by_sev: dict[str, list[Sleeve]] = {"NG": [], "WARNING": [], "OK": []}
    for s in floor_2f.sleeves:
        by_sev[sev7.get(s.id, "OK")].append(s)

    for sev in ("NG", "WARNING", "OK"):
        _add_sleeve_traces(fig, by_sev[sev], sev)

    fig.update_layout(title="#7 段差スラブ近接チェック", **_base_layout())
    return fig


# ---------------------------------------------------------------------------
# View: #8 FL情報
# ---------------------------------------------------------------------------

_RE_FL_VALUE = re.compile(r"FL\s*([±+\-])\s*(\d+)", re.IGNORECASE)


def _fl_color(fl_text: Optional[str]) -> str:
    """Map FL offset string to a color for the FL view."""
    if fl_text is None:
        return "gray"
    m = _RE_FL_VALUE.search(fl_text)
    if not m:
        return "gray"
    sign, val_s = m.group(1), m.group(2)
    val = int(val_s)
    if sign == "-":
        val = -val
    if val < -500:
        return "#0000ff"   # deep blue — very low
    if val < 0:
        return "#3399ff"   # light blue — below FL
    if val == 0:
        return "#009900"   # green — at FL
    if val <= 500:
        return "#ff9900"   # orange — slightly above
    return "#cc0000"       # red — very high


def build_check8_fig() -> go.Figure:
    fig = go.Figure()
    _add_grid_traces(fig, floor_2f)
    _add_wall_traces(fig, floor_2f)

    # Group sleeves by FL color
    color_groups: dict[str, list[Sleeve]] = {}
    for s in floor_2f.sleeves:
        c = _fl_color(s.fl_text)
        color_groups.setdefault(c, []).append(s)

    _FL_LABELS = {
        "#0000ff": "FL < -500",
        "#3399ff": "FL -500〜-1",
        "#009900": "FL ±0",
        "#ff9900": "FL +1〜+500",
        "#cc0000": "FL > +500",
        "gray":    "FL 不明",
    }

    for color, sleeves_group in color_groups.items():
        hover = [f"<b>{s.pn_number or s.id}</b><br>FL: {s.fl_text or '—'}" for s in sleeves_group]
        fig.add_trace(go.Scatter(
            x=[s.center[0] for s in sleeves_group],
            y=[s.center[1] for s in sleeves_group],
            mode="markers+text",
            marker=dict(
                size=10,
                color="rgba(0,0,0,0)",
                symbol="circle",
                line=dict(color=color, width=2),
            ),
            text=[s.pn_number or s.id or "" for s in sleeves_group],
            textfont=dict(size=7, color=color),
            textposition="top center",
            hovertext=hover,
            hoverinfo="text",
            name=_FL_LABELS.get(color, color),
            legendgroup=f"fl_{color}",
        ))

    fig.update_layout(title="#8 FL情報ビュー", **_base_layout())
    return fig


# ---------------------------------------------------------------------------
# View: #10-12 寸法基準
# ---------------------------------------------------------------------------

def build_check1012_fig() -> go.Figure:
    fig = go.Figure()
    _add_grid_traces(fig, floor_2f)
    _add_wall_traces(fig, floor_2f)

    # Dimension lines: draw as thin blue lines with markers at defpoints
    xs: list[Optional[float]] = []
    ys: list[Optional[float]] = []
    for dl in floor_2f.dim_lines:
        xs += [dl.defpoint1[0], dl.defpoint2[0], None]
        ys += [dl.defpoint1[1], dl.defpoint2[1], None]
    if xs:
        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="lines",
            line=dict(color="#4488cc", width=0.8),
            name="寸法線",
            legendgroup="dimlines",
            hoverinfo="skip",
        ))

    # Sleeves — color by worst of checks #10, #11, #12
    sev1012: dict[str, str] = {}
    for r in results:
        if r.check_id in (10, 11, 12) and r.sleeve:
            sid = r.sleeve.id
            if sid not in sev1012:
                sev1012[sid] = r.severity
            elif r.severity == "NG":
                sev1012[sid] = "NG"

    by_sev: dict[str, list[Sleeve]] = {"NG": [], "WARNING": [], "OK": []}
    for s in floor_2f.sleeves:
        by_sev[sev1012.get(s.id, "OK")].append(s)

    for sev in ("NG", "WARNING", "OK"):
        _add_sleeve_traces(fig, by_sev[sev], sev)

    fig.update_layout(title="#10-12 寸法基準チェック", **_base_layout())
    return fig


# ---------------------------------------------------------------------------
# Drawing view — tabs
# ---------------------------------------------------------------------------

st.subheader("図面ビュー")

tab_labels = ["全体ビュー", "#6 下階壁干渉", "#7 段差スラブ", "#8 FL情報", "#10-12 寸法基準"]
tabs = st.tabs(tab_labels)

with tabs[0]:
    st.plotly_chart(build_overview_fig(), use_container_width=True)

with tabs[1]:
    if floor_1f is None:
        st.info("1F DXF が読み込まれていません。#6 チェックには 1F DXF が必要です。")
    st.plotly_chart(build_check6_fig(), use_container_width=True)

with tabs[2]:
    if not floor_2f.step_lines:
        st.info("段差線データが見つかりません。")
    st.plotly_chart(build_check7_fig(), use_container_width=True)

with tabs[3]:
    st.plotly_chart(build_check8_fig(), use_container_width=True)

with tabs[4]:
    if not floor_2f.dim_lines:
        st.info("寸法線データが見つかりません。")
    st.plotly_chart(build_check1012_fig(), use_container_width=True)

# ---------------------------------------------------------------------------
# Results table
# ---------------------------------------------------------------------------

st.subheader("チェック結果")

filter_options = ["全て", "NG", "WARNING", "OK"]
selected_filter = st.selectbox("フィルタ", filter_options)

rows = []
for r in results:
    rows.append({
        "チェック#":  r.check_id,
        "チェック名": r.check_name,
        "結果":       r.severity,
        "スリーブ":   r.sleeve.id if r.sleeve else "",
        "径":         r.sleeve.diameter if r.sleeve else "",
        "メッセージ": r.message,
    })

df = pd.DataFrame(rows)

if selected_filter != "全て":
    df = df[df["結果"] == selected_filter]


def _style_severity(val: str) -> str:
    if val == "NG":
        return "background-color: #ffcccc"
    if val == "WARNING":
        return "background-color: #fff0cc"
    if val == "OK":
        return "background-color: #ccffcc"
    return ""


styled = df.style.map(_style_severity, subset=["結果"])
st.dataframe(styled, use_container_width=True)
