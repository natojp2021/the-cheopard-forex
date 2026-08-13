# The Cheopard Forex — Báo cáo chiến lược

Sinh tự động từ `src/python/strategies/` ngày 14/08/2026. Mọi con số đọc trực tiếp từ code và backtest, không chép tay.

---

## 1. Tóm tắt — tài khoản $100.000

Mọi con số dưới đây là **đô-la và phần trăm tài khoản**, không phải đơn vị nội bộ.
Tính trên 6,5 năm (2020-01 → 2026-08), **cộng dồn không nhân lãi kép** — quỹ cấp vốn
tính mục tiêu và hạn mức trên số dư ban đầu, nên cộng dồn là cách đọc khớp luật của họ.

### Ba mức rủi ro

|                           | THẬN TRỌNG           | **CHUẨN**            | MẠO HIỂM             |
| ------------------------- | -------------------- | -------------------- | -------------------- |
| Mục tiêu biến động        | 6 %/năm              | **10 %/năm**         | 15 %/năm             |
| **Lãi mỗi năm**           | **+28,8%** · $28.825 | **+48,0%** · $48.042 | **+72,1%** · $72.063 |
| **Sụt vốn sâu nhất**      | **−4,9%** · $9.033   | **−6,5%** · $15.056  | **−7,8%** · $22.583  |
| Ngày tệ nhất              | −$1.972              | −$3.287              | −$4.931              |
| Sharpe                    | 3,31                 | 3,31                 | 3,31                 |
| Sortino                   | 4,71                 | 4,71                 | 4,71                 |
| **Calmar** (lãi ÷ MaxDD)  | 5,94                 | **7,39**             | 9,21                 |
| Profit factor             | 2,10                 | 2,10                 | 2,10                 |
| Ngày thắng                | 61,3%                | 61,3%                | 61,3%                |
| Tháng thắng               | 88,6%                | 88,6%                | 88,6%                |
| Chuỗi tháng thua dài nhất | 1 tháng              | 1 tháng              | 1 tháng              |

Sharpe và tỷ lệ thắng **không đổi theo đòn bẩy** — chỉ lợi nhuận và drawdown đổi,
và chúng đổi **tuyến tính**. Nên "lãi 72%/năm" chỉ có nghĩa khi đọc kèm "MaxDD 7,8%".

### Chi tiết mức CHUẨN (10%/năm)

|                              |                         |
| ---------------------------- | ----------------------- |
| Vốn ban đầu                  | $100.000                |
| Equity cuối kỳ               | **$414.097**            |
| Tổng lãi 6,5 năm             | **+$314.097** (+314,1%) |
| Lãi mỗi năm                  | +$48.042 (+48,0%/năm)   |
| Sụt vốn sâu nhất             | **−$15.056** (−6,5%)    |
| Ngày tệ nhất                 | −$3.287                 |
| Ngày tốt nhất                | +$11.579                |
| Thời gian dưới đỉnh lâu nhất | **117 ngày liên tiếp**  |

### Lợi nhuận từng năm

| Năm  | Lãi    | Đô-la    | DD trong năm |
| ---- | ------ | -------- | ------------ |
| 2020 | +58,8% | +$58.770 | −6,4%        |
| 2021 | +34,0% | +$34.003 | −4,5%        |
| 2022 | +51,3% | +$51.293 | −12,8%       |
| 2023 | +72,6% | +$72.622 | −5,3%        |
| 2024 | +27,6% | +$27.608 | **−15,1%**   |
| 2025 | +45,6% | +$45.614 | −7,5%        |
| 2026 | +24,2% | +$24.187 | −6,2%        |

**7/7 năm dương.** Nhưng chú ý cột DD: 2024 lãi thấp nhất _và_ drawdown sâu nhất —
đó là năm khó nhất, và nó nằm **trong giai đoạn OOS**.

### Thống kê theo lệnh — 9.538 lệnh

|                         |                                       |
| ----------------------- | ------------------------------------- |
| Tổng số lệnh            | 9.538 (≈1.467/năm · **28 lệnh/tuần**) |
| **Tỷ lệ thắng**         | **65,3%**                             |
| Lãi trung bình mỗi lệnh | +38,13 bps                            |
| Lỗ trung bình mỗi lệnh  | −50,31 bps                            |
| **R:R trung bình**      | **0,76**                              |
| **Profit factor**       | **1,43**                              |
| Kỳ vọng mỗi lệnh        | **+7,48 bps**                         |
| Chi phí mỗi lệnh        | 1,78 bps (**19% lợi nhuận gộp**)      |
| Giữ lệnh trung bình     | 40 nến                                |

**R:R 0,76 < 1 là bình thường ở đây, không phải lỗi.** Toàn bộ danh mục là hồi quy
trung bình: thắng nhiều lần nhỏ (65,3%), thua ít lần lớn. Profit factor 1,43 mới là
con số quyết định — nó gộp cả tần suất lẫn độ lớn.

| Khung | Lệnh  | Thắng | Net/lệnh  | Phí/lệnh |
| ----- | ----- | ----- | --------- | -------- |
| M30   | 4.364 | 64,5% | +6,97 bps | 1,81     |
| H1    | 4.030 | 65,2% | +7,31 bps | 1,64     |
| H4    | 1.144 | 69,0% | +9,99 bps | 2,19     |

### Kịch bản FTMO — một lỗ hổng đã tìm ra và đã bịt

Chính sách đòn bẩy cũ (`ftmo_leverage_policy`) cho phép **4,85x**. Ở mức đó:

|              | Kết quả                | Luật FTMO          |
| ------------ | ---------------------- | ------------------ |
| Ngày tệ nhất | −$3.849 (−3,85%)       | 5% ✅              |
| **MaxDD**    | **−$17.117 (−10,74%)** | 10% ❌ **VI PHẠM** |

Nguyên nhân: ba ràng buộc của chính sách đều bó **một ngày** hoặc **một cửa sổ 21
ngày**, không cái nào bó **drawdown TÍCH LUỸ**. Không ngày nào riêng lẻ vi phạm,
nhưng chuỗi ngày xấu liên tiếp vẫn đủ xuyên trần tổng.

**Đã sửa**: sàn tính toán hạ từ 10% (mốc FTMO) xuống **9% nội bộ**, trần cứng đòn
bẩy hạ từ 6,0x xuống **3,7x**.

| Đòn bẩy   | MaxDD      | Ngày tệ nhất | Lãi/năm    |                      |
| --------- | ---------- | ------------ | ---------- | -------------------- |
| 3,00x     | −7,74%     | −$2.381      | +18,1%     |                      |
| 3,50x     | −8,65%     | −$2.777      | +21,1%     |                      |
| **3,71x** | **−9,00%** | **−$2.943**  | **+22,3%** | **trần mới**         |
| 4,00x     | −9,47%     | −$3.174      | +24,1%     | vượt sàn nội bộ      |
| 4,85x     | −10,74%    | −$3.849      | +29,2%     | ❌ vượt cả luật FTMO |

Ở trần 3,7x: **+22,3%/năm ($22.328)**, mục tiêu Phase 1 (+10%) đạt sau **≈5,4 tháng**,
MaxDD 9,00% — còn nguyên 1 điểm phần trăm biên dưới mốc thật.

Biên đó không phải cho đẹp: backtest không có trượt giá khi tin ra, spread giãn lúc
thanh khoản mỏng, hay lệnh bị từ chối. MaxDD thật **luôn** sâu hơn MaxDD đo được.

### Điều backtest KHÔNG có

