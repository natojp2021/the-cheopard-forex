# KB — Bám xu hướng và momentum

## References

| #   | nguồn                                                                                    | chương / trang                                    | nguyên lý lấy ra                                                                                        |
| --- | ---------------------------------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| [A] | Chan, E.P. (2013). _Algorithmic Trading: Winning Strategies and Their Rationale_. Wiley. | Ch. 6 "Interday Momentum Strategies", tr. 133-154 | bốn nguyên nhân của momentum; phép kiểm tương quan lookback-holding; ưu nhược so với hồi quy trung bình |
| [B] | Chan (2013)                                                                              | Ch. 1, ví dụ 1.1                                  | mô phỏng chuỗi cùng độ nhọn nhưng KHÔNG tự tương quan vẫn tái tạo lợi nhuận trong 12% lần               |
| [C] | Daniel, K. & Moskowitz, T. (2011). "Momentum Crashes"                                    | dẫn trong [A] tr. 151                             | momentum sụp đổ nhiều năm sau khủng hoảng tài chính                                                     |
| [D] | Moskowitz, T., Ooi, Y.H. & Pedersen, L.H. (2012). "Time Series Momentum". _JFE_ 104(2)   | dẫn trong [A] tr. 138                             | mua/bán theo dấu lợi suất 12 tháng, giữ 1 tháng                                                         |
| [E] | Aronson, D. (2007). _Evidence-Based Technical Analysis_.                                 | Ch. 8 tr. 397-398                                 | toán tử phá vỡ kênh giá                                                                                 |

---

## 1. Bốn nguyên nhân của momentum — [A] tr. 133

> "There are four main causes of momentum:
>
> 1. For futures, the persistence of roll returns, especially of their signs.
> 2. **The slow diffusion, analysis, and acceptance of new information.**
> 3. The forced sales or purchases of assets of various type of funds.
> 4. Market manipulation by high-frequency traders."

**Đối chiếu với XAUUSD giao ngay (CFD):**

| nguyên nhân                  | áp dụng cho vàng?                                                                          |
| ---------------------------- | ------------------------------------------------------------------------------------------ |
| 1. lợi suất đảo hạn hợp đồng | **KHÔNG** — CFD giao ngay không có roll                                                    |
| 2. thông tin lan chậm        | **CÓ** — cùng cơ chế phản ứng-dưới-mức mà Aronson mô tả (xem `trading_principles.md` §2.1) |
| 3. mua/bán cưỡng bức của quỹ | **CÓ** — quỹ ETF vàng, ngân hàng trung ương, tái cân bằng danh mục                         |
| 4. thao túng của HFT         | có thể, nhưng không kiểm được bằng dữ liệu đang có                                         |

**Điều này quan trọng:** hai trong bốn nguyên nhân áp dụng được, và cả hai đều
có tài liệu hậu thuẫn. Nhưng nguyên nhân số 1 — thứ Chan gọi là chiếm vị trí
trung tâm cho hợp đồng tương lai — **không áp dụng cho vàng giao ngay**. Nghĩa
là các con số Sharpe của Chan cho hợp đồng tương lai (BR 1,09; HG 1,05; TU 1,04)
**không chuyển sang được** cho vàng CFD.

## 2. Phép kiểm momentum — công cụ nghiên cứu TRƯỚC backtest

Đây là thứ có giá trị thực dụng cao nhất trong chương, vì nó đúng loại công cụ
mà López de Prado đòi hỏi: tính được **trước** khi mô phỏng hiệu suất.

> "Time series momentum of a price series means that past returns are positively
> correlated with future returns. It follows that we can just calculate the
> correlation coefficient of the returns together with its p-value... **We should
> find the optimal pair of past and future periods that gives the highest
> positive correlation and use that as our look-back and holding period.**"

Chan quét lưới `lookback × holddays` ∈ `{1, 5, 10, 25, 60, 120, 250}`.

### Ràng buộc bắt buộc: KHÔNG được dùng dữ liệu chồng lấn — [A] tr. 135

> "In computing the correlations of pairs of returns resulting from different
> look-back and holding periods, **we must take care not to use overlapping
> data.** If look-back is greater than the holding period, we have to shift
> forward by the holding period to generate a new returns pair. If the holding
> period is greater than the look-back, we have to shift forward by the
> look-back period."

Tức bước nhảy giữa hai cặp quan sát độc lập là `max(lookback, holddays)`.

Đây cùng một vấn đề mà López de Prado gọi là **nhãn chồng lấn** (xem
`machine_learning.md` §3) — hai tài liệu độc lập chỉ ra cùng một cái bẫy.

### Hurst và Variance Ratio KHÔNG thay thế được — [A] tr. 136

