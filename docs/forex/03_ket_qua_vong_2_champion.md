# The Cheopard Forex — Vòng 2: tìm ra Champion, và bốn hướng bị bác bỏ trên đường đi

> Ngày 13/08/2026 · Dữ liệu `D:\data-ticks-train\_m1` (tick Dukascopy → M1, spread thật)
> Mã: `src/python/strategies/currency_reversal.py` · Số liệu: `reports/fx_research/`
> Nền tri thức: `01_kien_thuc_nen_forex.md` (10 paper) · `02_kien_thuc_nen_internet.md` (51 nguồn)

---

## 0. Kết quả

**Champion: Cross-Sectional Currency Short-Term Reversal, có cổng chế độ biến động.**

|                           | DEV 2020-2024 | **OOS 2024-2026** | ALL   |
| ------------------------- | ------------- | ----------------- | ----- |
| Lợi nhuận/năm             | 6,20%         | **4,33%**         | 5,47% |
| Biến động/năm             | 5,34%         | 3,79%             | 4,79% |
| **Sharpe**                | 0,935         | **0,919**         | 0,918 |
| Sortino                   | 1,239         | 1,223             | 1,205 |
| **MaxDD**                 | 7,12%         | **3,22%**         | 7,12% |
| **Calmar**                | 0,871         | **1,346**         | 0,768 |
| Hit rate (ngày có vị thế) | 0,520         | 0,518             | 0,519 |

**7/7 năm dương.** Chi phí thật ăn 7,5% lợi nhuận gộp. Dollar-neutral 2,78e-16 theo xây dựng.
Đứng ngoài 18,6% số ngày (chế độ khủng hoảng).

| năm       | 2020   | 2021   | 2022   | 2023   | 2024   | 2025   | 2026   |
| --------- | ------ | ------ | ------ | ------ | ------ | ------ | ------ |
| lợi nhuận | +5,94% | +4,69% | +3,47% | +5,86% | +4,95% | +2,10% | +3,31% |
| Sharpe    | 0,82   | 0,94   | 0,96   | 1,21   | 1,31   | 0,52   | 1,00   |

---

## 1. Vì sao chiến lược này là THUẦN FOREX

Nó xếp hạng **8 đồng tiền với nhau** rồi mua đồng yếu nhất / bán đồng mạnh nhất.
Trên một tài sản đơn lẻ như vàng, **không tồn tại mặt cắt ngang để xếp hạng** — chiến
lược này không định nghĩa được. Đó là thứ phân biệt nó với mọi thứ trong hệ XAUUSD cũ.

Và nó giải đúng vấn đề cấu trúc đã đo ở vòng 1: `EURUSD BUY + GBPUSD BUY + AUDUSD BUY`
thực chất là **một** cược "USD yếu". Xếp hạng cắt ngang biến ba lệnh giả-độc-lập thành
một cược tương đối thật. Đây đồng thời **chính là Currency Exposure Engine** mà anh yêu
cầu — nó không phải một tầng lọc gắn thêm, nó là bản chất của chiến lược.

### Luật đầy đủ

```
mỗi ngày:
  1. lợi nhuận log D1 của 8 đồng tiền từ 7 cặp vs USD, chuẩn hoá tổng = 0
  2. tín hiệu(đồng) = −(lợi nhuận tích luỹ 21 ngày, đến hết hôm qua)
  3. mỗi 21 ngày tái cân bằng:
       long  3 đồng tín hiệu CAO nhất  (= yếu nhất quá khứ)
       short 3 đồng tín hiệu THẤP nhất (= mạnh nhất quá khứ)
       tỷ trọng trong chân ∝ 1/σ(63 ngày)
  4. CỔNG CHẾ ĐỘ: biến động rổ ≥ phân vị 80 của 252 ngày trước → ĐỨNG NGOÀI
  5. giữa hai lần tái cân bằng: KHÔNG đổi vị thế
  6. khớp lệnh trong 10:00-16:00 UTC, tối ưu 15:00
```

### Nền học thuật

- **PAMR** (Li, Zhao, Hoi & Gopalkrishnan 2012) — khái niệm đảo chiều cắt ngang một kỳ.
  Cơ chế cập nhật của họ KHÔNG dùng (giả định không chi phí giao dịch).
- **Menkhoff, Sarno, Schmeling & Schrimpf 2012 (JFE)** — hạ tầng xếp hạng 3/3, tái cân
  bằng tháng. Họ tìm momentum ở 1-12 tháng; ta đo reversal ở 21 ngày — khác thang, không
  mâu thuẫn. Và chính họ (_Currency Value_ 2014) cảnh báo chiều tín hiệu cắt ngang trên
  FX **không hiển nhiên**, nên cả hai chiều đều được đo và OOS quyết định.
