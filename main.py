import gzip
import json
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# ==========================================
# 1. 스트림릿 페이지 및 귀여운 커스텀 테마 설정
# ==========================================
st.set_page_config(
    page_title="말랑말랑 인구 지도 💖",
    page_icon="🎀",
    layout="wide"
)

# 귀여운 감성 CSS 스타일링
st.markdown("""
    <style>
    /* 전체 배경 및 폰트 */
    .stApp {
        background-color: #fff9fb;
        font-family: 'Pretendard', 'Nanum Gothic', sans-serif;
    }
    
    /* 타이틀 영역 스타일링 */
    .title-box {
        background: linear-gradient(135deg, #ffe6ea 0%, #f0e6ff 100%);
        padding: 1.8rem;
        border-radius: 24px;
        box-shadow: 0 8px 20px rgba(255, 182, 193, 0.25);
        border: 2px solid #ffccd5;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    .title-box h1 {
        color: #ff4d6d;
        font-weight: 800;
        margin-bottom: 0.3rem;
    }
    .title-box p {
        color: #6c757d;
        font-size: 0.95rem;
    }

    /* 사이드바 스타일링 */
    [data-testid="stSidebar"] {
        background-color: #fff0f3;
        border-right: 2px dashed #ffb3c1;
    }

    /* 카드 스타일 (Metrics용) */
    .cute-card {
        background: white;
        padding: 1.2rem;
        border-radius: 20px;
        border: 2px solid #ffccd5;
        box-shadow: 0 6px 15px rgba(255, 182, 193, 0.15);
        text-align: center;
    }
    .cute-card-title {
        font-size: 0.9rem;
        color: #ff758f;
        font-weight: 700;
        margin-bottom: 0.3rem;
    }
    .cute-card-value {
        font-size: 1.5rem;
        color: #2b2d42;
        font-weight: 800;
    }
    .cute-card-sub {
        font-size: 0.85rem;
        color: #ff4d6d;
        font-weight: 600;
        margin-top: 0.2rem;
    }
    </style>
""", unsafe_allow_html=True)

# 메인 타이틀
st.markdown("""
    <div class="title-box">
        <h1>🎀 대한민국 말랑말랑 인구 지도 🎀</h1>
        <p>우리 동네 연령대별 인구 비율을 파스텔 색상으로 확인해보세요 ✨</p>
    </div>
""", unsafe_allow_html=True)

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
    df_pop = pd.read_csv(POPULATION_URL, compression='gzip', dtype={'코드': str})
    return geojson_data, df_pop

with st.spinner("🧸 데이터를 뽀짝 불러오는 중이에요..."):
    geojson_kr, df_pop_raw = load_raw_data()

# ------------------------------------------
# A. 사이드바 제어 영역 (귀여운 컨셉)
# ------------------------------------------
st.sidebar.markdown("### 🎈 지도 제어판")

metric_option = st.sidebar.radio(
    "🌸 어떤 지표를 볼까요?",
    options=["고령인구 비율 (65세 이상)", "유소년 비율 (0~14세)", "청소년 비율 (15~19세)"],
    index=0
)

min_year = int(df_pop_raw['연도'].min())
max_year = int(df_pop_raw['연도'].max())
selected_year = st.sidebar.slider(
    "📅 궁금한 연도 선택",
    min_value=min_year,
    max_value=max_year,
    value=max_year,
    step=1
)

sido_list = ["전국"] + sorted(list(df_pop_raw['시도'].dropna().unique()))
selected_sido = st.sidebar.selectbox("📍 보고 싶은 시도 선택", options=sido_list)

