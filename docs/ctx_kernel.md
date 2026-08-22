# Context Card Kernel

Bộ khung ngữ cảnh hội thoại, bất biến qua mọi usecase.

Tài liệu này thay thế §4 (Card) của `docs/process_query.md` và tổng quát hoá bản phác trong `app/modules/ctx.md`. Các phần còn lại của `process_query.md` (luồng, node `rewrite`, node `generate`) vẫn giữ nguyên hiệu lực.

---

## 0. Bối cảnh và tiêu chí thành công

`app/modules/ctx.md` đã phác đúng hạt nhân: mọi query đều mang theo ngữ cảnh về **ai hỏi**, **hỏi về cái gì**, **phạm vi không–thời gian**, và **nguồn tri thức**. Nhưng bản phác đó — cũng như card §4.1 trong `process_query.md` — trộn lẫn hai thứ khác hẳn nhau:

- _bộ khung ngữ nghĩa_, bất biến, dùng cho mọi usecase;
- _tên trường của một domain HR cụ thể_ (`cap_bac`, `phong_ban`, `loai_hop_dong`).

Tài liệu này tách hai thứ đó. Bộ khung là code, viết một lần. Tên trường là manifest, viết lại mỗi domain.

**Tiêu chí thành công, kiểm tra được:** đổi sang domain mới = viết một file manifest. Không một tên trường mang tính domain nào được xuất hiện trong `.py` hay trong prompt template. Xem bất biến I6 ở §12.

---

## 1. Luận điểm trung tâm

Ngữ cảnh của một câu hỏi không phải là _tập hợp trường dữ liệu_. Nó là tập hợp **vai ngữ nghĩa** — và tập vai này ổn định qua mọi domain, vì nó phản ánh cấu trúc của hành vi hỏi chứ không phản ánh nội dung được hỏi.

Mọi câu hỏi tra cứu đều phân rã thành bốn **neo**:

| Neo        | Câu hỏi nó trả lời                    | Ví dụ                                 |
| ---------- | ------------------------------------- | ------------------------------------- |
| `asker`    | Ai đang hỏi?                          | NV-2291, chuyên viên, phòng Kỹ thuật  |
| `target`   | Hỏi về ai / cái gì?                   | nhân viên thử việc, năm 2026          |
| `source`   | Câu trả lời nằm ở đâu?                | Quy chế v3.2 Mục 4.1, bảng`nghi_phep` |
| `dialogue` | Cuộc hội thoại đang ở trạng thái nào? | còn câu hỏi chưa được thoả mãn        |

Và mỗi neo được mô tả trên năm **chiều**:

| Chiều       | Nghĩa                        |
| ----------- | ---------------------------- |
| `identity`  | định danh / locator          |
| `attribute` | thuộc tính phân loại         |
| `space`     | phạm vi không gian / tổ chức |
| `time`      | phạm vi thời gian            |
| `topic`     | chủ đề, ý định               |

**Lưới 4 × 5 này là bất biến.** Mọi trường của mọi domain rơi vào đúng một ô. Manifest chỉ nói: domain này dùng những ô nào, đặt tên gì, chiếu ra sao.

### Vì sao tin rằng lưới này đúng

Không phải vì nó gọn, mà vì nó **sinh ra những ô mà thiết kế viết tay đã bỏ sót**: cụ thể là `source.time` và `source.space` (§3). Một trừu tượng chỉ mô tả lại cái đã có thì vô dụng; một trừu tượng chỉ ra chỗ thiếu thì có giá trị. §14 là phần chứng minh.

---

## 2. Ô hợp lệ và ô bị cấm

|              | `identity`            | `attribute`            | `space`                       | `time`                      | `topic`                        |
| ------------ | --------------------- | ---------------------- | ----------------------------- | --------------------------- | ------------------------------ |
| **asker**    | ai đang hỏi           | cấp bậc, loại hợp đồng | phòng ban, chi nhánh          | thâm niên, ngày vào         | ⛔                             |
| **target**   | đối tượng được hỏi    | thuộc tính đối tượng   | phạm vi đối tượng             | **kỳ mà câu hỏi hướng tới** | **chủ đề + ý định**            |
| **source**   | tài liệu / bảng / mục | phiên bản, loại nguồn  | **phạm vi áp dụng của nguồn** | **hiệu lực của nguồn**      | nguồn bao phủ chủ đề gì        |
| **dialogue** | session, turn         | trạng thái routing     | ⛔                            | ⛔                          | **câu hỏi chưa được thoả mãn** |

