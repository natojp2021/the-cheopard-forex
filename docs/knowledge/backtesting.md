# KB — Thiết kế và kiểm định backtest

## References

| #   | nguồn                                                                        | chương / trang                                                      | nguyên lý lấy ra                                                    |
| --- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------- |
| [A] | Aronson, D. (2007). _Evidence-Based Technical Analysis_. Wiley.              | Ch. 8 "Case Study of Rule Data Mining for the S&P 500", tr. 397-442 | toán tử kênh giá, cách giãn tham số, ngôn ngữ mô tả chỉ báo         |
| [B] | Aronson (2007)                                                               | Ch. 9 "Case Study Results and the Future of TA", tr. 443-478        | kết quả 6.402 luật; danh sách kiểm soát thiên lệch; ba khiếm khuyết |
| [C] | Hsu, P.-H. & Kuan, C.-M. — nghiên cứu 39.832 luật trên 4 chỉ số Mỹ 1990-2002 | dẫn trong [B] tr. 450                                               | 82% luật đạt ý nghĩa là luật PHỨC HỢP                               |
| [D] | Ashby, W.R. — _Law of Requisite Variety_                                     | dẫn trong [B] tr. 450                                               | độ phức tạp của mô hình phải tương xứng độ phức tạp của bài toán    |
| [E] | Wolf, M. & Romano, J.                                                        | dẫn trong [B] tr. 447                                               | bản cải tiến tăng lực kiểm định, dùng trong case study              |

---

## 1. Kết quả case study — con số cần nhớ

6.402 luật trên S&P 500. Luật tốt nhất: **10,25%/năm**, p đơn-luật = **0,0005**
(trông rất có ý nghĩa). Sau khi dựng phân phối null đúng — cực đại trên 6.402
luật vô dụng — ngưỡng thành ([B] tr. 443):

| mức ý nghĩa | lợi nhuận/năm cần đạt |
| ----------- | --------------------: |
| p < 0,05    |             **> 15%** |
| p < 0,001   |             **> 17%** |

Luật tốt nhất đạt 10,25%. **Không một luật nào trong 6.402 luật đạt ý nghĩa
thống kê.**

Trích [B] tr. 443-444 — đoạn đắt nhất của cả cuốn sách:

> "Ironically, the failure of any rule to generate statistically significant
> returns, after adjustment for data-mining bias, **underscores the huge
> importance of using statistical inference methods that take the biasing
> effects of data mining into consideration.** Had I used an ordinary
> significance test, which pays no attention to data-mining bias, the mean
> return of the best rule would have appeared to be highly significant (a
> p-value of 0.0005)."

> "Had a conventional test of significance been used, **about 320 of the 6,402
> rules would have appeared to be significant at the 0.05 level. This is exactly
> what would be predicted to occur by chance.** The naive data miner using a
> conventional test of significance would have concluded that many rules with
> predictive power had been discovered. In reality, mining operations conducted
> in this fashion would have **produced nothing but fool's gold.**"

Và [B] tr. 450, tác giả tự nhận:

> "the case study was restricted to simple rules to keep its scope manageable.
> However, I did so in the belief that at least a few of the 6,402 rules would
> prove significant. **Clearly, I was overconfident.**"

**Áp dụng cho dự án:** con số 320/6.402 ≈ 5% chính xác bằng mức ý nghĩa. Phép
quét 108 tổ hợp của tôi, nếu dùng kiểm định thông thường, kỳ vọng có ~5 tổ hợp
"đạt 0,05" hoàn toàn do may. Tôi đã tìm được 2-4 tổ hợp như vậy.

## 2. Danh sách kiểm soát năm loại thiên lệch ([B] tr. 448-450)

Đây là danh sách kiểm bắt buộc cho mọi backtest của dự án.

### 2.1 Mốc chuẩn — bắt buộc

> "the back-tested performance of a rule **only makes sense in relation to a
> benchmark. Absolute levels of performance are uninformative.**"

Mốc thấp nhất hợp lý: hiệu suất của một luật KHÔNG có khả năng dự báo. Mốc cao
hơn khi có: nếu tuyên bố cải tiến một luật, mốc phải là bản gốc của luật đó.

**Trạng thái dự án:** đã làm — đối chứng vào lệnh ngẫu nhiên cùng chiều. Nhưng
mốc phải là _cực đại trên toàn vũ trụ luật_, xem `statistical_validation.md` §4.

### 2.2 Khử xu hướng thị trường — CHƯA LÀM, và đây là chỗ hổng lớn nhất

> "the case study used **detrended market data** to compute rule returns to
> eliminate performance distortions. As explained, distortions result when a
> rule with a long- or short-position bias has its returns computed on market
> data that has a net upward or downward trend over the back-test period."

**Đây chính xác là "long-bias artifact" mà dự án đã vấp ba lần** (DON-H4 19/07,
H4-Metals 20/07, MOMBURST 27/07). Mỗi lần đều xử lý bằng cách dựng đối chứng
ngẫu nhiên — hiệu quả, nhưng tốn kém và phải làm lại từ đầu mỗi lần.

Aronson dùng cách rẻ hơn và chặt hơn: **tính lợi suất luật trên dữ liệu ĐÃ KHỬ
XU HƯỚNG**. Khi chuỗi giá không còn drift, một luật chỉ-mua không thể ăn tiền
nhờ drift nữa; mọi lợi nhuận còn lại là do định thời.

Vàng tăng ~11 lần trong 2003-2026, nên đây là biện pháp có giá trị đặc biệt cao
với dự án này.

→ **Việc phải làm:** thêm chế độ tính lợi suất trên chuỗi đã khử xu hướng vào
tầng đo lường nghiên cứu. Không thay thế đối chứng ngẫu nhiên mà bổ sung — hai
phép chặn hai lỗ hổng khác nhau.

### 2.3 Thiên lệch nhìn trước

> "if closing price information is needed to compute a rule's signals, it would
> not be legitimate to assume an entry or exit at the closing. **The first
> legitimate price at which an entry or exit could legitimately be assumed is
> the next price.**"

Case study vào/ra ở **giá MỞ của ngày kế tiếp** sau tín hiệu.

**Trạng thái dự án — cần phân biệt hai tình huống:**

- Dữ liệu NGÀY: đúng như Aronson nói, không được khớp ở giá đóng.
- Nến H4/H1 với khớp lệnh tức thì: chiến lược đánh giá khi nến đóng và gửi lệnh
  thị trường, khớp trong vài giây ở giá gần bằng giá đóng. `portfolio_simbroker_
driver.py` khớp ở giá đóng nến CỘNG spread hiệu lực (`bid = price − sp/2`,
  `ask = price + sp/2`), tức người mua trả `ask`. Cách này **hợp lệ** vì tái tạo
  đúng cơ chế live, khác với trường hợp dữ liệu ngày.

Điểm cần cảnh giác Aronson nêu thêm: chuỗi dữ liệu **được công bố trễ hoặc bị
hiệu chỉnh lại** (thống kê chính phủ, dữ liệu quỹ) phải dùng giá trị có độ trễ
đúng. → liên quan tới module macro và COT của dự án.

### 2.4 Thiên lệch khai thác dữ liệu

Xem `statistical_validation.md`. Case study dùng ba phép: WRC bản Wolf–Romano,
WRC bản thương mại của Quantmetrics, và MCP bản Masters có cải tiến Wolf–Romano.

### 2.5 Thiên lệch dò dẫm nghiên cứu trước — chưa từng được xử lý trong dự án

Trích [B] tr. 449:

> "**Data-snooping bias**, which might be more properly named
> **prior-research-snooping bias**, occurs when data miners use the results of
> prior research to choose which rules to test... This is an insidious problem
> because **it is unknown how many rules were tested to find the successful
> rules.** Because the number of rules tested is an important factor
> contributing to the magnitude of the data-mining bias it is impossible to
> evaluate the actual statistical significance of a rule that was included in a
> new data-mining venture because it had been successful in prior research."

Case study tránh bằng cách **liệt kê tổ hợp đầy đủ**: 11 giá trị tham số × 39
chuỗi = 429 luật, đưa vào TẤT CẢ, không chọn lọc theo nghiên cứu trước.

Aronson còn kể chính mình suýt phạm: nếu ông biết trước nghiên cứu Hsu–Kuan tìm
được luật hiệu quả trên NASDAQ và Russell 2000 rồi chọn hai chỉ số đó, thì p-value
của ông sẽ vô hiệu ([B] tr. 451).

**Đây là chỗ dự án phạm nặng nhất và chưa từng ghi nhận.** Danh mục champion hiện
tại — `DonchianH4Breakout`, `PaDonchianH4`, `PaPullbackH4`, `SwingDon` — là kết
quả sống sót qua **hàng chục vòng nghiên cứu** kể từ tháng 7. Mỗi vòng loại bỏ
các ứng viên thua và giữ lại kẻ thắng. Số luật thực sự đã thử trên đường tới bốn
chiến lược này là **không đếm được**, và theo lập luận trên thì mọi p-value tính
riêng cho chúng đều **không diễn giải được**.

Không thể sửa hồi tố. Chỉ có hai cách đi tiếp:

1. Ghi nhận công khai giới hạn này trong tài liệu danh mục.
2. Từ nay dùng **liệt kê tổ hợp đầy đủ** thay vì chọn lọc dần, và ghi lại tổng
   số luật đã thử vào một sổ chung — dự án đã có ý tưởng "sổ scope toàn cục
   chống data-mining xuyên vòng" trong spec 06 nhưng chưa thực thi triệt để.

## 3. Ba khiếm khuyết Aronson tự nhận — và cái nào áp cho ta

### 3.1 Không xét luật PHỨC HỢP — khiếm khuyết lớn nhất ([B] tr. 450)

Trích, kèm số liệu từ [C]:

> "Of the entire rule set, 3,180 or 8 percent were complex rules, but **of the
> 229 rules that generated statistically significant profits, 188, or 82
> percent, were complex rules.**"

Lý do lý thuyết, dẫn Ashby [D]:

> "A nonlinear combination of simple rules allows the complex rule to be more
> informative than the summed information contained in its individual
> constituents. This allows the rule to comply with **Ashby's Law of Requisite
> Variety**, which stipulates that a problem and its solution must have similar
> degrees of complexity."

**Áp dụng — mâu thuẫn trực tiếp với hướng đi hiện tại của dự án.** Cả bốn chiến
lược champion đều là luật ĐƠN (một hoặc hai điều kiện). Toàn bộ nỗ lực tìm chiến
lược bán hôm 03/08 cũng chỉ quét luật đơn và các tổ hợp AND hai điều kiện.

8% luật phức hợp chiếm 82% số luật đạt ý nghĩa — tỉ lệ trúng cao hơn khoảng
**48 lần**. Nếu con số này chuyển được sang thị trường vàng, thì hướng nghiên cứu
đúng là **tổ hợp phi tuyến của các luật đơn**, không phải quét thêm luật đơn.

Lưu ý giới hạn: [C] cũng cho thấy KHÔNG có luật nào — đơn hay phức — hiệu quả
trên Dow Jones và S&P 500. Luật phức hợp chỉ đạt trên NASDAQ và Russell 2000.

### 3.2 Chỉ xét luật đảo chiều mua/bán ([B] tr. 450-451)

