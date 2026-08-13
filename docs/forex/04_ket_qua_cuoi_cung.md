# The Cheopard Forex — Kết quả cuối vòng 2: edge thật, và một rào cản nằm ngoài code

> Ngày 13/08/2026 · Dữ liệu `D:\data-ticks-train\_m1` · Mã `src/python/strategies/currency_reversal.py`
> Thay thế các con số ở `03_ket_qua_vong_2_champion.md` — tài liệu đó **chưa tính phí swap**.

---

## 0. Tóm tắt cho người ra quyết định

Tìm được **một chiến lược thuần Forex có edge được kiểm chứng nghiêm ngặt**:
Cross-Sectional Currency Short-Term Reversal. Edge phân biệt được với ngẫu nhiên ở
**p = 0,0083**, cả hai chân đều sinh lời, 7/7 năm dương trước phí swap.

Nhưng sau khi mô hình hoá **phí swap qua đêm** — thứ tôi đã bỏ sót cho đến khi đọc
`project-refer/carver-systematic-trading` — kết quả rơi vào vùng ranh giới, và **khả
năng triển khai phụ thuộc vào một tham số nằm ngoài code: biên swap của broker.**

**Việc phải làm trước tiên:** chạy `scripts/check_broker_swap.py` trên MT5 của broker
sẽ dùng. Con số đó quyết định đi tiếp hay dừng.

---

## 1. Bài học từ `project-refer/carver-systematic-trading`

Repo tham chiếu ghi lại một nghiên cứu kết thúc bằng kết luận phủ định, và kết luận
ấy giá trị hơn nhiều kết quả dương:

> *"EWMAC trend following on retail CFDs is not viable after swap costs."*
> *"Swap alone turns +$130K gross profit into -$80K net loss."*

Bảng của họ cho thấy trình tự sụp đổ:

| kịch bản | Sharpe |
| -------- | ------ |
| Gross (không chi phí) | 0,314 |
| Net (chỉ spread + commission) | 0,216 ← vẫn trông ổn |
| **Net (đủ chi phí, có swap)** | **−0,456** ← chết |

**Spread và commission không giết chiến lược giữ lệnh lâu; swap thì có.** Chiến lược
của tôi giữ vị thế 21 ngày. Cho đến trước khi đọc repo này, backtest của tôi dừng ở
đúng cột "Sharpe 0,216" — cột trông vẫn ổn ngay trước khi sụp.

Hai kỹ thuật lấy nguyên từ đó, đã đưa vào `shared/carry_costs.py`:
* `SWAP_CALENDAR_MULTIPLIER = 365/252` — swap tính theo ngày **lịch** nhưng backtest
  lặp theo ngày **giao dịch**; bỏ qua hệ số này là hạ thấp chi phí thật ~31%
* swap FX ~ chênh lệch lãi suất chính sách, có tách riêng **biên broker**

---

## 2. Trình tự chi phí — chiến lược sống ở đâu, chết ở đâu

| lớp | ALL Sharpe | OOS Sharpe | chi phí %/năm |
| --- | ---------- | ---------- | ------------- |
| 1. Gross | 0,992 | 1,024 | — |
| 2. + spread & commission | 0,918 | 0,919 | 0,355 |
| 3. + swap chênh lệch lãi suất | 0,880 | 0,780 | 0,184 |
| **4. + biên broker 1,0%/năm** | **0,576** | **0,395** | **1,457** |

Ba lớp đầu gần như không đụng đến edge. **Lớp 4 ăn 25% lợi nhuận gộp.**

### Giả thuyết short-carry của tôi: ĐÚNG, nhưng không phải thủ phạm chính
Reversal mua đồng vừa yếu / bán đồng vừa mạnh; đồng mạnh thường là đồng lãi cao →
chiến lược short carry. **Đo được: −0,231%/năm, t = −7,74** (rất có ý nghĩa). Nhưng
độ lớn nhỏ (0,184%/năm chi phí). Thủ phạm là **biên broker**, thứ tính trên tổng phơi
nhiễm gộp bất kể chiều — nên **không cổng lọc nào tránh được**.

---

## 3. Biến quyết định: biên swap của broker

| biên %/năm | ALL Sharpe | ALL %/năm | OOS Sharpe | OOS %/năm | phán quyết |
| ---------- | ---------- | --------- | ---------- | --------- | ---------- |
| 0,00 | 0,880 | 5,24 | 0,780 | 2,96 | tốt |
| 0,25 | 0,804 | 4,79 | 0,684 | 2,59 | tốt |
| **0,50** | **0,728** | **4,33** | **0,587** | **2,23** | **dùng được** |
| 0,75 | 0,652 | 3,88 | 0,491 | 1,86 | ranh giới |
| **1,00** | **0,576** | **3,43** | **0,395** | **1,50** | **ranh giới** |
| 1,50 | 0,424 | 2,52 | 0,202 | 0,77 | không nên |
| 2,00 | 0,272 | 1,62 | 0,009 | 0,03 | **không dùng được** |

