# KB-02 — Kiểm định thống kê và sai lệch khai thác dữ liệu

## References

| #   | nguồn                                                                                                                    | chương / trang                                                         | nguyên lý lấy ra                                                                  |
| --- | ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| [A] | Aronson, D. (2007). _Evidence-Based Technical Analysis_. Wiley.                                                          | Ch. 6 "Data-Mining Bias: The Fool's Gold of Objective TA", tr. 257-332 | hai vai trò của con số backtest; năm yếu tố; WRC; MCP; co ngót                    |
| [B] | White, H. (2000). "A Reality Check for Data Snooping". _Econometrica_ 68(5), 1097-1126                                   | —                                                                      | bootstrap cho thống kê cực đại; chứng minh luật thắng là luật đáng chọn khi n → ∞ |
| [C] | Hansen, P.R. (2005). "A Test for Superior Predictive Ability". _JBES_ 23(4), 365-380                                     | —                                                                      | WRC mất lực kiểm định khi vũ trụ chứa luật tệ                                     |
| [D] | Romano, J.P. & Wolf, M. (2005). "Stepwise Multiple Testing as Formalized Data Snooping". _Econometrica_ 73(4), 1237-1282 | —                                                                      | bản từng bước                                                                     |
| [E] | Markowitz, H. & Xu, G. (1994). "Data Mining Corrections". _JPM_ 21(1), 60-69                                             | —                                                                      | công thức co ngót                                                                 |
| [F] | Leinweber, D. — ví dụ bơ Bangladesh                                                                                      | dẫn trong [A] tr. 260-261                                              | tương quan 0,70 giữa sản lượng bơ Bangladesh và S&P 500                           |

Đã cài đặt: `src/python/research/validation/reality_check.py` (14 test).

---

## 1. Hai vai trò của con số backtest — và chỉ một vai trò hợp lệ mỗi lúc

Trích [A] tr. 270-271:

> "In single-rule back testing, observed performance serves as an **estimator**
> of future performance. In data mining, observed performance serves as a
> **selection criterion**. Problems arise for the data miner when observed
> performance is asked to play both roles."

> "The data miner's mistake is using the best rule's back-tested performance to
> estimate its expected performance. This is not a legitimate use... because the
> back-tested performance of the best-performing rule is positively biased."

Lý do toán học ([A] tr. 275): người quét không quan sát _một trung bình mẫu_ mà
quan sát _cực đại trong nhiều trung bình mẫu_. Hai đại lượng khác nhau, hai phân
phối mẫu khác nhau.

> "the data miner requires the sampling distribution of the maximum mean among
> a multitude of means because that is the statistic being considered when
> evaluating the best rule found by data mining."

## 2. Suy thoái ngoài mẫu KHÔNG phải bằng chứng thị trường đã đổi

[A] tr. 262-264 loại ba cách giải thích và giữ một:

| giải thích                      | vì sao bị loại                                                                     |
| ------------------------------- | ---------------------------------------------------------------------------------- |
| biến thiên ngẫu nhiên đơn thuần | nếu vậy ngoài mẫu phải TỐT hơn cũng thường xuyên như tệ hơn; thực tế tệ hơn áp đảo |
| động lực thị trường đã đổi      | đòi thị trường đổi đúng lúc mỗi luật rời phòng thí nghiệm — "almost fiendish"      |
| quá nhiều người dùng luật đó    | số luật khả dĩ gần vô hạn, khó đủ đông người dùng đúng một luật                    |
| **sai lệch khai thác dữ liệu**  | giải thích cùng hiện tượng, không cần giả định thêm → dao cạo Occam                |

> "out-of-sample performance deterioration of the best rule is most probably a
> **fall from an unrealistically high expectation** rather than an actual
> decline in the rule's predictive power." (tr. 263-264)

## 3. Năm yếu tố quyết định độ lớn sai lệch ([A] tr. 288-289)