Với TU: các phép kiểm tương quan cho thấy momentum rõ, nhưng **số mũ Hurst
= 0,44** (tức hồi quy trung bình) và **Variance Ratio không bác bỏ được bước đi
ngẫu nhiên**.

> "this time series (as with many other financial time series) **exhibits
> momentum and mean reversion at different time frames.** The Variance Ratio test
> is unable to test the specific time frames where the correlations might be
> stronger than average."

**Áp dụng:** một phép kiểm tổng quát cho kết quả "ngẫu nhiên" KHÔNG loại trừ khả
năng có momentum ở một khung thời gian cụ thể. Ngược lại cũng vậy.

### Việc phải làm rút ra

Dự án chọn tham số `DonchianH4Breakout` bằng cách **quét backtest** — đúng thứ
López de Prado cấm. Chan cho một cách thay thế hợp lệ: quét **lưới tương quan
lookback-holding trên dữ liệu không chồng lấn**, chọn cặp có tương quan cao và
p nhỏ, rồi mới backtest MỘT lần để loại bỏ.

Đây là con đường cụ thể để thoát khỏi vòng lặp "backtest làm công cụ tìm kiếm".

## 3. Ba nhược điểm của momentum — [A] tr. 151-153

### 3.1 Ít tín hiệu độc lập → Sharpe thấp, và tăng tần suất KHÔNG chữa được

> "many established momentum strategies have long look-back and holding periods.
> So clearly the number of independent trading signals is few and far in between.
> **(We may rebalance a momentum portfolio every day, but that doesn't make the
> trading signals more independent.)** Fewer trading signals naturally lead to
> lower Sharpe ratio."

**Đây là cảnh báo trực tiếp với công việc tăng tần suất ngày 03/08.** Tôi hạ
`DONCHIAN_N` từ 200 xuống 34 và số lệnh tăng từ 5,2 lên 37,4 mỗi năm, rồi kết
luận thông lượng tăng gấp bảy. Chan chỉ ra câu hỏi đúng phải là: **37,4 lệnh đó
có ĐỘC LẬP không, hay là cùng một tín hiệu bị chia nhỏ?**

Công thức `θ ∝ √n` trong AFML ch.15 (xem `risk_management.md` §2) chỉ đúng khi
`n` là số lệnh **độc lập cùng phân phối**. Nếu các lệnh chồng lấn thông tin thì
`√n` là ước lượng quá lạc quan.

→ Cần đo **độ duy nhất trung bình** của nhãn (AFML ch.4) hoặc tương quan chuỗi
giữa các lệnh liên tiếp trước khi tin vào con số tăng tần suất.

### 3.2 Sụp đổ momentum sau khủng hoảng — [C] dẫn trong [A] tr. 151

> "research by Daniel and Moskowitz on 'momentum crashes' indicates that
> **momentum strategies for futures or stocks tend to perform miserably for
> several years after a financial crisis**... After the stock market crash of
> 1929, a representative momentum strategy **did not return to its high watermark
> for more than 30 years!** The cause of this crash is mainly due to the strong
> rebound of short positions following a market crisis."

Chỉ số S&P DTI khi Chan viết: drawdown **−25,9%** kể từ 05/12/2008.

**Áp dụng:** danh mục hiện tại toàn bám xu hướng. Đây là rủi ro có tên gọi, có
tài liệu, và **chưa được đưa vào bất kỳ kịch bản stress nào** của dự án. Monte
Carlo hiện có bootstrap từ lịch sử đã quan sát; nó không mô phỏng được một chế
độ nhiều năm mà momentum ngừng hoạt động.

Lưu ý cơ chế: nguyên nhân là _cú bật của các vị thế bán sau khủng hoảng_. Danh
mục chỉ-mua của dự án chịu tác động theo cách khác — nó không bị kẹt vị thế bán,
nhưng cũng không hưởng lợi từ cú bật.

### 3.3 Momentum ngắn dần khi nhiều người biết — [A] tr. 153

> "the duration over which momentum remains in force gets progressively shorter
> as more traders catch on to it. For example, price momentum driven by earnings
> announcements used to last several days. **Now it lasts barely until the market
> closes.**... we may have to constantly shorten our holding period, yet **there
> is no predictable schedule for doing so.**"

**Áp dụng:** đây là lập luận có nguồn ủng hộ việc rút ngắn hạn giữ — nhưng cũng
là cảnh báo rằng không có lịch trình dự đoán được. Tức tham số hạn giữ cần được
**theo dõi trôi dạt**, không đặt một lần rồi thôi.

## 4. Ba ưu điểm — trong đó một điểm biện minh cho thiết kế hiện tại

