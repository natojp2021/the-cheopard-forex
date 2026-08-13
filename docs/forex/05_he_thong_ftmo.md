# The Cheopard Forex — Hệ thống hoàn chỉnh cho FTMO $100.000

> Ngày 13/08/2026 · Thay thế các con số ở `03_` và `04_` (hai tài liệu đó lần lượt
> thiếu phí swap và thiếu chân carry).
> Mỏ neo luật: `docs/ftmo/ftmo.md` — khi mâu thuẫn, **tài liệu đúng, sửa code**.

---

## 0. Hệ thống cuối cùng

```
DANH MỤC HAI CHÂN, chia đều
├── currency_reversal   long đồng vừa YẾU / short đồng vừa MẠNH   (21 ngày)
└── currency_carry      long đồng lãi CAO / short đồng lãi THẤP   (21 ngày)
    ↓ gộp tỷ trọng TRƯỚC khi tính chi phí  → phơi nhiễm giảm 37%
CỔNG CHẾ ĐỘ  biến động rổ ≥ phân vị 80 (trượt 252 ngày) → đứng ngoài
ĐÒN BẨY      thích ứng theo đệm equity, trần 4x
THỰC THI     H1, cửa sổ 10:00-16:00 UTC (tối ưu 15:00), cấm 20:00-23:00
```

| ở đòn bẩy 1,0 | DEV 2020-24 | **OOS 2024-26** | ALL   |
| ------------- | ----------- | --------------- | ----- |
| Lợi nhuận/năm | 2,51%       | **3,48%**       | 2,88% |
| Biến động/năm | 3,62%       | 2,47%           | 3,22% |
| **Sharpe**    | 0,557       | **1,132**       | 0,721 |
| Sortino       | 0,683       | 1,197           | 0,837 |
| **MaxDD**     | 5,28%       | **4,25%**       | 5,28% |
| Calmar        | 0,475       | **0,819**       | 0,546 |

**Đủ chi phí**: spread + commission + swap chênh lệch lãi suất + biên broker 1,0%/năm.

---

## 1. Vì sao chân carry — nó tháo đúng nút thắt

`04_ket_qua_cuoi_cung.md` kết luận: reversal đơn bị chặn bởi phí swap (biên broker
ăn 1,457%/năm = 25% lợi nhuận gộp), và reversal **short carry hệ thống**
(−0,231%/năm, t = −7,74).

Carry là chiến lược duy nhất trong toàn bộ tài liệu đã đọc có **dấu phơi nhiễm swap
ngược lại**. Đo được:

|                    | chênh lệch lãi suất    | phơi nhiễm gộp | phí carry tổng  |
| ------------------ | ---------------------- | -------------- | --------------- |
| reversal đơn       | **+0,184%/năm** (trả)  | 1,457          | +1,641%/năm     |
| carry đơn          | **−1,716%/năm** (nhận) | 1,448          | −0,268%/năm     |
| **hai chân 50/50** | —                      | **0,913**      | **+0,147%/năm** |

Hai cơ chế cùng hoạt động:

1. **Bù trừ lãi suất** — một chân trả, chân kia nhận
2. **Triệt tiêu vị thế** — hai chân thường yêu cầu hướng ngược nhau trên cùng cặp
   (reversal short đồng mạnh, carry long đồng lãi cao, mà đồng mạnh thường lãi cao),
   nên gộp tỷ trọng trước khi tính chi phí làm phơi nhiễm gộp giảm **1,457 → 0,913**

Đo được: gộp vị thế tiết kiệm **+0,595%/năm** so với cộng hai chuỗi lợi nhuận rời.
Đây chính là **Currency Exposure Engine** hoạt động ở tầng liên-chiến-lược.

Tương quan hai chân: **−0,059** (gần như độc lập hoàn hảo).

### Kết quả đúng như Olszweski & Zhou dự đoán