| #   | yếu tố                                 | chiều                                                    |
| --- | -------------------------------------- | -------------------------------------------------------- |
| 1   | số luật đã kiểm định                   | nhiều hơn → sai lệch LỚN hơn (gần tuyến tính theo log₁₀) |
| 2   | số quan sát để tính chỉ số             | nhiều hơn → sai lệch NHỎ hơn                             |
| 3   | tương quan giữa lợi suất các luật      | thấp hơn → sai lệch LỚN hơn                              |
| 4   | giá trị ngoại lai dương                | nhiều/lớn hơn → sai lệch LỚN hơn                         |
| 5   | phương sai công lực thật giữa các luật | thấp hơn → sai lệch LỚN hơn                              |

Hiệu chuẩn bằng luật nhân tạo ([A] tr. 294-297) — lịch sử 24 tháng, mọi luật kỳ
vọng đúng bằng 0, lợi suất độc lập; sai lệch tính bằng % lợi nhuận năm:

| chọn tốt nhất trong | sai lệch |
| ------------------: | -------: |
|      1 (không quét) |       0% |
|                   2 |    +8,5% |
|                  10 |     +22% |
|                  50 |     +33% |
|                 400 |     +48% |

Trích [A] tr. 297-298 về giới hạn của bảng này:

> "the particular magnitudes of data-mining bias shown in the preceding tests
> are valid only for the particulars of this test... In a different data-mining
> venture, with different particulars, the same principle would apply (more
> rules produce a bigger bias) but the specific levels of the data-mining bias
> would be different."

## 4. Ba phương pháp hiệu chỉnh

### 4.1 White's Reality Check ([A] tr. 325-326, [B])

Giả thuyết không: MỌI luật trong vũ trụ đã quét có lợi suất kỳ vọng 0.

1. Trừ trung bình của chính nó khỏi từng luật → áp đặt kỳ vọng 0.
2. Lấy mẫu CÓ HOÀN LẠI các mốc thời gian, độ dài bằng lịch sử gốc, **cùng bộ mốc
   cho mọi luật**.
3. Trung bình từng luật → lấy giá trị LỚN NHẤT.
4. Lặp ≥ 500 lần.
5. p = tỉ lệ giá trị ≥ trung bình quan sát của luật tốt nhất.

### 4.2 Hoán vị Monte Carlo ([A] tr. 327-328)

Giả thuyết không khác: "trạng thái đầu ra của luật tương quan ngẫu nhiên với
biến động tương lai". Ghép chuỗi trạng thái (+1/−1) với lợi suất thị trường đã
xáo trộn.

Chi tiết dễ bỏ sót nhất, trích nguyên văn tr. 328:

> "it is important the same pairings be used for all competing rules. Thus, if a
> rule's output value for day 7 is paired with the market return for day 15,
> this same pairing must be done for all competing rules. **This is done to
> preserve correlation structure that may be present in the rules, which is one
> of the five factors impacting the data-mining bias.**"

MCP không dựng được khoảng tin cậy vì không kiểm giả thuyết về giá trị trung
bình; WRC thì được.

### 4.3 Co ngót Markowitz–Xu ([A] tr. 323-324, [E])

`H' = R + B(H − R)`. Aronson gọi thẳng: _"MX is best used as a rough
guideline"_ — có điều kiện cho kết quả sai nặng.

### 4.4 Phê bình Hansen và cải tiến Romano–Wolf ([A] tr. 329-330, [C], [D])

Hansen: WRC/MCP mất lực kiểm định khi vũ trụ chứa luật _tệ hơn mốc chuẩn_ — ví
dụ khi đưa cả bản đảo dấu của mỗi luật vào. Masters kiểm lại: đúng khi luật kỳ
vọng âm có phương sai cực lớn; trường hợp thường gặp thì vẫn đủ khoẻ.

Romano–Wolf: bản từng bước, tăng lực kiểm định và tìm được MỌI luật đạt chứ
không chỉ luật đầu bảng.

## 5. Khai thác dữ liệu là HỢP LỆ — đừng rút ra kết luận sai

[A] tr. 268 bác thẳng việc từ chối quét:

> "an objective technician who refuses to data mine is like the taxi driver who
> refuses to abandon the horse-drawn carriage."

Ba lý do: (1) nó hiệu quả — quét nhiều luật hơn thì xác suất tìm được luật tốt
cao hơn; (2) công nghệ đã rẻ; (3) TA chưa có nền lý thuyết đủ để suy diễn một
giả thuyết duy nhất từ lý thuyết như vật lý.

