# The Cheopard Forex — Hệ thống BA CHÂN hoàn chỉnh

> Ngày 13/08/2026 · Thay thế `05_he_thong_ftmo.md` (tài liệu đó chỉ có hai chân D1,
> chưa có chân H1 và chưa có ràng buộc đuôi trong chính sách đòn bẩy).
> Mỏ neo luật: `docs/ftmo/ftmo.md` — khi mâu thuẫn, **tài liệu đúng, sửa code**.

---

## 0. Hệ thống

```
DANH MỤC BA CHÂN — chia đều rủi ro, chuẩn hoá biến động trên FORM
├── CurrencyReversal    D1 → H1   long đồng vừa yếu / short đồng vừa mạnh
├── CurrencyCarry       D1 → H1   long đồng lãi cao / short đồng lãi thấp
└── CrossMeanReversion  H1 → H1   mean reversion trên 20 cặp chéo tổng hợp
    ↑ CHIẾN LƯỢC H1 — tìm được sau 13 hướng nội ngày bị bác bỏ

CỔNG CHẾ ĐỘ   biến động rổ ≥ phân vị 80 trượt → hai chân D1 đứng ngoài
ĐÒN BẨY       thích ứng theo đệm equity + RÀNG BUỘC ĐUÔI
THỰC THI      H1, cửa sổ 10:00-16:00 UTC (tối ưu 15:00), cấm 20:00-23:00
LOG           mọi quyết định vào `logs/decisions/` — kể cả HOLD/SKIP
```

| ở đòn bẩy 1,0 (chuẩn hoá) | FORM 2020-24 | **OOS 2024-26** | ALL       |
| ------------------------- | ------------ | --------------- | --------- |
| **Sharpe**                | 0,884        | **1,260**       | **1,006** |
| Sortino                   | 0,999        | 1,160           | 1,055     |
| Calmar                    | 0,649        | 0,729           | 0,674     |
| hit rate                  | 0,416        | 0,440           | 0,426     |

**7/7 năm dương.** Đủ chi phí: spread + commission + swap + biên broker 1,0%/năm.

| tương quan | reversal | carry      | cross_h1   |
| ---------- | -------- | ---------- | ---------- |
| reversal   | 1,000    | **−0,059** | **+0,050** |
| carry      | −0,059   | 1,000      | **+0,008** |

Gần trực giao hoàn hảo — đây là lý do ghép ba chân hoạt động.

---

## 1. Chân H1 — thứ tìm được sau 13 lần thất bại

`strategies/h1/cross_mean_reversion.py`

### Ý tưởng then chốt

Spread EURUSD/GBPUSD **chính là EURGBP**. Giao dịch nó như _một cặp chéo_ thay vì
_hai chân USD_ trả **một** spread và **một** biên swap:

|               | 2 chân USD | **1 cross** |
| ------------- | ---------- | ----------- |
| phí giao dịch | 2,14 bps   | 1,86        |
| swap          | 6,29 bps   | **3,50**    |
| net/lệnh      | +1,31      | **+15,35**  |
| OOS           | −1,11      | +1,96       |

Arbitrage tam giác giữ giá cross khớp hai cặp USD tới từng pip — cùng một spread,
khác chỗ trả phí.

### Luật — lấy NGUYÊN từ Zheng Nan (2025)

```
1. mỗi 500 nến: HL từ AR(1) trên log giá 2000 nến trước; bỏ nếu HL ∉ [4,120]
2. window = ceil(HL × 4,32)            ← ln(1/0,05)/ln2, phân rã 95%
3. µ, σ = log giá trong `window` nến TRƯỚC;  z = (logP − µ)/σ
4. VÀO: z ra ngoài ±2σ RỒI QUAY VÀO → vào NGƯỢC chiều lệch
5. RA:  logP cắt µ (89% lệnh)  hoặc  time-stop ceil(4,32×HL) (11%)
6. khớp trong 10:00-16:00 UTC
```

### Kết quả — 1.886 lệnh, 290 lệnh/năm, giữ 6,4 ngày

|          | FORM  | **OOS**   | ALL       |
| -------- | ----- | --------- | --------- |
| Sharpe   | 1,027 | **1,121** | **1,059** |
| bps/ngày | 9,86  | 9,22      | 9,60      |

