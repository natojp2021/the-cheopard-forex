# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Dự án là gì

Bot giao dịch **Forex danh mục nhiều chân** cho tài khoản quỹ **FTMO $100.000**, chạy trên Windows + MetaTrader 5 (Pure Python API, KHÔNG dùng EA MQL5). Đây là dự án kế thừa từ một hệ XAUUSD trước đó (`quant-xau`) — rất nhiều docstring tham chiếu hệ cũ để giải thích "vì sao ở đây làm khác".

Hiện trạng: danh mục năm chân đang ở giai đoạn `FORWARD_TEST`, chưa có chân nào `LIVE`.

### MỤC TIÊU DUY NHẤT — mọi quyết định kỹ thuật phải phục vụ nó

**Pass kỳ thi FTMO rồi vận hành tài khoản Swing được cấp vốn, dưới đúng luật của FTMO.**
Không phải tối đa hoá Sharpe, không phải tìm cho nhiều chiến lược. Ba ràng buộc cứng
quyết định mọi thứ khác:

|            | Luật FTMO                                      | Mức hệ này tự đặt                           | Vì sao chặt hơn                                                                                   |
| ---------- | ---------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Max loss   | 10% ($90.000, neo balance ban đầu TĨNH)        | **9%** (`ftmo_leverage_policy.DD_SELF_CAP`) | backtest không có trượt giá, spread giãn, lệnh bị từ chối — MaxDD thật LUÔN sâu hơn MaxDD đo được |
| Daily loss | 5%, chốt theo CE(S)T, tính cả lãi/lỗ CHƯA đóng | ngày tệ nhất đã quan sát × biên             | —                                                                                                 |
| Đòn bẩy    | Swing forex 1:30 (ký quỹ)                      | **3,5x phơi nhiễm**                         | 3,51x cho MaxDD đúng 9,00%; 3,7x cho 9,35% tức VƯỢT sàn                                                |

Tài khoản **Swing** chứ không phải Standard: mọi chân đều giữ lệnh qua đêm và qua
cuối tuần (time-stop ngắn nhất 12 nến H4 = 2 ngày), mà Standard cấm đúng điều đó.

Hệ quả cho mọi lần sửa code: một thay đổi làm tăng lợi nhuận nhưng đẩy MaxDD lên
trên 9% là thay đổi BỊ TỪ CHỐI, không cần bàn thêm.

### Tìm chiến lược — chỉ chấp nhận cơ sở KHOA HỌC

Một ý tưởng chỉ được xem xét nếu trả lời được **vì sao nó đáng tồn tại TRƯỚC KHI
backtest**. Nguồn hợp lệ, theo thứ tự ưu tiên:

1. **Bài báo học thuật / luận văn** có phương pháp và số liệu — `D:\project-learning\documents\forex-strategies` (25 bài). Trích dẫn phải ghi TÁC GIẢ · TÊN BÀI · TẠP CHÍ/NĂM · ĐƯỜNG DẪN FILE. Không có bản gốc trong kho thì phải ghi rõ "trích GIÁN TIẾP qua <file>".
2. **Chẩn đoán đo được trước khi backtest** — ví dụ ngưỡng hoà vốn `c* = √(π/2a)·|φ|/(1−φ)` của Sepp & Lucic (2026): nó chọn công cụ mà KHÔNG tốn bậc tự do nào. Đây là thứ đã chấm dứt 57 vòng quét mù.
3. **Sách/mã nguồn tham khảo** (`D:\project-learning\project-refer`) — lấy NGUYÊN TẮC, viết lại theo SSOT repo này, ghi nguồn trong docstring.

**Bị từ chối thẳng**: ý tưởng chỉ có "backtest đẹp", tối ưu lưới tham số rồi lấy đỉnh,
chỉ báo ghép ngẫu nhiên, hay bất kỳ luật nào không nói được cơ chế kinh tế/vi cấu
trúc đứng sau. Tiền lệ: 4 luật hợp lưu lấy từ `freqtrade-strategies` cho **0/56 ô**
qua cổng và đã vào `REJECTED_DIRECTIONS`.

Sau khi có cơ sở, ý tưởng vẫn phải qua đủ 6 kiểm định + cổng PBO ở mục "Quy trình
thăng cấp". Có cơ sở khoa học là điều kiện CẦN, không phải điều kiện đủ.

### Code phải chuẩn và sạch

- **Một nguồn sự thật.** Trước khi thêm hằng số hay hàm, tìm chủ sở hữu ở mục "Bốn nguồn sự thật DUY NHẤT". Bản sao thứ hai là chỗ hai bên trôi khỏi nhau.
- **Hỏng thì NỔ, không im lặng.** Ba lỗi nặng nhất của dự án đều không có exception: `live_targets()` phát 3/27 chân · `lot_notional_usd` mặc định `usd_per_quote=1.0` làm notional EURJPY sai 150 lần · `bars_held` không ai tính nên time-stop không bao giờ kích hoạt. Đầu vào sai phải `raise`, không được trả một con số trông hợp lý.
- **Fail-closed ở tầng rủi ro.** Không tính được rủi ro thì risk = 0, không phải "mức sàn dương".
- **Không code chết.** Nhánh không ai gọi, module không import được, hằng số không ai đọc — xoá, đừng để lại.
- **Mỗi bất biến một test.** Test kiểm HÀNH VI (ghim dữ liệu tương lai, bật/tắt lớp chi phí rồi đòi kết quả đổi), không kiểm sự hiện diện của một dòng code.
- Docstring ghi **VÌ SAO** và **SỐ ĐO**, không ghi lại chữ ký hàm.

