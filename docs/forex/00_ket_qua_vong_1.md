# The Cheopard Forex — Vòng nghiên cứu 1: thư viện chiến lược XAUUSD KHÔNG chuyển được sang Forex

> Ngày: 13/08/2026 · Dữ liệu: `D:\data-ticks-train\_m1` (M1 dựng từ tick Dukascopy, spread thật + tick volume)
> Mã: `src/python/shared/asset_profile.py` · `src/python/research/fx_lab.py` · `src/python/research/fx_entry_power.py`
> Số liệu: `reports/fx_recon/` · `reports/fx_research/`

## Kết luận một dòng

Toàn bộ 8 strategy family của The Cheopard (bản XAUUSD) chạy trên EURUSD/GBPUSD/USDJPY
tại M30/H1/H4 **không chứa edge phát hiện được** — và điều đó được chứng minh ở tầng
TÍN HIỆU, độc lập với mọi cách thoát lệnh. Không phải "cần chỉnh tham số". Cần giả
thuyết khác.

---

## 1. Trước hết: đơn vị của vàng vô nghĩa với Forex

Đo trên H1, cửa sổ chung 2020+ (`reports/fx_recon/pair_profile.csv`):

| cặp    | ATR H1 (pip) | ATR H1 (% giá) | spread (pip) | **spread / ATR** |
| ------ | ------------ | -------------- | ------------ | ---------------- |
| EURUSD | 12,96        | 0,115%         | 0,31         | **2,44%**        |
| USDJPY | 18,34        | 0,131%         | 0,52         | **2,73%**        |
| GBPUSD | 17,25        | 0,132%         | 0,86         | **5,00%**        |
| _XAUUSD (tham chiếu)_ | _53,70_ | _0,259%_ | _3,85_ | _7,26%_ |
| AUDUSD | 11,95        | 0,174%         | 1,02         | 8,65%            |
| USDCHF | 11,08        | 0,125%         | 0,94         | 8,69%            |
| USDCAD | 14,08        | 0,106%         | 1,22         | 8,84%            |
| NZDUSD | 11,19        | 0,176%         | 1,10         | 10,11%           |

Hai hệ quả bắt buộc:

1. **`ATR_MIN = 1.50 / ATR_MAX = 10.00` (USD/oz) trong `research/backtest.py` lọc sạch
   100% tín hiệu FX** — ATR H1 của EURUSD là 0,0013 đơn vị giá, nhỏ hơn sàn đó ~1.000
   lần. Port thẳng không cho ra "kết quả xấu", nó cho ra "không có cơ hội nào", trông
   giống hệt một hệ thống hỏng. Đã thay bằng `shared/asset_profile.py`.
2. **Thứ hạng Tier 1 của người dùng khớp chính xác thứ hạng rào chi phí đo được.**
   Bốn cặp Tier 2 có rào chi phí gấp **3,5-4 lần** EURUSD. Đó là lý do định lượng để
   chưa mở rộng danh mục — không phải một sở thích.

### Commission: khoản bị bỏ sót lớn hơn cả spread

Dữ liệu Dukascopy là spread ECN **thô**. Broker raw-spread thu ~$7/lot khứ hồi. Với
EURUSD đó là **0,70 pip — lớn hơn chính spread trung vị 0,31 pip**. Và quy đổi khác
nhau theo họ cặp:

```
XXXUSD:  7 / 100.000                = 0,70 pip  (EURUSD, GBPUSD…)
USDXXX:  7 × price / 100.000        = USDJPY@150 -> 1,05 pip
                                      USDCAD@1,35 -> 0,95 pip
                                      USDCHF@0,90 -> 0,63 pip
```

Cùng một mức phí USD cho ra chi phí pip **khác nhau tuỳ cặp và tuỳ tỷ giá**. Đây đúng
là loại giả định mà "port thẳng" bỏ sót. Đã đưa vào `AssetProfile.commission_price_units()`.

### Giờ 21:00 GMT là bẫy, không phải cơ hội

Spread giãn 3-5 lần trên **mọi** cặp (USDCHF: spread bằng **68%** biên độ giờ đó).
`fx_lab` chặn thẳng giờ này ở tầng entry. `pa_framework/features.py` hiện định nghĩa
`is_ny = 13-21h`, tức **đang bao gồm cả giờ độc này** — cần sửa khi thiết kế session
model riêng cho FX.

---

## 2. Sweep #1 — mô phỏng đầy đủ: 32/33 biến thể bị loại