Và [A] tr. 281 dẫn chứng minh của White [B]: khi cỡ mẫu → ∞, luật có hiệu suất
quan sát cao nhất CHÍNH LÀ luật có kỳ vọng cao nhất với xác suất → 1.

> "This tells us that the basic logic of data mining is sound!"

**Cái không được phép** chỉ là một điều: dùng chính con số thắng cuộc làm ước
lượng.

## 6. Rủi ro chọn nhầm luật kém ([A] tr. 286-287)

Khi hai luật có công lực gần nhau, phân phối hiệu suất quan sát của chúng chồng
lấn nhiều → khả năng cao luật KÉM hơn thắng cuộc thi nhờ may mắn. Chỉ khi chênh
lệch công lực đủ lớn thì "merit will shine through the fog of randomness".

Hệ quả thực tế: trong một cao nguyên tham số phẳng, việc cấu hình A thắng cấu
hình B **không** là bằng chứng A tốt hơn B. Cao nguyên phẳng là dấu hiệu tốt cho
tính bền, nhưng đồng thời là dấu hiệu xấu cho việc chọn ra một điểm cụ thể.

## 7. Bơ Bangladesh ([A] tr. 260-261, [F])

Leinweber quét vài trăm chuỗi kinh tế trong CSDL Liên Hợp Quốc để tìm chuỗi
tương quan cao nhất với S&P 500. Người thắng: **sản lượng bơ ở Bangladesh**,
tương quan ~0,70.

> "Intuition alone would tell us a high correlation between Bangladesh butter
> and the S&P 500 is specious, but now imagine if the time series with the
> highest correlation **had a plausible connection** to the S&P 500. Intuition
> would not warn us."

Đây là lời cảnh báo sắc nhất cho dự án này: trực giác chỉ bảo vệ ta khỏi những
mối liên hệ NGHE ĐÃ THẤY VÔ LÝ. Với một mối liên hệ nghe hợp lý — "nén biến động
rồi phá vỡ", "bán khi thủng đáy trong xu hướng giảm" — trực giác im lặng, và chỉ
còn phép kiểm định đứng giữa ta và bơ Bangladesh.

## 8. Quy tắc rút ra cho hệ thống

1. Mọi kết quả quét phải ghi kèm **số luật đã thử**. Không ghi thì con số vô nghĩa.
2. Con số của luật thắng trong một cuộc quét **không bao giờ** được báo cáo như
   ước lượng hiệu suất. Ước lượng phải đến từ holdout chưa mở, hoặc từ WRC/MCP.
3. Phép đối chứng phải dựng phân phối của **cực đại trên toàn vũ trụ luật**, dùng
   `reality_check.py`. Đối chứng chỉ-luật-thắng-với-một-luật-ngẫu-nhiên là
   hiệu chỉnh THIẾU.
4. MCP phải dùng **cùng một hoán vị cho mọi luật**.
5. Khi một luật hỏng ở holdout, giải thích mặc định là sai lệch khai thác dữ
   liệu. Muốn đổ cho thị trường thì phải nêu lý do TRƯỚC khi xem kết quả.
6. Cao nguyên tham số phẳng: dùng để kết luận _họ luật có bền không_, KHÔNG dùng
   để kết luận _điểm nào trong cao nguyên tốt nhất_.

---

# Phần XII — Katz & McCormick, _The Encyclopedia of Trading Strategies_ (2000) ch.4

Bổ sung cho các phần đã ghi từ ch.3/4/5. Hai điểm phương pháp luận dưới đây chưa
được ghi và cả hai đều áp ngược vào chính kết quả của dự án.

## 64. Trong mẫu thì HIỆU CHỈNH, ngoài mẫu thì KHÔNG — tr. 129

Quy tắc phát biểu thẳng và chính xác:

> "Be sure to use statistics that are **corrected for multiple tests** when
> analyzing **in-sample optimization results**. **Out-of-sample tests should be
> analyzed with standard, uncorrected statistics.**"

Lý do: trong mẫu ta đã chọn người thắng trong nhiều ứng viên, nên phải trả giá
cho việc chọn. Ngoài mẫu chỉ có **một** phép kiểm trên một cấu hình đã cố định
từ trước, nên không có gì để hiệu chỉnh — hiệu chỉnh thêm là **phạt oan**.

