import json
import re
import time
import urllib.parse
import urllib.request
import http.cookiejar
from io import StringIO
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_DIR = DATA_DIR / "optional_kosis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

REGION_ALIASES = {
    "전국": "전국",
    "서울특별시": "서울",
    "부산광역시": "부산",
    "대구광역시": "대구",
    "인천광역시": "인천",
    "광주광역시": "광주",
    "대전광역시": "대전",
    "울산광역시": "울산",
    "세종특별자치시": "세종",
    "경기도": "경기",
    "강원도": "강원",
    "강원특별자치도": "강원",
    "충청북도": "충북",
    "충청남도": "충남",
    "전라북도": "전북",
    "전북특별자치도": "전북",
    "전라남도": "전남",
    "경상북도": "경북",
    "경상남도": "경남",
    "제주도": "제주",
    "제주특별자치도": "제주",
}


class KosisStatHtmlClient:
    def __init__(self):
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )
        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://kosis.kr/statHtml/statHtml.do",
        }

    def post(self, url, params):
        request = urllib.request.Request(
            url,
            data=urllib.parse.urlencode(params).encode("utf-8"),
            headers=self.headers,
        )
        with self.opener.open(request, timeout=90) as response:
            return response.read().decode("utf-8", "replace")

    def fetch_stat_info(self, org_id, tbl_id, list_id="", conn_path="Z1"):
        params = {
            "orgId": org_id,
            "tblId": tbl_id,
            "language": "ko",
            "pub": "2",
            "conn_path": conn_path,
            "obj_var_id": "A",
            "list_id": list_id,
            "vw_cd": "MT_ZTITLE",
            "itm_id": "",
            "dbUser": "NSI.",
            "tblSe": "",
            "scrId": "",
            "fieldList": "",
            "colAxis": "",
            "rowAxis": "",
            "isFirst": "Y",
            "dataOpt": "ko",
        }
        html = self.post("https://kosis.kr/statHtml/statHtmlContent.do", params)
        match = re.search(r"var\s+g_jsonStatInfo\s*=\s*'(.*?)';", html, re.S)
        if not match:
            raise RuntimeError(f"g_jsonStatInfo를 찾지 못했습니다: {org_id}/{tbl_id}")
        return json.loads(match.group(1))

    def fetch_html_table(self, info, item_ids, class_selections, periods, period_code):
        field_list = [
            {
                "targetId": "PRD",
                "targetValue": "",
                "prdValue": f"{period_code}," + ",".join(periods) + ",@",
            }
        ]
        field_list.extend(
            {"targetId": "ITM_ID", "targetValue": item_id, "prdValue": ""}
            for item_id in item_ids
        )
        for level, class_info in enumerate(info["classInfoList"], start=1):
            class_id = class_info["classId"]
            selected = class_selections.get(class_id)
            if selected is None:
                selected = [
                    item["itmId"]
                    for item in class_info["itmList"]
                    if item.get("leaf", 1) == 1
                ]
            field_list.extend(
                {"targetId": f"OV_L{level}_ID", "targetValue": code, "prdValue": ""}
                for code in selected
            )

        cell_count = max(1, len(periods) * max(1, len(item_ids)))
        for selected in class_selections.values():
            cell_count *= max(1, len(selected))
        if not class_selections:
            for class_info in info["classInfoList"]:
                cell_count *= max(1, len(class_info["itmList"]))

        param_info = info.get("paramInfo", {})
        if isinstance(param_info, list):
            param_info = param_info[0] if param_info else {}

        params = {
            "jsonStr": "",
            "orgId": info["orgId"],
            "tblId": info["tblId"],
            "language": "ko",
            "file": "",
            "analText": "",
            "scrId": "",
            "fieldList": json.dumps(field_list, ensure_ascii=False),
            "colAxis": ",".join(info["pivotInfo"]["colList"]),
            "rowAxis": ",".join(info["pivotInfo"]["rowList"]),
            "isFirst": "Y",
            "contextPath": "/statHtml",
            "ordColIdx": "",
            "ordType": "",
            "logSeq": "",
            "vwCd": "MT_ZTITLE",
            "listId": param_info.get("listId", ""),
            "connPath": param_info.get("connPath", "Z1"),
            "statId": info["statId"],
            "pub": "2",
            "pubLog": info.get("pubLog", "4"),
            "viewKind": "1",
            "viewSubKind": "",
            "doAnal": "N",
            "analType": "",
            "analCmpr": "",
            "analTime": "",
            "analCombo": "",
            "originData": "",
            "analClass": "",
            "analItem": "",
            "obj_var_id": "A",
            "itm_id": "",
            "mode": "",
            "dataOpt": "ko",
            "noSelect": "",
            "view": "table",
            "mobChk": "false",
            "analWithCHGRATE": "",
            "defaulPeriodArr": "",
            "defaultClassArr": "",
            "defaultItmArr": "",
            "existStblCmmtKor": info.get("existStblCmmtKor", "N"),
            "existStblCmmtEng": info.get("existStblCmmtEng", "N"),
            "classAllArr": "[]",
            "classSet": "[]",
            "selectAllFlag": "N",
            "selectTimeRangeCnt": "",
            "periodStr": period_code,
            "funcPrdSe": "",
            "tblNm": info["tblNm"],
            "tblEngNm": info.get("tblEngNm", ""),
            "isChangedDataOpt": "",
            "itemMultiply": str(max(1, len(item_ids))),
            "dimCo": str(info.get("dimCo", "")),
            "dbUser": "NSI.",
            "usePivot": "N",
            "isChangedTableType": "N",
            "isChangedPeriodCo": "N",
            "isChangedPrdSort": "N",
            "p_chkStatus": "",
            "p_objVarId": "",
            "p_lvl": "",
            "p_logicFlag": "",
            "p_classAllChkYn": "N",
            "p_classAllSelectYn": "N",
            "useAddFuncLog": "",
            "chargerLvl": "",
            "st": "",
            "new_win": "",
            "first_open": "",
            "debug": "",
            "maxCellOver": "",
            "reqCellCnt": str(cell_count),
            "inheritYn": "N",
            "originOrgId": "",
            "originTblId": "",
            "pubSeType": "",
            "relChkOrgId": "",
            "relChkTblId": "",
            "highLightStr": "",
            "markType": "",
            "docId": "",
            "itmNm": "",
            "cmmtChk": "",
            "labelOriginData": "원자료 함께 보기",
            "diviSearchYn": "N",
            "orderStr": ",".join(info["pivotInfo"]["rowList"] + info["pivotInfo"]["colList"]),
            "startNum": "1",
            "endNum": str(cell_count),
            "lastChk": "N",
            "colClsAt": "N",
            "analyzable": str(info.get("analyzable", "true")).lower(),
            "tmprScrId": "",
            "expDash": "Y",
        }
        raw = self.post("https://kosis.kr/statHtml/html.do", params)
        if raw.lstrip().startswith("<"):
            raise RuntimeError(f"KOSIS html.do가 JSON이 아닌 응답을 반환했습니다: {raw[:200]}")
        result = json.loads(raw)
        if result.get("errCode"):
            raise RuntimeError(f"KOSIS html.do 오류: {result.get('errMsg')}")
        return result["result"][0]