17 ô hợp lệ, **3 ô bị cấm**. Ba ô này là bất biến kiểm tra được, không phải "chưa dùng tới":

- `asker.topic` — người hỏi không có chủ đề; chủ đề luôn thuộc về cái được hỏi. Dữ liệu nào muốn vào ô này thì nó thuộc về `target.topic`.
- `dialogue.space` và `dialogue.time` — trục hội thoại đã nằm trong envelope của **mọi** fact (§4). Đặt thêm ở đây là nhân đôi nguồn sự thật.

**Ô `target.topic` là ô duy nhất được phép nối vào chuỗi query.** Đây là cách phát biểu lại nguyên tắc N3 của `process_query.md` dưới dạng bất biến kiểm tra bằng test, thay vì một lời khuyên.

---

## 3. Bốn trục thời gian

Đây là phần đóng góp chính, và là chỗ bản card cũ hụt nhiều nhất. Bốn trục thường xuyên bị gộp làm một; với văn bản pháp luật / quy chế, gộp là **sai kết quả**, không phải mất tinh tế.

### 3.1 Hai trục là metadata của mọi fact — nằm trong envelope

| Trục      | Nghĩa                                             | Ví dụ                               |
| --------- | ------------------------------------------------- | ----------------------------------- |
| `t_conv`  | Hội thoại biết fact này từ lượt nào, tới lượt nào | biết từ lượt 2, bị thay ở lượt 9    |
| `t_world` | Fact này đúng trong thế giới thực từ khi nào      | chuyển phòng có hiệu lực 2026-07-01 |

Hai trục này khác nhau và cả hai đều cần. Người dùng nói ở **lượt 9** rằng họ đã chuyển phòng từ **tháng 7**: `t_conv.from_turn = 9`, `t_world.from = 2026-07-01`.

Câu trả lời ở lượt 4 _không sai tại thời điểm nó được đưa ra_. Vì vậy không bao giờ ghi đè — chỉ đóng khoảng và thêm bản mới.

### 3.2 Hai trục là nội dung của fact cụ thể — nằm trong ô

| Ô             | Nghĩa                                  | Ví dụ                                         |
| ------------- | -------------------------------------- | --------------------------------------------- |
| `target.time` | Câu hỏi hỏi**về** thời kỳ nào          | "phép năm 2026"                               |
| `source.time` | Nguồn**có hiệu lực** trong thời kỳ nào | Quy chế v3.2 hiệu lực 2025-01-01 → 2026-08-31 |

`source.time` là ô mà không thiết kế viết tay nào trong repo có, và nó là ô quan trọng nhất cho tra cứu quy chế:

> Câu hỏi về năm 2026 phải được trả lời bằng **phiên bản tài liệu có hiệu lực trong năm 2026**, không phải bằng phiên bản mới nhất trong kho.

Không có `source.time` thì hệ thống trả lời câu hỏi về quá khứ bằng quy định hiện hành, và **không có cách nào phát hiện** — câu trả lời trông hoàn toàn hợp lý. Đây là kiểu lỗi tệ nhất: sai mà không có tín hiệu.

Cùng logic áp cho không gian. `source.space` = tài liệu này áp dụng cho chi nhánh / đơn vị nào. Câu hỏi từ người ở đơn vị X không được trả bằng quy chế chỉ áp dụng cho đơn vị Y.

Hai ô này được dùng qua luật dẫn xuất D1 và D2 (§9), không cần LLM tham gia.

---

## 4. Envelope

Mọi giá trị trong card, không ngoại lệ, có đúng hình dạng này. Đây là điều kiện để `project` và `update_card` là code tổng quát thay vì một chuỗi nhánh `if` theo tên trường.

```json
{
  "id": "asker.space.dept#1",
  "value": "Sản phẩm",
  "polarity": "include",
  "source": "user_stated",
  "confidence": "certain",
  "t_conv": { "from_turn": 9, "to_turn": null, "active": true },
  "t_world": { "from": "2026-07-01", "to": null },
  "evidence": "tôi chuyển sang phòng Sản phẩm"
}
```

| Trường       | Ràng buộc                                                         |
| ------------ | ----------------------------------------------------------------- |
| `id`         | `anchor.dim.key#n` — ổn định; dùng cho op `close` và cho citation |
| `value`      | scalar, list, hoặc`{"ref": "<id>"}`                               |
| `polarity`   | `include` hoặc `exclude` — xem §5                                 |
| `source`     | enum đóng, xem §7                                                 |
| `confidence` | `certain` / `probable` / `inferred`                               |
| `t_conv`     | bắt buộc với mọi fact                                             |
| `t_world`    | tuỳ chọn; vắng nghĩa là "luôn đúng"                               |
| `evidence`   | **trích nguyên văn**, không phải diễn giải của model              |