**Áp vào dự án:** các kết quả holdout của TOM-XAU, Magic-Hours, DON-H4 đã từng
bị đối chiếu với ngưỡng Bonferroni. Theo Katz thì đó là sai hướng: ngưỡng
Bonferroni thuộc về giai đoạn quét trong mẫu, không thuộc về holdout. Cần rà lại
các phán quyết cũ xem có cái nào bị loại oan vì áp nhầm ngưỡng không.

## 65. Bonferroni QUÁ BẢO THỦ khi các phép kiểm tương quan — tr. 178-179

> "in many trading systems, **small changes in the parameters produce relatively
> small changes in the results. This is exactly like serial dependence in data
> samples: It reduces the effective population size**, in this case, the
> effective number of tests run. Because many of the tests are correlated, **the
> 20 actual tests probably correspond to about 5 to 10 independent tests.**"

Ví dụ định lượng của Katz: p thô 0,02; hiệu chỉnh Bonferroni cho 20 phép kiểm ra
0,3104; nhưng ước lượng thực tế có tính tương quan là **khoảng 0,15** — tức
Bonferroni phạt nặng gấp đôi mức đáng phạt.

Và ông ghi rõ giới hạn:

> "The nature and extent of serial dependence in the multiple tests are **never
> known**, and therefore, a less conservative adjustment for optimization
> **cannot be directly calculated, only roughly reckoned.**"

### Áp ngược vào kết quả entry_power của chính tôi (§47 backtesting.md)

Tôi đã báo "0/10 cấu hình vượt Bonferroni" và kết luận chiều cao đỉnh là ảo ảnh
chọn lọc. Theo Katz, kết luận đó **quá nặng tay**:

- 10 cấu hình gồm 5 cửa sổ nhìn lại × 2 thị trường;
- năm cửa sổ trên cùng một thị trường chồng lấn nặng (Katz: "small changes in
  parameters produce relatively small changes in results");
- hai thị trường tương quan 0,82 (Katz sanos ch.7 tr.96).

Số phép kiểm **hiệu dụng** gần với 2-3 hơn là 10. Ngưỡng tương ứng khi đó là
α ≈ 0,017-0,025 chứ không phải 0,005 — và cấu hình XAUUSD/Donchian200 có
p = 0,0102 sẽ **vượt**.

Cần nói rõ hai điều để không đu sang thái cực ngược lại:

1. Đây là "roughly reckoned" theo đúng chữ của Katz, **không phải một phép tính**.
   Không được dùng nó để tuyên bố ý nghĩa thống kê.
2. White's Reality Check bên trong mỗi cấu hình **đã** xử lý tương quan giữa 120
   mốc thời gian giữ. Phần quá bảo thủ chỉ nằm ở lớp Bonferroni giữa 10 cấu hình.

**Phát biểu đúng của kết quả §47:** sự thật nằm giữa "0/10 vượt" và "1/10 vượt",
và không phép hiệu chỉnh nào cho câu trả lời chính xác. Điều quyết định vẫn là
backtest thật ở §66 — nó không phụ thuộc vào tranh cãi hiệu chỉnh này.

Ghi lại cả hai phiên bản thay vì lặng lẽ sửa con số, vì bản thân việc tôi suýt
kết luận sai theo **cả hai** hướng (đầu tiên quá lạc quan với t ≥ 2, rồi quá bi
quan với Bonferroni) là bài học đáng giữ.

## 66. Việc phải làm

| #   | việc                                                                                                                           | mức ưu tiên                           | căn cứ          |
| --- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------- | --------------- |
| 66  | Rà các phán quyết holdout cũ xem có cái nào bị áp nhầm ngưỡng Bonferroni (ngoài mẫu KHÔNG hiệu chỉnh)                          | **cao** — có thể đã loại oan ứng viên | Katz tr.129     |
| 67  | Khi báo kết quả quét trong mẫu, ghi **cả** p thô và p Bonferroni, kèm ghi chú số phép kiểm hiệu dụng nhỏ hơn số phép kiểm thực | trung bình                            | Katz tr.178-179 |
