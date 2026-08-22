# Kế hoạch triển khai: tầng xử lý ngữ cảnh hội thoại cho RAG

Tài liệu này chốt lại những gì có bằng chứng, loại bỏ những gì đã thử và bác, và nêu rõ chỗ nào còn phải tự đo.

---

## 0. Nguyên tắc chi phối

Bốn nguyên tắc này quyết định mọi lựa chọn phía dưới. Nếu phải bỏ chi tiết nào đó, giữ lại các nguyên tắc.

**N1 — Hợp đồng của tầng rewrite là một tính chất, không phải một định dạng.**
Output phải _độc lập ngữ cảnh_ và _bảo toàn nghĩa_. Không tối ưu cho retrieval, không tối ưu cho SQL, không tối ưu cho bất kỳ consumer nào. Mọi tối ưu hoá dời xuống tầng projection.

Cơ sở: đây là định nghĩa task decontextualization (Choi et al., TACL 2021). Vế "bảo toàn nghĩa" là thứ khiến một output phục vụ được nhiều consumer — nếu không bao giờ xoá, mọi consumer vẫn còn đủ nguyên liệu để tự chiếu.

**N2 — Query đã rewrite không bao giờ chạm tới generation.**
`utterance` (nguyên văn người dùng) và `queries` (bản đã xử lý) là hai trường tách biệt về mặt cấu trúc, không phải hai biến cùng kiểu string.

Cơ sở: LlamaIndex đã sửa đúng lỗi này khi chuyển từ `CondenseQuestionChatEngine` sang `CondensePlusContextChatEngine` — bản sau chỉ đưa câu condense vào retriever, còn generation nhận tin nhắn gốc.

**N3 — Ngữ cảnh có cấu trúc đi vào filter và boost, không đi vào chuỗi query.**
Nhồi định danh vào text làm vector lệch về phía token định danh thay vì khái niệm, và hạ điểm retrieval.

**N4 — Không xây node phát hiện đổi chủ đề.**
SOTA trên TIAGE là F1 27.8 sau 5 năm nghiên cứu chuyên biệt, và recall tệ nhất (28–30) đúng ở vùng chủ đề dài 4–9 lượt, tức vùng ta quan tâm nhất. Ba hệ memory production hàng đầu (Mem0, Zep, Letta) đều không có node này — họ biến bài toán nhị phân thành bài toán truy hồi.

---

## 1. Kiến trúc

### 1.1 Luồng

```
                          ┌──────────────────────┐
  raw query + history ──► │   select_context     │ ◄┈┈ ≤2 trường (CARD)
                          │  deterministic       │
                          │  < 600 token         │
                          └──────────┬───────────┘
                                     ▼
                          ┌──────────────────────┐
                          │      rewrite         │      LLM 30B
                          │  reasoning tự do     │      constrained CHỈ ở cuối
                          │  → JSON ở bước cuối  │
                          └──────────┬───────────┘
                                     ▼
                          ┌──────────────────────┐
                          │      project         │ ◄─── toàn bộ CARD
                          │   deterministic      │
                          └──────────┬───────────┘
                                     ▼
                          ┌──────────────────────┐
                          │  retrieve + rerank   │
                          └──────────┬───────────┘
                                     ▼
  raw query ──────────────►┌──────────────────────┐
  (đường vòng, KHÔNG        │      generate       │      LLM
   qua rewrite)             │  prose + verdict    │
                           └──────────┬───────────┘
                                      ▼
                            answer + citations + verdict
                                      │
                                      ▼  (chờ lượt N+1)
                          ┌──────────────────────┐
                          │    update_card       │      LLM, JSON constrained
                          │  BẤT ĐỒNG BỘ         │      ngoài critical path
                          └──────────┬───────────┘
                                     ▼  ops[]
                              ┌─────────────┐
                              │ CARD STORE  │
                              └─────────────┘
```

### 1.2 Hợp đồng từng node

| Node                | Vào                                                           | Ra                                          | LLM      |
| ------------------- | ------------------------------------------------------------- | ------------------------------------------- | -------- |
| `select_context`    | raw query, 2 lượt gần nhất, card                              | 2 lượt nguyên văn + ≤2 trường ứng viên      | không    |
| `rewrite`           | gói <600 token                                                | `standalone`, `resolutions[]`               | có       |
| `project`           | `standalone`, toàn bộ card                                    | `queries[]`, `filters`, `boosts`, `exclude` | không    |
| `retrieve + rerank` | queries, filters, boosts                                      | top-k chunks                                | reranker |
| `generate`          | **raw query**, chunks, history                                | prose answer, citations, verdict            | có       |
| `update_card`       | raw query, standalone, verdict, citations, card, **lượt N+1** | `ops[]`                                     | có       |

