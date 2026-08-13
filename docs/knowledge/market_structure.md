---
# Phần VI — Katsanos, *Intermarket Trading Strategies* (2009)

## References bổ sung

| # | nguồn | chương / trang | nguyên lý lấy ra |
  |---|---|---|---|
  | [S] | Katsanos, M. (2009). *Intermarket Trading Strategies*. John Wiley & Sons. | Ch. 7 "Gold", tr. 93-110 | vàng định giá bằng đô-la: xu hướng vàng có thể chỉ là xu hướng đô-la; ma trận tương quan; phân tích dẫn/trễ |
  | [T] | Katsanos (2009) | Ch. 11 tr. 181-184 | hệ thống hồi quy liên thị trường trên vàng; hệ số hồi quy đô-la trôi theo thời gian |

  Đây là cuốn có mật độ nội dung về **vàng** cao nhất kho (633-447 lần nhắc), và
  là cuốn duy nhất kiểm định định lượng quan hệ vàng-đô-la.
---

## 39. XU HƯỚNG VÀNG CÓ THỂ CHỈ LÀ XU HƯỚNG ĐÔ-LA — [S] tr. 96-97

Đây là phát hiện quan trọng nhất của cả cuốn đối với dự án này.

> "To illustrate my point I have prepared two charts... They are both of gold, the
> only difference being the currency gold is priced in. The first one is in US
> dollars, and the other in euro. For the 3½-year period from the beginning of
> 2002 and until about the middle of 2005 **the first gold chart (in dollars)
> showed a strong up trend but this was not the case with the second chart (in
> euro) which moved in a sideways range, finishing in April 2005 LOWER than it
> started in January 2002.**"

Và câu kết luận:

> "**The gold's (in dollars) uptrend was caused by a bear market in the dollar,
> not a bull market in gold.** During this period, the correct position for an
> international investor was a short dollar position, not a long gold position."

### ĐÃ KIỂM BẰNG DỮ LIỆU — và giả thuyết ban đầu của tôi SAI

Khi đọc xong đoạn trên tôi đã viết rằng đây là lời giải thích cho "long-bias
artifact" mà dự án phát hiện ngày 19/07. **Tôi đã chạy phép kiểm và điều đó
không đúng.** Ghi lại cả giả thuyết lẫn kết quả bác bỏ, vì đây đúng là loại suy
diễn không căn cứ mà vòng refactor này tồn tại để loại bỏ.

Giả thuyết: nếu drift của XAUUSD 2015-2026 là do đô-la yếu, thì vàng định giá
bằng đồng tiền khác sẽ đi ngang hoặc giảm, đúng như ví dụ 2002-2005 của Katsanos.

Kết quả đo trên dữ liệu thật (3.589 nến ngày, 2015-01 → 2026-07):

| định giá bằng | drift toàn kỳ |
| ------------- | ------------: |
| USD           |       +238,5% |
| EUR           |       +257,7% |
| JPY           |       +295,2% |
| CHF           |       +120,8% |
| GBP           |       +160,6% |

**Vàng tăng ở cả năm đồng tiền.** Giai đoạn 2015-2026 là thị trường bò của vàng
thật, không phải hiện tượng đô-la yếu. Cơ chế Katsanos mô tả **có thật** (ví dụ
2002-2005 của ông đứng vững) nhưng **không áp dụng cho giai đoạn dự án đang
backtest**. Mức chênh giữa các đồng tiền cho thấy phần đóng góp của đô-la là
đáng kể nhưng không chi phối: so với CHF vàng chỉ tăng 121% thay vì 238%, tức
khoảng một nửa mức tăng tính bằng đô-la là do đô-la yếu so với franc — phần còn
lại là vàng lên thật.

Vậy "long-bias artifact" của dự án là gì? Nó vẫn là hiện tượng có thật, nhưng
nguyên nhân là **drift của chính vàng**, không phải drift của đô-la. Hệ quả thực
tế không đổi: mọi chiến lược long-only đều thu được drift đó và phải chứng minh
mình vượt được control ngẫu nhiên cùng chiều. Nhưng chẩn đoán phải ghi đúng
nguyên nhân, nếu không phép chữa sẽ nhắm sai chỗ.