> "The requirement that a rule always hold a market position, which is true of
> reversal rules, rests on the **unlikely assumption that the market is in a
> perpetual state of inefficiency** and continually presents profit
> opportunities. In contrast, rules that are more selective in identifying when
> market exposure is warranted are consistent with the more reasonable
> assumption that **markets are occasionally inefficient.** Therefore,
> tri-state rules, which would allow for long/short/neutral positions, or binary
> rules, which are long/neutral or short/neutral, may be superior."

**Áp dụng — chỗ này dự án làm ĐÚNG và nên ghi nhận.** Mọi chiến lược trong
`live_strategies/` đều là mua/đứng-ngoài (nhị phân có trạng thái trung tính),
không phải đảo chiều liên tục. Theo Aronson đây là thiết kế _ưu việt hơn_.

Nó cũng bác luôn một lo ngại lặp đi lặp lại của người dùng — "đứng ngoài thị
trường quá lâu". Đứng ngoài không phải khuyết điểm của thiết kế; nó là hệ quả
của giả định đúng rằng thị trường chỉ _thỉnh thoảng_ kém hiệu quả.

Nhưng lưu ý: điều này KHÔNG biện minh cho tần suất 4,9 lệnh/năm. Aronson nói về
việc _không bắt buộc luôn có vị thế_, không nói gì về mức tần suất tối ưu.

### 3.3 Chỉ một thị trường

Case study chỉ chạy S&P 500. Dự án chỉ chạy XAUUSD theo ràng buộc FTMO — cùng
giới hạn, và cùng hệ quả: không kiểm được tính nhân bản sang thị trường khác,
vốn là bằng chứng mạnh chống overfit.

## 4. Chi tiết kỹ thuật đáng lấy từ chương 8

### 4.1 Toán tử phá vỡ kênh giá — có nguồn cho `DonchianH4Breakout`

Trích [A] tr. 397:

> "**Despite its extreme simplicity, the channel-breakout operator has proven to
> be as effective as more complex trend-following methods.**"

Và lời giải thích cơ chế, tr. 398:

> "Although the channel has a constant look-back span with respect to the time
> axis, its vertical width... **adjusts dynamically to the range of the series
> over the past n-periods. This feature may explain the effectiveness of the
> method.** This is to say, the channel breakout's dynamic range may reduce the
> likelihood of false signals caused by **an increase in the series' volatility
> rather than an actual change in its trend.**"

**Áp dụng:** đây là lý do kỹ thuật vì sao kênh Donchian hơn ngưỡng cố định — bề
rộng kênh tự co giãn theo biến động, nên một cú tăng biến động thuần tuý không
sinh tín hiệu giả.

Đáng chú ý: điều này khiến bộ lọc "nén biến động" (`atr < atr_ma`) trong
`DonchianH4Breakout` trở nên **thừa về mặt lý thuyết** — kênh giá đã tự xử lý
biến động rồi. Và phép quét thực nghiệm ngày 03/08 cho đúng kết quả ấy: bỏ điều
kiện nén thì R/năm tăng. Lý thuyết và số liệu khớp nhau.

### 4.2 Cách giãn giá trị tham số khi quét

[A] tr. 397: case study thử 11 cửa sổ nhìn lại, **giãn theo hệ số ~1,5**:

    3, 5, 8, 12, 18, 27, 41, 61, 91, 137, 205

**Áp dụng:** phép quét của tôi dùng N ∈ {20, 34, 55, 89, 144, 200} — dãy
Fibonacci, hệ số ~1,6. Gần đúng nguyên tắc này một cách tình cờ. Từ nay ghi rõ
lý do: giãn theo cấp số nhân phủ được dải rộng với ít điểm, và tránh việc quét
dày đặc quanh một vùng vốn chỉ làm phình số luật mà không thêm thông tin.

### 4.3 Ba loại toán tử và vai trò lọc tần số

| toán tử                                | vai trò                                         | công thức độ trễ                                                  |
| -------------------------------------- | ----------------------------------------------- | ----------------------------------------------------------------- |
| trung bình động (MA)                   | lọc thông THẤP — giữ xu hướng, bỏ dao động ngắn | trễ = (n−1)/2 với MA đơn giản; (n−1)/3 với MA trọng số tuyến tính |
| chuẩn hoá kênh (CN, tức "stochastics") | lọc thông CAO — bỏ xu hướng, giữ dao động ngắn  | —                                                                 |
| phá vỡ kênh (CBO)                      | nhận diện xu hướng                              | —                                                                 |

Aronson chỉ ra tên gọi "stochastic" của Lane là **dùng sai thuật ngữ** — không
có gì ngẫu nhiên trong toán tử này, nó hoàn toàn tất định ([A] tr. 403).

Ba chủ đề luật trong case study: **xu hướng**, **giá trị cực trị và chuyển
trạng thái**, **phân kỳ**.

## 5. Việc phải làm rút ra từ hai chương này

| #   | việc                                                                                                                | mức ưu tiên | căn cứ                   |
| --- | ------------------------------------------------------------------------------------------------------------------- | ----------- | ------------------------ |
| 1   | Thêm chế độ đo trên dữ liệu **đã khử xu hướng** vào tầng nghiên cứu                                                 | cao         | [B] tr. 448 §2.2         |
| 2   | Ghi nhận công khai rằng danh mục champion mang **thiên lệch dò dẫm nghiên cứu trước**, p-value không diễn giải được | cao         | [B] tr. 449 §2.5         |
| 3   | Chuyển hướng nghiên cứu sang **luật phức hợp** thay vì quét thêm luật đơn                                           | cao         | [B] tr. 450, [C] §3.1    |
| 4   | Ghi lý do kỹ thuật của kênh Donchian vào `donchian_h4_breakout.py`                                                  | trung bình  | [A] tr. 397-398 §4.1     |
| 5   | Bỏ điều kiện "nén biến động" — thừa về lý thuyết, và số liệu xác nhận                                               | trung bình  | [A] tr. 398 + quét 03/08 |
| 6   | Ghi nhận thiết kế mua/đứng-ngoài là ƯU ĐIỂM, không phải khuyết điểm                                                 | thấp        | [B] tr. 450-451 §3.2     |

---

# Phần III — Wright, _Building Reliable Trading Systems_ (2013)

## References bổ sung

| #   | nguồn                                                                                                                                             | chương / trang                                                          | nguyên lý lấy ra                                                            |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| [K] | Wright, K. (2013). _Building Reliable Trading Systems: Tradable Strategies That Perform As They Backtest and Meet Your Risk-Reward Goals_. Wiley. | Ch. 2 "Developing a Strategy So It Trades Like It Back-Tests", tr. 7-30 | hai định nghĩa của khớp đường cong; overfit tỉ lệ với SỐ LỆNH; sai số chuẩn |

## 14. Hai định nghĩa của khớp đường cong — [K] tr. 8

> "Curve-fitting can be defined in the following way: either **the overuse of
> trading rules, parameters, filters, stops, and so forth when developing a
> trading strategy on a relatively large body of data**, or **the proper use of
> rules, filters, and so on on a relatively small body of data.**"

Định nghĩa thứ hai là cái nguy hiểm: dùng ĐÚNG phương pháp vẫn khớp đường cong,
chỉ vì dữ liệu ít.

### Ví dụ của Wright cho loại thứ hai — [K] tr. 9-11

Franc Thuỵ Sĩ thập niên 1980. Hệ thống: đảo chiều theo trung bình động 50 ngày,
bộ lọc nhìn lại 110 ngày, cắt lỗ thảm hoạ 750 đô. Tác giả tự nhận xét:

> "This system is pure and simple: one entry rule, one filter, and one piece of
> risk control logic. **I doubt anyone would claim it has got too many variables
> or that it is over-optimized.**"

| giai đoạn              | lợi nhuận trung bình/năm |
| ---------------------- | -----------------------: |
| 1980-1989 (phát triển) |                 8.500 đô |
| 1990-2010 (sau đó)     |             **1.500 đô** |

> "We curve-fit to a relatively small amount of data, **even though we did not
> weigh the system down with a lot of rules, filters, and so on.**"

### Ví dụ cho loại thứ nhất — [K] tr. 8

Một nhà giao dịch dựng hệ thống S&P 500 trên nến 45 phút, dữ liệu 1984-1998 —
khoảng **34.000 nến**. Hệ thống sinh **dưới 90 lệnh** trong 15 năm, lệnh trung
bình hơn 2.000 đô.

> "The system 'stopped working' as soon as he started trading it. I believe that
> what really happened is that **he used so many rules, filters, and so forth on
> the relatively large amount of data that he isolated 90 short periods of time
> that were highly profitable.**"

**Điểm chung của hai ví dụ:** cả hai đều có **ít LỆNH** trong mẫu phát triển —
không phải ít nến, không phải ít năm.

## 15. Tiên đề: overfit tỉ lệ với SỐ LỆNH, không phải số nến — [K] tr. 12-19

Wright kiểm tiên đề này bằng thực nghiệm **trên chính vàng**: dữ liệu ngày từ
1975, hệ thống đảo chiều trung bình động 20 ngày, 683 lệnh, lợi nhuận trung bình
32,80 đô, độ lệch chuẩn **1.884 đô**.

Phương pháp: rút ngẫu nhiên 10.000 mẫu cỡ `n` lệnh, tính trung bình từng mẫu,
rồi lấy độ lệch chuẩn của 10.000 trung bình ấy → sai số chuẩn.

|   cỡ mẫu |                                               sai số chuẩn |
| -------: | ---------------------------------------------------------: |
|  90 lệnh |                                                    ~200 đô |
| 300 lệnh | ~100 đô — vẫn rất lớn so với lợi nhuận trung bình 32,80 đô |

Mở rộng sang 37 hàng hoá, 24.982 lệnh: **ngay cả ở cỡ mẫu 1.000 lệnh, sai số
chuẩn vẫn khoảng 75 đô.**

Kết luận của tác giả ([K] tr. 19):

> "for most trading systems (I will not say all, but I am thinking all) **you
> need many hundreds to thousands of trades in your back-test** to minimize the
> effects of curve-fitting and gain the confidence that real trading will match
> the parameters of your back-test."

### Đánh đổi ngắn hạn ↔ dài hạn — [K] tr. 19

| loại chiến lược | lãi TB | độ lệch chuẩn | số lệnh cần   |
| --------------- | ------ | ------------- | ------------- |
| ngắn hạn        | nhỏ    | **nhỏ**       | **ít hơn**    |
| dài hạn         | lớn    | **lớn**       | **nhiều hơn** |

Nghịch lý: chiến lược dài hạn vừa sinh ít lệnh vừa **cần nhiều lệnh hơn** để tin
được. Đó chính là cấu hình của danh mục hiện tại.

### Cảnh báo về việc so sánh nhiều lần chạy — [K] tr. 16

Với năm mẫu 10 lệnh rút từ CÙNG một phân phối (trung bình thật 100 đô, độ lệch
chuẩn 500 đô), kết quả ra: +263, −31, −72, +199, +276.

> "Think of each of the five samples as a separate back-test, maybe with **one
> parameter value changed slightly per run.** We are likely to think we are on the
> right track with Samples 1 and 5, and on the wrong track with Samples 2 and 3,
> **but the results come from the same distribution.** We just cannot make a
> judgment on a small sample with a relatively large standard deviation."