gross +16,16 · phí 2,14 · swap 5,38 · **net +8,64 bps**

### Cổng đã qua

| cổng                               | kết quả                                                                     |
| ---------------------------------- | --------------------------------------------------------------------------- |
| **PBO**                            | **0,2571** — dưới ngưỡng 0,50. **Đầu tiên của dự án** (mọi cái trước 0,686) |
| Control (ngẫu nhiên hoá thời điểm) | thật +3,64 vs p50 −5,97 → **p = 0,0000**                                    |
| **Bootstrap Levich & Thomas**      | thật +14,02 vs xáo trộn p50 −1,13, p95 +4,22 → **p = 0,0000**               |
| Kiểm tra Menkhoff                  | corr(spread, net) = **−0,064** — không lệch về cross đắt                    |
| Vùng tham số                       | **15/15 ô dương**, min 0,496 · trung vị 0,813                               |
| Ổn định năm                        | 6/7 dương                                                                   |
| Outlier                            | bỏ 20/2633 lệnh tốt nhất = 50,4%, **giữ dấu**                               |

**Bootstrap Levich & Thomas (NBER 1991)** là bài quan trọng nhất và tôi chưa từng
chạy trước đó: xáo trộn **chính chuỗi giá** (phá cấu trúc chuỗi, giữ nguyên phân
phối/biến động/đuôi) rồi chạy lại luật 60 lần. Nếu luật "ra ngoài dải rồi quay vào"
tự tạo thiên lệch tổng hợp thì nó phải lộ ra ở đây. Không lộ → **lợi nhuận đến từ
mean reversion thật, không từ hình dạng của luật.**

**Kiểm tra Menkhoff** (BIS WP366) — họ cảnh báo trực tiếp: _"danh mục momentum FX
lệch mạnh về đồng tiền PHỤ có chi phí cao, chiếm ~50% lợi nhuận"_. Đo trên 20 cross:
cross rẻ 42% / đắt 58%, đúng tỷ lệ số lượng (9 vs 11). Không rơi vào bẫy.

---

## 2. Ràng buộc ĐUÔI — sửa một lỗi thiết kế nghiêm trọng

### Lỗi

Chính sách đòn bẩy ban đầu dùng hệ số σ (3,0σ ngày / 2,5σ cho 21 ngày), tức **giả
định phân phối chuẩn**. Chuỗi thật không chuẩn:

```
σ = 50,4 bps/ngày = 0,504%      ngày tệ nhất = −546,6 bps = −5,47%  →  10,8σ
```

Ở đòn bẩy 1,73x mà hai ràng buộc đầu cho phép, ngày đó thành **−9,47% equity** —
vượt cả giới hạn lỗ ngày 5% của FTMO. Đo được: **vi phạm 29–57%** cửa sổ funded.

### Sửa

Thêm ràng buộc thứ ba, lấy min của cả ba:

```
lev_ngày = đệm_ngày / (3,0 × σ)
lev_tổng = đệm_tổng / (2,5 × σ × √21)
lev_đuôi = đệm_ngày / (1,3 × |ngày tệ nhất ĐÃ THẤY|)     ← MỚI
```

Hệ số 1,3 vì ngày tệ nhất _tương lai_ có thể tệ hơn ngày tệ nhất _đã quan sát_ —
mẫu 6,5 năm không phải giới hạn của phân phối.

### Kết quả

|                        | không đuôi | **có đuôi** |
| ---------------------- | ---------- | ----------- |
| Phase 1 PASS           | 60,8%      | 33,3%       |
| Phase 1 **VI PHẠM**    | 4,9%       | **0,0%**    |
| Phase 2 PASS           | —          | **71,6%**   |
| Phase 2 VI PHẠM        | —          | **0,0%**    |
| FUNDED **VI PHẠM**     | 29–57%     | **0,0%**    |
| FUNDED equity trung vị | +3,85%     | **+6,53%**  |
| FUNDED **p10 equity**  | −6,84%     | **+0,64%**  |

**p10 = +0,64%** nghĩa là **90% cửa sổ 1 năm có lãi**. Không chỉ tránh vi phạm mà
tránh cả thua lỗ. Đòn bẩy hạ 1,73x → 0,70x, ngày tệ nhất −9,47% → **−3,85%**.