## Cách trả lời (BẮT BUỘC)

Trả lời **ngắn, khô, kiểu báo cáo backtest** — số liệu và kết luận, không diễn giải.

- Không chào hỏi, không nhắc lại yêu cầu, không giải thích code hiển nhiên, không thuật lại từng thao tác.
- Không liệt kê chi tiết kỹ thuật trừ khi được hỏi. Kết luận trước, bằng chứng sau, mỗi ý một dòng.
- Không tự đề xuất cải tiến ngoài phạm vi, không lặp lại kết luận đã nói.

Định dạng báo cáo khi xong việc (bỏ mục rỗng):

```text
Đã sửa
- file chính và thay đổi

Kiểm định
- test đã chạy và kết quả

Còn lại
- rủi ro chưa xử lý hoặc điểm chưa kiểm chứng
```

Không tuyên bố "đã hoàn hảo / production-ready" khi không có bằng chứng đo được.

### Báo cáo BACKTEST / RESEARCH — nói ngôn ngữ của TRADER, không phải của lập trình viên

Khi trình bày kết quả một vòng backtest hay một hướng nghiên cứu, báo cáo bằng **các
chỉ số một trader đọc là hiểu ngay**, không phải bằng chi tiết kỹ thuật của code:

| Nhóm            | Chỉ số bắt buộc có                                                     |
| --------------- | ---------------------------------------------------------------------- |
| Kết quả         | Số dư đầu → **số dư cuối**, lãi/lỗ ròng ($ và %)                       |
| Rủi ro          | **MaxDD** (% và $), DD ngày tệ nhất, số ngày chạm cảnh báo             |
| Chất lượng lệnh | **Tổng số lệnh**, số **thắng/thua**, **winrate**, **R:R**, Profit Factor |
| Phân bố         | Lệnh lãi lớn nhất / lỗ lớn nhất, lãi TB, lỗ TB, chuỗi thua dài nhất    |
| Thời gian       | Thời gian nắm giữ trung bình, số lệnh mỗi tháng                        |

Quy ước trình bày:

- **Bảng trước, chữ sau.** Một bảng số đọc trong ba giây hơn một đoạn văn.
- Luôn quy ra **tiền và phần trăm**, không chỉ bps hay σ. "MaxDD 4,00σ" không nói
  được điều gì cho người phải quyết định có nạp tiền hay không; "MaxDD 8,01% =
  −$8.010" thì có.
- **Đối chiếu thẳng với hạn mức FTMO** ở mỗi báo cáo có rủi ro: MaxDD so với sàn nội
  bộ 9% và luật 10%, DD ngày so với mốc 5%. Một con số rủi ro không kèm khoảng cách
  tới hạn mức là một con số chưa dùng được.
- Sharpe, PBO, DSR, p-value **vẫn ghi** — nhưng xuống dưới, ở mục kiểm định, không
  đứng đầu báo cáo.
- Chi tiết kỹ thuật (tên hàm, đường dẫn file, cấu trúc dữ liệu) chỉ nêu khi được hỏi
  hoặc khi cần để tái lập kết quả.

## Ngôn ngữ và quy ước viết code (BẮT BUỘC)

- **Định danh (biến, hàm, class, module) viết bằng tiếng Anh**, theo đúng convention Python: `snake_case` cho hàm/biến, `PascalCase` cho class, `UPPER_SNAKE` cho hằng số.
- **Comment và docstring LUÔN viết bằng tiếng Việt CÓ DẤU.** Không viết tiếng Việt không dấu, không viết comment tiếng Anh.
- Docstring của module ở repo này không phải chỗ mô tả API — nó là chỗ ghi **VÌ SAO** module tồn tại, số liệu đo được, và cái bẫy đã từng làm hỏng hệ thống. Giữ đúng phong cách đó khi thêm module mới.
- **Tên hàm test cũng là tiếng Anh** (`test_rulebook_matches_registry`), như mọi định danh khác. Quy ước cũ dùng tiếng Việt không dấu đã bị bỏ ngày 14/08/2026 — toàn bộ 83 test đã đổi.
- **KHÔNG dùng tiếng Việt không dấu ở bất cứ đâu**: không trong tên, không trong chuỗi, không trong comment, không trong thông điệp log. Tiếng Việt thì phải CÓ DẤU; còn lại là tiếng Anh.
- **Không đặt tên file kiểu `_v2`, `_new`, `_fixed`, `_final`, `_backup`.** Sửa file chuẩn, dùng Git cho lịch sử.

## Lệnh thường dùng

Toàn bộ lệnh chạy từ **gốc repo** (imports dạng `src.python.*` phụ thuộc cwd), dùng venv Python **3.11** (`MetaTrader5` không hỗ trợ Python mới hơn):

