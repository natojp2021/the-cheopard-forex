# KB — Tâm lý nhận thức: vì sao nghiên cứu tự sinh ra tri thức sai

## References

| # | nguồn | chương / trang | nguyên lý lấy ra |
|---|---|---|---|
| [A] | Aronson, D. (2007). *Evidence-Based Technical Analysis*. Wiley. | Ch. 2 "The Illusory Validity of Subjective Technical Analysis", tr. 35-122 | toàn bộ file này |
| [B] | Kahneman, D., Slovic, P. & Tversky, A. — nghiên cứu heuristic và thiên lệch | dẫn trong [A] tr. 41 | hai nguồn của tri thức ảo |
| [C] | Simon, H. — nguyên lý *bounded rationality* | dẫn trong [A] tr. 42 | giới hạn xử lý thông tin của trí óc |
| [D] | Gilovich, T. *How We Know What Isn't So* | dẫn trong [A] tr. 38-39 | — |
| [E] | Shermer, M. *Why People Believe Weird Things* | dẫn trong [A] tr. 38, 40 | — |
| [F] | Fischhoff và cộng sự — thí nghiệm thiên lệch nhận thức muộn về chuyến đi Trung Quốc của Nixon 1972 | dẫn trong [A] tr. 56 | 67% → 84% theo thời gian |

**Vì sao file này quan trọng nhất trong knowledge base:** chương 2 không nói về
thị trường. Nó nói về *người nghiên cứu thị trường*. Mọi lỗi được mô tả ở đây
đều đã xuất hiện trong nhật ký nghiên cứu của chính dự án này.

---

## 1. Sai số HỆ THỐNG, không phải ngẫu nhiên — và đó là tin tốt

Trích [A] tr. 35:

> "A systematic error, unlike a random error, occurs over and over again in
> similar situations. **This is good news because it means the error is
> predictable and steps can be taken to avoid it.** The first step is realizing
> that such errors are common."

Đây là tiền đề của cả chương: các lỗi dưới đây không phải xui rủi, chúng lặp
lại theo quy luật, nên chống được bằng quy trình.

## 2. Không kiểm định được thì TỆ HƠN CẢ SAI

Trích [A] tr. 35:

> "subjective TA cannot be called wrong, because to call a method wrong implies
> it has been tested and contradicted by objective evidence. Subjective TA is
> immune to empirical challenge because it is untestable. Thus, **it is worse
> than wrong; it is meaningless.**"

Và tr. 36 phân biệt hai kiểu tri thức sai:

> "Whereas subjective TA suffers from a lack of quantitative evidence,
> **objective TA suffers from faulty inferences drawn from quantitative
> evidence.**"

**Áp dụng:** hệ thống này thuộc nhóm thứ hai. Rủi ro của nó không phải thiếu
số liệu — nó có rất nhiều số liệu — mà là suy luận sai từ số liệu ấy. Đó chính
là chương 6 (xem `statistical_validation.md`).

## 3. Chuyên gia KHÔNG phân biệt được biểu đồ thật với biểu đồ ngẫu nhiên

Trích [A] tr. 38:

> "When I learned that the same patterns and trends, to which TA attributes such
> significance, **also appear with regularity in purely random data**, my faith
> in chart analysis was shaken to the core. Moreover, it came to my attention
> that **studies have shown that expert chart readers cannot reliably
> distinguish actual market charts from charts produced by a random process.**"

> "'obvious validity' is an inadequate standard for judging the validity of
> market patterns."

**Áp dụng:** đây là cơ sở lý thuyết cho quy tắc đối chứng ngẫu nhiên đã có trong
dự án (chốt 27/07). Quy tắc ấy trước nay dựa vào kinh nghiệm; giờ nó có nguồn.

## 4. Giới hạn xử lý của trí óc — và hệ quả cho thiết kế hệ thống

Trích [A] tr. 42, dẫn Simon [C]:

> "The capacity of the human mind for formulating and solving complex problems
> is very small compared with size of the problems whose solution is required."

Ba con số cụ thể từ [A] tr. 42-43:

| giới hạn | giá trị |
|---|---|
| số mẩu thông tin giữ trong trí nhớ làm việc | 7 ± 2 |
| số yếu tố xử lý được theo kiểu **cấu hình** (phải xét đồng thời, không tách rời) | **tối đa 3** |
| chuyên gia so với hồi quy tuyến tính hình thức | chuyên gia KÉM hơn, vì không nhất quán |

Trích tr. 43 về điểm cuối:

> "human experts are less effective than linear regression models because they
> **fail to combine the information in the consistent manner** of a formal
> mathematical model."

Aronson tách rõ hai loại bài toán:

* **tuần tự / tuyến tính** — mỗi biến đọc độc lập rồi cộng lại. Đọc biến A không
  phụ thuộc B, C.