### 4.1 Cắt lỗ NHẤT QUÁN với momentum, MÂU THUẪN với hồi quy trung bình — [A] tr. 153

> "Stop losses are perfectly consistent with momentum strategies. If momentum has
> changed direction, we should enter into the opposite position. Since the
> original position would have been losing, and now we have exited it, this new
> entry signal effectively served as a stop loss. **In contrast, stop losses are
> not consistent with mean-reverting strategies, because they contradict mean
> reversion strategies' entry signals.**"

**Áp dụng:** mọi chiến lược trong danh mục đều bám xu hướng và đều có SL theo
ATR. Theo [A] đó là kết hợp nhất quán về mặt logic. Nhưng nó cũng cảnh báo cho
`MeanRevDip` (hiện BACKTEST_ONLY): chiến lược hồi quy trung bình có SL là mâu
thuẫn nội tại — SL cắt đúng lúc tín hiệu vào lệnh mạnh nhất.

### 4.2 Lỗ có giới hạn, lãi không giới hạn — [A] tr. 153

> "For mean-reverting strategies, their upside is limited by their natural profit
> cap (set as the 'mean' to which the prices revert), but their downside can be
> unlimited. For momentum strategies, their upside is unlimited (unless one
> arbitrarily imposes a profit cap, **which is ill-advised**), while their
> downside is limited."

> "The more often 'black swan' events occur, the more likely that a momentum
> strategy will benefit from them. **The thicker the tails of the returns
> distribution curve, or the higher its kurtosis, the better that market is for
> momentum strategies.**"

**Mâu thuẫn với hệ thống:** Chan gọi việc áp trần lợi nhuận cho chiến lược
momentum là _"ill-advised"_. `PaPullbackH4` có hard TP 2R. `DonchianH4Breakout`
và `SwingDon` thì không — đúng khuyến nghị.

Đáng chú ý hơn: bảng ở `risk_management.md` §3 cho thấy `SwingDon` (không TP,
payout +1,88R) và `DonchianH4Breakout` (không TP, +2,04R) có biên an toàn cao
nhất; hai chiến lược CÓ trần lợi nhuận (`PaDonchianH4` +1,41R, `PaPullbackH4`
+1,43R) có biên thấp nhất. **Số liệu của dự án khớp với khuyến nghị của Chan.**

### 4.3 Đa dạng hoá — không áp dụng ở đây

Chan nêu ưu điểm cuối là momentum cho phép đa dạng hoá qua nhiều lớp tài sản.
Không áp dụng: hệ thống chỉ giao dịch XAUUSD.

## 5. Cảnh báo mạnh nhất — 12% chuỗi ngẫu nhiên tái tạo được lợi nhuận

[A] tr. 154 dẫn lại ví dụ 1.1 của chính cuốn sách:

> "We simulated a returns series with the same kurtosis as the futures series for
> TU but **with no serial autocorrelations.** We found that it can still generate
> the same returns as our TU momentum strategy in **12 percent of the random
> realizations!**"

Nghĩa là: một chiến lược momentum có Sharpe 1,04 trên TU vẫn có **12% khả năng**
được tái tạo bởi một chuỗi hoàn toàn không có tự tương quan, chỉ cần chuỗi đó có
cùng độ nhọn.

Đây là lập luận độc lập thứ ba — sau Aronson (biểu đồ ngẫu nhiên trông như thật)
và López de Prado (vé số thắng) — cho cùng một kết luận: **đối chứng ngẫu nhiên
là bắt buộc, và ngưỡng ý nghĩa phải tính trên phân phối của đối chứng ấy.**

Con số 12% cũng cho một mốc cụ thể: p-value của một chiến lược momentum tốt trên
hợp đồng tương lai, so với chuỗi ngẫu nhiên cùng độ nhọn, vào khoảng 0,12 — tức
**không đạt mức ý nghĩa 0,05**.

## 6. Việc phải làm

| #   | việc                                                                                                                                            | mức ưu tiên | căn cứ                    |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | ------------------------- |
| 1   | Đo **độ độc lập** của tín hiệu trước khi tin vào con số tăng tần suất — 37,4 lệnh/năm có thể không phải 37,4 tín hiệu độc lập                   | cao         | [A] tr. 151               |
| 2   | Thay việc quét backtest chọn tham số bằng **lưới tương quan lookback-holding trên dữ liệu không chồng lấn**                                     | cao         | [A] tr. 135-137           |
| 3   | Thêm kịch bản stress **"momentum ngừng hoạt động nhiều năm"** — chưa có trong MC hiện tại                                                       | cao         | [C] dẫn trong [A] tr. 151 |
| 4   | Theo dõi **trôi dạt hạn giữ tối ưu** theo thời gian, không đặt một lần                                                                          | trung bình  | [A] tr. 153               |
| 5   | Xem lại hard TP 2R của `PaPullbackH4` — Chan gọi trần lợi nhuận cho momentum là "ill-advised", và số liệu biên an toàn của dự án khớp với ý này | trung bình  | [A] tr. 153               |
| 6   | Nếu đưa `MeanRevDip` trở lại LIVE: SL mâu thuẫn nội tại với hồi quy trung bình, cần thiết kế thoát lệnh khác                                    | trung bình  | [A] tr. 153               |