`evidence` phải là trích nguyên văn là một **luật cứng**, không phải khuyến nghị. Cho phép model viết diễn giải vào đây là mở cửa sau cho văn xuôi vào card — và văn xuôi do model sinh, đọc lại ở lượt sau, sẽ trở thành "sự thật đã ghi nhớ". Sau vài lượt không phân biệt được đâu là điều tài liệu nói, đâu là điều model từng nói.

---

## 5. Polarity thay cho danh sách ràng buộc phủ định riêng

Card cũ có `negative_constraints` là một danh sách riêng, và vì cấu trúc đó nó **chỉ loại trừ được chủ đề**. Nhưng người dùng loại trừ đủ thứ:

| Phát ngôn                      | Ô                  | polarity |
| ------------------------------ | ------------------ | -------- |
| "không tính nghỉ ốm"           | `target.topic`     | exclude  |
| "đừng lấy bản cũ"              | `source.time`      | exclude  |
| "bỏ qua quy định chi nhánh HN" | `source.space`     | exclude  |
| "trừ nhân viên thời vụ"        | `target.attribute` | exclude  |

Đưa `polarity` vào envelope làm mọi ô đều loại trừ được, và xoá hẳn một cấu trúc dữ liệu đặc biệt. `project` chiếu nó thành `must_not` (Qdrant) hoặc `NOT IN` (SQL) bằng **cùng đoạn code** chiếu `include`.

---

## 6. Vòng đời: suy ra từ neo, không cần bảng tra

`process_query.md` §4.5 duy trì một bảng tay liệt kê trường nào bền, trường nào theo chủ đề. Bảng đó phải bảo trì mỗi domain. Với lưới, nó rút thành một luật:

> **Fact neo vào `asker` và `dialogue` thì bền. Fact neo vào `target` và `source` thì theo chủ đề.**

Đúng về mặt trực giác: mô tả con người thì bền, mô tả cái đang tra cứu thì đổi theo cái đang tra cứu. Và không cần quyết định gì thêm khi thêm trường mới — vị trí của nó trong lưới đã quyết định vòng đời.

**Một ngoại lệ, có chủ ý:** fact có `source: user_stated` **không bao giờ bị tự động bỏ**, kể cả khi neo vào `target` hay `source`. Nó chỉ đóng khoảng khi bị chính người dùng phủ nhận. Người dùng nói một câu rồi hệ thống lặng lẽ quên là kiểu lỗi khiến người ta nghĩ chatbot không nghe mình — không đánh đổi lấy sự gọn gàng.

"Đổi chủ đề" ở đây **không cần bộ phát hiện**: nó là hệ quả của việc `target.topic` được ghi đè bởi giá trị mới từ `retrieved` / `sql_result`. Không đo similarity, không đặt ngưỡng. (Lý do bác node phát hiện đổi chủ đề: xem `process_query.md` N4.)

---

## 7. Phân tầng nguồn tin

Enum `source` đóng. Thứ tự trong bảng là thứ tự quyền ghi đè.

| `source`          | Độ tin             | Được ghi vào                      | Chiếu ra      |
| ----------------- | ------------------ | --------------------------------- | ------------- |
| `session`         | định danh xác thực | `asker.*`                         | filter cứng   |
| `external_system` | hệ thống ngoài     | `asker.*`                         | filter cứng   |
| `user_stated`     | người dùng tự khai | `asker.*`, `target.*`, `source.*` | filter cứng   |
| `retrieved`       | grounded, từ kho   | `source.*`, `target.topic`        | filter cứng   |
| `sql_result`      | grounded, từ DB    | `source.*`, `target.topic`        | filter cứng   |
| `verdict`         | model tự chấm      | **chỉ `dialogue.*`**              | **chỉ boost** |
| _prose_           | không kiểm chứng   | **không đâu cả**                  | —             |

Hai luật cứng:

1. **`verdict` không được ghi đè fact do `retrieved` / `sql_result` / `user_stated` ghi.** Model kết luận "đang nói về Mục 4.1" nhưng citation cho thấy Mục 4.3 → card theo citation. Đây là cơ chế khiến card hội tụ về đúng thay vì trôi xa dần qua các lượt.
2. **`verdict` chỉ được ghi vào neo `dialogue`.** Nó không biết gì về thế giới; nó chỉ biết cuộc hội thoại vừa rồi có thoả mãn hay không.

