import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
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
        .main {
            padding: 0rem 1rem;
        }
        .metric-box {
            background-color: #f0f2f6;
            padding: 1.5rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
        }
        h1 {
            color: #1f77b4;
            font-size: 2.5rem;
            font-weight: bold;
        }
        h2 {
            color: #1f77b4;
            border-bottom: 3px solid #1f77b4;
            padding-bottom: 0.5rem;
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

# ========== ĐỌC DỮ LIỆU TỪ BIGQUERY ==========
@st.cache_data(ttl=3600)
def load_data_from_bigquery():
    """Tải dữ liệu từ BigQuery"""
    try:
        client = bigquery.Client()
        query = """
            SELECT 
                link,
                title,
                description,
                category,
                publish_date AS published_date,
                view_count,
                interaction_count
            FROM `project-ceb4f683-ad1a-44e3-8d8.bigdata_project.vnexpress_world_news`
            WHERE publish_date >= CURRENT_DATE() - 90
            ORDER BY publish_date DESC
        """
        df = client.query(query).to_dataframe()
        df['published_date'] = pd.to_datetime(df['published_date']).dt.date
        st.session_state.bigquery_error = None
        return df
    except Exception as e:
        st.session_state.bigquery_error = str(e)
        return None

@st.cache_data(ttl=3600)
def load_sample_data():
    """Tải dữ liệu mẫu nếu không có kết nối BigQuery"""
    data = {
        'title': ['Tin tức 1', 'Tin tức 2', 'Tin tức 3', 'Tin tức 4', 'Tin tức 5'],
        'category': ['Kinh doanh', 'Thế giới', 'Công nghệ', 'Kinh doanh', 'Thế giới'],
        'published_date': [
            (datetime.now() - timedelta(days=i)).date() for i in range(5)
        ],
        'view_count': [150, 230, 180, 290, 145],
        'keywords': ['Tiền tệ', 'Chính trị', 'AI', 'Thị trường', 'Ngoài nước']
    }
    return pd.DataFrame(data)

# ========== LOAD DỮ LIỆU ==========
uploaded_file = st.sidebar.file_uploader("Tải lên file dữ liệu CSV/JSON", type=['csv', 'json'])
use_local_sample = False

if uploaded_file is not None:
    try:
        if uploaded_file.type == 'application/json':
            df = pd.read_json(uploaded_file)
        else:
            df = pd.read_csv(uploaded_file)
        df['published_date'] = pd.to_datetime(df['published_date']).dt.date
        st.sidebar.success("✅ Đã tải dữ liệu từ file thành công.")
    except Exception as e:
        st.sidebar.error(f"❌ Không đọc được file: {e}")
        df = load_sample_data()
        use_local_sample = True
else:
    st.session_state.df_cache = load_data_from_bigquery()
    if st.session_state.df_cache is None:
        df = load_sample_data()
        use_local_sample = True
    else:
        df = st.session_state.df_cache

if st.session_state.bigquery_error:
    st.warning(
        "⚠️ Không thể kết nối BigQuery. Ứng dụng sẽ dùng dữ liệu mẫu hoặc bạn có thể tải file dữ liệu CSV/JSON.")
    st.info(st.session_state.bigquery_error)

# ========== HEADER ==========
col1, col2 = st.columns([0.8, 0.2])
with col1:
    st.title("📊 News Analytics Dashboard")
    st.markdown("Trực quan dữ liệu tin tức - Tương tự Google Report")
    if use_local_sample:
        st.info("Dữ liệu hiện tại là dữ liệu mẫu vì không thể truy cập BigQuery.")

with col2:
    if st.button("🔄 Làm mới", key="refresh_btn"):
        st.session_state.df_cache = None
        st.cache_data.clear()
        st.rerun()

# ========== SIDEBAR - BỘ LỌC ==========
st.sidebar.title("🔍 Bộ Lọc")

# Lọc theo thời gian (chỉ ngày)
date_range = st.sidebar.date_input(
    "Chọn khoảng thời gian (Ngày)",
    value=(datetime.now().date() - timedelta(days=30), datetime.now().date()),
    max_value=datetime.now().date()
)

# Lọc theo danh mục
categories = st.sidebar.multiselect(
    "Danh mục",
    options=df['category'].unique() if 'category' in df.columns else [],
    default=df['category'].unique() if 'category' in df.columns else []
)

# Lọc theo từ khóa
keyword_filter = st.sidebar.text_input("Tìm kiếm từ khóa")

# ========== LỌC DỮ LIỆU ==========
df_filtered = df.copy()

# Lọc theo thời gian
if len(date_range) == 2:
    start_date, end_date = date_range
    df_filtered = df_filtered[
        (df_filtered['published_date'] >= start_date) & 
        (df_filtered['published_date'] <= end_date)
    ]

# Lọc theo danh mục
if categories:
    df_filtered = df_filtered[df_filtered['category'].isin(categories)]

# Lọc theo từ khóa
if keyword_filter:
    df_filtered = df_filtered[
        df_filtered['title'].str.contains(keyword_filter, case=False, na=False) |
        df_filtered['keywords'].astype(str).str.contains(keyword_filter, case=False, na=False)
    ]

# ========== KPI CHÍNH ==========
st.markdown("## 📈 Số liệu chính")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="📰 Tổng bài viết",
        value=len(df_filtered),
        delta=len(df_filtered) - len(df) if len(df) > 0 else 0
    )