```powershell
# Tạo môi trường
py -3.11 -m venv .venv311
.\.venv311\Scripts\python.exe -m pip install -r requirements.txt

# Test — toàn bộ (82 test, ~2 phút vì có backtest 14 chân)
.\.venv311\Scripts\python.exe -m pytest -q

# Test một file / một test
.\.venv311\Scripts\python.exe -m pytest -q tests/test_rulebook.py --tb=short
.\.venv311\Scripts\python.exe -m pytest -q tests/test_no_lookahead.py::test_zscore_khong_dung_du_lieu_tuong_lai

# Chạy bot — CONSOLE-ONLY từ 19/08/2026 (bảng điều khiển Tk đã bị XOÁ)
.\.venv311\Scripts\python.exe -m src.python.live_server
#   hoặc nhấn đúp start_live_server.bat — cửa sổ console CHÍNH LÀ ứng dụng
#   dừng êm từ ngoài: tạo tệp data/live/STOP_REQUESTED (đừng dùng taskkill:
#   kill giữa lúc gửi lệnh là chỗ sinh ra vị thế không có SL)
#   `start_live_server.vbs` đã bị xoá — nó chạy `pythonw.exe`, vốn KHÔNG CÓ
#   console, nên với app console-only thì nó không hiện được gì cả

# Điều khiển bot từ MỘT cửa sổ KHÁC (thay các nút của bảng điều khiển cũ)
.\.venv311\Scripts\python.exe -m src.python.ops_ctl status
.\.venv311\Scripts\python.exe -m src.python.ops_ctl run|stop
.\.venv311\Scripts\python.exe -m src.python.ops_ctl positions
.\.venv311\Scripts\python.exe -m src.python.ops_ctl flatten --confirm   # KILL SWITCH

# In thẻ luật của mọi chiến lược
.\.venv311\Scripts\python.exe -m src.python.strategies.rulebook

# Script nghiên cứu (mỗi file tự chèn ROOT vào sys.path, ghi CSV vào reports/fx_research/)
.\.venv311\Scripts\python.exe research/fx/xs_z_validate.py

# Kiểm tra broker trước khi cấp vốn (cần MT5 đang mở, đã đăng nhập)
.\.venv311\Scripts\python.exe scripts/check_broker_swap.py
.\.venv311\Scripts\python.exe scripts/check_symbol_spec.py
```

`pytest.ini` chỉ thu thập `tests/`; `tests/manual/` bị loại khỏi thu thập tự động (script chạy tay đọc parquet thật). Không chạy full suite sau mỗi patch nhỏ — chạy test đích trước.

## Console vận hành (19/08/2026 — thay bảng điều khiển Tk)

Bảng điều khiển customtkinter 1.926 dòng đã bị XOÁ, không phải tắt mặc định. Ba lý do, và cả ba đều đo được:

- **RAM/CPU** — Tk + customtkinter + matplotlib + Pillow nạp vào CÙNG tiến trình với vòng lặp giao dịch, cho một cửa sổ không ai ngồi trước trên VPS.
- **Rủi ro** — ba sự cố vận hành đã ghi lại đều xuất phát từ tầng giao diện, không từ logic giao dịch: `pythonw` không có console nên traceback biến mất; `_Redirector` thay `sys.stdout` làm logger ghi sang chỗ khác; `root.after()` gọi từ luồng nền ném `RuntimeError` và giết luồng nền. Console-only không vá chúng — nó bỏ chỗ để chúng xảy ra.
- **Bảo trì** — một chế độ không ai dùng vẫn phải nạp, kiểm, và giữ phụ thuộc.

Phần LOGIC được cứu ra nguyên vẹn: `core/ops_view.py` (ma trận quyết định 27 chân, sức khoẻ hệ, thiên hướng danh mục) và `core/ops_theme.py` (bảng màu ngữ nghĩa, chép nguyên mã hex).

**Console kể SỰ KIỆN, không vẽ TRẠNG THÁI.** Đó là ranh giới quan trọng nhất của thiết kế này. Giao diện được phép hiển thị trạng thái vì nó VẼ LẠI cùng một vùng màn hình; terminal thì mỗi dòng in ra là một dòng cộng thêm vĩnh viễn. Bê nội dung các thẻ sang chữ sẽ cho ra thứ tệ hơn cả GUI.

    console   sự kiện · đổi trạng thái · cảnh báo · nhịp tim 45s   ← người, vài giây
    JSONL     mọi số đo, mọi trường, mọi lần                       ← máy, về sau
              logs/{system,market,strategy,trading,ai,risk,daily}/<ngày>.jsonl

**Chống spam: hai lớp, khác bản chất.** Bằng chứng gốc — nhật ký VPS 18/08/2026 có **590 dòng cổng spread trong 49 phút** (mỗi 5 giây một dòng, mỗi dòng 20 công cụ) đi qua trọn HAI lớp khử lặp đã có. Cả hai thất bại vì cùng một lý do: dấu vân tay dedup CÓ CHỨA những con số đổi mỗi tick.

- Lớp một: sửa từ gốc ở điểm ghi log (`engine._log_spread_gate` dedup theo *số công cụ*, không theo giá trị bps).
- Lớp hai: `ops_console._Squelch` so vân tay **sau khi xoá hết chữ số** — bắt được các đợt CHƯA biết, không phụ thuộc điểm ghi nào.

Nén **chỉ ở tầng hiển thị và chỉ SAU khi đã ghi sổ**. Đảo thứ tự là đánh mất chính những dòng cần cho việc truy vết về sau.