# ------------------------------------------
# B. 데이터 전처리 및 코드 보정
# ------------------------------------------
@st.cache_data
def process_year_data(df_raw, year):
    df_year = df_raw[df_raw['연도'] == year].copy()
    df_year['시군구코드'] = df_year['코드'].str[:5]

    def fix_code(code):
        if pd.isna(code):
            return code
        if code == '47720':  # 군위군
            return '27720'
        if code.startswith('42'):  # 강원도
            return '51' + code[2:]
        if code.startswith('45'):  # 전라북도
            return '52' + code[2:]
        return code

    df_year['시군구코드'] = df_year['시군구코드'].apply(fix_code)

    total_cols = [c for c in df_year.columns if c.startswith('계_')]

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

    senior_cols = get_age_cols(65)
    youth_cols = get_age_cols(0, 14)
    teen_cols = get_age_cols(15, 19)

    df_year['총인구'] = df_year[total_cols].sum(axis=1)
    df_year['고령인구'] = df_year[senior_cols].sum(axis=1)
    df_year['유소년인구'] = df_year[youth_cols].sum(axis=1)
    df_year['청소년인구'] = df_year[teen_cols].sum(axis=1)

    df_sigungu = df_year.groupby('시군구코드').agg({
        '시도': 'first',
        '시군구': 'first',
        '총인구': 'sum',
        '고령인구': 'sum',
        '유소년인구': 'sum',
        '청소년인구': 'sum'
    }).reset_index()

    df_sigungu['고령화율'] = (df_sigungu['고령인구'] / df_sigungu['총인구'] * 100).round(2)
    df_sigungu['유소년비율'] = (df_sigungu['유소년인구'] / df_sigungu['총인구'] * 100).round(2)
    df_sigungu['청소년비율'] = (df_sigungu['청소년인구'] / df_sigungu['총인구'] * 100).round(2)

    return df_sigungu

df_sigungu_all = process_year_data(df_pop_raw, selected_year)

# ------------------------------------------
# C. 파스텔 톤 색상 조합 설정
# ------------------------------------------
if metric_option == "고령인구 비율 (65세 이상)":
    target_col = '고령화율'
    target_name = '고령화율(%)'
    target_count_col = '고령인구'
    bins = [-1, 19, 23, 28, 38, 100]
    labels = ['19% 미만', '19% 이상 ~ 23% 미만', '23% 이상 ~ 28% 미만', '28% 이상 ~ 38% 미만', '38% 이상']
    # 파스텔 핑크/보라
    color_map = {
        '19% 미만': '#fff0f3',
        '19% 이상 ~ 23% 미만': '#ffccd5',
        '23% 이상 ~ 28% 미만': '#ff4d6d',
        '28% 이상 ~ 38% 미만': '#c77dff',
        '38% 이상': '#7b2cbf'
    }

elif metric_option == "유소년 비율 (0~14세)":
    target_col = '유소년비율'
    target_name = '유소년 비율(%)'
    target_count_col = '유소년인구'
    bins = [-1, 8, 10, 12, 14, 100]
    labels = ['8% 미만', '8% 이상 ~ 10% 미만', '10% 이상 ~ 12% 미만', '12% 이상 ~ 14% 미만', '14% 이상']
    # 파스텔 민트/라임
    color_map = {
        '8% 미만': '#f7fcf5',
        '8% 이상 ~ 10% 미만': '#c7f9cc',
        '10% 이상 ~ 12% 미만': '#80ed99',
        '12% 이상 ~ 14% 미만': '#57cc99',
        '14% 이상': '#22577a'
    }

else:  # 청소년 비율 (15~19세)
    target_col = '청소년비율'
    target_name = '청소년 비율(%)'
    target_count_col = '청소년인구'
    bins = [-1, 3.5, 4.5, 5.5, 6.5, 100]
    labels = ['3.5% 미만', '3.5% 이상 ~ 4.5% 미만', '4.5% 이상 ~ 5.5% 미만', '5.5% 이상 ~ 6.5% 미만', '6.5% 이상']
    # 파스텔 하늘/블루
    color_map = {
        '3.5% 미만': '#f0f8ff',
        '3.5% 이상 ~ 4.5% 미만': '#e0f2fe',
        '4.5% 이상 ~ 5.5% 미만': '#7dd3fc',
        '5.5% 이상 ~ 6.5% 미만': '#38bdf8',
        '6.5% 이상': '#0284c7'
    }