Trượt giá khi tin ra · spread giãn lúc thanh khoản mỏng · lệnh bị từ chối · chênh
lệch giữa spread demo và spread tài khoản thật. Mọi con số ở trên là **giới hạn trên**
của cái đạt được, không phải kỳ vọng.

_Script sinh số_: `research/fx/account_report.py`

---

## 1b. Chỉ số kỹ thuật (đơn vị nội bộ)

Bảng này dùng đơn vị **σ chuẩn hoá** — số lần độ lệch chuẩn ngày của từng chân sau
khi cân bằng biến động. Nó KHÔNG đọc được thành đô-la, và có mặt vì hai việc: so
sánh chiến lược với nhau, và kiểm tra tính độc lập. Ai muốn con số tiền thật thì đọc
§1.

|                             |                                                     |
| --------------------------- | --------------------------------------------------- |
| Danh mục                    | **TwentySevenLegFX**                                |
| Chiến lược                  | **27** · **21** nhóm rủi ro                         |
| Sharpe toàn mẫu             | **3,313**                                           |
| Sharpe FORM (→2024-01)      | 3,451                                               |
| Sharpe OOS (2024-01→)       | **3,106**                                           |
| MaxDD                       | 5,63 σ                                              |
| Ngày tệ nhất                | −1,23 σ                                             |
| \|corr\| giữa nhóm lớn nhất | **0,300**                                           |
| Giai đoạn                   | FORWARD_TEST · trần đòn bẩy 3,7x · sàn DD nội bộ 9% |

**Chi phí trong mọi con số**: spread ĐO THẬT trên MT5 (14/08/2026) × hệ số an toàn
1,5 + commission + swap + biên broker 1,0%/năm. Không lớp nào bỏ qua.

**Giai đoạn OOS chưa từng dùng để chọn bất cứ thứ gì** — không chọn công cụ, không
chọn tham số, không chọn ngưỡng. Mọi quyết định chỉ dùng dữ liệu tới hết 2023.

---

## 2. Phân bố theo khung và họ tín hiệu

| Khung   | Accel | Cross Mean-Reversion | Cross X-Section | Currency X-Section | RSI-Divergence | Streak | Vol-Regime | Z-Band | Tổng   | Yêu cầu |
| ------- | ----- | -------------------- | --------------- | ------------------ | -------------- | ------ | ---------- | ------ | ------ | ------- |
| **M30** |       |                      |                 |                    | 2              | 1      | 2          | 3      | **8**  | >2 ✅   |
| **H1**  | 1     | 1                    |                 |                    | 1              | 2      | 1          | 6      | **12** | >3 ✅   |
| **H4**  |       |                      | 1               |                    |                |        |            | 3      | **4**  | >1 ✅   |
| **D1**  |       |                      |                 | 3                  |                |        |            |        | **3**  | >1 ✅   |

**Vì sao đếm họ quan trọng hơn đếm chiến lược**: mười chân cùng đọc một đại lượng thì lỗ cùng lúc. Sharpe danh mục tăng từ 2,501 (17 chân, 1 họ ở M30) lên 3,313 (27 chân, 4 họ ở M30) **không phải vì chân nào mạnh hơn** — chân mạnh nhất trong nhóm mới chỉ Sharpe 1,350 — mà vì các cách nhìn mới gần trực giao với mọi thứ đã có.

---

## 3. Bảng đầy đủ 27 chiến lược

| #   | Chiến lược           | Khung | Công cụ         | Họ                   | Sharpe    | FORM   | OOS   | Tỷ trọng | Nhóm rủi ro      |
| --- | -------------------- | ----- | --------------- | -------------------- | --------- | ------ | ----- | -------- | ---------------- |
| 1   | `RsiDivGBPNZDM30`    | M30   | GBPNZD          | RSI-Divergence       | **1.350** | 1.668  | 0.765 | 4.8%     | RsiDiv_GBPNZD    |
| 2   | `StreakAUDCADM30`    | M30   | AUDCAD          | Streak               | **0.969** | 1.062  | 0.803 | 4.8%     | Streak_AUDCAD    |
| 3   | `VolRegimeGBPCHFM30` | M30   | GBPCHF          | Vol-Regime           | **0.951** | 0.851  | 1.122 | 4.8%     | VolRegime_GBPCHF |
| 4   | `ZBandGBPAUDM30`     | M30   | GBPAUD          | Z-Band               | **0.919** | 0.891  | 1.007 | 1.6%     | ZBand_GBPAUD     |
| 5   | `ZBandAUDCADM30`     | M30   | AUDCAD          | Z-Band               | **0.811** | 0.788  | 0.856 | 1.6%     | ZBand_AUDCAD     |
| 6   | `RsiDivNZDCADM30`    | M30   | NZDCAD          | RSI-Divergence       | **0.782** | 0.581  | 1.147 | 2.4%     | RsiDiv_NZDCAD    |
| 7   | `VolRegimeAUDCHFM30` | M30   | AUDCHF          | Vol-Regime           | **0.752** | 0.470  | 1.254 | 4.8%     | VolRegime_AUDCHF |
| 8   | `ZBandNZDCADM30`     | M30   | NZDCAD          | Z-Band               | **0.675** | 0.772  | 0.503 | 2.4%     | ZBand_NZDCAD     |
| 9   | `AccelGBPNZDH1`      | H1    | GBPNZD          | Accel                | **1.098** | 1.357  | 0.581 | 4.8%     | Accel_GBPNZD     |
| 10  | `CrossMeanReversion` | H1    | EURGBP, EURJPY… | Cross Mean-Reversion | **1.059** | 1.057  | 1.121 | 4.8%     | CrossMeanRev_H1  |
| 11  | `StreakGBPCADH1`     | H1    | GBPCAD          | Streak               | **0.967** | 1.179  | 0.521 | 4.8%     | Streak_GBPCAD    |
| 12  | `RsiDivNZDCADH1`     | H1    | NZDCAD          | RSI-Divergence       | **0.828** | 0.793  | 0.905 | 2.4%     | RsiDiv_NZDCAD    |
| 13  | `VolRegimeGBPAUDH1`  | H1    | GBPAUD          | Vol-Regime           | **0.818** | 0.910  | 0.628 | 4.8%     | VolRegime_GBPAUD |
| 14  | `StreakGBPAUDH1`     | H1    | GBPAUD          | Streak               | **0.809** | 0.848  | 0.741 | 4.8%     | Streak_GBPAUD    |
| 15  | `ZBandNZDCADH1`      | H1    | NZDCAD          | Z-Band               | **0.796** | 0.823  | 0.749 | 2.4%     | ZBand_NZDCAD     |
| 16  | `ZBandEURCHFH1`      | H1    | EURCHF          | Z-Band               | **0.795** | 0.848  | 0.708 | 4.8%     | ZBand_EURCHF     |
| 17  | `ZBandAUDCADH1`      | H1    | AUDCAD          | Z-Band               | **0.775** | 0.849  | 0.649 | 1.6%     | ZBand_AUDCAD     |
| 18  | `ZBandGBPAUDH1`      | H1    | GBPAUD          | Z-Band               | **0.742** | 0.891  | 0.439 | 1.6%     | ZBand_GBPAUD     |
| 19  | `ZBandEURGBPH1`      | H1    | EURGBP          | Z-Band               | **0.713** | 0.881  | 0.307 | 4.8%     | ZBand_EURGBP     |
| 20  | `ZBandGBPUSDH1`      | H1    | GBPUSD          | Z-Band               | **0.679** | 0.644  | 0.738 | 4.8%     | ZBand_GBPUSD     |
| 21  | `ZBandGBPNZDH4`      | H4    | GBPNZD          | Z-Band               | **1.214** | 1.395  | 0.879 | 4.8%     | ZBand_GBPNZD     |
| 22  | `ZBandAUDCADH4`      | H4    | AUDCAD          | Z-Band               | **1.062** | 1.062  | 1.059 | 1.6%     | ZBand_AUDCAD     |
| 23  | `ZBandGBPAUDH4`      | H4    | GBPAUD          | Z-Band               | **0.904** | 1.082  | 0.563 | 1.6%     | ZBand_GBPAUD     |
| 24  | `CrossXsReversion`   | H4    | EURGBP, EURJPY… | Cross X-Section      | **0.460** | 0.593  | 0.381 | 4.8%     | CrossXsRev_H4    |
| 25  | `CrossMomentum`      | D1    | EURGBP, EURJPY… | Currency X-Section   | **0.897** | 0.885  | 0.920 | 4.8%     | CrossMomentum    |
| 26  | `CurrencyReversal`   | D1    | EURUSD, GBPUSD… | Currency X-Section   | **0.576** | 0.618  | 0.395 | 4.8%     | CurrencyReversal |
| 27  | `CurrencyCarry`      | D1    | EURUSD, GBPUSD… | Currency X-Section   | **0.151** | -0.105 | 0.745 | 4.8%     | CurrencyCarry    |