def normalize_region(region):
    if pd.isna(region):
        return None
    text = str(region).strip()
    return REGION_ALIASES.get(text, text)


def parse_year_month(label):
    text = str(label)
    match = re.search(r"((?:19|20)\d{2})(?:\D?([01]\d))?", text)
    if not match:
        return None, None
    year = int(match.group(1))
    month = int(match.group(2)) if match.group(2) else None
    return year, month


def melt_kosis_html_table(html):
    df = pd.read_html(StringIO(html))[0]
    region_col = df.columns[0]
    rows = []

    for _, row in df.iterrows():
        region = normalize_region(row[region_col])
        if region is None or region in {"행정구역별", "시도별", "지역별"}:
            continue
        for col in df.columns[1:]:
            parts = col if isinstance(col, tuple) else (col,)
            labels = [
                str(part)
                for part in parts
                if str(part) != "nan" and not str(part).startswith("Unnamed:")
            ]
            label = " ".join(labels)
            year, month = parse_year_month(label)
            if year is None:
                continue
            value_text = str(row[col]).strip().replace(",", "")
            if value_text in {"", "-", "--", "nan"}:
                value = pd.NA
            else:
                value = pd.to_numeric(value_text, errors="coerce")
            rows.append(
                {
                    "지역": region,
                    "연도": year,
                    "월": month,
                    "label": label,
                    "value": value,
                }
            )
    return pd.DataFrame(rows)