|             | reversal đơn | **hai chân** | họ đo (momentum+carry, 20 năm) |
| ----------- | ------------ | ------------ | ------------------------------ |
| ALL Sharpe  | 0,576        | **0,721**    | 0,79 → **0,98**                |
| OOS Sharpe  | 0,395        | **1,132**    | —                              |
| MaxDD       | 8,27%        | **5,28%**    | −17,4%/−29,2% → **−8,95%**     |
| r_cubed     | 0,559        | **0,759**    | —                              |
| DD dài nhất | 610 ngày     | **495 ngày** | —                              |

`w = 0,5` là **chia đều do Olszweski & Zhou đặc tả trước** (họ chứng minh chia đều
thắng tối ưu hoá mean-variance, 0,98 vs 0,70), KHÔNG phải giá trị chọn từ lưới —
điểm này quan trọng vì PBO trên lưới tỷ trọng vẫn là 0,686.

### Độ nhạy biên swap — nút thắt đã được tháo

| biên broker | REV đơn ALL / OOS | **hai chân ALL / OOS** |
| ----------- | ----------------- | ---------------------- |
| 0,5%        | 0,728 / 0,587     | **0,862 / 1,301**      |
| 1,0%        | 0,576 / 0,395     | **0,721 / 1,132**      |
| 2,0%        | 0,272 / **0,009** | **0,438 / 0,794**      |
| 3,0%        | −0,032 / −0,376   | **0,154 / 0,455**      |

Ở biên 2,0% reversal đơn chết; hai chân vẫn OOS Sharpe 0,794. **Biên swap không còn
là công tắc sinh tử** — nhưng vẫn phải đo (`scripts/check_broker_swap.py`).

---

## 2. Đòn bẩy thích ứng — cải tiến lớn nhất

### Vấn đề của đòn bẩy cố định

Rủi ro vi phạm **không cố định theo thời gian**:

- Ngày đầu: equity $100.000, sàn $90.000 → đệm đúng 10%. Nguy hiểm nhất, và đây là
  nơi gần như toàn bộ xác suất vi phạm được sinh ra.
- Sau khi lãi 8%: equity $108.000, sàn vẫn $90.000 → đệm 16,7%. An toàn hơn hẳn mà
  ta vẫn đang dùng đúng mức đòn bẩy cũ.

`execution/ftmo_leverage_policy.py` đặt đòn bẩy là hàm của **đệm còn lại tới sàn**,
lấy giá trị nhỏ hơn giữa hai ràng buộc, tính lại mỗi ngày:

```
lev_ngày = đệm_ngày / (3,0 × σ_ngày)
lev_tổng = đệm_tổng / (2,5 × σ_ngày × √21)     [21 = chu kỳ tái cân bằng]
```

### Đo được — 86 cửa sổ trượt, luật FTMO đầy đủ

**Phase 1 (+10%, 252 ngày):**
| cấu hình | PASS | **VI PHẠM** | ngày TV | equity p10 |
| --- | --- | --- | --- | --- |
| cố định 3x | 37,2% | 9,3% | 162 | +0,00% |
| cố định 4x | 59,3% | 18,6% | 155 | −11,07% |
| cố định 6x | 76,7% | 20,9% | 90 | −10,74% |
| **thích ứng, trần 4x** | 52,3% | **1,2%** | 146 | **−7,10%** |
| **thích ứng, trần 6x** | 57,0% | **1,2%** | 113 | **−7,09%** |

**Cùng tỷ lệ pass, vi phạm thấp hơn 15 lần.**

**Phase 2 (+5%):** thích ứng trần 4x → PASS 74,4%, vi phạm **1,2%**
(cố định 3x: 77,9% / 9,3%).

**Funded (1 năm, chỉ cần sống):**
| cấu hình | lợi nhuận TV | vi phạm |
| --- | --- | --- |
| cố định 4x | — | 23,3% |
| **thích ứng, trần 4x** | **+6,37%/năm** | **5,8%** |
| thích ứng, trần 6x | +2,57%/năm | 5,8% |