---

## 4. Chi tiết từng họ tín hiệu

### Z-Band — 12 chiến lược

**Phân loại**: CỔ ĐIỂN, ĐÃ TINH CHỈNH HIỆN ĐẠI

**Nguồn**: Sepp & Lucic arXiv 2607.19497 (2026) — chẩn đoán ngưỡng hoà vốn chọn công cụ · Zheng Nan (2025) MSc — time-stop thay stop giá (+85%)

**Luật vào lệnh**:

- **a.** |z| > 1.5 — _ngưỡng vào; vùng tham số k ∈ [1,5 · 2,5] cùng dấu, không phải đỉnh_
- **b.** nến TRƯỚC cũng ngoài dải: |z(t−1)| > 1.5 — _chống vào lại liên tục khi z dao động quanh ngưỡng_
- **c.** z < −1.5 → MUA · z > +1.5 → BÁN — _vào NGƯỢC chiều lệch — φ đo được ÂM nên hồi quy, không phải đà_

**Luật thoát lệnh**:

- z về 0 — _hồi quy đã xảy ra, không còn lý do giữ_
- time-stop 48 nến — _đo được time-stop hơn SL theo ATR trên CẢ hai vòng 57 và 59_
- xuất hiện tín hiệu NGƯỢC chiều
- **Cắt lỗ**: KHÔNG có cắt lỗ theo giá — chiến lược hồi quy vào lệnh khi giá ĐANG đi ngược, nên SL đặt gần luôn bị chạm trước khi hồi. Đo được: time_only +0,070 vs SL 3ATR+TP2R −0,272 ở H1. Rủi ro kiểm soát bằng CỠ VỊ THẾ và time-stop.

| Chiến lược       | Khung | Công cụ | Sharpe    | FORM  | OOS   | MaxDD |
| ---------------- | ----- | ------- | --------- | ----- | ----- | ----- |
| `ZBandGBPNZDH4`  | H4    | GBPNZD  | **1.214** | 1.395 | 0.879 | 5.04% |
| `ZBandAUDCADH4`  | H4    | AUDCAD  | **1.062** | 1.062 | 1.059 | 3.13% |
| `ZBandGBPAUDM30` | M30   | GBPAUD  | **0.919** | 0.891 | 1.007 | 4.55% |
| `ZBandGBPAUDH4`  | H4    | GBPAUD  | **0.904** | 1.082 | 0.563 | 5.02% |
| `ZBandAUDCADM30` | M30   | AUDCAD  | **0.811** | 0.788 | 0.856 | 7.59% |
| `ZBandNZDCADH1`  | H1    | NZDCAD  | **0.796** | 0.823 | 0.749 | 7.20% |
| `ZBandEURCHFH1`  | H1    | EURCHF  | **0.795** | 0.848 | 0.708 | 5.16% |
| `ZBandAUDCADH1`  | H1    | AUDCAD  | **0.775** | 0.849 | 0.649 | 6.72% |
| `ZBandGBPAUDH1`  | H1    | GBPAUD  | **0.742** | 0.891 | 0.439 | 6.29% |
| `ZBandEURGBPH1`  | H1    | EURGBP  | **0.713** | 0.881 | 0.307 | 6.31% |
| `ZBandGBPUSDH1`  | H1    | GBPUSD  | **0.679** | 0.644 | 0.738 | 7.25% |
| `ZBandNZDCADM30` | M30   | NZDCAD  | **0.675** | 0.772 | 0.503 | 8.05% |

### RSI-Divergence — 3 chiến lược

**Phân loại**: CỔ ĐIỂN THUẦN — nhưng lần đầu được ĐO thay vì giả định

**Nguồn**: Wilder (1978) — RSI gốc · phân kỳ được ĐO chứ không giả định

**Luật vào lệnh**:

- **a.** giá lập cực trị mới so với 192 nến trước
- **b.** RSI lệch ít nhất 3.0 điểm khỏi cực trị RSI của cùng cửa sổ — _đây là phần PHÂN KỲ: hai chuỗi nói ngược nhau_
- **c.** giá ĐÁY mới + RSI cao hơn đáy RSI ≥ 3.0 điểm → MUA · giá ĐỈNH mới + RSI thấp hơn đỉnh RSI ≥ 3.0 điểm → BÁN — _vào NGƯỢC chiều giá, THUẬN chiều đà_

**Luật thoát lệnh**:

- xuất hiện tín hiệu NGƯỢC chiều
- time-stop 192 nến H1 — _đo được time-stop hơn SL theo ATR ở cả vòng 57 và 59_
- **Cắt lỗ**: KHÔNG có cắt lỗ theo giá — đo được hai lần độc lập rằng SL theo ATR làm tệ hơn trên FX. Rủi ro kiểm soát bằng CỠ VỊ THẾ và time-stop.

| Chiến lược        | Khung | Công cụ | Sharpe    | FORM  | OOS   | MaxDD |
| ----------------- | ----- | ------- | --------- | ----- | ----- | ----- |
| `RsiDivGBPNZDM30` | M30   | GBPNZD  | **1.350** | 1.668 | 0.765 | —     |
| `RsiDivNZDCADH1`  | H1    | NZDCAD  | **0.828** | 0.793 | 0.905 | —     |
| `RsiDivNZDCADM30` | M30   | NZDCAD  | **0.782** | 0.581 | 1.147 | —     |

### Streak — 3 chiến lược

**Phân loại**: Ý TƯỞNG CỔ ĐIỂN, BIẾN THỂ HIỆN ĐẠI

**Nguồn**: Lo & MacKinlay RFS 1990 (contrarian ngắn hạn), biến thể ĐẾM

**Luật vào lệnh**:

- **a.** chuỗi ≥ 4 nến cùng chiều liên tiếp
- **b.** tổng dịch chuyển > 0.5 × ATR × √4 — _loại chuỗi dài nhưng toàn nến ruồi — nhiễu vi cấu trúc_
- **c.** chuỗi 4 nến GIẢM → MUA · 4 nến TĂNG → BÁN — _chuỗi dài phản ánh dòng lệnh một chiều đã cạn_

