# The Cheopard Forex — Nền tri thức (Vòng đọc 2: nguồn học thuật & thực hành trên internet)

> Tiếp nối `01_kien_thuc_nen_forex.md` (corpus local). Tài liệu này lấp **đúng khoảng trống**
> mà corpus local để lại: *"không nguồn nào chứng minh edge FX ở thang H1 trên dữ liệu hiện đại."*
> Kết quả: **có** — nhưng nó không phải mẫu hình giá, và biên rất mỏng.
> Quy ước: `➤ SUY LUẬN` = suy luận của tôi, không phải nội dung nguồn.

---

## 1. PHÁT HIỆN TRUNG TÂM: đảo chiều quanh các phiên định giá chuẩn (FX fixings)

### 1.1 Krohn, Mueller & Whelan — *Journal of Finance* 79(1), 2024, tr. 541-578

Đây là nguồn chất lượng cao nhất tìm được, và nó nói đúng về thang giờ.

**Sự kiện phong cách hoá (stylised fact) mới:**
> USD **tăng giá một cách hệ thống** trước ba phiên fix lớn và **giảm giá sau đó** — đạt cực đại
> toàn cục đúng tại thời điểm fix. Danh mục đầu tư vào ngoại tệ vì vậy có hình **V quanh từng
> fix**, và hình **W trên toàn bộ 24 giờ** bắt đầu từ 17:00 New York.

**Ba mốc fix — giờ chính xác:**

| fix | giờ địa phương | UTC (mùa đông) | UTC (mùa hè) |
| --- | -------------- | -------------- | ------------ |
| Tokyo | 09:55 JST | **00:55** | 00:55 (Nhật không đổi giờ) |
| Frankfurt / ECB | 14:15 CET | **13:15** | 12:15 |
| London (WM/R) | 16:00 London | **16:00** | 15:00 |

**Phạm vi & độ tin cậy:** G9, dữ liệu tần số cao **21 năm** (1999-2018/2019, Reuters TRTH).
Hiện diện **mọi ngày trong tuần, mọi tháng trong năm, và mọi năm trong mẫu**. t-stat ~5,5–9,2.

**Độ lớn (mid-quote, CHƯA chi phí):**
- Sau khi New York đóng đến trước fix Tokyo: DOL tăng **~5,3%/năm (2,1 bps/ngày)**, t ≈ 9,2 vùng lân cận
- Ngay sau fix Tokyo: đảo chiều, giảm **~5,5%/năm (2,2 bps/ngày)**
- Trước khi thị trường châu Âu mở: tăng **~4,3%/năm (1,7 bps/ngày)**
- Đến khi New York đóng: giảm **~4,8%/năm (1,9 bps/ngày)**, t ≈ 5,5
- Danh mục long toàn bộ G9: biên độ dao động ngày **~2 bps (>5%/năm)**

**Cơ chế (không phải data mining):** rủi ro tồn kho (inventory risk). Dealer FX phải trung gian
một lượng cầu USD **vô điều kiện** tại các fix (doanh nghiệp, quỹ hưu trí, công ty bảo hiểm cần
định giá/thanh toán). Họ đòi bù đắp cho việc giữ tồn kho qua các múi giờ → giá dạt trước fix và
hồi sau fix. Tác giả nói thẳng đây **không phải bất hiệu quả thị trường** mà là thù lao trung gian.

### 1.2 Chi phí giao dịch — phần quyết định, và tác giả tự làm rất kỹ (§V)

Chiến lược fix-reversal họ định nghĩa: long USD trước fix, đóng tại fix, short USD sau fix.
Cửa sổ (giờ New York):

| fix | long USD | short USD |
| --- | -------- | --------- |
| Tokyo | 17:00 → 20:55 | 20:55 → 02:00 |
| ECB | 02:00 → 08:15 | 08:15 → 17:00 |
| London | 02:00 → 11:00 | 11:00 → 17:00 |

| kịch bản chi phí | EUR | GBP | JPY | Sharpe |
| ---------------- | --- | --- | --- | ------ |
| **Bỏ qua chi phí** | +13,6% | +11,2% | +12,9% | rất cao |
| **Spread chỉ dẫn ĐẦY ĐỦ** | **ÂM** | **ÂM** | **ÂM** | **ÂM** |
| **Giảm spread 50%** | +6,6% | +4,2% | +3,4% | **0,5 – 0,7** |
| Futures CME, spread đầy đủ | **+ (Sharpe 0,61)** | ÂM | ÂM | — |

- Cơ sở cho việc giảm spread: Gargano, Riddiough & Sarno (2018) chỉ ra spread chỉ dẫn
  (indicative) trong các database rộng hơn spread hiệu dụng thật, và đề nghị **giảm tới 75%**
  để xấp xỉ chi phí mà trader lớn thật sự trả.
