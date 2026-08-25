# Asia Range Sweep — KẾT QUẢ ĐO LƯỜNG

**Ngày đo:** 25/08/2026 · **Dữ liệu:** M1 dựng từ tick Dukascopy, EURUSD 2015-2026 (11,5
năm), GBPUSD/USDJPY 2020-2026 (6,5 năm) · **Chi phí:** spread THẬT tại phút khớp +
commission $7/lot khứ hồi · **Đường code:** cùng `asia_sweep_core` mà live dùng.

> ⚠️ Bảng số trong tài liệu này là **ảnh chụp**. Nguồn sự thật là `registry.PORTFOLIO`
> và docstring của `h1/asia_sweep.py`. Khi hai bên lệch thì code đúng, tài liệu sửa.

---

## 0. Kết luận trong bốn dòng

|                                                                          |                                                                                                                 |
| ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| Luật "xuyên biên Á rồi đóng lại trong biên thì vào ngược", đứng MỘT MÌNH | **−0,09 đến −0,17 R/lệnh**, t = −2,5 đến −4,2. Bị bác bỏ.                                                       |
| Thêm **cổng MSS** — điều kiện quyết định                                 | hạng A **+0,015 R/lệnh** so với hạng B **−0,56…−0,70**                                                          |
| Luật thoát hiện tại: **TP cố định 1:3, breakeven ở +1R**                 | **+0,0147 R/lệnh**, t = **+0,52** · FORM −0,0023 → OOS +0,0547                                                  |
| Đủ để pass FTMO chưa?                                                    | **Chưa.** +0,48%/năm ở rủi ro 0,35% ⇒ một vòng 10% mất ~21 năm, và MaxDD −11,21% **vượt cả sàn 9% và luật 10%** |

Chiến lược ở `stage = FORWARD_TEST`. Mức rủi ro 0,35% là quyết định của chủ tài khoản,
khai báo ở `registry.PORTFOLIO["dd_floor_override"]`.

---

## 1. Cấu hình sản xuất và số đo

Biên Á 00:00–06:59 UTC · cửa sổ khớp lệnh 07:00–20:00 UTC · **khung phát hiện và khớp
lệnh: H1** · nến H1 xuyên biên rồi ĐÓNG lại trong biên · **MSS xác nhận trong 3 nến** ·
còn chỗ tới biên Á đối diện · ngoài ±30 phút quanh tin lớn · khớp ở giá MỞ nến kế tiếp
NẾN XÁC NHẬN · SL = cực trị nến quét ± đệm · **TP = giá vào + 3R** · **breakeven ở +1R,
đặt tại giá vào + đúng phí khứ hồi** · đóng hết 20:00 UTC.

| Công cụ      |         n | Lệnh/tuần |    Winrate | SL pip | Phí (R) |       R gộp |  **R ròng** |         t |
| ------------ | --------: | --------: | ---------: | -----: | ------: | ----------: | ----------: | --------: |
| EURUSD       |       620 |      1,03 |     44,35% |   27,0 |   0,037 |     +0,0564 | **+0,0177** |     +0,43 |
| GBPUSD       |       323 |      0,96 |     39,94% |   35,0 |   0,042 |     +0,0503 | **+0,0049** |     +0,09 |
| USDJPY       |       313 |      0,92 |     47,60% |   32,2 |   0,041 |     +0,0640 | **+0,0187** |     +0,34 |
| **Rổ 3 cặp** | **1.256** |  **2,91** | **44,03%** |   31,0 |   0,040 | **+0,0567** | **+0,0147** | **+0,52** |

**R:R KHAI 3,00 (hằng số) · R:R THỰC HIỆN 1,32.** Lãi TB thắng +0,873R · lỗ TB thua
−0,660R · winrate hoà vốn 43,1% (đang có 44,0%, biên +0,9 điểm) · Profit Factor 1,040 ·
chuỗi thua dài nhất 14 · giữ trung vị 300 phút · 8/12 năm dương.

**FORM (< 2024-01-01) −0,0023 (n=882) → OOS +0,0547 (n=374).**

⚠️ Đọc hai dòng FORM/OOS trước mọi dòng khác. FORM gần đúng **bằng không** trên 882
lệnh; toàn bộ phần dương nằm ở 374 lệnh OOS. Đó không phải chữ ký overfit thông thường
(thường FORM đẹp, OOS sụp), nhưng nó nói rõ một điều: giai đoạn hiệu chỉnh không có
biên nào, và t = +0,52 toàn mẫu không phân biệt được với ngẫu nhiên.

