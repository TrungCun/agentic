# Agentic Skeleton

Một bộ khung tái sử dụng (skeleton) cho các hệ thống agentic, được phát triển bởi Truncus. Bao gồm các tiện ích cấu hình, logging, và wrapper LLM chuẩn bị sẵn để dễ dàng mở rộng thành các dự án agentic hoàn chỉnh.

## Cấu trúc dự án

```
agentic/
├── app/
│   ├── config/
│   │   ├── config.py          # Cấu hình ứng dụng (pydantic Settings)
│   │   └── log.py             # Tiện ích logging tái sử dụng
│   └── model/
│       └── llm.py             # Wrapper ChatOpenAI + health-check
├── storage/
│   └── log/                   # Thư mục lưu log file (mặc định)
├── docs/                      # Tài liệu (chuẩn bị)
├── tests/                     # Bài kiểm thử (chuẩn bị)
├── .env                       # Biến môi trường
├── requirements.in            # Danh sách dependencies (pip-compile)
├── constraints.txt            # Phiên bản cố định (PyTorch, NumPy, ...)
└── README.md
```

## Yêu cầu và cài đặt

### Yêu cầu
- **Python**: 3.12+
- **CUDA** (tùy chọn): Nếu sử dụng GPU, cài CUDA 12.1 (torch được pin ở `cu128` trong `constraints.txt`)

### Cài đặt

1. Clone repository:
   ```bash
   git clone <repository-url>
   cd agentic
   ```

2. Cài đặt dependencies:
   ```bash
   pip install -r requirements.in -c constraints.txt
   ```

   **Ghi chú**: Dự án dùng `pip-compile` để quản lý dependencies:
   - `requirements.in`: Danh sách dependencies chính (docling, transformers, easyocr, pandas, python-dotenv, ...)
   - `constraints.txt`: Phiên bản cố định cho các gói không ổn định (PyTorch, torchvision, torchaudio, NumPy)
   - Xem `requirements.sh` để xem hướng dẫn chi tiết về `pip-compile` workflow

3. Tạo file `.env` nếu chưa có:
   ```bash
   cp .env.example .env  # (nếu tồn tại)
   # Hoặc chỉnh sửa `.env` trực tiếp với các giá trị của bạn
   ```

## Cấu hình (.env)

Các biến môi trường chính:

| Biến | Yêu cầu | Mô tả | Ví dụ |
|------|---------|-------|-------|
| `LLM_BASE_URL` | Bắt buộc | URL base API LLM | `http://10.0.99.116:8070/v1` |
| `LLM_MODEL` | Bắt buộc | Tên model LLM | `deepseek-v3` |
| `LLM_TEMPERATURE` | Tùy chọn | Nhiệt độ (0.0-2.0) | `0.0` |
| `LLM_MAX_TOKENS` | Tùy chọn | Số token tối đa | `4096` |
| `GPU_DEVICE` | Tùy chọn | ID GPU (nếu dùng CUDA) | `1` |

### Biến logging (tùy chọn)

Cấu hình logging qua biến môi trường:

| Biến | Giá trị | Mô tả |
|------|--------|-------|
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | Mức log (mặc định: `INFO`) |
| `LOG_FORMAT` | `text` hoặc `json` | Định dạng output (mặc định: `text`) |
| `LOG_FILE_ENABLED` | `true` hoặc `false` | Bật ghi log ra file (mặc định: `false`) |

Ví dụ:
```bash
LOG_LEVEL=DEBUG LOG_FILE_ENABLED=true python -m app.model.llm
```

## Logging

Module `app.config.log` cung cấp một tiện ích logging linh hoạt:

```python
from app.config.log import setup_logging, get_logger

# Gọi một lần ở entry point của ứng dụng
setup_logging(
    service_name="my_app",      # Tên service (dùng trong JSON log, tên file log)
    level="INFO",               # Mức log
    json_format=False,          # True: JSON log | False: text log
    file_enabled=True,          # True: ghi file | False: stdout only
    log_dir="storage/log"       # Thư mục lưu log file
)

# Lấy logger cho module
logger = get_logger(__name__)
logger.info("Hello, world!")
```

**Đặc điểm:**
- Console handler luôn được tạo (output tô màu ANSI cho text format)
- File handler tự động rotate hàng ngày, giữ tối đa 30 file backup
- Hỗ trợ cấu hình qua parameter hoặc biến môi trường

## Sử dụng nhanh

### Health check LLM

Kiểm tra kết nối LLM:

```bash
python -m app.model.llm
```

Lệnh này sẽ:
1. Khởi tạo logging
2. Tạo kết nối tới LLM qua `ChatOpenAI`
3. Gửi một tin nhắn test ("Hello, respond with exactly 'OK'")
4. In response trên console
5. Ghi log vào `storage/log/llm_health_check.log`

### Sử dụng LLM trong code

```python
from app.model.llm import llm, llm_reasoning, llm_stream, llm_stream_reasoning
from langchain_core.messages import HumanMessage

# LLM tiêu chuẩn (không stream, không reasoning)
response = llm.invoke([HumanMessage(content="Your question here")])
print(response.content)

# LLM với reasoning (deep thinking)
response = llm_reasoning.invoke([HumanMessage(content="Complex problem")])
print(response.content)

# LLM với streaming
for chunk in llm_stream.stream([HumanMessage(content="Your question here")]):
    print(chunk.content, end="", flush=True)
```

Bốn biến thể có sẵn:
- `llm`: Tiêu chuẩn
- `llm_reasoning`: Bật thinking/extended reasoning
- `llm_stream`: Streaming kết quả từng phần
- `llm_stream_reasoning`: Streaming + thinking

## Trạng thái hiện tại

Đây là phiên bản **skeleton / khung nền tảng** của dự án, ở giai đoạn đầu phát triển:

✅ **Hoàn thành**
- Lớp cấu hình với pydantic_settings
- Module logging tái sử dụng (console + rotating file, text/JSON)
- Wrapper LLM với ChatOpenAI (streaming, reasoning support)
- Health check LLM

⏳ **Chuẩn bị**
- Cấu trúc agent/graph (LangGraph integration)
- Các node xử lý (retrieval, reasoning, ...)
- Entrypoint chính thức
- Bộ test
- Tài liệu chi tiết

## Đóng góp

Khi mở rộng dự án, vui lòng:
- Tuân theo cấu trúc thư mục hiện có
- Tái sử dụng module `log.py` cho logging
- Cập nhật `.env.example` khi thêm biến môi trường mới
- Thêm test vào thư mục `tests/`

## Liên hệ

Dự án được duy trì bởi **Truncus**. Để báo cáo lỗi hoặc đề xuất cải tiến, vui lòng tạo một issue trong repository.
