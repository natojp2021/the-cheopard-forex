# CLAUDE.md

Hướng dẫn cho Claude Code (claude.ai/code) khi làm việc trong repo này.

## Dự án là gì

Bot giao dịch **Forex** cho tài khoản quỹ **FTMO $100.000**, chạy trên Windows +
MetaTrader 5 (Pure Python API, KHÔNG dùng EA MQL5).

Hiện trạng: **MỘT chiến lược duy nhất**, `AsiaSweepH1`, ở giai đoạn `FORWARD_TEST`.
Chưa có gì `LIVE`.

### MỤC TIÊU DUY NHẤT — mọi quyết định kỹ thuật phải phục vụ nó

**Pass kỳ thi FTMO rồi vận hành tài khoản Swing được cấp vốn, dưới đúng luật của FTMO.**
Không phải tối đa hoá Sharpe, không phải tìm cho nhiều chiến lược. Ba ràng buộc cứng
quyết định mọi thứ khác:

|            | Luật FTMO                                      | Mức hệ này tự đặt                                | Vì sao chặt hơn                                                                    |
| ---------- | ---------------------------------------------- | ------------------------------------------------ | ---------------------------------------------------------------------------------- |
| Max loss   | 10% ($90.000, neo balance ban đầu TĨNH)        | **9%** (`ftmo_leverage_policy.DD_SELF_CAP`)      | backtest không có trượt giá, spread giãn, lệnh bị từ chối — MaxDD thật LUÔN sâu hơn |
| Daily loss | 5%, chốt theo CE(S)T, tính cả lãi/lỗ CHƯA đóng | **4%** (`order_plan._DAILY_RISK_CAP_PCT`)        | để một ngày mọi SL cùng chạm vẫn còn 1 điểm % đệm cho trượt giá và gap             |
| Tập trung  | (không có luật)                                | **1,5%/đồng tiền** (`_CURRENCY_RISK_CAP_PCT`)    | ba cặp của rổ đều có chân USD; ba lệnh cùng chiều USD là MỘT cược gấp ba           |

Tài khoản **Swing** chứ không phải Standard. Chiến lược hiện tại đóng hết trong phiên
(20:00 UTC) nên không cần đặc quyền giữ qua đêm, nhưng loại tài khoản đã chọn là Swing.

Hệ quả cho mọi lần sửa code: một thay đổi làm tăng lợi nhuận nhưng đẩy MaxDD lên trên
9% là thay đổi BỊ TỪ CHỐI, không cần bàn thêm.

### Tìm chiến lược — chỉ chấp nhận cơ sở KHOA HỌC

Một ý tưởng chỉ được xem xét nếu trả lời được **vì sao nó đáng tồn tại TRƯỚC KHI
backtest**. Nguồn hợp lệ, theo thứ tự ưu tiên:

1. **Bài báo học thuật / luận văn** có phương pháp và số liệu — `D:\project-learning\documents\forex-strategies`. Trích dẫn phải ghi TÁC GIẢ · TÊN BÀI · TẠP CHÍ/NĂM · ĐƯỜNG DẪN FILE. Không có bản gốc trong kho thì phải ghi rõ "trích GIÁN TIẾP qua <file>".
2. **Chẩn đoán đo được trước khi backtest** — ví dụ: dựng mô hình NULL cho một tỷ lệ trước khi tin nó là edge. Đây là thứ đã cứu dự án khỏi tin vào "break rate 99,4%".
3. **Sách/mã nguồn tham khảo** (`D:\project-learning\project-refer`) — lấy NGUYÊN TẮC, viết lại theo SSOT repo này, ghi nguồn trong docstring.

**Bị từ chối thẳng**: ý tưởng chỉ có "backtest đẹp", tối ưu lưới tham số rồi lấy đỉnh,
chỉ báo ghép ngẫu nhiên, hay bất kỳ luật nào không nói được cơ chế kinh tế/vi cấu trúc
đứng sau.

Sau khi có cơ sở, ý tưởng vẫn phải qua đủ 6 kiểm định + cổng PBO ở mục "Quy trình
thăng cấp". Có cơ sở khoa học là điều kiện CẦN, không phải điều kiện đủ.

### Code phải chuẩn và sạch