---

# Phần II — Antonacci, _Dual Momentum Investing_ (2015)

## References bổ sung

| #   | nguồn                                                                                                                    | chương / trang                                                                                    | nguyên lý lấy ra                                                                                               |
| --- | ------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| [F] | Antonacci, G. (2015). _Dual Momentum Investing: An Innovative Strategy for Higher Returns with Lower Risk_. McGraw-Hill. | Phụ lục B "Absolute Momentum: A Simple Rule-Based Strategy and Universal Trend-Following Overlay" | momentum tuyệt đối 12 tháng áp cho 8 lớp tài sản **gồm VÀNG**, 1974-2012                                       |
| [G] | Antonacci (2015)                                                                                                         | Ch. 5 "Asset Selection: The Good, the Bad, and the Ugly"                                          | hàng hoá là trò chơi tổng bằng không; lợi suất đảo hạn đã đảo dấu                                              |
| [H] | Erb, C. & Harvey, C. (2006)                                                                                              | dẫn trong [G]                                                                                     | _"The average excess returns of individual commodity futures contracts have been indistinguishable from zero"_ |
| [I] | Jegadeesh, N. & Titman, S. (1993)                                                                                        | dẫn trong [F]                                                                                     | kỳ hình thành tốt nhất 3-12 tháng, tụ ở 12                                                                     |

---

## 26. Momentum TUYỆT ĐỐI — và vì sao nó KHÁC với thứ tôi đã đo

### Định nghĩa chính xác — [F] phụ lục B

> "our strategy simply defines absolute momentum as being positive when the
> **excess return (asset return less the Treasury bill return) over the formation
> (look-back) period is positive.** We hold a long position in our selected
> assets during these times. When absolute momentum turns negative... our
> baseline strategy is to **exit the asset and switch into 90-day U.S. Treasury
> bills** until absolute momentum again becomes positive."

Tái cân bằng **hàng tháng**. Chi phí giao dịch trừ 20 điểm cơ bản mỗi lần chuyển.
Số lần chuyển mỗi năm rất thấp: từ 0,33 (REIT) tới 1,08 (trái phiếu lợi suất cao).

### Kết quả trên tám lớp tài sản, GỒM VÀNG, 1974-2012

> "**Every asset has a higher Sharpe ratio, lower maximum drawdown, and higher
> percentage of profitable months with 12-month absolute momentum over this
> 38-year period.**"

Tám tài sản gồm MSCI US, MSCI EAFE, trái phiếu kho bạc Mỹ, trái phiếu tín dụng,
trái phiếu lợi suất cao, REIT, S&P GSCI, và **vàng London** (giá chốt buổi chiều
London, hình B.12).

### Kỳ hình thành: 12 tháng, xác nhận qua từng thập kỷ — [F] phụ lục B

Quét kỳ hình thành từ 2 tới 18 tháng, kết quả tốt nhất **tụ ở 12 tháng**. Tác giả
kiểm chéo bằng cách chia mẫu theo từng thập kỷ 1974-2012 và đếm số lần mỗi kỳ đạt
Sharpe cao nhất — vẫn tụ ở 12.

> "Both our aggregated and segmented results coincide with the best formation
> periods of relative momentum, which extend from 3 to 12 months and cluster at
> 12 months (Jegadeesh and Titman 1993)... Given its dominance here and
> throughout the literature, we also use a 12-month formation period as our
> benchmark strategy. **This should minimize transaction costs and the risk of
> data snooping.**"

Đoạn cuối đáng chú ý về phương pháp: chọn 12 tháng **vì tài liệu đã dùng nó rộng
rãi**, chứ không vì nó thắng trong phép quét của chính tác giả — đó là cách chống
dò dẫm dữ liệu.

## 27. SỬA PHẠM VI KẾT LUẬN CỦA TÔI — hai phép đo khác nhau

Ngày 03/08 tôi chạy lưới tương quan của Chan trên XAUUSD và kết luận:

> "vàng KHÔNG có momentum theo lợi suất ở các khung đã thử"

