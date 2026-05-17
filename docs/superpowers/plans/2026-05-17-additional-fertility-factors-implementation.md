# Additional Fertility Factors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional extension section to the population analysis notebook for additional fertility factors approved after the research step.

**Architecture:** Keep the existing lecture-style analysis as the main path. Add optional factor discovery and extraction helpers that only activate when matching KOSIS Excel files exist in `data/`, then run a separate extended complete-case/imputed sensitivity analysis.

**Tech Stack:** Python, Jupyter Notebook JSON generator, pandas, seaborn, scikit-learn.

---

### Task 1: Extend The Notebook Generator

**Files:**
- Modify: `src/create_population_analysis_notebook.py`
- Regenerate: `population_analysis_assignment.ipynb`

- [ ] **Step 1: Add optional factor metadata**

Add a notebook markdown/code section after the base panel is created. It must define candidate variables, file keywords, rationale, KOSIS search terms, and interpretation cautions.

- [ ] **Step 2: Add robust optional extraction helpers**

Add helper functions that search `data/` by filename keywords and try both `extract_multi_indicator()` and `extract_simple_indicator()` patterns. Missing files must produce a clear status table, not an exception.

- [ ] **Step 3: Add extended analysis cells**

When at least two optional variables plus `출산율` are available, build `extended_panel`, print coverage, select a common analysis year, run `run_pca_pcr()`, run imputed sensitivity analysis, and compare base vs extended ranks. If data is insufficient, print KOSIS download guidance.

- [ ] **Step 4: Regenerate the notebook**

Run: `python3 src/create_population_analysis_notebook.py`

Expected: the script prints the notebook path and exits 0.

### Task 2: Verify

**Files:**
- Check: `src/create_population_analysis_notebook.py`
- Check: `population_analysis_assignment.ipynb`

- [ ] **Step 1: Syntax check**

Run: `python3 -m py_compile src/create_population_analysis_notebook.py`

Expected: exit 0 with no output.

- [ ] **Step 2: Notebook JSON check**

Run a Python snippet that opens `population_analysis_assignment.ipynb` as JSON and confirms the added extension headings exist.

Expected: exit 0 and headings printed.

- [ ] **Step 3: Git check**

Run: `git status -sb`

Expected: modified generator/notebook and new plan file only.