## Kiến trúc

### Phân tầng và ranh giới

```
src/python/
├── core/infra/      RÀNG BUỘC + hạ tầng: ftmo.py, target_mode.py, mt5_bridge.py, clock.py,
│                    state_store.py, symbol_spec.py, ftmo_risk_state.py, ftmo_reward.py
├── shared/          thư viện thuần, KHÔNG state nghiệp vụ: asset_profile, carry_costs,
│                    fx_data, indicators, paths, statistics
├── research/        THƯ VIỆN lab đã đóng gói (fx_cross_lab, fx_cross_pairs, fx_momentum…)
│                    + research/validation/ (reality_check, stress_testing, overfitting_stats…)
├── strategies/      registry.py, rulebook.py, portfolio.py + d1/ h1/ h4/ m30/ theo signal_tf
├── execution/       order_plan (ĐƯỜNG DUY NHẤT ra lệnh), entry_gate, portfolio_sizing,
│                    ftmo_leverage_policy, disaster_stop, portfolio_risk,
│                    rule_trace, decision_log
├── core/          engine.py, config.py, strategy_registry.py + tầng TRÌNH BÀY console:
│                  ops_console.py (dòng sự kiện + nhịp tim + báo cáo khởi động/tắt máy),
│                  ops_view.py (đọc trạng thái — cứu ra từ GUI cũ), ops_theme.py (màu)
├── core/execution/  entry_pipeline, order_state_machine, position_execution_service
├── ai/            news_guard.py — cổng tin MỘT TẦNG (thay ai_moe_engine 2 tầng của XAU)
└── utils/           logger, env_loader
research/fx/         SCRIPT nghiên cứu chạy tay (~55 file), mỗi file là một "vòng" thí nghiệm
```

**Hai thư mục tên `research` và chúng KHÁC NHAU** — đây là chỗ dễ nhầm nhất:

- `src/python/research/` = thư viện lab **đã được production import hợp lệ** (chiến lược gọi `from src.python.research import fx_cross_lab as LAB`).
- `research/` ở gốc repo = script thí nghiệm chạy tay. **Production tuyệt đối không được import từ đây** (cũng như từ `scratch/`). Mỗi script tự `sys.path.insert(0, ROOT)` rồi ghi kết quả ra `reports/fx_research/*.csv`.

Ranh giới khác (kế thừa từ `README` của hệ cũ, vẫn áp dụng):

- Chiến lược khai báo setup/entry/direction/invalidation — **không** tính cỡ lệnh, **không** gửi lệnh MT5, **không** quản lý phơi nhiễm danh mục.
- `shared/` không được import `core/`, `strategies/`, `research/`; dùng `shared/paths.py` cho mọi hằng số đường dẫn (module này cố ý không có side-effect để tránh circular import).

### Bốn nguồn sự thật DUY NHẤT (SSOT)

Trước khi thêm hằng số hay logic mới, tìm chủ sở hữu tương ứng — không tạo bản thứ hai:

| Câu hỏi                                                 | Chủ sở hữu                                            |
| ------------------------------------------------------- | ----------------------------------------------------- |
| Chiến lược nào tồn tại, ở giai đoạn nào, số liệu ra sao | `strategies/registry.py`                              |
| Luật FTMO (max loss 10%, daily loss 5%, múi giờ CE(S)T) | `core/infra/ftmo.py`, neo vào `docs/ftmo/ftmo.md`     |
| Quy đổi rủi ro → cỡ lệnh                                | `core/infra/target_mode.py` (uỷ quyền sang `ftmo.py`) |
| Đặc tả tài sản, chi phí theo cặp                        | `shared/asset_profile.py`, `shared/carry_costs.py`    |

`registry.py` còn giữ `REJECTED_DIRECTIONS` — danh sách các hướng nghiên cứu **đã bị bác bỏ bằng bằng chứng**, kèm lý do. Gọi `registry.is_rejected(name)` **trước khi** bắt đầu một hướng nghiên cứu mới; đừng xoá các mục ở đó.

### Luồng từ tín hiệu tới lệnh

```
fx_data.load_m1()  ─→  chiến lược (live_targets / live_decisions / combined)
        │                        │
        │                        ├─ rulebook.RULEBOOK        thẻ luật KHAI BÁO (7 mục)
        │                        └─ rule_trace.RuleTrace     bản ghi RUNTIME từng quyết định
        ↓
portfolio.live_targets()          MỤC TIÊU của cả 27 chân
        ↓                         (pair_weights · cross_decisions ·
        ↓                          rank_weights · single_decisions)
portfolio.target_weights()        gộp 27 chân → tỷ trọng RÒNG theo CÔNG CỤ,
        ↓                         hai chân ngược chiều TRIỆT TIÊU tại đây
execution/order_plan.build()      ĐƯỜNG DUY NHẤT ra lệnh — bảy bước cố định:
        │   1. portfolio_risk.snapshot()       đọc vị thế THẬT từ broker
        │   2. entry_gate.EntryGate.evaluate() cổng an toàn, FAIL-CLOSED
        │   3. ftmo_leverage_policy.decide()   đòn bẩy theo ĐỆM tới sàn
        │   4. portfolio.target_weights()      tỷ trọng ròng
        │   5. portfolio_sizing.weights_to_lots()  tỷ trọng → LOT
        │   6. so vị thế thật ↔ mục tiêu       → OPEN/CLOSE/REVERSE/…
        │   7. disaster_stop.compute_book()    CẦU CHÌ cho mọi vị thế
        ↓
execution/decision_log.record_many()      JSONL vào logs/decisions/, GHI CẢ HOLD/SKIP
```