`reports/fx_research/sweep01_tier1_baseline.csv` — 3 cặp × {M30,H1,H4} × 8 family,
hồ sơ thoát cơ sở (BE@1R + hard TP 2,0-2,5R), chi phí đúng đơn vị từng cặp,
DEV 2020-2024 / OOS 2024+.

- **PASS: 1/33** (USDJPY H1 `AvwapVpConfluence`, OOS +0,290R, PF 1,62, n=201).
  Nhưng DEV của chính nó là **−0,048R** — đảo dấu giữa hai cửa sổ. Với 33 phép thử,
  một PASS là **đúng bằng kỳ vọng ngẫu nhiên**. Không tin.
- Win rate hầu hết **13-30%** trong khi TP đặt ở 2,0-2,5R.
- Chi phí chỉ 0,016-0,12 R/lệnh → **chi phí KHÔNG phải thủ phạm chính**.

Điểm đáng ngờ: các trường phái **ngược nhau** (breakout, mean-reversion, momentum,
liquidity sweep) cùng âm ở mức gần giống nhau (PF 0,5-0,9). Khi mọi thứ hỏng như
nhau, nghi can là phần **dùng chung** — tức hồ sơ thoát — chứ không phải từng luật.

Không thể phân biệt hai giả thuyết bằng cách chạy thêm backtest:

```
H1: tín hiệu vô dụng           -> bỏ family
H2: tín hiệu có tin, exit sai  -> sửa exit, GIỮ family
```

Chạy lại backtest với exit khác chính là *"nghiên cứu dưới ảnh hưởng của backtest"*
mà `docs/knowledge/research_process.md` §1 cấm (AFML ch.11 tr.153).

---

## 3. Chẩn đoán quyết định — đo TÍN HIỆU, bỏ hẳn exit

`src/python/research/fx_entry_power.py`. Không SL/TP/BE. Chỉ đo đường giá sau tín hiệu:

```
fwd(h) = side × (close[t+h] − close[t]) / ATR[t]        h = 1…48 nến
```

đối chiếu với **control khớp hai chiều**: cùng phân phối giờ GMT, cùng tỷ lệ long/short,
thời điểm ngẫu nhiên, 200 lần rút. Control trả lời: *"một điểm vào MÙ, cùng giờ, cùng
tỷ lệ chiều, được bao nhiêu?"* — phần vượt lên trên đó mới là edge của luật.

### Kết quả: 28/33 = NO_INFORMATION

| kết luận | số biến thể |
| -------- | ----------- |
| NO_INFORMATION | **28** |
| HAS_INFORMATION | 5 (xem bên dưới) |

**33 biến thể × 11 horizon = 363 phép thử.** Ở ngưỡng p < 0,05, riêng ngẫu nhiên đã
sinh ra ~18 "phát hiện". Ta thu được 5 — **ít hơn cả mức ngẫu nhiên**. Năm cái đó
không phải phát hiện, chúng là nhiễu:

| biến thể | vấn đề |
| -------- | ------ |
| EURUSD H4 `MomentumRegime` | n=63 — mẫu quá nhỏ |
| USDJPY M30 `WaveRiderNY` | chỉ h=36, tắt ở h=4 và h=48 |
| USDJPY H1 `DonchianBreakout` | chỉ h=48, và **dấu ÂM** |
| USDJPY H1 `MomentumRegime` | chỉ h=1-2, đảo dấu mạnh ở h=24 (t=−1,53) |
| USDJPY H4 `DonchianBreakout` | chỉ h=3, đảo dấu ở h=24 (t=−2,26) |

### Bằng chứng độc lập thứ hai: MFE/MAE đối xứng

Mọi biến thể, không trừ cái nào:

```
MFE ≈ 3,3 – 4,5 ATR      |MAE| ≈ 3,3 – 4,7 ATR      tỷ lệ ≈ 1,00
```

Đó là **chữ ký của bước đi ngẫu nhiên**. Một tín hiệu có thông tin phải tạo ra biên
độ thuận lớn hơn biên độ nghịch. Không family nào làm được, trên bất kỳ cặp nào.
Kết luận này đến từ một phép đo hoàn toàn khác với t-test ở trên, và nói cùng một điều.

### Một quan sát KHÔNG phải nhiễu (đáng theo dõi)

`PullbackTrend` trên H4 âm **nhất quán** ở h=3-4 trên **hai cặp độc lập**:
EURUSD t=−2,18 · GBPUSD t=−3,24. Cùng dấu, cùng horizon, hai thị trường khác nhau.
Chưa đủ để giao dịch, nhưng đây là ứng viên giả thuyết *fade* duy nhất rút ra được
từ vòng này.