- Chiến lược đòi **đảo vị thế tới 4 lần trong 24 giờ** → vòng quay khổng lồ là lý do chi phí
  đầy đủ xoá sạch lợi nhuận.
- Chỉ **EUR** sống sót ngay cả với spread futures CME đầy đủ, "do thanh khoản cực cao so với
  các cặp khác".

### 1.3 ⚠️ Suy giảm theo thời gian — phải đọc trước khi phấn khích

Hình 9 (với chi phí = 50% spread): giao dịch đảo chiều Tokyo cho lợi nhuận **âm** những năm
đầu mẫu, dương nhưng phẳng đến ~2007, có lãi đến ~2013, và **từ 2013 trở đi ÂM với EUR và GBP,
phẳng với JPY**.

Ngoài ra: cải cách WM/R **15/02/2015** nới cửa sổ fix từ 1 phút lên **5 phút (15:57:30–16:02:30
giờ London)**. Nghiên cứu sau đó (FCA Occasional Paper 46; NBER WP 23327) kết luận mô hình
**vẫn còn nhưng YẾU HƠN và đã THAY ĐỔI HÌNH DẠNG**; khối lượng trong cửa sổ fix không giảm, tức
cầu fix vẫn cao.

➤ SUY LUẬN: cửa sổ dữ liệu của ta (**2020-2026**) nằm hoàn toàn **SAU** cả mốc suy giảm 2013 lẫn
cải cách 2015. Không được mượn con số 13,6%/năm. Phải **tự đo lại trên chính dữ liệu của mình**.
Đây chính là một giả thuyết đã được đặc tả đầy đủ trước khi backtest — đúng quy trình mà
`docs/knowledge/research_process.md` §1 đòi hỏi.

---

## 2. XÁC NHẬN ĐỘC LẬP: hiệu ứng "giờ nhà" (home-hours depreciation)

### 2.1 Breedon & Ranaldo — SNB Working Paper 2011-4

> "Dùng 10 năm dữ liệu FX tần số cao, chúng tôi trình bày bằng chứng về hiệu ứng thời-gian-trong-
> ngày qua **xu hướng rõ rệt của một đồng tiền GIẢM GIÁ trong chính giờ giao dịch địa phương của
> nó**. Chúng tôi xác nhận mô hình này trên một dải các đồng tiền và thấy rằng, với **EUR/USD, nó
> tạo thành một chiến lược giao dịch đơn giản, CÓ LỢI NHUẬN**."

- 6 tỷ giá, dữ liệu giờ, **1/1997 – 5/2007**
- Cùng hiện diện trong **order flow** → cơ chế: người tham gia có xu hướng **mua ròng ngoại tệ
  trong giờ giao dịch của chính họ** (doanh nghiệp châu Âu mua USD trong giờ châu Âu để thanh
  toán hoá đơn toàn cầu, và ngược lại trong giờ Mỹ)
- Luật cụ thể: **SHORT EURUSD trong giờ làm việc châu Âu (03:00–09:00 ET), LONG EURUSD trong giờ
  làm việc Mỹ (11:00–15:00 ET)**

### 2.2 Ba nguồn nói CÙNG một điều — đây là điểm quan trọng nhất của cả vòng đọc

| nguồn | mẫu | phát biểu |
| ----- | --- | --------- |
| Breedon & Ranaldo (SNB) | 1997-2007 | long USD giờ châu Âu, short USD giờ Mỹ |
| Krohn/Mueller/Whelan (JoF) | 1999-2018 | long USD 02:00→08:15 ET, short USD 08:15→17:00 ET |
| Phân tách dollar-carry theo giờ | — | phần lớn lợi nhuận dollar-carry đến từ **vị thế long ngoại tệ TRONG NGÀY (+4,20%)** vì USD giảm giá trong giờ New York; ban đêm thì âm/không đáng kể (+0,95%, không khác 0) |

**Ba mẫu dữ liệu khác nhau, ba phương pháp khác nhau, cùng một hướng: USD mạnh lên trong buổi
sáng châu Âu và yếu đi trong buổi chiều Mỹ.** Đó không phải trùng hợp thống kê — đó là dấu vết
của một dòng tiền cơ cấu.

### 2.3 ⚠️ Replication hiện đại — và phép tính giết chết phiên bản gốc

Ernie Chan / PredictNow (03/2023) chạy lại **đúng luật Breedon-Ranaldo** trên EURUSD, nến M1,
**10/2021 – 01/2023, out-of-sample**:

| | baseline (luật gốc) | + "Corrective AI" |
| --- | --- | --- |
| Lợi nhuận năm | **3,5%** | 4,1% |
| Sharpe | **0,88** | 1,29 |
| MaxDD | −3,5% | −1,9% |
| **Chi phí giao dịch** | **KHÔNG tính** | KHÔNG tính |