Đây là mô tả chính xác một phép quét tham số trên mẫu nhỏ — và là lập luận độc
lập thứ tư cho cùng kết luận của Aronson ch.6.

## 16. Áp phương pháp Wright vào bốn chiến lược LIVE

Sai số chuẩn = `SD(lệnh) / √n`. Cột cuối là số lệnh cần để sai số chuẩn bằng
một phần tư lợi nhuận trung bình.

| chiến lược           | n hiện có | R/lệnh |    SD | sai số chuẩn | SE / R-TB | **n cần** | thiếu    |
| -------------------- | --------: | -----: | ----: | -----------: | --------: | --------: | -------- |
| `SwingDon`           |       168 | +0,520 | 1,814 |        0,140 |      0,27 |       195 | −27      |
| `DonchianH4Breakout` |       111 | +0,438 | 1,796 |        0,171 |      0,39 |       270 | **−159** |
| `PaDonchianH4`       |       217 | +0,223 | 1,497 |        0,102 |      0,46 |       724 | **−507** |
| `PaPullbackH4`       |       275 | +0,201 | 1,372 |        0,083 |      0,41 |       747 | **−472** |
| **cả danh mục gộp**  |   **771** | +0,311 | 1,578 |        0,057 |  **0,18** |       414 | **đạt**  |

**Cả bốn chiến lược đều dưới cỡ mẫu cần cho phương sai của chính nó.** Hai chiến
lược thiếu nhiều nhất là `PaDonchianH4` và `PaPullbackH4` — cũng chính là hai
chiến lược có biên an toàn `p − p*` mỏng nhất (xem `risk_management.md` §3). Hai
phép đo độc lập chỉ vào cùng hai chiến lược.

Điểm sáng: **danh mục gộp lại có 771 lệnh và tỉ số SE/R-TB là 0,18** — con số
lành mạnh nhất trong bảng. Đa dạng hoá bốn cấu phần làm giảm phương sai đủ để
tổng thể đạt ngưỡng, dù từng phần thì không.

### Hệ quả cho bài toán tần suất — lập luận MẠNH NHẤT đã tìm được

Từ trước tới nay, lý do tăng tần suất luôn là **thông lượng lợi nhuận**. Wright
cho một lý do khác và mạnh hơn: **độ tin cậy thống kê**.

Số lệnh ít không chỉ làm chậm tài khoản — nó khiến ta _không biết chiến lược có
thật hay không_. Một chiến lược 111 lệnh với độ lệch chuẩn 1,8R đơn giản là chưa
đủ dữ liệu để phân biệt với may mắn.

### Ghi chú thẳng thắn về mâu thuẫn với phán quyết ở tài liệu ma trận §4.1

Tiêu chí của Wright nói ngược với phán quyết "giữ bộ lọc nén" hôm nay: bỏ lọc
đưa `DonchianH4Breakout` từ 111 lên 302 lệnh, tức từ **dưới** ngưỡng 270 lên
**trên** ngưỡng — một lập luận về độ tin cậy, độc lập với lập luận R/lệnh.

**Nhưng không được dùng nó để lật phán quyết cũ.** Tôi đã nhìn thấy kết quả của
phép kiểm ấy rồi; mọi tiêu chí đặt ra sau đó đều nhiễm. Cách sạch duy nhất là
kiểm tiến trên dữ liệu chưa từng chạm, hoặc để nguyên và ghi nhận mâu thuẫn.

Ghi nhận, và để nguyên.

## 17. Việc phải làm rút ra từ Wright

| #   | việc                                                                                                                                | mức ưu tiên | căn cứ        |
| --- | ----------------------------------------------------------------------------------------------------------------------------------- | ----------- | ------------- |
| 13  | Ghi **số lệnh và sai số chuẩn** vào mọi báo cáo chiến lược, cạnh R/lệnh                                                             | cao         | [K] tr. 13-19 |
| 14  | Đặt **ngưỡng số lệnh tối thiểu** cho việc thăng cấp LIVE, tính từ phương sai của chính chiến lược chứ không phải một con số cố định | cao         | [K] tr. 19    |
| 15  | Khi so sánh nhiều cấu hình trên mẫu nhỏ, nhớ chênh lệch có thể hoàn toàn do sai số chuẩn                                            | cao         | [K] tr. 16    |
| 16  | Ưu tiên chiến lược **ngắn hạn** khi cần độ tin cậy: độ lệch chuẩn nhỏ hơn nên cần ít lệnh hơn                                       | trung bình  | [K] tr. 19    |

---

# Phần III — Katz & McCormick, _The Encyclopedia of Trading Strategies_ (2000)

## References bổ sung

| #   | nguồn                                                                                       | chương / trang                                 | nguyên lý lấy ra                                                                      |
| --- | ------------------------------------------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------- |
| [L] | Katz, J.O. & McCormick, D.L. (2000). _The Encyclopedia of Trading Strategies_. McGraw-Hill. | Ch. 3 "Optimizers and Optimization", tr. 29-50 | bốn cách thất bại và bốn cách thành công với tối ưu hoá; bậc tự do; công thức co ngót |
| [M] | Katz & McCormick (2000)                                                                     | Ch. 5 "Breakout Models", tr. 83-108            | kiểm định có hệ thống mô hình phá vỡ trên danh mục hàng hoá rộng                      |

**Vì sao cuốn này quan trọng riêng với dự án:** chương 5 là một **kiểm định độc
lập trên chính họ chiến lược mà danh mục đang dùng** — phá vỡ kênh giá
đỉnh-cao-nhất/đáy-thấp-nhất, tức Donchian.

---

## 18. Bốn cách THẤT BẠI với tối ưu hoá — [L] tr. 41

> "Failure with an optimizer is easy to accomplish by following a few key rules.
> First, be sure to use a **small data sample**... Next, make sure the trading
> system has a **large number of parameters and rules** to optimize... It would
> also be beneficial to employ **only a single sample** on which to run tests;
> annoying out-of-sample data sets have no place in the rose-colored world of the
> ardent loser. Finally, do **avoid the headache of inferential statistics.**"

Và câu phân định quan trọng:

> "In actual fact, optimizers are not dangerous and not all optimization should
> be feared. **Only bad optimization is dangerous.**"

Trùng với Aronson ch.6 tr.268 (bác chuyện từ chối quét) — hai nguồn độc lập cùng
nói: vấn đề không phải tối ưu hoá, mà là tối ưu hoá tồi.

### Vì sao mẫu nhỏ giết chết — [L] tr. 42

> "Applied to a small development sample, an optimizer will faithfully discover
> the best possible solution. The best solution for the development sample,
> however, may turn out to be a dreadful solution for the later sample... Failure
> ensues, not because optimization has found a bad solution, but because **it has
> found a good solution to the wrong problem!**"

### Bậc tự do — [L] tr. 42

> "As the number of data points declines to the number of free (adjustable)
> parameters, **most models will attain a perfect fit to even random data.** The
> principle involved is the same one responsible for the fact that a line, which
> is a two-parameter model, can always be drawn through any two distinct points,
> but cannot always be made to intersect three arbitrary points."

Và điểm tinh tế hơn:

> "Even when there are enough data points to avoid a totally artifact-determined
> solution, **some part of the model fitness obtained through optimization will
> be of an artifact-determined nature**, a by-product of the process."

Tức không có ngưỡng an toàn tuyệt đối — chỉ có mức độ.

## 19. Bốn cách THÀNH CÔNG — [L] tr. 43-45

1. tối ưu trên mẫu **lớn nhất có thể và có tính đại diện**, với nhiều lệnh mô phỏng;
2. giữ **ít tham số và luật**, nhất là so với cỡ mẫu;
3. kiểm trên dữ liệu **ngoài mẫu**;
4. đánh giá kết quả bằng **thống kê suy diễn**.

### Định nghĩa "mẫu đại diện" — [L] tr. 44

> "Such a data sample should include **bull and bear markets, trending and
> nontrending periods, and even crashes.** In addition, the data in the sample
> should be **as recent as possible** so that it will reflect current patterns of
> market behavior."

Và cảnh báo về đánh đổi:

> "As one goes farther back in history to bolster a sample, the data may become
> **less representative** of current market conditions."

**Đối chiếu:** mẫu XAUUSD 2003-2026 của dự án có đủ pha bò và pha gấu (bảy pha
gấu Pagan–Sossounov), có khủng hoảng 2008 và 2020. Đạt tiêu chí đại diện.

### Câu quan trọng nhất cho dự án — [L] tr. 44

> "when running simulations and optimizations, **pay attention to the number of
> trades a system takes.** Like large data samples, it is highly desirable that
> simulations and tests involve numerous trades. **Chance or artifact can easily
> be responsible for any profits produced by a system that takes only a few
> trades, regardless of the number of data points used in the test!**"

Đây là **nguồn độc lập thứ ba** cho cùng một nguyên lý:

| nguồn                      | phát biểu                                                    |
| -------------------------- | ------------------------------------------------------------ |
| Wright ch.2 tr.19          | _"you need many hundreds to thousands of trades"_            |
| Katz & McCormick [L] tr.44 | _"regardless of the number of data points used in the test"_ |
| Aronson ch.6 tr.288        | yếu tố 2: số quan sát càng nhiều, sai lệch càng nhỏ          |

### Hiệu chuẩn số tham số so với số lệnh — [L] tr. 44-45

> "Although **several dozen parameters may be acceptable when working with
> several thousand trades** taken on 100,000 1-minute bars... **even two or three
> parameters may be excessive when developing a system using a few years of
> end-of-day data.**"

**Áp vào dự án — và kết quả không dễ chịu:**

| chiến lược           |                                    số tham số tự do | số lệnh | đánh giá theo [L]                    |
| -------------------- | --------------------------------------------------: | ------: | ------------------------------------ |
| `DonchianH4Breakout` | 4 (`DONCHIAN_N`, `ATR_MA_N`, `SL_ATR`, `HOLD_BARS`) |     111 | **quá nhiều tham số so với số lệnh** |
| `SwingDon`           |                                                   4 |     168 | quá nhiều                            |
| `PaDonchianH4`       |                                                  ~4 |     217 | căng                                 |
| `PaPullbackH4`       |                                                  ~5 |     275 | căng                                 |

Thang của Katz: vài chục tham số cần **vài nghìn** lệnh; hai-ba tham số đã có thể
là quá nhiều với vài năm dữ liệu ngày. Bốn chiến lược của dự án đều nằm ở vùng
"quá nhiều tham số cho số lệnh có được".

### Kỹ thuật thay thế: tối ưu trên CẢ DANH MỤC thị trường — [L] tr. 45

> "An alternative that sometimes works is optimizing a trading model on a **whole
> portfolio, using the same rules and parameters across all markets** — a
> technique used extensively in this book."

**Nguồn độc lập thứ ba** cho khuyến nghị dùng nhiều thị trường (sau López de
Prado ch.11 tr.154 và Aronson ch.9 tr.451). Ba tác giả khác nhau, ba lý do khác
nhau, cùng một kết luận về phương pháp.

Ở đây lý do là **kỹ thuật**: dùng chung tham số trên nhiều thị trường làm tăng số
quan sát mà **không** tăng số tham số — đúng thứ tỉ lệ mà [L] tr.44 nói là quyết
định.