- **Một nguồn sự thật.** Trước khi thêm hằng số hay hàm, tìm chủ sở hữu ở mục "Bốn nguồn sự thật DUY NHẤT". Bản sao thứ hai là chỗ hai bên trôi khỏi nhau.
- **Hỏng thì NỔ, không im lặng.** Đầu vào sai phải `raise`, không được trả một con số trông hợp lý. Hai lỗi nặng nhất đã gặp đều thuộc họ này: `usd_per_quote` mặc định 1,0 làm notional cặp quote JPY sai 150 lần; và `R × risk_pct / 100` chia hai lần làm MaxDD báo −0,09% thay vì −8,74%.
- **Fail-closed ở tầng rủi ro.** Không tính được rủi ro thì lot = 0, không phải "mức sàn dương".
- **Không code chết.** Nhánh không ai gọi, module không import được, hằng số không ai đọc — xoá, đừng để lại.
- **Mỗi bất biến một test.** Test kiểm HÀNH VI (ghim dữ liệu tương lai, bật/tắt lớp chi phí rồi đòi kết quả đổi), không kiểm sự hiện diện của một dòng code.
- **Docstring ghi VÌ SAO và SỐ ĐO**, không ghi lại chữ ký hàm. Và chỉ ghi về hệ ĐANG chạy — lịch sử của những thứ đã xoá thuộc về Git.

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

### Báo cáo BACKTEST / RESEARCH — nói ngôn ngữ của TRADER

| Nhóm            | Chỉ số bắt buộc có                                                       |
| --------------- | ------------------------------------------------------------------------ |
| Kết quả         | Số dư đầu → **số dư cuối**, lãi/lỗ ròng ($ và %)                         |
| Rủi ro          | **MaxDD** (% và $), DD ngày tệ nhất, số ngày chạm cảnh báo               |
| Chất lượng lệnh | **Tổng số lệnh**, số **thắng/thua**, **winrate**, **R:R**, Profit Factor |
| Phân bố         | Lệnh lãi lớn nhất / lỗ lớn nhất, lãi TB, lỗ TB, chuỗi thua dài nhất      |
| Thời gian       | Thời gian nắm giữ trung bình, số lệnh mỗi tuần                           |

Quy ước trình bày:

- **Bảng trước, chữ sau.** Một bảng số đọc trong ba giây hơn một đoạn văn.
- Luôn quy ra **tiền và phần trăm**. "MaxDD 4,00σ" không nói được gì cho người phải quyết định có nạp tiền hay không; "MaxDD 8,74% = −$8.740" thì có.
- **Đối chiếu thẳng với hạn mức FTMO** ở mỗi báo cáo có rủi ro: MaxDD so với sàn nội bộ 9% và luật 10%, DD ngày so với trần nội bộ 4% và mốc 5%.
- Sharpe, PBO, DSR, p-value **vẫn ghi** — nhưng xuống dưới, ở mục kiểm định.
- Chi tiết kỹ thuật chỉ nêu khi được hỏi hoặc khi cần để tái lập kết quả.

## Ngôn ngữ và quy ước viết code (BẮT BUỘC)

- **Định danh (biến, hàm, class, module) viết bằng tiếng Anh**, theo convention Python: `snake_case` cho hàm/biến, `PascalCase` cho class, `UPPER_SNAKE` cho hằng số.
- **Comment và docstring LUÔN viết bằng tiếng Việt CÓ DẤU.** Không viết tiếng Việt không dấu, không viết comment tiếng Anh.
- **Tên hàm test cũng là tiếng Anh** (`test_rulebook_matches_registry`).
- **KHÔNG dùng tiếng Việt không dấu ở bất cứ đâu**: không trong tên, không trong chuỗi, không trong comment, không trong thông điệp log.
- **Không đặt tên file kiểu `_v2`, `_new`, `_fixed`, `_final`, `_backup`.** Sửa file chuẩn, dùng Git cho lịch sử.

## Lệnh thường dùng

Toàn bộ lệnh chạy từ **gốc repo** (imports dạng `src.python.*` phụ thuộc cwd), dùng venv
Python **3.11** (`MetaTrader5` không hỗ trợ Python mới hơn):