➤ PHÉP TÍNH BẮT BUỘC PHẢI LÀM (dùng chi phí đo được của chính ta ở `00_ket_qua_vong_1.md`):

```
EURUSD @ 1,10   →   1 pip = 0,909 bps
chi phí khứ hồi = spread 0,28 pip + commission 0,70 pip = 0,98 pip ≈ 0,89 bps
luật gốc giữ 2 vị thế/ngày = 2 khứ hồi/ngày
  → 2 × 0,89 bps × 252 ngày = 448 bps = 4,5%/năm

3,5% (thô) − 4,5% (chi phí) = −1,0%/năm
```

**Luật Breedon-Ranaldo nguyên bản, trên dữ liệu hiện đại, ở mức chi phí retail: LỖ.**
Và điều này khớp chính xác với Bảng 8 của Krohn: spread đầy đủ → âm, spread 50% → dương.

Hai nguồn hoàn toàn độc lập, hai cách tính, cùng một kết luận về ranh giới khả thi.

---

## 3. Ý kiến thực hành đồng thuận với học thuật

**FXEmpire, tổng kết FX seasonality 2026** — cái gì CÒN chạy, cái gì KHÔNG:

| CÒN CHẠY | ghi chú của nguồn |
| -------- | ----------------- |
| Hiệu ứng "home vs away" trong ngày | nhưng "lợi nhuận khứ hồi trung bình chỉ **vài pip**", rất nhạy với chi phí |
| **Dòng tái cân bằng cuối tháng** | tập trung **quanh London fix của ngày giao dịch cuối cùng**; cơ chế là hành vi tổ chức BẮT BUỘC, "không thể ngừng hay bị hấp thụ dễ dàng" |
| Đảo chiều trong phiên London/NY overlap (~08:00-12:00 NY) | "thật nhưng bé — backtest không chi phí có lãi, rồi **chết một cách thảm khốc** khi cộng chi phí" |

| KHÔNG CHẠY | ghi chú |
| ---------- | ------- |
| Hiệu ứng ngày-trong-tuần | "phần lớn đã biến mất — nếu từng tồn tại" |
| Mùa vụ theo tháng | "thống kê, không phải bảo đảm" (USDJPY mạnh tháng 8 đúng ~68% lịch sử, nhưng sai 2019 và 2020) |

**Robot Wealth — phân loại edge cho trader độc lập** (đồng thuận về cơ chế):
> Edge bền cho trader độc lập thường trông **không hấp dẫn** — nhiễu, khó giao dịch, quá nhỏ để
> tổ chức quan tâm; chúng **gánh rủi ro mà người khác trả tiền để tránh** và **đứng trước những
> dòng tiền lớn có thể đoán trước**. Chính sự không hấp dẫn đó là lý do chúng tồn tại.
> Edge không nằm ở độ chính xác dự báo, mà ở việc **tìm ván chơi nơi người khác có hệ thống sẵn
> lòng trả tiền cho bạn**: thu hoạch risk premia, **dòng tái cân bằng**, mất cân bằng vị thế.

➤ Ba nhóm này đúng khớp với cơ chế inventory-risk của Krohn và crash-risk của carry ở [D]. Toàn
bộ bằng chứng đang hội tụ về **một lớp edge duy nhất: đứng trước dòng tiền cơ cấu bắt buộc.**

---

## 4. Các hướng khác: kiểm tra rồi HẠ mức ưu tiên (kèm lý do)

### 4.1 Currency momentum cắt ngang — Menkhoff, Sarno, Schmeling & Schrimpf, *JFE* 2012
- Chênh lệch cắt ngang tới **10%/năm** giữa đồng thắng và đồng thua trong quá khứ
- Không giải thích được bằng nhân tố rủi ro truyền thống; **giải thích một phần bằng chi phí giao dịch**
- Rất khác carry, và **không tương quan cao với các quy tắc giao dịch kỹ thuật chuẩn**
- ⚠️ Kết luận của chính tác giả: *"dường như có những **giới hạn arbitrage rất hiệu quả** ngăn
  lợi nhuận momentum khỏi bị khai thác dễ dàng trên thị trường tiền tệ."*

### 4.2 Time-series momentum (TSMOM) — suy giảm ngoài mẫu
Moskowitz, Ooi & Pedersen (2012) là nền tảng, nhưng đánh giá out-of-sample sau này cho thấy
Sharpe in-sample chỉ 0,1–0,2 và **lợi thế này sụp ngoài mẫu, Sharpe âm với gần như mọi bộ tham số**.
➤ Kết hợp với [C] (momentum 20/120 ngày, Sharpe 0,79 CÓ chi phí, 20 năm): TSMOM còn giá trị như
**một chân của danh mục chiến lược**, không phải như chiến lược đơn lẻ. Đúng vai trò [C] gán cho nó.