### 1.3 Bốn quyết định nằm ở mũi tên, không ở hộp

1. **Card vào `select_context` có trần cứng ≤2 trường.** `select_context` là node _giới hạn_ ngữ cảnh, không phải node làm giàu. Nó tồn tại để đảm bảo gói vào rewrite luôn dưới ngưỡng bất kể card đã phình đến đâu.
2. **Card vào `project` thì toàn bộ** — ở đây không có LLM đọc, chỉ có code ánh xạ trường sang filter/boost. Card dài bao nhiêu cũng không sao.
3. **Đường vòng raw query xuống `generate`** — `standalone` chết sau `project`.
4. **`update_card` nhận citations + verdict, không nhận chunks và không nhận prose.**

---

## 2. Node `select_context`

Không có LLM. Nhiệm vụ duy nhất: giữ gói đầu vào của rewrite dưới ngưỡng.

### Ngân sách

```
raw query                      ~30 token
2 lượt gần nhất, nguyên văn   ~300 token
≤2 trường card đã lọc          ~40 token
prompt                        ~200 token
──────────────────────────────────────────
tổng                          < 600 token
```

### Vì sao ngưỡng này là điều kiện bắt buộc

Nghiên cứu Context Rot (Chroma, 18 model gồm cả Qwen3) phân biệt **distractor** — nội dung liên quan về chủ đề nhưng không trả lời câu hỏi — với nội dung không liên quan. Kết quả đo: hiệu năng giảm khi độ dài input tăng, **và** giảm khi số distractor tăng; kết hợp cả hai gây sụt giảm đáng kể. Một distractor đã làm giảm rõ rệt, bốn distractor thì lao dốc.

Một card 6 nhóm trường ném vào rewrite chỉ cần giải chữ "nó" = 5 distractor. Đây là chẩn đoán cho hiện tượng "summary quá rối làm rewrite đi sai hướng".

### Luật chọn trường

Deterministic, theo thứ tự:

1. Xác định các span tham chiếu trong raw query (đại từ, cụm chỉ định, câu cụt).
2. Nếu không có span nào → **bỏ qua node rewrite hoàn toàn**, `standalone = raw query`.
3. Nếu có → chọn tối đa 2 trường card thuộc loại **định danh thực thể** (`thong_tin.tai_lieu`, `thong_tin.muc`, `chu_the`). Không bao giờ đưa `rang_buoc_phu_dinh`, `chua_tra_loi`, hay trục thời gian vào — chúng không phải ứng viên tham chiếu.

Bước 2 quan trọng về chi phí: phần lớn lượt không cần rewrite, và bỏ qua được một lần gọi LLM.

---

## 3. Node `rewrite`

### Hợp đồng

Bốn loại phép sửa của Choi et al., với mức rủi ro rất khác nhau:

| Phép                              | Ví dụ                           | Rủi ro   | Xử lý                    |
| --------------------------------- | ------------------------------- | -------- | ------------------------ |
| 1. Hoàn chỉnh tên, thay đại từ/NP | _"nó"_ → _"Điều 15"_            | Thấp     | LLM                      |
| 2. Bỏ discourse marker            | _"còn khoản 3"_ → _"khoản 3"_   | Rất thấp | **Regex, không cần LLM** |
| 3. Bắc cầu phạm vi                | thêm _"theo Nghị định 15/2020"_ | Cao      | LLM + ngân sách độ dài   |
| 4. Bổ sung thông tin nền          | thêm cụm giới từ                | Cao nhất | LLM + ngân sách độ dài   |

**Phép 2 là phép xoá duy nhất được phép.** Mọi thứ bị xoá ngoài discourse marker là vi phạm hợp đồng bảo toàn nghĩa.

**Ngân sách tăng độ dài:** phép 1–2 gần như không đổi độ dài, phép 3–4 làm câu dài ra. Đặt trần: `len(standalone) <= len(raw) * 2.5`. Vượt trần → loại rewrite, giữ query gốc. Đây là phòng vệ rẻ tiền chống oversummarization ngược (phình chữ).

