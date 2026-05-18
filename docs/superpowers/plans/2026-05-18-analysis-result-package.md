# Analysis Result Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate durable assignment-ready result files that summarize the correlation, PCA, PCR, imputation comparison, optional-factor extension, and natural-increase findings from the notebook.

**Architecture:** Keep `population_analysis_assignment.ipynb` as the source of truth for data cleaning and analysis. Add a small report-generation script that executes the notebook code cells in a controlled namespace, extracts the result tables already computed by the notebook, and writes Markdown/CSV outputs under `reports/`. This avoids duplicating data-cleaning logic while giving the student stable files to use in slides and writeups.

**Tech Stack:** Python 3, Jupyter Notebook JSON, pandas, matplotlib Agg backend, existing scikit-learn/seaborn notebook code.

---

### Task 1: Create Result Export Script

**Files:**
- Create: `src/generate_analysis_report.py`
- Create output directory at runtime: `reports/`
- Create output directory at runtime: `reports/tables/`

- [ ] **Step 1: Add notebook executor and output helpers**

Create `src/generate_analysis_report.py` with:

```python
import json
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "population_analysis_assignment.ipynb"
REPORT_DIR = ROOT / "reports"
TABLE_DIR = REPORT_DIR / "tables"


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
        exec(compile(source, f"notebook_cell_{index}", "exec"), namespace)
    return namespace
```

- [ ] **Step 2: Add table writer helpers**

Append:

```python
def write_table(df, filename):
    path = TABLE_DIR / filename
    df.to_csv(path, index=True if df.index.name or not isinstance(df.index, pd.RangeIndex) else False, encoding="utf-8-sig")
    return path


def fmt_float(value, digits=3):
    if pd.isna(value):
        return ""
    return f"{float(value):.{digits}f}"


def df_to_markdown(df):
    if df.empty:
        return "(표시할 행이 없습니다.)"

    formatted = df.copy()
    for column in formatted.columns:
        formatted[column] = formatted[column].map(
            lambda value: fmt_float(value) if isinstance(value, float) else str(value)
        )

    headers = [str(column) for column in formatted.columns]
    rows = formatted.astype(str).values.tolist()
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)
```

- [ ] **Step 3: Add summary Markdown builder**

Append:

```python
def build_summary(namespace):
    comparison_df = namespace["comparison_df"].copy()
    extended_comparison_df = namespace.get("extended_comparison_df", pd.DataFrame()).copy()
    complete_result = namespace["complete_result"]
    imputed_result = namespace["imputed_result"]
    analysis_year = namespace["ANALYSIS_YEAR"]
    imputed_year = namespace["IMPUTED_ANALYSIS_YEAR"]

    top_complete = comparison_df.sort_values("complete_case_rank").head(5)
    top_imputed = comparison_df.sort_values("imputed_rank").head(5)

    lines = [
        "# 인구분석 과제 결과 요약",
        "",
        "## 핵심 결론",
        "",
        f"- 강의자료 방식 complete-case 분석 기준 연도는 {analysis_year}년입니다.",
        f"- complete-case 기준 상위 요인은 {', '.join(top_complete['변수'].head(3))}입니다.",
        f"- 보간 적용 분석 기준 연도는 {imputed_year}년이며, 상위 요인은 {', '.join(top_imputed['변수'].head(3))}입니다.",
        f"- complete-case PCR R²는 {fmt_float(complete_result['r_squared'])}, 보간 적용 PCR R²는 {fmt_float(imputed_result['r_squared'])}입니다.",
        "- 이 결과는 시도 단위 탐색 분석이므로 인과관계가 아니라 상관관계와 영향 가능성이 큰 요인의 비교로 해석합니다.",
        "",
        "## Complete-Case 상위 요인",
        "",
        df_to_markdown(top_complete[["변수", "complete_case_rank", "complete_case_cosine", "complete_case_pcr_coef"]]),
        "",
        "## 보간 적용 상위 요인",
        "",
        df_to_markdown(top_imputed[["변수", "imputed_rank", "imputed_cosine", "imputed_pcr_coef", "rank_change"]]),
        "",
    ]

    if not extended_comparison_df.empty:
        top_extended = extended_comparison_df.sort_values("extended_rank").head(5)
        top_extended_imputed = extended_comparison_df.sort_values("extended_imputed_rank").head(5)
        lines.extend(
            [
                "## 추가 요인 확장 분석",
                "",
                f"- 확장 complete-case 상위 요인은 {', '.join(top_extended['변수'].head(5))}입니다.",
                f"- 확장 보간 분석 상위 요인은 {', '.join(top_extended_imputed['변수'].head(5))}입니다.",
                "- 혼인 지표는 출산율의 직접 원인이라기보다 한국 출산율 변동을 매개하는 인구학적 경로로 해석합니다.",
                "- 주택 가격지수와 경력단절여성비율은 보간 확장 분석에서 강하게 나타나지만, 결측 보강에 민감하므로 보조 결과로 제시합니다.",
                "",
                df_to_markdown(top_extended[["변수", "extended_rank", "extended_cosine", "extended_imputed_rank", "extended_rank_change_after_imputation", "추가요인여부"]]),
                "",
            ]
        )

    lines.extend(
        [
            "## 발표용 한 문단",
            "",
            "교수님 강의자료 방식에 맞춰 complete-case 분석을 메인으로 두고, 결측 보강 분석은 민감도 확인용으로 비교했다. "
            f"{analysis_year}년 complete-case 기준으로는 {', '.join(top_complete['변수'].head(3))}가 출산율과 가장 밀접하게 나타났다. "
            f"반면 보간을 적용한 {imputed_year}년 분석에서는 {', '.join(top_imputed['변수'].head(3))}의 순위가 높아져, 결측 처리 방식에 따라 주거·물가 관련 요인의 중요성이 커질 수 있음을 확인했다. "
            "추가 요인 분석에서는 혼인, 주택가격, 경력단절, 청년이동을 보조적으로 검토했으며, 이는 메인 결론을 대체하기보다 결과 안정성을 점검하는 확장 분석으로 해석한다.",
            "",
            "## 산출 파일",
            "",
            "- `reports/tables/base_comparison.csv`: 기본 complete-case와 보간 분석 순위 비교",
            "- `reports/tables/extended_comparison.csv`: 추가 요인 확장 분석 순위 비교",
            "- `reports/tables/complete_case_correlation.csv`: complete-case 상관계수 행렬",
            "- `reports/tables/imputed_correlation.csv`: 보간 적용 상관계수 행렬",
        ]
    )
    return "\\n".join(lines) + "\\n"
```

