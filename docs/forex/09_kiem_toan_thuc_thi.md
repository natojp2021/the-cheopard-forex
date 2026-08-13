# Kiểm toán tầng thực thi — 14/08/2026

Đối chiếu `the-cheopard-forex` với `quant-xau` (17 module, 6.839 dòng ở
`core/execution/`) và `D:\project-learning\project-refer`.

Câu hỏi: **phần vào lệnh, quản lý cỡ lệnh, quản lý lệnh có thống nhất không, hay còn
vênh?**

Trả lời ngắn: **còn vênh, và đã tìm ra bảy chỗ.** Bốn chỗ đã bịt trong đợt này, ba
chỗ còn lại ghi ở cuối.

---

## 1. Vì sao phải nghi ngờ

Ba lỗ hổng tìm được trước đợt kiểm toán đều cùng một dạng:

| Lỗ hổng                                         | Triệu chứng                                       |
| ----------------------------------------------- | ------------------------------------------------- |
| `live_targets()` phát 3/27 chân                 | Không exception. Backtest 27 chân, live 3 chân.   |
| `asset_profile` thiếu 21 cross                  | `ValueError` — nhưng chỉ khi có người thật sự gọi |
| `lot_notional_usd` mặc định `usd_per_quote=1.0` | Notional EURJPY sai **150 lần**, vẫn ra số dương  |

Không cái nào có test đỏ. Giả định đúng phải là: **còn nữa**. Đợt này tìm thêm bốn.

---

## 2. Bảng đối chiếu module

| quant-xau                         | Bất biến nó giữ                         | Hệ Forex                                    | Trạng thái                                                             |
| --------------------------------- | --------------------------------------- | ------------------------------------------- | ---------------------------------------------------------------------- |
| `position_sizing.py`              | Một đường DUY NHẤT quy risk → lot       | `execution/portfolio_sizing.py`             | ✅ có, mô hình khác (vol-target)                                       |
| `portfolio_allocation.py`         | Ngân sách rủi ro cho từng lệnh          | —                                           | 🚫 cố ý không có: danh mục cấp theo tỷ trọng, không theo lệnh          |
| `portfolio_coordinator.py`        | Trọng tài xung đột, quyền sở hữu symbol | `portfolio.target_weights()`                | ✅ có, ở tầng DANH MỤC — hai chân ngược chiều triệt tiêu trước khi gửi |
| `portfolio_risk.py`               | Rủi ro mở thật + vị thế không rõ rủi ro | `execution/portfolio_risk.py`               | ✅ có, viết lại (không có SL nên đo bằng phơi nhiễm × đuôi)            |
| `entry_safety_gate.py`            | Hội tụ mọi cổng, fail-closed            | `execution/entry_gate.py`                   | ✅ có                                                                  |
| `reconciliation.py`               | Đối soát khởi động, chặn tới khi sạch   | `execution/position_book.reconcile()`       | ✅ **BỔ SUNG ĐỢT NÀY**                                                 |
| `trading_control.py`              | Công tắc thủ công, bền vững             | `execution/trading_control.py`              | ✅ **BỔ SUNG ĐỢT NÀY**                                                 |
| `position_lifecycle.py`           | Mọi nhánh đóng lệnh hội tụ một điểm     | `position_book.close()`                     | ✅ **BỔ SUNG ĐỢT NÀY**                                                 |
| (không có)                        | Đồng hồ time-stop bền vững              | `position_book.bars_held()`                 | ✅ **BỔ SUNG ĐỢT NÀY**                                                 |
| `order_state_machine.py`          | Idempotency, sự kiện bền vững           | `execution/order_router` (khoá idempotency) | ⚠️ rút gọn — xem §4                                                    |
| `position_execution_service.py`   | Gửi lệnh, vòng đời tới PROTECTED        | `execution/order_router.py`                 | ✅ viết lại theo mô hình danh mục                                      |
| `circuit_breaker.py`              | Ngắt mạch khi broker lỗi liên tiếp      | `core/execution/circuit_breaker.py`         | ⚠️ có file, CHƯA nối vào router                                        |
| `exit_pipeline.py`                | Tính R-multiple, ghi lý do đóng         | `decision_log`                              | ⚠️ một phần — không có R vì không có SL                                |
| `factor_exposure.py`              | Quy vị thế về nhân tố chung             | `portfolio.exposure_report()`               | ✅ có, theo ĐỒNG TIỀN thay vì nhân tố                                  |
| `signal_enhancement.py`           | Cổng ML vi cấu trúc                     | —                                           | 🚫 cố ý không có: hệ Forex không có mô hình ML                         |
| `mt5_bridge.py`                   | Lớp gọi MT5                             | `execution/order_router.py`                 | ❌ bridge cũ **KHÔNG import được**, xem §4                             |
| `ftmo_guard.py` / `risk_guard.py` | Chặn theo lỗ ngày/tổng                  | `core/infra/ftmo*.py`                       | ✅ có                                                                  |