Kết luận ấy **vẫn đúng như đã phát biểu**, nhưng phải nói rõ nó KHÔNG bao hàm
điều gì về momentum tuyệt đối. Hai phép đo hỏi hai câu khác nhau:

|                                  | phép đo của tôi (Chan ch.6)                                                 | phép đo của Antonacci (phụ lục B)                                       |
| -------------------------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| câu hỏi                          | lợi suất quá khứ có **tương quan tuyến tính** với lợi suất tương lai không? | lọc theo dấu lợi suất vượt trội 12 tháng có **cải thiện Sharpe** không? |
| bản chất                         | vô điều kiện, đối xứng                                                      | có điều kiện, **bất đối xứng** — chỉ mua khi dương, ra tiền mặt khi âm  |
| cơ chế có thể sinh kết quả dương | khả năng dự báo lợi suất                                                    | **né giai đoạn biến động cao**, giảm sụt vốn                            |
| mẫu                              | XAUUSD 2003-2026, H4 và D1                                                  | vàng London 1974-2012, tháng                                            |

Một bộ lọc xu hướng có thể nâng Sharpe **thuần tuý bằng cách tránh giai đoạn
xấu** — giảm mẫu số — mà không cần dự báo được lợi suất. Đó chính là điều
Antonacci đo: Sharpe cao hơn, sụt vốn thấp hơn, tỉ lệ tháng có lãi cao hơn.

**Hệ quả: hai kết quả tương thích, không mâu thuẫn.** Nhưng tôi phải sửa cách
diễn giải: từ kết quả lưới tương quan KHÔNG được suy ra rằng "bộ lọc xu hướng 12
tháng vô ích với vàng". Bằng chứng 38 năm của Antonacci nói ngược lại.

## 28. Hàng hoá không có lợi suất kỳ vọng dương — [G] và [H]

> "Commodity futures contracts are a **zero sum game** in which the profits and
> losses of contract buyers and sellers are equal, disregarding transaction
> costs. According to Erb and Harvey (2006), '**The average excess returns of
> individual commodity futures contracts have been indistinguishable from
> zero.**'"

> "There is no expectation of aggregate positive returns... Because gains and
> losses are symmetrical to the buyer and seller of a futures contract, one
> cannot say that the buyer, by taking on volatility, is entitled to a positive
> return."

Lợi suất đảo hạn hợp đồng đã **đảo dấu**:

| giai đoạn | lợi suất đảo hạn trung bình/năm |
| --------- | ------------------------------: |
| 1969-1992 |                        **+11%** |
| từ 2001   |                       **−6,6%** |

Cộng thêm chi phí bị chạy trước 3,6%/năm (Mou 2011) và 3-4%/năm theo J.P. Morgan.

### Áp dụng cho XAUUSD giao ngay — phân biệt cẩn thận

Hệ thống giao dịch **CFD vàng giao ngay**, không phải hợp đồng tương lai. Nên:

- lợi suất đảo hạn **không áp dụng** — không có hợp đồng để đảo;
- chi phí bị chạy trước khi đảo hạn **không áp dụng**;
- nhưng lập luận cốt lõi **CÓ áp dụng**: vàng không sinh dòng tiền, nên **không
  có lợi suất vượt trội kỳ vọng** theo cách cổ phiếu và trái phiếu có.

Đây là cơ sở lý thuyết cho một điều dự án đã quan sát thực nghiệm: **không có
drift để dựa vào**. Việc vàng tăng khoảng 11 lần trong 2003-2026 là hiện tượng
của một giai đoạn cụ thể, không phải phần thưởng rủi ro có cấu trúc.

Điều này củng cố hai việc: (1) khử xu hướng khi đo lợi suất luật là **bắt buộc**,
không phải tuỳ chọn; (2) mọi kết luận dựa trên giai đoạn 2003-2026 phải được coi
là đặc thù giai đoạn cho tới khi kiểm được trên mẫu khác.

## 29. Tương quan tăng khi khủng hoảng — [G]

|                                                      | trước                        | sau         |
| ---------------------------------------------------- | ---------------------------- | ----------- |
| tương quan nội bộ giữa các hàng hoá                  | < 0,10 (thập niên 1990-2000) | 0,50 (2009) |
| GSCI với S&P 500                                     | −0,20 tới 0,10 (trước 2008)  | > 0,50      |
| cổ phiếu với hàng hoá trong khủng hoảng 1929 và 2008 |                              | **> 80%**   |

> "Commodities diversification was lacking **when it was needed the most.**"