## 20. Chương 5 — kiểm định mô hình PHÁ VỠ KÊNH GIÁ, cùng họ với danh mục

Thiết lập: danh mục hàng hoá rộng, kiểm trong mẫu tới giữa thập niên 1990 và
ngoài mẫu tới 12/1998. So ba kiểu phá vỡ (kênh giá chỉ theo giá đóng; đỉnh-cao-
nhất/đáy-thấp-nhất; phá vỡ theo biến động) × ba kiểu lệnh (thị trường, dừng,
giới hạn) × các bộ lọc.

### Kết luận tổng — [M] tr. 107

> "**No technique, except restricting the model to the currencies, improved
> results enough to overcome transaction costs in the out-of-sample period.**"

> "In both samples, all models evidenced **deterioration over time that cannot be
> attributed to overoptimization. Breakout models of the kind studied here no
> longer work, even though they once may have.** This accords with the belief
> that there are fewer and fewer good trends to ride."

Đây là kết quả nặng và phải ghi nhận nguyên vẹn: một nghiên cứu có hệ thống, dữ
liệu tới 1998, kết luận rằng **mô hình phá vỡ đơn giản đã ngừng hoạt động**.

**Ba giới hạn khi chuyển sang dự án — [suy luận của ta]:**

1. mẫu dừng ở 1998; XAUUSD 2003-2026 là giai đoạn khác hoàn toàn;
2. tác giả kiểm trên **hàng hoá tương lai**, chịu chi phí đảo hạn mà CFD giao
   ngay không có;
3. kết luận "không vượt được chi phí giao dịch" phụ thuộc mức chi phí thập niên
   1990, cao hơn hiện nay nhiều.

Nhưng cảnh báo vẫn đứng vững: **họ chiến lược này có tiền sử suy giảm theo thời
gian**, và điều đó phải nằm trong kịch bản rủi ro chứ không bị bỏ qua.

### Bốn phát hiện chi tiết — mỗi cái đều chạm trực tiếp vào thiết kế hiện tại

**(a) Phá vỡ hoạt động tốt hơn ở PHÍA MUA — [M] tr. 106**

> "Restricting trades to long positions **greatly improved** the performance of
> the volatility breakout in-sample, and improved it to some extent out-of-sample.
> **Breakout models do better on the long side than on the short one.**"

Xác nhận độc lập, từ mẫu khác và thời kỳ khác, cho kết quả ~90 phép thử phía bán
của dự án ngày 03/08 (xem `downtrend-evidence-2026-08-03.md`). Không phải đặc thù
của vàng hay của giai đoạn 2003-2026.

**(b) Kênh đỉnh-đáy BỀN hơn phá vỡ theo biến động — [M] tr. 107**

> "Focus on support and resistance, fundamental verities of technical analysis
> that are unlikely to be 'traded away.' **The highest-high/lowest-low breakout
> held up better in the tests than other models**, even though it did not always
> produce the greatest returns. **Stay away from popular volatility breakouts**
> unless they implement some special twist."

Ủng hộ lựa chọn Donchian của dự án, và đồng thời là một dấu hỏi cho
`SqueezeBreakout`/`SqueezeBreakdown` — vốn là phá vỡ có điều kiện biến động.
`SqueezeBreakdown` đã bị bác bỏ; `SqueezeBreakout` hiện `BACKTEST_ONLY`.

**(c) Bộ lọc ADX KHÔNG có ích ngoài mẫu — [M] tr. 106-107**

> "The ADX trend filter had a smaller benefit in-sample and **provided no benefit
> out-of-sample.**"

> "**Do not rely on indicators like the ADX for trendiness determination.**"

Liên quan trực tiếp tới câu hỏi bộ lọc nén `atr < atr_ma` của
`DonchianH4Breakout`: đây cũng là một bộ lọc điều kiện thị trường gắn thêm vào
tín hiệu phá vỡ. Katz & McCormick tìm thấy loại bộ lọc ấy có ích trong mẫu và
**hết ích ngoài mẫu** — đúng hình dạng của thiên lệch khai thác dữ liệu.

Không dùng để lật phán quyết ngày 03/08 (xem lý do trong
`xau-strategy-matrix-2026-08-03.md` §4.1), nhưng đây là **nguồn thứ hai** nghi
ngờ bộ lọc, sau Aronson ch.8 tr.398.

**(d) Lệnh GIỚI HẠN là cải thiện lớn nhất — [M] tr. 107**

> "If possible, **use a limit order to enter the market.** The markets are noisy
> and usually give the patient trader an opportunity to enter at a better price;
> **this is the single most important thing one can do to improve a system's
> profitability.** Controlling transaction costs with limit orders can make a
> huge difference in the performance of a breakout model."

Trong bảng so ba kiểu lệnh: _"In all periods, the limit order performed best."_

**Đây là khuyến nghị có giá trị thực dụng cao nhất rút ra được từ cả cuốn sách,
và nó chạm đúng một thứ dự án đang làm.** Cần kiểm: các chiến lược hiện dùng
lệnh thị trường hay lệnh giới hạn? Nhật ký dự án ghi "limit order thật" trong
đợt pivot 15/07 — phải xác minh còn hiệu lực không.

Lưu ý đánh đổi: lệnh giới hạn giảm chi phí nhưng **bỏ lỡ** những cú phá vỡ không
quay lại. Với chiến lược bám xu hướng vốn sống nhờ số ít cú lớn, đó là rủi ro
thật. Katz & McCormick đã đo và kết luận lợi lớn hơn hại — nhưng trên hàng hoá
tương lai thập niên 1990, không phải vàng CFD hôm nay.

**(e) Thoát lệnh — [M] tr. 108**

> "Use something better than the standard exit to close open positions... **A
> good exit can go a long way toward making a trading system profitable.**"

Trùng với Van Tharp: _"expectancy is controlled by your exits"_. Hai nguồn độc
lập cùng chỉ vào tầng thoát lệnh.

### Vàng trong bảng kết quả theo thị trường — [M] tr. 106

> "The S&P 500, NYFE, **Comex Gold**, Corn, and the wheats had **positive
> out-of-sample returns with in-sample losses.**"

Tức vàng nằm nhóm "lỗ trong mẫu, lãi ngoài mẫu" — mẫu hình ngược với overfit,
nhưng cũng là dấu hiệu kết quả không ổn định giữa hai giai đoạn.

Và tương quan giữa lợi nhuận trong mẫu và ngoài mẫu trên các thị trường chỉ
**0,15** — rất thấp. Nghĩa là thị trường chạy tốt trong giai đoạn tối ưu chỉ hơi
có xu hướng chạy tốt trong giai đoạn kiểm chứng.

## 21. Việc phải làm rút ra từ Katz & McCormick

| #   | việc                                                                                                                                                            | mức ưu tiên                    | căn cứ        |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ | ------------- |
| 25  | **Kiểm xem các chiến lược dùng lệnh thị trường hay lệnh giới hạn**; nếu lệnh thị trường thì đo thử lệnh giới hạn — tác giả gọi đây là cải thiện đơn lẻ lớn nhất | **cao**                        | [M] tr. 107   |
| 26  | Đếm số tham số tự do của từng chiến lược và đối chiếu với số lệnh theo thang của [L] tr.44                                                                      | cao                            | [L] tr. 44-45 |
| 27  | Đưa "họ phá vỡ suy giảm theo thời gian" vào kịch bản rủi ro                                                                                                     | trung bình                     | [M] tr. 107   |
| 28  | Ghi nhận: kênh đỉnh-đáy bền hơn phá vỡ theo biến động — ủng hộ Donchian, nghi ngờ họ Squeeze                                                                    | trung bình                     | [M] tr. 107   |
| 29  | Ghi nhận nguồn thứ hai nghi ngờ bộ lọc điều kiện gắn thêm (ADX ↔ nén ATR)                                                                                       | thấp — không lật phán quyết cũ | [M] tr. 106   |

---

# Phần IV — Pring, _Technical Analysis Explained_ (4th ed. 2002)

## References bổ sung

| #   | nguồn                                                                                                                                                      | chương / trang                                  | nguyên lý lấy ra                                                                                       |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| [N] | Pring, M.J. (2002). _Technical Analysis Explained: The Successful Investor's Guide to Spotting Investment Trends and Turning Points_, 4th ed. McGraw-Hill. | Ch. 29 "Automated Trading Systems", tr. 539-550 | ưu và nhược của hệ thống cơ giới; tám quy tắc thiết kế; thị trường xu hướng so với thị trường đi ngang |

**Ghi chú nguồn:** bản `.md` do người dùng OCR lại ngày 03/08 từ PDF quét ảnh 329
trang. Bản OCR trộn cột ở vài chỗ; các trích dẫn dưới đây đã đối chiếu ngữ cảnh
trước sau để chắc chắn không ghép nhầm câu.

---

## 22. Nguyên tắc nền: khớp KHÔNG HOÀN HẢO tốt hơn khớp hoàn hảo — [N] tr. 539

> "most mechanical trading systems are based on historical data and are
> constructed from a more or less perfect fit with past, in the expectation that
> history will be repeated in the future. **This expectation will not necessarily
> be fulfilled, because market conditions change.**"

> "**it is better to design a system that gives a less-than-perfect fit, but more
> accurately reflects normal market conditions.** Remember that you are
> interested in future profits, not perfect historical simulations. **If special
> rules have to be invented to improve results, the chances are that the system
> will not operate successfully when extrapolated to future market conditions.**"

Câu cuối là một phép thử đơn giản mà dự án dùng được ngay: **mỗi khi phải thêm
một luật đặc biệt để cải thiện kết quả backtest, đó là dấu hiệu cảnh báo.**

Liên hệ trực tiếp tới bộ lọc nén `atr < atr_ma` của `DonchianH4Breakout` — đúng
là một "luật đặc biệt" thêm vào để cải thiện kết quả. Đây là **nguồn thứ ba**
nghi ngờ bộ lọc ấy, sau Aronson ch.8 tr.398 và Katz & McCormick ch.5 tr.106.

Vẫn không lật phán quyết ngày 03/08 (lý do ở `xau-strategy-matrix-2026-08-03.md`
§4.1), nhưng ba nguồn độc lập cùng chỉ vào một chỗ thì đáng ghi rõ.

## 23. Hai cách dùng hệ thống cơ giới — [N] tr. 539

> "I believe that mechanical trading systems should be used in one of two ways.
> The preferred method is to incorporate a well thought-out mechanical trading
> system to **alert the trader or investor that a trend reversal has probably
> taken place.** In this method the mechanical trading system is an important
> filter, but represents just one more indicator in the overall decision-making
> process."

> "The other way... is to **take action on every signal.** If the system is well
> thought out, it should generate profits over the long term. However, if you
> pick and choose which signal to follow without other independently based
> technical criteria, you run the risk of making emotional decisions, thereby
> **losing the principal benefit of the mechanical approach.**"

Dự án thuộc cách thứ hai — hành động trên mọi tín hiệu, không có người can thiệp.
Pring nói cách này hợp lệ, với điều kiện **không chọn lọc tín hiệu**.