### Phân bố kết cục — chỉ 3,4% chạm được TP 3R

| Kết cục               |   n |     % | R ròng TB |
| --------------------- | --: | ----: | --------: |
| TIME (đóng 20:00 UTC) | 735 | 58,5% |    +0,306 |
| SL                    | 352 | 28,0% |    −1,041 |
| BE (breakeven)        | 126 | 10,0% | **0,000** |
| TP (3R)               |  43 |  3,4% |    +2,948 |

Nguyên nhân cơ học: SL trung vị 31 pip nên TP 3R cách 93 pip, và một chiến lược đóng
trong phiên chỉ còn khoảng 4 giờ để đi hết khoảng đó. Mức BE ra đúng 0,000 R vì nó được
đặt tại giá vào **cộng đúng phí khứ hồi thật của chính lệnh đó**.

### Quy ra tiền — tài khoản $100.000, lãi kép trên 4.212 ngày

| Rủi ro/lệnh           |    Lãi/năm | MaxDD từ đỉnh | Ngày tệ nhất | Ghi chú                          |
| --------------------- | ---------: | ------------: | -----------: | -------------------------------- |
| 0,20%                 |     +0,30% |        −6,47% |      −0,629% |                                  |
| 0,25%                 |     +0,36% |        −8,06% |      −0,787% | mức có đệm                       |
| 0,27%                 |     +0,39% |        −8,70% |      −0,849% | **TRẦN tuân thủ sàn 9%**         |
| 0,30%                 |     +0,42% |        −9,64% |      −0,944% | vượt sàn 9%                      |
| **0,35% (đang dùng)** | **+0,48%** |   **−11,21%** |  **−1,101%** | **vượt sàn 9% VÀ luật FTMO 10%** |

### Đối chiếu hạn mức FTMO ở mức đang dùng

|               |     Đo được |                              Hạn mức |                 |
| ------------- | ----------: | -----------------------------------: | --------------- |
| MaxDD từ đỉnh | **−11,21%** |     sàn nội bộ −9,00% · luật −10,00% | **VƯỢT CẢ HAI** |
| Ngày tệ nhất  |     −1,101% | trần nội bộ −4,00% · mốc FTMO −5,00% | ĐẠT             |
| Lãi/năm       |      +0,48% |                   mục tiêu FTMO +10% | **KHÔNG ĐẠT**   |

Mức 0,35% là quyết định của chủ tài khoản sau khi đã được trình bày bảng trên, với lập
luận rằng kết quả backtest chỉ mang tính tham khảo. Quyết định ghi ở
`registry.PORTFOLIO["dd_floor_override"]`, và
`tests/test_portfolio_single_leg.py::test_breaching_the_internal_floor_must_be_declared`
đòi khoá đó phải tồn tại khi MaxDD vượt sàn — nên việc vượt sàn không đi qua âm thầm.

Và MaxDD thật sẽ còn sâu hơn −11,21%: backtest không có trượt giá, không có spread
giãn, không có gap cuối tuần, không có lệnh bị broker từ chối.

---

## 2. MỘT LỖI KẾ TOÁN ĐÃ LÀM MỌI SỐ TRƯỚC ĐÓ SAI

Đây là mục quan trọng nhất của tài liệu, vì nó vô hiệu hoá một kết luận đã từng được
ghi vào registry.

Nhánh thoát cũ có chốt-một-phần: khi `tp1_frac = 0` và `be_after_tp1 = False`, một lệnh
chạm mức chốt-một-phần rồi bị **dừng lỗ GỐC** quét được ghi **0 R thay vì −1 R**. Nhánh
`TP1_BE` cộng `r_locked` (đang bằng 0) rồi thoát, không trừ 1 R. 22 trong 453 lệnh rơi
vào nhánh đó.

Kiểm chứng số học: 22 × (−1,05 − (−0,044)) / 453 = **−0,0488 R/lệnh**, và kỳ vọng đã
báo cáo +0,0903 trừ 0,0488 bằng **+0,0415** — khớp với **+0,0417** đo lại bằng đường
code đã sửa.