---

## 8. Manifest theo domain

Đây là **toàn bộ** phần phải viết lại khi đổi usecase. Nó khai báo ô nào tồn tại, đặt tên gì, và chiếu thế nào sang từng consumer. Bản đầy đủ: `domains/hrm.yaml`.

```yaml
domain: hrm
consumers: [rag, sql]

asker:
  space:
    dept:
      multi: true
      rag: { filter_key: dept, on_empty: demote_to_boost }
      sql: { column: nhan_vien.phong_ban, predicate: IN }

target:
  time:
    period:
      rag: { via: D1 } # không filter trực tiếp; xem §9
      sql: { column: nghi_phep.ky, predicate: BETWEEN }
  topic:
    subject:
      to_query_string: true # ô DUY NHẤT được phép mang cờ này

source:
  time:
    validity:
      rag: { filter_key_from: valid_from, filter_key_to: valid_to }

derive: [D1, D2, D3]
```

Đổi domain = viết file này. Code không đổi.

---

## 9. Luật dẫn xuất

Danh sách **đóng, ba luật**. Cố tình không làm rule engine — đó chính là cái bẫy khiến slot schema cũ phình ra và bị bác (§13).

**D1 — Neo phiên bản nguồn theo kỳ được hỏi.**
`filter: source.time.validity ∋ target.time.period`
Vắng `target.time` thì mặc định `now`. Đây là luật giải bài toán hiệu lực ở §3, và là lý do `target.time` không cần `filter_key` riêng cho nhánh RAG.

**D2 — Phạm vi nguồn phải phủ phạm vi đối tượng.**
`filter: target.space ⊆ source.space`; `source.space` rỗng nghĩa là áp dụng toàn bộ.

**D3 — Kế thừa asker → target khi không có đối tượng tường minh.**
Không có `target.identity` thì `target.* := asker.*` cho mục đích chiếu.
Luật này giải quyết "tôi" một cách **cấu trúc**, bằng code, thay vì nhờ LLM suy luận. Chuyển việc ra khỏi LLM là hướng đúng cho mô hình 30B.

Thêm luật mới phải sửa tài liệu này và thêm test. Manifest **không** được tự định nghĩa luật.

---

## 10. Chiếu sang consumer

`project` là **bộ thông dịch manifest**, không phải code ánh xạ tay. Một hàm, chạy cho mọi domain và mọi consumer.

```
project(card, manifest, consumer) -> QuerySpec
```

| Ô                       | → RAG (Qdrant)                  | → SQL                        |
| ----------------------- | ------------------------------- | ---------------------------- |
| `target.topic`          | **chuỗi query** (ô duy nhất)    | mô tả ý định cho bộ sinh SQL |
| `source.identity`       | `must` trên doc_id / section_id | chọn bảng                    |
| `source.time` (qua D1)  | `must` khoảng hiệu lực          | —                            |
| `source.space` (qua D2) | `must`                          | —                            |
| `asker.*`               | `must` hoặc boost theo manifest | `WHERE` + row-level security |
| `target.*`              | `must` hoặc boost               | `WHERE`                      |
| `polarity: exclude`     | `must_not`                      | `NOT IN`                     |
| `dialogue.*`            | **chỉ boost**                   | —                            |

### 10.1 Bậc thang xuống thang khi rỗng

Deterministic, không LLM. Filter cứng là nguồn duy nhất khiến hệ thống trả về rỗng, nên bắt buộc phải có đường lùi:

1. Chạy đủ filter.
2. `hits == 0` → hạ fact `confidence: inferred` xuống boost, chạy lại.
3. `hits == 0` → chỉ giữ filter từ `retrieved` / `sql_result`, chạy lại.
4. `hits == 0` → bỏ hết filter, chỉ boost.
5. Ghi `degraded_level` vào state để `generate` nói rõ với người dùng, và để đo được.

**Cần xác minh sớm:** `must` / `must_not` của Qdrant ánh xạ trực tiếp và sạch, nhưng **boost là thứ được hỗ trợ native yếu nhất** — `should` ảnh hưởng tới việc khớp chứ không phải là hệ số nhân điểm như trực giác. Bước 2 và 4 của bậc thang phụ thuộc vào cơ chế boost có thật (Query API `formula`, prefetch + rescore, hoặc rescore phía client). Cần một prototype nhỏ trước khi xây `project`.

---