with col2:
    total_views = df_filtered['view_count'].sum() if 'view_count' in df_filtered.columns else 0
    st.metric(
        label="👁️ Tổng lượt xem",
        value=f"{total_views:,}",
        delta=None
    )

with col3:
    total_interactions = df_filtered['interaction_count'].sum() if 'interaction_count' in df_filtered.columns else 0
    st.metric(
        label="💬 Tương tác",
        value=f"{total_interactions:,}",
        delta=None
    )

with col4:
    if 'category' in df_filtered.columns and len(df_filtered) > 0:
        top_category = df_filtered['category'].value_counts().index[0]
    else:
        top_category = "N/A"
    st.metric(
        label="🏆 Danh mục top",
        value=top_category,
        delta=None
    )

# ========== TABS CHÍNH ==========
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 Biểu đồ", "📋 Bảng dữ liệu", "🏷️ Phân tích từ khóa", "📅 Xu hướng theo ngày", "⚙️ Chi tiết"]
)

# ========== TAB 1: BIỂU ĐỒ ==========
with tab1:
    st.markdown("### Phân bố theo danh mục")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if 'category' in df_filtered.columns and len(df_filtered) > 0:
            category_counts = df_filtered['category'].value_counts()
            fig1 = go.Figure(data=[
                go.Pie(
                    labels=category_counts.index,
                    values=category_counts.values,
                    hovertemplate="<b>%{label}</b><br>Bài viết: %{value}<extra></extra>"
                )
            ])
            fig1.update_layout(height=400, title_text="Phân bố danh mục")
            st.plotly_chart(fig1, use_container_width=True)
        else:
            st.info("Không có dữ liệu danh mục")
    
    with col2:
        if 'view_count' in df_filtered.columns and len(df_filtered) > 0:
            top_articles = df_filtered.nlargest(10, 'view_count')[['title', 'view_count']]
            fig2 = go.Figure(data=[
                go.Bar(
                    y=top_articles['title'].str[:30],
                    x=top_articles['view_count'],
                    orientation='h',
                    marker_color='#1f77b4',
                    hovertemplate="<b>%{y}</b><br>Lượt xem: %{x:,}<extra></extra>"
                )
            ])
            fig2.update_layout(
                height=400,
                title_text="Top 10 bài viết nhiều xem nhất",
                xaxis_title="Lượt xem",
                yaxis_title=""
            )
            st.plotly_chart(fig2, use_container_width=True)

# ========== TAB 2: BẢNG DỮ LIỆU ==========
with tab2:
    st.markdown("### Danh sách chi tiết bài viết")
    
    display_columns = [col for col in ['title', 'category', 'published_date', 'view_count'] 
                       if col in df_filtered.columns]
    
    if len(df_filtered) > 0:
        display_df = df_filtered[display_columns].copy()
        display_df.columns = ['Tiêu đề', 'Danh mục', 'Ngày đăng', 'Lượt xem']
        
        st.dataframe(
            display_df,
            use_container_width=True,
            height=400,
            column_config={
                "Tiêu đề": st.column_config.TextColumn(width="large"),
                "Danh mục": st.column_config.TextColumn(width="small"),
                "Ngày đăng": st.column_config.DateColumn(width="small"),
                "Lượt xem": st.column_config.NumberColumn(width="small", format="%d")
            }
        )
        
        st.markdown(f"**Tổng cộng: {len(df_filtered)} bài viết**")
    else:
        st.warning("Không có dữ liệu phù hợp với bộ lọc")