⚠️ **Trần 4x tốt hơn trần 6x** ở tài khoản funded — nghịch lý biểu kiến nhưng có cơ
chế: đòn bẩy cao gây drawdown sâu hơn, kích hoạt trạng thái PRESERVATION/HALT, rồi
khoá đòn bẩy ở mức thấp trong thời gian dài. **Khuyến nghị: trần 4x.**

### Chính sách quyết định gì

| tình huống         | equity   | đòn bẩy   | trạng thái   | chặn bởi       |
| ------------------ | -------- | --------- | ------------ | -------------- |
| ngày đầu           | $100.000 | 4,30x     | CONSERVATIVE | MAX_LOSS       |
| đã lãi 3%          | $103.000 | 5,43x     | NORMAL       | MAX_LOSS       |
| đã lãi 8%          | $108.000 | 6,00x     | NORMAL       | TRẦN CỨNG      |
| đang lỗ 4%         | $96.000  | 2,69x     | PRESERVATION | MAX_LOSS       |
| lỗ 8%, sát sàn     | $92.000  | **0,00x** | **HALT**     | ĐỆM CẠN        |
| lỗ 2,9% trong ngày | $101.000 | 3,58x     | CONSERVATIVE | **DAILY_LOSS** |

Đây là anti-martingale trên đường equity — đúng máy trạng thái mà
`docs/ftmo/ftmo-the-cheopard.md` đặt ra, diễn đạt lại cho danh mục vol-target.

---

## 3. Tinh chỉnh cho cặp tiền — ba điểm quy đổi

`execution/portfolio_sizing.py`. Hệ XAUUSD cũ tính `lot = rủi ro USD / (khoảng cách
SL × giá trị điểm)` — công thức đó giả định mỗi lệnh có SL riêng. **Danh mục cắt
ngang không có SL từng lệnh**; nó có tỷ trọng mục tiêu và rủi ro đo bằng biến động.

1. **Giá trị 1 lot phụ thuộc họ cặp:**
   ```
   XXXUSD:  1 lot = 100.000 XXX  →  notional USD = 100.000 × price
   USDXXX:  1 lot = 100.000 USD  →  notional USD = 100.000   (không nhân giá)
   ```
   Dùng chung một công thức là sai notional tới vài lần.
2. **Làm tròn theo `volume_step` của broker, làm tròn XUỐNG** — vượt trần rủi ro do
   làm tròn lên là lỗi im lặng.
3. **`symbol_spec.py` đã viết lại**: bản cũ ghim XAUUSD làm fallback cho mọi symbol
   lạ — với FX đó là sai sizing ~1.000 lần (vàng 100 oz/lot point 0,01; EURUSD
   100.000 đơn vị point 0,00001). Nay fallback là chuẩn FX, và ghi log CẢNH BÁO khi
   phải dùng fallback.

`ftmo.py` cũng đã sửa: `SYMBOL = "XAUUSD"` (một symbol duy nhất) → `SYMBOLS_ALLOWED`
gồm 7 cặp, có bỏ hậu tố broker khi so khớp. Chiến lược cắt ngang **bắt buộc** phải
giữ nhiều cặp cùng lúc — một symbol duy nhất làm nó không định nghĩa được.

---

## 4. Bằng chứng edge (không đổi sau khi thêm chi phí)

| bài                        | kết quả                                             |
| -------------------------- | --------------------------------------------------- |
| Control ngẫu nhiên         | phân vị **99,2%**, **p = 0,0083**                   |
| Bootstrap khối 21 ngày     | Sharpe 0,645, CI95 [−0,006 · +1,250]                |
| `parameter_stability_scan` | **không vách đá** trên q ∈ [0,40·0,90] và w ∈ [0·1] |
| `tenths_consistency`       | **8/10 khúc dương**                                 |
| `robust_metrics`           | r_cubed 0,759 · robust_sharpe 0,721 · MAR 0,443     |
| `outlier_removal_test`     | 5 tháng tốt nhất = 61,4%, bỏ đi **vẫn giữ dấu**     |
| Cả hai chân reversal       | long đồng yếu 0,67 · short đồng mạnh 0,59           |
| Dollar-neutral             | max\|Σw\| = **2,78e-16** theo xây dựng              |