### 4.3 Currency value / PPP — **thang thời gian loại nó khỏi hệ H1**
- Đồng thuận tài liệu (IMF WP/04/128 và panel studies): **half-life của hồi quy tỷ giá thực về
  PPP là 3–5 năm**; PPP deviation bị xói mòn ~**15%/năm**; một nghiên cứu cho median 8 năm với
  nước công nghiệp; chế độ tỷ giá cố định → gần như vĩnh viễn.
- Menkhoff et al. (2014) *Currency Value*: tỷ giá thực **CÓ** dự báo excess return, nhưng
  **theo chiều NGƯỢC với trực giác "value"** — mức định giá cao lại dự báo ngoại tệ TĂNG giá.
  Chỉ sau khi điều chỉnh cho **năng suất** và **chất lượng hàng xuất khẩu** thì mới ra một thước
  đo value hành xử đúng.
- ➤ KẾT LUẬN: chân "PPP" của [D] (Brière & Drut) **không triển khai được trong hệ H1**. Half-life
  4 năm không thể là thành phần của một hệ giao dịch H1 với tần suất có ý nghĩa. Giữ nó như
  **kiến thức về regime** (giải thích *vì sao* carry vỡ), không phải như một chiến lược.

### 4.4 Carry — còn sống, nhưng là thù lao rủi ro đuôi
Nghiên cứu 2025 (CEPR DP20745 và các nguồn khác): **46–77% lợi nhuận carry là bù đắp cho phơi
nhiễm rủi ro sụp (crash exposure)**; >20% phương sai giải thích được của carry kỳ vọng đến từ
crash risk. Carry "không chết", nhưng nó **không phải alpha** — nó là phí bảo hiểm ta bán.
➤ Với tài khoản có ràng buộc drawdown cứng (mô hình FTMO của dự án), bán bảo hiểm đuôi là
lựa chọn cần cân nhắc rất kỹ, không phải mặc định.

### 4.5 Volatility management — chỉnh lại một kết luận của vòng đọc 1
Vòng đọc 1 (§6, từ paper [F]) ghi: inverse-vol scaling thắng HMM timing. Điều đó **đúng nhưng
cần tách hai khẳng định khác nhau**:
- **Inverse-vol SIZING trong một chiến lược** (mỗi thị trường nhận tỷ trọng ∝ 1/σ): tiêu chuẩn,
  và [C] dùng nó **có tính chi phí**, cho Sharpe 0,79 qua 20 năm. → GIỮ.
- **Volatility-managed TIMING toàn danh mục** (Moreira & Muir 2017, scale exposure theo 1/σ²
  tháng trước): in-sample rất tốt, nhưng **Cederburg et al. chứng minh THẤT BẠI ngoài mẫu**, và
  **Barroso & Detzel chứng minh KHÔNG sống sót chi phí giao dịch**. Nguyên nhân: bất ổn cấu trúc
  trong hồi quy nền. → KHÔNG dùng.

### 4.6 London Breakout — không có nền học thuật
Tìm kiếm có chủ đích: mọi nguồn về "London Breakout strategy" là blog/broker/TradingView, **không
có paper bình duyệt nào**. Cơ chế được viện dẫn (UK = ~38% turnover FX toàn cầu theo BIS, biên
độ phiên Á hẹp → phá vỡ mạnh khi London mở) là thật, nhưng **chưa từng được kiểm định độc lập
với chi phí**. Và nó thuộc đúng họ "breakout theo mẫu hình giá" mà vòng 1 đã đo là NO_INFORMATION
trên 3 cặp Tier 1. → Không ưu tiên.

### 4.7 Thực tế chi phí retail — con số cần treo trước mặt
- 71,63% tài khoản FX retail lỗ (trung bình qua 52 broker được quản lý)
- Scalper nhắm 5 pip với spread 2 pip cần **win rate > 70%** chỉ để hoà
- Với chiến lược 52% win / R:R 1:1, chi phí đẩy win-rate hoà vốn lên ~53,4%
- ➤ Toàn bộ bằng chứng nói cùng một điều: **ở FX, thắng hay thua được quyết định ở tầng chi phí,
  không ở tầng tín hiệu.** Đó là lý do `AssetProfile` phải là SSOT và mọi backtest phải đi qua nó.

---

## 5. TỔNG HỢP CUỐI: bốn ứng viên, đã xếp hạng, đã đặc tả trước khi backtest

Nguyên tắc tuân thủ (AFML ch.11 qua `docs/knowledge/research_process.md`): **mô hình phải được
đặc tả ĐẦY ĐỦ trước khi mô phỏng; backtest dùng để LOẠI BỎ, không để cải thiện.** Bốn ứng viên
dưới đây đều lấy nguyên từ nguồn đã bình duyệt, không phải suy ra từ kết quả nào của ta.