### Xác minh output

Model trả về danh sách cặp `{span, replaces_with}`, **không trả về chuỗi cuối**. Code ghép:

- `span` phải khớp nguyên văn trong raw query
- `replaces_with` phải xuất hiện nguyên văn trong lịch sử hoặc trong 2 trường card được cấp
- Bất kỳ span nào không khớp → **loại toàn bộ rewrite**, không áp dụng một phần

Cách này chặn bốn kiểu hỏng của model nhỏ: phình chữ, bịa thực thể, rò rỉ khuôn mẫu ("Chắc chắn rồi! Đây là..."), trôi ngôn ngữ.

### Constrained decoding: chỉ ở bước cuối

**Không** bật JSON-mode cho toàn bộ lần gọi. Cho model suy luận tự do trước, chỉ áp grammar cho phần nộp JSON ở đuôi.

Cơ sở, và đây là con số quan trọng nhất cho quy mô 30B:

- Tam et al. (EMNLP 2024): ràng buộc định dạng làm giảm suy luận 10–15%, tới 27 điểm phần trăm trên benchmark toán. Cơ chế là **premature serialization** — model bị ép phát ra trường đáp án trước khi hoàn thành chuỗi suy luận.
- Nghiên cứu 2026: _"hiệu năng phục hồi bất cứ khi nào phần suy luận không bị ràng buộc đi trước phần nộp có cấu trúc, bất kể cơ chế cụ thể."_
- **Format tax phụ thuộc mạnh vào năng lực model**: Haiku giảm 36.2pp, GPT-4o-mini giảm 28.0pp, trong khi Opus 4.7 chỉ giảm ~5.3pp trên AIME. Model closed-weight phần lớn kháng được; open-weight thì không.

Hàm ý: mọi báo cáo "structured output chạy tốt" đều đến từ model lớn. Ở 30B, chi phí cao hơn hẳn.

**Cạm bẫy nếu làm agentic:** ràng buộc JSON Schema được biên dịch thành token mask theo grammar, khiến token gọi tool không thể tiếp cận khi decode (_Tool Suppression_). Không bật structured output cùng lúc với tool calling trong một lần gọi.

---

## 4. Card

> **Mục này đã được thay thế bởi [`ctx_kernel.md`](ctx_kernel.md).**
>
> Card dưới đây là *ví dụ minh hoạ cho một usecase HR*, không phải schema.
> Bộ khung tổng quát (lưới 4 neo x 5 chiều, envelope đồng nhất, phân tầng
> nguồn tin, ops) nằm trong `ctx_kernel.md`; tên trường theo domain nằm trong
> `domains/*.yaml`. Bảng ánh xạ giữa hai bên: `ctx_kernel.md` §14.

### 4.1 Schema

```json
{
  "phien": "hrm-8842",
  "cap_nhat_luot": 9,

  "chu_the": {
    "la_ai": { "gia_tri": "nhân viên", "nguon": "user_khai_bao", "luot": 2 },
    "cap_bac": { "gia_tri": "chuyên viên", "nguon": "hr_system" },
    "danh_tinh": { "gia_tri": "NV-2291", "nguon": "phien_dang_nhap" }
  },

  "thong_tin": {
    "chu_de": "phép năm",
    "tai_lieu": "Quy chế lao động v3.2",
    "muc": ["Mục 4.1 – Định mức", "Mục 4.3 – Chuyển phép tồn"],
    "hanh_dong": "tra cứu định mức và điều kiện chuyển tiếp",
    "nguon": "retrieval"
  },

  "pham_vi": {
    "phong_ban": [
      {
        "gia_tri": "Kỹ thuật",
        "t_fact_tu": "luot_2",
        "t_fact_den": "luot_9",
        "con_hieu_luc": false
      },
      {
        "gia_tri": "Sản phẩm",
        "t_fact_tu": "luot_9",
        "t_fact_den": null,
        "con_hieu_luc": true,
        "hieu_luc_thuc_te_tu": "2026-07-01"
      }
    ],
    "loai_hop_dong": { "gia_tri": "chính thức", "nguon": "hr_system" },
    "tham_nien": { "gia_tri": "dưới 12 tháng", "vao_lam": "2026-03" }
  },

  "t_noi_dung": { "ky": "năm 2026", "moc_tinh": "2026-12-31" },

  "rang_buoc_phu_dinh": [
    {
      "loai_tru": "nghỉ ốm",
      "phat_ngon_goc": "không tính nghỉ ốm nhé",
      "luot": 4,
      "con_hieu_luc": true
    }
  ],

  "chua_tra_loi": [
    {
      "cau_hoi": "chuyển phép tồn với nhân viên dưới 12 tháng",
      "thieu_gi": "Mục 4.3 chỉ nêu trường hợp đủ 12 tháng",
      "goi_y_tiep": "Phụ lục 2 / quy định nhân viên mới",
      "luot": 3,
      "trang_thai": "chua_giai_quyet"
    }
  ]
}
```

