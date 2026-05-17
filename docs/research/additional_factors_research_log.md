# 추가 출산율 요인 조사 로그

작성일: 2026-05-17 20:42 KST  
브랜치: `research/additional-fertility-factors`  
워크트리: `/Users/kimgt/Developer/Project/data_science/population/.worktrees/additional-fertility-factors`

## 목적

과제 안내문에 제시된 9개 요인과 PDF에서 확인한 개인소득 변수 외에, 교수님께서 "추가적으로 더 고려해도 된다"고 답변한 전제에서 확장 분석 후보를 정리한다. 본 단계에서는 기존 노트북을 바로 수정하지 않고, 추가할 가치가 있는 변수와 데이터 리스크를 먼저 기록한다.

## 조사 방식

- Chrome으로 KOSIS 주제별 통계 페이지를 열어 인구, 가족, 노동, 소득, 주거, 교육, 안전, 보건 등 과제와 연결되는 주제 묶음을 확인했다.
- Chrome에서 `한국 저출산 원인 주거비 사교육비 혼인율 경력단절 2025`를 검색해 최근 논의 키워드를 훑었다. 검색 결과 요약은 참고용으로만 사용하고, 근거는 아래 원문/공식 자료 링크에 맞췄다.
- KOSIS/e-지방지표에서 시도-연도 패널로 만들 수 있는지 우선 확인했다.
- OECD, KDI, Yonhap 등 연구/보도 자료에서 변수 선택의 해석 근거를 확인했다.

## 확인한 핵심 출처

| 구분 | 출처 | 확인 내용 |
| --- | --- | --- |
| 공식 통계 포털 | [KOSIS 주제별 통계](https://kosis.kr/statisticsList/statisticsListIndex.do?vwcd=MT_ZTITLE&menuId=M_01_01#content-group) | 인구, 범죄ㆍ안전, 노동, 소득ㆍ소비ㆍ자산, 보건, 복지, 교육ㆍ훈련, 주거, 물가, 지역통계 등 과제 변수군 확인 |
| 지역 지표 후보 | [KOSIS e-지방지표 지표체계도](https://kosis.kr/visual/eRegionIndex/index.do) | 평균 초혼연령, 청년순이동률, 1인가구비율, 조혼인율, 주택 매매/전세/월세가격지수, 경력단절여성인구 등 후보 확인 |
| 혼인 메커니즘 | [KOSIS 초혼연령](https://kosis.kr/visual/populationKorea/PopulationDashBoardDetail.do?areaId=&areaNm=&listId=A_02&statJipyoId=3770&vStatJipyoId=5282) | 초혼연령은 2000~2025년까지 제공되며 2025년 남 33.85세, 여 31.62세로 확인 |
| 사교육비 | [KOSIS 100대 지표: 학생 1인당 월평균 사교육비](https://kosis.kr/visual/nsportalStats/chart.do?grp_view_at=01&num=1142) | 2016~2025년 지표가 있고, 2025년 45.8만원으로 확인. 지역별 표는 KOSIS `초중고사교육비조사`에서 추가 확인 필요 |
| 인구 이동 | [KOSIS 국내인구이동통계 최근수록자료](https://kosis.kr/serviceInfo/newContrainDataDetail.do?boardIdx=1976003&boardOrgId=101) | 시도/성/연령별 이동자수, 순이동자수, 인구이동률이 월 단위로 최근까지 수록됨 |
| 국제 연구 | [OECD Economic Surveys: Korea 2024, population decline section](https://www.oecd.org/en/publications/oecd-economic-surveys-korea-2024_c243e16a-en/full-report/responding-to-population-decline_7f6620e6.html) | 결혼율 하락, 청년 경제 여건, 주거비 부담, 사교육비, 일-가정 양립을 저출산 관련 요인으로 설명 |
| 국제 연구 | [OECD Korea's Unborn Future, 2025](https://www.oecd.org/content/dam/oecd/en/publications/reports/2025/03/korea-s-unborn-future_1b836111/005ce8f7-en.pdf) | 주거비, 사교육비, 여성 고용/돌봄 부담, 수도권 집중, 1인 가구 증가를 구조적 요인으로 논의 |
| 국내 연구 | [KDI Focus: 여성의 경력단절 우려와 출산율 감소](https://www.kdi.re.kr/research/focusView?pub_no=18306) | child penalty와 경력단절 우려가 출산율 감소와 연결될 수 있음을 제시 |
| 최근 보도 | [Yonhap, 2026-01-28](https://en.yna.co.kr/view/AEN20260128004700320) | 2025년 출생아 증가가 혼인 증가와 연결된다는 정부 자료 기반 보도. 한국은 혼외출산이 드물어 혼인 증가가 출생 증가에 선행하기 쉽다고 설명 |
| 최근 보도 | [The Korea Times, 2025-03-21](https://www.koreatimes.co.kr/economy/policy/20250321/bok-head-calls-for-painstaking-reform-to-bolster-low-birthrates) | 한국은행 총재 발언을 통해 수도권 집중, 교육 경쟁, 일자리/주거/양육 불확실성이 함께 거론됨 |

## 조사 메모

- 기존 과제 변수 중 `주거안정률`은 점유 형태 중심이라 주택 가격·전세·월세 부담을 직접 측정하지 못한다.
- 기존 `청년고용률`은 청년의 "지역 잔류/유입" 문제를 보여주지 못하므로 `청년순이동률`이 보조 설명력이 있을 수 있다.
- 기존 `맞벌이 가구`는 여성의 출산 이후 경력 손실이나 일-가정 양립 비용을 직접 측정하지 못하므로 `경력단절여성인구`, 가능하면 `육아휴직` 지표가 유용하다.
- `혼인율/초혼연령`은 합계출산율과 매우 가까운 인구학적 메커니즘이라 설명력은 크지만, 정책 요인처럼 해석하면 내생성 문제가 생길 수 있다. 따라서 "영향 요인"이라기보다 "중간 메커니즘/통제 변수"로 표시하는 편이 안전하다.
- `사교육비`는 OECD와 국내 여론에서 반복적으로 언급되는 요인이며, 발표에서 청중이 이해하기 쉽다. 단, 출산 결정을 하는 청년세대와 현재 초중고 사교육비 사이에는 시차가 있으므로 해석에서는 "예상 양육비 부담"의 대리변수라고 써야 한다.

## 다음 작업 제안

1. KOSIS에서 실제 엑셀 파일을 추가 다운로드한다.
2. 파일명과 출처, 수록기간, 단위를 `data_inventory`에 추가한다.
3. 기존 노트북에는 "확장 분석" 섹션으로만 붙이고, 교수님 방식의 기본 분석 결과와 분리한다.
4. 추가 변수는 complete-case와 보간 버전을 모두 돌리되, 표본 수가 지나치게 줄면 순위 비교만 보조로 제시한다.