## 11. Ops — cách card thay đổi

Model không bao giờ chép lại card. Nó chỉ sinh phép biến đổi. **Năm op, danh sách đóng:**

```json
{"op": "assert", "anchor": "asker", "dim": "space", "key": "dept",
 "value": "Sản phẩm", "source": "user_stated",
 "t_world": {"from": "2026-07-01"},
 "evidence": "tôi chuyển sang phòng Sản phẩm"}

{"op": "close", "id": "asker.space.dept#0", "to_turn": 9}

{"op": "exclude", "anchor": "target", "dim": "topic",
 "value": "nghỉ ốm", "source": "user_stated",
 "evidence": "không tính nghỉ ốm nhé"}

{"op": "open_gap", "value": "chuyển phép tồn khi dưới 12 tháng",
 "gap": "Mục 4.3 chỉ nêu trường hợp đủ 12 tháng",
 "lead": "Phụ lục 2", "source": "verdict"}

{"op": "resolve_gap", "id": "dialogue.topic#0"}
```

**Không có `delete`.** Không bao giờ xoá — chỉ `close`. Op log cho phép tái dựng card từ đầu để debug, và rollback khi phát hiện nhiễm độc.

Bắt model chép lại toàn bộ card mỗi lượt là chép lại cơ hội bóp méo; sau vài lượt card trôi khỏi thực tế mà không truy được lỗi bắt đầu từ đâu.

### 11.1 Hai pha ghi

Sửa một mâu thuẫn trong thiết kế cũ: `update_card` chạy sau lượt N+1 nhưng lại được kỳ vọng có mặt cho chính lượt N+1.

| Pha    | Chạy khi             | Ghi gì                                                  | Vì sao                                                                                       |
| ------ | -------------------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| **P1** | ngay sau lượt N      | `user_stated`, `retrieved`, `sql_result`                | Không cần lượt sau xác nhận. Chờ thì lượt N+1 retrieve mà thiếu đúng ràng buộc vừa được nêu. |
| **P2** | sau khi lượt N+1 tới | chỉ fact`source: verdict` — nâng/hạ độ tin, đóng khoảng | Verdict là model tự chấm mình, nên mới cần ground truth từ lượt sau.                         |

Tín hiệu cho P2:

| Lượt N+1 nói gì      | Làm gì với fact verdict của lượt N |
| -------------------- | ---------------------------------- |
| "không phải cái đó"  | `close` toàn bộ                    |
| "đúng rồi, vậy còn…" | nâng`confidence`                   |
| hỏi lại gần y hệt    | coi như chưa thoả mãn,`open_gap`   |

Cả hai pha đều ngoài critical path của việc trả lời.

### 11.2 Trần cho `update_card`

`update_card` có LLM đọc card, nên card **có** đi vào context. Trần là bắt buộc — nếu không thì vấn đề distractor (lý do `select_context` bị giới hạn 600 token) quay lại nguyên vẹn ở node kế bên.

`update_card` không đọc card thô. Nó đọc một projection: chỉ fact `t_conv.active == true`, trần N fact mỗi neo, ưu tiên `from_turn` giảm dần. Fact đã đóng khoảng nằm trong op log — tái dựng được để debug, nhưng không nạp vào prompt.

---

## 12. Bất biến — kiểm tra bằng test

|     | Bất biến                                                                                           |
| --- | -------------------------------------------------------------------------------------------------- |
| I1  | Mọi fact nằm trong đúng một ô hợp lệ;**3 ô cấm** ở §2 luôn rỗng                                    |
| I2  | Chỉ ô mang cờ`to_query_string` được nối vào chuỗi query — và chỉ `target.topic` được mang cờ đó    |
| I3  | Mọi fact có`source` thuộc enum §7; không fact nào có nguồn là văn xuôi model sinh                  |
| I4  | Fact`source: verdict` chỉ tồn tại ở neo `dialogue`                                                 |
| I5  | Không op nào xoá fact;`close` là cách duy nhất kết thúc một fact                                   |
| I6  | `grep` tên trường domain (`dept`, `level`, `tenure`…) chỉ trúng manifest, không trúng `.py`/prompt |
| I7  | Prompt của`update_card` không bao giờ chứa fact `active == false`                                  |
| I8  | `evidence` là chuỗi con của phát ngôn người dùng hoặc của chunk được trích                         |

I6 là bài kiểm tra trực tiếp cho mục tiêu tái sử dụng. I2 là nguyên tắc N3 phát biểu dưới dạng test.

---

## 13. Cố tình không có