### Phép kiểm vẫn giữ giá trị, chỉ đổi vai trò

Phép kiểm khử-đô-la không vô dụng — nó vừa **loại trừ** được một giả thuyết cạnh
tranh, và đó chính là việc của một phép kiểm. Nó vẫn cần chạy cho mọi chiến lược
long-only, vì chu kỳ đô-la tiếp theo có thể đi ngược, và khi đó một chiến lược
chỉ sống nhờ đô-la yếu sẽ lộ ra ngay.

Module: `src/python/research/validation/dollar_neutral.py` (16 test).

### Cơ chế gốc, giữ nguyên để đối chiếu

Ngày 19/07 dự án phát hiện bằng thực nghiệm: **mọi tín hiệu long-only trên
XAU/XAG, kể cả vào lệnh ngẫu nhiên, đều cho kết quả đẹp trên tập 2023-2026.**
Hồi đó kết luận là "gold bull thật" và dựng spec 11 làm bộ lọc bắt buộc. Ngày
27/07 lặp lại với MOMBURST: control ngẫu nhiên kiếm nhiều hơn tín hiệu thật.

Katsanos giải thích **cơ chế**: XAUUSD không phải một tài sản, nó là một **tỉ
giá** — tử số là vàng, mẫu số là đô-la. Khi đô-la yếu kéo dài, chuỗi giá
XAUUSD có drift dương mà không cần vàng mạnh lên chút nào. Bất kỳ chiến lược
long-only nào cũng thu được drift đó, và đó không phải kỹ năng.

Điều này nâng phát hiện của dự án từ "quan sát thực nghiệm không rõ nguyên
nhân" lên **cơ chế có nguồn**. Nó cũng cho một phép kiểm mới, rẻ và mạnh:

> **Phép kiểm khử-đô-la:** chạy lại chiến lược trên **XAU tính bằng EUR**
> (XAUUSD ÷ EURUSD) hoặc trên một rổ tiền tệ. Nếu edge biến mất thì cái đang đo
> là xu hướng đô-la, không phải hành vi giá vàng.

Phép này khác với detrending của Aronson (ch.1 tr.27-29): detrend trừ drift
**trung bình**, còn phép này khử **nguồn gốc kinh tế của drift**. Hai phép bổ
sung nhau — một chiến lược vượt được cả hai mới đáng tin.

Cần ghi rõ giới hạn: FTMO trả tiền bằng đô-la và dự án giao dịch XAUUSD, nên
drift đô-la là lợi nhuận **có thật** khi nó xảy ra. Vấn đề không phải nó giả, mà
là nó **không lặp lại theo yêu cầu** — nó phụ thuộc chu kỳ đô-la kéo dài nhiều
năm, và một backtest 2023-2026 không cho biết gì về chu kỳ tiếp theo. Đúng cảnh
báo lấy mẫu của Faith ch.12 tr.182: "like polling at the Democratic convention".

## 40. Ma trận tương quan của vàng — [S] tr. 95-96, Bảng 7.1-7.2

Tương quan phi tham số của biến động phần trăm hàng tuần với World Gold Index,
tính đến 31/12/2007:

| chu kỳ | S&P 500 | XAU (cổ phiếu vàng) |  Bạc |  CRB | **Chỉ số đô-la** |  EUR |  JPY | Dầu thô |
| ------ | ------: | ------------------: | ---: | ---: | ---------------: | ---: | ---: | ------: |
| 2 năm  |    0,20 |                0,78 | 0,82 | 0,63 |        **−0,55** | 0,54 | 0,24 |    0,41 |
| 5 năm  |    0,10 |                0,74 | 0,74 | 0,55 |        **−0,57** | 0,54 | 0,32 |    0,23 |
| 10 năm |    0,02 |                0,71 | 0,66 | 0,45 |        **−0,49** | 0,43 | 0,26 |    0,17 |
| 15 năm |    0,00 |                0,71 | 0,66 | 0,43 |        **−0,38** |   NA | 0,23 |    0,14 |

Ba điều đọc ra được, mỗi điều đều có hệ quả cho dự án:

