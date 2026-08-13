# The Cheopard Forex — Nền tri thức chiến lược Forex (Vòng đọc 1: corpus local)

> Nguồn: `D:\project-learning\documents\forex-strategies` — **10/10 tài liệu đã đọc**.
> Nguyên tắc dự án (`docs/knowledge/knowledge_index.md`): sách/paper > đặc tả > code > suy luận AI.
> Tài liệu này chỉ ghi **cái paper nói** + **cái đo được**, tách riêng khỏi suy luận của tôi
> (mọi suy luận đánh dấu `➤ SUY LUẬN`).

---

## 0. Bản đồ corpus

| #   | nguồn                                     | năm   | chủ đề                                                          | dùng được gì                                      |
| --- | ----------------------------------------- | ----- | --------------------------------------------------------------- | ------------------------------------------------- |
| A   | Zheng Nan, MSc thesis (Univ. Japan)       | 2025  | **Cointegration pairs trading trên FX**                         | quy trình chọn cặp + half-life window + time-stop |
| B   | Leung & Li, arXiv:1411.5062v3             | 2015  | **Optimal double stopping cho spread OU + chi phí + stop-loss** | lý thuyết ngưỡng entry/exit tối ưu                |
| C   | Olszweski & Zhou, J. Deriv. & Hedge Funds | 2014  | **Kết hợp FX momentum + carry**                                 | thiết kế Strategy Portfolio, số liệu 20 năm       |
| D   | Brière & Drut, Amundi WP-005-2009         | 2010  | **Carry vs PPP qua khủng hoảng**                                | Multi-Regime: quy tắc chuyển chiến lược           |
| E   | Dempster & Leemans, Cambridge CFR wp0418  | 2004  | **Hệ FX tự động 3 tầng (ARL/RRL)**                              | kiến trúc phân tầng + hàm utility rủi ro          |
| F   | Daniel, Jagannathan & Kim                 | 2019  | **HMM 2 trạng thái của momentum**                               | regime turbulent/calm, và giới hạn của nó         |
| G   | Jirapongpan & Phumchusri, IEEE            | ~2019 | **Stress-indicator pairs trading FX, khung H1**                 | kết quả ÂM có giá trị cao                         |
| H   | Kim & Kim, _Complexity_                   | 2019  | **Pairs trading + DQN, biên trading/stop-loss động**            | biên động > biên cố định                          |
| I   | Li, Zhao, Hoi & Gopalkrishnan, PAMR       | 2012  | **Online portfolio mean reversion**                             | khái niệm; triển khai KHÔNG dùng được             |
| J   | Haeri et al., JACST                       | 2015  | **Dự báo EURJPY bằng HMM + CART**                               | bất đối xứng hướng vs biên độ                     |

Chủ đề trội của corpus: **relative value / mean reversion / carry / regime** — KHÔNG phải mẫu
hình giá đơn lẻ. Điều này độc lập xác nhận kết luận vòng 1 (`00_ket_qua_vong_1.md`).

---

## 1. [C] Nền tảng quan trọng nhất: momentum + carry, 20 năm, FX majors

Olszweski (Eclipse Capital, quản $500M) & Zhou (WashU). AUD·GBP·CAD·EUR·JPY·NZD·CHF·USD
(88% turnover FX toàn cầu, BIS 2010). Dữ liệu 4/1993–3/2013, **đã gồm commission + slippage**.

**Momentum:** giao MA 20 ngày / 120 ngày. Long khi MA20 > MA120, short khi ngược lại.
**Luôn có vị thế, không có vùng trung tính.** Sizing = nghịch đảo biến động (rolling 1-month σ).

**Carry:** xếp hạng theo lãi suất tiền gửi 3 tháng → long 3 đồng cao nhất, short 3 đồng thấp nhất.

|                | Momentum | Carry   | **50/50 đều** | Min-Var | Max-Utility |
| -------------- | -------- | ------- | ------------- | ------- | ----------- |
| Lợi nhuận năm  | 7,08%    | 5,35%   | 6,25%         | 6,09%   | 5,50%       |
| Std năm        | 8,93%    | 8,49%   | **6,36%**     | 6,31%   | 7,81%       |
| Tháng xấu nhất | −5,53%   | −10,00% | **−4,65%**    | −5,23%  | −5,08%      |
| **MaxDD**      | −17,42%  | −29,16% | **−8,95%**    | −8,41%  | −14,40%     |
| **Sharpe**     | 0,79     | 0,63    | **0,98**      | 0,97    | 0,70        |
| **Calmar**     | 0,41     | 0,18    | **0,70**      | 0,72    | 0,38        |

### Bốn kết luận có sức nặng