Ghi ra để lần sau đọc lại không tưởng là thiếu sót.

| Không có                                | Vì sao                                                                                                                                    |
| --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `ttl`, `vocab`, `filter_mode` trên slot | Đã bác: mỗi cái sinh ra một cơ chế vá lỗi phải bảo trì theo domain. Hiệu lực đã nằm trong`t_conv`/`t_world`; chiếu đã nằm trong manifest. |
| Node phát hiện đổi chủ đề               | SOTA TIAGE F1 27.8, tệ nhất đúng ở vùng phiên dài. §6 biến nó thành hệ quả của việc ghi`target.topic`.                                    |
| Bảng tra vòng đời theo trường           | §6 suy từ neo.                                                                                                                            |
| Cấu trúc riêng cho ràng buộc phủ định   | §5 dùng`polarity` trên envelope.                                                                                                          |
| Rule engine cho luật dẫn xuất           | §9 là danh sách đóng ba luật.                                                                                                             |
| Văn xuôi ở bất kỳ trường nào            | Kể cả`evidence` — phải là trích nguyên văn.                                                                                               |

---

## 14. Ánh xạ ví dụ HR — chứng minh lưới phủ được

Card §4.1 của `process_query.md`, đặt vào lưới:

| Trường cũ                                   | Ô                                             |
| ------------------------------------------- | --------------------------------------------- |
| `chu_the.la_ai`                             | `asker.identity.role`                         |
| `chu_the.cap_bac`                           | `asker.attribute.level`                       |
| `chu_the.danh_tinh`                         | `asker.identity.id`                           |
| `pham_vi.phong_ban[]`                       | `asker.space.dept`                            |
| `pham_vi.loai_hop_dong`                     | `asker.attribute.contract`                    |
| `pham_vi.tham_nien`                         | `asker.time.tenure`                           |
| `thong_tin.chu_de` + `thong_tin.hanh_dong`  | `target.topic.subject`                        |
| `thong_tin.tai_lieu`                        | `source.identity.doc`                         |
| `thong_tin.muc[]`                           | `source.identity.section`                     |
| `t_noi_dung`                                | `target.time.period`                          |
| `rang_buoc_phu_dinh[]`                      | `target.topic.subject`, `polarity: exclude`   |
| `chua_tra_loi[]`                            | `dialogue.topic.gap`                          |
| `t_fact_tu` / `t_fact_den` / `con_hieu_luc` | envelope`t_conv`                              |
| `hieu_luc_thuc_te_tu`                       | envelope`t_world`                             |
| —                                           | `source.time.validity` ← **ô cũ không có**    |
| —                                           | `source.space.applies_to` ← **ô cũ không có** |

Phủ 100%, không dư trường nào, và lộ ra hai ô thiếu. Đây là bằng chứng cho §1.

---

## 15. Còn bỏ ngỏ

Ghi ra để không nhầm với phần đã chốt.

- **Truy vấn lai.** Một `standalone` fan-out sang cả RAG lẫn SQL, rồi `generate` hợp nhất hai loại bằng chứng có độ tin khác nhau (số liệu chính xác vs. trích dẫn văn bản). Chưa có luật hợp nhất.
- **Verdict theo consumer.** Enum `co` / `khong` / `co_dieu_kien` / `khong_du_can_cu` / `mau_thuan` mang hình dạng RAG; nhánh SQL cần trạng thái riêng (truy vấn lỗi, không ánh xạ được schema, kết quả rỗng ≠ không đủ căn cứ). Nghiêng về verdict tách theo consumer.
- **Trần N fact mỗi neo** ở §11.2. Đặt theo cảm tính, phải đo.
- **Cơ chế boost trên Qdrant.** Xem §10.1 — chặn bậc thang xuống thang.
- **`asker.time.tenure`** là thuộc tính _dẫn xuất_ từ ngày vào làm. Chưa quyết định lưu giá trị đã tính hay tính lúc chiếu. Lưu giá trị thì nó cũ đi theo thời gian thật.

---

## 16. Quy ước đặt tên

Khoá trong card, trong manifest, và trong schema Python dùng **tiếng Anh**; prose và mô tả dùng tiếng Việt. Lý do: các khoá này trở thành payload key trong Qdrant và tên cột trong SQL, nơi identifier không dấu là bắt buộc trên thực tế.

`docs/process_query.md` hiện dùng khoá tiếng Việt trong ví dụ card §4.1. Bảng §14 ở trên là bảng ánh xạ chính thức giữa hai bên.