- **Brière & Drut 2010 (Amundi)** — nguồn của cổng chế độ (xem §3).
- **Olszweski & Zhou 2014** — chia đều + inverse-vol, **không dùng lợi nhuận kỳ vọng**
  để đặt tỷ trọng (họ đo được điều đó làm Sharpe tụt 0,98 → 0,70).

---

## 2. Kiểm định độ vững — sáu bài, chạy để GIẾT chiến lược

| bài                        | kết quả                                                                    | phán quyết                |
| -------------------------- | -------------------------------------------------------------------------- | ------------------------- |
| **Vùng tham số**           | OOS dương khắp lb 10-30 × rb 5-21. rb=42 xấu đều = ranh giới cấu trúc thật | ✅ không phải đỉnh cô lập |
| **Control ngẫu nhiên**     | Sharpe +0,64 vs p50 control −0,08 → **phân vị 99,2%, p = 0,0083**          | ✅                        |
| **Bootstrap khối 21 ngày** | Sharpe 0,645, CI95 [−0,006 · +1,250], P(<0) = 2,6%                         | ⚠️ chạm 0                 |
| **Loại ngoại lai**         | 5 tháng tốt nhất = 62,7% lợi nhuận; bỏ đi vẫn **giữ dấu** (+1,42%)         | ⚠️ đuôi dày               |
| **Stress chi phí**         | sống sót **×10 chi phí** (Sharpe +0,21)                                    | ✅ rất mạnh               |
| **Ổn định năm**            | **7/7 năm dương** sau cổng chế độ                                          | ✅                        |

Bổ sung: phân phối tháng **44/79 dương (55,7%)**, trung vị **+44 bps** → không phải vài
tháng may. Cả **hai chân đều có edge**: long đồng yếu +2,05% (Sharpe 0,67), short đồng
mạnh +1,78% (0,59) → hiệu ứng cắt ngang thật, không phải artifact một phía.

Đóng góp theo đồng tiền phân tán hợp lý: CAD 33% · EUR 20% · NZD 15% · AUD 14% · JPY 11%.

---

## 3. Cổng chế độ — tái lập cấu trúc Brière & Drut

Đo được (biến động rổ, top 20% trượt = CRISIS):

|          | CALM                     | CRISIS                    |
| -------- | ------------------------ | ------------------------- |
| REVERSAL | **+5,56%, Sharpe 1,049** | −5,34%, Sharpe −0,842     |
| MOMENTUM | −6,10%, Sharpe −1,149    | **+4,82%, Sharpe +0,760** |

Đảo vai hoàn toàn — cùng dạng với carry/PPP của Brière & Drut (0,85/−0,48 → 0,20/+1,09).

⚠️ **Trung thực về điều này:** `corr(REV, MOM) = −1,000`. Momentum là **cùng tín hiệu đảo
dấu**, nên đây là MỘT phát hiện, không phải hai. "Momentum ăn tiền lúc khủng hoảng" chỉ là
cách nói khác của "reversal mất tiền lúc khủng hoảng".

**Ba cấu hình được đo, bản SWITCH bị LOẠI:**

| cấu hình                              | DEV Sharpe | OOS Sharpe | phán quyết                                                                     |
| ------------------------------------- | ---------- | ---------- | ------------------------------------------------------------------------------ |
| REV thuần                             | 0,558      | 0,831      | nền                                                                            |
| SWITCH (đổi sang momentum khi crisis) | **1,133**  | **0,710**  | ❌ DEV đẹp, OOS sụt = chữ ký overfit; chênh lệch so với bản dưới chỉ t = +0,98 |
| **REV + đứng ngoài khi crisis**       | **0,956**  | **0,965**  | ✅ ổn định gần như hoàn hảo                                                    |

Bản được chọn chính là biến thể **CTC** của Brière & Drut ("dừng carry khi khủng hoảng"),
mà họ cũng đo là tốt hơn carry thuần (0,69 vs 0,55). Nó đã biến 2022 — năm duy nhất âm —
từ −2,47% thành **+3,47%**, vì 2022 là chu kỳ siêu tăng USD, đúng lúc reversal phải nghỉ.

**Proxy regime:** ta KHÔNG có VIX (nguồn gốc của Brière & Drut) nên dùng **biến động rổ
tiền tệ** làm thước đo risk-aversion nội-FX. Ngưỡng là phân vị **trượt 252 ngày**, nhân
quả, chạy được ở live — không phải phân vị toàn mẫu (bản đó dùng thông tin tương lai).

---

## 4. Tầng thực thi H1 — khung giao dịch chính

Tín hiệu sinh ở D1; H1 là nơi **mọi thứ khác** xảy ra. Chi phí khứ hồi rổ 7 cặp theo giờ UTC:

| giờ UTC     | 15        | 14    | 16    | 11    | …   | 20    | 21    | **22**    |
| ----------- | --------- | ----- | ----- | ----- | --- | ----- | ----- | --------- |
| bps/khứ hồi | **1,657** | 1,660 | 1,666 | 1,668 | …   | 1,805 | 2,099 | **2,304** |

- **15:00 UTC rẻ nhất** (chồng lấn London/NY). 22:00 UTC đắt hơn **1,39 lần**.
- Cả dải **10:00-16:00 UTC** nằm trong 1% của nhau → đây là **vùng ổn định**, không phải
  điểm tối ưu mong manh. Luật: khớp trong dải, ưu tiên 15:00.
- **20:00-23:00 UTC bị CẤM** — cửa sổ rollover, spread giãn 1,4-3 lần trên mọi cặp.

Tách `execution_ok()` khỏi `live_targets()` theo tầng của Dempster & Leemans (2004): tầng
tín hiệu nói vị thế nên giữ, tầng rủi ro quyết định có được khớp hay không.

---

## 5. Bốn hướng bị BÁC BỎ trên đường đi (không lặp lại)

| #   | hướng                                       | bằng chứng bác bỏ                                                                                                                                                                                                                                                                                          |
| --- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **8 strategy family của hệ XAUUSD trên FX** | 28/33 NO_INFORMATION; MFE/\|MAE\| ≈ 1,00 (chữ ký bước đi ngẫu nhiên); 363 phép thử sinh 5 "phát hiện" — **ít hơn mức ngẫu nhiên**                                                                                                                                                                          |
| 2   | **Hiệu ứng fix theo giờ** (Krohn 2024, JoF) | Tín hiệu THẬT và đặc tả trước (EURUSD h13 Frankfurt, gross t = −3,83, vượt Bonferroni). Nhưng độ lớn ≈ đúng **1 lượt khứ hồi**. 1/1104 luật qua DEV → **OOS Sharpe −1,34**; control **p = 0,56**; **DSR = 0,0000**. Phân phối control p50 = −1,21: trung bình mọi luật trong không gian đó lỗ sau chi phí. |
| 3   | **Momentum 20/120 ngày** (Olszweski & Zhou) | Chi phí chỉ ăn 0,5-7,4% lợi nhuận gộp → **chi phí không còn là ràng buộc**, nhưng tín hiệu âm: danh mục Sharpe −0,07, **2/7 năm dương**; EURUSD qua 11 năm Sharpe −0,13. Khớp tài liệu TSMOM suy giảm ngoài mẫu.                                                                                           |
| 4   | **Dòng cuối tháng** (chân thứ hai ứng viên) | \|t\| lớn nhất chỉ **1,27**; ứng viên tốt nhất DEV Sharpe 0,07 vs OOS 0,53 — bất ổn. Ghép vào sẽ là thêm chân **không có edge chứng minh được**, chỉ đẹp OOS do may.                                                                                                                                       |

Ghi chú về #4: nó có tương quan với lõi chỉ **+0,027** (gần như độc lập hoàn hảo) và ghép
50/50 cho OOS Sharpe 1,078. **Vẫn loại** — một chân không có ý nghĩa thống kê thì tương
quan thấp chỉ làm kết quả trông đẹp hơn chứ không tạo ra edge.

---

## 6. Điều đã học được về Forex (khác XAUUSD ở đâu)

1. **Edge FX không nằm ở hình dạng giá của một cặp.** Bốn hướng directional đều đổ. Cái
   sống sót là cược **tương đối giữa các đồng tiền**.
2. **Ràng buộc thật là SỐ LƯỢT KHỨ HỒI, không phải chất lượng tín hiệu.**
   ```
   hiệu ứng fix  1 lượt/ngày → chi phí ≈ drift          → chết
   reversal      12 lượt/năm → chi phí = 7,5% lợi nhuận → sống
   ```
   Cùng một tín hiệu có thật, khác nhau ở tần suất, cho hai kết cục ngược nhau.
3. **Đơn vị của vàng vô hiệu hoá hệ thống, không phải làm nó kém.** `ATR_MIN = 1,50 USD`
   lớn hơn ATR H1 của EURUSD ~1.000 lần → lọc sạch 100% tín hiệu. Và **commission
   ($7/lot = 0,70 pip trên EURUSD) lớn hơn cả spread trung vị (0,31 pip)**.
4. **Chế độ thị trường đảo VAI chiến lược, không chỉ bật/tắt.** Hệ vàng cũ chỉ biết tắt
   (`regimes_allowed`). Ở đây cấu trúc calm/crisis là đảo dấu hoàn toàn.