1. **Chia đều THẮNG tối ưu hoá mean-variance.** Max-Utility (τ=3) cho Sharpe 0,70 — TỆ HƠN
   cả momentum đơn lẻ, vì sai số ước lượng kỳ vọng lợi nhuận. Min-Var (chỉ dùng phương sai,
   KHÔNG dùng kỳ vọng lợi nhuận) thì tốt bằng chia đều.
   ➤ Xác nhận trực tiếp quyết định cũ của dự án: "không dùng ML để chia tỷ trọng". Và nói rõ
   ranh giới: dùng **biến động** để chia tỷ trọng thì được, dùng **lợi nhuận kỳ vọng** thì không.
2. **Lợi ích lớn nhất là drawdown, không phải lợi nhuận.** −17,4% và −29,2% → **−8,95%**.
   Lợi nhuận thậm chí GIẢM so với momentum đơn (7,08% → 6,25%) nhưng Calmar tăng 71%.
3. **Hai chiến lược cứu nhau ở đúng lúc cần.** Trong 10 tháng tệ nhất của momentum, carry có
   lãi 6/10 và vượt trội 9/10. Ngược lại: momentum có lãi 5/10 và vượt trội **10/10**.
   Tương quan rolling 3 năm dương nhưng THẤP suốt 20 năm.
4. **Momentum FX có edge ở thang 20/120 NGÀY**, tức ~1 tháng vs ~6 tháng. Không phải breakout H1.

---

## 2. [D] Multi-Regime: quy tắc chuyển chiến lược theo khủng hoảng

Brière & Drut (Amundi). 8 đồng phát triển, 28 cặp, 1/1993–12/2009, tái cân bằng THÁNG,
mọi chiến lược **hiệu chỉnh về cùng biến động 5%/năm** (chuẩn thực hành quỹ tiền tệ).

- **CT** = vay đồng lãi thấp nhất, đầu tư đồng lãi cao nhất.
- **PPP** = ước lượng giá trị cân bằng theo Purchasing Power Parity (đệ quy, out-of-sample);
  vay đồng ĐANG ĐẮT, đầu tư đồng ĐANG RẺ, trên từng cặp trong 28 cặp.
- **Định nghĩa khủng hoảng: VIX > (trung bình 3 năm + 0,75σ).** Chỉ dùng dữ liệu thị trường
  → dùng được real-time. Bắt 62/204 tháng = **30% thời gian**.

|                            | CT        | PPP       |
| -------------------------- | --------- | --------- |
| Toàn kỳ Sharpe             | 0,55      | 0,12      |
| Skewness                   | **−1,08** | **+1,19** |
| MaxDD                      | −16,4%    | −7,6%     |
| **Sharpe khi BÌNH LẶNG**   | **0,85**  | **−0,48** |
| **Sharpe khi KHỦNG HOẢNG** | **0,20**  | **+1,09** |

Đảo ngược hoàn toàn. Và chiến lược lai:

|                 | CT     | CTC (carry, nghỉ khi crisis) | **CTPPP (carry↔PPP)** |
| --------------- | ------ | ---------------------------- | --------------------- |
| Lợi nhuận năm   | 6,73%  | 6,28%                        | **8,34%**             |
| Sharpe          | 0,55   | 0,69                         | **0,92**              |
| Skewness        | −1,08  | −0,23                        | **+0,91**             |
| MaxDD           | −16,4% | −5,19%                       | **−5,42%**            |
| Tỷ lệ tháng lãi | 73,5%  | **81,9%**                    | 72,6%                 |

**CƠ CHẾ (quan trọng hơn con số):** carry là "arbitrage tự tăng cường" (Plantin & Shin 2008) —
càng nhiều vốn vào carry, đồng lãi cao càng tăng giá, càng XA giá trị cơ bản (vốn có quán tính
mạnh vì dựa trên chỉ số kinh tế). Khủng hoảng kích hoạt unwind → giá **đột ngột hồi về giá trị
cơ bản**. Nên PPP ăn tiền CHÍNH XÁC lúc carry vỡ. Đây là lý do NHÂN QUẢ, không phải data mining.

➤ SUY LUẬN: đây chính là khuôn cho yêu cầu "Multi-Regime + Strategy Portfolio + Macro drivers".
Và nó cho một bài học ngược trực giác: **CHUYỂN chiến lược (0,92) tốt hơn TẮT bớt (0,69)**.
Hệ vàng cũ chỉ biết tắt (`regimes_allowed`), chưa bao giờ biết chuyển.

