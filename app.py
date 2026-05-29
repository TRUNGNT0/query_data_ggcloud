import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from collections import Counter
import re
import json
from google.cloud import bigquery
from google.cloud import storage
import io
import numpy as np

# ========== CẤU HÌNH STREAMLIT ==========
st.set_page_config(
    page_title="News Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========== CSS ĐẶC BIỆT ==========
st.markdown("""
    <style>
        :root { color-scheme: dark; }
        body { background-color: #061a26; color: #e8f8ff; }
        .stApp {
            background: linear-gradient(135deg, #02111b 0%, #062836 50%, #051d2c 100%);
            color: #eef8ff;
        }
        .css-18e3th9 { background-color: transparent; }
        .css-1d391kg { background-color: rgba(3, 29, 44, 0.82); }
        .stButton>button { background-color: #0fb5ff; color: white; border: none; }
        .stButton>button:hover { background-color: #24c5ff; color: white; }
        .st-b8 { background: rgba(255,255,255,0.05); }
        .block-container { padding: 1.2rem 1.5rem 0 1.5rem; }
        .reportview-container .main .block-container { padding-top: 1rem; }
        .css-1aumxhk { background: rgba(4, 29, 45, 0.7); }
        .stSidebar { background-color: #031519; }
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 { color: #d3f9ff; }
        .stMetric {
            background: rgba(6, 29, 46, 0.85);
            border: 1px solid rgba(15, 181, 255, 0.25);
            border-radius: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)

# ========== KHỞI TẠO SESSION STATE ==========
if 'df_cache' not in st.session_state:
    st.session_state.df_cache = None
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = None
if 'bigquery_error' not in st.session_state:
    st.session_state.bigquery_error = None

# ========== HELPER FUNCTIONS ==========
STOPWORDS = {
    'và', 'của', 'trong', 'với', 'là', 'các', 'cho', 'trên', 'tại', 'về',
    'những', 'đó', 'một', 'nhiều', 'giữa', 'bị', 'đã', 'có', 'từ', 'the',
    'this', 'that', 'theo', 'khi', 'vào', 'sau', 'được', 'không', 'còn',
    'đây', 'như', 'hay', 'lên', 'ra', 'đến', 'nên', 'vì', 'rằng'
}


def normalize_keywords(keywords):
    """
    FIX: Điều chỉnh lại để chấp nhận cụm 2-3 từ là mặc định.
    - Bỏ điều kiện `2 <= len(w) <= 5` (đây là check ký tự sai)
    - Giữ từ có ít nhất 2 ký tự thay vì 2-5 ký tự
    - Ưu tiên cụm 2-3 từ, vẫn giữ từ đơn nếu dài >= 3 ký tự
    """
    if isinstance(keywords, list):
        candidates = [str(k) for k in keywords if k]
    elif isinstance(keywords, str):
        candidates = []
        for chunk in re.split(r'[;/]+', keywords):
            candidates.extend(re.split(r'[,]+', chunk))
    else:
        return []

    normalized = []
    for item in candidates:
        item_text = str(item).strip()
        if not item_text:
            continue
        # Loại bỏ ký tự đặc biệt
        item_text = re.sub(r'["\'\(\)\[\]\\/]+', ' ', item_text)
        item_text = re.sub(r'\s+', ' ', item_text).strip().lower()

        # Tách từ và lọc stopwords
        words = [w for w in re.split(r'\s+', item_text) if w]
        # FIX: Chỉ lọc stopwords, giữ mọi từ có >= 2 ký tự (không giới hạn 5 ký tự)
        filtered_words = [w for w in words if w not in STOPWORDS and len(w) >= 2]

        if not filtered_words:
            continue

        word_count = len(filtered_words)
        if word_count >= 2:
            # FIX: Ưu tiên cụm 2-3 từ; nếu dài hơn thì lấy 3 từ đầu
            normalized.append(' '.join(filtered_words[:3]))
        else:
            # Từ đơn: chỉ giữ nếu đủ dài (>= 3 ký tự) để tránh nhiễu
            if len(filtered_words[0]) >= 3:
                normalized.append(filtered_words[0])

    return normalized


def get_keyword_counts(df, top_n=40):
    all_keywords = []
    if 'keywords' in df.columns:
        for row in df['keywords'].dropna():
            all_keywords.extend(normalize_keywords(row))
    return Counter(all_keywords).most_common(top_n)


def build_topic_events(df, top_n=4):
    if 'category' not in df.columns:
        return []
    df = df.copy()
    if 'published_date' in df.columns:
        recent_threshold = datetime.now().date() - timedelta(days=7)
        df_recent = df[df['published_date'] >= recent_threshold]
    else:
        df_recent = df

    category_counts = df['category'].value_counts()
    recent_counts = df_recent['category'].value_counts()

    events = []
    for category, count in category_counts.items():
        recent_count = int(recent_counts.get(category, 0))
        burst = min(100, max(10, int((recent_count / max(1, count)) * 100)))
        keywords = []
        if 'keywords' in df.columns:
            category_keywords = []
            for row in df[df['category'] == category]['keywords'].dropna():
                category_keywords.extend(normalize_keywords(row))
            keywords = [kw for kw, _ in Counter(category_keywords).most_common(5)]
        events.append({
            'name': category,
            'keywords': ', '.join(keywords[:5]),
            'count': int(count),
            'burst': burst,
            'recent_count': recent_count
        })

    events = sorted(events, key=lambda x: x['burst'], reverse=True)[:top_n]
    return events


def simple_sentiment_analysis(text):
    positive = ['tốt', 'tăng', 'hoạt động', 'thắng', 'tin vui', 'mạnh', 'vươn lên', 'đạt']
    negative = ['lo ngại', 'khó', 'thiệt', 'sụp', 'giảm', 'sự cố', 'nguy', 'bùng nổ', 'tấn công']
    if not isinstance(text, str):
        return 0
    text_lower = text.lower()
    score = sum(word in text_lower for word in positive) - sum(word in text_lower for word in negative)
    return score


def aggregate_sentiment(df):
    if 'sentiment' in df.columns:
        sentiments = df['sentiment'].dropna().tolist()
    else:
        sentiments = [simple_sentiment_analysis(text) for text in df['description'].fillna('')]
    positive = sum(1 for v in sentiments if v > 0)
    negative = sum(1 for v in sentiments if v < 0)
    neutral = len(sentiments) - positive - negative
    return {'positive': positive, 'negative': negative, 'neutral': neutral}


def build_keyword_network(df, top_n=20):
    counts = Counter()
    if 'keywords' in df.columns:
        for row in df['keywords'].dropna():
            counts.update(normalize_keywords(row))
    top_keywords = [kw for kw, _ in counts.most_common(top_n)]
    cooccurrence = Counter()
    for row in df['keywords'].dropna():
        normalized = [kw for kw in normalize_keywords(row) if kw in top_keywords]
        for i in range(len(normalized)):
            for j in range(i + 1, len(normalized)):
                cooccurrence[tuple(sorted([normalized[i], normalized[j]]))] += 1
    nodes = [{'id': kw, 'size': counts[kw]} for kw in top_keywords]
    edges = [{'from': a, 'to': b, 'weight': weight} for (a, b), weight in cooccurrence.items() if weight > 1]
    return nodes, edges


def prepare_topic_tree(df):
    rows = []
    if 'category' in df.columns:
        for category in df['category'].dropna().unique():
            category_df = df[df['category'] == category]
            keywords = Counter()
            if 'keywords' in category_df.columns:
                for row in category_df['keywords'].dropna():
                    keywords.update(normalize_keywords(row))
            for kw, count in keywords.most_common(8):
                rows.append({'category': category, 'keyword': kw.title(), 'count': count})
    return pd.DataFrame(rows)


# ========== ĐỌC DỮ LIỆU TỪ BIGQUERY ==========
@st.cache_data(ttl=3600)
def load_data_from_bigquery():
    try:
        client = bigquery.Client()
        query = """
            SELECT 
                title,
                publish_date AS published_date,
                link,
                description,
                category,
                clean_keywords
            FROM `project-ceb4f683-ad1a-44e3-8d8.bigdata_project.vnexpress_world_news`
            WHERE publish_date >= CURRENT_DATE() - 90
            ORDER BY publish_date DESC
        """
        df = client.query(query).to_dataframe()
        df['published_date'] = pd.to_datetime(df['published_date']).dt.date
        df['keywords'] = df['clean_keywords'].apply(
            lambda x: ', '.join(x) if isinstance(x, list) else str(x)
        )
        st.session_state.bigquery_error = None
        return df
    except Exception as e:
        st.session_state.bigquery_error = str(e)
        return None


@st.cache_data(ttl=3600)
def load_sample_data():
    """Dữ liệu mẫu mở rộng để test đủ keyword"""
    data = {
        'title': [
            'Quy định mới phủ bóng lên giấc mơ thẻ xanh Mỹ',
            'Những nhà hàng đặc sản Texas lao đao vì giá thịt tăng phi mã',
            'Sát thủ bóng đêm của Hezbollah khiến Israel lo ngại',
            'Ukraine sẽ mua 20 tiêm kích Gripen hiện đại nhất của Thụy Điển',
            'Tổng Bí thư, Chủ tịch nước Tô Lâm hội kiến Nhà Vua Thái Lan',
            'Xung đột Gaza leo thang sau các cuộc không kích mới',
            'Mỹ áp thêm lệnh trừng phạt lên Nga vì vấn đề Ukraine',
            'Hàn Quốc và Nhật Bản tăng cường hợp tác quân sự',
            'Trung Quốc phản đối các tuyên bố chủ quyền Biển Đông',
            'EU thảo luận gói viện trợ mới cho Ukraine',
            'NATO họp bàn về chiến lược phòng thủ năm 2025',
            'Lũ lụt nghiêm trọng tàn phá miền Trung châu Âu',
            'Khủng hoảng di cư tại biên giới Hy Lạp và Thổ Nhĩ Kỳ',
            'Israel mở chiến dịch quân sự tại miền Nam Gaza',
            'Nga tấn công cơ sở hạ tầng năng lượng Ukraine',
        ],
        'category': [
            'Chính trị', 'Kinh tế', 'Xung đột', 'Quân sự', 'Ngoại giao',
            'Xung đột', 'Chính trị', 'Quân sự', 'Ngoại giao', 'Chính trị',
            'Quân sự', 'Thiên tai', 'Di cư', 'Xung đột', 'Xung đột'
        ],
        'published_date': [
            (datetime.now() - timedelta(days=i % 10)).date() for i in range(15)
        ],
        'keywords': [
            'Quy định mới, Mỹ, Thẻ xanh, Nhập cư',
            'Texas, Nhà hàng đặc sản, Giá thịt, Lạm phát',
            'Hezbollah, Israel, Drone chiến đấu, Tấn công',
            'Ukraine, Gripen, Thụy Điển, Hợp đồng quân sự',
            'Tô Lâm, Thái Lan, Hội kiến, Ngoại giao',
            'Gaza, Không kích, Xung đột leo thang, Israel',
            'Trừng phạt Nga, Mỹ, Lệnh trừng phạt, Ukraine',
            'Hàn Quốc, Nhật Bản, Hợp tác quân sự, Liên minh',
            'Trung Quốc, Biển Đông, Chủ quyền, Tranh chấp',
            'EU, Viện trợ Ukraine, Gói hỗ trợ, Châu Âu',
            'NATO, Chiến lược phòng thủ, Hội nghị, Liên minh',
            'Lũ lụt, Châu Âu, Thiệt hại, Khẩn cấp',
            'Di cư, Hy Lạp, Thổ Nhĩ Kỳ, Biên giới',
            'Israel, Gaza, Chiến dịch quân sự, Xung đột',
            'Nga, Ukraine, Cơ sở hạ tầng, Tấn công tên lửa',
        ],
        'description': [
            'Thay đổi mới trong quy định xin thẻ xanh của Mỹ khiến người nhập cư lo ngại.',
            'Những nhà hàng nổi tiếng ở Texas đang phải vật lộn vì giá nguyên liệu tăng cao.',
            'Quan chức Israel ví drone của Hezbollah như cơn ác mộng với quân đội.',
            'Ukraine dự kiến đặt mua 20 tiêm kích Gripen hiện đại của Thụy Điển.',
            'Tổng Bí thư hội kiến Nhà Vua Thái Lan trong khuôn khổ chuyến thăm cấp nhà nước.',
            'Các cuộc không kích mới tại Gaza khiến xung đột leo thang nghiêm trọng.',
            'Washington mở rộng lệnh trừng phạt nhằm vào các thực thể tài chính Nga.',
            'Seoul và Tokyo tăng cường phối hợp trong bối cảnh căng thẳng khu vực.',
            'Bắc Kinh phản đối mạnh mẽ các tuyên bố chủ quyền Biển Đông từ các bên.',
            'Liên minh châu Âu xem xét gói hỗ trợ tài chính và quân sự mới cho Ukraine.',
            'Các bộ trưởng quốc phòng NATO thảo luận chiến lược ứng phó các mối đe dọa mới.',
            'Trận lũ lịch sử tàn phá nhiều quốc gia miền Trung châu Âu, hàng nghìn người sơ tán.',
            'Dòng người di cư tại biên giới Hy Lạp - Thổ Nhĩ Kỳ tạo ra khủng hoảng nhân đạo.',
            'Lực lượng Israel mở rộng hoạt động quân sự tại miền Nam dải Gaza.',
            'Tên lửa Nga tấn công nhiều cơ sở điện và năng lượng tại miền Đông Ukraine.',
        ],
        'link': [
            f'https://vnexpress.net/bai-viet-{i}.html' for i in range(1, 16)
        ]
    }
    return pd.DataFrame(data)


# ========== LOAD DỮ LIỆU ==========
source_options = ['BigQuery', 'Mẫu nội bộ', 'Upload JSON/CSV']
data_source = st.sidebar.selectbox('Nguồn dữ liệu', source_options, index=0)
uploaded_file = st.sidebar.file_uploader('Tải lên dữ liệu JSON/CSV', type=['json', 'csv'])
use_local_sample = False

if uploaded_file is not None:
    try:
        if uploaded_file.type == 'application/json':
            try:
                df = pd.read_json(uploaded_file, lines=True)
            except ValueError:
                uploaded_file.seek(0)
                df = pd.read_json(uploaded_file)
        else:
            df = pd.read_csv(uploaded_file)
        if 'published_date' in df.columns:
            df['published_date'] = pd.to_datetime(df['published_date']).dt.date
        st.sidebar.success('✅ Dữ liệu tải lên thành công.')
    except Exception as e:
        st.sidebar.error(f'❌ Không đọc được file: {e}')
        df = load_sample_data()
        use_local_sample = True
elif data_source == 'BigQuery':
    st.session_state.df_cache = load_data_from_bigquery()
    if st.session_state.df_cache is None:
        df = load_sample_data()
        use_local_sample = True
    else:
        df = st.session_state.df_cache
else:
    df = load_sample_data()
    use_local_sample = True

if 'clean_keywords' in df.columns and 'keywords' not in df.columns:
    df['keywords'] = df['clean_keywords'].apply(
        lambda x: ', '.join(x) if isinstance(x, list) else (str(x) if pd.notna(x) else '')
    )
elif 'keywords' not in df.columns:
    df['keywords'] = ''

if 'published_date' in df.columns:
    df['published_date'] = pd.to_datetime(df['published_date']).dt.date

if st.session_state.bigquery_error:
    st.warning('⚠️ Không thể kết nối BigQuery. Ứng dụng sẽ dùng dữ liệu mẫu hoặc bạn có thể tải file CSV/JSON.')
    st.info(st.session_state.bigquery_error)

st.sidebar.markdown('---')
st.sidebar.markdown('## Bộ lọc nâng cao')
start_date, end_date = st.sidebar.date_input(
    'Khoảng thời gian',
    value=(datetime.now().date() - timedelta(days=14), datetime.now().date()),
    max_value=datetime.now().date()
)
category_filter = st.sidebar.multiselect(
    'Danh mục',
    options=df['category'].dropna().unique().tolist() if 'category' in df.columns else [],
    default=df['category'].dropna().unique().tolist() if 'category' in df.columns else []
)

# ========== DỮ LIỆU CHUNG ==========
filtered = df.copy()
if 'published_date' in filtered.columns:
    filtered = filtered[(filtered['published_date'] >= start_date) & (filtered['published_date'] <= end_date)]
if category_filter:
    filtered = filtered[filtered['category'].isin(category_filter)]

keyword_counts = get_keyword_counts(filtered, top_n=40)
trending_events = build_topic_events(filtered, top_n=4)
sentiment_counts = aggregate_sentiment(filtered)
keyword_nodes, keyword_edges = build_keyword_network(filtered, top_n=20)
topic_df = prepare_topic_tree(filtered)

# ========== HEADER ==========
st.markdown('# News Intelligence Dashboard')
st.markdown('**Dark mode analytics dashboard cho tin tức realtime & social listening.**')

metric1, metric2, metric3, metric4 = st.columns(4)
metric1.metric('Tổng bài viết', len(filtered), delta=f'{len(filtered) - len(df):+d}')
metric2.metric('Số chủ đề', filtered['category'].nunique() if 'category' in filtered.columns else 0)
metric3.metric('Chủ đề hot', len(trending_events))
metric4.metric('Từ khóa hot', len(keyword_counts))

# ========== TRENDING KEYWORDS ==========
st.markdown('## Trending Keywords')
kw_col1, kw_col2, kw_col3 = st.columns([1.4, 1.6, 1.0])

with kw_col1:
    st.markdown('### Top Keywords')
    if keyword_counts:
        # FIX: Lọc cụm 2-3 từ (mặc định mới), fallback sang tất cả nếu không đủ
        phrase_counts_2_3 = Counter()
        phrase_counts_all = Counter()

        for kw, count in keyword_counts:
            word_count = len(kw.split())
            phrase_counts_all[kw] = count
            if 2 <= word_count <= 3:
                phrase_counts_2_3[kw] = count

        # Ưu tiên cụm 2-3 từ; nếu < 5 kết quả thì dùng tất cả
        if len(phrase_counts_2_3) >= 5:
            top_phrases = phrase_counts_2_3.most_common(20)
            label_note = "cụm 2–3 từ"
        else:
            top_phrases = phrase_counts_all.most_common(20)
            label_note = "tất cả từ khóa"

        st.caption(f"Hiển thị: {label_note} | Tổng: {len(top_phrases)} từ khóa")

        if top_phrases:
            total_count = sum(cnt for _, cnt in top_phrases)
            table_data = []
            for idx, (ph, cnt) in enumerate(top_phrases[:15], 1):
                tf = cnt / max(1, total_count)
                # IDF: log(N / df) — dùng rank làm proxy cho df
                idf = np.log(max(2, len(top_phrases)) / max(1, idx))
                trend_score = round(tf * idf * 100, 2)
                table_data.append({
                    'STT': idx,
                    'Cụm từ hot': ph.title(),
                    'Số lần xuất hiện': cnt,
                    'Điểm Trend': trend_score
                })

            kw_df = pd.DataFrame(table_data)
            st.dataframe(
                kw_df,
                use_container_width=True,
                height=min(60 + len(table_data) * 35, 500),
                hide_index=True
            )
        else:
            st.info('Chưa có từ khóa nào được tìm thấy.')
    else:
        st.info('Không đủ dữ liệu từ khóa để hiển thị.')

with kw_col2:
    st.markdown('### Bài viết nổi bật')
    if not filtered.empty:
        top_k = [kw for kw, _ in keyword_counts][:20]

        def score_row(row):
            kws = normalize_keywords(row.get('keywords', ''))
            matches = sum(1 for k in kws if k in top_k)
            pub = row.get('published_date', None)
            try:
                days = (datetime.now().date() - pd.to_datetime(pub).date()).days if pub is not None else 0
            except Exception:
                days = 0
            recency = max(0, 7 - days)
            return matches * 2 + recency

        tmp = filtered.copy()
        tmp['score'] = tmp.apply(score_row, axis=1)
        top_articles = tmp.sort_values(['score', 'published_date'], ascending=[False, False]).head(12)
        for _, r in top_articles.iterrows():
            title = r.get('title', 'Không có tiêu đề')
            link = r.get('link', '#')
            cat = r.get('category', 'Không xác định')
            pub = r.get('published_date', '')
            desc = r.get('description', '')
            st.markdown(f"**[{title}]({link})**  — _{cat}_ — _{pub}_")
            if desc:
                st.markdown(f"{str(desc)[:200]}...")
            st.markdown('')
    else:
        st.info('Chưa có bài viết để hiển thị.')

with kw_col3:
    st.markdown('### Xu hướng theo ngày')
    if 'published_date' in filtered.columns and len(filtered) > 0:
        daily = filtered.groupby('published_date').size().reset_index(name='count')
        fig_line = px.line(
            daily,
            x='published_date',
            y='count',
            markers=True,
            template='plotly_dark',
            color_discrete_sequence=['cyan']
        )
        fig_line.update_layout(
            height=460,
            margin=dict(t=30, b=0, l=0, r=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info('Không có dữ liệu xu hướng theo ngày.')

# ========== EVENT DETECTION ==========
st.markdown('## Event Detection')
if trending_events:
    event_summary = pd.DataFrame(trending_events)
    event_summary['status'] = event_summary['burst'].apply(
        lambda x: 'Hot' if x >= 70 else ('Trending' if x >= 40 else 'Emerging')
    )
    event_summary['score'] = event_summary['burst']

    fig_event_trend = px.bar(
        event_summary,
        x='name',
        y='score',
        color='status',
        color_discrete_map={'Hot': '#f97316', 'Trending': '#38bdf8', 'Emerging': '#34d399'},
        title='Chủ đề hot / trending',
        labels={'name': 'Chủ đề', 'score': 'Burst score (%)'},
        template='plotly_dark'
    )
    fig_event_trend.update_layout(height=380, margin=dict(t=40, b=40, l=0, r=0), xaxis_tickangle=-20)
    st.plotly_chart(fig_event_trend, use_container_width=True)

    topic_choice = st.selectbox(
        'Chọn chủ đề để xem bài nổi bật',
        options=[''] + [e['name'] for e in trending_events],
        index=0
    )

    event_cols = st.columns(len(trending_events))
    for idx, event in enumerate(trending_events):
        with event_cols[idx]:
            st.markdown(f"### Chủ đề: {event['name']}")
            st.markdown(f"**Từ khóa liên quan:** {event['keywords'] or 'Không có dữ liệu'}")
            st.markdown(f"**Số bài:** {event['count']}")
            st.markdown(f"**Mức độ hot:** {event['burst']}%")
            top_df = filtered[filtered['category'].astype(str) == event['name']].sort_values(
                'published_date', ascending=False
            )
            if not top_df.empty:
                top = top_df.iloc[0]
                title = top.get('title', 'Không có tiêu đề')
                link = top.get('link', '#')
                desc = top.get('description', '')
                st.markdown(f"**Bài nổi bật:** [{title}]({link})")
                if desc:
                    st.markdown(f"_{str(desc)[:240]}..._")
            else:
                st.markdown('*Chưa có bài nổi bật cho chủ đề này.*')

            st.progress(min(event['burst'], 100))
            st.markdown(f"**Trạng thái:** {event_summary.loc[idx, 'status']}")

    if 'published_date' in filtered.columns:
        trend_rows = []
        for event in trending_events:
            counts = filtered[filtered['category'].astype(str) == event['name']].groupby(
                'published_date'
            ).size().reset_index(name='count')
            counts['event'] = event['name']
            trend_rows.append(counts)
        if trend_rows and any(not r.empty for r in trend_rows):
            event_trends = pd.concat([r for r in trend_rows if not r.empty], ignore_index=True)
            fig_event_time = px.line(
                event_trends,
                x='published_date',
                y='count',
                color='event',
                markers=True,
                title='Xu hướng theo ngày của chủ đề hot',
                template='plotly_dark'
            )
            fig_event_time.update_layout(height=420, margin=dict(t=40, b=40, l=0, r=0))
            st.plotly_chart(fig_event_time, use_container_width=True)
        else:
            st.info('Chưa có dữ liệu xu hướng theo ngày cho các chủ đề đang chọn.')

    if topic_choice:
        sel_df = filtered[filtered['category'].astype(str) == topic_choice].sort_values(
            'published_date', ascending=False
        )
        if not sel_df.empty:
            st.markdown(f"### Bài viết nổi bật cho chủ đề: {topic_choice}")
            for _, row in sel_df.head(10).iterrows():
                title = row.get('title', 'Không có tiêu đề')
                link = row.get('link', '#')
                pub = row.get('published_date', '')
                desc = row.get('description', '')
                st.markdown(f"- [{title}]({link}) — _{pub}_")
                if desc:
                    st.markdown(f"  - {str(desc)[:200]}...")
        else:
            st.info('Không tìm thấy bài cho chủ đề đã chọn.')
else:
    st.info('Chưa có sự kiện trending để hiển thị.')

# ========== TOPIC MODELING ==========
st.markdown('## Topic Modeling')
if not topic_df.empty:
    fig_topic = px.treemap(
        topic_df,
        path=['category', 'keyword'],
        values='count',
        color='count',
        color_continuous_scale='tealrose',
        template='plotly_dark'
    )
    fig_topic.update_layout(
        height=520,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    st.plotly_chart(fig_topic, use_container_width=True)
else:
    st.info('Chưa đủ dữ liệu cho Topic Modeling.')

# ========== NEWS EXPLORER ==========
st.markdown('## News Explorer')
keyword_options = [kw for kw, _ in keyword_counts]
event_options = [''] + [event['name'] for event in trending_events]
selected_keyword = st.selectbox('Chọn từ khóa', options=keyword_options if keyword_options else [''], index=0)
selected_event = st.selectbox('Chọn chủ đề hot', options=event_options, index=0)

news_filter = filtered.copy()
if selected_event:
    news_filter = filtered[filtered['category'].astype(str) == selected_event]
elif selected_keyword and selected_keyword != '':
    news_filter = filtered[
        filtered['keywords'].astype(str).str.contains(selected_keyword, case=False, na=False)
    ]

if not news_filter.empty:
    for _, row in news_filter.sort_values('published_date', ascending=False).head(12).iterrows():
        st.markdown(f"#### [{row['title']}]({row['link']})")
        st.markdown(f"_{row.get('category', 'Không xác định')} • {row.get('published_date', '')}_")
        st.markdown(str(row.get('description', '')))
        st.markdown('---')
else:
    st.info('Chưa có bài viết liên quan cho lựa chọn hiện tại.')

# ========== SENTIMENT ANALYSIS ==========
st.markdown('## Sentiment Analysis')
fig_sentiment = px.pie(
    names=['Positive', 'Neutral', 'Negative'],
    values=[sentiment_counts['positive'], sentiment_counts['neutral'], sentiment_counts['negative']],
    color_discrete_sequence=['#2dd4bf', '#94a3b8', '#f87171'],
    template='plotly_dark'
)
fig_sentiment.update_layout(
    height=420,
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)'
)
st.plotly_chart(fig_sentiment, use_container_width=True)

# ========== FOOTER ==========
st.markdown('---')
st.markdown(
    '<div style="text-align:center;color:#9fd8ff;">Realtime analytics dashboard - cập nhật tức thời khi dữ liệu có thay đổi.</div>',
    unsafe_allow_html=True
)