**[suy luận của ta]** — với hệ thống một symbol thì đa dạng hoá liên thị trường
không áp dụng. Nhưng con số này cảnh báo một điều khác: nếu sau này thêm bạc hay
FX vào để đa dạng hoá, đừng trông đợi tương quan thấp giữ nguyên trong khủng
hoảng.

## 30. Ứng viên có bằng chứng mạnh nhất tìm được cho tới nay

Gộp ba nguồn độc lập:

| nguồn                            | phát hiện                                                                                                                  |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Antonacci [F] phụ lục B          | momentum tuyệt đối 12 tháng nâng Sharpe, giảm sụt vốn, tăng tỉ lệ tháng lãi cho **cả tám** lớp tài sản gồm vàng, 1974-2012 |
| Moskowitz, Ooi & Pedersen (2012) | TSMOM 12 tháng trên 58 công cụ gồm vàng, 1965-2009                                                                         |
| Jegadeesh & Titman (1993)        | kỳ hình thành tốt nhất tụ ở 12 tháng                                                                                       |

Ba nghiên cứu độc lập, ba mẫu khác nhau, cùng một tham số: **12 tháng**.

Nhưng phải đối chiếu với phép đo của chính dự án ngày 03/08: TSMOM 12 tháng trên
XAUUSD 2003-2026 cho **chân bán** Sharpe −0,19 (xem
`downtrend-evidence-2026-08-03.md`). Chân MUA thì chưa đo riêng bằng phép của
Antonacci.

→ **Việc phải làm:** đo momentum tuyệt đối 12 tháng đúng đặc tả Antonacci trên
XAUUSD — dấu lợi suất vượt trội 12 tháng, tái cân bằng tháng, so Sharpe và sụt
vốn có/không bộ lọc. Đây là phép đo có **ba nguồn công bố hậu thuẫn** và chưa
từng chạy đúng cách trong dự án.

Lưu ý ràng buộc: "chuyển sang tín phiếu kho bạc" không áp dụng — với FTMO thì
trạng thái tương ứng là **đứng ngoài**. Điều này làm giảm lợi ích so với bản của
Antonacci, vì ta mất phần lợi suất tín phiếu.

## 31. Việc phải làm rút ra từ Antonacci

| #   | việc                                                                                                                                                | mức ưu tiên                          | căn cứ        |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ | ------------- |
| 21  | Đo momentum tuyệt đối 12 tháng trên XAUUSD đúng đặc tả phụ lục B; nếu đạt thì cân nhắc làm **lớp phủ** cho cả danh mục thay vì một chiến lược riêng | **cao** — ba nguồn công bố hậu thuẫn | [F] phụ lục B |
| 22  | Sửa cách diễn giải kết quả lưới tương quan: không suy từ "không có tương quan lợi suất" ra "bộ lọc xu hướng vô ích"                                 | **cao** — đã sửa trong tài liệu này  | §27           |
| 23  | Ghi nhận vàng KHÔNG có lợi suất vượt trội kỳ vọng có cấu trúc → khử xu hướng là bắt buộc khi đo                                                     | cao                                  | [G], [H]      |
| 24  | Nếu sau này thêm tài sản để đa dạng hoá: đừng giả định tương quan thấp giữ nguyên trong khủng hoảng                                                 | thấp                                 | [G]           |

---

# Phần V — Faith, _Way of the Turtle_ (2007)

## References bổ sung

| #   | nguồn                                                                                                                      | chương / trang                        | nguyên lý lấy ra                                                         |
| --- | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------ |
| [Q] | Faith, C. (2007). _Way of the Turtle: The Secret Methods that Turned Ordinary People into Legendary Traders_. McGraw-Hill. | Ch. 3 tr. 38-40                       | luật gốc của hệ Turtle: System 1 và System 2, dừng lỗ 2N, định cỡ theo N |
| [R] | Faith (2007)                                                                                                               | Ch. 12 "On Solid Ground", tr. 182-190 | các thước đo hiệu suất thông dụng KHÔNG bền; RAR%; R-cubed               |

Đây là **sách luật gốc** của cơ chế Donchian mà danh mục đang chạy — Faith là
một trong các Turtle nguyên bản của Richard Dennis và Bill Eckhardt.

---

## 35. Luật gốc của hệ Turtle — [Q] tr. 38-39

> "The specific method we used was known as the breakout, sometimes referred to
> as **Donchian channels** after Richard Donchian... The basic idea was to buy if
> a market exceeded the highest price for a particular number of preceding days."

|                               | System 1                            | System 2              |
| ----------------------------- | ----------------------------------- | --------------------- |
| cửa sổ phá vỡ                 | **20 ngày** (4 tuần)                | **60 ngày** (12 tuần) |
| dừng lỗ                       | tối đa **2N** (hai ATR) từ điểm vào | như trên              |
| định cỡ                       | theo **N** (average true range)     | như trên              |
| số đơn vị tối đa mỗi hàng hoá | 4                                   | 4                     |