Đánh đổi: Phase 1 pass 60,8% → 33,3%. Đây là đánh đổi ĐÚNG theo nguyên tắc thứ tự
của dự án (`Account Survival > FTMO Compliance > ... > Profit Maximization`) —
trượt kỳ thi thì thi lại được, vi phạm thì mất tài khoản. Và Phase 2 (+5%) vẫn
**71,6% pass với 0% vi phạm**, nên đường đi thực tế là qua Phase 1 chậm hơn chứ
không phải không qua được.

---

## 3. Lỗi đơn vị tôi mắc và đã sửa

`PortfolioResult` giờ trả **hai** chuỗi, và tài liệu ghi rõ đừng lẫn chúng:

|                        | đơn vị                             | dùng cho                                    |
| ---------------------- | ---------------------------------- | ------------------------------------------- |
| `net`                  | số lần σ_FORM                      | Sharpe/Calmar/tương quan (bất biến đòn bẩy) |
| `net_bps`              | bps thật, đòn bẩy 1,0              | —                                           |
| `risk_parity_bps(vol)` | bps, mỗi chân góp rủi ro bằng nhau | **sizing + FTMO**                           |

Lý do phải tách: ba chân lệch biến động rất mạnh ở đòn bẩy 1,0 —
**reversal 4,45%/năm · carry 4,27% · cross_h1 22,46%**. Tôi đã quy chuỗi _chuẩn hoá_
sang % equity bằng cách nhân hằng số, và đó là lỗi đơn vị làm mô phỏng FTMO sai
hoàn toàn (vi phạm 55,9% trong khi Phase 1 chỉ 4,9% — con số không thể cùng đúng).

`risk_parity_bps()` là cách gộp đúng: giữ chia-đều-rủi-ro (cross_h1 không áp đảo)
đồng thời cho đơn vị % equity dùng được.

---

## 4. Log quyết định vào lệnh

`execution/decision_log.py` — JSONL xoay theo tháng, ghi **cả lần KHÔNG giao dịch**.

```
[2026-07-17 17:00] CADCHF HOLD · z=+1.78 (µ=... σ=...) · HL=79 cửa sổ=340
                   · timestop=340 nến · chi phí≈1.85bps
                   · z=+1.78 trong dải, chưa có lệch đủ lớn
```

Mỗi bản ghi có đủ: `z_score`, `mu`, `sigma`, `half_life_bars`, `window_bars`,
`was_outside_band`, `reentered`, `hl_in_range`, `execution_hour_ok`,
`est_cost_bps`, `timestop_bars`, `reason`.

Ba hàm truy vấn:

- `audit_trade(cross, entry_time)` — bối cảnh ±48h quanh một lệnh cụ thể
- `daily_summary(day)` — mỗi cross một dòng, hành động + lý do
- `load(month, strategy)` — đọc thô

Vì sao ghi cả HOLD/SKIP: câu hỏi vận hành hay gặp nhất **không** phải "vì sao mở
lệnh này" mà là **"vì sao hôm nay không có lệnh nào"**. Chỉ log lệnh đã mở thì câu
đó không trả lời được.

Và vì sao cần tách khỏi log nghiên cứu: khi một lệnh tiền thật thua bất thường, chỉ
bản ghi đầy đủ tham số mới phân biệt được ba khả năng — (a) tín hiệu đúng luật,
thị trường đi ngược; (b) tham số đã **trôi**; (c) dữ liệu vào **sai**.

---

## 5. Hai ý tưởng có nguồn tốt nhưng dữ liệu KHÔNG ủng hộ

| ý tưởng            | nguồn                              | kết quả                                                                    |
| ------------------ | ---------------------------------- | -------------------------------------------------------------------------- |
| Inverse-vol sizing | TSMOM §4.1 "position size = 40%/σ" | 1,059 → 1,068 (**+0,9%**) — quá nhỏ để tin                                 |
| ATR exclusion zone | AdTurtle (JRFM 2019)               | FORM **xấu đi** 1,027 → 0,994 trong khi OOS tốt lên — chữ ký chọn theo OOS |