|                                           | Đã báo cáo |        Đúng |
| ----------------------------------------- | ---------: | ----------: |
| R ròng/lệnh (luật TP theo thanh khoản H1) |    +0,0903 | **+0,0417** |
| t                                         |      +1,99 |       ~+0,9 |
| MaxDD @ 0,60% (lãi đơn)                   |     −8,17% | **−13,68%** |

**Hai hậu quả:**

1. Kết luận "một SL một TP (+0,0893) tốt hơn chốt-một-phần (+0,0124)" là **sai ở cả hai
   đầu**. Đo lại bằng đường code đúng cho kết quả **ngược** ở phần breakeven: BE ở +1R
   cho +0,0147 R/lệnh so với +0,0101 khi tắt BE, và MaxDD giảm rõ rệt.
2. Lớp lỗi này **không có triệu chứng nào khác**: số lệnh đúng, winrate đúng, đường
   equity trông hợp lý. Chỉ một bất biến kế toán mới bắt được nó.

Bài học đã thành test — `tests/test_asia_sweep.py`:

- `test_stopped_out_trade_loses_exactly_one_r` — lệnh bị dừng lỗ GỐC quét phải là −1 R gộp, không bao giờ 0 R
- `test_breakeven_exit_nets_exactly_zero` — chạm BE phải ra đúng 0 R **sau phí**
- `test_target_exit_pays_exactly_the_declared_rr` — chạm TP phải ra đúng 3,0 R gộp
- `test_every_outcome_is_one_of_the_four_declared` — bốn kết cục, không có nhánh thoát nào không ai khai

---

## 3. MỘT BỘ LỌC ẨN, phát hiện khi dọn code

Khi xoá nhánh chốt-một-phần, điều kiện `rw1 <= 0` mất theo — và nó **là một bộ lọc
thật**, chỉ tình cờ được biểu đạt qua mức TP1.

Nó loại lệnh mà **giá vào đã đi hết biên Á sang phía đối diện**. MSS có thể xác nhận
muộn tới 3 nến sau cú quét, và trong khoảng đó giá có thể đã chạy xuyên cả biên — vào
lệnh lúc đó là BÁN ở đáy biên, đúng chiều mà sai hoàn toàn về vị trí.

|                            |     n | R ròng/lệnh |
| -------------------------- | ----: | ----------: |
| Không có cổng              | 1.856 | **−0,0177** |
| Có cổng (`min_room_r = 0`) | 1.256 | **+0,0147** |

