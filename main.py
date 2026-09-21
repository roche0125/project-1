import gzip
import json
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# ==========================================
# 1. 스트림릿 페이지 기본 설정
# ==========================================
st.set_page_config(
    page_title="전국 인구구조 지도",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ 전국 시군구 연령대별 인구 비율 지도")
st.write("2015~2026년 전국 읍·면·동 인구 데이터를 바탕으로 시군구별 인구 비율 변화를 보여주는 지도입니다.")

# 데이터 URL 정의
POPULATION_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
GEOJSON_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"

# ==========================================
# 2. 데이터 로드 및 전처리 (캐싱 적용)
# ==========================================
@st.cache_data
def load_raw_data():
    geojson_res = requests.get(GEOJSON_URL)
    geojson_data = geojson_res.json()

    # 인구 데이터 불러오기 (코드는 문자열 처리)
    df_pop = pd.read_csv(POPULATION_URL, compression='gzip', dtype={'코드': str})
    return geojson_data, df_pop

with st.spinner("데이터를 로드하는 중입니다..."):
    geojson_kr, df_pop_raw = load_raw_data()

# ------------------------------------------
# A. 사이드바 및 제어 영역
# ------------------------------------------
st.sidebar.header("⚙️ 지도 설정")

# 1. 지표 선택
metric_option = st.sidebar.radio(
    "📊 표시할 지표 선택",
    options=["고령인구 비율 (65세 이상)", "유소년 비율 (0~14세)", "청소년 비율 (15~19세)"],
    index=0
)

# 2. 연도 선택 슬라이더
min_year = int(df_pop_raw['연도'].min())
max_year = int(df_pop_raw['연도'].max())
selected_year = st.sidebar.slider(
    "📅 연도 선택",
    min_value=min_year,
    max_value=max_year,
    value=max_year,
    step=1
)

# 3. 시도 선택 드롭다운
sido_list = ["전국"] + sorted(list(df_pop_raw['시도'].dropna().unique()))
selected_sido = st.sidebar.selectbox("📍 시도 선택", options=sido_list)

# ------------------------------------------
# B. 선택된 연도 데이터 전처리 및 코드 보정
# ------------------------------------------
@st.cache_data
def process_year_data(df_raw, year):
    df_year = df_raw[df_raw['연도'] == year].copy()
    df_year['시군구코드'] = df_year['코드'].str[:5]

    # 행정구역 코드 개편 보정
    def fix_code(code):
        if pd.isna(code):
            return code
        if code == '47720':  # 군위군 (경북 47 -> 대구 27)
            return '27720'
        if code.startswith('42'):  # 강원도 -> 강원특별자치도 (42 -> 51)
            return '51' + code[2:]
        if code.startswith('45'):  # 전라북도 -> 전북특별자치도 (45 -> 52)
            return '52' + code[2:]
        return code

    df_year['시군구코드'] = df_year['시군구코드'].apply(fix_code)

    # 전체 연령 열 ('계_'로 시작)
    total_cols = [c for c in df_year.columns if c.startswith('계_')]

    # 연령대별 열 추출 함수
    def get_age_cols(start_age, end_age=None):
        cols = []
        for c in total_cols:
            age_str = c.replace('계_', '').replace('세', '').replace(' 이상', '')
            if age_str.isdigit():
                age = int(age_str)
                if end_age is not None:
                    if start_age <= age <= end_age:
                        cols.append(c)
                else:
                    if age >= start_age:
                        cols.append(c)
            elif age_str == '100' and (end_age is None or end_age >= 100):
                cols.append(c)
        return cols

    senior_cols = get_age_cols(65)      # 65세 이상
    youth_cols = get_age_cols(0, 14)    # 0~14세
    teen_cols = get_age_cols(15, 19)    # 15~19세

    # 인구 합산
    df_year['총인구'] = df_year[total_cols].sum(axis=1)
    df_year['고령인구'] = df_year[senior_cols].sum(axis=1)
    df_year['유소년인구'] = df_year[youth_cols].sum(axis=1)
    df_year['청소년인구'] = df_year[teen_cols].sum(axis=1)

    # 시군구 단위 집계
    df_sigungu = df_year.groupby('시군구코드').agg({
        '시도': 'first',
        '시군구': 'first',
        '총인구': 'sum',
        '고령인구': 'sum',
        '유소년인구': 'sum',
        '청소년인구': 'sum'
    }).reset_index()

    # 비율(%) 계산
    df_sigungu['고령화율'] = (df_sigungu['고령인구'] / df_sigungu['총인구'] * 100).round(2)
    df_sigungu['유소년비율'] = (df_sigungu['유소년인구'] / df_sigungu['총인구'] * 100).round(2)
    df_sigungu['청소년비율'] = (df_sigungu['청소년인구'] / df_sigungu['총인구'] * 100).round(2)

    return df_sigungu

df_sigungu_all = process_year_data(df_pop_raw, selected_year)

# ------------------------------------------
# C. 지표별 구간 나누기 및 설정
# ------------------------------------------
if metric_option == "고령인구 비율 (65세 이상)":
    target_col = '고령화율'
    target_name = '고령화율(%)'
    target_count_col = '고령인구'
    bins = [-1, 19, 23, 28, 38, 100]
    labels = ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']
    color_map = {
        '19% 미만': '#edf8fb',
        '19% 이상 ~ 23% 미만': '#b2e2e2',
        '23% 이상 ~ 28% 미만': '#66c2a4',
        '28% 이상 ~ 38% 미만': '#2ca25f',
        '38% 이상': '#006d2c'
    }

elif metric_option == "유소년 비율 (0~14세)":
    target_col = '유소년비율'
    target_name = '유소년 비율(%)'
    target_count_col = '유소년인구'
    bins = [-1, 8, 10, 12, 14, 100]
    labels = ['8% 미만', '8% 이상 ~ 10% 미만', '10% 이상 ~ 12% 미만', '12% 이상 ~ 14% 미만', '14% 이상']
    color_map = {
        '8% 미만': '#f7fcf5',
        '8% 이상 ~ 10% 미만': '#e5f5e0',
        '10% 이상 ~ 12% 미만': '#a1d99b',
        '12% 이상 ~ 14% 미만': '#41ab5d',
        '14% 이상': '#006d2c'
    }

else:  # 청소년 비율 (15~19세)
    target_col = '청소년비율'
    target_name = '청소년 비율(%)'
    target_count_col = '청소년인구'
    bins = [-1, 3.5, 4.5, 5.5, 6.5, 100]
    labels = ['3.5% 미만', '3.5% 이상 ~ 4.5% 미만', '4.5% 이상 ~ 5.5% 미만', '5.5% 이상 ~ 6.5% 미만', '6.5% 이상']
    color_map = {
        '3.5% 미만': '#eff3ff',
        '3.5% 이상 ~ 4.5% 미만': '#bdd7e7',
        '4.5% 이상 ~ 5.5% 미만': '#6baed6',
        '5.5% 이상 ~ 6.5% 미만': '#3182bd',
        '6.5% 이상': '#08519c'
    }

df_sigungu_all['구간'] = pd.cut(
    df_sigungu_all[target_col],
    bins=bins,
    labels=labels,
    right=False
).astype(str)

# 시도 필터링
if selected_sido != "전국":
    df_display = df_sigungu_all[df_sigungu_all['시도'] == selected_sido].copy()
else:
    df_display = df_sigungu_all.copy()

# ==========================================
# 3. 상단 지표 카드 (Metrics)
# ==========================================
total_pop_sum = df_display['총인구'].sum()
target_pop_sum = df_display[target_count_col].sum()
avg_ratio = (target_pop_sum / total_pop_sum * 100).round(2) if total_pop_sum > 0 else 0

max_row = df_display.loc[df_display[target_col].idxmax()] if not df_display.empty else None
min_row = df_display.loc[df_display[target_col].idxmin()] if not df_display.empty else None

col_m1, col_m2, col_m3 = st.columns(3)
with col_m1:
    region_label = "전국" if selected_sido == "전국" else selected_sido
    st.metric(label=f"📌 {region_label} 평균 {metric_option.split()[0]}", value=f"{avg_ratio}%")

with col_m2:
    if max_row is not None:
        st.metric(
            label=f"🔴 가장 높은 시군구",
            value=f"{max_row['시도']} {max_row['시군구']}",
            delta=f"{max_row[target_col]}%"
        )

with col_m3:
    if min_row is not None:
        st.metric(
            label=f"🔵 가장 낮은 시군구",
            value=f"{min_row['시도']} {min_row['시군구']}",
            delta=f"{min_row[target_col]}%"
        )

st.markdown("---")

# ==========================================
# 4. 지도 시각화 (Plotly)
# ==========================================
st.subheader(f"📍 {selected_year}년 {selected_sido} {metric_option} 지도")

fig = px.choropleth_map(
    df_display,
    geojson=geojson_kr,
    locations='시군구코드',
    featureidkey='properties.코드',
    color='구간',
    color_discrete_map=color_map,
    category_orders={'구간': labels},
    center={"lat": 35.9, "lon": 127.8} if selected_sido == "전국" else None,
    zoom=6.2 if selected_sido == "전국" else 8.5,
    map_style="white-bg",
    hover_name='시군구',
    hover_data={
        '시군구코드': False,
        '시도': True,
        target_col: ':.2f',
        target_count_col: ':,',
        '총인구': ':,'
    },
    labels={
        '구간': '비율 구간',
        target_col: target_name,
        '시도': '시도명',
        '총인구': '총인구(명)',
        target_count_col: '해당인구(명)'
    }
)

fig.update_layout(
    margin={"r":0, "t":0, "l":0, "b":0},
    legend=dict(
        title=f"<b>{target_name} 구간</b>",
        yanchor="top",
        y=0.98,
        xanchor="left",
        x=0.02,
        bgcolor="rgba(255, 255, 255, 0.8)",
        bordercolor="Gray",
        borderwidth=1
    )
)

st.plotly_chart(fig, use_container_width=True)

# GeoJSON과 매칭되지 않는 옛 코드 또는 경계 데이터 미포함 안내
geojson_codes = {f['properties']['코드'] for f in geojson_kr['features']}
display_codes = set(df_display['시군구코드'])
unmatched_codes = display_codes - geojson_codes

if unmatched_codes:
    st.caption("⚠️ **안내**: 과거 행정구역 개편이나 경계 데이터 미지원으로 인해 일부 지역은 지도에 회색으로 표시되거나 제외될 수 있습니다.")

# ==========================================
# 5. 하단 순위 표 (TOP 10 & BOTTOM 10)
# ==========================================
st.markdown("---")
st.subheader(f"📊 {selected_sido} {metric_option} 순위")

col1, col2 = st.columns(2)

with col1:
    st.markdown(f"### 🔴 {metric_option.split()[0]} 가장 높은 곳 TOP 10")
    top10 = df_display.sort_values(by=target_col, ascending=False).head(10)[['시도', '시군구', target_col, '총인구', target_count_col]]
    top10.columns = ['시도', '시군구', target_name, '총인구(명)', '해당인구(명)']
    st.dataframe(top10.reset_index(drop=True), use_container_width=True)

with col2:
    st.markdown(f"### 🔵 {metric_option.split()[0]} 가장 낮은 곳 TOP 10")
    bottom10 = df_display.sort_values(by=target_col, ascending=True).head(10)[['시도', '시군구', target_col, '총인구', target_count_col]]
    bottom10.columns = ['시도', '시군구', target_name, '총인구(명)', '해당인구(명)']
    st.dataframe(bottom10.reset_index(drop=True), use_container_width=True)