**Áp dụng — có một điều đáng kiểm:** hệ thống có các cổng chặn (`check_cycle_gates`,
macro veto, circuit breaker) vốn _bỏ qua_ một số tín hiệu. Theo Pring, việc bỏ
qua tín hiệu chỉ hợp lệ khi dựa trên **tiêu chí kỹ thuật độc lập được định
nghĩa trước**, không phải phán đoán tình huống. Các cổng của dự án đều là luật
cố định, nên đạt điều kiện — nhưng cổng dựa trên đánh giá của LLM
(`macro_circuit_breaker` đọc regime từ mô hình ngôn ngữ) thì **không** rõ ràng
thoả, vì nó không phải tiêu chí kỹ thuật cố định.

## 24. Năm nhược điểm — [N] tr. 540-541

| #   | nhược điểm                                                                                                                                                   | trạng thái dự án                                                                                      |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| 1   | không hệ thống nào chạy tốt mọi lúc; có thể có giai đoạn dài thất bại                                                                                        | đã ghi nhận qua "momentum crashes" (Chan ch.6 tr.151)                                                 |
| 2   | dùng dữ liệu quá khứ dự báo tương lai không nhất thiết hợp lệ vì tính chất thị trường đổi                                                                    | đã ghi nhận                                                                                           |
| 3   | **sự kiện ngẫu nhiên có thể phá hỏng hệ thống kém thiết kế** — Hong Kong 1987, thị trường đóng cửa 7 ngày, không có cơ hội thoát dù có tín hiệu bán          | **chưa có kịch bản này**; vàng có khoảng trống cuối tuần, và Chan ch.8 tr.182 cũng cảnh báo cùng điều |
| 4   | **phần lớn hệ thống cơ giới thành công đều bám xu hướng; và có những giai đoạn DÀI thị trường không có xu hướng, khiến hệ thống không sinh lời**             | đúng mô tả danh mục hiện tại                                                                          |
| 5   | **backtest không nhất thiết mô phỏng đúng điều đã xảy ra** — không phải lúc nào cũng khớp được ở giá hệ thống chỉ ra, vì thanh khoản mỏng hoặc môi giới chậm | dự án có SimBroker với spread thật; nhưng chưa mô phỏng trượt giá hay từ chối lệnh                    |

Trích nguyên văn nhược điểm 5:

> "**'Back-testing' won't necessarily simulate what actually would have happened.
> It is not always possible to get an execution at the price indicated by the
> system**, because of illiquidity, failure of your broker to execute orders on
> time, and so forth."

## 25. Tám quy tắc thiết kế — [N] tr. 541-544

| #   | quy tắc                                                                                                 | trạng thái dự án                                                                 |
| --- | ------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| 1   | càng nhiều dữ liệu kiểm được, kết quả tương lai càng đáng tin                                           | 23,2 năm XAUUSD — đạt                                                            |
| 2   | **đánh giá bằng cách ngoại suy sang một giai đoạn khác** — thiết kế trên 1977-1985, kiểm trên 1985-1990 | có dev/holdout, nhưng một đường duy nhất và đã mở nhiều lần (AFML ch.11 tr.155)  |
| 3   | **định nghĩa hệ thống thật chính xác** — mọi tín hiệu vào phải có tín hiệu ra tương ứng                 | **đạt**: mọi chiến lược có SL và hạn giữ, nên mọi lệnh vào đều có lối ra bảo đảm |
| 4   | **đủ vốn sống qua chuỗi thua tệ nhất** — giả định kịch bản xấu nhất                                     | có CPPI theo đệm và MC 4.000 đường đời                                           |
| 5   | **theo mọi tín hiệu, không hỏi lại**                                                                    | đạt — hệ thống tự động                                                           |
| 6   | **dùng danh mục đa dạng**                                                                               | chỉ một symbol; vừa được phép mở rộng forex                                      |
| 7   | **chỉ giao dịch thị trường có đặc tính xu hướng tốt**                                                   | chưa có phép đo chính thức nào chọn thị trường theo tiêu chí này                 |
| 8   | **GIỮ ĐƠN GIẢN**                                                                                        | 4-5 tham số cho 111-275 lệnh — Katz ch.3 tr.44 nói là quá nhiều                  |

Trích quy tắc 3 nguyên văn ([N] tr. 541):

> "**Define the system precisely.** This is important for two reasons. First, if
> the rules occasionally leave you in doubt about their correct interpretation,
> some degree of subjectivity will permeate the approach. Second, **for every buy
> signal there should be a sell signal, and vice versa.**... there could be long
> periods during which a countervailing signal is not generated, simply because
> the indicator does not move to these extremes. **Failure to define the system
> precisely can therefore result in significant losses.**"

Ý của Pring ở đây không phải "phải có cả mua lẫn bán" mà là **mọi lệnh vào phải
có lối ra được định nghĩa trước**. Dự án đạt điều này bằng SL cộng hạn giữ — mọi
lệnh đều có thời hạn hữu hạn. **Verified.**

Trích quy tắc 4 ([N] tr. 542) — có một quan sát đáng chú ý:

> "When you are devising a system, it is always a good idea to assume the worst
> possible scenario and to make sure that you start off with enough capital to
> survive such a period. In this respect, it is worth noting that **the most
> profitable moves usually occur after a prolonged period of whipsawing.**"

Câu cuối là lý lẽ chống lại việc tắt chiến lược sau chuỗi thua — đúng lúc cần
kiên nhẫn nhất lại là lúc muốn bỏ cuộc nhất.

Trích quy tắc 8 ([N] tr. 544):

> "**Keep it simple.** It is always possible to invent special rules to make
> back-testing more profitable. **Overcome this temptation.** Keep the rules
> simple, few in number, and logical. The results are more likely to be
> profitable in the future, when profitability counts."

## 26. Thị trường xu hướng và thị trường đi ngang — nguồn thứ hai cho việc GHÉP hai họ

[N] tr. 544-545:

> "MAs... are virtually useless in a trading range market since they move right
> through the middle of the price fluctuations, and almost always result in
> unprofitable signals. **Oscillators, on the other hand, come into their own in
> a trading range market.** They are continually moving from overbought [to
> > oversold, giving] timely buy and sell signals. **During a persistent uptrend or
> downtrend, the oscillator is of relatively little use** because it gives
> premature buy and sell signals, often taking the trader out at the beginning of
> a major move."

Và kết luận:

> "**The ideal automated system therefore should include a combination of an
> oscillator and a trend-following indicator.**"