Ghi lại để không thử lại. Cả hai đều là ý tưởng hợp lý từ nguồn bình duyệt; đó
chính là lý do phải đo chứ không suy.

---

## 6. Rủi ro và giới hạn

1. **Chi phí cross là ƯỚC LƯỢNG.** Giá cross suy chính xác từ hai cặp USD (arbitrage
   tam giác), nhưng `D:/data-ticks-train` không có chuỗi cross nên spread lấy từ bảng
   công bố broker raw-spread. **Phải đo spread thật trước khi cấp vốn.**
2. **Chân H1 chết ở chi phí ×2.** Biên mỏng.
3. **Phụ thuộc biên swap broker** (Sharpe danh mục ALL/OOS):
   | biên | 0,0% | 0,5% | **1,0%** | 1,5% | 2,0% | 3,0% |
   | --- | --- | --- | --- | --- | --- | --- |
   | ALL | 1,607 | 1,306 | **1,006** | 0,708 | 0,412 | −0,174 |
   | OOS | 1,962 | 1,610 | **1,260** | 0,913 | 0,569 | −0,110 |
   → `scripts/check_broker_swap.py` là cổng đi/dừng.
4. **Đuôi dày.** Ngày tệ nhất 10,8σ. Ràng buộc đuôi xử lý được điều đã thấy, nhưng
   một ngày 15σ trong tương lai vẫn có thể vượt biên 1,3.
5. **Cửa sổ đo 6,5 năm**, 86 cửa sổ FTMO **chồng lấn** (bước 21 ngày) → tỷ lệ
   PASS/vi phạm là ước lượng thô, không phải xác suất độc lập.
6. **Cross ngầm chồng lấn với hai chân D1** — EURGBP mang EUR long + GBP short. Tương
   quan đo được nhỏ (+0,050 / +0,008) nhưng không bằng 0; `portfolio.exposure_report()`
   theo dõi phơi nhiễm ròng gồm cả phần ngầm này.

---

## 7. Kiến trúc

```
src/python/
├── strategies/
│   ├── registry.py            SSOT — 3 chiến lược + 10 hướng đã bác bỏ kèm lý do
│   ├── portfolio.py           DANH MỤC BA CHÂN — điểm vào duy nhất cho live
│   ├── d1/  currency_reversal · currency_carry
│   ├── h1/  cross_mean_reversion          ← CHIẾN LƯỢC H1
│   └── m30/ news_overreaction             (đã bác bỏ, giữ làm bản ghi)
├── execution/
│   ├── portfolio_sizing.py    tỷ trọng → lot, ràng buộc FTMO
│   ├── ftmo_leverage_policy.py đòn bẩy thích ứng + ràng buộc ĐUÔI
│   └── decision_log.py        sổ quyết định vào lệnh
├── research/                  fx_* (13 vòng) · validation/ (bộ kiểm định)
├── shared/                    asset_profile · fx_data · carry_costs · indicators
└── core/infra/                ftmo.py (luật quỹ) · symbol_spec · mt5_bridge

scripts/check_broker_swap.py   ← CHẠY ĐẦU TIÊN, quyết định đi/dừng
research/fx/                   38 script nghiên cứu, mỗi vòng một file
```

---

## 8. Việc tiếp theo

1. **`scripts/check_broker_swap.py`** trên MT5 broker thật → lấy biên swap, chạy lại
   `PF.backtest(broker_markup_pct=<số thật>)`. Nếu > 2,0%/năm thì đổi broker.
2. **Đo spread thật của 20 cross** trên MT5 — thay `TYPICAL_SPREAD_PIPS` trong
   `fx_cross_pairs.py` bằng số đo được, chạy lại toàn bộ.
3. **Tầng thực thi MT5**: đọc giá live → `portfolio.live_targets()` →
   `portfolio_sizing.size_portfolio()` → `ftmo_leverage_policy.decide(worst_day_bps=…)`
   → đặt lệnh, kèm reconciliation.
4. **Forward test demo ≥ 3 tháng.** Chân H1 có 290 lệnh/năm nên 3 tháng ≈ 70 lệnh —
   đủ để bắt lỗi vận hành và kiểm parity, **chưa** đủ để kết luận về edge.