def select_series(long_df, variable, includes=None, excludes=None):
    includes = includes or []
    excludes = excludes or []
    mask = pd.Series(True, index=long_df.index)
    for keyword in includes:
        mask &= long_df["label"].str.contains(keyword, regex=False, na=False)
    for keyword in excludes:
        mask &= ~long_df["label"].str.contains(keyword, regex=False, na=False)
    selected = long_df[mask].copy()
    selected = (
        selected.groupby(["지역", "연도"], as_index=False)["value"]
        .mean()
        .rename(columns={"value": variable})
    )
    return selected


def merge_frames(frames):
    result = None
    for frame in frames:
        if frame.empty:
            continue
        result = frame if result is None else result.merge(frame, on=["지역", "연도"], how="outer")
    return result if result is not None else pd.DataFrame(columns=["지역", "연도"])


def fetch_e_region_detail(unity_srvc_id, std_idct_id, variable, start_year, end_year):
    params = {
        "unitySrvcId": unity_srvc_id,
        "stdIdctId": std_idct_id,
        "clsfGroupCd": "A000000001",
        "clsfCd": "00",
        "cyclSe": "Y",
        "year": "",
        "clsfLevel": "1",
        "regionCd": "",
    }
    request = urllib.request.Request(
        "https://kosis.kr/visual/eRegionIndex/selectWholeDetailData.do",
        data=urllib.parse.urlencode(params).encode("utf-8"),
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://kosis.kr/visual/eRegionIndex/eRegionWhole.do",
        },
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = json.loads(response.read().decode("utf-8", "replace"))

    rows = []
    for row in payload.get("data", []):
        year = int(str(row.get("wrtPnttm", ""))[:4])
        if year < start_year or year > end_year:
            continue
        rows.append(
            {
                "지역": normalize_region(row.get("regionNm")),
                "연도": year,
                variable: pd.to_numeric(row.get("vl"), errors="coerce"),
            }
        )

    return (
        pd.DataFrame(rows)
        .dropna(subset=["지역"])
        .groupby(["지역", "연도"], as_index=False)[variable]
        .mean()
    )


def fetch_and_melt(client, config):
    info = client.fetch_stat_info(
        config["org_id"],
        config["tbl_id"],
        config.get("list_id", ""),
        config.get("conn_path", "Z1"),
    )
    time.sleep(0.2)
    html = client.fetch_html_table(
        info,
        item_ids=config["item_ids"],
        class_selections=config.get("class_selections", {}),
        periods=config["periods"],
        period_code=config["period_code"],
    )
    long_df = melt_kosis_html_table(html)
    return info, long_df