⚠️ **Khoảng trống dữ liệu đã xác định:** ta KHÔNG có VIX, KHÔNG có lãi suất, KHÔNG có CPI trong
`D:\data-ticks-train`. Ba thứ này là đầu vào của cả CT lẫn PPP lẫn định nghĩa crisis. Phải giải
trước khi triển khai được §1-§2. Ứng viên proxy nội-FX (chưa kiểm định): sức mạnh JPY+CHF
(trú ẩn) so với AUD+NZD (risk-on) làm thước đo risk-appetite; biến động thực hiện của rổ FX làm
thay thế VIX. MT5 cấp **swap rate** theo symbol ở live = carry đo được trực tiếp, nhưng lịch sử
swap thì không có.

---

## 3. [A] Quy trình cointegration pairs trading trên FX — chi tiết thực thi

16 đồng, quy về cùng mẫu số (JPY). In-sample 2017-2021 chọn cặp; OOS 1/2022–6/2025.

### Quy trình (đúng thứ tự)

1. **Log-price** mọi chuỗi. Ổn định phương sai, biến quan hệ nhân thành cộng, cho phép so sánh
   các cặp có thang giá khác nhau (KRWJPY vs USDJPY).
2. **ADF trên từng chuỗi** — phải KHÔNG bác bỏ unit root (p > 0,05), tức chuỗi là I(1).
   Nếu một cặp tự nó đã dừng thì không cần pairs trading, khai thác trực tiếp.
3. **Johansen** → quan hệ cointegration + hệ số hedge β.
4. **Bộ lọc bắt buộc:**
   - β phải **ÂM** (β dương = long/short cùng chiều = không market-neutral)
   - **2/3 < |β| < 2** — chặn trường hợp một chân áp đảo chân kia thành cược có hướng
   - **loại cặp có cấu trúc carry** (một chân lãi rất thấp, chân kia rất cao) để tách edge
     thống kê khỏi edge lãi suất
5. **Spread:** `S_t = ln(P_x,t) − β·ln(P_y,t) − c`
6. **Half-life từ AR(1):** hồi quy `ΔS_t = α·S_{t-1} + ε` → `HL = ln2 / |ln(1+α)|`
7. **Cửa sổ Bollinger = HL × 4,32.** Hệ số 4,32 = ln(1/0,05)/ln(2) = 2,996/0,693 — thời gian
   để deviation phân rã **95%** thay vì 50%. Không phải số tự chọn.
8. **Ngưỡng ±2σ** trên spread với cửa sổ động đó.
9. **VÀO LỆNH: spread ra NGOÀI dải RỒI QUAY VÀO LẠI** — không vào ngay lúc xuyên dải.
   Chờ dấu hiệu đã bắt đầu hồi, giảm tín hiệu giả khi cặp mất tính mean-reverting.
10. **RA LỆNH: spread cắt đường MA** (đã về cân bằng).
11. **DỪNG LỖ: time-stop = ceil(4,32 × HL) bar, KHÔNG dùng 3σ.**
12. **Sizing:** `β_cash = −β · P_x/P_y` ; `y = notional/(P_x + |β_cash|·P_y)` ;
    chân x = y, chân y = y·β_cash.

### Kết quả — và vì sao phải đọc kỹ

| cấu hình                | P&L        | lợi nhuận | số lệnh | win       | bar/lệnh |
| ----------------------- | ---------- | --------- | ------- | --------- | -------- |
| cửa sổ cố định 252D     | ¥14,3M     | 0,65%     | 120     | 73,3%     | 103      |
| **HL×4,32 + time-stop** | **¥72,1M** | **3,28%** | 225     | **78,2%** | 53       |
| HL×4,32 + stop 3σ       | ¥38,8M     | 1,76%     | 258     | 68,2%     | 47       |

- HL-window vs cố định: P&L **×5**, win 73%→78%, thời gian giữ **giảm một nửa**.
- time-stop vs 3σ-stop: P&L **+85%**, win 68%→78%.
- **Sàng lọc theo half-life là một bộ lọc thật:** lợi nhuận tập trung ở cặp HL < 40 ngày;
  loại HL > 60 ngày sẽ bỏ hết 6 cặp lỗ dai dẳng mà giữ 90% cặp thắng.

⚠️ **Ba giới hạn mà chính tác giả nêu — phải ghi nhớ khi trích số này:**

1. **Chi phí giao dịch và carry KHÔNG được mô hình hoá.** 3,28%/3,5 năm mà chưa trừ chi phí là
   một biên rất mỏng.