```powershell
# Tạo môi trường
py -3.11 -m venv .venv311
.\.venv311\Scripts\python.exe -m pip install -r requirements.txt

# Test — toàn bộ (~340 test, ~10 phút vì có backtest trên M1 thật)
.\.venv311\Scripts\python.exe -m pytest -q

# Test một file / một test
.\.venv311\Scripts\python.exe -m pytest -q tests/test_asia_sweep.py --tb=short
.\.venv311\Scripts\python.exe -m pytest -q tests/test_asia_sweep.py::test_decision_does_not_change_when_future_bars_are_pinned

# Chạy bot — CONSOLE-ONLY (bảng điều khiển Tk đã bị XOÁ)
.\.venv311\Scripts\python.exe -m src.python.live_server
#   hoặc nhấn đúp start_live_server.bat — cửa sổ console CHÍNH LÀ ứng dụng
#   dừng êm từ ngoài: tạo tệp data/live/STOP_REQUESTED (đừng dùng taskkill:
#   kill giữa lúc gửi lệnh là chỗ sinh ra vị thế không có SL)

# Điều khiển bot từ MỘT cửa sổ KHÁC
.\.venv311\Scripts\python.exe -m src.python.ops_ctl status
.\.venv311\Scripts\python.exe -m src.python.ops_ctl run|stop
.\.venv311\Scripts\python.exe -m src.python.ops_ctl positions
.\.venv311\Scripts\python.exe -m src.python.ops_ctl flatten --confirm   # KILL SWITCH

# In thẻ luật + số đo + quyết định phiên hiện tại
.\.venv311\Scripts\python.exe -m src.python.strategies.h1.asia_sweep
.\.venv311\Scripts\python.exe -m src.python.strategies.rulebook
.\.venv311\Scripts\python.exe -m src.python.strategies.registry

# Script nghiên cứu (mỗi file tự chèn ROOT vào sys.path, ghi CSV vào reports/fx_research/)
.\.venv311\Scripts\python.exe research/fx/asia_sweep_lab.py        # hiện tượng + control
.\.venv311\Scripts\python.exe research/fx/asia_sweep_filters.py    # lưới bộ lọc
.\.venv311\Scripts\python.exe research/fx/asia_sweep_calibrate.py  # tần suất

# Kiểm tra broker trước khi cấp vốn (cần MT5 đang mở, đã đăng nhập)
.\.venv311\Scripts\python.exe scripts/check_broker_swap.py
.\.venv311\Scripts\python.exe scripts/check_symbol_spec.py
```

`pytest.ini` chỉ thu thập `tests/`; `tests/manual/` bị loại khỏi thu thập tự động.
Không chạy full suite sau mỗi patch nhỏ — chạy test đích trước.

## Console vận hành

Console-only, không có GUI. Ba lý do, và cả ba đo được: RAM/CPU (Tk + matplotlib nạp
vào CÙNG tiến trình với vòng lặp giao dịch, cho một cửa sổ không ai ngồi trước trên
VPS); rủi ro (ba sự cố vận hành đã ghi lại đều xuất phát từ tầng giao diện, không từ
logic giao dịch); bảo trì (một chế độ không ai dùng vẫn phải nạp, kiểm, giữ phụ thuộc).

**Console kể SỰ KIỆN, không vẽ TRẠNG THÁI.** Đó là ranh giới quan trọng nhất của thiết
kế này. Giao diện được phép hiển thị trạng thái vì nó VẼ LẠI cùng một vùng màn hình;
terminal thì mỗi dòng in ra là một dòng cộng thêm vĩnh viễn.

    console   sự kiện · đổi trạng thái · cảnh báo · nhịp tim 45s   ← người, vài giây
    JSONL     mọi số đo, mọi trường, mọi lần                       ← máy, về sau
              logs/{system,market,strategy,trading,ai,risk,daily}/<ngày>.jsonl

**Chống spam: hai lớp, khác bản chất.** Bằng chứng gốc — một nhật ký VPS có **590 dòng
cổng spread trong 49 phút** đi qua trọn hai lớp khử lặp đã có. Cả hai thất bại vì cùng
một lý do: dấu vân tay dedup CÓ CHỨA những con số đổi mỗi tick.

- Lớp một: sửa từ gốc ở điểm ghi log (dedup theo *số công cụ*, không theo giá trị bps).
- Lớp hai: `ops_console._Squelch` so vân tay **sau khi xoá hết chữ số** — bắt được các đợt CHƯA biết, không phụ thuộc điểm ghi nào.

Nén **chỉ ở tầng hiển thị và chỉ SAU khi đã ghi sổ**.

## Kiến trúc

### Phân tầng và ranh giới

```
src/python/
├── core/infra/      RÀNG BUỘC + hạ tầng: ftmo.py, target_mode.py, mt5_bridge.py, clock.py,
│                    state_store.py, symbol_spec.py, ftmo_risk_state.py, ftmo_reward.py
├── shared/          thư viện thuần, KHÔNG state nghiệp vụ: asset_profile, carry_costs,
│                    fx_data, indicators, paths, statistics, mt5_bars
├── research/validation/   CỔNG THĂNG CẤP: reality_check, stress_testing, overfitting_stats…
├── strategies/      registry.py (SSOT), rulebook.py, portfolio.py,
│                    asia_sweep_core.py (động cơ 7 lớp) + h1/asia_sweep.py (chiến lược)
├── execution/       order_plan (ĐƯỜNG DUY NHẤT ra lệnh), entry_gate, risk_sizing,
│                    ftmo_leverage_policy, disaster_stop, portfolio_risk,
│                    order_router, position_book, rule_trace, decision_log, exit_manager
├── core/            engine.py, config.py, strategy_registry.py + tầng TRÌNH BÀY console:
│                    ops_console.py, ops_view.py, ops_theme.py
├── core/intelligence/  fx_market_state (trạng thái thị trường đo từ giá), strategy_scoring
├── ai/              news_guard.py — cổng tin MỘT TẦNG (đang TẮT, chưa đo trên rổ này)
└── utils/           logger, env_loader
research/fx/         SCRIPT nghiên cứu chạy tay, mỗi file là một "vòng" thí nghiệm
```