# ========== TAB 3: PHÂN TÍCH TỪ KHÓA ==========
with tab3:
    st.markdown("### Từ khóa nổi bật")
    
    if 'keywords' in df_filtered.columns and len(df_filtered) > 0:
        # Xử lý từ khóa
        all_keywords = []
        for keywords_str in df_filtered['keywords'].dropna():
            if isinstance(keywords_str, str):
                all_keywords.extend([k.strip() for k in keywords_str.split(',')])
        
        if all_keywords:
            keyword_counts = pd.Series(all_keywords).value_counts().head(15)
            
            fig = go.Figure(data=[
                go.Bar(
                    x=keyword_counts.values,
                    y=keyword_counts.index,
                    orientation='h',
                    marker_color='#ff7f0e',
                    hovertemplate="<b>%{y}</b><br>Xuất hiện: %{x}<extra></extra>"
                )
            ])
            fig.update_layout(
                height=500,
                title_text="Top 15 từ khóa nổi bật",
                xaxis_title="Số lần xuất hiện",
                yaxis_title="Từ khóa"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Không có dữ liệu từ khóa")
    else:
        st.info("Không có cột từ khóa")

# ========== TAB 4: XU HƯỚNG THEO NGÀY ==========
with tab4:
    st.markdown("### Xu hướng công bố bài viết theo ngày")
    
    if 'published_date' in df_filtered.columns and len(df_filtered) > 0:
        daily_counts = df_filtered.groupby('published_date').size().reset_index(name='count')
        daily_counts = daily_counts.sort_values('published_date')
        
        fig = go.Figure(data=[
            go.Scatter(
                x=daily_counts['published_date'],
                y=daily_counts['count'],
                mode='lines+markers',
                line=dict(color='#2ca02c', width=3),
                marker=dict(size=8),
                hovertemplate="<b>%{x}</b><br>Bài viết: %{y}<extra></extra>"
            )
        ])
        fig.update_layout(
            height=400,
            title_text="Số bài viết công bố theo ngày",
            xaxis_title="Ngày",
            yaxis_title="Số bài viết",
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Không có dữ liệu theo ngày")

# ========== TAB 5: CHI TIẾT ==========
with tab5:
    st.markdown("### Thông tin chi tiết")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📊 Số liệu thống kê**")
        stats = {
            "Tổng bài viết": len(df_filtered),
            "Thời gian": f"{df_filtered['published_date'].min()} đến {df_filtered['published_date'].max()}",
            "Số danh mục": df_filtered['category'].nunique() if 'category' in df_filtered.columns else 0,
        }
        for key, value in stats.items():
            st.metric(label=key, value=value)
    
    with col2:
        st.markdown("**🔝 Top danh mục**")
        if 'category' in df_filtered.columns and len(df_filtered) > 0:
            top_cats = df_filtered['category'].value_counts().head(5)
            for idx, (cat, count) in enumerate(top_cats.items(), 1):
                st.write(f"{idx}. {cat}: {count} bài viết")
    
    st.markdown("---")
    st.markdown("**ℹ️ Hướng dẫn sử dụng**")
    st.info("""
    - 📅 **Bộ lọc ngày**: Chọn khoảng thời gian để xem dữ liệu trong khoảng đó
    - 🏷️ **Danh mục**: Chọn một hoặc nhiều danh mục để lọc
    - 🔍 **Tìm kiếm**: Nhập từ khóa để tìm bài viết
    - 📊 **Biểu đồ**: Xem phân bố dữ liệu dạng hình ảnh
    - 📋 **Bảng**: Xem chi tiết từng bài viết
    - 📈 **Xu hướng**: Theo dõi xu hướng qua các ngày
    """)

# ========== FOOTER ==========
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #888; font-size: 0.9rem;'>
    📊 News Analytics Dashboard | Cập nhật lần cuối: """ + datetime.now().strftime("%Y-%m-%d %H:%M") + """
    </div>
    """,
    unsafe_allow_html=True
)