### ★ Ứng viên 1 — FIX REVERSAL (ưu tiên cao nhất)
- **Nguồn:** Krohn/Mueller/Whelan, *Journal of Finance* 2024 · xác nhận bởi Breedon & Ranaldo (SNB)
- **Cơ chế:** rủi ro tồn kho của dealer quanh cầu USD vô điều kiện tại các fix
- **Vì sao xếp đầu:** (a) 21 năm, G9, t 5,5–9,2; (b) mọi ngày/tháng/năm trong mẫu; (c) **đúng
  thang giờ — drift kéo dài hàng GIỜ**, khớp H1; (d) cơ chế cơ cấu, không phải mẫu hình giá;
  (e) ba nguồn độc lập trùng khớp
- **Cần đo trước tiên:** mô hình W còn tồn tại trong mid-price 2020-2026 không?
- **Rào phải vượt:** chi phí. Phiên bản 4-lượt/ngày chắc chắn chết. Phải tìm **cửa sổ con có
  drift/chi phí cao nhất** và giảm số lượt khứ hồi.
- **Biến điều kiện có trong paper:** độ lớn đảo chiều **LỚN HƠN sau ngày biến động cao / spread
  cao**. Đây là regime conditioner có cơ sở cơ chế (tồn kho rủi ro hơn → thù lao cao hơn).
- **Ưu tiên cặp:** EURUSD (duy nhất sống sót cả spread CME đầy đủ; và rào chi phí thấp nhất
  trong dữ liệu ta: 2,44%)

### ★ Ứng viên 2 — DÒNG CUỐI THÁNG quanh London fix
- **Nguồn:** đồng thuận thực hành rộng; cơ chế tái cân bằng hedge tổ chức; hàng chục tỷ USD
  notional trong 3 ngày giao dịch cuối tháng
- **Vì sao xếp thứ 2:** cơ chế BẮT BUỘC (không thể tự dừng) — đúng loại "dòng tiền lớn đoán
  trước được" của Robot Wealth; tần suất thấp nên **chi phí gần như không phải vấn đề**
- **Cộng hưởng:** nó tập trung ĐÚNG tại London fix → **giao thoa với Ứng viên 1**. Kiểm định
  giả thuyết "hiệu ứng fix mạnh nhất vào cuối tháng" là một phép thử tự nhiên, gần như miễn phí.
- ➤ Lưu ý cho hệ này: `TomXau` của The Cheopard Forex (Turn-of-Month, D1, evidence 0,90) là cùng
  họ hiệu ứng nhưng trên vàng. Cơ chế FX khác hẳn (tái cân bằng hedge tiền tệ, không phải dòng
  trú ẩn) → phải hiệu chỉnh lại từ đầu, đúng như yêu cầu của anh.

### ☆ Ứng viên 3 — Danh mục chiến lược: momentum D1 + một chân không tương quan
- **Nguồn:** Olszweski & Zhou 2014 (Sharpe 0,79 → **0,98**, MaxDD −17,4% → **−8,95%**, có chi phí, 20 năm)
- **Đã biết trước:** momentum FX ở thang **20/120 ngày**, sizing inverse-vol, **chia đều thắng
  tối ưu hoá**
- **Vấn đề dữ liệu:** chân thứ hai của họ là carry → cần lãi suất, ta chưa có (§2 của tài liệu 01).
  Ứng viên 1 hoặc 2 có thể **thay thế** chân đó: cả hai đều là intraday/flow-based nên gần như
  chắc chắn **không tương quan** với momentum D1 — mà không tương quan chính là toàn bộ giá trị
  của [C].
- **Vai trò của H1:** thực thi tín hiệu D1 (chọn giờ vào lệnh có spread rẻ, dùng cấu trúc phiên)

### ☆ Ứng viên 4 — Cointegration/half-life trên cross tổng hợp (thang cao hơn H1)
- **Nguồn:** Zheng Nan 2025 (quy trình đầy đủ) + Leung & Li 2015 (lý thuyết ngưỡng) + Kim 2019
- **Đã biết trước:** cửa sổ = HL × 4,32; vào khi spread ra ngoài dải RỒI quay vào; time-stop thay
  vì 3σ; lọc β âm và 2/3<|β|<2; **lọc HL < 40-60**
- ⚠️ **Ba cảnh báo nghiêm trọng:**
  1. Bằng chứng ở thang NGÀY (HL 15-52 ngày, giữ 53 ngày) — chưa ai chứng minh ở H1
  2. Chi phí và carry **không được mô hình hoá** trong nguồn; lợi nhuận thô chỉ 3,28%/3,5 năm
  3. **Cross phải tổng hợp từ 2 cặp USD** (EURJPY = EURUSD × USDJPY) → **spread phải CỘNG cả hai
     chân**, và một lệnh pairs-trading = **4 chân** = 4 lần spread. Rào chi phí gấp ~4 lần.
     Cộng thêm bài học [G] (đúng H1, không đạt) → đây là ứng viên **rủi ro cao nhất**.