---

## 3. Bốn lỗ hổng bịt trong đợt này

### 3.1 `bars_held` không có ai tính — NẶNG NHẤT

Cả 27 chân thoát bằng đúng hai cách: tín hiệu ngược chiều, và **time-stop**. Không
chân nào có dừng lỗ theo giá. Với phần lớn lệnh, time-stop là lối thoát **duy nhất**.

Time-stop cần `bars_held`. Trước đợt này:

```
live_decision(start, bars_held=0)   ← mọi nơi gọi đều truyền 0
(không module nào sinh ra giá trị này)
```

Hậu quả nếu chạy thật: điều kiện `bars_held >= timestop` **không bao giờ đúng** →
vị thế giữ vô hạn. Chân H4 time-stop 12 nến (2 ngày) sẽ nằm lại nhiều tuần.

Bịt bằng `execution/position_book.py`: sổ vị thế **bền vững trên đĩa**, đếm **NẾN**
chứ không đếm giờ (17:00 thứ Sáu → 09:00 thứ Hai là 64 giờ nhưng **0 nến**; quy đổi
bằng giờ sẽ đóng lệnh sớm hai ngày mỗi tuần).

### 3.2 `entry_gate` chờ hai giá trị không ai sinh ra

`reconciliation_done` và `trading_enabled` là tham số bắt buộc của cổng, nhưng không
module nào tính chúng — bên gọi phải tự bịa `True`. Một cổng mà đầu vào do người gọi
bịa thì không phải cổng.

Bịt bằng `position_book.reconcile()` (sinh `reconciliation_done`) và
`execution/trading_control.py` (sinh `trading_enabled`, bền vững trên đĩa, **file
hỏng → fail-CLOSED**).

### 3.3 Không có điểm chạm broker

`order_plan` dựng kế hoạch nhưng không gửi. `mt5_bridge` không import được.

Bịt bằng `execution/order_router.py` — điểm **duy nhất** gọi `order_send()`, bốn bất
biến có test khoá: không gửi khi cổng chặn · ĐẢO CHIỀU là **hai** lệnh · cầu chì đi
**kèm** lệnh mở · ghi nhật ký mọi lệnh kể cả bị từ chối.

### 3.4 Cổng tin khai phạm vi rộng hơn dữ liệu

Code khai 12 loại sự kiện; lịch chỉ có 5. Mười loại (RBA/BOC/RBNZ/SNB/BOJ/GDP/PPI/
RETAIL_SALES/PMI/UNEMPLOYMENT) **không có một dòng nào** → cổng không bao giờ nổ cho
AUD/NZD/CAD/CHF/JPY, mà đó chính là phần rổ giao dịch nặng nhất.

Bịt bằng cách **thu hẹp khai báo cho khớp dữ liệu**: `COVERED_CURRENCIES =
("USD","EUR","GBP")`, và `blocks_instrument()` trả `False` kèm lý do "ngoài phạm vi"
cho công cụ ngoài ba đồng đó — không chặn vì **KHÔNG BIẾT**, không phải vì đã kiểm.

---

## 4. Ba chỗ còn lại