**(a) Tương quan vàng-bạc tăng từ 0,66 lên 0,82.** Katsanos gọi mức 0,82 là "rất
mạnh". Dự án đang chạy `XAG-Rider` song song với các chiến lược XAU. Ở mức 0,82
thì đó **không phải hai vị thế độc lập** — Murphy ch.16 tr.396 đã cảnh báo về đa
dạng hoá giả, còn đây là con số cụ thể cho đúng cặp mà dự án đang giao dịch.
Cần **trần rủi ro theo nhóm kim loại quý**, không phải trần theo từng mã.

Katsanos còn nói rõ quan hệ này **không có tính nhân quả**:

> "Their relationship, however, is not fundamental. The price of one does not move
> in a particular direction because the other market is moving the same way, as
> **both markets are driven by the same fundamentals.**"

Nghĩa là: không được dùng bạc để dự báo vàng, nhưng **phải** tính rủi ro chung.

**(b) Tương quan với đô-la KHÔNG ỔN ĐỊNH:** −0,38 (15 năm) → −0,49 → −0,57 →
−0,55 (2 năm). Nó trôi theo thời gian, gần gấp rưỡi giữa hai đầu. Bất kỳ tham số
nào hiệu chỉnh theo tương quan này đều có hạn sử dụng.

**(c) Tương quan với S&P 500 gần bằng 0 ở mọi chu kỳ dài** (0,00-0,10) và chỉ
tăng lên 0,20 trong 2 năm gần nhất. Katsanos dự đoán nó sẽ hồi về trung bình.

## 41. Hệ số hồi quy TRÔI — cảnh báo về mọi tham số hiệu chỉnh theo vĩ mô — [T] tr. 181

> "The regression coefficient of the dollar index **nearly doubled recently, from
> −0.3 to −0.6**, indicating an intensification of the negative correlation
> between gold and the dollar. By the time this book is published, the negative
> correlation between gold and the dollar will most probably increase further, so
> **it is a good idea to re-optimize this particular regression coefficient before
> using the system in real time.**"

Số cụ thể ([T] Bảng 11.4), hệ số hồi quy chỉ số đô-la theo độ dài cửa sổ:

| cửa sổ |  hệ số |
| ------ | -----: |
| 15 năm | −0,296 |
| 10 năm | −0,434 |
| 5 năm  | −0,545 |
| 3 năm  | −0,587 |

Cùng một quan hệ, cùng một dữ liệu, chỉ khác độ dài cửa sổ — hệ số đổi **gấp
đôi**. Đây là bằng chứng định lượng cho một điều dự án đang làm mà chưa có căn
cứ: module `attach_macro_to_m5` gắn 6 z-feature vĩ mô có dấu, trong đó có DXY
proxy từ rổ 5 cặp. **Các z-feature đó được chuẩn hoá trên cửa sổ nào?** Nếu cửa
sổ cố định thì hệ số ngầm bên trong sẽ trôi đúng như bảng trên.

Và một câu tự phê rất đáng chú ý của chính tác giả:

> "The regression equation with **the best coefficient of determination (R²) did
> not necessarily produce the most profitable test results.**"

R² cao không đồng nghĩa lợi nhuận cao. Trùng với López de Prado ch.11: sức mạnh
thống kê trong mẫu không chuyển thành hiệu quả ngoài mẫu.

## 42. Vàng LAG cổ phiếu vàng, nhưng LEAD đô-la — [S] tr. 101-104, Bảng 7.3

Tương quan Pearson theo độ trễ, dữ liệu 15 năm 1992-2006 (số dương = vàng dẫn):

|                     |       XAU | chỉ số đô-la |       Bạc |       CRB |
| ------------------- | --------: | -----------: | --------: | --------: |
| trung bình phía TRỄ |     0,291 |       −0,098 |     0,209 |     0,142 |
| **độ trễ 0**        | **0,679** |   **−0,315** | **0,612** | **0,428** |
| trung bình phía DẪN |     0,150 |       −0,113 |     0,167 |     0,120 |

Đọc: với XAU, tương quan phía trễ (0,291) gấp đôi phía dẫn (0,150) → **cổ phiếu
vàng dẫn vàng**. Nhưng con số quan trọng nhất là **độ trễ 0 luôn lớn nhất, và
lớn hơn hẳn**: 0,679 so với 0,291 và 0,150.

