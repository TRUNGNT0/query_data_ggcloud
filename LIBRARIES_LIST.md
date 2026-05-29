# 📦 DANH SÁCH THƯ VIỆN CẦN CÀI ĐẶT

## Tóm tắt nhanh
Để chạy ứng dụng Streamlit, cài đặt tất cả thư viện bằng:
```bash
pip install -r requirements.txt
```

---

## 📋 Chi tiết từng thư viện

### 🌐 Web Framework
| Tên | Phiên bản | Mục đích |
|-----|---------|---------|
| **streamlit** | 1.28.1 | Framework chính để tạo web app interactive |

### 📊 Xử lý & Trực quan dữ liệu
| Tên | Phiên bản | Mục đích |
|-----|---------|---------|
| **pandas** | 2.1.3 | Xử lý dữ liệu, dataframe, filtering, grouping |
| **plotly** | 5.18.0 | Tạo biểu đồ tương tác (Pie, Bar, Line chart) |
| **numpy** | 1.24.3 | Tính toán số học, xử lý mảng |

### ☁️ Google Cloud
| Tên | Phiên bản | Mục đích |
|-----|---------|---------|
| **google-cloud-bigquery** | 3.14.0 | Kết nối và query dữ liệu từ BigQuery |
| **google-cloud-storage** | 2.10.0 | Đọc/ghi dữ liệu từ Google Cloud Storage |

### 🇻🇳 Xử lý tiếng Việt
| Tên | Phiên bản | Mục đích |
|-----|---------|---------|
| **pyvi** | 0.1.1 | Tokenize (tách từ) tiếng Việt |

### 📰 Xử lý tin tức
| Tên | Phiên bản | Mục đích |
|-----|---------|---------|
| **feedparser** | 6.0.10 | Parse RSS feeds từ các nguồn tin |
| **beautifulsoup4** | 4.12.2 | Parse HTML, xử lý cấu trúc web |

### ⚙️ Cấu hình
| Tên | Phiên bản | Mục đích |
|-----|---------|---------|
| **pyyaml** | 6.0.1 | Đọc và parse file cấu hình YAML |

---

## 🚀 Cách cài đặt

### Cách 1: Cài đặt từ requirements.txt (Khuyến nghị ⭐)
```bash
pip install -r requirements.txt
```

### Cách 2: Cài đặt từng thư viện
```bash
pip install streamlit==1.28.1
pip install pandas==2.1.3
pip install plotly==5.18.0
pip install google-cloud-bigquery==3.14.0
pip install google-cloud-storage==2.10.0
pip install pyvi==0.1.1
pip install feedparser==6.0.10
pip install beautifulsoup4==4.12.2
pip install pyyaml==6.0.1
pip install numpy==1.24.3
```

### Cách 3: Cài đặt phiên bản mới nhất
```bash
pip install --upgrade streamlit pandas plotly google-cloud-bigquery google-cloud-storage pyvi feedparser beautifulsoup4 pyyaml numpy
```

---

## ✅ Kiểm tra cài đặt
Sau khi cài, kiểm tra xem tất cả thư viện đã cài đúng:
```bash
pip list
```

Hoặc test import từng thư viện:
```python
import streamlit
import pandas
import plotly
from google.cloud import bigquery
import pyvi
import feedparser
```

---

## 🔗 Links tải thêm
Nếu cần cài thủ công:
- Streamlit: https://pypi.org/project/streamlit/
- Pandas: https://pypi.org/project/pandas/
- Plotly: https://pypi.org/project/plotly/
- Google Cloud: https://pypi.org/project/google-cloud-bigquery/

---

## ⚠️ Lưu ý quan trọng

1. **Python version**: Yêu cầu Python 3.8+
2. **Virtual environment**: Khuyến nghị sử dụng virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. **Google Cloud Credentials**: Nếu dùng BigQuery, cần setup credentials:
   ```bash
   gcloud auth application-default login
   ```

---

## 📌 Thứ tự cài đặt (nếu cài thủ công)
1. numpy (dependency của nhiều thư viện khác)
2. pandas (dependency của plotly)
3. streamlit, plotly
4. google-cloud-*
5. pyvi, feedparser, beautifulsoup4, pyyaml

---

## 💾 Cách tạo requirements.txt cho dự án
Nếu bạn thay đổi dự án và muốn lưu lại danh sách thư viện:
```bash
pip freeze > requirements.txt
```

---

**Cập nhật lần cuối**: May 2024  
**Tác giả**: GitHub Copilot