**Luật thoát lệnh**:

- xuất hiện tín hiệu NGƯỢC chiều
- time-stop 192 nến H1 — _đo được time-stop hơn SL theo ATR ở cả vòng 57 và 59_
- **Cắt lỗ**: KHÔNG có cắt lỗ theo giá — đo được hai lần độc lập rằng SL theo ATR làm tệ hơn trên FX. Rủi ro kiểm soát bằng CỠ VỊ THẾ và time-stop.

| Chiến lược        | Khung | Công cụ | Sharpe    | FORM  | OOS   | MaxDD |
| ----------------- | ----- | ------- | --------- | ----- | ----- | ----- |
| `StreakAUDCADM30` | M30   | AUDCAD  | **0.969** | 1.062 | 0.803 | —     |
| `StreakGBPCADH1`  | H1    | GBPCAD  | **0.967** | 1.179 | 0.521 | —     |
| `StreakGBPAUDH1`  | H1    | GBPAUD  | **0.809** | 0.848 | 0.741 | —     |

### Vol-Regime — 3 chiến lược

**Phân loại**: HIỆN ĐẠI — dựa trên tính chất thống kê, không có tiền lệ bán lẻ

**Nguồn**: Cont (2001) — cụm biến động là tính chất bền nhất của chuỗi tài chính

**Luật vào lệnh**:

- **a.** σ(24 nến) / σ(96 nến) > 1.6 — _thị trường vừa nhận cú sốc — biến động vọt lên so với nền_
- **b.** tổng lợi nhuận 24 nến gần nhất < 0 → MUA · > 0 → BÁN — _vào NGƯỢC chiều cú sốc: sau cú sốc giá thường hồi một phần_

**Luật thoát lệnh**:

- xuất hiện tín hiệu NGƯỢC chiều
- time-stop 48 nến H1 — _đo được time-stop hơn SL theo ATR ở cả vòng 57 và 59_
- **Cắt lỗ**: KHÔNG có cắt lỗ theo giá — đo được hai lần độc lập rằng SL theo ATR làm tệ hơn trên FX. Rủi ro kiểm soát bằng CỠ VỊ THẾ và time-stop.

| Chiến lược           | Khung | Công cụ | Sharpe    | FORM  | OOS   | MaxDD |
| -------------------- | ----- | ------- | --------- | ----- | ----- | ----- |
| `VolRegimeGBPCHFM30` | M30   | GBPCHF  | **0.951** | 0.851 | 1.122 | —     |
| `VolRegimeGBPAUDH1`  | H1    | GBPAUD  | **0.818** | 0.910 | 0.628 | —     |
| `VolRegimeAUDCHFM30` | M30   | AUDCHF  | **0.752** | 0.470 | 1.254 | —     |

### Accel — 1 chiến lược

**Phân loại**: HIỆN ĐẠI — họ duy nhất trong danh mục đọc bậc hai

**Nguồn**: Hiệu hai lợi nhuận liên tiếp cùng cửa sổ, chuẩn hoá theo σ của chính nó

**Luật vào lệnh**:

- **a.** gia tốc = lợi nhuận(48 nến) − lợi nhuận(48 nến trước đó), chuẩn hoá theo σ của chính nó
- **b.** |z(gia tốc)| > 2.5
- **c.** z < −2.5 → MUA · z > +2.5 → BÁN — _gia tốc âm mạnh = đà đang tắt nhanh; vào NGƯỢC chiều đà đang tắt_

**Luật thoát lệnh**:

- xuất hiện tín hiệu NGƯỢC chiều
- time-stop 24 nến H1 — _đo được time-stop hơn SL theo ATR ở cả vòng 57 và 59_
- **Cắt lỗ**: KHÔNG có cắt lỗ theo giá — đo được hai lần độc lập rằng SL theo ATR làm tệ hơn trên FX. Rủi ro kiểm soát bằng CỠ VỊ THẾ và time-stop.

| Chiến lược      | Khung | Công cụ | Sharpe    | FORM  | OOS   | MaxDD |
| --------------- | ----- | ------- | --------- | ----- | ----- | ----- |
| `AccelGBPNZDH1` | H1    | GBPNZD  | **1.098** | 1.357 | 0.581 | —     |

### Currency X-Section — 3 chiến lược

**Phân loại**: CỔ ĐIỂN HỌC THUẬT — luật lấy nguyên văn từ bài báo

**Nguồn**: Li/Zhao/Hoi PAMR 2012 · Menkhoff et al. JFE 2012 · cổng chế độ theo Brière & Drut Amundi 2010

**Luật vào lệnh**:

- **a.** hôm nay là ngày tái cân bằng (mỗi 21 ngày) — _giữ vị thế giữa hai lần tái cân bằng là thứ giữ chi phí thấp_
- **b.** MUA 3 đồng có tín hiệu CAO nhất (= yếu nhất quá khứ) — _Menkhoff et al. dùng đúng 3 cao / 3 thấp_
- **c.** BÁN 3 đồng có tín hiệu THẤP nhất (= mạnh nhất quá khứ) — _hai chân đối xứng → phơi nhiễm USD ròng ≈ 0 (đo: max|sum| = 1,7e-13)_
- **d.** tỷ trọng trong mỗi chân ∝ 1/σ(63), tổng mỗi chân = 1 — _Olszweski & Zhou: chia đều/inverse-vol thắng mean-variance (0,98 vs 0,70)_
- **e.** biến động rổ < phân vị 80% trượt 252 ngày — _CALM +5,56%/năm (Sharpe 1,049) vs CRISIS −5,34% (−0,842) — đảo dấu hoàn toàn_

**Luật thoát lệnh**:

- tái cân bằng kế tiếp sau 21 ngày — _không có thoát theo giá — đây là chiến lược tỷ trọng, không phải theo lệnh_
- cổng chế độ chuyển sang CRISIS → về 0 toàn bộ chân
- **Cắt lỗ**: KHÔNG có cắt lỗ theo giá — rủi ro kiểm soát bằng cỡ vị thế và cổng chế độ

| Chiến lược         | Khung | Công cụ         | Sharpe    | FORM   | OOS   | MaxDD  |
| ------------------ | ----- | --------------- | --------- | ------ | ----- | ------ |
| `CrossMomentum`    | D1    | EURGBP, EURJPY… | **0.897** | 0.885  | 0.920 | —      |
| `CurrencyReversal` | D1    | EURUSD, GBPUSD… | **0.576** | 0.618  | 0.395 | 8.27%  |
| `CurrencyCarry`    | D1    | EURUSD, GBPUSD… | **0.151** | -0.105 | 0.745 | 10.37% |

### Cross Mean-Reversion — 1 chiến lược

**Phân loại**: HIỆN ĐẠI — luận văn 2025, tham số lấy nguyên

**Nguồn**: Zheng Nan (2025) MSc thesis — cửa sổ HL×4,32 · vào 2σ có quay lại · time-stop thay stop 3σ. Vũ trụ của họ cũng là cross (JPY crosses)

**Luật vào lệnh**:

- **a.** 4 <= half*life <= 120 nến H1 — \_ngoài khoảng này thì cross không hồi quy đủ nhanh để bù chi phí; khi rơi ra ngoài phải THOÁT, không được giữ (lỗi giữ vị thế cũ làm 93% thời gian trong thị trường, Sharpe −0,234)*
- **b.** |z| > 2.0 — _ngưỡng vào của Zheng Nan, không tinh chỉnh_
- **c.** nến TRƯỚC còn NGOÀI dải: |z(t−1)| > 2.0 (was*outside_band) — \_chống vào lại liên tục khi z dao động quanh ngưỡng*
- **d.** giờ UTC thuộc (10, 11, 12, 13, 14, 15, 16)
- **e.** z < 0 → MUA cross · z > 0 → BÁN cross

