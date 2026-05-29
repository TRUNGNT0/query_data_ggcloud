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
        :root {
            color-scheme: dark;
        }
        body {
            background-color: #061a26;
            color: #e8f8ff;
        }
        .stApp {
            background: linear-gradient(135deg, #02111b 0%, #062836 50%, #051d2c 100%);
            color: #eef8ff;
        }
        .css-18e3th9 {
            background-color: transparent;
        }
        .css-1d391kg {
            background-color: rgba(3, 29, 44, 0.82);
        }
        .stButton>button {
            background-color: #0fb5ff;
            color: white;
            border: none;
        }
        .stButton>button:hover {
            background-color: #24c5ff;
            color: white;
        }
        .st-b8 {
            background: rgba(255,255,255,0.05);
        }
        .block-container {
            padding: 1.2rem 1.5rem 0 1.5rem;
        }
        .reportview-container .main .block-container {
            padding-top: 1rem;
        }
        .css-1aumxhk {
            background: rgba(4, 29, 45, 0.7);
        }
        .stSidebar {
            background-color: #031519;
        }
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
            color: #d3f9ff;
        }
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
    'những', 'đó', 'một', 'nhiều', 'giữa', 'bị', 'đã', 'có', 'từ', 'the'
}


def normalize_keywords(keywords):
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
        item_text = re.sub(r'["\'\(\)\[\]\\/]+', ' ', item_text)
        item_text = re.sub(r'\s+', ' ', item_text).strip().lower()
        words = [w for w in re.split(r'\s+', item_text) if w and w not in STOPWORDS]
        if not words:
            continue
        filtered_words = [w for w in words if 2 <= len(w) <= 5]
        if not filtered_words:
            continue
        if len(filtered_words) >= 2:
            normalized.append(' '.join(filtered_words))
        elif len(filtered_words) == 1:
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
    """Tải dữ liệu từ BigQuery"""
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
        # Convert clean_keywords array to comma-separated string
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
    """Tải dữ liệu mẫu nếu không có kết nối BigQuery"""
    data = {
        'title': [
            'Quy định mới phủ bóng lên giấc mơ thẻ xanh Mỹ',
            'Những nhà hàng đặc sản Texas lao đao vì giá thịt tăng phi mã',
            'Sát thủ bóng đêm của Hezbollah khiến Israel lo ngại',
            'Ukraine sẽ mua 20 tiêm kích Gripen hiện đại nhất của Thụy Điển',
            'Tổng Bí thư, Chủ tịch nước Tô Lâm hội kiến Nhà Vua Thái Lan'
        ],
        'category': ['Thế giới', 'Thế giới', 'Thế giới', 'Thế giới', 'Thế giới'],
        'published_date': [
            (datetime.now() - timedelta(days=i)).date() for i in range(5)
        ],
        'keywords': [
            'Quy định, Mỹ, Thẻ xanh',
            'Texas, Nhà hàng, Giá thịt',
            'Hezbollah, Israel, Drone',
            'Ukraine, Gripen, Thụy Điển',
            'Tô Lâm, Thái Lan, Hội kiến'
        ],
        'description': [
            'Thay đổi mới trong quy định xin thẻ xanh của Mỹ khiến người nhập cư lo ngại.',
            'Những nhà hàng nổi tiếng ở Texas đang phải vật lộn vì giá nguyên liệu tăng.',
            'Quan chức Israel ví drone của Hezbollah như cơn ác mộng.',
            'Ukraine dự kiến đặt mua 20 tiêm kích Gripen của Thụy Điển.',
            'Tổng Bí thư hội kiến Nhà Vua Thái Lan trong khuôn khổ chuyến thăm.'
        ],
        'link': [
            'https://vnexpress.net/quy-dinh-moi-1.html',
            'https://vnexpress.net/nha-hang-texas-2.html',
            'https://vnexpress.net/hezbollah-3.html',
            'https://vnexpress.net/ukraine-gripen-4.html',
            'https://vnexpress.net/to-lam-thai-lan-5.html'
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
    st.warning('⚠️ Không thể kết nối BigQuery. Ứng dụng sẽ dùng dữ liệu mẫu hoặc bạn có thể tải file dữ liệu CSV/JSON.')
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
kw_col1, kw_col2, kw_col3 = st.columns([1.5, 1.2, 1.3])
with kw_col1:
    st.markdown('### Top Keywords')
    if keyword_counts:
        top_kw_df = pd.DataFrame(keyword_counts, columns=['keyword', 'count']).head(12)
        fig_kw = px.bar(
            top_kw_df,
            x='count',
            y='keyword',
            orientation='h',
            color='count',
            color_continuous_scale='tealrose',
            template='plotly_dark'
        )
        fig_kw.update_layout(height=460, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_kw, use_container_width=True)
    else:
        st.info('Không đủ dữ liệu từ khóa để hiển thị.')
with kw_col2:
    st.markdown('### Word Cloud')
    if keyword_counts:
        cloud_df = pd.DataFrame(keyword_counts[:30], columns=['keyword', 'count'])
        cloud_df['x'] = np.random.uniform(0, 1, size=len(cloud_df))
        cloud_df['y'] = np.random.uniform(0, 1, size=len(cloud_df))
        cloud_df['size'] = cloud_df['count'] / cloud_df['count'].max() * 45 + 10
        fig_cloud = px.scatter(
            cloud_df,
            x='x',
            y='y',
            size='size',
            text='keyword',
            color='count',
            color_continuous_scale='teal',
            template='plotly_dark'
        )
        fig_cloud.update_traces(textposition='middle center', marker=dict(opacity=0.75))
        fig_cloud.update_layout(height=460, xaxis={'visible': False}, yaxis={'visible': False}, showlegend=False, margin=dict(t=10, b=10, l=10, r=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_cloud, use_container_width=True)
    else:
        st.info('Chưa có dữ liệu để tạo word cloud.')
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
        fig_line.update_layout(height=460, margin=dict(t=30, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
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
        title='Sự kiện hot / trending',
        labels={'name': 'Event', 'score': 'Burst score (%)'},
        template='plotly_dark'
    )
    fig_event_trend.update_layout(height=380, margin=dict(t=40, b=40, l=0, r=0), xaxis_tickangle=-20)
    st.plotly_chart(fig_event_trend, use_container_width=True)

    event_cols = st.columns(len(trending_events))
    for idx, event in enumerate(trending_events):
        with event_cols[idx]:
            st.markdown(f"### Chủ đề: {event['name']}")
            st.markdown(f"**Từ khóa liên quan:** {event['keywords'] or 'Không có dữ liệu'}")
            st.markdown(f"**Số bài:** {event['count']}")
            st.markdown(f"**Mức độ hot:** {event['burst']}%")
            st.progress(min(event['burst'], 100))
            st.markdown(f"**Trạng thái:** {event_summary.loc[idx, 'status']}")

    if 'published_date' in filtered.columns:
        trend_rows = []
        for event in trending_events:
            counts = filtered[filtered['category'].astype(str) == event['name']].groupby('published_date').size().reset_index(name='count')
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
    fig_topic.update_layout(height=520, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
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
    news_filter = filtered[filtered['keywords'].astype(str).str.contains(selected_keyword, case=False, na=False)]

if not news_filter.empty:
    for _, row in news_filter.sort_values('published_date', ascending=False).head(12).iterrows():
        st.markdown(f"#### [{row['title']}]({row['link']})")
        st.markdown(f"_{row.get('category', 'Không xác định')} • {row.get('published_date', '')}_")
        st.markdown(row.get('description', ''))
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
fig_sentiment.update_layout(height=420, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
st.plotly_chart(fig_sentiment, use_container_width=True)

# ========== KEYWORD RELATIONSHIP GRAPH ==========
st.markdown('## Keyword Relationship Graph')
if keyword_nodes and keyword_edges:
    node_positions = {}
    angle_step = 2 * np.pi / len(keyword_nodes)
    for i, node in enumerate(keyword_nodes):
        node_positions[node['id']] = (np.cos(i * angle_step), np.sin(i * angle_step))
    edge_x = []
    edge_y = []
    for edge in keyword_edges:
        x0, y0 = node_positions[edge['from']]
        x1, y1 = node_positions[edge['to']]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
    fig_graph = go.Figure()
    fig_graph.add_trace(go.Scatter(x=edge_x, y=edge_y, mode='lines', line=dict(color='#26c6da', width=1), hoverinfo='none'))
    fig_graph.add_trace(go.Scatter(
        x=[node_positions[node['id']][0] for node in keyword_nodes],
        y=[node_positions[node['id']][1] for node in keyword_nodes],
        mode='markers+text',
        marker=dict(size=[max(8, min(40, node['size'] * 1.5)) for node in keyword_nodes], color='#0aefff'),
        text=[node['id'] for node in keyword_nodes],
        textposition='top center',
        hovertemplate='<b>%{text}</b>',
    ))
    fig_graph.update_layout(height=520, xaxis=dict(showgrid=False, zeroline=False, visible=False), yaxis=dict(showgrid=False, zeroline=False, visible=False), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_graph, use_container_width=True)
else:
    st.info('Chưa đủ dữ liệu để xây dựng mối quan hệ từ khóa.')

# ========== LIVE FEED ==========
st.markdown('## Live Feed')
if 'published_date' in df.columns:
    latest = df.sort_values('published_date', ascending=False).head(8)
else:
    latest = df.head(8)
for _, row in latest.iterrows():
    st.markdown(f"- [{row['title']}]({row['link']}) — _{row.get('category', 'Không xác định')}_")
st.markdown('---')
st.markdown('<div style="text-align:center;color:#9fd8ff;">Realtime analytics dashboard - cập nhật tức thời khi dữ liệu có thay đổi.</div>', unsafe_allow_html=True)