| Việc                                | Mức nguy hiểm | Ghi chú                                                                                                                                                                                                                                                    |
| ----------------------------------- | ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `mt5_bridge.py` — giữ, sửa hay xoá  | thấp          | **Kết luận ĐẢO NGƯỢC 15/08/2026: GIỮ.** Kiểm lại thì nó IMPORT ĐƯỢC — các module thiếu đã bổ sung trong chính đợt này (`core/config.py`, `utils/exception_handler`, `symbol_spec.get_symbol_spec`). Và nó có NGƯỜI DÙNG THẬT: nút FLATTEN ALL, đóng tay, đóng nửa, dời break-even trên GUI, cùng `risk_guard.halt_trading()`. Xoá là gỡ mất thao tác thủ công của người vận hành. Ranh giới rõ: `order_router` là đường TỰ ĐỘNG (tái cân bằng danh mục), `mt5_bridge` là đường THỦ CÔNG (người bấm nút). |
| Circuit breaker chưa nối vào router | trung bình    | Chỉ thành vấn đề khi `dry_run=False`. Broker từ chối liên tiếp hiện chỉ ghi log, không tự ngắt.                                                                                                                                                            |
| `order_state_machine` per-trade     | thấp          | Router dùng khoá idempotency riêng, đủ cho mô hình tái cân bằng. OSM đầy đủ (sự kiện bền vững, replay) là việc của giai đoạn cấp vốn.                                                                                                                      |

---

## 5. Truy vết đường tiền — đơn vị ở từng bước

| Bước                            | Đơn vị vào                 | Đơn vị ra                 | SSOT                    | Hỏng thì                                  |
| ------------------------------- | -------------------------- | ------------------------- | ----------------------- | ----------------------------------------- |
| `live_decision()`               | nến                        | BUY/SELL/HOLD/FLAT        | module chân             | trả exception, ghi vào `single_decisions` |
| `target_weights()`              | quyết định + `leg_scale`   | tỷ trọng ròng, Σ\|w\| = 1 | `portfolio.LEG_WEIGHTS` | chân lỗi bị bỏ, không im lặng thành 0     |
| `ftmo_leverage_policy.decide()` | equity, σ ngày             | hệ số phơi nhiễm ≤ 3,7x   | `ftmo.py`               | trả 0 → cổng chặn                         |
| `weights_to_lots()`             | tỷ trọng + giá             | LOT                       | `asset_profile`         | cross thiếu tỷ giá → **ném lỗi** (đã sửa) |
| `order_plan.build()`            | lot mục tiêu + vị thế thật | OPEN/CLOSE/REVERSE        | —                       | cổng chặn → `allowed=False`               |
| `disaster_stop`                 | tỷ trọng, đòn bẩy          | giá SL                    | —                       | không đặt được → chặn mở lệnh             |
| `order_router.route()`          | kế hoạch                   | `order_send`              | —                       | dry-run mặc định                          |

Đơn vị khớp ở mọi bước. Chỗ từng vênh — notional cross — đã nổ thành `ValueError`
thay vì trả số sai.

---

## 6. Đối chiếu PIPELINE CHUẨN — 15/08/2026

Yêu cầu: _"coi nó là bản sao hoàn hảo của The Cheopard XAU nhưng áp dụng cho forex"_.

Đối chiếu từng chặng của pipeline chuẩn (tìm tín hiệu → quản lý rủi ro → vào lệnh →
quản lý lệnh → log → trailing stop):