- [ ] **Step 4: Add main entrypoint**

Append:

```python
def main():
    REPORT_DIR.mkdir(exist_ok=True)
    TABLE_DIR.mkdir(exist_ok=True)
    namespace = execute_notebook()

    write_table(namespace["comparison_df"], "base_comparison.csv")
    if not namespace.get("extended_comparison_df", pd.DataFrame()).empty:
        write_table(namespace["extended_comparison_df"], "extended_comparison.csv")
    write_table(namespace["complete_corr"], "complete_case_correlation.csv")
    write_table(namespace["imputed_corr"], "imputed_correlation.csv")

    summary = build_summary(namespace)
    summary_path = REPORT_DIR / "analysis_summary.md"
    summary_path.write_text(summary, encoding="utf-8")
    print(summary_path)


if __name__ == "__main__":
    main()
```

### Task 2: Generate Results

**Files:**
- Generate: `reports/analysis_summary.md`
- Generate: `reports/tables/base_comparison.csv`
- Generate: `reports/tables/extended_comparison.csv`
- Generate: `reports/tables/complete_case_correlation.csv`
- Generate: `reports/tables/imputed_correlation.csv`

- [ ] **Step 1: Run the report script**

Run:

```bash
python3 src/generate_analysis_report.py
```

Expected: command exits 0 and prints `/Users/kimgt/Developer/Project/data_science/population/.worktrees/additional-fertility-factors/reports/analysis_summary.md`.

- [ ] **Step 2: Inspect the generated summary**

Run:

```bash
sed -n '1,220p' reports/analysis_summary.md
```

Expected: the file includes `핵심 결론`, `Complete-Case 상위 요인`, `보간 적용 상위 요인`, `추가 요인 확장 분석`, and `발표용 한 문단`.

### Task 3: Verify and Commit

**Files:**
- Check: `src/generate_analysis_report.py`
- Check: `reports/analysis_summary.md`
- Check: `reports/tables/*.csv`

- [ ] **Step 1: Syntax check**

Run:

```bash
python3 -m py_compile src/create_population_analysis_notebook.py src/download_optional_kosis_data.py src/generate_analysis_report.py
```

Expected: exit 0 with no output.

- [ ] **Step 2: Notebook smoke execution**

Run:

```bash
MPLBACKEND=Agg python3 - <<'PY'
import json
from pathlib import Path

nb = json.loads(Path("population_analysis_assignment.ipynb").read_text(encoding="utf-8"))
ns = {"display": lambda *args, **kwargs: None}
for index, cell in enumerate(nb["cells"]):
    if cell.get("cell_type") != "code":
        continue
    source = "".join(cell.get("source", []))
    if source.strip():
        exec(compile(source, f"cell_{index}", "exec"), ns)
print("EXECUTED_CODE_CELLS_OK")
PY
```

Expected: prints `EXECUTED_CODE_CELLS_OK`.

- [ ] **Step 3: Diff check**

Run:

```bash
git diff --check
git status -sb
```

Expected: `git diff --check` exits 0. Status shows the plan, report script, and generated report files.

- [ ] **Step 4: Commit and push**

Run:

```bash
git add docs/superpowers/plans/2026-05-18-analysis-result-package.md src/generate_analysis_report.py reports/analysis_summary.md reports/tables/base_comparison.csv reports/tables/extended_comparison.csv reports/tables/complete_case_correlation.csv reports/tables/imputed_correlation.csv
git commit -m "Add assignment analysis result summary"
git push
```

Expected: commit is created on `research/additional-fertility-factors` and pushed to origin.