2. Cointegration in-sample **không đảm bảo** tồn tại OOS. Ví dụ thất bại chính họ báo:
   - **AUD/NZD**: được coi là cặp pairs-trading kinh điển, LỖ −9%. Nguyên nhân: cú tăng vọt
     biến động 2022-2023 làm β đã hiệu chỉnh trở nên vô hiệu; dải Bollinger tính từ chế độ
     2017-2021 không thích ứng → tín hiệu kích hoạt QUÁ SỚM liên tục.
   - **CNH/KRW**: pass cointegration in-sample, OOS có xu hướng giảm rõ ràng → quan hệ vỡ.
3. Hệ số 4,32 tuy có cơ sở lý thuyết nhưng có thể cần hiệu chỉnh riêng từng cặp.

**Hai điều kiện tác giả kết luận là cần cho thành công:**
(1) tính chất cointegration phải **BỀN** qua các giai đoạn; (2) cointegration và deviation phải
**ĐỒNG THỜI tồn tại** — cặp cointegrate hoàn hảo không có deviation thì không có tín hiệu nào.

Ví dụ cặp tốt nhất (ZARJPY/NOKJPY, +¥21M, win >90%): cả NOK và ZAR đều là đồng
risk-on gắn hàng hoá (NOK–dầu, ZAR–kim loại) → đủ liên hệ để hồi quy về nhau; nhưng phơi nhiễm
hàng hoá khác nhau và không có liên kết kinh tế trực tiếp Na Uy–Nam Phi → đủ khác để lệch tạm
thời. ➤ SUY LUẬN: đó là một tiêu chí CHỌN CẶP có nội dung kinh tế, không chỉ thống kê — "cùng
nhân tố rủi ro, khác nguồn gốc".

---

## 4. [B] Lý thuyết ngưỡng tối ưu — Leung & Li 2015

Spread mô hình hoá bằng OU: `dX_t = µ(θ − X_t)dt + σ dB_t`. Bài toán double stopping (khi nào
vào, khi nào ra) có chi phí giao dịch c, ĉ và mức stop-loss L. **Có lời giải giải tích.**

Bốn kết quả có hệ quả trực tiếp lên thiết kế:

1. **Vùng vào lệnh tối ưu là một KHOẢNG BỊ CHẶN `[a*_L, d*_L]`**, nằm hẳn TRÊN mức stop-loss L
   và hẳn DƯỚI mức thoát tối ưu `b*_L`.
2. **Nếu giá quá GẦN stop-loss thì tối ưu là KHÔNG vào**, dù giá đang rất "rẻ" — vì xác suất
   bị buộc thoát lỗ ngay sau đó rất cao. Hệ quả: **vùng chờ bị NGẮT LÀM HAI ĐOẠN** (disconnected).
3. **Stop-loss NỚI RỘNG ⇒ take-profit tối ưu HẠ XUỐNG** (Proposition 5.3, đơn điệu ngặt). Khi
   hai mức trùng nhau thì thanh lý ngay lập tức là tối ưu ở mọi mức giá.
4. **Mức vào lệnh tối ưu giảm theo chi phí giao dịch** (Proposition 4.6) — chi phí cao đòi
   deviation sâu hơn mới đáng vào.

➤ SUY LUẬN — điểm này đáng để phá bỏ một thói quen: quy tắc "2σ vào, 3σ dừng lỗ" phổ biến
(và chính là cấu hình bị paper [A] đo là TỆ HƠN time-stop) vi phạm kết quả (1) và (2). Vào ở
đúng 2σ khi stop ở 3σ nghĩa là vào ở mép dưới của vùng bị loại trừ. Lý thuyết nói vùng vào
phải nằm **giữa** L và b\*, không sát L.

---

## 5. [E] Kiến trúc phân tầng — Dempster & Leemans 2004 (Cambridge)

Hệ FX tự động 3 tầng. **Đây là tiền lệ học thuật gần nhất với kiến trúc mà dự án muốn.**

**Tầng 1 — tín hiệu (RRL: mạng 1 lớp hồi quy, output ∈ {−1,+1}).** Ba phát hiện quan trọng
độc lập với việc ta có dùng RRL hay không:

- **Thêm 14 chỉ báo kỹ thuật KHÔNG cải thiện hiệu suất**, trừ khi số lượng return quá khứ đưa
  vào quá ít. Tức chỉ báo kỹ thuật chỉ là bộ lọc của cùng một thông tin đã nằm trong chuỗi return.
- **Chi phí giao dịch δ được dùng làm THAM SỐ ĐIỀU CHỈNH, không ghim vào spread thật.** δ cao
  ⇒ đòi lợi nhuận kỳ vọng thô cao hơn mới vào lệnh. δ trở thành một cổng cường độ tín hiệu.