**Hệ quả thẳng cho dự án:** quan hệ liên thị trường của vàng gần như hoàn toàn là
**đồng thời**, không phải dự báo. Tín hiệu dẫn có tồn tại nhưng yếu (0,29 so với
0,68 — chưa bằng một nửa). Điều này giải thích vì sao 6 z-feature vĩ mô trong
`v2.5-macro` chỉ giúp được rất ít: chúng chủ yếu mô tả **hiện tại**, không dự báo
tương lai. Không phải lỗi triển khai — là giới hạn của chính quan hệ.

Katsanos tự đặt giới hạn cho phát hiện của mình:

> "Keep in mind that these indicate **only the average short-term tendency** and
> are **not appropriate to use for longer-term trends.**"

## 43. Mùa vụ của vàng — và cách nó bị bóp méo — [S] tr. 98-99

> "Gold prices usually spike up during the **September through December** period
> as jewellers stock up in gold prior to the year-end holiday shopping season."

Nhưng ngay sau đó là cảnh báo phương pháp luận:

> "Although seasonal patterns tend to recur each and every year in a more or less
> similar fashion, **something that is more macro fundamental might override
> them.** In the case of gold this factor was the dollar's weakness... **the
> recent bullish trend that has been in place since 2002 pushed toward higher
> prices. As a result, the normal seasonal low is not as pronounced as it might be
> otherwise.**"

Nghĩa là: mùa vụ đo trên giai đoạn có xu hướng vĩ mô mạnh sẽ **lẫn** xu hướng vào
mùa vụ. Dự án có chiến lược `TOM-XAU` (Turn-of-Month, giữ 5 ngày cuối tháng) —
đúng loại chiến lược lịch mà cảnh báo này áp vào. TOM đã qua holdout mù, placebo,
bootstrap và nhân bản sang XAG; nhưng **chưa qua phép kiểm khử-đô-la ở §39**.
Vì TOM là long-only, đó là phép kiểm còn thiếu quan trọng nhất với nó.

## 44. Việc phải làm rút ra từ Katsanos

| #   | việc                                                                                                                             | mức ưu tiên                                                  | căn cứ          |
| --- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ | --------------- |
| 48  | **Phép kiểm khử-đô-la**: chạy lại mọi chiến lược long-only XAU trên XAU/EUR và rổ tiền tệ; edge biến mất = đang thu drift đô-la  | **rất cao** — chạm trực tiếp TOM-XAU và toàn bộ họ long-only | [S] tr. 96-97   |
| 49  | **Trần rủi ro nhóm kim loại quý** cho XAU + XAG (tương quan 0,82) thay vì trần từng mã                                           | **cao**                                                      | [S] tr. 96      |
| 50  | Kiểm cửa sổ chuẩn hoá của 6 z-feature vĩ mô: hệ số hồi quy đô-la trôi gấp đôi giữa cửa sổ 3 năm và 15 năm                        | trung bình                                                   | [T] tr. 181     |
| 51  | Hạ kỳ vọng về giá trị **dự báo** của feature vĩ mô: quan hệ của vàng gần như thuần đồng thời (0,68 ở trễ 0 so với 0,29 phía dẫn) | trung bình — chỉnh kỳ vọng, không phải sửa code              | [S] tr. 101-104 |
| 52  | Ghi nhận mùa vụ tháng 9-12 của vàng, nhưng **không** dùng làm tín hiệu cho tới khi tách được khỏi xu hướng đô-la                 | thấp                                                         | [S] tr. 98-99   |

---

## 45. TOM-XAU KHÔNG vượt được control ngẫu nhiên cùng chiều — đo 03/08

Đây là kết quả có hệ quả trực tiếp cho danh mục, nên ghi đầy đủ cả cách đo.

**Phép đo.** Cơ chế trần của TOM-XAU: mua vàng 5 ngày trước cuối tháng, giữ 5
ngày. Đối chứng: mua vàng ở thời điểm **ngẫu nhiên**, giữ đúng 5 ngày, đúng số
lệnh — tức control CÙNG CHIỀU theo cách người dùng chỉ ra ngày 27/07. Lặp 2.000
lần để dựng phân bố thay vì một hạt giống đơn lẻ. Tiêu chí đăng ký trước khi
chạy: TOM phải nằm ngoài phân vị 95 của phân bố control.