* **cấu hình** — thông tin nằm trong *mạng quan hệ giữa các biến*. A cao có
  nghĩa này khi B thấp C cao, và nghĩa hoàn toàn khác khi B cao C thấp.

Với ba biến nhị phân: 8 cấu hình khác nhau, nhưng tổ hợp tuyến tính chỉ tạo ra
4 giá trị phân biệt. Nghĩa là mô hình tuyến tính **không biểu diễn nổi** bài
toán cấu hình.

**Áp dụng — mâu thuẫn với hệ thống hiện tại:**

`shared/regime/states9.py` phân loại bằng ba trục xét đồng thời (hướng × sức
mạnh × biến động) → đúng là bài toán CẤU HÌNH ba yếu tố, tức chạm trần khả năng
của trí óc con người. Ngưỡng của nó do tôi đặt tay. Theo [A] tr. 43, việc đặt
tay ngưỡng cho một bài toán cấu hình ba yếu tố là chỗ con người làm kém nhất, và
mô hình hình thức làm tốt hơn — **không phải vì mô hình thông minh hơn mà vì nó
nhất quán.**

Đây là lập luận có nguồn cho việc thay ngưỡng đặt tay bằng mô hình học được.

## 5. Thiên lệch nhận thức muộn — lỗi nguy hiểm nhất cho nghiên cứu backtest

### Thực nghiệm ([A] tr. 56, [F])

Sinh viên dự đoán kết quả chuyến đi Trung Quốc của Nixon năm 1972. Sau đó được
hỏi lại chính mình đã dự đoán gì:

| thời gian sau sự kiện | tỉ lệ nhớ SAI, tưởng mình đã dự đoán chính xác hơn thực tế |
|---|---:|
| 2 tuần | 67% |
| vài tháng | **84%** |

### Không chống được bằng ý chí ([A] tr. 56)

> "Other experimental evidence shows that strategies aimed specifically at
> reducing the hindsight bias **are not effective.** Even when people are warned
> about hindsight bias and told to avoid it, it still occurs. **It appears to be
> beyond rational control.** Not even professional expertise is helpful."

Thí nghiệm với bác sĩ đánh giá sai sót chẩn đoán của đồng nghiệp, khi đã biết
kết quả giải phẫu bệnh: họ không hiểu nổi vì sao một bác sĩ được đào tạo lại có
thể sai như vậy.

### Cơ chế ([A] tr. 57)

Trí nhớ không lưu theo trình tự thời gian mà **giải cấu trúc sự kiện rồi lưu
theo phạm trù liên tưởng**, khi nhớ lại thì *dựng lại* từ các mảnh. Vì thời điểm
xảy ra không phải đặc trưng lưu trữ, ta không truy được thứ tự — mà thứ tự (ta
biết điều gì vào lúc nào) mới là thứ quyết định khi đánh giá khả năng dự báo.

> "Post-outcome knowledge becomes indistinguishable from pre-outcome knowledge
> and seems as if it were known all along."

### Lối thoát duy nhất ([A] tr. 57-58)

> "**Only objective TA methods offer the opportunity of avoiding hindsight bias**
> because only information known at a given point in time is used to generate
> signals, and signals are evaluated in an objective manner."

Và với dự báo thời gian thực, điều kiện là **dự báo phải KHẢ BÁC BỎ** — tại thời
điểm ra dự báo phải nêu rõ (1) kết quả nào thì coi là sai, hoặc (2) quy trình
đánh giá và thời điểm áp dụng quy trình đó.

Ba ví dụ dự báo khả bác bỏ mà Aronson nêu (tr. 58):

> * "The market will be higher six months from now, and within that timeframe
>   the market will not decline more than 20 percent from current levels"
> * "The market will advance 20 percent from current levels before it declines
>   20 percent from current levels"
> * "A buy signal has been given. Hold long position until a sell signal is given."

**Áp dụng — đây là quy tắc quan trọng nhất rút ra được cho quy trình của chúng ta:**