- Đánh giá tín hiệu **HAI LẦN** mỗi bước (trước và sau khi cập nhật trọng số) để dập hiện tượng
  đảo vị thế do dự từ tick sang tick — nguồn chi phí giao dịch khổng lồ.

**Tầng 2 — quản trị rủi ro & hiệu suất, TÁCH KHỎI tín hiệu.** "Tầng 1 nói vị thế nên giữ trong
thế giới lý tưởng; tầng 2 xét các yếu tố rủi ro thế giới thật rồi mới quyết định có giao dịch."

- Trailing stop x điểm dưới/trên giá tốt nhất từng đạt trong đời vị thế.
- **Cool-down sau khi bị stop:** nếu vị thế bị đóng bởi stop TRƯỚC khi mô hình ra tín hiệu thoát,
  thì thị trường vừa hành xử ngoài dự kiến của mô hình → hành vi lệch đó có xu hướng KÉO DÀI →
  phải nghỉ một lúc. ➤ Đây là lý do có nội dung cho cooldown, khác hẳn "chọn 30 phút cho chắc".
- **Cổng cường độ tín hiệu:** dùng output CHƯA lấy dấu, chỉ giao dịch khi |output| > y.
- **Tự động dừng hệ thống** khi drawdown vượt z, kèm cảnh báo.

**Tầng 3 — tối ưu utility động.** Không ghim siêu tham số trước.

```
Σ  = Σ(R_i² · 1{R_i<0}) / Σ(R_i² · 1{R_i>0})
U  = a·(1−ν)·R̄ − ν·Σ            ν = mức e sợ rủi ro của người vận hành
```

Bốn tính chất được thiết kế có chủ ý của Σ:

1. một cú lỗ lớn bị phạt nặng hơn nhiều cú lỗ nhỏ có cùng tổng (chống margin call);
2. so sánh tổng tác động lệnh lỗ với lệnh thắng → ưu tiên equity tăng đơn điệu hơn equity zigzag;
3. dùng TỶ SỐ nên bất biến theo hệ số nhân quy mô;
4. **chỉ phạt return ÂM, không phạt return dương nhỏ hơn trung bình** — vì semivariance quy tâm
   sẽ gán rủi ro CAO HƠN cho chiến lược có vài lệnh siêu lãi (chúng kéo trung bình lên mà không
   đổi phần đuôi dưới). Đây là một lỗi thiết kế hàm mục tiêu rất dễ mắc.

Tối ưu bằng **one-at-a-time random search** (15 giá trị phân phối chuẩn quanh giá trị hiện tại,
chọn tốt nhất) vì không gian 5 chiều quá đắt và utility không trơn.

### Kết quả — và caveat quyết định

EURUSD, dữ liệu M1 từ HSBC interdealer, **1/2000 – 1/2002**. Chỉ giao dịch **9h–17h giờ London**
(giờ spread interdealer < 2 pip). Spread mô phỏng ghim 2 pip.

- **5.104 pip trong 2 năm ≈ 26%/năm.** Buy-and-hold: −1.636 pip (−8%/năm).
- Tỷ lệ đúng hướng **~62%** (sau chi phí).
- **Lợi nhuận ròng trung bình mỗi lệnh: 1,53 – 1,77 pip.** N = 2.600–3.350 lệnh/2 năm.
- Tầng 3 (tối ưu động) **thắng cả bộ tham số tĩnh tối ưu-trong-hindsight** ở mọi mức ν.

⚠️ **Caveat lớn nhất của cả corpus, và chính tác giả tự nêu:** dữ liệu đến 1/2004 cho thấy
**đường lợi nhuận có độ dốc giảm dần**, và họ viết thẳng rằng điều này _"có thể nghĩa là thị
trường ngày càng hiệu quả và ngày càng khó kiếm lời khi chỉ đưa thông tin giá vào hệ thống."_

➤ SUY LUẬN: đây là paper duy nhất trong corpus cho lợi nhuận intraday FX ấn tượng, và nó
(a) dùng dữ liệu 2000-2002, (b) biên ròng chỉ 1,5 pip/lệnh, (c) tự quan sát thấy suy giảm ngay
từ 2004. Với EURUSD ngày nay, spread 0,31 pip + commission 0,70 pip = **1,01 pip chi phí** —
tức chi phí bằng ~2/3 toàn bộ biên ròng mà họ đo được ở thời kỳ dễ hơn nhiều. **Không được dùng
paper này làm cơ sở kỳ vọng lợi nhuận.** Giá trị của nó là KIẾN TRÚC, không phải con số.

---

## 6. [F] HMM momentum — và giới hạn tự thừa nhận của regime model

Daniel, Jagannathan & Kim: HMM 2 trạng thái (calm / turbulent) trên return thị trường + momentum.