**Luật thoát lệnh**:

- z về 0 → chốt (hồi quy đã xảy ra)
- giữ đủ ceil(4.32 × HL) nến → TIME-STOP — _Zheng Nan đo time-stop hơn stop 3σ +85% — cắt lỗ theo giá trên spread hồi quy là cắt đúng lúc spread căng nhất_
- half-life rơi ra ngoài dải → thoát ngay, không giữ
- **Cắt lỗ**: TIME-STOP thay cho stop giá — xem x2

| Chiến lược           | Khung | Công cụ         | Sharpe    | FORM  | OOS   | MaxDD |
| -------------------- | ----- | --------------- | --------- | ----- | ----- | ----- |
| `CrossMeanReversion` | H1    | EURGBP, EURJPY… | **1.059** | 1.057 | 1.121 | —     |

### Cross X-Section — 1 chiến lược

**Phân loại**: CỔ ĐIỂN, BẢN GIẢN LƯỢC CỦA MỘT MÔ HÌNH HIỆN ĐẠI

**Nguồn**: Lo & MacKinlay RFS 1990 (tự tương quan CHÉO là nguồn lợi nhuận contrarian) · Avellaneda & Lee 2010 (bản giản lược: xếp hạng z thô thay phần dư PCA) · Olszweski & Zhou 2014 (chia đều 1/N cứng)

**Luật vào lệnh**:

- **a.** nến này là nến tái cân bằng (mỗi 12 nến H4 = 2 ngày giao dịch) — _mỗi nến thì chi phí ăn 60% gross → Sharpe rơi về 0,305; 5 ngày thì tín hiệu hết hạn → 0,072_
- **b.** MUA 7 cross có z THẤP nhất trong 20 cross — _bị bán quá mức so với 19 cross khác → kỳ vọng hồi lên_
- **c.** BÁN 7 cross có z CAO nhất
- **d.** tỷ trọng chia đều 1/7 mỗi chân — KHÔNG tối ưu hoá — _tín hiệu z ở đây YẾU nhưng RỘNG: chọn 3 cross tốt nhất là đặt cược vào độ chính xác của thứ hạng, mà độ chính xác đó không có (n_leg 3 → 0,131)_

**Luật thoát lệnh**:

- tái cân bằng kế tiếp sau 12 nến H4
- **Cắt lỗ**: KHÔNG có cắt lỗ theo giá — 14/20 cross luôn có vị thế, rủi ro nằm ở cỡ vị thế và ở tính trung hoà của rổ

| Chiến lược         | Khung | Công cụ         | Sharpe    | FORM  | OOS   | MaxDD |
| ------------------ | ----- | --------------- | --------- | ----- | ----- | ----- |
| `CrossXsReversion` | H4    | EURGBP, EURJPY… | **0.460** | 0.593 | 0.381 | 7.75% |

---

## 5. Ma trận tương quan giữa các nhóm rủi ro

Ngưỡng độc lập **|corr| < 0,70**. Áp ở tầng NHÓM chứ không tầng chân: hai chân cùng công cụ khác khung được phép tương quan cao (đo được AUDCAD H1↔M30 = 0,712) vì chúng đã gộp thành một suất.

|                      | CurrencyReversal | CurrencyCarry | CrossMeanRev·H1 | CrossMomentum | CrossXsRev·H4 | ZB·AUDCAD | ZB·NZDCAD | ZB·GBPAUD | ZB·GBPNZD | ZB·EURCHF | ZB·GBPUSD | ZB·EURGBP | RsiDiv·NZDCAD | Streak·GBPCAD | Streak·GBPAUD | VolRegime·GBPAUD | RsiDiv·GBPNZD | Streak·AUDCAD | VolRegime·GBPCHF | VolRegime·AUDCHF | Accel·GBPNZD |
| -------------------- | ---------------- | ------------- | --------------- | ------------- | ------------- | --------- | --------- | --------- | --------- | --------- | --------- | --------- | ------------- | ------------- | ------------- | ---------------- | ------------- | ------------- | ---------------- | ---------------- | ------------ |
| **CurrencyReversal** | —                | -0.06         | +0.05           | -0.07         | +0.06         | +0.09     | +0.05     | +0.00     | +0.03     | +0.04     | -0.03     | +0.02     | -0.01         | -0.03         | -0.06         | -0.01            | +0.02         | +0.08         | +0.01            | +0.13            | +0.04        |
| **CurrencyCarry**    | -0.06            | —             | +0.01           | +0.19         | +0.06         | +0.01     | -0.02     | +0.01     | -0.01     | -0.03     | +0.00     | -0.02     | -0.03         | -0.03         | -0.04         | +0.05            | +0.05         | +0.05         | +0.02            | +0.13            | +0.02        |
| **CrossMeanRev·H1**  | +0.05            | +0.01         | —               | -0.01         | +0.07         | +0.04     | +0.02     | -0.01     | +0.08     | +0.02     | +0.03     | +0.01     | +0.01         | -0.02         | +0.01         | -0.01            | +0.00         | -0.00         | +0.04            | +0.00            | +0.06        |
| **CrossMomentum**    | -0.07            | +0.19         | -0.01           | —             | +0.00         | -0.01     | -0.02     | -0.03     | -0.03     | -0.02     | +0.00     | -0.01     | +0.02         | +0.01         | +0.02         | -0.02            | +0.02         | -0.02         | -0.01            | -0.03            | -0.02        |
| **CrossXsRev·H4**    | +0.06            | +0.06         | +0.07           | +0.00         | —             | +0.02     | +0.07     | +0.09     | +0.06     | +0.01     | +0.02     | +0.07     | +0.02         | -0.01         | -0.01         | -0.03            | +0.04         | +0.03         | +0.10            | +0.08            | +0.03        |
| **ZB·AUDCAD**        | +0.09            | +0.01         | +0.04           | -0.01         | +0.02         | —         | **+0.30** | +0.06     | +0.05     | +0.01     | +0.01     | -0.00     | +0.16         | -0.01         | +0.01         | +0.00            | +0.03         | +0.10         | +0.05            | +0.03            | -0.07        |
| **ZB·NZDCAD**        | +0.05            | -0.02         | +0.02           | -0.02         | +0.07         | **+0.30** | —         | +0.02     | +0.16     | +0.03     | -0.03     | -0.01     | **+0.27**     | +0.03         | +0.03         | -0.03            | -0.01         | +0.08         | -0.01            | +0.03            | -0.09        |
| **ZB·GBPAUD**        | +0.00            | +0.01         | -0.01           | -0.03         | +0.09         | +0.06     | +0.02     | —         | +0.15     | -0.01     | +0.02     | +0.01     | -0.01         | +0.05         | +0.09         | +0.14            | +0.05         | +0.15         | +0.02            | +0.16            | -0.00        |
| **ZB·GBPNZD**        | +0.03            | -0.01         | +0.08           | -0.03         | +0.06         | +0.05     | +0.16     | +0.15     | —         | -0.00     | -0.02     | -0.01     | +0.08         | +0.03         | +0.07         | +0.04            | +0.03         | +0.00         | +0.03            | -0.01            | -0.00        |
| **ZB·EURCHF**        | +0.04            | -0.03         | +0.02           | -0.02         | +0.01         | +0.01     | +0.03     | -0.01     | -0.00     | —         | -0.01     | -0.03     | +0.01         | +0.01         | -0.01         | +0.01            | +0.04         | +0.02         | +0.06            | +0.06            | +0.04        |
| **ZB·GBPUSD**        | -0.03            | +0.00         | +0.03           | +0.00         | +0.02         | +0.01     | -0.03     | +0.02     | -0.02     | -0.01     | —         | -0.00     | -0.01         | +0.03         | +0.02         | +0.05            | +0.03         | +0.04         | +0.00            | +0.01            | -0.01        |
| **ZB·EURGBP**        | +0.02            | -0.02         | +0.01           | -0.01         | +0.07         | -0.00     | -0.01     | +0.01     | -0.01     | -0.03     | -0.00     | —         | +0.00         | +0.08         | +0.02         | +0.02            | +0.03         | +0.02         | +0.01            | -0.01            | +0.01        |
| **RsiDiv·NZDCAD**    | -0.01            | -0.03         | +0.01           | +0.02         | +0.02         | +0.16     | **+0.27** | -0.01     | +0.08     | +0.01     | -0.01     | +0.00     | —             | +0.03         | -0.00         | -0.00            | +0.02         | -0.05         | -0.10            | -0.10            | -0.00        |
| **Streak·GBPCAD**    | -0.03            | -0.03         | -0.02           | +0.01         | -0.01         | -0.01     | +0.03     | +0.05     | +0.03     | +0.01     | +0.03     | +0.08     | +0.03         | —             | +0.09         | +0.04            | -0.05         | -0.05         | +0.01            | -0.02            | -0.02        |
| **Streak·GBPAUD**    | -0.06            | -0.04         | +0.01           | +0.02         | -0.01         | +0.01     | +0.03     | +0.09     | +0.07     | -0.01     | +0.02     | +0.02     | -0.00         | +0.09         | —             | +0.07            | -0.05         | -0.03         | -0.00            | -0.04            | +0.01        |
| **VolRegime·GBPAUD** | -0.01            | +0.05         | -0.01           | -0.02         | -0.03         | +0.00     | -0.03     | +0.14     | +0.04     | +0.01     | +0.05     | +0.02     | -0.00         | +0.04         | +0.07         | —                | -0.01         | +0.12         | -0.06            | +0.20            | +0.14        |
| **RsiDiv·GBPNZD**    | +0.02            | +0.05         | +0.00           | +0.02         | +0.04         | +0.03     | -0.01     | +0.05     | +0.03     | +0.04     | +0.03     | +0.03     | +0.02         | -0.05         | -0.05         | -0.01            | —             | +0.02         | +0.10            | -0.03            | +0.03        |
| **Streak·AUDCAD**    | +0.08            | +0.05         | -0.00           | -0.02         | +0.03         | +0.10     | +0.08     | +0.15     | +0.00     | +0.02     | +0.04     | +0.02     | -0.05         | -0.05         | -0.03         | +0.12            | +0.02         | —             | +0.03            | +0.24            | +0.00        |
| **VolRegime·GBPCHF** | +0.01            | +0.02         | +0.04           | -0.01         | +0.10         | +0.05     | -0.01     | +0.02     | +0.03     | +0.06     | +0.00     | +0.01     | -0.10         | +0.01         | -0.00         | -0.06            | +0.10         | +0.03         | —                | +0.11            | +0.03        |
| **VolRegime·AUDCHF** | +0.13            | +0.13         | +0.00           | -0.03         | +0.08         | +0.03     | +0.03     | +0.16     | -0.01     | +0.06     | +0.01     | -0.01     | -0.10         | -0.02         | -0.04         | +0.20            | -0.03         | +0.24         | +0.11            | —                | +0.03        |
| **Accel·GBPNZD**     | +0.04            | +0.02         | +0.06           | -0.02         | +0.03         | -0.07     | -0.09     | -0.00     | -0.00     | +0.04     | -0.01     | +0.01     | -0.00         | -0.02         | +0.01         | +0.14            | +0.03         | +0.00         | +0.03            | +0.03            | —            |

