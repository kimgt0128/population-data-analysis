import json
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "population_analysis_assignment.ipynb"


def md(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": textwrap.dedent(source).strip().splitlines(keepends=True),
    }


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": textwrap.dedent(source).strip().splitlines(keepends=True),
    }


cells = [
    md(
        """
        # 인구분석 과제: 출산율과 지역 사회·경제 요인 분석

        이 노트북은 강의자료 `출산율.ipynb`, `week10.ipynb`의 흐름을 기준으로 작성했습니다.

        - 주 분석 대상: `합계출산율`
        - 보조 분석 대상: `인구증감률/자연증가율` 자료가 있을 경우 추가 확인
        - 분석 방식 A: 강의자료 방식에 가까운 complete-case 분석
        - 분석 방식 B: 평균 대체와 선형 보간을 적용한 민감도 분석

        원본 KOSIS 엑셀 파일은 수정하지 않고, `data/` 폴더에서 읽기만 합니다.
        """
    ),
    md(
        """
        ## 00 설정

        Google Drive나 Colab에 올릴 때는 이 노트북과 `data/` 폴더가 같은 폴더에 있으면 그대로 실행됩니다.
        """
    ),
    code(
        """
        import importlib.util
        import subprocess
        import sys

        required_packages = {
            "openpyxl": "openpyxl",
            "seaborn": "seaborn",
            "scikit-learn": "sklearn",
        }

        for package_name, module_name in required_packages.items():
            if importlib.util.find_spec(module_name) is None:
                print(f"Installing {package_name} ...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        """
    ),
    code(
        """
        import os
        import re
        import unicodedata
        import warnings
        from functools import reduce
        from pathlib import Path
        from tempfile import gettempdir

        os.environ.setdefault("MPLCONFIGDIR", str(Path(gettempdir()) / "matplotlib-cache"))

        import numpy as np
        import pandas as pd
        import matplotlib as mpl
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm
        import seaborn as sns

        from sklearn.decomposition import PCA
        from sklearn.linear_model import LinearRegression
        from sklearn.metrics.pairwise import cosine_similarity
        from sklearn.preprocessing import StandardScaler

        warnings.filterwarnings("ignore", category=UserWarning)

        import platform

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

            def find_available_font():
                available = {font.name for font in fm.fontManager.ttflist}
                for font_name in candidates:
                    if font_name in available:
                        return font_name
                return None

            selected = find_available_font()
            if selected is None and platform.system() == "Linux":
                try:
                    subprocess.run(
                        ["apt-get", "update", "-qq"],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    subprocess.run(
                        ["apt-get", "install", "-y", "-qq", "fonts-nanum"],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    fm.fontManager = fm._load_fontmanager(try_read_cache=False)
                    selected = find_available_font()
                except Exception as exc:
                    print("한글 폰트 자동 설치를 건너뜁니다:", exc)

            if selected:
                mpl.rcParams["font.family"] = selected
                plt.rcParams["font.family"] = selected
                sns.set_theme(style="whitegrid", font=selected)
                print("한글 폰트 설정:", selected)
            else:
                sns.set_theme(style="whitegrid")
                print("한글 폰트를 찾지 못했습니다. Colab에서는 fonts-nanum 설치 후 런타임을 다시 실행하세요.")


        configure_korean_font()

        plt.rcParams["axes.unicode_minus"] = False
        """
    ),
    code(
        """
        PROJECT_DIR = Path.cwd()

        # 현재 위치가 population 바깥일 때도 동작하도록 보정
        if not (PROJECT_DIR / "data").exists() and (PROJECT_DIR / "population" / "data").exists():
            PROJECT_DIR = PROJECT_DIR / "population"

        DATA_DIR = PROJECT_DIR / "data"
        DOCS_DIR = PROJECT_DIR / "docs"

        print("PROJECT_DIR:", PROJECT_DIR)
        print("DATA_DIR exists:", DATA_DIR.exists())
        print("DOCS_DIR exists:", DOCS_DIR.exists())

        if not DATA_DIR.exists():
            raise FileNotFoundError("data 폴더를 찾지 못했습니다. 노트북과 data 폴더를 같은 위치에 두세요.")
        """
    ),
    md(
        """
        ## 01 데이터 인벤토리

        OpenAI 데이터 분석 가이드의 권장 흐름처럼, 먼저 파일별 출처·기간·단위·최신 연도를 확인합니다.
        결론을 서두르기보다 데이터의 범위와 품질을 먼저 확인하는 단계입니다.
        """
    ),
    code(
        """
        def nfc(text):
            return unicodedata.normalize("NFC", str(text))


        def find_files_by_keywords(*keywords):
            matches = []
            for path in DATA_DIR.rglob("*.xlsx"):
                name = nfc(path.name)
                if all(keyword in name for keyword in keywords):
                    matches.append(path)
            return sorted(matches)


        def first_file(*keywords):
            matches = find_files_by_keywords(*keywords)
            if not matches:
                raise FileNotFoundError(f"키워드 {keywords}에 맞는 xlsx 파일이 없습니다.")
            return matches[0]


        FILES = {
            "출산율": [first_file("출생아수", "합계출산율")],
            "보육시설": [first_file("유아", "보육시설수")],
            "주거안정률": find_files_by_keywords("점유형태"),
            "삶의만족도": [first_file("삶의", "만족도")],
            "주관적소득부족": [first_file("주관적소득")],
            "맞벌이가구": [first_file("맞벌이")],
            "물가지수": [first_file("소비자물가지수")],
            "범죄율": [first_file("범죄발생건수")],
            "청년고용률": [first_file("청년고용률")],
            "어린이집충족률": [first_file("어린이집", "정현원")],
            "개인소득": [first_file("지역내총생산")],
        }

        for key, paths in FILES.items():
            print(f"{key}: {len(paths)}개 파일")
            for path in paths:
                print("  -", path.relative_to(PROJECT_DIR))
        """
    ),
    code(
        """
        def read_meta(path):
            try:
                meta = pd.read_excel(path, sheet_name="메타정보", header=None, engine="openpyxl")
            except Exception:
                return {}

            result = {}
            for _, row in meta.iterrows():
                key = str(row.iloc[0]).replace("○", "").strip()
                value = row.iloc[1] if len(row) > 1 else np.nan
                if key and key != "nan":
                    result[key] = value
            return result


        def preview_years_from_excel(path):
            try:
                raw = pd.read_excel(path, sheet_name="데이터", header=None, nrows=2, engine="openpyxl")
            except Exception:
                return []
            text = " ".join(raw.astype(str).values.ravel())
            return sorted({int(x) for x in re.findall(r"(?:19|20)\\d{2}", text)})


        inventory_rows = []
        for variable, paths in FILES.items():
            for path in paths:
                meta = read_meta(path)
                years = preview_years_from_excel(path)
                inventory_rows.append(
                    {
                        "변수": variable,
                        "파일명": nfc(path.name),
                        "통계표명": meta.get("통계표명", ""),
                        "출처": meta.get("출처", ""),
                        "조회기간": meta.get("조회기간", ""),
                        "단위": meta.get("단위", ""),
                        "자료다운일자": meta.get("자료다운일자", ""),
                        "최소연도": min(years) if years else np.nan,
                        "최신연도": max(years) if years else np.nan,
                    }
                )

        inventory_df = pd.DataFrame(inventory_rows)
        display(inventory_df)
        """
    ),
    md(
        """
        ## 02 정제 함수

        강의자료에서 사용한 핵심 절차를 함수화했습니다.

        - `-`, `--`는 결측치로 처리
        - KOSIS 2단 헤더를 연도와 항목으로 분리
        - 지역명은 시도 단위로 표준화
        - 설문형 자료는 위쪽 지역명을 `ffill()`로 채움
        """
    ),
    code(
        """
        REGION_ORDER = [
            "전국", "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
            "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
        ]

        REGION_DISPLAY = {
            "전국": "전국",
            "서울": "서울특별시",
            "부산": "부산광역시",
            "대구": "대구광역시",
            "인천": "인천광역시",
            "광주": "광주광역시",
            "대전": "대전광역시",
            "울산": "울산광역시",
            "세종": "세종특별자치시",
            "경기": "경기도",
            "강원": "강원특별자치도",
            "충북": "충청북도",
            "충남": "충청남도",
            "전북": "전북특별자치도",
            "전남": "전라남도",
            "경북": "경상북도",
            "경남": "경상남도",
            "제주": "제주특별자치도",
        }

        REGION_ALIASES = {
            "계": "전국",
            "전국": "전국",
            "서울특별시": "서울",
            "서울": "서울",
            "부산광역시": "부산",
            "부산": "부산",
            "대구광역시": "대구",
            "대구": "대구",
            "인천광역시": "인천",
            "인천": "인천",
            "광주광역시": "광주",
            "광주": "광주",
            "대전광역시": "대전",
            "대전": "대전",
            "울산광역시": "울산",
            "울산": "울산",
            "세종특별자치시": "세종",
            "세종": "세종",
            "경기도": "경기",
            "경기": "경기",
            "강원도": "강원",
            "강원특별자치도": "강원",
            "강원": "강원",
            "충청북도": "충북",
            "충북": "충북",
            "충청남도": "충남",
            "충남": "충남",
            "전라북도": "전북",
            "전북특별자치도": "전북",
            "전북": "전북",
            "전라남도": "전남",
            "전남": "전남",
            "경상북도": "경북",
            "경북": "경북",
            "경상남도": "경남",
            "경남": "경남",
            "제주특별자치도": "제주",
            "제주도": "제주",
            "제주": "제주",
        }


        def normalize_region(value):
            if pd.isna(value):
                return np.nan
            text = nfc(str(value)).strip().replace(" ", "")
            if not text or text.lower() == "nan":
                return np.nan
            return REGION_ALIASES.get(text, text)


        def clean_missing(df):
            return df.replace(["-", "--", "－", "…", ""], np.nan)


        def col_text(col):
            if isinstance(col, tuple):
                return " ".join(nfc(x) for x in col if "Unnamed:" not in nfc(x))
            return nfc(col)


        def item_text(col):
            if isinstance(col, tuple) and len(col) > 1:
                return nfc(col[1])
            return nfc(col)


        def year_from_label(label):
            match = re.search(r"((?:19|20)\\d{2})", nfc(label))
            return int(match.group(1)) if match else None


        def year_from_col(col):
            if isinstance(col, tuple):
                return year_from_label(col[0])
            return year_from_label(col)


        def to_numeric_series(values):
            series = pd.Series(values)
            return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce")


        def find_col(df, keywords):
            for col in df.columns:
                text = col_text(col)
                if any(keyword in text for keyword in keywords):
                    return col
            raise KeyError(f"컬럼을 찾지 못했습니다: {keywords}")


        def read_multi_header(path):
            df = pd.read_excel(path, sheet_name="데이터", header=[0, 1], engine="openpyxl")
            df = clean_missing(df)
            cleaned_cols = []
            for col in df.columns:
                top = "" if "Unnamed:" in nfc(col[0]) else nfc(col[0]).strip()
                bottom = "" if "Unnamed:" in nfc(col[1]) else nfc(col[1]).strip()
                if not top:
                    top = bottom
                if not bottom:
                    bottom = top
                cleaned_cols.append((top, bottom))
            df.columns = pd.MultiIndex.from_tuples(cleaned_cols)
            return df


        def keep_sido_rows(df):
            return df[df["지역"].isin(REGION_ORDER)].copy()
        """
    ),
    code(
        """
        def aggregate_values(values, agg="first"):
            nums = to_numeric_series(values).dropna()
            if nums.empty:
                return np.nan
            if agg == "sum":
                return nums.sum()
            if agg == "mean":
                return nums.mean()
            return nums.iloc[0]


        def extract_multi_indicator(path, region_keywords, item_keywords, value_name, agg="first", row_filter=None):
            df = read_multi_header(path)
            region_col = find_col(df, region_keywords)
            df[region_col] = df[region_col].ffill()

            if row_filter is not None:
                df = row_filter(df)

            years = sorted({year_from_col(col) for col in df.columns if year_from_col(col) is not None})
            rows = []
            for _, row in df.iterrows():
                region = normalize_region(row[region_col])
                if region not in REGION_ORDER:
                    continue
                for year in years:
                    selected_cols = [
                        col for col in df.columns
                        if year_from_col(col) == year and any(keyword in item_text(col) for keyword in item_keywords)
                    ]
                    if not selected_cols:
                        continue
                    rows.append(
                        {
                            "지역": region,
                            "연도": int(year),
                            value_name: aggregate_values(row[selected_cols].values, agg=agg),
                        }
                    )

            result = pd.DataFrame(rows)
            if result.empty:
                raise ValueError(f"{value_name} 추출 결과가 비었습니다: {path}")
            result = result.groupby(["지역", "연도"], as_index=False)[value_name].mean()
            return keep_sido_rows(result)


        def extract_simple_indicator(path, region_keywords, item_keywords, item_values, value_name, agg="first"):
            df = pd.read_excel(path, sheet_name="데이터", engine="openpyxl")
            df = clean_missing(df)
            region_col = find_col(df, region_keywords)
            item_col = find_col(df, item_keywords) if item_keywords else None

            df[region_col] = df[region_col].ffill()
            if item_col is not None and item_values:
                mask = df[item_col].astype(str).map(lambda text: any(value in nfc(text) for value in item_values))
                df = df[mask]

            year_cols = [col for col in df.columns if year_from_col(col) is not None]
            rows = []
            for _, row in df.iterrows():
                region = normalize_region(row[region_col])
                if region not in REGION_ORDER:
                    continue
                for col in year_cols:
                    rows.append(
                        {
                            "지역": region,
                            "연도": int(year_from_col(col)),
                            value_name: aggregate_values([row[col]], agg=agg),
                        }
                    )

            result = pd.DataFrame(rows)
            if result.empty:
                raise ValueError(f"{value_name} 추출 결과가 비었습니다: {path}")
            result = result.groupby(["지역", "연도"], as_index=False)[value_name].mean()
            return keep_sido_rows(result)
        """
    ),
    md(
        """
        ## 03 요인별 추출

        각 파일을 `지역-연도-변수` 형태로 맞춥니다. 이 구조가 되어야 강의자료처럼 산점도, 상관분석, PCA/PCR을 같은 방식으로 반복할 수 있습니다.
        """
    ),
    code(
        """
        def survey_total_filter(df):
            col1 = find_col(df, ["특성별(1)"])
            col2 = find_col(df, ["특성별(2)"])
            return df[
                (df[col1].astype(str).str.strip() == "전체")
                & (df[col2].astype(str).str.strip() == "계")
            ].copy()


        birth_df = extract_multi_indicator(
            FILES["출산율"][0],
            region_keywords=["시군구별"],
            item_keywords=["합계출산율"],
            value_name="출산율",
        )

        childcare_df = extract_multi_indicator(
            FILES["보육시설"][0],
            region_keywords=["행정구역별"],
            item_keywords=["유아 천명당 보육시설수"],
            value_name="보육시설",
        )

        life_df = extract_multi_indicator(
            FILES["삶의만족도"][0],
            region_keywords=["행정구역별"],
            item_keywords=["매우 만족", "약간 만족"],
            value_name="삶의만족도",
            agg="sum",
            row_filter=survey_total_filter,
        )

        subjective_income_df = extract_multi_indicator(
            FILES["주관적소득부족"][0],
            region_keywords=["행정구역별"],
            item_keywords=["약간 부족함", "매우 부족함"],
            value_name="주관적소득부족",
            agg="sum",
            row_filter=survey_total_filter,
        )

        crime_df = extract_multi_indicator(
            FILES["범죄율"][0],
            region_keywords=["행정구역별"],
            item_keywords=["인구 천명당 범죄발생건수"],
            value_name="범죄율",
        )

        personal_income_df = extract_multi_indicator(
            FILES["개인소득"][0],
            region_keywords=["시도별"],
            item_keywords=["1인당 가계총처분가능소득"],
            value_name="개인소득",
        )

        regional_income_df = extract_multi_indicator(
            FILES["개인소득"][0],
            region_keywords=["시도별"],
            item_keywords=["1인당 지역총소득"],
            value_name="지역총소득",
        )

        dual_income_df = extract_multi_indicator(
            FILES["맞벌이가구"][0],
            region_keywords=["시도별"],
            item_keywords=["맞벌이가구비율"],
            value_name="맞벌이가구비율",
        )

        cpi_df = extract_simple_indicator(
            FILES["물가지수"][0],
            region_keywords=["도시별"],
            item_keywords=["지출목적별"],
            item_values=["0 총지수"],
            value_name="물가지수",
        )

        youth_employment_df = extract_simple_indicator(
            FILES["청년고용률"][0],
            region_keywords=["시도별"],
            item_keywords=["연령계층별"],
            item_values=["15 - 29세"],
            value_name="청년고용률",
        )

        daycare_capacity_df = extract_simple_indicator(
            FILES["어린이집충족률"][0],
            region_keywords=["시도별"],
            item_keywords=["항목"],
            item_values=["정원"],
            value_name="어린이집정원",
        )

        daycare_current_df = extract_simple_indicator(
            FILES["어린이집충족률"][0],
            region_keywords=["시도별"],
            item_keywords=["항목"],
            item_values=["현원"],
            value_name="어린이집현원",
        )

        daycare_df = pd.merge(daycare_capacity_df, daycare_current_df, on=["지역", "연도"], how="outer")
        daycare_df["어린이집충족률"] = daycare_df["어린이집현원"] / daycare_df["어린이집정원"] * 100
        daycare_df = daycare_df[["지역", "연도", "어린이집충족률", "어린이집정원", "어린이집현원"]]

        print("요인별 추출 완료")
        """
    ),
    code(
        """
        def extract_housing(paths):
            frames = []
            for path in paths:
                df = read_multi_header(path)
                region_col = find_col(df, ["시도구분", "구분", "행정구역"])
                df[region_col] = df[region_col].ffill()
                years = sorted({year_from_col(col) for col in df.columns if year_from_col(col) is not None})

                rows = []
                for _, row in df.iterrows():
                    region = normalize_region(row[region_col])
                    if region not in REGION_ORDER:
                        continue
                    for year in years:
                        owner_cols = [
                            col for col in df.columns
                            if year_from_col(col) == year and item_text(col).strip() == "자가"
                        ]
                        free_cols = [
                            col for col in df.columns
                            if year_from_col(col) == year and item_text(col).strip() == "무상"
                        ]
                        if not owner_cols:
                            continue
                        owner = aggregate_values(row[owner_cols].values)
                        free = aggregate_values(row[free_cols].values) if free_cols else 0
                        rows.append({"지역": region, "연도": int(year), "주거안정률": owner + free})
                if rows:
                    frames.append(pd.DataFrame(rows))

            result = pd.concat(frames, ignore_index=True)
            result = result.groupby(["지역", "연도"], as_index=False)["주거안정률"].mean()
            return keep_sido_rows(result)


        housing_df = extract_housing(FILES["주거안정률"])
        display(housing_df.head())
        """
    ),
    code(
        """
        source_frames = [
            birth_df,
            childcare_df,
            housing_df,
            life_df,
            subjective_income_df,
            dual_income_df,
            cpi_df,
            crime_df,
            youth_employment_df,
            daycare_df[["지역", "연도", "어린이집충족률"]],
            personal_income_df,
            regional_income_df,
        ]

        panel = reduce(lambda left, right: pd.merge(left, right, on=["지역", "연도"], how="outer"), source_frames)
        panel = panel.sort_values(["연도", "지역"]).reset_index(drop=True)

        FACTOR_VARS = [
            "보육시설",
            "주거안정률",
            "삶의만족도",
            "주관적소득부족",
            "맞벌이가구비율",
            "물가지수",
            "범죄율",
            "청년고용률",
            "어린이집충족률",
            "개인소득",
        ]

        MODEL_VARS = ["출산율"] + FACTOR_VARS

        print(panel.shape)
        display(panel.head())
        """
    ),
    md(
        """
        ## 04 데이터 품질 체크

        강의자료의 결측 처리 흐름을 따르되, 분석 전에 변수별 최신 연도와 결측률을 표로 확인합니다.
        """
    ),
    code(
        """
        coverage_rows = []
        for var in MODEL_VARS:
            temp = panel[["지역", "연도", var]].copy()
            non_null = temp.dropna(subset=[var])
            coverage_rows.append(
                {
                    "변수": var,
                    "관측치수": int(non_null.shape[0]),
                    "지역수": int(non_null["지역"].nunique()),
                    "최소연도": int(non_null["연도"].min()) if not non_null.empty else np.nan,
                    "최신연도": int(non_null["연도"].max()) if not non_null.empty else np.nan,
                    "결측률": round(temp[var].isna().mean(), 3),
                }
            )

        coverage_df = pd.DataFrame(coverage_rows)
        display(coverage_df)

        year_coverage = (
            panel.groupby("연도")[MODEL_VARS]
            .apply(lambda df: df.dropna().shape[0])
            .rename("complete_case_지역수")
            .reset_index()
        )
        display(year_coverage.tail(12))
        """
    ),
    code(
        """
        duplicate_count = panel.duplicated(["지역", "연도"]).sum()
        print("지역-연도 중복 행 수:", duplicate_count)

        latest_by_variable = (
            coverage_df[["변수", "최신연도", "관측치수", "결측률"]]
            .sort_values(["최신연도", "변수"], ascending=[False, True])
            .reset_index(drop=True)
        )
        display(latest_by_variable)
        """
    ),
    md(
        """
        ## 05 최신 현황 그래프

        2025 잠정치가 있는 변수는 최신 현황 그래프에 사용합니다. 다만 모든 요인이 2025년까지 있는 것은 아니므로, 통합 PCA/PCR에서는 별도로 공통 연도를 선택합니다.
        """
    ),
    code(
        """
        def latest_year_for(var):
            non_null = panel.dropna(subset=[var])
            return int(non_null["연도"].max())


        def plot_latest_bar(var, title, ylabel):
            year = latest_year_for(var)
            df_year = panel[(panel["연도"] == year) & (panel["지역"] != "전국")][["지역", var]].dropna()
            df_year = df_year.sort_values(var, ascending=False)
            national = panel[(panel["연도"] == year) & (panel["지역"] == "전국")][var]

            plt.figure(figsize=(12, 5))
            sns.barplot(data=df_year, x="지역", y=var, color="#6BAED6")
            if not national.empty and pd.notna(national.iloc[0]):
                plt.axhline(national.iloc[0], color="red", linestyle="--", label=f"전국 {national.iloc[0]:.2f}")
                plt.legend()
            plt.title(f"{title} ({year}년)")
            plt.xlabel("지역")
            plt.ylabel(ylabel)
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.show()


        plot_latest_bar("출산율", "시도별 합계출산율 최신 현황", "합계출산율")
        plot_latest_bar("삶의만족도", "시도별 삶의 만족도 최신 현황", "매우+약간 만족 비율(%)")
        plot_latest_bar("청년고용률", "시도별 청년고용률 최신 현황", "청년고용률(%)")
        """
    ),
    code(
        """
        def compare_region_trend(var, regions=("서울", "전남"), title=None, ylabel=None):
            plt.figure(figsize=(10, 5))
            for region in regions:
                temp = panel[(panel["지역"] == region)][["연도", var]].dropna().sort_values("연도")
                plt.plot(temp["연도"], temp[var], marker="o", label=REGION_DISPLAY.get(region, region))
            plt.title(title or f"{var} 지역별 추세")
            plt.xlabel("연도")
            plt.ylabel(ylabel or var)
            plt.grid(True, linestyle=":")
            plt.legend()
            plt.tight_layout()
            plt.show()


        compare_region_trend("출산율", title="서울특별시 vs 전라남도 연도별 합계출산율", ylabel="합계출산율")
        compare_region_trend("보육시설", title="서울특별시 vs 전라남도 유아 천명당 보육시설수", ylabel="유아 천명당 보육시설수")
        """
    ),
    md(
        """
        ## 06 강의자료 기준 분석: complete-case

        먼저 교수님 방식에 가깝게 결측이 있는 행을 제거하고 분석합니다. 이 결과를 메인 결과로 둡니다.
        """
    ),
    code(
        """
        min_obs = max(8, len(FACTOR_VARS) + 2)
        complete_case_counts = (
            panel.groupby("연도")[MODEL_VARS]
            .apply(lambda df: df.dropna().shape[0])
            .rename("complete_case_지역수")
            .reset_index()
        )

        candidate_years = complete_case_counts[complete_case_counts["complete_case_지역수"] >= min_obs]
        if candidate_years.empty:
            candidate_years = complete_case_counts[complete_case_counts["complete_case_지역수"] > 0]

        ANALYSIS_YEAR = int(candidate_years["연도"].max())
        print("통합 분석 기준 연도:", ANALYSIS_YEAR)
        display(complete_case_counts)

        complete_case_df = panel[panel["연도"] == ANALYSIS_YEAR][["지역"] + MODEL_VARS].dropna()
        print("complete-case 표본 수:", complete_case_df.shape[0])
        display(complete_case_df)
        """
    ),
    code(
        """
        def plot_scatter_grid(panel_data, features, year, title_prefix):
            n_cols = 3
            n_rows = int(np.ceil(len(features) / n_cols))
            fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols * 5, n_rows * 4))
            axes = np.array(axes).reshape(-1)

            for idx, feature in enumerate(features):
                ax = axes[idx]
                temp = panel_data[
                    (panel_data["연도"] == year) & (panel_data["지역"] != "전국")
                ][["출산율", feature]].dropna()
                sns.regplot(data=temp, x=feature, y="출산율", ax=ax, scatter_kws={"alpha": 0.75})
                corr = temp["출산율"].corr(temp[feature]) if temp.shape[0] >= 3 else np.nan
                ax.set_title(f"{feature} vs 출산율\\nr={corr:.2f}")
                ax.grid(True, linestyle=":")

            for idx in range(len(features), len(axes)):
                axes[idx].axis("off")

            plt.suptitle(f"{title_prefix}: {year}년 요인별 산점도", fontsize=16)
            plt.tight_layout(rect=[0, 0, 1, 0.96])
            plt.show()


        plot_scatter_grid(panel, FACTOR_VARS, ANALYSIS_YEAR, "complete-case 기준")
        """
    ),
    code(
        """
        def plot_corr_heatmap(df, variables, title):
            corr = df[variables].corr()
            plt.figure(figsize=(11, 9))
            sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1)
            plt.title(title)
            plt.tight_layout()
            plt.show()
            return corr


        complete_corr = plot_corr_heatmap(
            complete_case_df,
            MODEL_VARS,
            f"{ANALYSIS_YEAR}년 complete-case 상관계수 행렬",
        )
        """
    ),
    code(
        """
        def run_pca_pcr(panel_data, features, year, label):
            df_year = panel_data[panel_data["연도"] == year][["지역", "출산율"] + features].dropna().copy()
            df_year = df_year[df_year["지역"] != "전국"].reset_index(drop=True)

            print(f"[{label}] 분석 연도:", year)
            print(f"[{label}] 표본 수:", df_year.shape[0])
            print(f"[{label}] 변수 수:", len(features))

            if df_year.shape[0] < 4:
                raise ValueError(f"{label}: PCA/PCR을 수행하기에 표본 수가 너무 적습니다.")

            pca_variables = ["출산율"] + features
            scaler_all = StandardScaler()
            all_scaled = scaler_all.fit_transform(df_year[pca_variables])

            pca_2 = PCA(n_components=2)
            coords = pca_2.fit_transform(all_scaled)
            loadings = pd.DataFrame(pca_2.components_.T, index=pca_variables, columns=["PC1", "PC2"])

            plt.figure(figsize=(10, 8))
            for i, region in enumerate(df_year["지역"]):
                plt.scatter(coords[i, 0], coords[i, 1], color="gray", alpha=0.7)
                plt.text(coords[i, 0] + 0.04, coords[i, 1], region, fontsize=8)

            scale = 2.5
            for variable in pca_variables:
                color = "red" if variable == "출산율" else "black"
                plt.arrow(
                    0,
                    0,
                    loadings.loc[variable, "PC1"] * scale,
                    loadings.loc[variable, "PC2"] * scale,
                    color=color,
                    width=0.004,
                    head_width=0.05,
                    alpha=0.85,
                )
                plt.text(
                    loadings.loc[variable, "PC1"] * scale * 1.08,
                    loadings.loc[variable, "PC2"] * scale * 1.08,
                    variable,
                    color=color,
                    fontsize=9,
                )

            plt.axhline(0, color="gray", linestyle="--", linewidth=0.8)
            plt.axvline(0, color="gray", linestyle="--", linewidth=0.8)
            plt.xlabel(f"PC1 ({pca_2.explained_variance_ratio_[0] * 100:.1f}%)")
            plt.ylabel(f"PC2 ({pca_2.explained_variance_ratio_[1] * 100:.1f}%)")
            plt.title(f"PCA Biplot ({label}) - {year}년")
            plt.grid(True, linestyle=":")
            plt.tight_layout()
            plt.show()

            target_vec = loadings.loc["출산율", ["PC1", "PC2"]].values.reshape(1, -1)
            cosine_rows = []
            for feature in features:
                feature_vec = loadings.loc[feature, ["PC1", "PC2"]].values.reshape(1, -1)
                cosine_rows.append(
                    {
                        "변수": feature,
                        "cosine_similarity": cosine_similarity(target_vec, feature_vec)[0][0],
                    }
                )
            cosine_df = pd.DataFrame(cosine_rows).sort_values("cosine_similarity", ascending=False)
            cosine_df["rank"] = range(1, len(cosine_df) + 1)

            X = df_year[features].astype(float)
            y = df_year["출산율"].astype(float)

            scaler_x = StandardScaler()
            X_scaled = scaler_x.fit_transform(X)

            pca_full = PCA()
            X_pca = pca_full.fit_transform(X_scaled)
            explained_ratio = np.cumsum(pca_full.explained_variance_ratio_)
            n_components = int(np.argmax(explained_ratio >= 0.8) + 1)

            model = LinearRegression()
            X_pca_reduced = X_pca[:, :n_components]
            model.fit(X_pca_reduced, y)
            y_pred = model.predict(X_pca_reduced)
            r_squared = model.score(X_pca_reduced, y)

            plt.figure(figsize=(6, 5))
            plt.scatter(y, y_pred, color="#3182BD")
            plt.plot([y.min(), y.max()], [y.min(), y.max()], "r--")
            plt.xlabel("실제 출산율")
            plt.ylabel("예측 출산율 (PCR)")
            plt.title(f"PCR 예측 ({label})\\nR²={r_squared:.3f}, PC={n_components}")
            plt.grid(True, linestyle=":")
            plt.tight_layout()
            plt.show()

            V = pca_full.components_[:n_components, :].T
            beta_orig = V @ model.coef_
            coef_df = (
                pd.DataFrame({"변수": features, "pcr_coef": beta_orig})
                .sort_values("pcr_coef", ascending=False)
                .reset_index(drop=True)
            )

            print(f"[{label}] 선택된 주성분 개수:", n_components)
            print(f"[{label}] R²:", round(r_squared, 3))
            display(cosine_df)
            display(coef_df)

            return {
                "label": label,
                "year": year,
                "sample_size": df_year.shape[0],
                "loadings": loadings,
                "cosine": cosine_df,
                "coef": coef_df,
                "r_squared": r_squared,
                "n_components": n_components,
            }


        complete_result = run_pca_pcr(panel, FACTOR_VARS, ANALYSIS_YEAR, "complete-case")
        """
    ),
    md(
        """
        ## 07 보간 적용 분석

        이 단계는 메인 결론이 아니라 민감도 분석입니다. `week10`의 결측 대체 흐름을 반영해 다음 순서로 처리합니다.

        1. 지역별 시계열 내부 결측: 선형 보간
        2. 양끝 결측: 같은 변수·같은 연도의 시도 평균
        3. 그래도 남는 결측: 해당 변수 전체 평균
        """
    ),
    code(
        """
        def make_imputed_panel(panel_data, variables):
            years = sorted(panel_data["연도"].dropna().astype(int).unique())
            regions = [region for region in REGION_ORDER if region in panel_data["지역"].dropna().unique()]

            grid = pd.MultiIndex.from_product([regions, years], names=["지역", "연도"]).to_frame(index=False)
            base = grid.merge(panel_data, on=["지역", "연도"], how="left")

            imputation_rows = []
            for var in variables:
                before = base[var].copy()
                base[var] = base.groupby("지역")[var].transform(
                    lambda series: series.interpolate(method="linear", limit_area="inside")
                )
                base[var] = base.groupby("연도")[var].transform(lambda series: series.fillna(series.mean()))
                base[var] = base[var].fillna(base[var].mean())
                flag_col = f"{var}_is_imputed"
                base[flag_col] = before.isna() & base[var].notna()
                imputation_rows.append(
                    {
                        "변수": var,
                        "원래결측수": int(before.isna().sum()),
                        "보간후결측수": int(base[var].isna().sum()),
                        "보간값수": int(base[flag_col].sum()),
                    }
                )

            return base, pd.DataFrame(imputation_rows)


        imputed_panel, imputation_summary = make_imputed_panel(panel, MODEL_VARS)
        display(imputation_summary)

        original_year_quality = (
            panel.groupby("연도")[MODEL_VARS]
            .apply(lambda df: (df.notna().sum() >= 12).mean())
            .rename("원자료_변수커버리지")
            .reset_index()
        )
        display(original_year_quality)

        imputed_year_candidates = original_year_quality[
            original_year_quality["원자료_변수커버리지"] >= 0.8
        ]
        if imputed_year_candidates.empty:
            IMPUTED_ANALYSIS_YEAR = ANALYSIS_YEAR
        else:
            IMPUTED_ANALYSIS_YEAR = int(imputed_year_candidates["연도"].max())

        print("complete-case 분석 연도:", ANALYSIS_YEAR)
        print("보간 적용 분석 연도:", IMPUTED_ANALYSIS_YEAR)

        imputed_case_df = imputed_panel[imputed_panel["연도"] == IMPUTED_ANALYSIS_YEAR][["지역"] + MODEL_VARS]
        print("보간 적용 표본 수:", imputed_case_df.dropna().shape[0])
        display(imputed_case_df.head())
        """
    ),
    code(
        """
        imputed_corr = plot_corr_heatmap(
            imputed_case_df.dropna(),
            MODEL_VARS,
            f"{IMPUTED_ANALYSIS_YEAR}년 보간 적용 상관계수 행렬",
        )

        imputed_result = run_pca_pcr(imputed_panel, FACTOR_VARS, IMPUTED_ANALYSIS_YEAR, "imputed")
        """
    ),
    md(
        """
        ## 08 complete-case와 보간 결과 비교

        발표에서는 complete-case 결과를 메인으로 설명하고, 보간 결과는 “결과가 크게 바뀌는지 확인한 민감도 분석”으로 간단히 제시합니다.
        보간 분석은 원자료 커버리지가 충분한 최신 연도를 자동 선택하므로 complete-case 기준 연도와 다를 수 있습니다.
        """
    ),
    code(
        """
        complete_cosine = complete_result["cosine"][["변수", "cosine_similarity", "rank"]].rename(
            columns={
                "cosine_similarity": "complete_case_cosine",
                "rank": "complete_case_rank",
            }
        )
        imputed_cosine = imputed_result["cosine"][["변수", "cosine_similarity", "rank"]].rename(
            columns={
                "cosine_similarity": "imputed_cosine",
                "rank": "imputed_rank",
            }
        )

        complete_coef = complete_result["coef"].rename(columns={"pcr_coef": "complete_case_pcr_coef"})
        imputed_coef = imputed_result["coef"].rename(columns={"pcr_coef": "imputed_pcr_coef"})

        comparison_df = (
            complete_cosine
            .merge(imputed_cosine, on="변수", how="outer")
            .merge(complete_coef, on="변수", how="outer")
            .merge(imputed_coef, on="변수", how="outer")
        )
        comparison_df["rank_change"] = comparison_df["imputed_rank"] - comparison_df["complete_case_rank"]
        comparison_df = comparison_df.sort_values("complete_case_rank").reset_index(drop=True)

        display(comparison_df)

        top_complete = comparison_df.sort_values("complete_case_rank").head(3)["변수"].tolist()
        top_imputed = comparison_df.sort_values("imputed_rank").head(3)["변수"].tolist()

        print(f"complete-case 기준 연도: {ANALYSIS_YEAR}")
        print(f"보간 적용 기준 연도: {IMPUTED_ANALYSIS_YEAR}")
        print("complete-case 기준 상위 3개 요인:", top_complete)
        print("보간 적용 기준 상위 3개 요인:", top_imputed)
        print("complete-case R²:", round(complete_result["r_squared"], 3))
        print("imputed R²:", round(imputed_result["r_squared"], 3))
        """
    ),
    md(
        """
        ## 09 인구증감률/자연증가율 보조 분석 자료 확인

        현재 과제 안내에는 인구 증감률이 언급되어 있으나, 현재 `data/` 폴더의 파일만 보면 사망자수·자연증가율·인구증가율 자료가 별도로 포함되어 있지 않습니다.
        아래 셀은 관련 파일이 추가되었는지 자동으로 확인합니다.
        """
    ),
    code(
        """
        growth_keywords = ["인구증감", "자연증가", "인구증가", "사망", "인구동향"]
        growth_candidates = []
        for path in DATA_DIR.rglob("*.xlsx"):
            name = nfc(path.name)
            if any(keyword in name for keyword in growth_keywords):
                growth_candidates.append(path)

        if growth_candidates:
            print("인구증감/자연증가 관련 후보 파일:")
            for path in growth_candidates:
                print("-", path.relative_to(PROJECT_DIR))
        else:
            print("현재 data 폴더에는 인구증감률/자연증가율 분석에 필요한 별도 파일이 없습니다.")
            print("추가하면 좋은 KOSIS 자료 예: 시도별 출생아수·사망자수·자연증가율 또는 주민등록인구 기반 인구증감률.")
        """
    ),
    md(
        """
        ## 10 결론 작성 가이드

        아래 문장은 실행 결과를 보고 발표문으로 다듬기 위한 틀입니다.
        """
    ),
    code(
        """
        conclusion_template = f'''
        [요약]
        complete-case는 {ANALYSIS_YEAR}년, 보간 적용 분석은 {IMPUTED_ANALYSIS_YEAR}년 시도 단위 자료를 기준으로 했다.
        강의자료 방식의 complete-case 분석을 메인 결과로 사용했고, 결측 보강을 위한 보간 분석은 민감도 분석으로 비교했다.

        [메인 결과]
        complete-case PCA 벡터 유사도 기준 상위 요인은 {", ".join(top_complete)} 순으로 나타났다.
        PCR 분석의 설명력은 R²={complete_result["r_squared"]:.3f}이며, 이는 변수 간 상관 구조를 줄인 뒤 출산율과의 관계를 본 결과다.

        [보간 비교]
        보간 적용 후 상위 요인은 {", ".join(top_imputed)} 순으로 나타났다.
        순위가 크게 유지되면 결과가 비교적 안정적이라고 볼 수 있고, 순위가 바뀌면 결측 처리 방식에 민감하므로 해석에 주의해야 한다.

        [주의점]
        이 분석은 시도 단위의 관측치가 많지 않으므로 인과관계가 아니라 상관관계와 탐색적 영향도 비교로 해석해야 한다.
        또한 2025 잠정치가 있는 변수와 없는 변수가 섞여 있어, 최신 현황 그래프와 통합 PCA/PCR의 기준 연도가 다를 수 있다.
        '''

        print(conclusion_template)
        """
    ),
]


notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.11",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}


OUTPUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
print(OUTPUT)