### 4.2 Vì sao JSON chứ không phải văn xuôi

Phát hiện phản trực giác từ Context Rot: _tài liệu mạch lạc, có cấu trúc tốt làm việc truy hồi khó hơn các đoạn xáo trộn ngẫu nhiên — model bị mắc kẹt đi theo mạch tự sự thay vì tìm thông tin cụ thể._

Summary văn xuôi tạo ra đúng mạch tự sự đó. Card JSON là các mục rời rạc, không có mạch để bám theo.

### 4.3 Ba trường dễ bị bỏ sót

**Hai trục thời gian.** `t_noi_dung` (câu hỏi nói về thời điểm nào) khác `t_fact` (mục card này đúng từ khi nào, còn đúng không). Với văn bản pháp luật, trục thứ hai chính là bài toán hiệu lực. Không ghi đè khi giá trị thay đổi — đóng khoảng và thêm bản mới, vì câu trả lời ở lượt 4 _không sai tại thời điểm nó được đưa ra_.

**Ràng buộc phủ định.** Không lưu thì lượt sau retrieve lại đúng thứ người dùng vừa loại trừ. Đây là kiểu lỗi khiến người dùng nghĩ chatbot không nghe mình.

**Phần chưa trả lời.** Phân biệt "đã hỏi" với "đã được thoả mãn". Cần cho việc diễn giải _"vậy tôi phải làm sao"_ ở lượt sau.

### 4.4 Phân tầng quyền ghi

| Nguồn           | Độ tin                    | Được ghi vào                               | Sinh ra          |
| --------------- | ------------------------- | ------------------------------------------ | ---------------- |
| `citations`     | grounded, từ dữ liệu thật | `thong_tin`                                | filter cứng được |
| `user_khai_bao` | cao                       | `chu_the`, `pham_vi`, `rang_buoc_phu_dinh` | filter cứng được |
| `verdict`       | model suy luận            | `chua_tra_loi`, `dieu_kien`                | **chỉ boost**    |
| prose answer    | không kiểm chứng          | **không ghi vào đâu cả**                   | —                |

**Verdict không được ghi đè trường nào citation đã ghi.** Model kết luận "đang nói về Mục 4.1" nhưng citation cho thấy Mục 4.3 → card theo citation. Đây là cơ chế tự sửa lỗi khiến card hội tụ về đúng thay vì trôi xa dần.

**Prose không bao giờ vào card.** Đưa văn xuôi do model sinh vào memory rồi lượt sau đọc lại để sinh tiếp = ảo giác trở thành "sự thật đã ghi nhớ". Sau vài lượt không phân biệt được đâu là điều tài liệu nói, đâu là điều model từng nói.

### 4.5 Đổi chủ đề: phân loại trường, không đo similarity

Khi chủ đề đổi, **không reset card**. Card cũ vẫn còn nhưng không được nạp vào context vì phép chiếu retrieval không khớp.

Ranh giới: **trường mô tả con người thì bền, trường mô tả chủ đề thì theo chủ đề.**

| Giữ xuyên chủ đề                               | Bỏ khi đổi chủ đề    |
| ---------------------------------------------- | -------------------- |
| `chu_the`                                      | `thong_tin`          |
| `pham_vi` (phòng ban, hợp đồng, thâm niên)     | `rang_buoc_phu_dinh` |
| `chua_tra_loi` (ngủ đông, đánh dấu chủ đề gốc) | `t_noi_dung`         |

Phân loại một lần khi thiết kế card, không cần đo ngưỡng gì. Gần với cách Letta tách `persona`/`human` block (bền) khỏi archival memory (truy hồi theo nhu cầu).

