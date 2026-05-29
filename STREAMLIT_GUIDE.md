# 📊 News Analytics Dashboard - Hướng Dẫn Sử Dụng

## 📌 Giới thiệu
Đây là một ứng dụng **Streamlit** để trực quan dữ liệu tin tức từ BigQuery, tương tự như **Google Report**. 
Ứng dụng cho phép lọc, phân tích và trực quan dữ liệu tin tức theo nhiều chiều khác nhau.

## 🎯 Tính năng chính
- ✅ **Bộ lọc theo thời gian (Ngày)** - Chỉ chia độ là ngày, không có giờ phút
- ✅ **Lọc theo danh mục** - Chọn một hoặc nhiều danh mục
- ✅ **Tìm kiếm từ khóa** - Tìm kiếm nhanh trong tiêu đề và từ khóa
- ✅ **5 Tab chính**:
  1. 📊 **Biểu đồ** - Pie chart danh mục, Bar chart top bài viết
  2. 📋 **Bảng dữ liệu** - Xem danh sách chi tiết tất cả bài viết
  3. 🏷️ **Phân tích từ khóa** - Top 15 từ khóa nổi bật
  4. 📅 **Xu hướng theo ngày** - Biểu đồ đường showing xu hướng công bố
  5. ⚙️ **Chi tiết** - Thống kê tổng quát và hướng dẫn

## 🚀 Cách cài đặt và chạy

### Bước 1: Cài đặt thư viện
```bash
pip install -r requirements.txt
```

### Bước 2: Thiết lập Google Cloud credentials
Nếu kết nối BigQuery, bạn cần thiết lập credentials:
```bash
# Linux/Mac
export GOOGLE_APPLICATION_CREDENTIALS="đường_dẫn/credentials.json"

# Windows (PowerShell)
$env:GOOGLE_APPLICATION_CREDENTIALS="đường_dẫn/credentials.json"
```

### Bước 3: Chạy ứng dụng
```bash
streamlit run app.py
```

Ứng dụng sẽ mở tại `http://localhost:8501`

## 📂 Cấu trúc thư mục
```
streamlit/
├── app.py                  # Ứng dụng chính
├── requirements.txt        # Danh sách thư viện
├── README.md              # Hướng dẫn này
└── ...
```

## 🔧 Cấu hình

### Thay đổi bảng BigQuery
Mở file `app.py` tìm hàm `load_data_from_bigquery()` và thay đổi:
```python
query = """
    SELECT ... FROM `project-ceb4f683-ad1a-44e3-8d8.bigdata_project.vnexpress_world_news`
    ...
"""
```

### Thay đổi khoảng thời gian mặc định
Tìm dòng:
```python
value=(datetime.now().date() - timedelta(days=30), datetime.now().date())
```
Thay `30` thành số ngày mong muốn.

## 📋 Danh sách thư viện cần thiết

| Thư viện | Phiên bản | Mục đích |
|---------|----------|---------|
| streamlit | 1.28.1 | Framework web app |
| pandas | 2.1.3 | Xử lý dữ liệu |
| plotly | 5.18.0 | Biểu đồ tương tác |
| google-cloud-bigquery | 3.14.0 | Kết nối BigQuery |
| google-cloud-storage | 2.10.0 | Kết nối Google Cloud Storage |
| pyvi | 0.1.1 | Xử lý tiếng Việt |
| feedparser | 6.0.10 | Parse RSS feeds |
| beautifulsoup4 | 4.12.2 | Parse HTML |
| pyyaml | 6.0.1 | Đọc file YAML |
| numpy | 1.24.3 | Tính toán số học |

## 💡 Hướng dẫn sử dụng chi tiết

### Sidebar - Bộ lọc
1. **Chọn khoảng thời gian**: Nhấp vào "Chọn khoảng thời gian (Ngày)" để chọn ngày bắt đầu và kết thúc
2. **Lọc danh mục**: Chọn một hoặc nhiều danh mục từ danh sách
3. **Tìm kiếm từ khóa**: Nhập từ khóa để tìm kiếm trong tiêu đề và từ khóa

### Tabs chính
- **📊 Biểu đồ**: Xem biểu đồ Pie (phân bố danh mục) và Bar chart (top 10 bài viết)
- **📋 Bảng dữ liệu**: Xem danh sách đầy đủ tất cả bài viết, có thể sắp xếp
- **🏷️ Phân tích từ khóa**: Xem top 15 từ khóa nổi bật nhất
- **📅 Xu hướng theo ngày**: Xem biểu đồ đường thể hiện xu hướng công bố qua các ngày
- **⚙️ Chi tiết**: Xem thống kê tổng quát và top danh mục

### Nút làm mới
Nhấp nút "🔄 Làm mới" để load lại dữ liệu từ BigQuery.

## ⚠️ Troubleshooting

### Lỗi: "No module named 'streamlit'"
**Giải pháp**: Cài đặt lại thư viện
```bash
pip install -r requirements.txt
```

### Lỗi: "Authentication failed"
**Giải pháp**: Kiểm tra credentials Google Cloud
```bash
gcloud auth application-default login
```

### Ứng dụng chạy chậm
**Giải pháp**: Dữ liệu được cache 1 giờ, nhấp "Làm mới" để load lại ngay.

## 📞 Liên hệ & Hỗ trợ
Nếu gặp bất kỳ vấn đề nào, vui lòng kiểm tra:
1. Thư viện đã cài đặt đầy đủ (`pip list`)
2. Credentials Google Cloud đã đúng
3. Kết nối Internet ổn định

---
**Phiên bản**: 1.0.0  
**Cập nhật lần cuối**: 2024