### ✗ Đã loại trước khi backtest (có lý do, không lặp lại)
| hướng | lý do loại |
| ----- | ---------- |
| PPP / currency value làm chiến lược | half-life 3-5 năm — sai thang thời gian một bậc độ lớn |
| Volatility-managed timing (Moreira-Muir) | thất bại ngoài mẫu (Cederburg) + không sống sót chi phí (Barroso-Detzel) |
| London Breakout | không có nền bình duyệt; cùng họ với thứ vòng 1 đã đo NO_INFORMATION |
| Day-of-week / mùa vụ tháng | đã biến mất theo tổng kết thực hành |
| Chênh lệch chỉ báo (RSI-diff) pairs FX H1 | [G] chạy đúng H1, không đạt |
| ML lọc lệnh trên feature giá/vol/corr | [G] < 60% CV, OOS bất định; `meta_label_prob` AUC 0,42-0,55 |
| TSMOM đơn lẻ | Sharpe âm ngoài mẫu gần như mọi tham số |

---

## 6. Ba nguyên tắc rút ra, sẽ chi phối toàn bộ vòng 2

1. **Edge FX không nằm ở dự báo giá, nó nằm ở việc đứng trước dòng tiền cơ cấu bắt buộc.**
   Hội tụ từ Krohn (inventory risk), Breedon-Ranaldo (order flow doanh nghiệp), month-end
   (tái cân bằng bắt buộc), carry (crash risk premium), Robot Wealth (phân loại edge).
   Vòng 1 đã chứng minh mặt còn lại: mẫu hình giá đơn công cụ = NO_INFORMATION.

2. **Ràng buộc thật là SỐ LƯỢT KHỨ HỒI, không phải chất lượng tín hiệu.**
   Krohn: cùng một tín hiệu — spread đầy đủ thì âm, spread một nửa thì Sharpe 0,7.
   Chan: 3,5% thô, nhưng 2 lượt/ngày = 4,5% chi phí.
   → Mọi thiết kế phải bắt đầu từ **ngân sách chi phí**, rồi mới đến tín hiệu.
   → Chỉ số thiết kế trung tâm: **bps drift thu được / bps chi phí trả ra**, không phải win rate.

3. **H1 là tầng THỰC THI của một edge sinh ra ở thang cao hơn — trừ một ngoại lệ.**
   Ngoại lệ đó là hiệu ứng fix/session: drift *kéo dài hàng giờ*, tức edge **sinh ra ĐÚNG ở thang
   H1**. Đó là lý do Ứng viên 1 được xếp đầu — nó là ứng viên duy nhất trong toàn bộ tài liệu đã
   đọc mà thang thời gian của edge trùng với khung giao dịch chính mà anh chỉ định.

---

## 7. Danh mục nguồn