> "The first was a stop loss exit that was a maximum of **2N, or two average true
> ranges away from the entry point.** This also happened to represent **2 percent
> of our account** because the way we determined the number of contracts to trade
> per market also was based on N."

### Đối chiếu với danh mục hiện tại

|                      | cửa sổ               | dừng lỗ | so với Turtle                              |
| -------------------- | -------------------- | ------- | ------------------------------------------ |
| Turtle System 1      | 20 ngày              | 2N      | —                                          |
| Turtle System 2      | 60 ngày              | 2N      | —                                          |
| `SwingDon`           | 55/20 ngày D1        | 2,5×ATR | **rất gần System 2**, dừng lỗ rộng hơn 25% |
| `DonchianH4Breakout` | 200 nến H4 ≈ 33 ngày | 1,5×ATR | giữa hai hệ, dừng lỗ **hẹp hơn 25%**       |

Cả hai chiến lược nằm trong họ Turtle, nhưng **không cái nào dùng đúng 2N**.
Dừng lỗ hẹp hơn của `DonchianH4Breakout` là một sai lệch chưa từng được đối
chiếu với nguồn gốc — ghi nhận, chưa kết luận đúng sai.

### Bốn bài học của lớp Turtle — [Q] tr. 39

1. **Giao dịch với một lợi thế** — chiến lược phải có kỳ vọng dương dài hạn
2. **Quản lý rủi ro** — sống được thì mới hưởng được kỳ vọng dương
3. **Nhất quán** — thực thi đúng kế hoạch
4. **Giữ đơn giản**

Bài học 4 kèm một câu quan trọng:

> "The core of our approach was simple: **catch every trend. Two or three trades
> might account for all your profits, so don't miss a trend or you might kill
> your whole year.**"

**Đây là lập luận có nguồn ủng hộ quyết định dùng lệnh thị trường của người
dùng.** Lệnh giới hạn chờ giá hồi về; nếu cú phá vỡ không quay lại thì mất lệnh.
Với hệ mà "hai hoặc ba lệnh chiếm toàn bộ lợi nhuận cả năm", bỏ lỡ một cú là mất
cả năm. Katz & McCormick ch.5 tr.107 đo thấy lệnh giới hạn tốt hơn trên hàng hoá
tương lai thập niên 1990; Faith — người thực sự giao dịch hệ này — nhấn mạnh
chiều rủi ro ngược lại. Hai nguồn, hai kết luận khác nhau; quyết định của người
dùng đứng về phía Faith.

---

# Phần X — Antonacci, _Dual Momentum Investing_ (2015), Phụ lục B

## References bổ sung

| #   | nguồn                                                         | chương / trang                           | nguyên lý lấy ra                                                 |
| --- | ------------------------------------------------------------- | ---------------------------------------- | ---------------------------------------------------------------- |
| [X] | Antonacci, G. (2015). _Dual Momentum Investing_. McGraw-Hill. | Ch. 7 tr. 100-105; Phụ lục B tr. 148-158 | động lượng tuyệt đối 12 tháng làm lớp phủ theo xu hướng phổ quát |

## 57. Định nghĩa và bằng chứng — [X] ch.7, PL B

> "In absolute momentum, we look at an asset's **excess return** (its return less
> the return on Treasury bills) over a given look-back period. If the excess
> return is above zero, then the asset has positive absolute momentum."

Chọn cửa sổ 12 tháng có căn cứ mạnh hơn một lần tối ưu ([X] tr.149):

> "Best results cluster at 12 months. **As a check on this, we segment our data
> into subsamples and find the highest Sharpe ratios for each asset in every
> decade from 1974 through 2012.**"

Và nó trùng với khoảng tốt nhất của relative momentum trong Jegadeesh & Titman
(1993) — hai dòng nghiên cứu độc lập hội tụ vào cùng một cửa sổ.

Kết quả trên 8 tài sản, 1974-2012, **trong đó có London Gold** (Hình B.12):

> "**Every asset** has a higher Sharpe ratio, lower maximum drawdown, and higher
> percentage of profitable months with 12-month absolute momentum over this
> 38-year period."

Một điểm nữa đáng lấy ([X] tr.153): tương quan trung bình giữa 8 tài sản là 0,22
khi không có lớp phủ và 0,21 khi có — **lớp phủ không làm tăng tương quan**. Điều
này quan trọng với danh mục nhiều chiến lược: một bộ lọc trạng thái chung dễ làm
mọi chiến lược bật/tắt cùng lúc, và dữ liệu của Antonacci nói điều đó không xảy ra.

