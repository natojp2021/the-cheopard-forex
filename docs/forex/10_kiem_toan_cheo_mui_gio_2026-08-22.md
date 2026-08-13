# Kiểm toán chéo 22/08/2026 — nến LIVE đang ở GIỜ MÁY CHỦ, không phải UTC

Nguồn: Weekly Backtest Audit của hệ `quant-xau` (`docs/research/weekly-backtest-audit-2026-08-22.md`)
tìm ra một họ lỗi "lưới nến lệch giờ máy chủ"; rà sang hệ này thì thấy **cùng họ, cơ
chế khác, và ở đây nặng hơn** vì nó chạm trực tiếp vào cổng vào lệnh của một chân.

## Lỗi

`shared/mt5_bars.load_m1()` làm `pd.to_datetime(rates["time"], unit="s")` rồi trả luôn.
`rates["time"]` của MT5 mang **giờ MÁY CHỦ** — FTMO/MetaQuotes chạy giờ Đông Âu (UTC+3
mùa hè, UTC+2 mùa đông) — trong khi `fx_data._load_m1_parquet` trả **UTC**.

Docstring của `fx_data.load_m1` khai cả hai nhánh đều "index UTC naive", và docstring đầu
`mt5_bars` nói rõ điều phải giữ là "hai nguồn cho ra CÙNG một hình dạng dữ liệu — cùng tên
cột, cùng đơn vị, **cùng múi giờ**". Đúng vế thứ ba bị vi phạm.

Trên VPS (`FX_BARS_FROM_MT5=1`) nhánh MT5 là nhánh đang chạy, nên **live lệch backtest
2–3 giờ về trục thời gian**.

## Hậu quả, theo thứ tự nghiêm trọng

| # | Chỗ bị ảnh hưởng | Hậu quả |
| --- | --- | --- |
| 1 | `strategies/h1/cross_mean_reversion.py` — `EXECUTION_WINDOW_UTC = 10..16`, `FORBIDDEN_HOURS_UTC = 20..23`, đọc `ts.hour` của chỉ mục nến | Ở live cửa sổ khớp THẬT chạy **07–13 UTC** và giờ bị cấm THẬT là **17–20 UTC**. Chân này giao dịch đúng những giờ nghiên cứu đã loại, và bị cấm ở những giờ nó muốn vào. |
| 2 | `fx_data.build_bars("4h")` và `fx_data.daily_bars()` gộp theo `origin="start_day"` | **Biên nến H4/D1 lệch 2–3 giờ.** Bốn chân H4 (`cross_xs_reversion`, `zband_audcad/gbpaud/gbpnzd`) và ba chân D1 (`cross_momentum`, `currency_carry`, `currency_reversal`) nhìn một chuỗi nến khác chuỗi đã kiểm định. |
| 3 | `mt5_bars.freshness()` so `utcnow()` với nến cuối | Nến cuối mang giờ máy chủ nên LỚN HƠN `utcnow` 2–3 giờ ⟹ tuổi dữ liệu ra **ÂM** ⟹ cổng chặn dữ liệu ôi không thể kích hoạt cho tới khi dữ liệu đã cũ hơn 2–3 giờ. Đúng lớp bảo vệ mà `mt5_bars` được viết ra để dựng. |

KHÔNG bị ảnh hưởng: các chân M30/H1 họ z-band và `signal_families` (`hours_utc="mọi giờ"`,
cửa sổ z là rolling) — lệch nguyên giờ không đổi lưới 30 phút/1 giờ.

## Đã sửa

`shared/mt5_bars.py`:

- `dst_calendar_offset_hours()` — lịch giờ Đông Âu (EEST từ 01:00 UTC chủ nhật cuối tháng 3
  tới 01:00 UTC chủ nhật cuối tháng 10; còn lại EET). Offset **không phải hằng số**, nên mọi
  cách vá bằng một con số cứng sẽ đúng nửa năm và sai nửa năm còn lại.
- `server_offset_hours(mt5, symbol)` — **ĐO trước, LỊCH sau**: đo bằng `symbol_info_tick().time`
  (đúng cho MỌI broker, kể cả broker không chạy giờ Đông Âu); chỉ rơi về lịch khi tick không
  dùng được (cuối tuần, terminal chưa kết nối, symbol chưa vào Market Watch). Cache 30 phút
  mỗi symbol — có TTL chứ không vĩnh viễn, để một tiến trình chạy liên tục qua mốc chuyển giờ
  tự nhận ra.
- `load_m1()` trừ offset trước khi dựng chỉ mục.
- `reset_offset_cache()` cho backtest/test.

Test: `tests/test_mt5_bars_utc_20260822.py` (12 test) khoá bốn bất biến — lịch DST ở sáu mốc
biên, đo-thắng-lịch, hai đường dự phòng, chỉ mục `load_m1` là UTC, `freshness()` không còn
âm, và biên H4 dựng từ nến MT5 nằm trên lưới UTC.

Bộ test: 287 passed. Bốn test còn đỏ (`test_costs.py` ×3, `test_rulebook.py` ×1) và 16 error
(`test_portfolio.py`, `test_rule_logging.py`) đều là `FileNotFoundError` do máy này chỉ có
parquet EURUSD/GBPUSD/USDJPY, thiếu AUDCAD/GBPAUD/NZDCAD/EURCHF/GBPNZD — **có sẵn từ trước,
không liên quan**.

## Đã sửa tiếp — hai việc từng để "cần người quyết" (22/08/2026, cùng ngày)

### 1. Cổng dữ liệu ôi: từ CODE CHẾT thành cổng thật