Mọi giả thuyết chiến lược phải ghi ĐIỀU KIỆN BÁC BỎ *trước khi* chạy backtest,
và ghi vào file, không giữ trong đầu. Dự án đã làm đúng việc này một lần
(`squeeze_breakdown.py` có mục "ĐIỀU KIỆN RÚT LẠI, ghi trước để sau này không
phải tranh luận") và chính nhờ vậy mà phán quyết bác bỏ ngày 03/08 diễn ra gọn,
không tranh cãi.

Ngược lại, lời giải thích "holdout nghèo cơ hội" được nêu SAU khi thấy kết quả
xấu — đúng dạng mà thiên lệch này sinh ra.

## 6. Thiên lệch thông tin gián tiếp: sức mạnh của một câu chuyện hay

Trích [A] tr. 59:

> "good stories are more powerful persuaders than objective facts... Philosopher
> Bertrand Russell said that when we learn things informally
> (nonscientifically), we are impacted by the **'emotional interest of the
> instances, not by their number'**. It is for this very reason that scientists
> train themselves to react in exactly the opposite way, that is to discount
> dramatic stories and pay attention to objective facts, preferably those that
> can be reduced to numbers."

Và tr. 59-60 về sự biến dạng qua mỗi lần kể lại:

> "inconsistencies and ambiguities are minimized while cohesive aspects are
> amplified... **What started out as a result with possible significance may end
> up being reported as a discovery of high significance.**"

Về chuỗi nhân quả (tr. 60):

> "The problem is that cause-effect explanations that are, in fact, fallacious
> **are hard to detect when they are plausible** and appeal to a sense of the
> ironic."

**Áp dụng — hai điều:**

1. Bài blog "Best Trend Trading Strategy for Beginners in 2026" mà bạn gửi hôm
   nay là đúng dạng này: câu chuyện mạch lạc, không số liệu, không mẫu, không
   kiểm định. Việc loại nó khỏi nguồn tri thức là đúng theo tiêu chuẩn của
   chính chương này.
2. Nguy hiểm hơn: **báo cáo của chính tôi cũng chịu sức ép này.** Mỗi lần tôi
   viết một tóm tắt mạch lạc về vì sao một chiến lược hoạt động, tôi đang làm
   phẳng các mâu thuẫn và khuếch đại phần gắn kết. Đối sách: mọi kết luận phải
   kèm con số thô và số lần thử, để người đọc kiểm được thay vì tin câu chuyện.

## 7. Ảo giác kiểm soát ([A] tr. 50)

Năm yếu tố sinh ra cảm giác kiểm soát không có căn cứ:

| yếu tố | biểu hiện trong dự án này |
|---|---|
| hoạt động phân tích dồn dập | phân tích lại dữ liệu, tạo chỉ báo mới, cách diễn giải mới |
| nhiều lựa chọn | chọn thị trường, chọn chỉ báo, chọn chỗ vẽ đường xu hướng |
| quen thuộc do dùng nhiều | phương pháp dùng lâu thành ra "cảm thấy" đáng tin |
| **thành công sớm — do MAY MẮN** | và thiên lệch tự quy kết khiến ta gán cho năng lực |
| cam kết cá nhân | đã bỏ nhiều công vào một hướng thì khó bỏ |

**Áp dụng:** "hoạt động dồn dập" và "nhiều lựa chọn" mô tả đúng một phiên nghiên
cứu 90 phép thử. Bản thân khối lượng công việc tạo ra cảm giác đang tiến bộ, độc
lập với việc có tiến bộ thật hay không.

## 8. Tính dai dẳng của niềm tin ([A] tr. 41)

> "once a belief has been adopted, it can survive the assault of new evidence
> contradicting it or **even a complete discrediting of the original evidence**
> that led to the belief's formation."

**Áp dụng:** đây là lý do phải ghi *phán quyết bác bỏ* thẳng vào docstring của
module, chứ không chỉ vào một file nghiên cứu riêng. `squeeze_breakdown.py` giờ
mở đầu bằng "PHÁN QUYẾT 03/08: BÁC BỎ" — ai đọc module cũng phải đi qua nó.

## 9. Bộ quy tắc rút ra cho quy trình nghiên cứu

Đây là đầu ra thực tế của chương 2 — chuyển từng thiên lệch thành một ràng buộc
quy trình:

| # | quy tắc | chống thiên lệch nào |
|---|---|---|
| 1 | Ghi **điều kiện bác bỏ** vào file TRƯỚC khi chạy backtest | nhận thức muộn (§5) |
| 2 | Mọi lời giải thích cho một thất bại phải được nêu trước khi xem kết quả; nếu không thì không tính | nhận thức muộn + giả thuyết đặc biệt |
| 3 | Mọi kết luận kèm **số liệu thô và số lần thử**, không chỉ câu chuyện | thông tin gián tiếp (§6) |
| 4 | Đối chứng ngẫu nhiên là bắt buộc — "nhìn thấy rõ ràng" không phải bằng chứng | §3 |
| 5 | Ngưỡng cho bài toán ≥ 3 yếu tố xét đồng thời: ưu tiên mô hình hình thức hơn đặt tay | §4 |
| 6 | Phán quyết bác bỏ ghi thẳng vào docstring module | tính dai dẳng của niềm tin (§8) |
| 7 | Khối lượng công việc KHÔNG phải chỉ dấu của tiến bộ | ảo giác kiểm soát (§7) |