**Đây là nguồn độc lập thứ hai** cho cùng một khuyến nghị, sau Chan ch.6 tr.154
(_"Adding momentum strategies to a portfolio of mean-reverting strategies allows
us to achieve higher Sharpe ratios and smaller drawdowns than either type of
strategy alone"_).

Hai tác giả khác nhau, hai lý do khác nhau — Chan nói theo góc danh mục
(tương quan thấp giữa hai họ), Pring nói theo góc chế độ thị trường (mỗi họ hoạt
động ở một chế độ) — cùng chỉ vào việc **ghép bám xu hướng với hồi quy trung
bình**.

Danh mục hiện tại **toàn bám xu hướng**. Ứng viên hồi quy trung bình H4 tìm được
ngày 03/08 (xem `xau-strategy-matrix-2026-08-03.md` §3) giờ có hai nguồn hậu
thuẫn về mặt nguyên lý, chứ không chỉ một phép đo tương quan.

Nhưng lưu ý điểm khác biệt quan trọng: Pring nói tới **chỉ báo dao động** dùng
làm tín hiệu vào lệnh trong biên; ứng viên của dự án là **đảo chiều ngắn hạn sau
một nến**, cơ chế khác (Jegadeesh 1990, Lehmann 1990). Trùng về tinh thần "ghép
hai họ", không trùng về công cụ.

## 27. Việc phải làm rút ra từ Pring

| #   | việc                                                                                                                                                        | mức ưu tiên | căn cứ                              |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | ----------------------------------- |
| 33  | Ghi nhận nguồn **thứ hai** cho việc ghép bám-xu-hướng với hồi-quy-trung-bình → nâng ưu tiên ứng viên H4                                                     | **cao**     | [N] tr. 545 + Chan ch.6 tr.154      |
| 34  | Kiểm cổng dựa trên đánh giá LLM (`macro_circuit_breaker`): Pring nói bỏ qua tín hiệu chỉ hợp lệ khi dựa trên **tiêu chí kỹ thuật độc lập định nghĩa trước** | **cao**     | [N] tr. 539                         |
| 35  | Thêm kịch bản "thị trường đóng cửa / không thoát được" vào stress test                                                                                      | trung bình  | [N] tr. 540, trùng Chan ch.8 tr.182 |
| 36  | Mô phỏng trượt giá và từ chối lệnh trong SimBroker, không chỉ spread                                                                                        | trung bình  | [N] tr. 541                         |
| 37  | Ghi nhận quy tắc 3 (mọi lệnh vào có lối ra định nghĩa trước) là **Verified**                                                                                | thấp        | [N] tr. 541                         |
| 38  | Nguồn **thứ ba** nghi ngờ "luật đặc biệt thêm vào để cải thiện backtest" — không lật phán quyết, chỉ ghi                                                    | thấp        | [N] tr. 539                         |

---

# Phần V — Kirkpatrick & Dahlquist, _Technical Analysis: The Complete Resource_ (2nd ed. 2011)

## References bổ sung

| #   | nguồn                                                                                                                                       | chương / trang                                  | nguyên lý lấy ra                                                                                 |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| [O] | Kirkpatrick, C.D. & Dahlquist, J.R. (2011). _Technical Analysis: The Complete Resource for Financial Market Technicians_, 2nd ed. FT Press. | Ch. 22 "System Design and Testing", tr. 546-560 | nguyên tắc tối ưu hoá thực tế; ba phương pháp; đo tính bền; chẩn đoán trong-mẫu so với ngoài-mẫu |
| [P] | Ruggiero, M. (2005)                                                                                                                         | dẫn trong [O] tr. 547                           | tính nhất quán quan trọng hơn lợi nhuận tuyệt đối khi chia mẫu                                   |

Đây là giáo trình chính thức của CMT Association — thay thế cho Murphy và Pring
ở phần phương pháp luận, và chặt hơn cả hai về mặt kiểm định.

---

## 28. Tối ưu hoá CÓ ÍCH — nhưng chỉ theo một cách — [O] tr. 546

Điểm khác biệt so với các nguồn khác: K&D nêu rõ tối ưu hoá dùng để **loại bỏ**,
không phải để tìm điểm tốt nhất.

> "if they do not work on the past data, it is highly likely they will not work
> in the future. Thus, **optimizing can eliminate useless rules and parameters.**"

> "Optimizing is also useful in determining whether certain types of stops are
> useful. Often the designer finds that **there is a limit — for example, to a
> protective stop — beyond which the stop does not add to the system
> performance.** Often, the distance of trailing stops is too close to the last
> price, causing premature exits."

Trùng đúng vai trò mà López de Prado ch.11 tr.153 gán cho backtest: _"the purpose
of a backtest is to discard bad models, not to improve them."_ Hai nguồn độc lập,
cùng một vai trò.

### Sáu nguyên tắc tối ưu hoá thực tế — [O] tr. 546

> "The basic principles of realistic optimization are to **keep it simple**, test
> out-of-sample data against in-sample optimization results, **preferably use
> baskets of securities**, **determine parameter SETS instead of single
> parameters**, understand that the best results are high profits with minimal
> risk, and **do not expect to find the Holy Grail.**"

Nguyên tắc "bộ tham số thay vì một tham số đơn lẻ" là cách nói khác của **cao
nguyên tham số** — chọn một vùng ổn định, không chọn đỉnh nhọn.

## 29. Đa thị trường là phép chống khớp đường cong — nguồn ĐỘC LẬP THỨ TƯ

Trích nguyên văn [O] tr. 548 — đây là phát biểu mạnh nhất trong tất cả các nguồn
đã đọc về chủ đề này:

> "One other method of reducing the effect of curve-fitting is to **use more than
> one market as the out-of-sample test. It is difficult to have the same
> parameter set in different markets and at the same time curve-fit.** This
> appears counterintuitive because most analysts would think that each market is
> different, has its own personality, and requires different parameters. Indeed,
> when looking at publicly available systems for sale, **one method of
> eliminating a system from consideration is if it has different parameters for
> different markets. This usually indicates that the results are from
> curve-fitting**, not real-time performance. **A reliable system should work in
> most markets.**"

Bốn nguồn độc lập giờ cùng khuyến nghị dùng nhiều thị trường, mỗi nguồn một lý do:

| nguồn                                  | lý do                                                                              |
| -------------------------------------- | ---------------------------------------------------------------------------------- |
| López de Prado ch.11 tr.154            | luật chỉ chạy trên một chứng khoán nhiều khả năng là khám phá giả                  |
| Katz & McCormick ch.3 tr.45            | tăng số quan sát mà không tăng số tham số                                          |
| Aronson ch.9 tr.451                    | nhân bản là bằng chứng mạnh                                                        |
| **Kirkpatrick & Dahlquist [O] tr.548** | **khó mà vừa khớp đường cong vừa dùng chung một bộ tham số trên nhiều thị trường** |

### Đối chiếu thẳng với kết quả 03/08 — và đây là điều khó nghe

K&D đặt tiêu chuẩn: _"A reliable system should work in **most** markets."_

`DonchianH4Breakout` với tham số production chạy được trên **3/9** thị trường.
Theo tiêu chuẩn này thì đó là **cảnh báo**, không phải kết quả trung tính.

Ba điều làm nhẹ bớt, phải ghi cả:

1. Murphy ch.16 tr.396 chỉ ra chín thị trường không độc lập — thực chất gần với
   2 trên 3 nhóm;
2. White's Reality Check cho XAUUSD p = 0,0338, tức edge trên vàng có thật sau
   khi đã hiệu chỉnh chọn-trong-chín;
3. tham số được chỉnh cho vàng, không phải chọn chung cho cả rổ — nên đây chưa
   phải phép thử mà K&D mô tả.

Nhưng điều **không** làm nhẹ được: nếu chạy đúng phép thử của K&D — chọn một bộ
tham số chung tốt nhất cho cả rổ rồi kiểm — mà vẫn chỉ vài thị trường chạy được,
thì theo tiêu chuẩn này hệ thống không đạt. Đó là phép thử còn nợ.

## 30. Ba phương pháp tối ưu hoá — [O] tr. 547-548

### (a) Toàn mẫu, kèm phép kiểm NHẤT QUÁN theo phần mười

> "the optimization is on **a basket of securities**... and over a long enough
> period to generate a large number of trades... After determining the optimal
> parameter sets... the next step is to **divide the optimization period roughly
> into tenths and run a test on each period** using the derived parameter sets.
> The results from these ten different periods then can be analyzed for
> **consistency**."

Cần xem: mức sụt vốn, số tín hiệu, số lần thua liên tiếp, lợi nhuận ròng tính
theo phần trăm sụt vốn tối đa.

> "**The actual amount of net profit is LESS IMPORTANT for each stage than are
> the determinants of risk and the consistency of results** (Ruggiero, 2005). If
> the results are not consistent, the system has a major problem and should be
> optimized using other means or **discarded**."

**Đây là phép chẩn đoán dự án chưa từng chạy**, và nó rẻ: chia 23 năm dữ liệu
XAUUSD thành mười khúc, chạy cùng bộ tham số, xem mười kết quả có nhất quán
không. Nó khác dev/holdout ở chỗ cho **mười** điểm quan sát thay vì hai — đúng
tinh thần "nhiều đường kiểm thử" mà López de Prado ch.11 tr.155 đòi hỏi.

### (b) Chia 70-80% trong mẫu, 20-30% ngoài mẫu — và cảnh báo về việc mở lại

> "**the more that the out-of-sample results are used as the determinant of
> parameter sets, the more that the objectivity of the optimization is
> compromised** and the closer to curve-fitting the process becomes. Eventually,
> if continued in this manner, **the out-of-sample data becomes the same as the
> sample data**, and the optimization is just curve-fitting."

Mô tả chính xác điều đã xảy ra ngày 03/08: tôi mở holdout 2017-2026 nhiều lần
trong một ngày. Nguồn thứ hai cho cùng cảnh báo, sau López de Prado ch.11 tr.155.

### (c) Walk forward — cửa sổ trượt

Tối ưu 70-80% đầu, kiểm trên một khúc nhỏ ngoài mẫu (một tháng tới một năm), ghi
kết quả, dịch cửa sổ, lặp. Điểm kiểm quan trọng:

> "**If some parameter set during the walk forward process suddenly changes, the
> system is unlikely to work in the future.**"

## 31. MÂU THUẪN THẬT giữa các nguồn — số lệnh tối thiểu

[O] tr. 549:

> "The next aspect is to be sure that the number of trades is large enough to
> make the results significant. **The rule of thumb is between 30 and 50 trades,
> with 50 or more being the ideal.**"

Điều này **mâu thuẫn trực tiếp** với hai nguồn khác đã đọc:

| nguồn                              | ngưỡng số lệnh                          | loại lập luận                                                                       |
| ---------------------------------- | --------------------------------------- | ----------------------------------------------------------------------------------- |
| Kirkpatrick & Dahlquist [O] tr.549 | **30-50, lý tưởng ≥50**                 | quy tắc ngón tay cái, không dẫn tính toán                                           |
| Wright ch.2 tr.19                  | **"many hundreds to thousands"**        | **định lượng** — thí nghiệm sai số chuẩn trên 683 lệnh vàng và 24.982 lệnh hàng hoá |
| Katz & McCormick ch.3 tr.44        | vài chục tham số cần **vài nghìn** lệnh | định lượng, qua bậc tự do                                                           |

**Phán quyết của tôi: theo Wright và Katz.** Lý do: cả hai đưa ra lập luận định
lượng kiểm chứng được, còn K&D chỉ nêu quy tắc ngón tay cái không kèm dẫn chứng.
Wright thậm chí làm thí nghiệm **trên chính vàng** và cho thấy ở cỡ mẫu 300 lệnh
sai số chuẩn vẫn khoảng 100 đô so với lợi nhuận trung bình 32,80 đô.

Ghi rõ mâu thuẫn này thay vì chọn im lặng — nếu sau này ai đó đọc K&D và thấy
dự án dùng ngưỡng cao hơn nhiều, họ cần biết vì sao.

## 32. Hai phép chẩn đoán mới, chưa từng chạy — [O] tr. 549

### (a) So sánh CẤU TRÚC trong mẫu và ngoài mẫu, không chỉ hiệu suất

> "the comparisons between in-sample and out-of-sample results **should differ in
> performance but should NOT materially differ in** average duration of trades,
> maximum consecutive winners and losers, the worst losing trade, and the average
> losing trade."

Đây là phép chẩn đoán tinh tế: hiệu suất **được phép** giảm ngoài mẫu (đó là
điều bình thường theo Aronson ch.6), nhưng **cấu trúc** của tập lệnh thì không
được đổi. Nếu thời gian giữ trung bình hay lệnh thua tệ nhất khác hẳn giữa hai
giai đoạn, đó là dấu hiệu chiến lược đang làm việc khác chứ không phải cùng một
việc với vận may khác.

### (b) Kiểm tính GIÒN — luật không bao giờ kích hoạt

> "we should test for **brittleness**, the phenomenon when one or more of the
> rules are never triggered."

**Áp dụng ngay:** dự án đã gặp đúng lỗi này bốn lần trong một ngày với
`SqueezeBreakdown` — luật ra 0 lệnh vì lỗi kỹ thuật, và không có phép kiểm nào
bắt được. Một phép kiểm tính giòn tự động sẽ bắt cả bốn.

## 33. Chỉ số tổng hợp K&D đề xuất — [O] tr. 548-549

> "most important, they look at **the net profit as a percentage of the maximum
> drawdown.** The means of profiting from a system, any system of investing, are
> determined by the amount of risk involved... **The net profit percentage of
> maximum drawdown describes quickly the bottom-line performance of the system.**"

Với FTMO, chỉ số này đặc biệt hợp lý vì sụt vốn là ràng buộc cứng chứ không chỉ
là thước đo khó chịu. Danh mục hiện tại 2015-2026: +20,02% lợi nhuận trên 3,20%
sụt vốn → tỉ số **6,3**.

## 34. Việc phải làm rút ra từ Kirkpatrick & Dahlquist

| #   | việc                                                                                                                                                | mức ưu tiên                                  | căn cứ      |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- | ----------- |
| 39  | Chạy **phép kiểm nhất quán theo phần mười** — chia 23 năm thành 10 khúc, cùng bộ tham số, xem sụt vốn / số tín hiệu / chuỗi thua có nhất quán không | **cao** — rẻ, cho 10 điểm quan sát thay vì 2 | [O] tr. 547 |
| 40  | Thêm **phép kiểm tính giòn** tự động: cảnh báo khi một luật không bao giờ kích hoạt                                                                 | **cao** — đã mất một ngày vì đúng lỗi này    | [O] tr. 549 |
| 41  | So sánh **cấu trúc** trong-mẫu với ngoài-mẫu (thời gian giữ TB, chuỗi thắng/thua dài nhất, lệnh thua tệ nhất), không chỉ hiệu suất                  | cao                                          | [O] tr. 549 |
| 42  | Ghi **lợi nhuận ròng trên sụt vốn tối đa** vào mọi báo cáo                                                                                          | trung bình                                   | [O] tr. 548 |
| 43  | Ghi nhận mâu thuẫn số lệnh tối thiểu giữa các nguồn; theo Wright/Katz vì lập luận định lượng                                                        | thấp — chỉ ghi tài liệu                      | §31         |

---

# Phan VI - Faith, Way of the Turtle (2007) ch.12

## 36. Các thước đo hiệu suất thông dụng KHÔNG BỀN — [R] tr. 183-186

Đây là đóng góp phương pháp luận mà **chưa nguồn nào khác trong kho nêu**, và nó
chạm thẳng vào cách dự án báo cáo số liệu.

> "the generally accepted performance measures are **not very stable — they are
> not robust.** This makes it difficult to assess the relative merits of an idea
> because **small changes in a few trades can have a large effect** on the values
> of these nonrobust measures."

> "A statistic is robust if changing a small part of the data set does not change
> that statistic significantly... **This makes it easy to overfit and to fool
> yourself with results that you will not be able to match in real life.**"

### Bằng chứng định lượng — [R] tr. 184

Faith dịch ngày bắt đầu lùi một tháng và ngày kết thúc lùi hai tháng, không đổi
gì khác:

| hệ thống              |          | lợi nhuận |      MAR |   Sharpe |
| --------------------- | -------- | --------: | -------: | -------: |
| Triple Moving Average | mốc gốc  |     43,2% |     1,39 |     1,25 |
|                       | mốc dịch | **46,2%** | **1,61** | **1,37** |
| ATR Channel Breakout  | mốc gốc  |     51,7% |     1,31 |     1,39 |
|                       | mốc dịch | **54,9%** | **1,49** | **1,47** |

Chỉ dịch ba tháng trên hơn mười năm, mà Sharpe đổi 0,08-0,12 và MAR đổi 0,18-0,22.

Lý do ([R] tr. 185): tử số của cả MAR lẫn Sharpe đều chứa lợi nhuận, mà lợi
nhuận nhạy với mốc đầu-cuối; và sụt vốn tối đa cũng nhạy khi nó rơi gần hai đầu.
MAR nhạy gấp đôi vì cả tử lẫn mẫu đều nhạy.

### RAR% — lợi nhuận năm theo hồi quy — [R] tr. 186

Thay vì CAGR% (độ dốc đường thẳng nối điểm đầu với điểm cuối), dùng **độ dốc của
đường hồi quy tuyến tính qua TOÀN BỘ các điểm** trên đồ thị log.

|       | mốc gốc | mốc dịch |       thay đổi |
| ----- | ------: | -------: | -------------: |
| CAGR% |   43,2% |    46,2% |  **+3,0 điểm** |
| RAR%  |  54,67% |   54,78% | **+0,11 điểm** |

> "**the CAGR% was almost 30 times more sensitive** to the change in the end
> dates."

### Sụt vốn tối đa là MỘT điểm — [R] tr. 187

> "The maximum drawdown is **a single point on an equity curve**, and so you are
> missing out on some valuable additional data. A better measure is one that
> includes more drawdowns. A system that had five large drawdowns of 32, 34, 35,
> 35, and 36 percent **would be harder to trade** than would a system that had
> drawdowns of 20, 25, 26, 29, and 36 percent."

Và chiều thứ hai — **thời lượng**:

> "All 30 percent drawdowns are not the same. I would not mind a drawdown that
> lasted only two months before recovering to new highs nearly as much as I would
> mind one that took two years to reach new highs."

### R-cubed — [R] tr. 188

```
R³ = RAR% / (sụt vốn tối đa trung bình × thời lượng trung bình / 365)

  sụt vốn tối đa trung bình = trung bình 5 lần sụt vốn LỚN NHẤT
  thời lượng trung bình     = trung bình 5 lần sụt vốn DÀI NHẤT (ngày)
```

Ví dụ của Faith: RAR% 50%, sụt vốn trung bình 25%, thời lượng trung bình 365 ngày
→ R³ = 50 / (25 × 365/365) = **2,0**.

> "R-cubed is a risk/reward measure that accounts for risk from **both a severity
> perspective and a duration perspective.**"

### Đối chiếu thẳng với cách dự án báo cáo — và tôi đã làm sai suốt phiên này

Mọi con số tôi báo cáo trong phiên 03/08 đều thuộc nhóm **không bền** theo Faith:

| tôi đã báo                      | vấn đề                                                      |
| ------------------------------- | ----------------------------------------------------------- |
| "2015-2026 +20,02% / DD 3,20%"  | cả hai đều nhạy với mốc đầu-cuối; DD là một điểm duy nhất   |
| "R tổng +48,6 so với +85,1"     | nhạy với mốc                                                |
| "R/lệnh +0,4378 so với +0,2819" | ít nhạy hơn, nhưng bỏ qua thời lượng và hình dạng đường vốn |
| "Sharpe thực +0,56"             | Faith chứng minh Sharpe nhạy với mốc                        |

Phép kiểm bỏ bộ lọc nén ngày 03/08 — trong đó R/lệnh giảm 35,6% và tôi giữ
nguyên bộ lọc theo tiêu chí đã ghi trước — có thể cho kết quả khác nếu đo bằng
R³. **Nhưng không được đo lại bằng thước mới để lật phán quyết cũ** (Aronson ch.7
tr.354-355). Thước mới chỉ dùng cho câu hỏi mới.

## 37. Lấy mẫu: mẫu ngắn chỉ chứa một hai trạng thái thị trường — [R] tr. 182

> "The problem with tests conducted over a short period is that during that period
> the market may have been in **only one or two of the market states**... If the
> market changes its state, the methods being tested may not work as well...
> **testing must be done in a way that maximizes the likelihood that the trades
> taken in the test are representative of what the future may hold.**"

Và một hình ảnh sắc:

> "This is perhaps most commonly seen when traders paper trade or backtest over
> only the very most recent history. **This is like polling at the Democratic
> convention.**"

Trùng với Kirkpatrick & Dahlquist ch.22 tr.547 (mẫu phải gồm cả xu hướng lẫn đi
ngang) và Katz & McCormick ch.3 tr.44 (mẫu đại diện phải có bò, gấu, và khủng
hoảng).

## 38. Việc phải làm rút ra từ Faith

| #   | việc                                                                                                                                               | mức ưu tiên                                               | căn cứ          |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- | --------------- |
| 44  | Thêm **RAR%** và **R-cubed** vào tầng báo cáo; ngừng dùng CAGR% và sụt-vốn-tối-đa-một-điểm làm thước so sánh chính                                 | **cao** — mọi con số phiên 03/08 đều thuộc nhóm không bền | [R] tr. 186-188 |
| 45  | Báo cáo **trung bình 5 lần sụt vốn lớn nhất** và **trung bình 5 thời lượng sụt vốn dài nhất**, không chỉ một con số DD                             | cao                                                       | [R] tr. 187     |
| 46  | Đối chiếu dừng lỗ: Turtle dùng **2N**, `DonchianH4Breakout` dùng 1,5×ATR, `SwingDon` dùng 2,5×ATR — ghi nhận sai lệch, chưa kết luận               | thấp                                                      | [Q] tr. 39      |
| 47  | Ghi nhận lập luận Faith ủng hộ **lệnh thị trường**: "don't miss a trend or you might kill your whole year" — đối trọng với Katz & McCormick tr.107 | thấp — quyết định đã chốt                                 | [Q] tr. 39      |

---

# Phần VII — Wright, _Building Reliable Trading Systems_ (2013) ch.4

## References bổ sung

| #   | nguồn                                                                      | chương / trang                                      | nguyên lý lấy ra                                                                                  |
| --- | -------------------------------------------------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| [U] | Wright, K. (2013). _Building Reliable Trading Systems_. John Wiley & Sons. | Ch. 4 "Trading System Elements: Entries", tr. 45-64 | phương pháp "sức mạnh điểm vào"; so sánh 7 kiểu điểm vào trên rổ 56 hàng hoá; hiện tượng chen lấn |

## 46. Phương pháp "sức mạnh điểm vào" — [U] tr. 45-64

Wright đo **lợi nhuận trung bình mỗi lệnh theo số ngày kể từ lúc vào**, tách
riêng từng cửa sổ tham số, trên rổ 56 hàng hoá. Không dừng lỗ, không chốt lời,
không chi phí — chủ ý tách sức mạnh của điểm vào khỏi mọi quyết định thoát lệnh.

Ba thứ đọc được từ một đường cong như vậy, và dự án chưa từng đo cái nào:

1. điểm vào có sức mạnh thật không (đường có tách nhau và bền không);
2. lợi nhuận đạt đỉnh ở ngày thứ mấy → gợi ý thời gian giữ **suy ra từ dữ liệu**;
3. lợi nhuận có âm trong những nến đầu không → chi phí chen lấn.

### Donchian thắng mọi điểm vào khác — [U] Bảng 4.1-4.4

Trên 56 hàng hoá, so 7 kiểu điểm vào ở 4 độ dài cửa sổ:

| cửa sổ | điểm vào tốt nhất        | lợi nhuận đỉnh/lệnh | ngày đạt đỉnh |
| ------ | ------------------------ | ------------------: | ------------: |
| 10 nến | **Donchian**             |              373,88 |            19 |
| 20 nến | Donchian ≈ độ lệch chuẩn |              559,47 |            15 |
| 40 nến | Donchian ≈ độ lệch chuẩn |              766,99 |            16 |
| 80 nến | Donchian                 |              973,30 |            16 |

> "Using 10 bars of information, **the Donchian entry is far and away the best.**"

> "If you can find something that competes in performance with the Donchian,
> standard deviation, or RSI entries in any time frame, **you have a trading
> nugget.**"

**Đây là xác nhận độc lập mạnh cho lựa chọn Donchian của dự án** — trên 56 thị
trường, không phải trên vàng, nên không bị nhiễm bởi việc dự án đã chọn nó.

Chi tiết đáng chú ý: **ngày đạt đỉnh gần như không đổi (15-19) dù cửa sổ nhìn
lại đổi từ 10 lên 80 nến.** Độ dài xu hướng bắt được không tỉ lệ với độ dài cửa
sổ phát hiện.

### Hiện tượng chen lấn — [U] tr. 48-49

> "Because of its popularity, almost every entry will have huge entry volume and
> corresponding **slippage, or price pullback, for a few days**... Profit doesn't
> start to accrue until some number of days after the signal."

Giải thích của Wright: tín hiệu càng nổi tiếng càng nhiều người vào cùng lúc,
thanh khoản không đỡ nổi, giá lùi lại vài ngày rồi mới đi. Ông đề nghị hoãn vào
lệnh hoặc dùng lệnh giới hạn. Dự án đã chốt **lệnh thị trường** (người dùng
quyết; Faith ch.3 tr.39 ủng hộ vì bỏ lỡ xu hướng thì mất cả năm) — nên ở đây chỉ
**đo** chi phí này, không đề xuất đổi loại lệnh.

## 47. Đo trên vàng: đỉnh ở ~75 nến H4, dự án giữ 12 — và vì sao đây CHƯA phải kết luận

Module: `src/python/research/validation/entry_power.py` (18 test).

Đo trực tiếp trên dữ liệu dự án, H4, 5 cửa sổ × 5 thị trường:

| thị trường      | mốc đỉnh (nến H4) |   quy ra ngày |
| --------------- | ----------------: | ------------: |
| XAUUSD          |             75-86 |     12,5-14,3 |
| XAGUSD          |             70-85 |     11,7-14,2 |
| USDJPY          |             7-118 |   rất tản mạn |
| EURUSD / GBPUSD |              2-14 | gần như nhiễu |

Trên kim loại quý, đỉnh rơi vào **12-14 ngày** — khớp đáng chú ý với 15-19 ngày
của Wright trên một rổ 56 hàng hoá hoàn toàn khác. Forex thì không có gì, trùng
với phát hiện 19/07 rằng Donchian không tổng quát hoá sang FX.

`DonchianH4Breakout` giữ **12 nến H4 = 2 ngày**. Tại mốc 12 nến, lợi nhuận trung
bình chỉ bằng khoảng **3-13%** mức đỉnh.

### Nhưng phép kiểm nghiêm túc nói KHÔNG

Nhìn thấy t ≥ 2 ở 5/25 cấu hình, tôi suýt báo đây là phát hiện. Đó sẽ là sai
lầm: **mốc đỉnh được chọn SAU KHI nhìn cả 120 mốc**, nên t tại chính mốc đó là
tiêu chí chọn chứ không phải ước lượng — đúng cảnh báo Aronson ch.6 tr.323-330.

Chạy White's Reality Check với thống kê tối đa trên toàn bộ 120 lựa chọn thời
gian giữ, bootstrap theo LỆNH để giữ cấu trúc tương quan giữa các mốc:

| thị trường | cửa sổ | mốc tốt nhất | TB tại mốc đó | TB tại 12 |          p |
| ---------- | -----: | -----------: | ------------: | --------: | ---------: |
| XAUUSD     |     10 |           86 |      +0,00176 |  +0,00006 |     0,0592 |
| XAUUSD     |     20 |           86 |      +0,00210 |  +0,00028 |     0,0552 |
| XAUUSD     |     40 |           86 |      +0,00224 |  +0,00010 |     0,0912 |
| XAUUSD     |     80 |           75 |      +0,00263 |  +0,00068 |     0,1026 |
| XAUUSD     |    200 |           75 |      +0,00556 |  +0,00086 | **0,0102** |
| XAGUSD     | 10-200 |        70-85 |             — |         — |  0,10-0,55 |

**Bonferroni cho 10 cấu hình (α = 0,005): 0/10 vượt.**

### Phán quyết trung thực

Chiều cao của đỉnh **không** phân biệt được với thứ ta thu được khi lấy max của
120 chuỗi nhiễu tương quan. Không được báo "giữ lâu hơn lãi gấp 5,5 lần" — con
số đó là ảo ảnh chọn lọc.

Nhưng **vị trí** của đỉnh thì đáng chú ý theo cách mà Bonferroni không đo được:
70-86 nến trên cả 10 cấu hình, hai thị trường, năm cửa sổ — và trùng với 15-19
ngày mà Wright đo độc lập trên 56 hàng hoá khác. Sự trùng khớp xuyên nguồn đó là
một dạng nhân bản (Aronson ch.9 tr.451), dù nó không cứu được ý nghĩa thống kê
của từng phép kiểm riêng lẻ.

Cần ghi rõ vì sao 10 cấu hình này **không phải 10 xác nhận độc lập**: bốn cửa sổ
trên cùng XAU chồng lấn nặng, và XAU-XAG tương quan 0,82 (Katsanos ch.7 tr.96).
Thực chất gần với 1-2 quan sát.

**Trạng thái: GIẢ THUYẾT, không phải phát hiện.** Điều duy nhất được phép kết
luận lúc này là con số `HOLD_BARS = 12` chưa bao giờ được suy ra từ dữ liệu, và
giờ đã có lý do cụ thể để nghi ngờ nó. Phép kiểm quyết định phải là backtest
thật có dừng lỗ, chi phí và định cỡ, chạy qua `evaluate_and_trade()` + SimBroker
theo quy tắc parity bắt buộc (27/07) — vì phép đo trần ở đây **không có dừng
lỗ**, mà giữ 75 nến thay vì 12 sẽ thay đổi hoàn toàn xác suất chạm dừng lỗ.

Script: `scratch/entry_power_run_2026-08-03.py`,
`scratch/entry_power_signif_2026-08-03.py`.

## 48. Việc phải làm rút ra từ Wright ch.4

| #   | việc                                                                                                 | mức ưu tiên                            | căn cứ        |
| --- | ---------------------------------------------------------------------------------------------------- | -------------------------------------- | ------------- |
| 53  | Backtest thật qua SimBroker quét `HOLD_BARS` cho `DonchianH4Breakout` — có dừng lỗ, chi phí, định cỡ | **cao** — phép kiểm quyết định cho §47 | [U] tr. 45-64 |
| 54  | Chạy sức mạnh điểm vào cho **mọi** chiến lược trước khi đặt thời gian giữ, thay vì đặt bằng tay      | cao                                    | [U] tr. 45-64 |
| 55  | Đo chi phí chen lấn trên các tín hiệu của dự án (vàng: 0 nến lỗ đầu — chưa thấy dấu hiệu)            | thấp — đã đo, âm tính                  | [U] tr. 48-49 |

---

# Phần XIII — Halls-Moore, _Successful Algorithmic Trading_ (2015) ch.3

## References bổ sung

| #   | nguồn                                                                 | chương / trang                 | nguyên lý lấy ra                                                                                       |
| --- | --------------------------------------------------------------------- | ------------------------------ | ------------------------------------------------------------------------------------------------------ |
| [Z] | Halls-Moore, M. (2015). _Successful Algorithmic Trading_. QuantStart. | Ch. 3 "Backtesting", tr. 15-19 | bốn loại thiên lệch backtest; ba con đường cụ thể dẫn tới rò rỉ nhìn-trước; mặt phẳng nhạy cảm tham số |

## 67. Ba con đường cụ thể dẫn tới rò rỉ nhìn-trước — [Z] tr. 16-17

Giá trị của mục này là ở chỗ nó **liệt kê cơ chế cụ thể**, không dừng ở cảnh báo
chung. Ba con đường:

**(a) Lỗi kỹ thuật về chỉ số mảng.** "Incorrect offsets of these indices can lead
to a look-ahead bias by incorporating data at N+k for non-zero k."

**(b) Tính tham số trên toàn bộ dữ liệu.** "If the whole data set (including
future data) is used to calculate the regression coefficients, and thus
retroactively applied to a trading strategy for optimisation purposes, then
future data is being incorporated."