---

## 4. Điều này chứng minh cái gì

Người dùng đặt ra ràng buộc *"không được bê nguyên The Cheopard sang Forex"* như một
nguyên tắc. Vòng 1 chuyển nó thành **kết quả đo được**, và mạnh hơn dự kiến: vấn đề
không nằm ở tham số, ngưỡng biến động hay chi phí — mà ở chỗ **loại giả thuyết**.

Cả 8 family đều đọc **hình dạng giá của MỘT công cụ đơn lẻ**. Đó là cách tiếp cận
hợp lý với vàng — một tài sản thật, có cung cầu vật chất, có dòng tiền trú ẩn vĩ mô.
**EURUSD không phải một tài sản. Nó là một TỶ SỐ giữa hai đồng tiền.** Thông tin
định giá nó nằm ở chênh lệch lãi suất, dòng vốn và sức mạnh tương đối của từng đồng
— chứ không nằm trong hình nến của chính tỷ số đó.

Đó là lý do cấu trúc khiến `PAIR × STRATEGY` thất bại, và cũng là lý do người dùng
yêu cầu `PAIR × SESSION × REGIME × STRATEGY` ngay từ đầu.

---

## 5. Cái gì giữ lại từ The Cheopard (đã kiểm chứng qua vòng này)

| tầng | phán quyết | căn cứ |
| ---- | ---------- | ------ |
| `pa_framework/features.py` | **TÁI DÙNG** | asset-agnostic thật; 75 cột chạy đúng trên FX không sửa dòng nào |
| `pa_framework/families.py` (cấu trúc `FamilySpec`) | **TÁI DÙNG** | "một luật, hai consumer" — đúng thứ giữ parity live↔backtest |
| `pa_framework/families.py` (8 luật cụ thể) | **LOẠI** | §3 — không cái nào có thông tin trên FX |
| `exit_lab/exit_engine.py` | **TÁI DÙNG** | mô phỏng M1 4 điểm giá, không look-ahead; chi phí đã tham số hoá |
| `exit_lab/metrics.py`, `grid_search.py` | **TÁI DÙNG** | walk-forward + Monte Carlo, asset-agnostic |
| `validation/*` (DSR, PBO, stress, control) | **TÁI DÙNG** | tầng chống overfit là tài sản lớn nhất của repo cũ |
| `core/intelligence/regime_engine.py` | **THÍCH NGHI** | ngưỡng đã chuẩn hoá theo ATR và √N — cấu trúc đúng, phải hiệu chỉnh lại từng cặp |
| chi phí / ngưỡng ATR / spread cap | **VIẾT LẠI** | §1 — đã xong qua `asset_profile.py` |
| `cost_context.session_id()` | **VIẾT LẠI** | phiên chia theo hành vi vàng; FX có cấu trúc phiên khác (§1) |
| position sizing (`target_mode`, `ftmo.py`) | **VIẾT LẠI** | tính theo $/oz; FX cần pip value theo cặp + phơi nhiễm tiền tệ |
| Currency Exposure / Correlation Engine | **CHƯA TỒN TẠI** | hệ vàng một symbol nên không cần; hệ FX bắt buộc phải có |

---

## 6. Hướng vòng 2

Bỏ hẳn hướng "mẫu hình giá trên một cặp". Giả thuyết mới phải khai thác đúng cái
làm nên Forex — và cả ba đều dùng được dữ liệu 7 cặp đang có:

1. **Currency Strength / Cross-sectional** — xếp hạng 8 đồng tiền từ 7 cặp, giao dịch
   đồng mạnh nhất vs yếu nhất. Đây là dạng bài mà FX có edge được ghi nhận rộng rãi,
   và nó biến `EURUSD BUY + GBPUSD BUY + AUDUSD BUY` thành **một** vị thế "USD yếu"
   thay vì ba lệnh độc lập — chính là Currency Exposure Engine người dùng yêu cầu.
2. **Session/Time-of-day conditional drift** — cấu trúc phiên đo được ở §1 rất mạnh
   và ổn định. Kiểm định trực tiếp drift có điều kiện theo giờ × phiên × cặp trước
   khi gắn bất kỳ mẫu hình nào lên nó.
3. **Trend ở horizon dài hơn** — Carver đo trend FX hiệu quả ở thang 30-100 ngày,
   không phải breakout H1. H1 vẫn là khung **thực thi**, nhưng tín hiệu neo vào D1.

Mỗi giả thuyết phải qua đúng cổng của §3 (entry power + control) **trước khi** được
phép chạm vào backtest.