| định giá bằng | TOM R/lệnh (log) | control TB | control p95 | phân vị của TOM |          p |
| ------------- | ---------------: | ---------: | ----------: | --------------: | ---------: |
| USD           |         +0,00416 |   +0,00170 |    +0,00448 |            92,8 | **0,0725** |
| EUR           |         +0,00332 |   +0,00175 |    +0,00429 |            84,8 | **0,1520** |

n = 139 lệnh, cửa sổ 2015-01 → 2026-07.

**Phán quyết: KHÔNG VƯỢT** theo tiêu chí đã đăng ký trước. Ở phân vị 92,8 thì
TOM có gợi ý về tín hiệu nhưng chưa đạt mức thông thường, và khi khử ảnh hưởng
đô-la (cột EUR) nó tụt xuống 84,8.

**Đọc con số cho đúng.** TOM kiếm gấp 2,4 lần control trung bình (+0,00416 so
với +0,00170) — nghe như nhiều. Nhưng độ lệch chuẩn của control là 0,00169, tức
khoảng cách đó chỉ khoảng 1,5 độ lệch chuẩn. Đúng bài học Wright ch.2 tr.16:
chênh lệch giữa các mẫu nhỏ có thể hoàn toàn do sai số chuẩn. Với 139 lệnh, một
chiến lược cần khoảng cách lớn hơn nhiều mới tách được khỏi may rủi.

**Giới hạn của phép đo này, ghi rõ để không kết luận quá tay:**

1. Đây là cơ chế trần — không có dừng lỗ, không có chi phí, không có định cỡ.
   TOM production có thể khác. Nhưng chi phí và dừng lỗ chỉ **làm giảm** lợi
   nhuận, chúng không tạo ra kỹ năng chưa có.
2. Nó không phủ nhận các phép kiểm TOM đã qua ngày 19/07 (holdout mù, placebo,
   bootstrap, nhân bản sang XAG). Nó **thêm** một phép kiểm mà lúc đó chưa có,
   và TOM không qua phép này.
3. p = 0,0725 không phải bằng chứng TOM vô dụng; nó là bằng chứng **chưa đủ** để
   khẳng định TOM có kỹ năng vượt việc chỉ đơn giản nắm giữ vàng.

**Hệ quả đề nghị.** Không tắt TOM — nó đang chạy demo, không mất gì, và p = 0,07
không phải bằng chứng phản bác. Nhưng **hạ nó khỏi nhóm "ứng viên đã xác thực"**
xuống nhóm "chưa tách được khỏi drift", và không dùng nó làm căn cứ cho bất kỳ
quyết định định cỡ nào cho tới khi có thêm dữ liệu ngoài mẫu. Đây là chiến lược
thứ hai của dự án ngã trước phép kiểm control cùng chiều, sau MOMBURST ngày
27/07 — dấu hiệu cho thấy phép kiểm này cần chạy **trước**, không phải sau.

Script: `scratch/dollar_neutral_run2_2026-08-03.py`.

---

# Phần VIII — Laidi, _Currency Trading and Intermarket Analysis_ (2008)

## References bổ sung

| #   | nguồn                                                                                                                                         | chương / trang                        | nguyên lý lấy ra                                               |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- | -------------------------------------------------------------- |
| [V] | Laidi, A. (2008). _Currency Trading and Intermarket Analysis: How to Profit from the Shifting Currents in Global Markets_. John Wiley & Sons. | Ch. 1 "Gold and the Dollar", tr. 1-23 | dùng vàng làm thước đo TRUNG TÍNH để xếp hạng sức mạnh tiền tệ |

Tác giả là chiến lược gia trưởng của CMC Markets. Cuốn này có mật độ nội dung
vàng cao thứ hai kho (633 lần) và cả chương 1 dành cho quan hệ vàng-đô-la.

---

## 49. Dùng VÀNG làm thước đo trung tính để xếp hạng tiền tệ — [V] tr. 8-11

Đây là chiều ngược lại của phép kiểm khử-đô-la ở §39-45: thay vì dùng EUR để
khử nhiễu cho vàng, dùng **vàng để khử nhiễu cho tiền tệ**.