Áp thẳng vào dự án: 6 z-feature vĩ mô trong `attach_macro_to_m5` được chuẩn hoá
bằng trung bình và độ lệch chuẩn. **Tính trên cửa sổ nào?** Nếu tính trên toàn
bộ chuỗi thì mỗi điểm z trong quá khứ đã chứa thông tin tương lai. Đây là đúng
cơ chế (b), và nó im lặng — không có ngoại lệ nào được ném ra. `market_memory.py`
đã xử lý đúng việc này bằng phân vị trượt và `as_of`; cần xác nhận `attach_macro`
cũng vậy.

**(c) Dùng giá cao/thấp của chính nến đang chạy.** Đây là con đường tinh vi nhất:

> "since these maximal/minimal values **can only be calculated at the end of a
> time period**, a look-ahead bias is introduced if these values are used during
> the current period. **It is always necessary to lag high/low values by at least
> one period** in any trading strategy making use of them."

Mọi chiến lược Donchian của dự án đều dùng đỉnh/đáy n nến. Module
`research/validation/entry_power.py` đã áp `shift(1)` đúng nguyên tắc này và có
test riêng cho nó (`test_donchian_KHONG_ro_ri_nhin_truoc`). Cần rà các chiến lược
live theo cùng tiêu chuẩn.