Biên 1,0%/năm ≈ **0,3 pip mỗi đêm mỗi lot** trên EURUSD — mức của một broker retail
phổ thông. Broker ECN/raw tốt có thể ở 0,3–0,5%. Đây không phải chi tiết kỹ thuật:
**nó là biến quan trọng nhất của toàn hệ.**

→ `scripts/check_broker_swap.py` đọc `swap_long`/`swap_short` thật từ MT5, tách biên
broker khỏi chênh lệch lãi suất bằng công thức `biên = −(swap_long + swap_short)/2`,
rồi cho phán quyết theo đúng bảng trên.

---

## 4. Bằng chứng edge là THẬT (không bị chi phí phủ nhận)

Chạy bằng **chính bộ công cụ có sẵn của dự án** trong `research/validation/`:

| bài | công cụ | kết quả |
| --- | ------- | ------- |
| Control ngẫu nhiên | tự viết theo mẫu | Sharpe +0,64 vs p50 control −0,08 → **phân vị 99,2%, p = 0,0083** |
| Bootstrap khối 21 ngày | tự viết | Sharpe 0,645, CI95 [−0,006 · +1,250], P(<0) = 2,6% |
| Parameter cliff | `parameter_stability_scan` + `find_stable_plateau` | **không có vách đá nào** trên q ∈ [0,40 · 0,90]; bình nguyên rộng 11/11 điểm |
| Tenths consistency | `tenths_consistency` | 8/10 khúc dương |
| Robust metrics | `robust_metrics.compute` | r_cubed 0,559 · robust_sharpe 0,638 · MAR 0,360 |
| Outlier removal | `outlier_removal_test` | 5 tháng tốt nhất = 62–79% lợi nhuận, **bỏ đi vẫn giữ dấu** |

Bằng chứng cấu trúc (không phải thống kê):
* **Cả hai chân đều sinh lời**: long đồng yếu Sharpe 0,67 · short đồng mạnh 0,59
* **Dollar-neutral 2,78e-16** theo xây dựng, không nhờ ràng buộc tối ưu hoá
* **Đóng góp phân tán**: CAD 33% · EUR 20% · NZD 15% · AUD 14% · JPY 11%
* **Cấu trúc chế độ tái lập Brière & Drut**: REVERSAL calm +5,56% (Sharpe 1,049) vs
  crisis −5,34% (−0,842) — đảo dấu hoàn toàn, đúng dạng carry/PPP của họ
* Phân phối tháng 44/79 dương (55,7%), trung vị +44 bps

---

## 5. ⚠️ Hai phát hiện chặn triển khai

### (a) PBO = 0,686 — không chọn được ngưỡng cổng chế độ
`probability_of_backtest_overfitting` (CSCV, 8 khối, 11 biến thể ngưỡng): **68,6%**
số tổ hợp cho thấy ngưỡng tốt nhất in-sample nằm **dưới trung vị** out-of-sample.
Ngưỡng của López de Prado là < 0,50.

Kết hợp với bình nguyên phẳng ở §4: các biến thể đều cho Sharpe ~0,55, nên **chọn
"tốt nhất" chính là chọn nhiễu**. Phản ứng đúng là **không chọn**: giữ
`REGIME_QUANTILE = 0.80` (phân vị 80 = "top quintile", quy ước chuẩn có sẵn từ trước
khi nhìn kết quả), và lấy **trung bình bình nguyên (~0,55)** làm kỳ vọng, không lấy
giá trị tốt nhất.

Tôi đã thử một hướng cứu — lọc theo độ phân tán tín hiệu để cắt thời gian trong thị
trường — và nó **không giúp**: mọi biến thể Sharpe 0,41–0,58, PBO giữ nguyên 0,686.
Ghi lại để không ai thử lại.

### (b) Drawdown dài và giai đoạn gần đây yếu
* `robust_metrics`: **drawdown dài nhất 610 ngày** (~1,7 năm), trung bình 367 ngày
* `tenths_consistency`: khúc 9 và 10 — tức **2025-03 → 2026-07 — đều ÂM** sau đủ chi phí
* Đuôi dày: 5 tháng tạo 62–79% lợi nhuận