600 lệnh, và chúng kéo chiến lược từ dương sang âm. Nay nó là điều kiện có tên
(`min_room_r`, setup xấu #8) với lý do cơ học viết ra, không còn là hệ quả phụ của một
mức TP không dùng nữa.

Quét ngưỡng cho thấy vì sao **không** được chọn 0,5R dù nó tốt hơn:

| `min_room_r` |     n |      R ròng |    FORM |     OOS |
| -----------: | ----: | ----------: | ------: | ------: |
|          0,0 | 1.256 |     +0,0147 | −0,0023 | +0,0547 |
|          0,5 |   476 | **+0,0491** | +0,0369 | +0,0756 |
|          1,0 |   150 | **−0,0652** | −0,0201 | −0,1367 |
|          1,5 |    52 |     +0,0105 | +0,0511 | −0,0334 |
|          2,0 |    19 |     −0,3212 | −0,4319 | −0,1689 |

**Không đơn điệu** — 0,5R tốt, 1,0R sụp, 1,5R bật lên. Đó là chữ ký nhiễu, không phải
một ngưỡng thật. Giữ 0,0 vì nó là con số có lý do cơ học ("giá chưa đi hết biên"), không
phải con số chọn theo kết quả.

---

## 4. Luật thoát — bảng đo các biến thể

Cùng 1.256 lệnh, chỉ khác cơ chế thoát, ở rủi ro 0,60% (lãi đơn) để so tương đối:

| Cơ chế thoát                    |   Winrate |        PF | R ròng/lệnh |         t |   MaxDD |
| ------------------------------- | --------: | --------: | ----------: | --------: | ------: |
| **TP 3R + BE ở 1R (đang dùng)** | **44,0%** | **1,040** | **+0,0147** | **+0,52** | −19,66% |
| TP 3R, không BE                 |     43,6% |     1,025 |     +0,0101 |     +0,34 | −28,34% |
| TP 3R + BE 1R + trailing 1R     |     48,2% |     1,024 |     +0,0088 |     +0,33 | −15,93% |
| TP 3R + BE ở 1,5R               |     43,7% |     1,023 |     +0,0093 |     +0,31 | −28,06% |
| TP 3R + BE ở 2R                 |     43,6% |     1,025 |     +0,0102 |     +0,35 | −28,88% |
| TP 2R + BE 1R                   |     44,1% |     0,998 |     −0,0006 |     −0,02 | −25,35% |
| TP 4R + BE 1R                   |     43,9% |     1,025 |     +0,0094 |     +0,33 | −20,42% |
| TP 1,5R + BE 0,75R              |     44,0% |     0,934 |     −0,0230 |     −0,96 | −31,71% |

**BE ở 1R là điểm tốt nhất trong cả hai chiều**: kỳ vọng cao nhất (+0,0147) và MaxDD
thấp hơn hẳn bản không BE (−19,66% so với −28,34%). Trailing 1R đổi kỳ vọng lấy thêm
drawdown thấp hơn nữa (−15,93%) — một đánh đổi có thể chọn nếu ràng buộc là drawdown.

TP 2R kém hơn cả TP 3R và TP 4R, tức không có một "TP tối ưu" đơn điệu — dấu hiệu nữa
rằng biên ở đây rất mỏng.

---

## 5. Cổng MSS — chênh 0,7 R mỗi lệnh

Cùng bộ luật, chỉ khác việc CÓ đòi một nến H1 sau đó ĐÓNG vượt cực trị vi mô ngược
chiều cú quét (trong 3 nến) hay không:

| Hạng              |     n | Winrate |       R ròng/lệnh |                     t |
| ----------------- | ----: | ------: | ----------------: | --------------------: |
| **A** (có MSS)    | 1.256 |   44,0% |       **+0,0147** |                 +0,52 |
| **B** (không MSS) | 2.437 |  15–19% | **−0,56 … −0,70** | −22,4 / −16,9 / −13,7 |

MSS không phải một chỉ báo trang trí — nó là điều kiện phân biệt cú quét THẤT BẠI
(giá đảo và xác nhận bằng một close) với cú quét THÀNH CÔNG (giá chảy tiếp, đúng như
Osler dự đoán). Không có nó, luật này là một cái máy mất tiền có ý nghĩa thống kê.

Ngưỡng 3 nến lấy từ mẫu **hikkake** của Chesler (2004), qua Kirkpatrick & Dahlquist
(2011) tr. 379–380 — mẫu fade-breakout-giả DUY NHẤT trong kho có ngưỡng số.

## 6. Bản KHÔNG có cổng MSS — bị bác bỏ

Luật đo: nến M15 trong 07:00–16:00 UTC xuyên biên ≥ max(2,0 pip; 5% biên Á) rồi ĐÓNG
lại trong biên · SL = cực trị nến quét + 3,0 pip · TP = biên Á đối diện.

|                 |     EURUSD |     GBPUSD |     USDJPY |
| --------------- | ---------: | ---------: | ---------: |
| Số lệnh         |      2.407 |      1.411 |      1.145 |
| Winrate         |      32,3% |      29,8% |      19,5% |
| **R/lệnh GỘP**  | **+0,007** | **−0,044** | **−0,008** |
| **R/lệnh RÒNG** | **−0,090** | **−0,170** | **−0,127** |
| t (ròng)        |      −2,97 |      −4,19 |      −2,48 |

**R gộp ≈ 0 trên cả ba cặp** — không phải "biên nhỏ bị chi phí ăn", mà là không có
biên nào. `winrate × R:R ≈ 1` là chữ ký bước đi ngẫu nhiên.

### 6.1 Lưới bộ lọc — 0 ô đạt ý nghĩa dương

54 ô có n ≥ 30: **5 ô dương (9,3%)**, **0 ô có t > +2,0**, **26 ô có t < −2,0**.
Aronson (2007, ch. 6) nói ở p < 0,05 phải kỳ vọng ~5% ô dương do may mắn. Đây không
phải "chưa tìm ra ô đúng" — đây là kỳ vọng âm phủ khắp lưới.

Ba bộ lọc được khuyến nghị rộng rãi đo được là **NGƯỢC DẤU**:

| Bộ lọc                                         | Khuyến nghị | Đo được                                                                               |
| ---------------------------------------------- | ----------- | ------------------------------------------------------------------------------------- |
| Chỉ fade THUẬN xu hướng H1                     | bắt buộc    | thuận TỆ HƠN ngược ở cả 3 cặp: −0,120 vs −0,065 · −0,197 vs −0,150 · −0,177 vs −0,090 |
| Nến quét đóng ở nửa đối diện (Wyckoff tr. 209) | bắt buộc    | nửa ĐÚNG tệ hơn nửa SAI ở cả 3 cặp                                                    |
| Bỏ biên Á rộng                                 | bắt buộc    | không nhất quán: biên rộng tốt nhất trên EURUSD/USDJPY, tệ nhất trên GBPUSD           |

Gộp mọi bộ lọc theo khuyến nghị (thuận H1 + sâu 5–25 pip + 07–09 UTC + đóng nửa đúng):
n = 515 · R ròng **−0,132** · FORM −0,066 → **OOS −0,313**. Gộp lọc làm TỆ HƠN.

### 6.2 Định nghĩa cửa sổ phiên Á — 0/24 ô dương

| Cửa sổ (UTC)                           | EURUSD | GBPUSD | USDJPY |
| -------------------------------------- | -----: | -----: | -----: |
| 00-07                                  | −0,090 | −0,170 | −0,127 |
| 00-06                                  | −0,058 | −0,161 | −0,154 |
| 01-05 (= ICT 20:00–00:00 EST mùa đông) | −0,060 | −0,168 | −0,181 |
| 23-07                                  | −0,089 | −0,176 | −0,128 |
| 22-07 (CBDR + Á)                       | −0,092 | −0,169 | −0,133 |
| 00-08                                  | −0,108 | −0,220 | −0,200 |
| 02-06                                  | −0,071 | −0,156 | −0,175 |
| 01-07                                  | −0,096 | −0,147 | −0,142 |

**0/24 ô dương · 24/24 ô có t < −2,0**, kể cả cửa sổ ICT gốc.

---

## 7. Vì sao "biên Á bị quét" tự nó không phải thông tin

Đo tần suất quét và hai control theo đúng thiết kế RRN-vs-RAN của Osler:

|                                              |    EURUSD | GBPUSD | USDJPY |
| -------------------------------------------- | --------: | -----: | -----: |
| Phiên có quét biên Á                         | **99,4%** |  99,2% |  94,2% |
| Control: mức BẤT KỲ cách biên 0,35 × biên độ |     91,6% |  90,5% |  71,8% |
| Control: biên Á của phiên d−5                |     92,5% |  92,1% |  89,3% |
| Độ sâu xuyên trung vị                        |  1,85 pip |   2,15 |   2,05 |
| Reclaim trong ≤ 30 phút                      |     89,2% |  89,5% |  91,1% |

"Break rate 99,4%" là **hình học biến động**, không phải hiệu ứng thanh khoản: cửa sổ
London 9 tiếng đương nhiên rộng hơn cửa sổ Á 7 tiếng, nên gần như mọi mức quanh đó đều
bị chạm. Một mức bất kỳ cũng bị chạm 91,6%. Độ sâu trung vị 1,85 pip cho thấy phần lớn
"cú quét" chỉ là nhiễu quanh biên.

Đây đúng lỗ hổng của nguồn định lượng công khai duy nhất về hướng này
(tradingstats.net, 12.372 phiên index futures, break rate 93–95%): **không có mô hình
null.** Ở đây null đã được dựng, và nó giải thích gần hết con số.

Cái thật sự phân biệt là **cú quét THẤT BẠI** — nhánh KHÔNG đóng lại trong biên chảy
tiếp **+17 đến +23 bps/60 phút**, nhánh CÓ đóng lại cho −0,5 đến −4,0 bps.

---

## 8. Osler bị trích sai trong tài liệu tham khảo — bản gốc nói ngược

> Osler (2003) _Stop-Loss Orders and Price Cascades in Currency Markets_, FRBNY Staff
> Report 150. USD/JPY · USD/DEM · GBP/USD, quote phút-theo-phút, giờ New York
> 09:00–16:00, 01/1996–04/1998. Stop-loss = 43% khối lượng lệnh, 45% giá trị.
> `references/Carol_Osler_FED_NY_sr150_StopLoss_Orders.md`

| Osler thật sự đo được                   | Con số                                                                                                                                                             | Ý nghĩa                                                            |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| Cụm STOP-LOSS làm giá **CHẢY TIẾP**     | USD/DEM đi 0,061% trong 15 phút sau khi XUYÊN mốc tròn vs 0,054% sau mốc bất kỳ (p < 0,001%)                                                                       | cú quét biên Á, nơi stop bán lẻ nằm ngay bên ngoài, phải chảy TIẾP |
| Hiệu ứng chảy tiếp bền                  | còn ý nghĩa **≥ 2 GIỜ**                                                                                                                                            | đây là cái giao dịch được                                          |
| Đảo chiều thuộc cụm TAKE-PROFIT, và NHỎ | 59,3% tại mốc tròn vs 54,8% tại mốc bất kỳ = **+4,5 điểm %**                                                                                                       | không đủ bù một lượt khứ hồi                                       |
| Cửa sổ đảo chiều NGẮN                   | còn ý nghĩa **< 30 PHÚT** (Bảng VIII.A)                                                                                                                            | trên H1 đó là NỬA nến                                              |
| Vị trí cụm lệnh                         | stop-loss NGOÀI mốc tròn (14,3% đuôi [01,10] vs 6,9% đuôi [91,00]); take-profit ĐÚNG mốc (9,9% vs 3,8%); lệnh ≥ $50M: 62% giá trị stop trong đuôi [90,100]/[01,09] | túi stop nằm trong ~10 pip                                         |
| Thanh khoản thấp → hiệu ứng MẠNH hơn    | chiều New York mạnh hơn sáng New York dù lệnh mở ít hơn                                                                                                            | phiên Á đáng quan tâm                                              |

Bản đo này **xác nhận Osler**, không xác nhận luật fade nguyên bản. Và nó giải thích
vì sao cổng MSS lại quan trọng: MSS chính là bằng chứng ĐO ĐƯỢC rằng cascade đã KHÔNG
xảy ra.

Lưu ý về hệ quả kiến trúc: cửa sổ đảo chiều < 30 phút giải thích vì sao **khớp lệnh
trên H1 lại TỐT HƠN M15** dù H1 vào muộn hơn — không phải vì H1 nhanh hơn, mà vì SL
neo vào cực trị nến H1 rộng gấp ba (28 pip vs 10,6 pip), nên cùng số pip chi phí chỉ
còn chiếm 0,046 R thay vì 0,114 R.

---

## 9. Toàn bộ bằng chứng học thuật

**PHẢN BÁC hướng fade** (mọi nguồn đều có dataset và phương pháp):

| Nguồn                                                              | Mẫu                                                   | Kết quả                                                                                                                                                                                                |
| ------------------------------------------------------------------ | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Neely & Weller (2003)**, _J. Int. Money & Finance_ 22(2):223-237 | FX intraday, GP + linear forecast, OOS                | _"When realistic transaction costs and trading hours are taken into account, we find **no evidence of excess returns**"_                                                                               |
| **Hsu, Taylor & Wang (2016)**, _J. Int. Economics_ 102:188-208     | 30 tiền tệ DM+EM, **45 năm**, > 21.000 luật, Step-SPA | _"virtually no traditional rule significant in the 2006-2015 sub-sample"_ — họ **channel/range breakout đã chết**                                                                                      |
| **Curcio & Goodhart (1992)**, LSE FMG DP 142                       | DEM/GBP/JPY vs USD, nến GIỜ, 04–06/1989               | lợi nhuận theo **HƯỚNG PHÁ VỠ** luôn dương, t = 1,27–2,85, sống sót chi phí 0,03%/lượt. Mức S/R họ dùng được cập nhật ĐÚNG tại giờ mở London và Tokyo. **Luật theo mốc tròn KHÔNG sinh lời, lỗ ở JPY** |
| **Crabel** qua Kirkpatrick & Dahlquist (2011) tr. 388              | S&P futures 1982-1986                                 | sau NR2 giá **không quay lại** open; setup wide-range **thua xa** setup NR; **breakout xuyên SỚM thành công CAO HƠN**                                                                                  |
| **Grimes (2012)** tr. 183                                          | định tính                                             | gọi kế hoạch "đảo chiều khi mức phá vỡ không giữ" là **"a futile plan"**                                                                                                                               |
| **Chan (2013)** tr. 167-168                                        | tóm lược Osler                                        | khi S/R bị xuyên, giá **đi tiếp** do cụm stop                                                                                                                                                          |
| **Aronson (2007)** ch. 6                                           | 6.402 luật trên S&P 500                               | luật tốt nhất p = 0,0005 đơn luật → **0 luật** sống sót hiệu chỉnh data-mining                                                                                                                         |

**ỦNG HỘ** — hai nguồn, cả hai không có kiểm định:

| Nguồn                                                               | Nội dung                                                                                                                                 | Hạn chế                                                                                                                                                                             |
| ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Lien (2008)** tr. 69, Wiley                                       | _"large investment banks and hedge funds are known to try to use the Asian session to **run important stop and option barrier levels**"_ | cơ chế, **không kèm số**                                                                                                                                                            |
| **tradingstats.net** (01/05/2026)                                   | NQ/ES/YM/RTY, 12.372 phiên-công cụ, 2014-2026, có Wilson 95% CI. Break rate 93-95%, reversion 96,8-97,4%                                 | **index futures, KHÔNG phải FX**; **không có mô hình null**; **không chi phí**; reversion là TỶ LỆ CHẠM không phải kỳ vọng; đuôi trôi (100% ext 29,4% toàn mẫu → 17-21% cửa sổ gần) |
| **Chesler (2004)** hikkake, qua Kirkpatrick & Dahlquist tr. 379-380 | đảo chiều phải xảy ra **trong 3 nến**                                                                                                    | không có thống kê FX — nhưng đây là nguồn của `mss_max_bars = 3`                                                                                                                    |

Nguồn **liquidityscan.io**, **pinescriptforge.com**, và các bài "winrate 85-92%" đều
không có n, giai đoạn, chi phí, hay phương pháp — không dùng làm bằng chứng.
`pinescriptforge.com` tự khai "310 chiến lược × 64 công cụ = 19.840 backtest", đúng cấu
trúc quét lưới không hiệu chỉnh đa kiểm định mà Aronson bác.

---

## 10. Các hướng đã đo và bác bỏ

Đầy đủ lý do và số đo ở `registry.REJECTED_DIRECTIONS`. Danh sách đó chỉ chứa hướng
bị bác bỏ **bằng bằng chứng** — nhánh chốt-một-phần KHÔNG có mặt ở đó, vì bản hiện
thực của nó chứa lỗi kế toán nên chưa từng được đo hợp lệ. Bài học của nó nằm ở §2 và
ở docstring `asia_sweep_core.simulate_path`, chỗ bất biến sống.

| Tên                                 | Kết luận                                                                          |
| ----------------------------------- | --------------------------------------------------------------------------------- |
| `AsiaSweepFade_NoConfirmation`      | luật fade đứng một mình: 0/54 ô lọc đạt t>+2, 0/24 cửa sổ dương                   |
| `AsiaSweepExecutionOnM15`           | M15 cho SL 10,6 pip nên phí chiếm 0,114 R; H1 cho 28 pip nên chỉ 0,046 R          |
| `AsiaSweepMssWindow6Bars`           | nới cửa sổ MSS 3→6 nến thêm tần suất, nhưng 3 có nguồn còn 6 là chọn theo kết quả |
| `AsiaSweepMinRoom_HalfR`            | ngưỡng 0,5R tốt hơn nhưng bề mặt KHÔNG đơn điệu (nhảy dấu hai lần) — xem §3       |
| `AsiaSweepBiasFilter_TrendAligned`  | "chỉ fade thuận H1" tệ hơn ngược ở cả 3 cặp                                       |

---

## 11. Xung đột với yêu cầu 4–8 lệnh/tuần

Trên H1 với ba cặp, tần suất bị chặn cứng bởi số phiên có nến H1 vừa xuyên biên, vừa
đóng lại trong biên, VÀ có MSS xác nhận trong 3 nến.

| Preset | Lệnh/tuần | R ròng/lệnh |
| --- | ---: | ---: |
| **MSS (đang bật)** | **2,91** | **+0,0147** |
| FREQ (nhận cả hạng B) | 7,90 | −0,0835 |
| SPEC (ngưỡng hẹp của tài liệu tham khảo) | 0,58 | −0,1654 |

Preset đang bật cho **2,91 lệnh/tuần = 0,58 lệnh mỗi ngày giao dịch**, và con số đó cần
đọc đúng: trần lý thuyết là 3 cặp × 1 lệnh/phiên = **3 lệnh/ngày**, nên 2,91/tuần chỉ
là **19% của trần**. Phân bố số lệnh trong một phiên: 81,3% phiên có 1 lệnh · 15,0% có
2 · 3,7% có 3. Không phiên nào phát hơn một lệnh trên cùng một cặp
(`test_no_more_than_one_trade_per_session` ghim điều đó).

TP cố định 3R làm số lệnh tăng 2,8 lần so với TP theo cấu trúc giá (453 → 1.256), vì
khi mọi lệnh có cùng R:R thì không còn cổng nào lọc theo R:R được nữa. Tỷ lệ phiên có
tín hiệu đi từ 7% lên 20%.

Đạt 4–8 lệnh/tuần đòi nhận hạng B, và hạng B mất **0,65 R mỗi lệnh** với t = −22.

Đường HỢP LỆ duy nhất để tăng tần suất mà không nhận hạng B: **thêm cặp**. Bốn cặp Tier
2 (AUDUSD, USDCAD, USDCHF, NZDUSD) hiện KHÔNG có parquet M1 trong
`D:/data-ticks-train/_m1/` — phải dựng lại từ tick trước.

---

## 12. Còn phải làm trước khi cấp vốn

1. **Sáu kiểm định + cổng PBO** ở `docs/knowledge/research_process.md`, chạy bằng
   `src/python/research/validation/`. Chưa chạy vòng nào. Với t = +0,52 và FORM ≈ 0,
   khả năng cao nó không qua được — nhưng chưa chạy thì chưa biết.
2. **Hạ rủi ro về 0,27%** nếu muốn tuân thủ sàn nội bộ 9%. Mức đang dùng 0,35% cho
   MaxDD −11,21%, vượt cả luật FTMO 10%; quyết định được khai báo ở
   `registry.PORTFOLIO["dd_floor_override"]`.
2. **Đo spread thật trên tài khoản sẽ giao dịch** — `scripts/check_symbol_spec.py`.
   Số hiện tại là spread Dukascopy, không phải spread broker.
3. **Bốn con số rủi ro** trong `registry.PORTFOLIO["can_do_lai"]` được hiệu chỉnh cho
   một danh mục sizing theo tỷ trọng; phải đo lại cho sizing theo khoảng cách SL.
4. **Cổng parity** — `execution/parity.py` được dựng cho một họ chiến lược khác và
   hiện ném `NotImplementedError`. Phần thoát đã có parity tuyệt đối (một SL, một TP
   trên server), nhưng đoạn `order_plan → order_router → broker` vẫn chưa có vòng
   replay nhiều nghìn nến.

## 13. Tái lập

```powershell
.\.venv311\Scripts\python.exe research\fx\asia_sweep_lab.py        # hiện tượng + control
.\.venv311\Scripts\python.exe research\fx\asia_sweep_filters.py    # lưới bộ lọc
.\.venv311\Scripts\python.exe research\fx\asia_sweep_calibrate.py  # tần suất
.\.venv311\Scripts\python.exe -m src.python.strategies.h1.asia_sweep   # thẻ luật + live
.\.venv311\Scripts\python.exe -m pytest -q tests\test_asia_sweep.py
```

CSV: `reports/fx_research/asia_sweep_*.csv`

## 14. Ghi chú về tài liệu tham khảo

- Tài liệu ICT 2022 **không có winrate, không R:R, không mẫu thống kê nào** trong toàn
  sách; mọi ngưỡng biên độ/stop tính bằng **điểm ES/NQ**, chỉ một lần quy ra pip
  (10–20 pip, tr. 158).
- Villahermosa (2019) tự thừa nhận tr. 172: _"it would seem **impossible to create a
  strategy with 100% objective rules**"_, và cho đúng ba ngưỡng đo được trong cả sách
  (đóng nến nửa trên/dưới tr. 209 · SOW đi ≥ 50% cấu trúc tr. 164 · rủi ro ≤ 1%/lệnh
  tr. 214).