df_sigungu_all['구간'] = pd.cut(
    df_sigungu_all[target_col],
    bins=bins,
    labels=labels,
    right=False
).astype(str)

if selected_sido != "전국":
    df_display = df_sigungu_all[df_sigungu_all['시도'] == selected_sido].copy()
else:
    df_display = df_sigungu_all.copy()

# ==========================================
# 3. 귀여운 지표 카드 (Metrics)
# ==========================================
total_pop_sum = df_display['총인구'].sum()
target_pop_sum = df_display[target_count_col].sum()
avg_ratio = (target_pop_sum / total_pop_sum * 100).round(2) if total_pop_sum > 0 else 0

max_row = df_display.loc[df_display[target_col].idxmax()] if not df_display.empty else None
min_row = df_display.loc[df_display[target_col].idxmin()] if not df_display.empty else None

col_m1, col_m2, col_m3 = st.columns(3)
region_label = "전국" if selected_sido == "전국" else selected_sido

with col_m1:
    st.markdown(f"""
        <div class="cute-card">
            <div class="cute-card-title">✨ {region_label} 평균 {metric_option.split()[0]}</div>
            <div class="cute-card-value">{avg_ratio}%</div>
        </div>
    """, unsafe_allow_html=True)

with col_m2:
    if max_row is not None:
        st.markdown(f"""
            <div class="cute-card">
                <div class="cute-card-title">🌸 가장 높은 곳</div>
                <div class="cute-card-value">{max_row['시도']} {max_row['시군구']}</div>
                <div class="cute-card-sub">▲ {max_row[target_col]}%</div>
            </div>
        """, unsafe_allow_html=True)

with col_m3:
    if min_row is not None:
        st.markdown(f"""
            <div class="cute-card">
                <div class="cute-card-title">🌱 가장 낮은 곳</div>
                <div class="cute-card-value">{min_row['시도']} {min_row['시군구']}</div>
                <div class="cute-card-sub">▼ {min_row[target_col]}%</div>
            </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 4. 지도 시각화 (Plotly)
# ==========================================
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
        title=f"<b>💖 {target_name}</b>",
        yanchor="top",
        y=0.98,
        xanchor="left",
        x=0.02,
        bgcolor="rgba(255, 255, 255, 0.9)",
        bordercolor="#ffccd5",
        borderwidth=2
    )
)

st.plotly_chart(fig, use_container_width=True)

# 안내 문구
geojson_codes = {f['properties']['코드'] for f in geojson_kr['features']}
display_codes = set(df_display['시군구코드'])
unmatched_codes = display_codes - geojson_codes

if unmatched_codes:
    st.caption("💌 **알림**: 과거 행정구역 개편이나 경계 파일 부족으로 인해 회색으로 표시되는 예쁜 지역이 있을 수 있어요!")

# ==========================================
# 5. 하단 순위 표 (TOP 10 & BOTTOM 10)
# ==========================================
st.markdown("---")
st.markdown(f"### 📊 {selected_sido} {metric_option} 랭킹")

col1, col2 = st.columns(2)

with col1:
    st.markdown(f"#### 💖 {metric_option.split()[0]} 높은 순 TOP 10")
    top10 = df_display.sort_values(by=target_col, ascending=False).head(10)[['시도', '시군구', target_col, '총인구', target_count_col]]
    top10.columns = ['시도', '시군구', target_name, '총인구(명)', '해당인구(명)']
    st.dataframe(top10.reset_index(drop=True), use_container_width=True)

with col2:
    st.markdown(f"#### 💙 {metric_option.split()[0]} 낮은 순 TOP 10")
    bottom10 = df_display.sort_values(by=target_col, ascending=True).head(10)[['시도', '시군구', target_col, '총인구', target_count_col]]
    bottom10.columns = ['시도', '시군구', target_name, '총인구(명)', '해당인구(명)']
    st.dataframe(bottom10.reset_index(drop=True), use_container_width=True)