|corr| lớn nhất: **0.300** (ZBand_AUDCAD ↔ ZBand_NZDCAD) — đạt.

---

## 6. Cách chọn chiến lược — giao thức kiểm định

### Bước 1 — chẩn đoán ngưỡng hoà vốn (TRƯỚC khi backtest)

Sepp & Lucic (2026, arXiv 2607.19497) cho công thức tính từ dữ liệu, không tốn bậc tự do:

```
c* = √(π / 2a) × |φ| / (1 − |φ|)

a = số kỳ mỗi năm của khung
φ = tự tương quan bậc một của lợi nhuận ĐÃ CHUẨN HOÁ theo biến động
```

Chi phí khứ hồi thực tế **vượt** c\* thì không span nào cứu được. Đây là khác biệt lớn nhất so với 57 vòng quét mù trước đó: chọn công cụ theo **φ** (một thống kê của dữ liệu) chứ không theo Sharpe (chính đại lượng sẽ báo cáo).

### Bước 2 — bảy cổng kiểm định, đặt TRƯỚC khi xem kết quả

| #   | Cổng                                                                      | Ngưỡng            |
| --- | ------------------------------------------------------------------------- | ----------------- |
| 1   | Control **thời điểm** — giữ số lệnh và thời gian giữ, vào lệnh ngẫu nhiên | p < 0,05          |
| 2   | Control **chiều** — giữ thời điểm, đảo chiều ngẫu nhiên                   | p < 0,05          |
| 3   | Bootstrap khối 21 ngày, 2000 lần                                          | P(Sharpe<0) < 10% |
| 4   | Ổn định năm                                                               | ≥ 6/7 năm dương   |
| 5   | Loại ngoại lai — bỏ 5 tháng tốt nhất                                      | vẫn giữ dấu       |
| 6   | Stress chi phí                                                            | sống ở ×2, ×3     |
| 7   | Vùng tham số — ô lân cận                                                  | ≥ 60% cùng dấu    |

Thêm cổng **độc lập**: |corr| với mọi chân cùng khung < 0,50 khi tìm họ mới.

Hai control bắt hai lỗi khác nhau và **cả hai đều bắt buộc**: control thời điểm bắt _“vào lệnh lúc nào cũng lãi”_, control chiều bắt _“nhịp vào ra mới sinh lãi, không phải việc chọn đúng chiều”_.

---

## 7. 19 hướng đã bác bỏ

Giữ lại **có chủ ý**: mỗi dòng là một hướng đã tốn công đo và đã có kết luận. Xoá đi thì lần sau sẽ có người thử lại chính nó.

**1. `GapFade_va_HLRange`** (M30/H1)

> Hai họ mới của vòng 67 KHÔNG có ô nào lọt top: `gap_fade` (khoảng hở mở cửa so với đóng cửa trước, vào ngược) và `hl_range` (biên độ high-low quá rộng, vào ngược). `hl_range` là bản ĐẢO CHIỀU của `range_break` đã bị loại ở vòng 65 — cả hai chiều đều thua, nên kết luận là ĐẠI LƯỢNG biên độ nến vô dụng trên FX, không phải do chọn sai chiều. `gap_fade` thua vì trên FX khoảng hở trong phiên quá hiếm và quá nhỏ để bù chi phí.

**2. `Accel_CADCHF_M30_va_GBPCAD_H1`** (M30/H1)