def main():
    client = KosisStatHtmlClient()
    source_rows = []
    factor_frames = []
    population_frames = []

    yearly = [str(year) for year in range(2015, 2026)]
    yearly_to_2024 = [str(year) for year in range(2015, 2025)]
    housing_months = [f"{year}{month:02d}" for year in range(2021, 2026) for month in range(1, 13)]

    configs = [
        {
            "name": "혼인/자연증가",
            "org_id": "101",
            "tbl_id": "DT_1B8000H",
            "item_ids": ["T40", "T41", "T31"],
            "periods": yearly,
            "period_code": "Y",
            "class_selections": {
                "B": ["00", "11", "21", "22", "23", "24", "25", "26", "29", "31", "32", "33", "34", "35", "36", "37", "38", "39", "90"]
            },
        },
        {
            "name": "평균초혼연령",
            "org_id": "101",
            "tbl_id": "DT_1B83A05",
            "item_ids": ["T2"],
            "periods": yearly,
            "period_code": "Y",
            "class_selections": {
                "A": ["00", "11", "21", "22", "23", "24", "25", "26", "29", "31", "32", "33", "34", "35", "36", "37", "38", "39", "90"]
            },
        },
        {
            "name": "사교육비",
            "org_id": "101",
            "tbl_id": "DT_1PE105",
            "item_ids": ["T00"],
            "periods": yearly,
            "period_code": "Y",
            "class_selections": {
                "C": ["00", "11", "21", "22", "23", "24", "25", "26", "29", "31", "32", "33", "34", "35", "36", "37", "38", "39"]
            },
        },
        {
            "name": "경력단절여성",
            "org_id": "101",
            "tbl_id": "INH_1ES4H09S",
            "item_ids": ["T00", "T21"],
            "periods": yearly_to_2024,
            "period_code": "Y",
            "class_selections": {
                "SGG": ["00", "11", "21", "22", "23", "24", "25", "26", "29", "31", "32", "33", "34", "35", "36", "37", "38", "39"]
            },
        },
        {
            "name": "주택매매가격지수",
            "org_id": "101",
            "tbl_id": "DT_1YL13502E",
            "conn_path": "I3",
            "item_ids": ["sales"],
            "periods": housing_months,
            "period_code": "M",
            "class_selections": {
                "type": ["00"],
                "region": ["a0", "a7", "b1", "b2", "a9", "b3", "b4", "b5", "b6", "a8", "c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"],
            },
        },
        {
            "name": "주택전세가격지수",
            "org_id": "101",
            "tbl_id": "DT_1YL13602E",
            "conn_path": "I3",
            "item_ids": ["sales"],
            "periods": housing_months,
            "period_code": "M",
            "class_selections": {
                "type": ["00"],
                "region": ["a0", "a7", "b1", "b2", "a9", "b3", "b4", "b5", "b6", "a8", "c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"],
            },
        },
    ]

    for config in configs:
        print(f"Downloading {config['name']} ({config['tbl_id']})")
        info, long_df = fetch_and_melt(client, config)
        source_rows.append(
            {
                "자료명": config["name"],
                "통계표ID": config["tbl_id"],
                "통계표명": info["tblNm"],
                "출처": info["statLinkInfo"]["urlStatNm"],
                "수록기간": f"{config['periods'][0]}~{config['periods'][-1]}",
                "자료갱신일": info.get("renewalDate", ""),
                "통계표URL": f"https://kosis.kr/statHtml/statHtml.do?orgId={config['org_id']}&tblId={config['tbl_id']}",
            }
        )

        if config["name"] == "혼인/자연증가":
            factor_frames.append(select_series(long_df, "조혼인율", ["조혼인율"]))
            factor_frames.append(select_series(long_df, "혼인건수", ["혼인건수"]))
            population_frames.append(select_series(long_df, "자연증가율", ["자연증가율"]))
        elif config["name"] == "평균초혼연령":
            factor_frames.append(select_series(long_df, "평균초혼연령", ["아내"]))
        elif config["name"] == "사교육비":
            factor_frames.append(select_series(long_df, "사교육비"))
        elif config["name"] == "경력단절여성":
            married = select_series(long_df, "기혼여성_15_54세", ["15 - 54세 기혼여성"])
            interrupted = select_series(long_df, "경력단절여성인구", ["경력단절여성"])
            career = married.merge(interrupted, on=["지역", "연도"], how="outer")
            career["경력단절여성비율"] = career["경력단절여성인구"] / career["기혼여성_15_54세"] * 100
            factor_frames.append(career[["지역", "연도", "경력단절여성비율"]])
        elif config["name"] == "주택매매가격지수":
            factor_frames.append(select_series(long_df, "주택매매가격지수"))
        elif config["name"] == "주택전세가격지수":
            factor_frames.append(select_series(long_df, "주택전세가격지수"))

        time.sleep(0.4)

    print("Downloading 청년순이동률 (e-지방지표 822/554)")
    youth_migration = fetch_e_region_detail(
        unity_srvc_id="822",
        std_idct_id="554",
        variable="청년순이동률",
        start_year=2015,
        end_year=2025,
    )
    factor_frames.append(youth_migration)
    source_rows.append(
        {
            "자료명": "청년순이동률",
            "통계표ID": "eRegion:822/std:554",
            "통계표명": "청년순이동률",
            "출처": "KOSIS e-지방지표",
            "수록기간": "2015~2025",
            "자료갱신일": "",
            "통계표URL": "https://kosis.kr/visual/eRegionIndex/eRegionWhole.do",
        }
    )

    factor_panel = merge_frames(factor_frames).sort_values(["연도", "지역"]).reset_index(drop=True)
    population_panel = merge_frames(population_frames).sort_values(["연도", "지역"]).reset_index(drop=True)
    source_df = pd.DataFrame(source_rows)

    factor_path = OUT_DIR / "additional_factors_panel_2015_2025.csv"
    population_path = OUT_DIR / "population_change_panel_2015_2025.csv"
    source_path = OUT_DIR / "optional_kosis_sources.csv"

    factor_panel.to_csv(factor_path, index=False, encoding="utf-8-sig")
    population_panel.to_csv(population_path, index=False, encoding="utf-8-sig")
    source_df.to_csv(source_path, index=False, encoding="utf-8-sig")

    print(factor_path)
    print(population_path)
    print(source_path)
    print(factor_panel.tail())
    print(population_panel.tail())


if __name__ == "__main__":
    main()