`order_plan` **không gửi lệnh** — nó trả về một kế hoạch đọc được và test được;
việc gửi thuộc tầng bridge. Điểm nối khai báo dữ liệu trong `registry.PORTFOLIO`:
`["entry_points"]` (27 chân) / `["target_weights"]` / `["sizing"]` /
`["leverage_policy"]` / `["disaster_stop"]` / `["live_risk"]` / `["decision_log"]` —
sửa đường dẫn ở đó chứ đừng hardcode ở nơi gọi.

**Hai loại dừng lỗ, đừng lẫn.** Chiến lược KHÔNG có SL theo giá — đo lại 14/08 trên
đúng 22 chân đang chạy (`research/fx/sl_test.py`): mọi mức SL đều tệ hơn, 1×ATR mất
23% Sharpe **và làm MaxDD TỆ ĐI** (4,00σ → 5,03σ). Nhưng `disaster_stop` là chuyện
khác: cầu chì ≥ 8×ATR trên server broker, phòng khi tiến trình chết, giá đo được chỉ
−1,5% Sharpe.

**`rulebook.py` và `rule_trace.py` phải đọc cùng nhau**: thẻ luật trả lời "hệ thống được PHÉP làm gì", bản ghi runtime trả lời "hôm nay hệ thống đã làm gì". Lệch nhau nghĩa là code đã trôi khỏi luật. Mỗi module chiến lược phải export biến `RULEBOOK`, và `trace_signal_name` phải khớp `RuleTrace.signal_name` — `tests/test_rulebook.py` cưỡng chế điều này (kể cả yêu cầu mọi điều kiện vào lệnh phải có **ngưỡng số**, không chấp nhận mô tả định tính).

### Dữ liệu

Nến M1 dựng từ tick Dukascopy nằm **ngoài repo**: `D:/data-ticks-train/_m1/<SYMBOL>_m1.parquet` (`shared/fx_data.py:M1_DIR`). EURUSD từ 2015, 6 cặp còn lại từ 2020. Cột `spread` đã là **đơn vị giá** (không phải điểm broker), `n_tick` → `volume` là tick volume (khớp `tick_volume` của MT5, nên là parity thật). Rổ giao dịch: 7 cặp major + 20 cross tổng hợp dựng từ chúng (`src/python/research/fx_cross_pairs.CROSS_DEFS`) — **chi phí cross là ƯỚC LƯỢNG**, phải đo spread thật trước khi cấp vốn.

Chia mẫu chuẩn của dự án: FORM 2020→2024-01-01, OOS 2024-01-01→nay.

### Trạng thái code chưa hoàn chỉnh

`core/infra/mt5_bridge.py` port từ hệ XAUUSD và **nay import được** (các module thiếu đã bổ sung 14-15/08). Nó là đường THỦ CÔNG: nút FLATTEN ALL, đóng tay, đóng nửa, dời break-even trên GUI, và `risk_guard.halt_trading()`. Đường TỰ ĐỘNG là `execution/order_router.py` — hai đường tách biệt có chủ ý, đừng gộp. `src/python/live_server.py` ĐÃ tồn tại; nhấn `start_live_server.vbs` nay DỪNG bản cũ rồi nạp bản mới (trước đó nó chỉ đưa cửa sổ cũ lên trước, và người vận hành thấy mãi một build cũ).

## Nguyên tắc bất biến khi sửa code

### ⛔ TUÂN THỦ LUẬT QUẢN LÝ VỐN CỦA FTMO LÀ ĐIỀU QUAN TRỌNG NHẤT

Trên mọi thứ khác. Trên Sharpe, trên lợi nhuận, trên số lượng chiến lược, trên sự
gọn gàng của code. **Vi phạm một lần là mất tài khoản, và không có "gần đúng".**

**Thứ tự ưu tiên tuyệt đối** — mọi xung đột giải theo thứ tự này, không có ngoại lệ:

```
Account Survival > FTMO Compliance > Risk Control
    > Consistency > Long-term Reward > Profit Maximization
```

Đọc thứ tự này theo nghĩa đen: khi một thay đổi làm tăng lợi nhuận nhưng đụng tới
hạn mức, câu trả lời là KHÔNG — không cần cân nhắc, không cần đo thêm.

**Ba cái bẫy FTMO** ghi ngay đầu `core/infra/ftmo.py` vì sai một trong ba là mất tài khoản:

1. Ngày giao dịch chốt theo **CE(S)T**, KHÔNG phải UTC. Lệch một múi giờ là lỗ của
   ngày này bị tính sang ngày khác, và mốc 5% được reset sai thời điểm.
2. Daily loss tính **cả lãi/lỗ CHƯA đóng**. Một vị thế đang âm 4% đã ăn gần hết
   hạn mức ngày dù chưa chốt gì.
