import contextlib
import io
import json
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib as mpl
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "population_analysis_assignment_result.ipynb"
FIGURE_DIR = ROOT / "reports" / "figures"


def configure_korean_font():
    candidates = [
        "AppleGothic",
        "Apple SD Gothic Neo",
        "NanumGothic",
        "Nanum Gothic",
        "Noto Sans CJK KR",
        "Noto Sans KR",
        "Malgun Gothic",
        "Arial Unicode MS",
    ]
    available = {font.name for font in fm.fontManager.ttflist}
    for font_name in candidates:
        if font_name in available:
            mpl.rcParams["font.family"] = font_name
            plt.rcParams["font.family"] = font_name
            sns.set_theme(style="whitegrid", font=font_name)
            break
    else:
        sns.set_theme(style="whitegrid")
    plt.rcParams["axes.unicode_minus"] = False


def display(*args, **kwargs):
    return None


def execute_notebook():
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    namespace = {"display": display}
    for index, cell in enumerate(notebook["cells"]):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        if not source.strip():
            continue
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            exec(compile(source, f"notebook_cell_{index}", "exec"), namespace)
        plt.close("all")
    return namespace


def save_current_figure(filename):
    path = FIGURE_DIR / filename
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()
    return path


def make_analysis_flow():
    steps = [
        ("1. 데이터 수집", "KOSIS 최신 자료\n2015~2025"),
        ("2. 정제", "지역·연도·변수\n형태로 통일"),
        ("3. 원자료 분석", "complete-case\n상관분석"),
        ("4. 구조 요약", "PCA/PCR로\n변수 묶음 확인"),
        ("5. 민감도 확인", "보간 결과와\n순위 비교"),
    ]
    fig, ax = plt.subplots(figsize=(13, 3.2))
    ax.axis("off")
    xs = np.linspace(0.08, 0.92, len(steps))
    colors = ["#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e", "#d62728"]
    for idx, ((title, body), x, color) in enumerate(zip(steps, xs, colors)):
        ax.text(
            x,
            0.62,
            title,
            ha="center",
            va="center",
            fontsize=13,
            fontweight="bold",
            color="white",
            bbox=dict(boxstyle="round,pad=0.5", facecolor=color, edgecolor=color),
            transform=ax.transAxes,
        )
        ax.text(x, 0.25, body, ha="center", va="center", fontsize=11, transform=ax.transAxes)
        if idx < len(steps) - 1:
            ax.annotate(
                "",
                xy=(xs[idx + 1] - 0.075, 0.62),
                xytext=(x + 0.075, 0.62),
                arrowprops=dict(arrowstyle="->", color="#444444", lw=1.8),
                xycoords=ax.transAxes,
                textcoords=ax.transAxes,
            )
    ax.set_title("분석 흐름: 원자료 중심 결과와 보간 민감도 비교", fontsize=17, pad=18)
    return save_current_figure("analysis_flow.png")


def make_correlation_heatmap(complete_corr):
    plt.figure(figsize=(11.5, 9.5))
    sns.heatmap(complete_corr, annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1, square=True)
    plt.title("2023년 complete-case 상관계수 행렬", fontsize=16, pad=14)
    return save_current_figure("complete_case_correlation_heatmap.png")


def make_fertility_correlation_bar(complete_corr):
    target_corr = complete_corr["출산율"].drop("출산율").sort_values()
    colors = ["#3b6fb6" if value < 0 else "#c44e52" for value in target_corr]
    plt.figure(figsize=(10, 6.5))
    ax = plt.gca()
    ax.barh(target_corr.index, target_corr.values, color=colors)
    ax.axvline(0, color="#222222", lw=1)
    for y, value in enumerate(target_corr.values):
        x_offset = 0.025 if value >= 0 else -0.025
        ha = "left" if value >= 0 else "right"
        ax.text(value + x_offset, y, f"{value:.2f}", va="center", ha=ha, fontsize=10)
    ax.set_xlim(-0.8, 0.8)
    ax.set_xlabel("출산율과의 상관계수")
    ax.set_title("출산율과 각 요인의 관계 방향", fontsize=16, pad=14)
    return save_current_figure("fertility_correlation_bar.png")


def make_rank_sensitivity(comparison_df):
    df = comparison_df.sort_values("complete_case_rank").copy()
    y_positions = np.arange(len(df))
    plt.figure(figsize=(9.5, 6.5))
    ax = plt.gca()
    for y, row in zip(y_positions, df.itertuples(index=False)):
        ax.plot(
            [row.complete_case_rank, row.imputed_rank],
            [y, y],
            color="#999999",
            lw=1.5,
            zorder=1,
        )
    ax.scatter(df["complete_case_rank"], y_positions, label="complete-case", color="#1f77b4", s=60, zorder=2)
    ax.scatter(df["imputed_rank"], y_positions, label="보간 적용", color="#d62728", s=60, zorder=2)
    ax.set_yticks(y_positions)
    ax.set_yticklabels(df["변수"])
    ax.set_xlabel("순위: 1에 가까울수록 출산율 방향과 가까움")
    ax.set_title("결측 처리 방식에 따른 요인 순위 변화", fontsize=16, pad=14)
    ax.set_xlim(0.5, max(df["complete_case_rank"].max(), df["imputed_rank"].max()) + 0.5)
    ax.invert_yaxis()
    ax.legend(loc="lower right")
    return save_current_figure("rank_sensitivity_comparison.png")


def make_pca_pcr_influence(comparison_df):
    df = comparison_df.sort_values("complete_case_cosine").copy()
    colors = ["#3b6fb6" if value < 0 else "#c44e52" for value in df["complete_case_cosine"]]
    plt.figure(figsize=(10, 6.5))
    ax = plt.gca()
    ax.barh(df["변수"], df["complete_case_cosine"], color=colors, alpha=0.9)
    ax.axvline(0, color="#222222", lw=1)
    ax.set_xlabel("PCA biplot에서 출산율 방향과의 유사도")
    ax.set_title("PCA 기준 출산율 방향과 가까운 요인", fontsize=16, pad=14)
    for y, value in enumerate(df["complete_case_cosine"]):
        x_offset = 0.025 if value >= 0 else -0.025
        ha = "left" if value >= 0 else "right"
        ax.text(value + x_offset, y, f"{value:.2f}", va="center", ha=ha, fontsize=10)
    ax.set_xlim(-1.1, 1.1)
    return save_current_figure("pca_pcr_influence.png")


def main():
    configure_korean_font()
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    namespace = execute_notebook()
    make_analysis_flow()
    make_correlation_heatmap(namespace["complete_corr"])
    make_fertility_correlation_bar(namespace["complete_corr"])
    make_rank_sensitivity(namespace["comparison_df"])
    make_pca_pcr_influence(namespace["comparison_df"])
    print(FIGURE_DIR)


if __name__ == "__main__":
    main()