**Hai thư mục tên `research` và chúng KHÁC NHAU** — đây là chỗ dễ nhầm nhất:

- `src/python/research/validation/` = **cổng thăng cấp**, production được import hợp lệ.
- `research/` ở gốc repo = script thí nghiệm chạy tay. **Production tuyệt đối không được import từ đây.** Mỗi script tự `sys.path.insert(0, ROOT)` rồi ghi kết quả ra `reports/fx_research/*.csv`.

Ranh giới khác:

- Chiến lược khai báo setup/entry/direction/invalidation/**SL/TP** — **không** tính cỡ lệnh, **không** gửi lệnh MT5, **không** quản lý phơi nhiễm danh mục.
- `shared/` không được import `core/`, `strategies/`, `research/`; dùng `shared/paths.py` cho mọi hằng số đường dẫn.

### Bốn nguồn sự thật DUY NHẤT (SSOT)

| Câu hỏi                                                 | Chủ sở hữu                                            |
| ------------------------------------------------------- | ----------------------------------------------------- |
| Chiến lược nào tồn tại, ở giai đoạn nào, số liệu ra sao | `strategies/registry.py`                              |
| Luật FTMO (max loss 10%, daily loss 5%, múi giờ CE(S)T) | `core/infra/ftmo.py`, neo vào `docs/ftmo/ftmo.md`     |
| Quy đổi rủi ro → cỡ lệnh                                | `execution/risk_sizing.py`                            |
| Đặc tả tài sản, chi phí theo cặp                        | `shared/asset_profile.py`, `shared/carry_costs.py`    |

`registry.py` còn giữ `REJECTED_DIRECTIONS` — danh sách các hướng nghiên cứu **đã bị
bác bỏ bằng bằng chứng**, kèm lý do. Gọi `registry.is_rejected(name)` **trước khi** bắt
đầu một hướng nghiên cứu mới; đừng xoá các mục ở đó.

### Luồng từ tín hiệu tới lệnh

```
fx_data.load_m1()  ─→  asia_sweep_core.detect_setup()   máy trạng thái 7 lớp
        │                        │
        │                        ├─ rulebook.RULEBOOK        thẻ luật KHAI BÁO (7 mục)
        │                        └─ rule_trace.RuleTrace     bản ghi RUNTIME
        ↓
portfolio.live_targets()          quyết định của 3 chân (một chân / công cụ)
        ↓
portfolio.stop_targets()          SL / TP / chiều — HỢP ĐỒNG với tầng thực thi
        ↓
execution/order_plan.build()      ĐƯỜNG DUY NHẤT ra lệnh — tám bước cố định:
        │   1. portfolio_risk.snapshot()       đọc vị thế THẬT từ broker
        │   2. entry_gate.EntryGate.evaluate() cổng an toàn, FAIL-CLOSED
        │   3. ftmo_leverage_policy.decide()   đòn bẩy theo ĐỆM tới sàn
        │   4. portfolio.target_weights()      tỷ trọng (CHỈ để báo cáo phơi nhiễm)
        │   5. risk_sizing.size_book()         SL + % equity → LOT
        │   6. trần rủi ro NGÀY và ĐỒNG TIỀN
        │   7. so vị thế thật ↔ mục tiêu       → OPEN/CLOSE/REVERSE/…
        │   8. disaster_stop.compute_book()    CẦU CHÌ dự phòng
        ↓
execution/order_router.route()    `sl` VÀ `tp` nằm trong CHÍNH `order_send`
        ↓
execution/decision_log.record_many()      JSONL vào logs/decisions/, GHI CẢ HOLD/SKIP
```

`order_plan` **không gửi lệnh** — nó trả về một kế hoạch đọc được và test được. Điểm nối
khai báo dữ liệu trong `registry.PORTFOLIO`: `["entry_points"]` / `["stop_targets"]` /
`["risk_sizing"]` / `["risk_pct_per_trade"]` / `["leverage_policy"]` /
`["disaster_stop"]` / `["live_risk"]` / `["decision_log"]` — sửa đường dẫn ở đó chứ
đừng hardcode ở nơi gọi.

**HAI loại dừng lỗ, đừng lẫn.**

```
SL chiến lược    cực trị nến quét ± đệm, 24-32 pip — luật GIAO DỊCH, quyết định cỡ lệnh
disaster_stop    >= 8xATR — CẦU CHÌ hạ tầng, chỉ nổ khi tiến trình chết
```

SL chiến lược LUÔN gần hơn cầu chì. Để cầu chì THAY nó là sai bậc: 8xATR trên EURUSD là
~80 pip, tức gần BA LẦN rủi ro dự kiến của một lệnh.

**`rulebook.py` và `rule_trace.py` phải đọc cùng nhau**: thẻ luật trả lời "hệ thống được
PHÉP làm gì", bản ghi runtime trả lời "hôm nay hệ thống đã làm gì". Lệch nhau nghĩa là
code đã trôi khỏi luật. `tests/test_rulebook.py` cưỡng chế điều này (kể cả yêu cầu mọi
điều kiện vào lệnh phải có **ngưỡng số**).

### Dữ liệu

Nến M1 dựng từ tick Dukascopy nằm **ngoài repo**:
`D:/data-ticks-train/_m1/<SYMBOL>_m1.parquet` (`shared/fx_data.py:M1_DIR`).

    EURUSD  2015-01 → 2026-07   (11,5 năm)
    GBPUSD  2020-01 → 2026-07   (6,5 năm)
    USDJPY  2020-01 → 2026-07   (6,5 năm)

Cột `spread` đã là **đơn vị giá** (không phải điểm broker); `n_tick` → `volume` là tick
volume (khớp `tick_volume` của MT5, nên là parity thật).

⚠️ **Bốn cặp Tier 2 (AUDUSD, USDCAD, USDCHF, NZDUSD) hiện KHÔNG có parquet.** Thêm cặp
vào rổ đòi dựng lại chúng từ tick trước.

Chia mẫu chuẩn của dự án: FORM → 2024-01-01, OOS 2024-01-01 → nay.

### Trạng thái code chưa hoàn chỉnh

- `core/infra/mt5_bridge.py` là đường THỦ CÔNG: FLATTEN ALL, đóng tay, đóng nửa, `risk_guard.halt_trading()`. Đường TỰ ĐỘNG là `execution/order_router.py` — hai đường tách biệt có chủ ý, đừng gộp.
- `execution/parity.py` được dựng cho một họ chiến lược khác và hiện ném `NotImplementedError` kèm lý do. Phần THOÁT đã có parity tuyệt đối (một SL, một TP trên server broker), nhưng đoạn `order_plan → order_router → broker` chưa có vòng replay nhiều nghìn nến.
- `ai/news_guard.py` có đủ hạ tầng nhưng đang **TẮT**: nó bị tắt sau một vòng đo trên một rổ cặp chéo KHÔNG chứa USD, và rổ hiện tại toàn cặp CÓ USD nên số đo đó không áp dụng được. Chưa đo lại.

## Nguyên tắc bất biến khi sửa code

### ⛔ TUÂN THỦ LUẬT QUẢN LÝ VỐN CỦA FTMO LÀ ĐIỀU QUAN TRỌNG NHẤT

Trên mọi thứ khác. Trên Sharpe, trên lợi nhuận, trên số lượng chiến lược, trên sự gọn
gàng của code. **Vi phạm một lần là mất tài khoản, và không có "gần đúng".**

**Thứ tự ưu tiên tuyệt đối** — mọi xung đột giải theo thứ tự này:

```
Account Survival > FTMO Compliance > Risk Control
    > Consistency > Long-term Reward > Profit Maximization
```

**Ba cái bẫy FTMO** ghi ngay đầu `core/infra/ftmo.py` vì sai một trong ba là mất tài khoản:

1. Ngày giao dịch chốt theo **CE(S)T**, KHÔNG phải UTC. Lệch một múi giờ là lỗ của ngày này bị tính sang ngày khác, và mốc 5% được reset sai thời điểm.
2. Daily loss tính **cả lãi/lỗ CHƯA đóng**. Một vị thế đang âm 4% đã ăn gần hết hạn mức ngày dù chưa chốt gì.
3. Max loss neo vào **balance ban đầu TĨNH** ($90.000), KHÔNG trôi theo đỉnh equity. Tài khoản lên $130.000 rồi rơi về $95.000 là drawdown 27% từ đỉnh nhưng VẪN HỢP LỆ; ngược lại chỉ cần chạm $89.999 một lần là hết.

**Ràng buộc số, đã đo, không được nới nếu chưa đo lại:**

| Đại lượng                | Giá trị                    | Ở đâu                                | Đo được                          |
| ------------------------ | -------------------------- | ------------------------------------ | -------------------------------- |
| Sàn nội bộ               | **9%** (chặt hơn luật 10%) | `ftmo_leverage_policy.DD_SELF_CAP`   | luật tự đặt, không phải số đo    |
| Rủi ro mỗi lệnh          | **0,60%** equity           | `asia_sweep.RISK_PCT_PER_TRADE`      | MaxDD −8,74%; 0,75% cho −11,13%  |
| Trần rủi ro NGÀY         | **4,0%** equity            | `order_plan._DAILY_RISK_CAP_PCT`     | ngày tệ nhất đo được −1,268%     |
| Trần theo ĐỒNG TIỀN      | **1,5%** equity            | `order_plan._CURRENCY_RISK_CAP_PCT`  | ba cặp đều có chân USD           |
| Trần cứng / vị thế       | **1,0%** equity            | `risk_sizing.MAX_RISK_PCT_PER_POSITION` | chốt bắt lỗi đơn vị           |
| Ngân sách cầu chì        | 2,0%/vị thế                | `disaster_stop.PER_POSITION_BUDGET_PCT` | **CẦN ĐO LẠI** — xem dưới     |

Bốn con số đầu là **hàm của chiến lược hiện tại**. Đổi luật vào lệnh, đổi khung, hay
thêm cặp là phải đo lại. `tests/test_portfolio_single_leg.py` cưỡng chế bất biến "MaxDD
ở mức rủi ro đang dùng phải dưới sàn nội bộ".

`registry.PORTFOLIO["can_do_lai"]` liệt kê các con số được hiệu chỉnh cho một mô hình
sizing KHÁC và chưa đo lại cho mô hình hiện tại.

**Các lớp chặn trước khi một lệnh chạm broker**, và không được bỏ lớp nào:

```
trading_control        công tắc thủ công, BỀN VỮNG trên đĩa, file hỏng → TẮT
entry_gate             hội tụ mọi cổng, FAIL-CLOSED (None = CHẶN, không phải "bỏ qua")
ftmo_leverage_policy   đòn bẩy theo ĐỆM còn lại tới sàn; đệm cạn → trả 0 → dừng hẳn
risk_sizing            không tính được rủi ro → lot 0, kèm LÝ DO
order_plan             trần rủi ro NGÀY (4%) và theo ĐỒNG TIỀN (1,5%)
order_router           `sl` và `tp` nằm TRONG chính `order_send`, không đặt sau
disaster_stop          cầu chì dự phòng, đi KÈM lệnh mở
```

Thêm một cổng mới thì đặt vào `entry_gate` (hoặc `order_plan` nếu nó cần biết cỡ lệnh),
đừng rải thêm `if` dọc pipeline — cổng rải rác là cổng sẽ bị quên.

Khi đụng vào logic giao dịch / feature / backtest, phải tự kiểm: **không look-ahead**,
không rò rỉ dữ liệu, nhân quả theo nến đã đóng, múi giờ đúng, chi phí đầy đủ, parity
backtest/live.

⚠️ **Look-ahead là lỗi ĐÃ XẢY RA trong chiến lược hiện tại.** Bản đầu của `_mss_confirm`
đọc close của nến SAU khi vào lệnh và cho winrate 73% với t = +14,6 — trông y hệt một
phát hiện. `tests/test_asia_sweep.py::test_decision_does_not_change_when_future_bars_are_pinned`
bắt đúng lớp lỗi đó: ghim dữ liệu tương lai, đòi mọi quyết định trước điểm cắt y nguyên.
Viết test mới theo đúng kiểu đó.

**Chi phí là nơi hệ này gần chết nhất.** Mọi số trong repo đều là **sau đủ chi phí**:
spread THẬT tại phút khớp + commission $7/lot khứ hồi. Bỏ sót một lớp đảo dấu kết luận.
`tests/test_asia_sweep.py` kiểm "lớp chi phí có thực sự được trừ" bằng cách đòi
`r_net < r_gross` ở mọi lệnh và đòi chi phí/R GIẢM khi SL rộng ra.

Không được bỏ hay làm yếu đi: kiểm tra đầu vào, xử lý lỗi nghiêm trọng, kiểm tra rủi ro,
kill switch, tính idempotent, lưu state, truy vết quyết định, audit log, nhân quả
backtest, chi phí thực thi, test hồi quy. **Fail-closed, không fail-soft** ở tầng rủi ro.

### TradingView MCP — nguồn ĐỘC LẬP để đối chiếu

Máy này có sẵn TradingView MCP server (`.mcp.json`, 84 tool `mcp__tradingview__*`) nối
tới TradingView Desktop đang mở. Giá trị lớn nhất của nó là **độc lập với MT5**: nó bắt
được lớp lỗi mà thêm bao nhiêu test nội bộ cũng không thấy, vì cả backtest lẫn live đều
đọc chung một nguồn dữ liệu có thể sai giống nhau.

Dùng để:

- **Đối chiếu dữ liệu.** `data_get_ohlcv` (luôn `summary=true` trừ khi cần từng nến) so với parquet trong `data-ticks-train/` — bắt lệch múi giờ, nến thiếu, giá sai.
- **Kiểm chứng chéo tín hiệu.** `chart_set_symbol`/`chart_set_timeframe` + `data_get_study_values` để xem một setup cụ thể trên biểu đồ thật.
- **Backtest độc lập bằng Pine.** Viết lại luật vào lệnh bằng Pine (`pine_new` → `pine_set_source` → `pine_smart_compile`) rồi đọc `data_get_strategy_results`/`data_get_trades`. Hai hiện thực độc lập cho cùng một kết quả là bằng chứng mạnh hơn nhiều so với một hiện thực chạy hai lần.
- **Xem lại một lệnh đã đóng.** `chart_scroll_to_date` tới đúng thời điểm vào/ra lệnh, `capture_screenshot` để lưu vào báo cáo.

Giới hạn phải nhớ: **số liệu TradingView KHÔNG thay được cổng parity.** Broker khác,
spread khác, không có gate cấp danh mục. Nó là nguồn ĐỐI CHIẾU và cảnh báo sai lệch —
kết luận chính thức vẫn phải đến từ SimBroker trên dữ liệu của chính broker. Khi hai bên
lệch nhau, đó là tín hiệu phải điều tra, không phải chỗ để chọn con số đẹp hơn.

## Quy trình thăng cấp một hướng nghiên cứu

Một ý tưởng chỉ được vào `registry.STRATEGIES` với `stage` cao hơn `FORWARD_TEST` sau
khi qua bộ kiểm định trong `docs/knowledge/research_process.md`, thực thi bằng
`src/python/research/validation/`:

1. **Control ngẫu nhiên** — giữ nguyên số vị thế/tần suất nhưng chọn công cụ hoặc thời điểm ngẫu nhiên; Sharpe thật phải vượt phân vị 95.
2. **Bootstrap khối** (khối 21 ngày, 2000 lần) — P(Sharpe < 0) phải dưới ~10%.
3. **Ổn định theo năm** — bao nhiêu năm dương trên toàn mẫu.
4. **Loại ngoại lai** — bỏ 5 tháng tốt nhất mà **vẫn giữ dấu**.
5. **Stress chi phí** ×2 ×5 ×10.
6. **Độc lập** — tương quan với mọi chân đang chạy.

PBO/DSR (`research/validation/overfitting_stats.py`) là cổng bắt buộc: PBO phải dưới
0,50. FORM/OOS đẹp **không** thay được kiểm định đuôi.

⚠️ **Chiến lược hiện tại CHƯA chạy vòng kiểm định nào.** Đó là việc phải làm trước khi
nâng `stage`.

## Tài liệu

Khi tài liệu mâu thuẫn với code: **tài liệu đúng, sửa code** — trừ khi tài liệu tự trích
sai nguồn của nó, và khi đó phải ghi lại phần trích sai bằng số đo (tiền lệ:
`docs/the-asia-sweep/00_KET_QUA_DO_LUONG.md` §5).

- `docs/ftmo/` — **BỘ QUY TẮC CỐT LÕI, BẮT BUỘC TUÂN THỦ TUYỆT ĐỐI**:
  - [`ftmo.md`](file:///D:/the-cheopard-forex/docs/ftmo/ftmo.md): Luật gốc FTMO (Max loss 10%, Daily loss 5%, múi giờ CE(S)T, đòn bẩy FTMO Swing theo loại tài sản — Forex 1:30, XAUUSD 1:15). Mỏ neo SSOT cho `core/infra/ftmo.py`.
  - [`ftmo-risk-and-reward.md`](file:///D:/the-cheopard-forex/docs/ftmo/ftmo-risk-and-reward.md): Q&A quản trị rủi ro, cơ chế tính Drawdown, chu kỳ rút tiền, Anti-Martingale Risk State Machine.
  - [`ftmo-the-cheopard.md`](file:///D:/the-cheopard-forex/docs/ftmo/ftmo-the-cheopard.md): thứ tự ưu tiên sinh tồn tài khoản và hàm Fitness định lượng cho FTMO.
- `docs/the-asia-sweep/` — chiến lược đang chạy:
  - `00_KET_QUA_DO_LUONG.md`: **số đo chính thức**, bảng đối chiếu học thuật, các hướng đã bác bỏ, việc còn phải làm.
  - `H1_INDUCEMENT_SWEEP_SPEC.md`, `AUTOMATED_STRATEGY_RULES.md`: đặc tả THAM KHẢO ban đầu. Nhiều ngưỡng trong đó đã được đo và cho kết quả NGƯỢC — đọc kèm `00_KET_QUA_DO_LUONG.md`.
  - `references/`: bản gốc các nguồn được trích.
- `docs/knowledge/` — knowledge anchor (Aronson, AFML, Chan…), ưu tiên cao nhất khi thiết kế; bắt đầu ở `knowledge_index.md`.

Chỉ cập nhật tài liệu khi đổi interface công khai, luật nghiệp vụ, ranh giới kiến trúc,
cấu hình, hành vi giao dịch/rủi ro, hoặc giả định backtest. Ưu tiên sửa tài liệu chuẩn
sẵn có hơn tạo file mới.

## Kho tham chiếu ngoài repo — `D:\project-learning`

Nguồn tri thức **ưu tiên số 1** của dự án (`docs/knowledge/knowledge_index.md`), nằm
ngoài repo và không được commit.

### `D:\project-learning\documents` — sách và paper

```
TradingBooks/        110 PDF/EPUB sách giao dịch   ·  TradingBooks-md/    122 bản .md
documents-md/        Successful Algorithmic Trading (bản .md)
forex-strategies/    25 paper học thuật FX, .md và .pdf nằm CẠNH nhau
pdfs/ · resize/      paper lẻ, có bản dịch `_vi*.md` cho một số file
_inventory.json · _scan.json · TradingBooks/_info.text   mục lục + rating
```

**Quy tắc đọc**: file `.md` là **bản export văn bản từ PDF gốc** — nhanh, đủ cho lý
thuyết, công thức và lập luận. Nhưng export **mất hình ảnh, biểu đồ, bảng phức tạp và
công thức đặt ảnh**. Khi nội dung cần đến những thứ đó thì **mở PDF gốc cùng tên** bằng
tham số `pages` của công cụ Read, đúng khoảng trang cần — đừng đọc cả cuốn.

Trình tự tra cứu: `_info.text` / `_inventory.json` để tìm tên → đọc `.md` → chỉ mở
`.pdf` khi thiếu hình/biểu đồ.

### `D:\project-learning\project-refer` — mã nguồn tham khảo

```
carver-systematic-trading    backtest       intelligent-trading-bot   trading-strategy-optimizer
freqtrade-strategies         tradingbot     tradingsystem             mt5_live_trading_bot
mt5-ai-xauusd-trader         xaubot-ai
```

Dùng để **học best practice**, không phải để copy: cách tổ chức backtest engine, mô hình
chi phí, quản lý vị thế, cấu trúc chiến lược, sizing theo biến động, lớp bridge MT5, bố
cục test.

Ràng buộc khi lấy ý tưởng từ đây:

- **Không import, không copy nguyên khối vào `src/`.** Đọc, hiểu nguyên tắc, viết lại theo kiến trúc và SSOT của repo này.
- Ghi rõ nguồn trong docstring khi mượn ý tưởng — quy ước sẵn có, ví dụ `shared/carry_costs.py` (hệ số 365/252 học từ `carver-systematic-trading`).
- **Một luật hay từ repo khác vẫn phải qua đủ 6 kiểm định + cổng PBO** trước khi nâng `stage`.
- Code viết cho MỘT tài sản thường có `point_value` là hằng số. Port thẳng hằng số sang FX là sai đơn vị — lý do `shared/asset_profile.py` tồn tại.

## Cấu hình môi trường

`.env` (mẫu ở `.env.example`, nạp bằng `utils/env_loader.load_env_file()`): thông tin
MT5, SMTP, `KILL_SWITCH_DD_PCT`, và API key cho nghiên cứu macro/news (Gemini/Groq/
OpenRouter, FRED/BLS/BEA, Finnhub/NewsAPI/Alpha Vantage). `APP_ENV=PROD` là công tắc duy
nhất bật gửi email thật — mọi giá trị khác chỉ ghi log.

Hai công tắc ảnh hưởng trực tiếp tới giao dịch:

```
FX_BARS_FROM_MT5=1   lấy nến từ MT5 thay vì parquet. BẮT BUỘC ở live.
NEWS_GUARD=1         bật cổng tin (mặc định TẮT — xem `ai/news_guard.py`)
```