---

## 5. Node `generate` và verdict

Generate viết văn xuôi tự do trước, **nối khối JSON ở cuối**, chỉ áp constrained decoding cho phần đuôi:

```json
{
  "ket_luan": "khong_du_can_cu",
  "citation_thuc_dung": [1, 3],
  "dieu_kien": ["áp dụng cho nhân viên đủ 12 tháng"],
  "thieu_gi": "Quy chế v3.2 không nêu trường hợp dưới 12 tháng",
  "goi_y_tra_tiep": "Phụ lục 2 / quy định nhân viên mới"
}
```

`ket_luan` là enum đóng: `co` / `khong` / `co_dieu_kien` / `khong_du_can_cu` / `mau_thuan`. Đây là phân loại — loại tác vụ mà ràng buộc schema **giúp ích** chứ không hại.

`citation_thuc_dung` là trường giá trị nhất: citations hiển thị là những chunk được retrieve, nhưng chỉ một phần thực sự chống đỡ câu trả lời. **Chỉ nhóm thực dùng mới được ghi vào `thong_tin`.**

Nếu vẫn lo format tax: tách verdict thành một lần gọi riêng chạy bất đồng bộ. Verdict không cần có mặt lúc trả lời, chỉ cần có trước lượt sau.

---

## 6. Node `update_card`

### 6.1 Chạy sau lượt N+1, không phải ngay sau lượt N

Lượt kế tiếp của người dùng là ground truth đáng tin hơn verdict (vốn là model tự chấm chính mình):

| Tín hiệu ở lượt N+1      | Hành động lên card của lượt N                             |
| ------------------------ | --------------------------------------------------------- |
| _"không phải cái đó"_    | Vô hiệu mọi mục ghi từ verdict lượt N                     |
| _"đúng rồi, vậy còn..."_ | Nâng độ tin các mục đó                                    |
| Hỏi lại gần y hệt        | Câu trả lời trước không thoả mãn, dù verdict tự chấm `co` |

Node vốn đã bất đồng bộ nên độ trễ này không tốn gì.

### 6.2 Op-diff, không ghi đè toàn bộ

Model chỉ sinh danh sách phép thay đổi:

```json
{
  "ops": [
    {
      "op": "set",
      "truong": "pham_vi.phong_ban",
      "gia_tri": "Sản phẩm",
      "nguon": "user_khai_bao",
      "bang_chung": "tôi chuyển sang phòng Sản phẩm"
    },
    { "op": "close", "truong": "pham_vi.phong_ban[0]", "t_fact_den": "luot_9" },
    { "op": "clear", "truong": "rang_buoc_phu_dinh[1]" }
  ]
}
```

Bắt model chép lại toàn bộ card mỗi lượt là chép lại cơ hội bóp méo; sau vài lượt card trôi khỏi thực tế mà không truy được lỗi bắt đầu từ đâu. Op log cũng cho phép tái dựng card từ đầu để debug.

### 6.3 Ngoài critical path — bắt buộc

Từ chính bài báo Mem0: bản v1.0.0 đặt `async_mode=True` làm mặc định vì việc ghi memory đồng bộ chặn pipeline phản hồi trong production từ rất lâu trước khi nó lộ ra trên benchmark.

---

## 8. Lộ trình

### Giai đoạn 1 — Đường đi tối giản (1 tuần)

- `select_context` (chỉ phát hiện span tham chiếu, chưa dùng card)
- `rewrite` với span-replacement + xác minh
- `project` deterministic
- `generate` nhận raw query — **N2 phải đúng ngay từ đây**

**Cổng ra:** recall@k vượt baseline. Không vượt thì dừng, không đi tiếp.

### Giai đoạn 2 — Card (2 tuần)

- Card store + op-diff
- `update_card` bất đồng bộ, chạy sau lượt N+1
- `project` đọc card sinh filter/boost
- Verdict block trong `generate`

**Cổng ra:** filter và boost sinh từ card cải thiện recall@k; card không gây kết quả rỗng.

### Giai đoạn 3 — Cấp trường cho rewrite (1 tuần)

- `select_context` cấp ≤2 trường card cho rewrite
- **Chỉ làm nếu §7.3 cho thấy mức 3 không tệ hơn mức 2**

### Giai đoạn 4 — Tinh chỉnh

