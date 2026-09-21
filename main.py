import streamlit as st

st.title("첫 배포 확인 👋")
st.write("여기까지 보이면 배포 성공입니다.")

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
    page_title="전국 고령화 지도",
    page_icon="🗺️",
    layout="wide"
)

st.title("🗺️ 전국 시군구 고령화율 지도")
st.write("읍·면·동 인구 데이터를 기반으로 시군구별 65세 이상 고령인구 비율을 5단계로 나타낸 지도입니다.")

# 데이터 URL 정의
POPULATION_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
GEOJSON_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"

# ==========================================
# 2. 데이터 로드 및 전처리 (캐싱 적용)
# ==========================================
@st.cache_data
def load_data():
    # --------------------------------------
    # A. GeoJSON 경계 데이터 불러오기
    # --------------------------------------
    geojson_res = requests.get(GEOJSON_URL)
    geojson_data = geojson_res.json()

    # --------------------------------------
    # B. 인구 데이터 불러오기
    # --------------------------------------
    # 코드는 행정동 코드로 문자열(str) 형태 유지
    df_pop = pd.read_csv(POPULATION_URL, compression='gzip', dtype={'코드': str})
    
    # 1. 가장 최신 연도 추출
    latest_year = df_pop['연도'].max()
    df_latest = df_pop[df_pop['연도'] == latest_year].copy()

    # 2. 시군구 코드 생성 (행정동 코드 10자리 중 앞 5자리)
    df_latest['시군구코드'] = df_latest['코드'].str[:5]

    # 3. 65세 이상 및 전체 인구수 계산 (남녀 합친 '계_' 열 대상)
    # 총인구: '계_'로 시작하는 모든 나이 열의 합
    total_cols = [c for c in df_latest.columns if c.startswith('계_')]
    
    # 65세 이상 인구: '계_65세'부터 '계_100세 이상'까지 추출
    senior_cols = []
    for c in total_cols:
        # 나이 숫자가 65 이상이거나 '100세 이상'인 열 필터링
        age_str = c.replace('계_', '').replace('세', '').replace(' 이상', '')
        if age_str.isdigit() and int(age_str) >= 65:
            senior_cols.append(c)
        elif age_str == '100':  # 혹시 모를 예외 처리
            senior_cols.append(c)

    # 읍면동 단위 인구 합산
    df_latest['총인구'] = df_latest[total_cols].sum(axis=1)
    df_latest['고령인구'] = df_latest[senior_cols].sum(axis=1)

    # 4. 시군구(앞 5자리 코드) 단위로 집계
    df_sigungu = df_latest.groupby('시군구코드').agg({
        '시도': 'first',
        '시군구': 'first',
        '총인구': 'sum',
        '고령인구': 'sum'
    }).reset_index()

    # 5. 고령화율(%) 계산
    df_sigungu['고령화율'] = (df_sigungu['고령인구'] / df_sigungu['총인구'] * 100).round(2)

    # 6. 5단계 구간 나누기 (19%, 23%, 28%, 38% 기준)
    bins = [-1, 19, 23, 28, 38, 100]
    labels = ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']
    
    df_sigungu['고령화_구간'] = pd.cut(
        df_sigungu['고령화율'], 
        bins=bins, 
        labels=labels, 
        right=False
    )

    return latest_year, geojson_data, df_sigungu

# 데이터 실행 및 진행 상황 표시
with st.spinner("데이터를 로드하는 중입니다..."):
    latest_year, geojson_kr, df_sigungu = load_data()

st.subheader(f"📅 데이터 기준 연도: {latest_year}년")

# ==========================================
# 3. 지도 시각화 (Plotly Choropleth)
# ==========================================
# 5단계 범례 색상 설정 (연한 보라/파랑 -> 진한 빨강/보라)
color_discrete_map = {
    '19% 미만': '#edf8fb',
    '19% 이상 ~ 23% 미만': '#b2e2e2',
    '23% 이상 ~ 28% 미만': '#66c2a4',
    '28% 이상 ~ 38% 미만': '#2ca25f',
    '38% 이상': '#006d2c'
}

# 지도 생성
fig = px.choropleth_mapbox(
    df_sigungu,
    geojson=geojson_kr,
    locations='시군구코드',       # 데이터의 위치 열
    featureidkey='properties.코드',  # GeoJSON의 위치 ID 열 (5자리 코드)
    color='고령화_구간',           # 색상으로 지정할 범주형 열
    color_discrete_map=color_discrete_map,
    category_orders={'고령화_구간': ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']},
    center={"lat": 35.9, "lon": 127.8},  # 대한민국 중심 좌표
    zoom=6.2,
    mapbox_style="white-bg",      # 타일 배경 없는 깔끔한 흰 배경
    hover_name='시군구',
    hover_data={
        '시군구코드': False,
        '시도': True,
        '고령화율': ':.2f',
        '고령인구': ':,',
        '총인구': ':,'
    },
    labels={
        '고령화_구간': '고령화율 구간',
        '고령화율': '고령화율(%)',
        '시도': '시도명',
        '총인구': '총인구(명)',
        '고령인구': '고령인구(명)'
    }
)

# 지도 레이아웃 조정 (마진 제거 및 범례 디자인)
fig.update_layout(
    margin={"r":0, "t":0, "l":0, "b":0},
    legend=dict(
        title="<b>고령화율 구간</b>",
        yanchor="top",
        y=0.98,
        xanchor="left",
        x=0.02,
        bgcolor="rgba(255, 255, 255, 0.8)",
        bordercolor="Gray",
        borderwidth=1
    )
)

# 지도 출력
st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 4. 하단 순위 표 (TOP 10 & BOTTOM 10)
# ==========================================
st.markdown("---")
st.subheader("📊 시군구 고령화율 순위")

col1, col2 = st.columns(2)

# 고령화율 높은 곳 Top 10
with col1:
    st.markdown("### 🔴 고령화율 가장 높은 곳 TOP 10")
    top10 = df_sigungu.sort_values(by='고령화율', ascending=False).head(10)[['시도', '시군구', '고령화율', '총인구', '고령인구']]
    top10.columns = ['시도', '시군구', '고령화율(%)', '총인구(명)', '고령인구(명)']
    st.dataframe(top10.reset_index(drop=True), use_container_width=True)

# 고령화율 낮은 곳 Bottom 10
with col2:
    st.markdown("### 🔵 고령화율 가장 낮은 곳 TOP 10")
    bottom10 = df_sigungu.sort_values(by='고령화율', ascending=True).head(10)[['시도', '시군구', '고령화율', '총인구', '고령인구']]
    bottom10.columns = ['시도', '시군구', '고령화율(%)', '총인구(명)', '고령인구(명)']
    st.dataframe(bottom10.reset_index(drop=True), use_container_width=True)