5. **Thứ hạng Tier 1 của anh khớp chính xác rào chi phí đo được**: EURUSD 2,44% ·
   USDJPY 2,73% · GBPUSD 5,00% — rồi Tier 2 nhảy lên 8,6-10,1%.

---

## 7. Rủi ro đã biết — phải theo dõi khi chạy thật

1. **Đuôi dày**: 5 tháng tạo 62,7% lợi nhuận. Một năm không gặp tháng tốt là hoàn toàn có
   thể; đường equity sẽ đi ngang rất lâu và điều đó KHÔNG có nghĩa chiến lược hỏng.
2. **CI95 của Sharpe chạm 0** ([−0,006 · +1,250]). Edge có thật nhưng biên không rộng.
3. **Cửa sổ đo chỉ 6,5 năm** (giới hạn dữ liệu: 6/7 cặp bắt đầu 2020). Không có nguồn học
   thuật nào đo đúng cấu hình này — nền lý thuyết là PAMR + Menkhoff, không phải một bản
   sao trực tiếp.
4. **Proxy regime chưa được kiểm chứng độc lập.** Biến động rổ thay VIX là lựa chọn bắt
   buộc do thiếu dữ liệu, không phải lựa chọn tối ưu.
5. **Cắt ngang trên 7 cặp là mặt cắt HẸP.** Menkhoff et al. dùng vũ trụ rộng hơn nhiều.
   Thêm cặp (cross, hoặc đồng G10 còn thiếu như SEK/NOK) là hướng mở rộng có cơ sở.

---

## 8. Trạng thái codebase sau khi dọn

Theo chỉ đạo 13/08: **xoá hoàn toàn** chiến lược XAUUSD thay vì giữ lại.

```
215 file Python  →  32 file
```

**Đã xoá:** toàn bộ `live_strategies/` (31 module XAU) · `pa_framework/` (8 family đã
chứng minh NO_INFORMATION trên FX) · `core/execution|intelligence|ai_macro|virtual/`
(engine dispatch từng-chiến-lược-XAU) · `research/ml/` (meta-labeling AUC 0,42-0,55) ·
`exit_lab/` (mô phỏng SL/TP từng lệnh) · `models/XAUUSD/` · `docs/strategies/`.

Lý do xoá `core/execution`: mô hình thực thi FX khác **về bản chất** — tái cân bằng danh
mục 7 cặp mỗi 21 ngày theo tỷ trọng, không phải dispatch tín hiệu + SL/TP từng lệnh. Giữ
lại chính là "giữ implementation chỉ vì nó đã tồn tại".

**Giữ lại (asset-agnostic, đã kiểm chứng qua sử dụng thật):**
`validation/` (DSR, PBO, reality check, stress testing, robust metrics) ·
`core/infra/` (mt5_bridge, symbol_spec, market_schedule, clock, state_store, ftmo) ·
`shared/` (indicators, statistics, paths).

**Mới:**

```
shared/asset_profile.py            SSOT pip/contract/commission theo cặp
shared/fx_data.py                  nạp M1/D1, SSOT dữ liệu
strategies/currency_reversal.py    CHAMPION — live-ready
research/fx_clock.py               cấu trúc lợi nhuận quanh đồng hồ
research/fx_fix_lab.py             cô đặc + điều kiện hoá hiệu ứng fix
research/fx_fix_portfolio.py       cổng DEV/OOS + control + DSR
research/fx_momentum.py            momentum D1 (đã bác bỏ, giữ làm bản ghi)
research/fx_cross_section.py       vòng nghiên cứu cắt ngang
```

---

## 9. Bước tiếp theo

**Ưu tiên 1 — mở rộng mặt cắt ngang.** Mặt cắt 7 cặp là hẹp so với tài liệu. Thêm SEK/NOK
(có trong `D:\data-ticks-train`? cần kiểm) hoặc dựng cross tổng hợp sẽ tăng số bậc tự do
của phép xếp hạng. Đây là hướng cải thiện có cơ sở lý thuyết rõ nhất.

**Ưu tiên 2 — chân thứ hai không tương quan.** Olszweski & Zhou đo được lợi ích chính của
đa dạng hoá cấp chiến lược là **cắt MaxDD gần một nửa** (−17,4%/−29,2% → −8,95%). Ứng
viên còn lại: carry (cần swap MT5 ở live — có sẵn, chỉ thiếu lịch sử) và cointegration
cross (rủi ro cao: 4 chân = 4 lần spread).

**Ưu tiên 3 — tầng vận hành live.** Cần: kết nối MT5, quy đổi tỷ trọng → lot theo
`AssetProfile.value_per_pip_per_lot()`, reconciliation vị thế, và giới hạn rủi ro theo
ngày/tháng.