- Trong trạng thái **turbulent**: biến động của cả momentum và thị trường **hơn GẤP ĐÔI**;
  beta chiều lên của momentum rất âm (−1,47) so với chiều xuống (−0,40) → convexity âm → đó là
  cơ chế của "momentum crash".
- Trạng thái **calm BỀN HƠN** turbulent. Calm: kỳ vọng thị trường 13,6%/năm, vol 13,9% (Sharpe
  0,98). Turbulent: −6,0%/năm, vol 28,9%.
- Ước lượng **out-of-sample**: mọi cú lỗ momentum > 20% chỉ xảy ra khi xác suất turbulent CAO.
  HMM dự báo đuôi/crash **tốt hơn hẳn** các phương pháp thay thế (kể cả GARCH).

⚠️ **NHƯNG (Table 14, chính họ báo):** chiến lược timing đơn giản dựa trên HMM (vào/ra theo
ngưỡng xác suất) **bị ĐÁNH BẠI** bởi hai cách scale exposure tầm thường — `k/σ_MOM` và
`k/σ²_MOM` (σ tính từ bình phương return ngày trong 6 tháng trước) — cả về Sharpe lẫn appraisal
ratio.

➤ SUY LUẬN, và đây là bài học đắt nhất trong corpus về regime:
**Regime model kiếm tiền ở việc TRÁNH ĐUÔI, không ở việc tăng Sharpe.** Muốn Sharpe thì dùng
inverse-vol sizing — đơn giản, không tham số, mạnh hơn. Điều này khớp với kết quả walk-forward
của chính dự án (lọc theo trạng thái LÀM XẤU Calmar ngoài mẫu: 0,484 không lọc → 0,426 → 0,205)
và biện minh cho thiết kế hiện có: **cổng regime là tầng TỐI ƯU fail-open; tầng AN TOÀN
fail-closed chạy trước nó.** Đừng kỳ vọng regime engine cải thiện lợi nhuận; hãy đo nó bằng
tail risk.

---

## 7. [G] Kết quả ÂM quan trọng nhất: stress-indicator pairs trading FX **trên H1**

Đây là paper duy nhất chạy đúng khung H1 trên FX. Phải đọc trước khi tự làm lại.

**Thiết lập:** dữ liệu MetaTrader 5, 1/2008–12/2018. 15 cặp đã lọc sạch dữ liệu: EURAUD,
EURGBP, AUDCAD, EURCAD, USDCAD, NZDCAD, EURNZD, AUDCHF, GBPCHF, CADCHF, EURCHF, USDCHF,
AUDUSD, GBPUSD, EURUSD. Hai chân của lệnh là hai CẶP TIỀN (không phải hai đồng tiền).

**Luật:**

- `Spread_t = RSI_t(leg1) − RSI_t(leg2)` (Kaufmann gốc dùng Stochastic-14, ngưỡng ±40)
- σ của Spread ước lượng trên 2008-2009 (pretest) → **vào lệnh khi |Spread| > 2σ**
- **thoát khi Spread cắt 0**
- volatility scaling: nếu vol(A) > vol(B) thì size chân B × vol(A)/vol(B)
- In-sample 2010-2014 · ML phase · OOS 2015-2018

**Kết quả:**

- Chiến lược thô: _"The strategy can't generate the cashflow as same as the pairs of airline
  stock"_ — tức trên FX H1 nó KHÔNG chạy như trên cổ phiếu cùng ngành.
- Lọc bằng ML (ANN, XGBoost; chọn feature bằng top-3 tương quan Pearson với Profit;
  brute-force hyperparameter + 10-fold CV; mục tiêu 60% accuracy):
  _"Although we set the goal to achieve the 60% accuracy, the performance is obviously lower
  than target."_ Và OOS: _"the accuracy in out-of-sample data is quite fluctuated."_

➤ SUY LUẬN: hai kết luận trực tiếp cho ta.

1. **Chênh lệch chỉ báo động lượng (RSI difference) là công thức quá thô** để bắt relative value
   trên FX H1. Nó bỏ hẳn phần cointegration/hedge-ratio/half-life mà [A] và [B] chứng minh là
   cần. Đừng lặp lại nó.
2. **Lọc lệnh bằng ML trên feature giá/biến động/tương quan không đạt cả 60% accuracy, và không
   ổn định OOS.** Trùng khớp với kết luận đã có trong repo: `meta_label_prob` test AUC thật chỉ
   0,42–0,55, không đủ căn cứ để gate. Hai bằng chứng độc lập cùng nói một điều.

---

## 8. [H] Biên động thắng biên cố định — Kim & Kim 2019