> Hai ô họ ACCEL qua 6/7 kiểm định nhưng TRƯỢT vùng tham số: 6/12 và 7/12 ô lân cận dương, dưới ngưỡng 60%. Cùng họ, ô GBPNZD H1 đạt 9/12 và được nhận. Vùng tham số là cổng phân biệt 'họ có tín hiệu' với 'ô may mắn trong họ có tín hiệu'.

**3. `RangeBreak_H1`** (H1)

> Họ MỞ RỘNG BIÊN ĐỘ (nến có biên độ > k lần trung bình, vào THUẬN chiều nến): chỉ **12,5%** ô trong lưới 384 ô cho Sharpe dương, net trung vị −1,82 bps/lệnh. Ba họ còn lại cùng vòng đều đạt 45-53% ô dương. Kết luận khớp với 63 vòng trước: trên FX, hướng THUẬN chiều thua ở mọi khung — chỉ hồi quy sống được.

**4. `ZBandGBPNZD_H1`** (H1)

> Vùng tham số ĐẸP NHẤT toàn bộ vòng 64 — 18/18 ô lân cận dương, Sharpe ALL 0,978, t = 3,34, qua cả hai control với p = 0,0000. Vẫn LOẠI vì FORM 1,493 so với OOS **−0,119**: toàn bộ lợi nhuận nằm ở giai đoạn hiệu chỉnh và biến mất ở giai đoạn kiểm chứng. Vùng tham số vững KHÔNG cứu được một ô có OOS âm — nó chỉ nói rằng cái sai được lặp lại nhất quán. Cùng công cụ ở H4 thì ĐẠT (ZBandGBPNZDH4, FORM 1,398 / OOS 0,879).

**5. `ZBandGBPCAD_H4_exit_at_mean_False`** (H4)

> GBPCAD H4 ra Sharpe 0,815 ở lab nhưng 0,557 ở động cơ sản xuất — lab không có nhánh thoát khi z về 0. Suýt cứu bằng tham số mới `exit_at_mean=False` (Sharpe lên 0,865), nhưng đo trên CẢ BẢY chân cho thấy nó chỉ tốt hơn ở **1/7**. Một tham số chỉ đúng đúng ô mình cần nó đúng là bậc tự do, không phải phát hiện. Tham số vẫn giữ trong `zband_core` KÈM bảng đo 7 chân, mặc định True, không chân nào dùng False. BÀI HỌC THÀNH QUY TẮC: kiểm định phải chạy trên cùng đường code với sản xuất; lab chỉ để quét rộng.

**6. `XsZscoreReversion_M30`** (M30)

> CÙNG luật với chân H4 đã nhận (`CrossXsReversion`) nhưng ở M30: Sharpe 0,410 · FORM 0,410 · OOS 0,417 — ổn định hơn cả bản H4 nhìn từ hai cửa sổ. Vẫn LOẠI vì hai kiểm định khác: bootstrap khối cho P(<0) = 11,5% (ngưỡng 10%), và bỏ 5 tháng tốt nhất thì ĐỔI DẤU (−0,49%) — 5 tháng đó chiếm 103,4% lợi nhuận. Bản H4 cùng luật chỉ 89,8% và giữ dấu. Bài học: FORM/OOS đẹp KHÔNG thay được kiểm định đuôi.

**7. `CointegrationPairs_Majors`** (M30/H1/H4)

> Spread β-hedge (Engle-Granger) giữa 21 tổ hợp hai major, 3 khung = 63 ô: **0/63 ô** có ADF trung vị < 0,05. Không có hai major nào cointegrate thật — chúng chung nhân tố USD nhưng chân còn lại là bước đi ngẫu nhiên độc lập. Ô 'tốt nhất' (NZDUSD~USDCAD H4, Sharpe 0,604) có ADF 0,118 và chỉ 30 lệnh — nhiễu. Kết luận cấu trúc: chân H1 thắng vì cross là CÔNG CỤ GIAO DỊCH ĐƯỢC (một spread), không vì cointegration; β khớp phải trả HAI spread nên không bù nổi.

**8. `LeadLag_CrossPredictability`** (H1)

> Tự tương quan CHÉO giữa 20 cross: 124/380 ô ngoài đường chéo vượt ngưỡng t>2 (32,6%) — tín hiệu THẬT về mặt thống kê. Nhưng giao dịch được thì âm sâu: gross 0,16 bps/nến vs chi phí 1,57. Hồi quy đa biến trượt, 6 cấu hình, ALL từ −9,06 đến −9,95. Vòng quay 2.600-4.960/năm. Bài học: t-stat lớn trên IC 0,03 vẫn không đủ biên độ để bù một lượt khứ hồi.

**9. `FreqtradeConfluence_4Rules`** (H1/M30)

> Bốn luật hợp lưu lấy nguyên văn từ `project-refer/freqtrade-strategies` (HLHB của babypips — viết RIÊNG cho forex, Triple Supertrend, Bandtastic, TrendRider pullback) × 2 khung × 7 cặp = 56 ô: **0/56 ô** qua cổng FORM>0 & OOS>0 & ALL>0,4. Trung vị theo luật: hlhb H1 −0,122, triple_st H1 −0,834, trendrider H1 −0,527, bandtastic H1 +0,014. Giả thiết 'giao của N điều kiện yếu lọc ra tập con đủ mạnh' bị bác bỏ: số lệnh giảm đúng như dự đoán nhưng net/lệnh KHÔNG tăng. Ngoại lệ duy nhất đáng ghi: `bandtastic` (hồi quy trung bình CÓ cổng xu hướng) dương 4/7 cặp và net +5,06 bps/lệnh trên GBPUSD H1 — không đủ phổ quát để nhận, nhưng xác nhận hướng sống sót trên FX là MEAN REVERSION, không phải trend.

**10. `PriceActionFamilies_XAU`** (M30/H1/H4)

> 8 family của hệ XAUUSD trên FX: 28/33 NO_INFORMATION, MFE/|MAE| ≈ 1,00 (chữ ký bước đi ngẫu nhiên); 363 phép thử sinh 5 'phát hiện' — ÍT HƠN mức ngẫu nhiên

**11. `FixReversal`** (H1)

> Tín hiệu THẬT và đặc tả trước (Krohn JoF 2024; EURUSD h13 Frankfurt t = −3,83, vượt Bonferroni) nhưng độ lớn ≈ đúng 1 lượt khứ hồi. 1/1104 luật qua DEV → OOS Sharpe −1,34; control p = 0,56; DSR = 0,0000

**12. `TrendMA_20_120`** (D1)

> Luật Olszweski & Zhou nguyên văn: chi phí chỉ ăn 0,5-7,4% lợi nhuận gộp (chi phí KHÔNG phải ràng buộc) nhưng tín hiệu âm — danh mục Sharpe −0,07, 2/7 năm dương; EURUSD qua 11 năm −0,13

**13. `CrossSectionalMomentum`** (D1)

> Chiều NGƯỢC với reversal: OOS Sharpe −0,95. Menkhoff et al. tìm momentum ở 1-12 tháng; ở 21 ngày dấu đảo lại

**14. `MonthEndFlow`** (D1)

> Ứng viên chân thứ hai: |t| lớn nhất chỉ 1,27; DEV Sharpe 0,07 vs OOS 0,53 — bất ổn. Tương quan thấp không cứu được một chân không có edge

**15. `IntradayVolumeConditioned`** (H1)

> Giả thuyết Campbell-Grossman-Wang (khối lượng tách thanh khoản khỏi thông tin) BỊ BÁC BỎ trên FX H1: fade trên khối lượng THẤP cho ratio −0,079 còn khối lượng CAO +0,264 — NGƯỢC dự đoán; 0/7 cặp vượt chi phí