3. Max loss neo vào **balance ban đầu TĨNH** ($90.000), KHÔNG trôi theo đỉnh equity.
   Đây là bẫy ngược với trực giác: tài khoản lên $130.000 rồi rơi về $95.000 là
   drawdown 27% từ đỉnh nhưng VẪN HỢP LỆ; ngược lại chỉ cần chạm $89.999 một lần
   là hết, kể cả khi đó là đáy nhất thời trong phiên.

**Ràng buộc số, đã đo, không được nới nếu chưa đo lại:**

| Đại lượng         | Giá trị                    | Ở đâu                                                      | Đo được                          |
| ----------------- | -------------------------- | ---------------------------------------------------------- | -------------------------------- |
| Sàn nội bộ        | **9%** (chặt hơn luật 10%) | `ftmo_leverage_policy.DD_SELF_CAP`                         | 4,85x cho MaxDD 10,74% = VI PHẠM |
| Trần đòn bẩy      | **3,5x** phơi nhiễm        | `ftmo_leverage_policy.LEVERAGE_MAX` · `registry.PORTFOLIO` | 3,51x cho MaxDD đúng 9,00%       |
| Ngân sách cầu chì | 2,0%/vị thế                | `disaster_stop.PER_POSITION_BUDGET_PCT`                    | nhỏ hơn nhiều mốc ngày 5%        |
| Cảnh báo notional | 6,3x                       | `target_mode.NOTIONAL_GAP_WARN_X`                          | ngày tệ nhất danh mục 0,794%     |

Bốn con số này là **hàm của danh mục hiện tại**. Thêm hay bớt một chân là phải đo
lại — chúng phụ thuộc tương quan giữa các chân, không phải hằng số của tự nhiên.

**Bốn lớp chặn trước khi một lệnh chạm broker**, và không được bỏ lớp nào:

```
trading_control    công tắc thủ công, BỀN VỮNG trên đĩa, file hỏng → TẮT
entry_gate         hội tụ mọi cổng, FAIL-CLOSED (None = CHẶN, không phải "bỏ qua")
ftmo_leverage_policy   đòn bẩy theo ĐỆM còn lại tới sàn; đệm cạn → trả 0 → dừng hẳn
disaster_stop      cầu chì ≥ 8×ATR đi KÈM lệnh mở, không đặt sau
```

Thêm một cổng mới thì đặt vào `entry_gate`, đừng rải thêm `if` dọc pipeline — cổng
rải rác là cổng sẽ bị quên khi thêm đường vào lệnh thứ hai.

Khi đụng vào logic giao dịch / feature / backtest, phải tự kiểm: không look-ahead, không rò rỉ dữ liệu, nhân quả theo nến đã đóng, múi giờ đúng, chi phí đầy đủ, parity backtest/live. `tests/test_no_lookahead.py` kiểm HÀNH VI (ghim dữ liệu tương lai, đòi tín hiệu trước điểm cắt không đổi) chứ không kiểm sự hiện diện của `.shift(1)` — viết test mới theo đúng kiểu đó.

**Chi phí là nơi hệ này gần chết nhất.** Mọi số Sharpe trong repo đều là **sau đủ chi phí**: spread + commission + swap + biên broker 1,0%/năm. Bỏ sót một lớp làm đảo dấu kết luận (đo được: Sharpe +0,216 sau spread+commission nhưng **−0,456** sau swap). `tests/test_costs.py` kiểm "lớp chi phí có thực sự được cộng vào" bằng cách bật/tắt và đòi kết quả phải đổi.

Không được bỏ hay làm yếu đi: kiểm tra đầu vào, xử lý lỗi nghiêm trọng, kiểm tra rủi ro, kill switch, tính idempotent, lưu state, truy vết quyết định, audit log, nhân quả backtest, chi phí thực thi, test hồi quy. **Fail-closed, không fail-soft** ở tầng rủi ro: khi tầng FTMO hỏng thì risk = 0 (không vào lệnh), không trả về "mức sàn dương" — xem `target_mode.risk_fraction`.

### TradingView MCP — nguồn ĐỘC LẬP để đối chiếu

      140 +
      141 +Máy này có sẵn TradingView MCP server (`.mcp.json`, 84 tool `mcp__tradingview__*`) nối tới TradingView Deskto
          +p đang mở. Giá trị lớn nhất của nó là **độc lập với MT5**: nó bắt được lớp lỗi mà thêm bao nhiêu test nội bộ
          +cũng không thấy, vì cả backtest lẫn live đều đọc chung một nguồn dữ liệu có thể sai giống nhau.
      142 +
      143 +Dùng để:
      144 +
      145 +- **Đối chiếu dữ liệu.** `data_get_ohlcv` (luôn `summary=true` trừ khi cần từng nến) so với parquet trong `da
          +ta-ticks-train/` — bắt lệch múi giờ, nến thiếu, giá sai. Feed đã từng lệch UTC+1, và cả một lớp "artifact" ho
          +á ra chỉ là vào lệnh sớm một nến M5.
      146 +- **Kiểm chứng chéo tín hiệu.** `chart_set_symbol`/`chart_set_timeframe` + `data_get_study_values` để xem một
          + setup cụ thể trên biểu đồ thật — nhanh hơn nhiều so với dựng lại chỉ báo trong script.
      147 +- **Backtest độc lập bằng Pine.** Viết lại luật vào lệnh bằng Pine (`pine_new` → `pine_set_source` → `pine_sm
          +art_compile`) rồi đọc `data_get_strategy_results`/`data_get_trades`. Hai hiện thực độc lập cho cùng một kết q
          +uả là bằng chứng mạnh hơn nhiều so với một hiện thực chạy hai lần.
      148 +- **Xem lại một lệnh đã đóng.** `chart_scroll_to_date` tới đúng thời điểm vào/ra lệnh, `capture_screenshot` đ
          +ể lưu vào báo cáo.
      149 +
      150 +Giới hạn phải nhớ: **số liệu TradingView KHÔNG thay được cổng parity.** Broker khác, spread khác, không có ga
          +te cấp danh mục. Nó là nguồn ĐỐI CHIẾU và cảnh báo sai lệch — kết luận chính thức vẫn phải đến từ `signal_rep
          +lay`/SimBroker trên dữ liệu của chính broker. Khi hai bên lệch nhau, đó là tín hiệu phải điều tra, không phải
          + chỗ để chọn con số đẹp hơn.