Pairs trading + Deep Q-Network học chọn **biên vào lệnh VÀ biên stop-loss** đã lượng tử hoá,
theo spread trong từng trading window, thay vì hằng số. Thiết kế reward: thưởng khi đóng lệnh
tại mục tiêu, phạt khi chạm stop-loss hoặc hết window không hồi quy. Có so sánh spread tính
bằng OLS vs TLS, và 6 kích thước (formation window, trading window).

Kết luận: **biên động theo spread cho lợi nhuận cao hơn biên cố định** của pairs trading truyền thống.

➤ SUY LUẬN: đây là điểm hội tụ của **ba nguồn độc lập, ba phương pháp khác nhau**:

- [B] giải tích: ngưỡng tối ưu là hàm của (µ, θ, σ, c, L)
- [A] thực nghiệm: cửa sổ & time-stop theo half-life thắng cố định (P&L ×5, +85%)
- [H] học tăng cường: biên học được thắng biên cố định

→ **Ngưỡng phải suy ra từ động lực mean-reversion đã ước lượng, không được là hằng số.** Ba
phương pháp không liên quan cùng chỉ về một hướng thì đó không phải data mining.
Ngược lại, RL ở đây KHÔNG cần thiết để đạt kết luận đó — [A] đạt cùng kết luận bằng một công
thức đóng. ➤ Ưu tiên công thức đóng (half-life) trước; RL là dặm cuối, không phải dặm đầu.

---

## 9. [J] Bất đối xứng quyết định: HƯỚNG không dự báo được, BIÊN ĐỘ thì được

Haeri et al., EURJPY **daily**, HMM + CART, so với CART thuần và neural network.

| mục tiêu dự báo                  | train | **test**  |
| -------------------------------- | ----- | --------- |
| **HƯỚNG** (tăng/giảm trong ngày) | 55,6% | **53,9%** |
| High − Open > 10 pip             | 91,2% | **89,8%** |
| High − Open > 20 pip             | 79,9% | **82,0%** |
| High − Open > 30 pip             | 68,1% | **72,7%** |
| High − Open > 40 pip             | 58,0% | 66,4%     |

➤ SUY LUẬN — đây là một phát hiện có giá trị thiết kế cao, dù paper không nhấn:
**dự báo hướng cho 53,9% (gần như nhiễu), nhưng dự báo BIÊN ĐỘ đạt 72–90%.** Đó là bất đối xứng
đã biết trong tài chính (biến động có tính cụm và tự tương quan; hướng thì không), nhưng nó chỉ
thẳng vào một lựa chọn kiến trúc:

- Chiến lược đặt cược vào **hướng** sẽ luôn phải chiến đấu với 53,9%.
- Chiến lược monetize **biên độ/biến động có điều kiện** (range expansion, đặt SL/TP theo biên
  độ dự báo, sizing theo vol, chọn giờ giao dịch theo biên độ kỳ vọng) đứng trên 72–90%.
  Và nó khớp chính xác với dữ liệu vòng 1 của ta: cấu trúc **biên độ theo giờ GMT** cực kỳ ổn định
  và mạnh (§1 `00_ket_qua_vong_1.md`), trong khi mọi tín hiệu HƯỚNG đều cho `NO_INFORMATION`.

---

## 10. [I] PAMR — khái niệm dùng được, triển khai KHÔNG dùng được

Online portfolio selection khai thác đảo chiều một-kỳ của price relative: kỳ vừa rồi tăng mạnh
thì giảm tỷ trọng, giảm mạnh thì tăng tỷ trọng; cập nhật kiểu passive-aggressive (giữ nguyên
portfolio nếu loss = 0, "aggressive" tiến tới portfolio mới nếu vượt ngưỡng ε).

⚠️ Bài báo **giả định không có chi phí giao dịch và không có thuế** (§Assumption 1). Với vòng
quay cao và bản chất đảo chiều mỗi kỳ, đây không phải giả định phụ — nó là giả định phá vỡ
tính áp dụng trên FX H1 có spread.

➤ Giữ lại: ý tưởng **đảo chiều tương đối cắt ngang (cross-sectional)** như một họ tín hiệu.
Bỏ: cơ chế cập nhật và mọi con số hiệu suất.

---

## 11. Tổng hợp: cái gì đã được CHỨNG MINH, cái gì bị BÁC BỎ, cái gì còn TRỐNG

### Đã có bằng chứng nhiều nguồn (đáng triển khai)