`mt5_bars.freshness()` có từ 15/08 và hai docstring trong `fx_data.py` khai rằng cổng chặn
dữ liệu ôi nằm ở `engine._build_plan`. Rà lại: `grep -rn "freshness("` toàn repo chỉ thấy
đúng định nghĩa hàm và hai dòng docstring đó — **lớp bảo vệ được mô tả chưa bao giờ tồn
tại**. Đúng họ lỗi tệ nhất: một cổng an toàn chỉ có trên giấy, mà người đọc tài liệu lại
tin là có.

Trở ngại khi nối: `freshness()` nhận một DataFrame, còn `_build_plan` không giữ DataFrame
nào — nến được nạp sâu trong `portfolio.live_targets()` cho 27 chân. Gọi lại `load_m1` cho
27 công cụ chỉ để đo tuổi là 27 × 200.000 nến, tức trả giá bằng cả chu kỳ.

Cách làm: **ghi sổ ngay tại chỗ nến vừa được nạp**, `_build_plan` chỉ đọc sổ.

| Thành phần | Việc |
| --- | --- |
| `mt5_bars.note_bars(symbol, df)` | ghi nhãn nến mới nhất — không thêm lần đọc nào |
| `mt5_bars.staleness()` / `stale_symbols()` | tuổi (giờ) theo từng công cụ / danh sách vượt ngưỡng |
| `mt5_bars.STALE_MAX_AGE_H = 2.0` | ngưỡng chặn |
| `fx_data.load_m1()` | gọi `note_bars()` cho **CẢ HAI** nhánh |
| `order_plan.build(..., extra_blocks=None)` | đường truyền lý do chặn từ bên gọi vào `EntryGate` |
| `engine._build_plan()` | đo → dựng `extra_blocks` → truyền xuống `OP.build` |

**Vì sao ngưỡng 2 giờ.** Bình thường nến M1 về mỗi phút; ngay cả cross mỏng (AUDCAD,
NZDCAD) cũng không đứng 2 giờ không tick trong giờ giao dịch, nên ngưỡng chặt hơn sẽ chặn
oan. Sự cố mà cổng này sinh ra để bắt được đo ở mức **28 NGÀY** (15/08, parquet cũ trên
VPS) — 2 giờ bắt được nó với biên **300 lần**. Thị trường đóng cửa thì tuổi vượt ngưỡng và
cổng chặn entry: đúng hành vi muốn có, và vô hại vì lúc đó không có gì để vào.

**Vì sao nhánh parquet cũng phải vào sổ.** Đó mới là nhánh nguy hiểm nhất: nó trả một
DataFrame **hoàn toàn hợp lệ** của tháng trước, không exception nào. Chỉ ghi sổ ở nhánh MT5
thì đúng tình huống thảm hoạ lại vô hình.

**Vì sao đi qua `extra_blocks` chứ không `return` sớm.** Cổng chặn làm `plan.allowed=False`,
và `order_router.route()` vẫn cho lệnh **GIẢM** phơi nhiễm đi qua — time-stop và lệnh đóng
vẫn tới được broker. Một `return` sớm ở `_build_plan` sẽ lặp lại đúng lỗi đã sửa ngày
15/08/2026 ("bấm STOP là khoá luôn đường thoát"). Test khoá lại bất biến này bằng cách đọc
mã nguồn của `_build_plan` và bắt lỗi nếu có `return` giữa cổng và router.

Không đo được tuổi dữ liệu thì **fail-closed** — chặn, không coi là "dữ liệu tươi".

### 2. `origin="start_day"` — mìn CHỜ NÂNG PHIÊN BẢN, không phải "no-op vô hại"

Bản đầu của tài liệu này nói pandas bỏ qua `origin` với freq `"1D"`. Đo lại trên cả hai
venv thì phát biểu đó **chỉ đúng một nửa**, và nửa còn lại mới là chỗ nguy hiểm:

| venv | pandas | `origin` với freq `"1D"` |
| --- | --- | --- |
| `the-cheopard-forex` (dự án này) | 2.3.3 | **CÓ** tác dụng |
| `quant-xau` (hệ anh em) | 3.0.3 | **BỊ BỎ QUA** + `RuntimeWarning` |

Nghĩa là code dựa vào `origin` để đổi lưới nến D1 **chạy đúng hôm nay và âm thầm đổi hành
vi ngay khi nâng pandas** — mà hệ anh em đã ở phiên bản đó rồi. Thêm nữa `"start_day"`
vốn LÀ giá trị mặc định, nên ba chỗ đang truyền nó không điều khiển gì; chúng chỉ *trông
như* một cần điều khiển.

Đã bỏ `origin=` khỏi nhánh `"1D"` ở `fx_data.build_bars`, `fx_data.daily_bars`,
`research/fx_cross_section.py`, `research/fx_momentum.py` (hành vi **không đổi** vì bằng
mặc định) và ghi rõ tại chỗ: lưới D1 là **nửa đêm UTC**, cố ý, và giờ cả hai nguồn đều là
UTC nên hai bên khớp. Muốn đổi lưới thì phải **dịch chỉ mục** trước khi gộp rồi dịch nhãn
trả lại — cách đó đúng ở mọi phiên bản pandas.

### Kiểm định

- `tests/test_mt5_bars_utc_20260822.py` — 12 test (múi giờ)
- `tests/test_stale_data_gate_20260822.py` — 14 test (cổng dữ liệu ôi + lưới D1)
- Toàn bộ: xem mục Kiểm định ở trên; bốn test đỏ + 16 error còn lại đều là
  `FileNotFoundError` do thiếu parquet AUDCAD/GBPAUD/NZDCAD/EURCHF/GBPNZD trên máy này —
  **có sẵn từ trước, không liên quan**.