Một chiến lược có thể đi ngang 1,7 năm cần cam kết vốn và tâm lý tương ứng. Với tài
khoản có ràng buộc drawdown cứng (mô hình FTMO), đây là rủi ro vận hành thật.

---

## 6. Trạng thái codebase

Theo chỉ đạo: **xoá hoàn toàn** chiến lược XAUUSD. `215 → 33 file Python`.

**Mới:**
```
shared/asset_profile.py            SSOT pip/contract/commission theo cặp
shared/fx_data.py                  SSOT nạp dữ liệu M1/D1
shared/carry_costs.py              mô hình swap (học từ Carver) + lãi suất chính sách
strategies/currency_reversal.py    CHAMPION — swap là chi phí MẶC ĐỊNH
scripts/check_broker_swap.py       đo biên swap thật từ MT5  ← chạy đầu tiên
research/fx_clock.py               cấu trúc lợi nhuận quanh đồng hồ (Krohn/Breedon)
research/fx_fix_lab.py             cô đặc + điều kiện hoá hiệu ứng fix
research/fx_fix_portfolio.py       cổng DEV/OOS + control + DSR
research/fx_momentum.py            momentum D1 (đã bác bỏ — giữ làm bản ghi)
research/fx_cross_section.py       vòng nghiên cứu cắt ngang
```

**Giữ lại vì asset-agnostic và đã dùng thật:** `research/validation/` (PBO/CSCV,
DSR, reality check, stress testing, robust metrics, robustness diagnostics),
`core/infra/` (mt5_bridge, symbol_spec, market_schedule, clock, state_store),
`shared/` (indicators, statistics, paths).

**Quy ước code:** tên hàm/biến tiếng Anh, chú thích tiếng Việt, docstring nêu rõ
*vì sao* chứ không chỉ *cái gì* — giữ nguyên định dạng hiện có.

---

## 7. Năm hướng đã bác bỏ (có bằng chứng, không lặp lại)

| hướng | bằng chứng |
| ----- | ---------- |
| 8 strategy family XAUUSD trên FX | 28/33 NO_INFORMATION; MFE/\|MAE\| ≈ 1,00; 363 phép thử sinh 5 "phát hiện" — ít hơn mức ngẫu nhiên |
| Hiệu ứng fix theo giờ (Krohn 2024) | Tín hiệu THẬT (t = −3,83, vượt Bonferroni) nhưng độ lớn ≈ 1 lượt khứ hồi. OOS Sharpe −1,34; control p = 0,56; DSR = 0,0000 |
| Momentum 20/120 ngày (Olszweski & Zhou) | Chi phí chỉ ăn 0,5–7,4% gộp, nhưng tín hiệu âm: Sharpe −0,07, 2/7 năm dương; EURUSD 11 năm −0,13 |
| Momentum cắt ngang (Menkhoff) | OOS Sharpe −0,95 (chiều ngược mới đúng) |
| Dòng cuối tháng | \|t\| lớn nhất 1,27; DEV 0,07 vs OOS 0,53 — bất ổn |
| Lọc độ phân tán tín hiệu | không cải thiện; PBO giữ 0,686 |

---

## 8. Việc tiếp theo, theo thứ tự

1. **Chạy `scripts/check_broker_swap.py`** trên MT5 của broker sẽ dùng. Đây là cổng
   đi/dừng. Nếu biên > 1,0%/năm thì phải đổi broker trước khi làm gì khác.
2. **Mở rộng mặt cắt ngang.** 7 cặp là hẹp (Menkhoff et al. dùng vũ trụ rộng hơn
   nhiều). Thêm SEK/NOK hoặc cross tổng hợp làm tăng bậc tự do của phép xếp hạng —
   đây là hướng cải thiện có cơ sở lý thuyết rõ nhất, và nó **không** làm tăng phí
   swap trên mỗi đơn vị rủi ro.
3. **Chân thứ hai không tương quan.** Olszweski & Zhou đo được lợi ích chính của đa
   dạng hoá cấp chiến lược là cắt MaxDD gần một nửa. Ứng viên còn lại: carry (MT5 có
   swap thật ở live — chính là dữ liệu `check_broker_swap.py` đọc được).
4. **Chỉ sau khi (1) cho kết quả tốt:** tầng vận hành live — quy tỷ trọng → lot qua
   `AssetProfile.value_per_pip_per_lot()`, reconciliation, giới hạn rủi ro ngày/tháng.

**Không nên** tiếp tục quét thêm biến thể của chính chiến lược này. PBO đã 0,686;
mỗi biến thể mới làm nó tệ hơn chứ không tốt lên.