## Quy trình thăng cấp một hướng nghiên cứu

Một ý tưởng chỉ được vào `registry.STRATEGIES` sau khi qua bộ kiểm định trong `docs/knowledge/research_process.md`, thực thi bằng `src/python/research/validation/`:

1. **Control ngẫu nhiên** — giữ nguyên số vị thế/tần suất nhưng chọn công cụ ngẫu nhiên; Sharpe thật phải vượt phân vị 95.
2. **Bootstrap khối** (khối 21 ngày, 2000 lần) — P(Sharpe < 0) phải dưới ~10%.
3. **Ổn định theo năm** — bao nhiêu năm dương trên 7 năm mẫu.
4. **Loại ngoại lai** — bỏ 5 tháng tốt nhất mà **vẫn giữ dấu**.
5. **Stress chi phí** ×2 ×5 ×10, và biên swap broker 0–3%/năm.
6. **Độc lập** — tương quan với mọi chân đang chạy (giá trị của chân mới nằm ở tính trực giao, không ở Sharpe).

PBO/DSR (`research/validation/overfitting_stats.py`) là cổng bắt buộc: PBO phải dưới 0,50. FORM/OOS đẹp **không** thay được kiểm định đuôi — `XsZscoreReversion_M30` bị loại dù OOS tốt hơn bản H4, lý do ghi trong `REJECTED_DIRECTIONS`.

## Tài liệu

Khi tài liệu mâu thuẫn với code: **tài liệu đúng, sửa code**.