- Cân nhắc model editing nhỏ thay cho prompt 30B (EdiT5 đạt exact match cao hơn và SARI-delete tốt hơn T5 base, với độ trễ giảm đáng kể và ít tham số hơn)

---

## 9. Những gì đã bác — không xây lại

| Đã bác                                                    | Lý do                                                                                                |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Slot schema với `level` / `ttl` / `vocab` / `filter_mode` | **Bác có điều kiện.** Cái bị bác là bốn cơ chế này — mỗi cái sinh ra một cách vá lỗi phải bảo trì theo domain. **Không** bác việc tách tên trường ra manifest khai báo: đó chính là cách `ctx_kernel.md` §8 đạt mục tiêu tái sử dụng. |
| Node phát hiện đổi chủ đề bằng ngưỡng similarity          | SOTA F1 27.8; tệ nhất đúng ở vùng phiên dài                                                          |
| Bộ phân loại follow-up riêng bằng LLM                     | LangChain gộp vào chính prompt rewrite: _"viết lại nếu cần, ngược lại trả về nguyên trạng"_          |
| Filter cứng sinh từ ngữ cảnh suy đoán                     | Nguồn duy nhất có thể làm hệ thống trả về rỗng                                                       |
| Summary văn xuôi làm bộ nhớ chính                         | Mạch tự sự làm truy hồi khó hơn đoạn rời rạc                                                         |
| `ConversationSummaryBufferMemory`                         | Đã deprecated; hiện dùng checkpointer + tự quản lý                                                   |

---

## 10. Rủi ro đã biết

| Rủi ro                      | Dấu hiệu                             | Phòng vệ                                                  |
| --------------------------- | ------------------------------------ | --------------------------------------------------------- |
| Distractor từ card          | Rewrite đi sai hướng ở phiên dài     | Trần ≤2 trường; đo §7.3                                   |
| Format tax ở 30B            | JSON đúng cú pháp nhưng nội dung sai | Reasoning trước, constrain ở cuối                         |
| Tool Suppression            | Model im lặng bỏ qua tool            | Không bật structured output + tool call chung một lần gọi |
| Nhiễm độc card              | Trả lời lạc dần qua nhiều lượt       | Phân tầng quyền ghi; verdict chỉ sinh boost               |
| Oversummarization           | SARI-delete > 0                      | Bất biến tự động; ngân sách độ dài ×2.5                   |
| `update_card` chặn phản hồi | Độ trễ tăng theo độ dài phiên        | Bất đồng bộ, chạy sau lượt N+1                            |

---

## 11. Chỗ chưa có bằng chứng

Ghi ra để không nhầm với phần đã chứng minh.

- **Format tax cụ thể ở 30B open-weight.** Con số 28–36pp là từ Haiku và GPT-4o-mini. 30B có thể khá hơn nhưng không có số liệu. Phải tự đo.
- **Ngưỡng 600 token.** Suy ra từ nguyên lý distractor, không phải từ một phép đo trực tiếp trên cấu hình này.
- **Trần ≤2 trường card.** Cùng lý do trên.
- **Hệ số ×2.5 cho ngân sách độ dài.** Đặt theo cảm tính, cần chỉnh theo dữ liệu.
- **Số liệu benchmark memory (Mem0/Zep/Letta)** không đáng tin: mỗi bên tự công bố điểm của mình trên harness riêng, các con số LoCoMo lưu hành mâu thuẫn nhau (83.2 vs 68.5 vs 92.5 cho cùng đối tượng), và có bản audit chỉ ra vấn đề phương pháp luận. Không dùng chúng để chọn kiến trúc.

---

## 12. Đọc thêm

| Chủ đề                                            | Nguồn                                           |
| ------------------------------------------------- | ----------------------------------------------- |
| Decontextualization (định nghĩa task, 4 phép sửa) | Choi et al., TACL 2021                          |
| Context Rot (distractor, ngưỡng context)          | Chroma Research, 2025                           |
| Format tax                                        | Tam et al., EMNLP 2024 — _Let Me Speak Freely?_ |
| Topic shift detection                             | TIAGE, EMNLP 2021                               |
| Bộ nhớ ba tầng, card tự sửa                       | MemGPT, arXiv 2310.08560                        |
| Neo thời gian cho memory                          | Graphiti / Zep                                  |
| CQR datasets                                      | CANARD, QReCC, TopiOCQA                         |