## 68. Mặt phẳng nhạy cảm tham số — [Z] tr. 16

> "One method to help mitigate this bias is to perform a **sensitivity
> analysis**... varying the parameters incrementally and plotting a 'surface' of
> performance... **If you have a very jumpy performance surface, it often means
> that a parameter is not reflecting a phenomena and is an artefact of the test
> data.**"

Đây là nguồn thứ ba cho cùng nguyên tắc, mỗi nguồn một cách diễn đạt:

| nguồn                     | cách diễn đạt                                                                                      |
| ------------------------- | -------------------------------------------------------------------------------------------------- |
| K&D ch.22 tr.546          | "determine parameter **SETS** instead of single parameters"                                        |
| Faith ch.12 tr.183        | thước đo không bền làm "slight differences in parameter values cause relatively large differences" |
| **Halls-Moore [Z] tr.16** | **mặt phẳng gồ ghề = tham số không phản ánh hiện tượng thật**                                      |

Ba nguồn độc lập → nâng lên hạng **Verified**. Đây là căn cứ cho tiêu chí "chọn
giữa cao nguyên, không chọn đỉnh nhọn" mà vòng 2 của phép quét thời gian giữ
đang dùng.

## 69. Thiên lệch sống sót — vì sao dự án phần lớn miễn nhiễm — [Z] tr. 17

> "One can also trade on asset classes that are **not prone to survivorship
> bias**, such as certain commodities (and their future derivatives)."

Dự án giao dịch vàng, bạc và các cặp tiền tệ chính — không có mã nào "huỷ niêm
yết". Đây là một trong số ít thiên lệch mà dự án **không** phải lo, và nên ghi rõ
để khỏi tốn công phòng chống thứ không tồn tại.

Một ngoại lệ cần ghi: nếu về sau dùng rổ nhiều cặp FX để xếp hạng (như ý tưởng
Laidi ở §49), thì việc chọn "6 cặp chính đang có dữ liệu" **là** một dạng chọn
lọc sau — các cặp đó là những cặp còn thanh khoản đến hôm nay.

## 70. Việc phải làm

| #   | việc                                                                                | mức ưu tiên | căn cứ        |
| --- | ----------------------------------------------------------------------------------- | ----------- | ------------- |
| 68  | ~~Xác nhận cửa sổ chuẩn hoá của z-feature vĩ mô là trượt~~ — **ĐÃ KIỂM 03/08: ĐẠT** | đóng        | [Z] tr.16 (b) |
| 69  | ~~Rà chiến lược live dùng đỉnh/đáy n nến~~ — **ĐÃ KIỂM 03/08: ĐẠT**                 | đóng        | [Z] tr.17 (c) |
| 70  | Ghi nhận dự án miễn nhiễm thiên lệch sống sót (không giao dịch cổ phiếu)            | thấp        | [Z] tr.17     |

## 71. Hai mục rò rỉ nhìn-trước — đã kiểm, ĐẠT cả hai (03/08)

**(b) Chuẩn hoá z-feature vĩ mô.** `src/python/shared/macro/features.py:324`:

```python
def _causal_z(ret: pd.Series) -> pd.Series:
    mu = ret.rolling(_Z_WINDOW, min_periods=_Z_MIN_PERIODS).mean()
    sd = ret.rolling(_Z_WINDOW, min_periods=_Z_MIN_PERIODS).std()
    return (ret - mu) / (sd + 1e-12)
```

Dùng `rolling`, không phải `expanding` hay toàn chuỗi. Hàm còn được đặt tên
`_causal_z` và docstring của `load_macro_momentum_frame` ghi rõ điều kiện nhân
quả. **ĐẠT.**

**(c) Đỉnh/đáy phải trễ ít nhất một nến.** Ba chiến lược dùng biên Donchian:

| tệp            | dòng | cách cắt                                       |
| -------------- | ---- | ---------------------------------------------- |
| `don_h4.py`    | 121  | `df["high"].iloc[-(DON_N+1):-1].max()`         |
| `swing_don.py` | 159  | `d1["high"].iloc[-(cfg["don_in"]+1):-1].max()` |
| `swing_don.py` | 353  | `d1["low"].iloc[-21:-1].min()`                 |

Lát cắt `[-(N+1):-1]` **loại nến hiện tại** ở cả ba chỗ. `swing_don.py:159` còn
có comment ghi đúng ý này. **ĐẠT.**

Ghi lại kết quả kiểm dù âm tính, vì lần sau ai đọc [Z] tr.16-17 sẽ đặt đúng câu
hỏi này và không cần kiểm lại từ đầu.
