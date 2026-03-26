"""
app.py - Streamlit UI for the sleeve checker.
"""

from __future__ import annotations

import tempfile
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd
import streamlit as st

from sleeve_checker.parser import parse_dxf
from sleeve_checker.checks import run_all_checks

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="スリーブチェッカー", layout="wide")

# Japanese font for matplotlib
matplotlib.rcParams["font.family"] = "MS Gothic"

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
    "LGS":   st.sidebar.number_input("LGS",   value=150, step=10),
    "ALC":   st.sidebar.number_input("ALC",   value=150, step=10),
    "PCa":   st.sidebar.number_input("PCa",   value=200, step=10),
    "パネル": st.sidebar.number_input("パネル", value=100, step=10),
    "不明":  st.sidebar.number_input("不明",   value=200, step=10),
}

st.sidebar.subheader("#7 段差近接しきい値")
step_threshold_input = st.sidebar.number_input(
    "しきい値 (mm)  ※ 0 = スキップ", value=0, step=50, min_value=0
)
step_threshold = float(step_threshold_input) if step_threshold_input > 0 else None

# ---------------------------------------------------------------------------
# File uploaders
# ---------------------------------------------------------------------------

col_up1, col_up2 = st.columns(2)
with col_up1:
    file_2f = st.file_uploader("2F DXF ファイル (必須)", type=["dxf"])
with col_up2:
    file_1f = st.file_uploader("1F DXF ファイル (任意: #6 下階壁チェック用)", type=["dxf"])

# ---------------------------------------------------------------------------
# Check button
# ---------------------------------------------------------------------------

run_btn = st.button("チェック実行", type="primary", disabled=(file_2f is None))

# ---------------------------------------------------------------------------
# Helper: save upload to temp file, parse, delete
# ---------------------------------------------------------------------------

def _parse_uploaded(uploaded_file) -> "FloorData":
    suffix = ".dxf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
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
# Main logic after button press
# ---------------------------------------------------------------------------

if run_btn and file_2f is not None:

    # --- Parse 2F ---
    with st.spinner("2F DXF を解析中… (最大 20 秒かかる場合があります)"):
        floor_2f = _parse_uploaded(file_2f)

    # --- Parse 1F (optional) ---
    floor_1f = None
    if file_1f is not None:
        with st.spinner("1F DXF を解析中… (最大 20 秒かかる場合があります)"):
            floor_1f = _parse_uploaded(file_1f)

    # --- Run checks ---
    with st.spinner("チェック実行中…"):
        results = run_all_checks(
            floor_2f,
            floor_1f=floor_1f,
            wall_thickness=wall_thickness,
            step_threshold=step_threshold,
        )

    # -----------------------------------------------------------------------
    # Results summary
    # -----------------------------------------------------------------------

    ng_count      = sum(1 for r in results if r.severity == "NG")
    warning_count = sum(1 for r in results if r.severity == "WARNING")
    ok_count      = sum(1 for r in results if r.severity == "OK")

    m1, m2, m3 = st.columns(3)
    m1.metric("NG",      ng_count)
    m2.metric("WARNING", warning_count)
    m3.metric("OK",      ok_count)

    # -----------------------------------------------------------------------
    # Determine worst severity per sleeve for drawing
    # -----------------------------------------------------------------------

    sleeve_worst: dict[str, str] = {}
    for r in results:
        if r.sleeve:
            sid = r.sleeve.id
            if sid not in sleeve_worst:
                sleeve_worst[sid] = r.severity
            elif r.severity == "NG":
                sleeve_worst[sid] = "NG"
            elif sleeve_worst[sid] != "NG" and r.severity == "WARNING":
                sleeve_worst[sid] = "WARNING"

    _COLOR_MAP = {"NG": "red", "WARNING": "orange", "OK": "green"}

    # -----------------------------------------------------------------------
    # Drawing view (matplotlib)
    # -----------------------------------------------------------------------

    st.subheader("図面ビュー")

    fig, ax = plt.subplots(figsize=(16, 8))

    # Grid lines — light gray dashed
    for gl in floor_2f.grid_lines:
        if gl.direction == "V":
            ax.axvline(gl.position, color="lightgray", linewidth=0.5, linestyle="--")
        else:
            ax.axhline(gl.position, color="lightgray", linewidth=0.5, linestyle="--")

    # Wall lines — gray thin
    for wl in floor_2f.wall_lines:
        ax.plot(
            [wl.start[0], wl.end[0]],
            [wl.start[1], wl.end[1]],
            color="gray",
            linewidth=0.5,
        )

    # Sleeves — circles colored by worst severity
    for sleeve in floor_2f.sleeves:
        worst = sleeve_worst.get(sleeve.id, "OK")
        color = _COLOR_MAP[worst]
        radius = sleeve.diameter / 2.0 if sleeve.diameter > 0 else 50.0
        circle = mpatches.Circle(
            sleeve.center,
            radius=radius,
            edgecolor=color,
            facecolor="none",
            linewidth=0.8,
        )
        ax.add_patch(circle)

        # P-N number annotation
        label = sleeve.pn_number or sleeve.id or ""
        ax.annotate(
            label,
            xy=sleeve.center,
            fontsize=4,
            ha="center",
            va="center",
            color=color,
        )

    ax.set_aspect("equal")
    ax.set_xlim(-5000, 85000)
    ax.set_ylim(-5000, 40000)
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")

    # Legend
    legend_handles = [
        mpatches.Patch(edgecolor="red",    facecolor="none", label="NG"),
        mpatches.Patch(edgecolor="orange", facecolor="none", label="WARNING"),
        mpatches.Patch(edgecolor="green",  facecolor="none", label="OK"),
    ]
    ax.legend(handles=legend_handles, loc="upper right", fontsize=6)

    st.pyplot(fig)
    plt.close(fig)

    # -----------------------------------------------------------------------
    # Results table
    # -----------------------------------------------------------------------

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

    # Color rows by severity
    def _style_severity(val: str) -> str:
        if val == "NG":
            return "background-color: #ffcccc"
        if val == "WARNING":
            return "background-color: #fff0cc"
        if val == "OK":
            return "background-color: #ccffcc"
        return ""

    styled = df.style.applymap(_style_severity, subset=["結果"])
    st.dataframe(styled, use_container_width=True)