| Chặng              | Hệ XAUUSD                                | Hệ Forex                        | Trạng thái                     |
| ------------------ | ---------------------------------------- | ------------------------------- | ------------------------------ |
| Tìm tín hiệu       | `live_strategies/*.evaluate_and_trade()` | 27 chân `live_decision()`       | ✅ tương đương                 |
| Cổng an toàn       | `entry_safety_gate`                      | `execution/entry_gate`          | ✅ port                        |
| Đối soát khởi động | `reconciliation` (5 bước)                | `position_book.reconcile()`     | ✅ port, rút gọn               |
| Công tắc thủ công  | `trading_control`                        | `execution/trading_control`     | ✅ port                        |
| Ngân sách rủi ro   | `portfolio_allocation`                   | `ftmo_leverage_policy`          | ✅ tương đương, mô hình khác   |
| Quy đổi cỡ lệnh    | `position_sizing` (risk$/SL)             | `portfolio_sizing` (vol-target) | ✅ tương đương, công thức khác |
| Trọng tài xung đột | `portfolio_coordinator`                  | `portfolio.target_weights()`    | ✅ ở tầng danh mục             |
| Gửi lệnh           | `position_execution_service`             | `execution/order_router`        | ✅ port                        |
| Ngắt mạch          | `circuit_breaker`                        | cùng module, đã nối vào router  | ✅ port                        |
| Vòng đời đóng lệnh | `position_lifecycle`                     | `exit_manager.record_close()`   | ✅ port                        |
| Ghi nhận khi đóng  | `exit_pipeline` (R-multiple…)            | `exit_manager` (MFE/MAE)        | ✅ port, đại lượng khác        |
| **Dừng lỗ 3×ATR**  | có                                       | **KHÔNG**                       | 🚫 đã ĐO, bác bỏ               |
| **Break-even +3R** | có                                       | **KHÔNG**                       | 🚫 đã ĐO, bác bỏ               |
| **Trailing ATR**   | **đã bỏ 23/07**                          | **KHÔNG**                       | 🚫 đã ĐO, bác bỏ               |

### Ba cơ chế quản lý lệnh — đo trên chính 22 chân, không suy luận

**Dừng lỗ** (`research/fx/sl_test.py`, mô phỏng MAE trên 100% lệnh thật):

| SL       | Sharpe | MaxDD(σ) | chân tệ đi |
| -------- | ------ | -------- | ---------- |
| không có | 3,634  | 4,00     | 0/22       |
| 1×ATR    | 2,786  | **5,03** | 20/22      |
| 3×ATR    | 3,521  | 3,87     | 5/22       |
| 8×ATR    | 3,579  | 4,01     | 1/22       |

**Trailing + break-even** (`research/fx/trailing_test.py`):

| Cơ chế         | Sharpe    | OOS   | MaxDD(σ) | chân tệ đi                     |
| -------------- | --------- | ----- | -------- | ------------------------------ |
| không có       | 3,327     | 2,822 | 4,25     | 0/22                           |
| trailing 1×ATR | **1,826** | 1,538 | **8,35** | 19/22                          |
| trailing 3×ATR | 3,193     | 2,725 | 4,06     | 5/22                           |
| trailing 8×ATR | 3,273     | 2,818 | 4,25     | 1/22                           |
| BE 0,5×ATR     | 3,172     | 2,619 | 4,40     | 13/22                          |
| BE 2×ATR       | 3,327     | 2,822 | 4,25     | 0/22 — KHÔNG BAO GIỜ kích hoạt |

Ba bảng cùng một hình dạng: **càng siết càng tệ, nới ra thì hội tụ về "không có gì"**.
Không có vùng nào có ích. Cơ chế kinh tế giống nhau ở cả ba: chiến lược hồi quy vào
lệnh KHI GIÁ ĐANG ĐI NGƯỢC, nên mọi thứ cắt sớm đều cắt đúng vào phần lợi nhuận.

Đáng chú ý nhất: cả dừng lỗ lẫn trailing đều **làm MaxDD TỆ ĐI** khi đặt gần
(4,00 → 5,03σ và 4,25 → 8,35σ). Chúng không mua được sự an toàn nào — chỉ tính tiền.

### Kết luận về "bản sao hoàn hảo"

Sao chép hệ cũ nghĩa là sao chép cả **quyết định loại bỏ** của nó, không phải mọi
nhánh code từng tồn tại. Chính XAU đã bỏ trailing ngày 23/07 sau khi đo — hệ Forex
đo lại trên dữ liệu của mình và ra cùng kết luận, mạnh hơn.

Cái ĐÃ thiếu và nay đã bổ sung là phần **ghi nhận khi đóng lệnh**
(`execution/exit_manager.py`): lý do đóng thuộc tập ĐÓNG, thời gian giữ, MFE/MAE.
Thiếu nó thì khi live lệch khỏi backtest chỉ thấy "equity thấp hơn dự kiến" mà không
lần ra được lệch ở đâu.