**Đã đọc toàn văn hoặc phần thực chất:**
1. Krohn, I., Mueller, P. & Whelan, P. (2024). "Foreign Exchange Fixings and Returns around the Clock." *Journal of Finance* 79(1), 541-578. [[JoF](https://onlinelibrary.wiley.com/doi/10.1111/jofi.13306)] [[bản working paper toàn văn](https://sites.insead.edu/facultyresearch/research/file.cfm?fid=66802)] [[SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3521370)]
2. Breedon, F. & Ranaldo, A. (2011). "Intraday patterns in FX returns and order flow." *SNB Working Paper 2011-4*. [[SNB](https://www.snb.ch/public/asset/en/www-snb-ch/publications/research/working-papers/2011/working_paper_2011_04/publications0_en/working_paper_2011_04.n.pdf)] [[SSRN](https://www.ssrn.com/abstract=2099321)]
3. Chan, E. (2023). "Applying Corrective AI to Daily Seasonal Forex Trading." [[epchan.blogspot](http://epchan.blogspot.com/2023/03/applying-corrective-ai-to-daily.html)] [[PredictNow](https://predictnow.ai/applying-corrective-ai-to-daily-seasonal-forex-trading/)]
4. "FX Seasonality: What Still Works For Forex Trading in 2026—and What Doesn't." [[FXEmpire](https://www.fxempire.com/education/article/fx-seasonality-what-still-works-and-what-doesnt-in-2026-1545003)]
5. Krohn, Mueller & Whelan (2018). "FX Premia Around the Clock" (bản sớm hơn). [[AUT ACFR](https://acfr.aut.ac.nz/__data/assets/pdf_file/0007/190753/Krohn_Mueller_Whelan_Jun2018_FXPremiaAroundTheClock.pdf)]

**Đã đọc abstract / kết quả chính:**
6. Menkhoff, L., Sarno, L., Schmeling, M. & Schrimpf, A. (2012). "Currency Momentum Strategies." *JFE*. [[SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1809776)] [[BIS WP 366](https://www.bis.org/publ/work366.pdf)] [[JFE](https://www.sciencedirect.com/science/article/abs/pii/S0304405X12001353)]
7. Menkhoff, Sarno, Schmeling & Schrimpf. "Currency Value." [[SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2492082)]
8. Moskowitz, T., Ooi, Y.H. & Pedersen, L. (2012). "Time Series Momentum." *JFE*. [[NYU Stern](https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf)] [[AQR data](https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Original-Paper-Data)]
9. "When Trend-Following Hits a Wall: New Evidence on the Boundaries of Time Series Momentum." [[Swedroe](https://larryswedroe.substack.com/p/when-trend-following-hits-a-wall)]
10. "(Non-Parametric) Bootstrap Robust Optimization for Portfolios and Trading Strategies" — đánh giá OOS của TSMOM. [[arXiv 2510.12725](https://arxiv.org/pdf/2510.12725)]
11. Moreira, A. & Muir, T. (2017). "Volatility-Managed Portfolios." [[NBER w22208](https://www.nber.org/system/files/working_papers/w22208.pdf)]
12. "On the performance of volatility-managed portfolios" (Cederburg et al.) — thất bại OOS. [[JFE](https://www.sciencedirect.com/science/article/abs/pii/S0304405X2030132X)]
13. FCA. "Fixing the Fix? Assessing the Effectiveness of the 4pm Fix." *Occasional Paper 46*. [[FCA](https://www.fca.org.uk/publication/occasional-papers/occasional-paper-46.pdf)]
14. "Did the Reform Fix the London Fix Problem?" [[NBER w23327](https://www.nber.org/system/files/working_papers/w23327/w23327.pdf)]
15. "FX Market Behaviour during the WM/R Fixing Window, 2015–2019." [[GFXC](https://www.globalfxc.org/uploads/20191204_presentation_wmr_fixing.pdf)]
16. "Foreign Exchange Market Microstructure and the WM/Reuters 4pm Fix." [[arXiv 1501.07778](https://ar5iv.labs.arxiv.org/html/1501.07778)]
17. "To fix or not to fix, the Fix: Reassessing the effectiveness of the 4pm Fix. A pre-registered study." [[Pacific-Basin Fin. J.](https://www.sciencedirect.com/science/article/pii/S0927538X24004049)]
18. Debelle, G. (RBA). "FX Benchmarks." [[BIS](https://www.bis.org/review/r150213c.htm)] [[RBA](https://www.rba.gov.au/speeches/2015/sp-ag-2015-02-12.html)]
19. Panagiotou. "The WMR Fix and its Impact on Currency Markets." [[Norges Bank](https://www.norges-bank.no/contentassets/619c8b75e1ed4ba691e8ad6a006855e6/39-panagiotou---the-wmr-fix-and-its-impact-on-currency-markets-.pdf)]
20. "DP20745 Carry Trade and Currency Crash Risk." [[CEPR](https://cepr.org/publications/dp20745)]
21. "Carry trades and risk factors heterogeneity: Three asymmetries." [[Econ. Letters](https://www.sciencedirect.com/science/article/abs/pii/S0165176525006159)]
22. Lustig, H. & Verdelhan, A. "The Term Structure of Currency Carry Trade Risk Premia." [[NYU Stern](https://w4.stern.nyu.edu/finance/docs/pdfs/Seminars/1901/1901w-verdelhan.pdf)] [[Stanford GSB](https://www.gsb.stanford.edu/faculty-research/publications/term-structure-currency-carry-trade-risk-premia)]
23. "A filtered currency carry trade." [[N. Am. J. Econ. Fin.](https://www.sciencedirect.com/science/article/abs/pii/S1062940821000930)]
24. Lee, S. & Wang, M. "The Impact of Jumps on Carry Trade Returns." [[Georgia Tech](https://www.scheller.gatech.edu/directory/research/finance/lee/pdf/leewang17.pdf)]
25. "Order Flow explains FX Carry Trade Strategies." [[Quantpedia](https://quantpedia.com/order-flow-explains-fx-carry-trade-strategies/)]
26. "FX Carry Trade." [[Quantpedia](https://quantpedia.com/strategies/fx-carry-trade)]
27. "Currency Momentum Factor." [[Quantpedia](https://quantpedia.com/strategies/currency-momentum-factor)]
28. IMF. "Parity Reversion in Real Exchange Rates: Fast, Slow, or Not at All?" *WP/04/128*. [[IMF](https://www.imf.org/external/pubs/ft/wp/2004/wp04128.pdf)]
29. Sarno, L. "Purchasing Power Parity and the Real Exchange Rate." *IMF Staff Papers*. [[IMF](https://www.imf.org/external/pubs/ft/staffp/2002/01/pdf/sarno.pdf)]
30. Taylor, Peel & Sarno. "Nonlinear mean-reversion in real exchange rates." [[UW-Madison](https://users.ssc.wisc.edu/~cengel/Econ872_2008/TaylorPeelSarnoNonlinearPPP.pdf)]
31. "Adjusting toward long-run purchasing power parity." [[J. Int. Money Fin.](https://www.sciencedirect.com/science/article/pii/S0261560624001918)]
32. ECB. "Is reversion to PPP..." *WP 682*. [[ECB](https://www.ecb.europa.eu/pub/pdf/scpwps/ecbwp682.pdf)]
33. ECB. "Real exchange rate forecasting." *WP 1576*. [[ECB](https://www.ecb.europa.eu/pub/pdf/scpwps/ecbwp1576.pdf)]
34. "Intra-day Seasonality in Foreign Exchange Market Transactions." [[arXiv 1103.5664](https://arxiv.org/pdf/1103.5664)] [[MPRA](https://mpra.ub.uni-muenchen.de/3502/)]
35. "Intraday seasonality in activities of the foreign exchange markets: Evidence from the electronic broking system." [[ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0889158306000463)]
36. "Intraday effects of the currency market." [[Int. Rev. Fin. Analysis](https://www.sciencedirect.com/science/article/abs/pii/S1042443117306121)]
37. "Intraday-of-the-week effects: What do the exchange rate data tell us?" [[ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1566014119302031)]
38. "Seasonalities and intraday return patterns in the foreign currency futures market." [[Academia](https://www.academia.edu/22777256/)]
39. "Daily Currency Exchange Pattern." [[CXO Advisory](https://www.cxoadvisory.com/currency-trading/daily-currency-exchange-pattern/)]
40. "Exploiting Business Day Patterns in FX Markets." [[QuantRocket](https://www.quantrocket.com/blog/business-day-fx-patterns/)]
41. "Hidden Markov Models Applied To Intraday Momentum Trading With Side Information." [[arXiv 2006.08307](https://arxiv.org/pdf/2006.08307)]
42. Robot Wealth. "Finding Edges in Trading." [[RW](https://robotwealth.com/finding-edges/)] · "The Art and Science of Trading Carry." [[RW](https://robotwealth.com/the-art-and-science-of-trading-carry/)] · "Risk Premia Harvesting." [[RW](https://robotwealth.com/harvesting-risk-premia/)]
43. Robot Wealth. "Exploring Mean Reversion and Cointegration with Zorro and R" Pt 1-2 (AUD/NZD). [[Pt1](https://robotwealth.com/exploring-mean-reversion-and-cointegration-with-zorro-and-r-part-1/)] [[Pt2](https://robotwealth.com/exploring-mean-reversion-and-cointegration-part-2/)]
44. "Bivariate cointegration of major exchange rates, cross-market efficiency and the introduction of the Euro." [[ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0148619509000393)]
45. "Optimal Entry and Exit with Signature in Statistical Arbitrage." [[arXiv 2309.16008](https://arxiv.org/pdf/2309.16008)]
46. QuantStart. "Cointegrated Time Series Analysis for Mean Reversion Trading with R." [[QuantStart](https://www.quantstart.com/articles/Cointegrated-Time-Series-Analysis-for-Mean-Reversion-Trading-with-R/)]
47. Nguồn dòng cuối tháng: [[Fusion Markets](https://fusionmarkets.com/posts/forex-month-end-flows)] · [[Global-View](https://global-view.com/monthly-report-how-month-end-rebalancing-moves-the-forex-market/)] · [[Pip Theory](https://piptheory.com/research/forex-seasonality)]
48. Daniel, K. & Moskowitz, T. "Momentum Crashes." [[NBER w20439](https://www.nber.org/system/files/working_papers/w20439/w20439.pdf)]
49. "Volatility-managed commodity futures portfolios" — thất bại OOS trên hàng hoá. [[ResearchGate](https://www.researchgate.net/publication/346491869)]
50. Thực tế chi phí retail: [[Trading Commissions guide](https://traderssecondbrain.com/guides/trading-commissions-hidden-cost)] · [[Dukascopy: Forex Spread](https://www.dukascopy.com/swiss/english/marketwatch/articles/forex-spread/)] · [[HyroTrader data-backed guide](https://www.hyrotrader.com/blog/most-profitable-trading-strategy/)]
51. London Breakout (kiểm tra → không có nền bình duyệt): [[QuantConnect](https://www.quantconnect.com/forum/discussion/1597)] · [[Big Ben Breakout PDF](https://cdn2.hubspot.net/hubfs/3799241/Big%20Ben%20Breakout%20Strategy.docx.pdf)]