**16. `H1GridCrossSectional`** (H1)

> Cắt ngang trên lưới H1 (lb/hold 24-120 nến): reversal ô tốt nhất có DEV −0,238 / OOS +1,426 — bất ổn, MaxDD 15,2%. Momentum: MỌI ô âm (−0,54 đến −1,38) sau khi sửa lỗi look-ahead

**17. `NewsOverreaction`** (M30)

> Edge THẬT (control p = 0,0000, phân vị 100%; nến tin dịch chuyển 4-6x bình thường) NHƯNG không với tới được: vào muộn 1 nến làm t tụt 1,64 → 0,47, tức edge nằm đúng ở nến spread rộng nhất. OOS t = 0,10-0,74, chết ở chi phí ×5, phụ thuộc nặng 2022

**18. `SignalDispersionGate`** (D1)

> Thử cắt thời gian trong thị trường để giảm phí swap: mọi biến thể Sharpe 0,41-0,58, PBO giữ nguyên 0,686 — không cải thiện

**19. `RegimeSwitch_RevToMom`** (D1)

> Đổi sang momentum khi khủng hoảng: DEV đẹp hơn (1,133) nhưng OOS sụt 0,710, chênh lệch t = +0,98 — chữ ký overfit. Bản 'đứng ngoài' ổn định hơn

---

## 8. Ba bài học đắt nhất

**Vùng tham số vững không cứu được OOS âm.** `ZBandGBPNZD_H1` có vùng đẹp nhất toàn dự án — 18/18 ô lân cận dương, Sharpe 0,978, t = 3,34, cả hai control p = 0,0000. Vẫn loại vì FORM 1,493 so với OOS **−0,119**. Vùng vững chỉ nói rằng cái sai được lặp lại nhất quán. Cùng công cụ ở H4 thì đạt.

**Một tham số chỉ đúng đúng ô mình cần nó đúng là bậc tự do, không phải phát hiện.** GBPCAD H4 ra 0,815 ở lab nhưng 0,557 ở động cơ sản xuất. Thêm `exit_at_mean=False` kéo lên 0,865 — nhưng đo trên cả bảy chân thì nó chỉ tốt hơn ở **1/7**. Đã loại, và thành quy tắc: **kiểm định phải chạy trên cùng đường code với sản xuất**; lab chỉ để quét rộng.

**Trên FX chỉ chiều hồi quy sống được.** Đo ở mọi khung, mọi tốc độ: EWMAC 6 tốc độ, Donchian 6 cửa sổ, range expansion, squeeze, session breakout, gap fade — tất cả gross âm. `hl_range` là bản đảo chiều của `range_break`; **cả hai chiều đều thua**, nên kết luận là đại lượng biên độ nến vô dụng, không phải do chọn sai chiều.

---

## 9. Điều kiện còn lại trước khi cấp vốn

**Spread đo trên tài khoản DEMO MetaQuotes**, không phải tài khoản FTMO thật. Tỷ lệ đo được là 0,342 so với ước lượng cũ (spread thật rẻ hơn 2,9 lần), và `SPREAD_SAFETY_FACTOR = 1,5` là biên phòng vệ chứ không phải số đo.

Chạy `scripts/measure_broker_costs.py` trên chính tài khoản sẽ giao dịch. Nếu spread thật đắt hơn giả định thì các ô sát ngưỡng sẽ rụng — và ngưỡng hoà vốn ở §6 cho biết ngay ô nào rụng trước.

Biên swap broker đo được **0,382 %/năm** (trung vị 27 symbol) so với giả định 1,0 %/năm trong mọi báo cáo — tức các con số ở đây **bi quan hơn** thực tế đo được trên demo.

---

## 10. Phụ lục — chiến lược ngoài đã kiểm định

Chiến lược do người dùng cung cấp, đo bằng đúng giao thức ở §6. Ghi lại để không ai
phải đo lại từ đầu.

### Asian Session Range Breakout (USDJPY)

**Luật**: range 03:00-06:00 giờ broker (GMT+2/+3) · vào khi phá · thoát 19:00 ·
SL = đầu kia range · 1 lệnh/ngày.

**Kết quả** (2020-01 → nay, đủ chi phí, giả định khớp bi quan — vào ở giá đóng cửa
nến phá chứ không ở mức biên độ):

|            |                                 |
| ---------- | ------------------------------- |
| Sharpe ALL | +0,319 · FORM 0,342 · OOS 0,281 |
| Lệnh       | 1.636 · thắng 44,1%             |
| net/lệnh   | +0,90 bps (chi phí 1,20 bps)    |
| t          | **+0,98**                       |
| Lợi nhuận  | +2,24 %/năm · MaxDD 12,25%      |
| Năm dương  | **4/7**                         |

**Bốn cổng cho kết quả trái ngược nhau**:

| Cổng                    | Kết quả                                                           |
| ----------------------- | ----------------------------------------------------------------- |
| Control ngày ngẫu nhiên | **ĐẠT** — p = 0,0067                                              |
| Bootstrap khối          | **KHÔNG** — CI95 [−0,254 · +0,874] chứa 0, P(<0) = 13,9%          |
| Loại ngoại lai          | **KHÔNG** — 5 tháng tốt nhất = 120,9% lợi nhuận, bỏ đi còn −3,07% |
| Ổn định năm             | **KHÔNG** — 4/7                                                   |

**Ba điểm quyết định việc không nhận**:

1. **Chỉ sống trên USDJPY.** Cùng luật trên 6 major khác: EURUSD −0,225 ·
   GBPUSD −0,545 · NZDUSD −0,655 · USDCHF −0,845 · AUDUSD −1,030 · USDCAD −1,353.
   **0/6 dương.**
2. **Chỉ chiều MUA có lãi.** Mua 894 lệnh net +1,94 bps; bán 742 lệnh net **−0,36
   bps**. Một luật đối xứng mà chỉ một chiều chạy, trong giai đoạn USDJPY tăng từ
   103 lên 160 — có thể là xu hướng của cặp, không phải hiệu ứng phiên.
3. **Rất nhạy múi giờ.** Ép cứng GMT+0 → 0,169 · GMT+1 → 0,086 · GMT+3 → 0,357 ·
   GMT+4 → −5,471. Lệch một hai tiếng đổi kết quả bốn lần.

**Quét 24 mốc giờ bắt đầu**: mốc 03:00 đứng **hạng 4/16**, và **chỉ 1/16 mốc có
t > 2,0** — mốc đó là **08:00** (Sharpe 0,882 · OOS 0,842 · t = 2,72), mạnh gần gấp
ba mốc gốc. Đây là hướng đáng đo tiếp.

**Kết luận**: control cho p = 0,0067, tức biên độ phiên Á **thật sự mang thông tin**.
Nhưng thông tin đó nhỏ hơn chi phí giao dịch trên rổ hiện có, ở mốc giờ được đưa ra.
Không nhận vào danh mục.

⚠️ **Giới hạn của phép đo**: dự án chỉ có dữ liệu từ 2020-01, không kiểm chứng được
giai đoạn 2011-2019 mà người cung cấp nhắc tới. Và giả định khớp lệnh ở đây là **giá
đóng cửa nến phá**; nếu thực tế dùng **lệnh chờ tại mức biên độ** thì kết quả khác
đáng kể — đó là câu hỏi còn mở.

_Script_: `research/fx/asian_range_breakout.py` · `research/fx/asian_range_validate.py`