- `docs/ftmo/` — **BỘ QUY TẮC CỐT LÕI VÀ QUAN TRỌNG NHẤT CỦA DỰ ÁN, BẮT BUỘC PHẢI TUÂN THỦ TUYỆT ĐỐI**:
  - [`ftmo.md`](file:///D:/the-cheopard-forex/docs/ftmo/ftmo.md): Luật gốc FTMO (Max loss 10%, Daily loss 5%, múi giờ CE(S)T, và thông số đòn bẩy FTMO Swing theo từng loại tài sản như Forex 1:30, XAUUSD 1:15). Đây là mỏ neo SSOT cho `core/infra/ftmo.py`.
  - [`ftmo-risk-and-reward.md`](file:///D:/the-cheopard-forex/docs/ftmo/ftmo-risk-and-reward.md): Q&A quản trị rủi ro chuyên sâu, cơ chế tính toán Drawdown, chu kỳ rút tiền (Payout Claim) và Anti-Martingale Risk State Machine.
  - [`ftmo-the-cheopard.md`](file:///D:/the-cheopard-forex/docs/ftmo/ftmo-the-cheopard.md): Đặc tả hệ thống The Cheopard AI, thứ tự ưu tiên sinh tồn tài khoản và hàm Fitness định lượng cho FTMO.
- `docs/knowledge/` — knowledge anchor (Aronson, AFML, Chan…), ưu tiên cao nhất khi thiết kế; bắt đầu ở `knowledge_index.md`
- `docs/forex/` — nhật ký kết quả theo vòng, `07_he_thong_ba_chan.md` là bản mô tả hệ thống mới nhất (lưu ý: hệ nay đã lên **năm** chân, xem `registry.PORTFOLIO`)

Chỉ cập nhật tài liệu khi đổi interface công khai, luật nghiệp vụ, ranh giới kiến trúc, cấu hình, hành vi giao dịch/rủi ro, hoặc giả định backtest. Ưu tiên sửa tài liệu chuẩn sẵn có hơn tạo file mới.

## Kho tham chiếu ngoài repo — `D:\project-learning`

Đây là nguồn tri thức **ưu tiên số 1** của dự án (`docs/knowledge/knowledge_index.md`), nằm ngoài repo và không được commit.

### `D:\project-learning\documents` — sách và paper

```
TradingBooks/        110 PDF/EPUB sách giao dịch   ·  TradingBooks-md/    122 bản .md
documents-md/        Successful Algorithmic Trading (bản .md)
forex-strategies/    25 paper học thuật FX, .md và .pdf nằm CẠNH nhau
pdfs/ · resize/      paper lẻ, có bản dịch `_vi*.md` cho một số file
_inventory.json · _scan.json · TradingBooks/_info.text   mục lục + rating, dùng để tra tên trước khi mở file
```

**Quy tắc đọc**: file `.md` là **bản export văn bản từ PDF gốc** — nhanh, đủ cho lý thuyết, công thức và lập luận. Nhưng export **mất hình ảnh, biểu đồ, bảng phức tạp và công thức đặt ảnh**. Khi nội dung cần đến những thứ đó (đồ thị equity, sơ đồ cấu trúc thị trường, bảng kết quả nhiều tầng, ký hiệu toán bị vỡ trong `.md`) thì **mở PDF gốc cùng tên** bằng tham số `pages` của công cụ Read, đúng khoảng trang cần — đừng đọc cả cuốn.

Trình tự tra cứu: `_info.text` / `_inventory.json` để tìm tên → đọc `.md` → chỉ mở `.pdf` khi thiếu hình/biểu đồ.

### `D:\project-learning\project-refer` — mã nguồn tham khảo

```
carver-systematic-trading    backtest       intelligent-trading-bot   trading-strategy-optimizer
freqtrade-strategies         tradingbot     tradingsystem             mt5_live_trading_bot
mt5-ai-xauusd-trader         xaubot-ai
```

Dùng để **học best practice**, không phải để copy: cách tổ chức backtest engine, mô hình chi phí, quản lý vị thế, cấu trúc chiến lược, sizing theo biến động, lớp bridge MT5, bố cục test.

Ràng buộc khi lấy ý tưởng từ đây:

- **Không import, không copy nguyên khối vào `src/`.** Đọc, hiểu nguyên tắc, viết lại theo kiến trúc và SSOT của repo này.
- Ghi rõ nguồn trong docstring khi mượn ý tưởng — quy ước sẵn có, ví dụ `shared/carry_costs.py` (hệ số 365/252 học từ `carver-systematic-trading`) và `research/fx/confluence_h1.py` (4 luật lấy từ `freqtrade-strategies`).
- **Một luật hay từ repo khác vẫn phải qua đủ 6 kiểm định + cổng PBO** trước khi vào `registry.STRATEGIES`. Tiền lệ: 4 luật hợp lưu của `freqtrade-strategies` cho **0/56 ô** qua cổng và đã bị đưa vào `REJECTED_DIRECTIONS`.
- Code MT5/XAUUSD ở đó viết cho bài toán khác (một tài sản, SL từng lệnh). Port thẳng hằng số sang FX là sai đơn vị — lý do `shared/asset_profile.py` tồn tại.

## Hệ tiền nhiệm — `C:\Users\ToanVD\Downloads\quant-xau\quant-xau`

Bot XAUUSD mà repo này kế thừa. **Cấu trúc kỹ thuật tương đương** — cùng `src/python/{core,shared,research,utils}`, cùng `core/infra/` (ftmo, mt5_bridge, clock, state_store, symbol_spec, target_mode), cùng phân tầng strategies theo khung `d1/ h1/ h4/ m30/`, cùng quy ước docstring "vì sao" và tên test theo ngày. Khi cần một chuẩn kỹ thuật đã chạy tiền thật (bố cục module, conftest/fixture, test ranh giới kiến trúc, order state machine, reconciliation, circuit breaker, decision attribution), **đọc bản ở đó trước khi tự nghĩ ra bản mới** — 320 file test và các module `core/execution/`, `core/intelligence/` là kho tham chiếu chính.

**Khác biệt — KHÔNG port thẳng ba nhóm này:**

|              | quant-xau (XAUUSD)                                   | repo này (FX danh mục)                                                                          |
| ------------ | ---------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Chiến lược   | price-action/ML một tài sản, SL từng lệnh            | 5 chân cắt ngang 7 major + 20 cross, không SL từng lệnh                                         |
| Sizing / lot | `lot = risk_usd / (SL_distance × point_value)`       | vol-targeting: `lot_i = equity × leverage × w_i / notional_i` (`execution/portfolio_sizing.py`) |
| Quản lý lệnh | position lifecycle, pyramid, trailing, exit pipeline | tái cân bằng tỷ trọng theo lịch, hai chân triệt tiêu nhau trước khi ra lệnh                     |

Hằng số của vàng (SPREAD_CAP 1,00 USD, ATR_MIN/MAX 1,50/10,00 USD, commission 0,07 $/oz) **vô nghĩa với FX** — ATR_H1 trung vị EURUSD nhỏ hơn `ATR_MIN` của vàng 1.000 lần. Mọi thứ phụ thuộc tài sản phải đi qua `shared/asset_profile.py`.

Cảnh báo: nhiều file trong repo này được port từ đó và **chưa gỡ hết phụ thuộc** (xem `core/infra/mt5_bridge.py` ở mục "Trạng thái code chưa hoàn chỉnh"). Khi port thêm, kéo theo đúng thứ cần và viết lại theo SSOT của repo này.

## Cấu hình môi trường

`.env` (mẫu ở `.env.example`, nạp bằng `utils/env_loader.load_env_file()`): thông tin MT5, SMTP, `KILL_SWITCH_DD_PCT`, và API key cho nghiên cứu macro/news (Gemini/Groq/OpenRouter, FRED/BLS/BEA, Finnhub/NewsAPI/Alpha Vantage). `APP_ENV=PROD` là công tắc duy nhất bật gửi email thật — mọi giá trị khác chỉ ghi log.