## 58. Đo trên dữ liệu dự án: KHÔNG có căn cứ để đổi cổng SMA200

Dự án dùng cổng SMA200. Absolute momentum 12 tháng cùng họ nhưng khác công thức:

    SMA200            : giá > trung bình 200 phiên
    absolute momentum : giá hôm nay > giá 252 phiên trước

Đo bằng **thước bền** của Faith ch.12 (RAR%, R³), không dùng CAGR/MAR:

**XAUUSD** (3.589 phiên, 2015-01 → 2026-07)

| cấu hình         | RAR% |        R³ | Sharpe | DD tối đa | trong thị trường |
| ---------------- | ---: | --------: | -----: | --------: | ---------------: |
| mua-và-giữ       | 8,82 |     0,308 |  0,589 |     27,7% |             100% |
| cổng SMA200      | 6,10 | **0,264** |  0,605 |     20,1% |            66,5% |
| abs.mom 12 tháng | 6,46 | **0,258** |  0,519 |     27,7% |            67,9% |
| abs.mom 6 tháng  | 6,55 |     0,331 |  0,641 |     20,1% |            67,8% |

**XAGUSD** (3.303 phiên)

| cấu hình         | RAR% |        R³ | Sharpe | DD tối đa | trong thị trường |
| ---------------- | ---: | --------: | -----: | --------: | ---------------: |
| mua-và-giữ       | 9,27 |     0,165 |  0,310 |     52,8% |             100% |
| cổng SMA200      | 2,92 | **0,061** |  0,205 |     43,0% |            53,8% |
| abs.mom 12 tháng | 5,81 | **0,130** |  0,254 |     52,8% |            54,7% |
| abs.mom 6 tháng  | 3,29 |     0,082 |  0,274 |     43,0% |            53,3% |

**Phán quyết: KHÔNG ĐẠT tiêu chí đăng ký trước.** Yêu cầu là abs.mom 12 tháng
phải hơn SMA200 về R³ trên **cả hai** thị trường; nó thua trên vàng (0,258 so
với 0,264) dù thắng rõ trên bạc (0,130 so với 0,061). Không đổi cổng.

Cấu hình 6 tháng trông tốt nhất trên vàng (R³ 0,331) nhưng kém trên bạc — chọn
nó sẽ là chọn người thắng trong 4 cấu hình × 2 thị trường, đúng thứ Aronson ch.6
cảnh báo.

### Vì sao phép kiểm này YẾU, và điều đó có ý nghĩa

Đây là điểm quan trọng hơn cả kết quả. Lớp phủ động lượng tuyệt đối tồn tại để
**tránh thị trường gấu**. Cửa sổ 2015-2026 của dự án gần như không có thị trường
gấu của vàng — vàng tăng ở cả năm đồng tiền (xem §39). Bằng chứng của Antonacci
trải 1974-2012, **bao gồm cả 20 năm gấu của vàng sau 1980**.

Nói cách khác: phép kiểm này không đủ sức phát hiện lợi ích chính của lớp phủ,
vì mẫu thiếu đúng trạng thái mà lớp phủ bảo vệ. Đây chính xác là điều Faith ch.12
tr.182 gọi là "like polling at the Democratic convention", và K&D ch.22 tr.547
đòi mẫu phải gồm cả bò lẫn gấu.

Kết luận đúng phải phát biểu là: **"không có căn cứ để đổi"**, không phải
**"lớp phủ vô dụng"**. Hai câu đó khác nhau, và ghi nhầm câu thứ hai sẽ khiến
lần sau không ai xem lại khi có dữ liệu dài hơn.

Việc cần làm về sau: dựng lại phép kiểm này trên dữ liệu vàng từ 1974 (ngoài kho
dữ liệu hiện có) trước khi kết luận dứt điểm.

Script: `scratch/absolute_momentum_overlay_2026-08-03.py`.

## 59. Việc phải làm rút ra từ Antonacci

| #   | việc                                                                                                                                                        | mức ưu tiên | căn cứ                       |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | ---------------------------- |
| 62  | Kiếm dữ liệu vàng dài hơn (1974+) để kiểm lại lớp phủ trên mẫu CÓ thị trường gấu                                                                            | trung bình  | [X] PL B; Faith ch.12 tr.182 |
| 63  | Ghi nhận: lớp phủ động lượng **không làm tăng tương quan** giữa các tài sản (0,22 → 0,21) — hữu ích khi lo bộ lọc chung làm mọi chiến lược bật/tắt cùng lúc | thấp        | [X] tr. 153                  |