Theo năm (đòn bẩy 1,0): 2020 +1,10% · 2021 +5,00% · 2022 −0,14% · 2023 +2,11% ·
2024 +4,53% · 2025 −0,16% · 2026 +5,03%. **Không năm nào lỗ đáng kể.**

---

## 5. ⚠️ Rủi ro và giới hạn phải biết

1. **PBO = 0,686** trên cả lưới ngưỡng chế độ lẫn lưới tỷ trọng. Nghĩa là **không
   chọn được tham số đáng tin** — nên mọi tham số đều lấy giá trị đặc tả trước từ
   nguồn (q=0,80 quy ước quintile; w=0,5 chia đều theo Olszweski & Zhou), không lấy
   giá trị tốt nhất trên lưới. Kỳ vọng hợp lý là **trung bình bình nguyên**.
2. **Đuôi dày**: 5 tháng tạo 61,4% lợi nhuận. Một năm không gặp tháng tốt là bình
   thường và KHÔNG có nghĩa chiến lược hỏng.
3. **Drawdown có thể kéo 495 ngày** (~1,4 năm).
4. **Cửa sổ đo 6,5 năm, 86 cửa sổ CHỒNG LẤN** (bước 21 ngày) — các tỷ lệ PASS/vi
   phạm là ước lượng thô, không phải xác suất độc lập.
5. **Mặt cắt ngang chỉ 7 cặp.** Menkhoff et al. dùng vũ trụ rộng hơn nhiều. Mở rộng
   cần nguồn dữ liệu mới (SEK/NOK không có trong `D:\data-ticks-train`).
6. **Lãi suất dùng lãi suất CHÍNH SÁCH**, không phải tiền gửi 3 tháng như nguồn gốc
   — tín hiệu carry vì vậy chậm hơn. Ở live nên thay bằng swap thật từ MT5.

---

## 6. Kiến trúc

```
src/python/
├── shared/
│   ├── asset_profile.py       SSOT pip/contract/commission theo cặp
│   ├── fx_data.py             SSOT nạp M1/D1
│   └── carry_costs.py         mô hình swap (Carver) + lãi suất chính sách
├── strategies/
│   ├── currency_reversal.py   chân 1 + cổng chế độ + cửa sổ thực thi H1
│   └── currency_carry.py      chân 2 + hàm `combined()` gộp danh mục
├── execution/
│   ├── portfolio_sizing.py    tỷ trọng → lot, ràng buộc FTMO
│   └── ftmo_leverage_policy.py đòn bẩy thích ứng theo đệm equity
├── core/infra/                ftmo.py (luật quỹ) · symbol_spec · mt5_bridge · clock
└── research/                  fx_* (vòng nghiên cứu) · validation/ (bộ kiểm định)

scripts/check_broker_swap.py   ← CHẠY ĐẦU TIÊN, quyết định đi/dừng
```

**Quy ước code:** tên hàm/biến tiếng Anh, chú thích tiếng Việt, docstring nêu rõ
_vì sao_ chứ không chỉ _cái gì_.

---

## 7. Việc tiếp theo

1. **`scripts/check_broker_swap.py`** trên MT5 broker sẽ dùng → lấy biên swap thật,
   chạy lại `CR.backtest(broker_markup_pct=<số thật>)`.
2. **Tầng thực thi MT5**: đọc giá live → `combined()` → `size_portfolio()` →
   `ftmo_leverage_policy.decide()` → đặt lệnh qua `mt5_bridge`, kèm reconciliation
   vị thế và log quyết định.
3. **Forward test trên demo tối thiểu 3 tháng** trước khi cấp vốn thật. Với chu kỳ
   tái cân bằng 21 ngày, 3 tháng chỉ là ~4 chu kỳ — đủ để bắt lỗi vận hành, **không**
   đủ để kết luận về edge.
4. **Không** quét thêm biến thể của chính hai chiến lược này. PBO đã 0,686.