| kết luận                                                                          | nguồn                        |
| --------------------------------------------------------------------------------- | ---------------------------- |
| Đa dạng hoá cấp CHIẾN LƯỢC cắt MaxDD ~một nửa; chia đều thắng tối ưu hoá          | [C]                          |
| Chuyển chiến lược theo regime > tắt bớt theo regime (Sharpe 0,92 vs 0,69 vs 0,55) | [D]                          |
| Ngưỡng vào/ra/stop phải suy từ động lực mean-reversion, không được là hằng số     | [A][B][H]                    |
| Time-stop theo half-life > stop theo σ                                            | [A]                          |
| Sizing theo nghịch đảo biến động; KHÔNG dùng kỳ vọng lợi nhuận để chia tỷ trọng   | [C][F][G]                    |
| Tách tầng TÍN HIỆU khỏi tầng RỦI RO; cool-down sau stop có cơ sở                  | [E]                          |
| Hàm mục tiêu phải phạt lỗ bất đối xứng, chỉ phạt phần âm                          | [E]                          |
| Vùng vào lệnh không được sát stop-loss                                            | [B]                          |
| Regime model đáng giá ở TRÁNH ĐUÔI, không ở tăng Sharpe                           | [F] + walk-forward của dự án |
| Biên độ dự báo được (72-90%), hướng thì không (53,9%)                             | [J] + vòng 1                 |

### Đã bị bác bỏ bằng bằng chứng (không lặp lại)

| hướng                                                                            | vì sao                                                                 |
| -------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Chênh lệch chỉ báo (RSI/Stochastic difference) làm tín hiệu relative-value FX H1 | [G] chạy đúng H1, không đạt                                            |
| Lọc lệnh bằng ML trên feature giá/vol/corr                                       | [G] < 60% CV, OOS bất định; + `meta_label_prob` AUC 0,42-0,55 của repo |
| Thêm chỉ báo kỹ thuật lên trên chuỗi return                                      | [E] không cải thiện                                                    |
| Tối ưu mean-variance dùng kỳ vọng lợi nhuận                                      | [C] Sharpe 0,70 < 0,79 đơn lẻ                                          |
| Mẫu hình giá đơn công cụ trên FX M30/H1/H4                                       | vòng 1: 28/33 NO_INFORMATION                                           |
| Quy tắc "vào 2σ / dừng 3σ"                                                       | [A] đo tệ hơn time-stop; [B] mâu thuẫn lý thuyết                       |

### Khoảng trống dữ liệu phải giải (chặn triển khai)

1. **Lãi suất / carry** — cần cho [C][D]. Live có swap MT5; lịch sử thì chưa có.
2. **VIX hoặc thước đo risk-aversion** — cần cho định nghĩa crisis của [D].
3. **CPI / PPP** — cần cho chân "fundamental" của [D].
4. **Cặp chéo (crosses)** — `D:\data-ticks-train` chỉ có 7 cặp vs USD + kim loại. [A] và [G] đều
   dùng crosses (EURJPY, AUDNZD, EURAUD…). Crosses tổng hợp được từ hai cặp USD (EURJPY =
   EURUSD × USDJPY) nhưng **spread tổng hợp phải cộng spread hai chân**, không phải spread thật
   của cross — điều này phải mô hình hoá đúng, nếu không sẽ đánh giá quá cao.

### Câu hỏi trung tâm chưa ai trả lời trong corpus

Toàn bộ bằng chứng mean-reversion/cointegration ở [A] đo trên **thang NGÀY** (half-life 15-52
ngày, giữ 53 ngày). Bằng chứng momentum ở [C] ở thang **20/120 ngày**. Bằng chứng carry ở [C][D]
tái cân bằng **theo tháng**. Nguồn duy nhất chạy H1 ([G]) cho kết quả không đạt, và nguồn duy
nhất chạy intraday có lãi ([E]) là dữ liệu 2000-2002 với biên 1,5 pip/lệnh và tự thừa nhận suy giảm.

**Không có nguồn nào trong corpus chứng minh edge FX ở thang H1 trên dữ liệu hiện đại.**

➤ Đây không phải lý do bỏ H1 — đây là lý do định vị H1 đúng vai trò của nó:

```
EDGE  sinh ra ở thang D1+ (cointegration/half-life, momentum 20/120, carry, regime)
H1    là tầng THỰC THI: chọn giờ theo cấu trúc phiên, vào lệnh khi spread rẻ,
      đặt SL/TP theo biên độ H1, quản lý vị thế, kiểm soát rủi ro
```

Đó cũng chính là kiến trúc "H1 giao dịch chính, H4/D1 làm context" — nhưng với chiều nhân quả
được sửa lại: **context không phải bộ lọc, context là NƠI CHỨA EDGE.** H1 không tạo ra edge,
nó bảo toàn edge khỏi bị chi phí và nhiễu ăn mất.