> "Assessing the performance of currencies against the value of gold enables a
> transparent examination of the strength of a nation's currency, **without the
> influence of dynamics in other currencies and their economies.** A rising euro
> against the U.S. dollar, for instance, **may not necessarily be a reflection of
> improved fundamentals in the Eurozone but of deteriorating fundamentals...
> in the U.S. dollar.**"

Lý do vàng đủ tư cách làm thước đo trung tính:

> "Unlike currencies, which are largely influenced by interest rate movements
> resulting from economic policies and capital flows, **gold is mainly a
> reflection of supply and demand, and not a direct result of any particular
> central bank actions.**"

Và câu quan trọng nhất — nó phát biểu thẳng một chiến lược:

> "Charting gold against different currencies over a three- or six-month period
> enables a truer assessment of individual currencies than comparing them against
> the dollar or the euro. This way, traders can not only determine the secular
> performance of currencies but **may also rank them in order of strength and be
> better able to BUY THE STRONGEST AGAINST THE WEAKEST.**"

### Ví dụ định lượng của Laidi — [V] tr. 9

Từ tháng 1/2001 đến tháng 5/2008, mức tăng của vàng so với từng đồng tiền:

| đồng tiền | vàng tăng bao nhiêu so với nó | suy ra sức mạnh đồng tiền |
| --------- | ----------------------------: | ------------------------- |
| AUD       |                        +90,5% | **mạnh nhất**             |
| CAD       |                         +123% |                           |
| EUR, NZD  |                          giữa |                           |
| USD       |                      cao nhất | **yếu nhất**              |

> "Thus, with gold showing the highest percentage increase against the USD and
> the lowest percentage increase against the AUD, we can conclude that **playing
> the AUD/USD currency pair (buying AUD and selling USD) would have produced the
> highest rate of return** if held between January 2001 and May 2008."

### Vì sao điều này quan trọng với dự án

Mọi lần thử mở rộng sang forex trước đây đều là **chuyển giao** cơ chế từ vàng
sang FX: Donchian, breakout, momentum. Tất cả đều thất bại — và §47 vừa đo lại
xác nhận: sức mạnh điểm vào Donchian trên EURUSD/GBPUSD gần như bằng nhiễu
(đỉnh ở 2-14 nến, t < 1,6), trong khi trên kim loại quý thì rõ rệt.

Ý tưởng của Laidi **không phải chuyển giao** — nó là một cơ chế riêng của FX:
**động lượng cắt ngang (cross-sectional momentum)**, xếp hạng rồi mua mạnh nhất
bán yếu nhất. Ba lý do đáng thử:

1. **Không phải long-only** → không dính bẫy drift mà §39-45 vừa mổ xẻ, và không
   cần vượt qua control long ngẫu nhiên.
2. **Tần suất phù hợp** — tái cân bằng theo tháng cho khoảng 12 lần đổi vị thế
   mỗi năm, đúng hướng giải bài toán "3,0 lệnh/tháng là quá thưa".
3. **Dùng đúng dữ liệu đang có** — 6 cặp FX cộng XAU, đã dựng sẵn từ 2020.

Cần ghi rõ hai điều dè dặt trước khi thử:

- Laidi trình bày đây như một **công cụ phân tích**, không phải hệ thống đã
  backtest. Ông không đưa ra quy tắc vào/ra, thời gian nắm giữ hay số liệu hiệu
  suất. Việc biến nó thành chiến lược là bước của dự án, và mọi rủi ro khai thác
  dữ liệu thuộc về dự án chứ không được viện dẫn Laidi.
- Ví dụ AUD/USD của ông là **hồi cứu trên đúng giai đoạn ông chọn** — chọn cặp
  tốt nhất sau khi đã nhìn kết quả. Bản thân nó không phải bằng chứng.

## 50. Vàng như hàn thử biểu tổng hợp — [V] tr. 11-13

Laidi cộng gộp lợi suất của vàng so với tám đồng tiền để ra "lợi suất tổng hợp".
Số liệu 1999-2007, trung bình năm **82%** so với rổ tám đồng tiền.

Điểm phương pháp luận đáng lấy:

> "Since those returns are the aggregate of individual gold returns in distinct
> currencies, **gold's performance is generally a function of the performance of
> individual currencies and paper currency in general.**"

Và một ví dụ cụ thể cho thấy vì sao đo bằng một đồng tiền duy nhất là sai lệch
([V] tr. 13): năm 2003-2004 vàng chỉ tăng nhẹ rồi giảm 8% tính theo rổ tám đồng
tiền, **nhưng tăng 24% và 20% so với riêng đô-la**. Cùng một tài sản, cùng một
năm, hai kết luận trái ngược tuỳ thước đo.

Đây là bằng chứng thứ hai, độc lập với Katsanos, cho nguyên tắc ở §39: **không
được đọc xu hướng của XAUUSD như thể nó là xu hướng của vàng.**

## 51. Việc phải làm rút ra từ Laidi

| #   | việc                                                                                                                                                          | mức ưu tiên                                                                          | căn cứ        |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ------------- |
| 56  | Thử **động lượng cắt ngang FX với vàng làm thước đo**: xếp hạng các đồng tiền theo hiệu suất so với vàng, mua mạnh nhất bán yếu nhất, tái cân bằng theo tháng | **cao** — cơ chế FX riêng, không phải chuyển giao từ vàng; giải cả bài toán tần suất | [V] tr. 8-11  |
| 57  | Báo cáo hiệu suất vàng theo **rổ tiền tệ** song song với theo đô-la trong mọi báo cáo nghiên cứu                                                              | trung bình                                                                           | [V] tr. 11-13 |

### Kết quả: ÂM TÍNH — đo 03/08

Đã thử đúng như đăng ký trước. Vũ trụ 7 đồng tiền (USD, EUR, GBP, NZD, JPY, CHF,
CAD), 2.027 ngày (2020-01 → 2026-07), lưới 4 cấu hình.

| nhìn lại | giữ | n lượt |  TB/lượt |    LCB95 |     t | tỉ lệ thắng |
| -------: | --: | -----: | -------: | -------: | ----: | ----------: |
|       63 |  21 |     93 | −0,00241 | −0,00669 | −0,93 |       49,5% |
|       63 |  63 |     31 | −0,01149 | −0,02355 | −1,54 |       41,9% |
|      126 |  21 |     90 | +0,00009 | −0,00389 | +0,04 |       50,0% |
|      126 |  63 |     30 | +0,00295 | −0,01040 | +0,36 |       60,0% |

- White's Reality Check trên 4 cấu hình: **p = 0,6742** ✗
- Control xếp hạng ngẫu nhiên (500 lần): **p = 0,2740** ✗
- LCB95 của cấu hình tốt nhất: **−0,0104** ✗

**Không đạt cả ba tiêu chí.** Hai trong bốn cấu hình âm hẳn. Điều đáng chú ý
nhất là control: xếp hạng ngẫu nhiên cho trung bình −0,00055, còn xếp hạng thật
cho +0,00295 — nghe như xếp hạng có ích, nhưng p = 0,274 nghĩa là 27% các lần
xếp hạng ngẫu nhiên còn làm tốt hơn thế. Việc xếp hạng không mang thông tin.

**Giới hạn phải ghi rõ, nhưng KHÔNG dùng làm lý do thử lại:** cửa sổ bị cắt về
2020 vì NZD và CAD chỉ có dữ liệu từ đó, nên chỉ 30-93 lượt tái cân bằng. Với cỡ
mẫu này sức mạnh thống kê thấp. Tôi **không** chạy lại với ít đồng tiền hơn để
kéo dài cửa sổ, vì phương án đó không nằm trong đăng ký trước — mở rộng lưới sau
khi thấy thất bại chính là lỗi mà K&D ch.22 tr.547 mô tả ("out-of-sample data
becomes the same as the sample data").

Ghi vào nghĩa địa giả thuyết. Ý tưởng của Laidi vẫn có giá trị như **công cụ
phân tích** (nó đúng là cách đọc sức mạnh tiền tệ ít thiên lệch hơn), nhưng
không chuyển thành edge giao dịch được ở dạng đơn giản này trên dữ liệu đang có.

Script: `scratch/fx_gold_ranked_momentum_2026-08-03.py`.
