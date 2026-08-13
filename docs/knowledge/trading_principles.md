# KB-01 — Vì sao một chiến lược có lý do tồn tại

## References

| #   | nguồn                                                                                                                                        | chương / trang                                          | nguyên lý lấy ra                                                                                        |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| [A] | Aronson, D. (2007). _Evidence-Based Technical Analysis: Applying the Scientific Method and Statistical Inference to Trading Signals_. Wiley. | Ch. 7 "Theories of Nonrandom Price Motion", tr. 333-396 | phản hồi dương/âm; thác thông tin; phản ứng dưới mức và quá mức; vì sao EMH không loại trừ TA           |
| [B] | Aronson (2007), như trên                                                                                                                     | Ch. 6 "Data-Mining Bias", tr. 257-332                   | luật không có lý do kinh tế thì chỉ còn là quét dữ liệu                                                 |
| [C] | Jegadeesh, N. & Titman, S. (1993). "Returns to Buying Winners and Selling Losers". _Journal of Finance_ 48(1), 65-91                         | —                                                       | momentum 6-12 tháng bền; dẫn lại trong [A] tr. 352-353                                                  |
| [D] | De Bondt, W. & Thaler, R. (1985/1987). nghiên cứu đảo chiều dài hạn                                                                          | —                                                       | momentum 3-5 năm ĐẢO chiều; dẫn lại trong [A] tr. 353                                                   |
| [E] | Cooper, M. — nghiên cứu đỉnh 52 tuần                                                                                                         | —                                                       | momentum đo bằng khoảng cách tới đỉnh 52 tuần thì KHÔNG đảo; dẫn lại trong [A] tr. 353                  |
| [F] | Shleifer, A. — tài chính hành vi, giới hạn của kinh doanh chênh lệch giá                                                                     | —                                                       | rủi ro nhà giao dịch nhiễu; dẫn lại trong [A] tr. 347-349                                               |
| [G] | Shiller, R. — tâm lý học đầu tư                                                                                                              | —                                                       | bác tâm lý học bình dân; sự chú ý xã hội; hiệu ứng truyền miệng; dẫn lại trong [A] tr. 333-334, 365-366 |

---

## 1. Nguyên lý trung tâm: PHẢN HỒI, không phải "9 trạng thái"

Đây là đoạn quan trọng nhất cho kiến trúc của dự án. Trích nguyên văn [A] tr. 369:

> "Financial markets, like other self-organizing self-regulated systems, rely on
> a healthy balance between negative and positive feedback. **Arbitrage provides
> negative feedback.** Prices that are too high or too low trigger arbitrage
> trading that pushes prices back toward rational levels. **Positive feedback
> occurs when investor decisions are dominated by imitative behavior rather than
> independent choice.** In this regime, investors will hop aboard an initial
> price movement, buying after first signs of strength or selling after first
> signs of weakness, thus amplifying an initial small price movement into a
> large-scale trend. **A TA approach, known as trend following, depends on
> large-scale price moves for its profitability and thus is most effective
> during times when positive feedback dominates.**"

Rút ra, và đây là trục PHÂN LOẠI TRẠNG THÁI CÓ CƠ SỞ:

| chế độ phản hồi                 | cơ chế                                                                | loại chiến lược hợp                    |
| ------------------------------- | --------------------------------------------------------------------- | -------------------------------------- |
| **phản hồi DƯƠNG chiếm ưu thế** | bắt chước, thác thông tin, chú ý xã hội khuếch đại một cú giá ban đầu | bám xu hướng, phá vỡ kênh giá          |
| **phản hồi ÂM chiếm ưu thế**    | kinh doanh chênh lệch giá kéo giá về mức hợp lý                       | hồi quy trung bình, mua bán trong biên |

**Đối chiếu với hệ thống hiện tại:** `shared/regime/states9.py` định nghĩa 9
trạng thái trên ba trục (hướng × sức mạnh × biến động) mà tôi tự đặt. Không trục
nào trong đó là trục _chế độ phản hồi_. Tài liệu chỉ ra trục có cơ sở lý thuyết
là **phản hồi dương hay âm đang chiếm ưu thế** — một phân biệt HAI chế độ, và
mỗi chế độ ứng với một họ chiến lược khác nhau.

Chín trạng thái của tôi không sai về mặt mô tả, nhưng chúng mô tả _hình dạng của
giá_, không mô tả _cơ chế sinh ra hình dạng ấy_. Mà cơ chế mới là thứ quyết định
chiến lược nào có lý do hoạt động.

## 2. Vì sao xu hướng tồn tại — bốn cơ chế được đặt tên

### 2.1 Phản ứng DƯỚI mức tin tức ([A] tr. 333, 339-340)

> "the so-called underreaction effect... says that, because prices sometimes
> fail to respond to new information as rapidly as EMH theorists contend, a
> systematic price movement, or trend, toward a price level that does reflect
> the new information occurs."

Giá không nhảy tức thì tới mức hợp lý mới mà TRÔI dần tới đó. Khoảng trôi ấy
chính là thứ chiến lược bám xu hướng ăn. Nguyên nhân nhận thức: thiên lệch bảo
thủ và hiệu ứng mỏ neo.

### 2.2 Thác thông tin ([A] tr. 364-365)

Ví dụ hai nhà hàng mở cạnh nhau: khách đầu tiên chọn ngẫu nhiên, khách thứ hai
thấy một quán có người nên vào theo, khách thứ ba càng dễ theo hơn. Kết quả:

> "an initial random event sets the course of history down one particular path...
> In the same way, **an initial random price movement can trigger successive
> rounds of imitative investor behavior, resulting in a long-duration
> large-amplitude price swing.**"

Điểm đáng chú ý về phương pháp luận: bắt chước ở đây là **hành vi HỢP LÝ của
từng cá nhân** — không phải "đám đông hoảng loạn" như tâm lý học bình dân nói.
Aronson dẫn Shiller bác thẳng lối giải thích ấy ([A] tr. 333-334):

> "In considering lessons from psychology, it must be noted that the many
> popular accounts of the psychology of investing are simply not credible.
> Investors are said to be euphoric or frenzied during booms or panic-stricken
> during market crashes... The fact is, people are more rational than these
> pop-psychology theories suggest."

**Áp dụng:** mọi comment trong codebase giải thích tín hiệu bằng "tâm lý đám
đông", "hoảng loạn", "tham lam" đều thuộc loại bị bác ở đây. Lời giải thích đúng
là _bắt chước hợp lý dưới bất định_ và _thông tin lan chậm_.

### 2.3 Chú ý xã hội ([A] tr. 366)

Bộ não chỉ chú ý được một thứ tại một thời điểm, và dùng quy tắc "cái gì người
khác chú ý thì đáng chú ý". Shiller cho thấy cả nhà đầu tư tổ chức cũng mua chỉ
vì giá vừa tăng nhanh — và thường không tự nhận ra đó là lý do.

### 2.4 Giới hạn của kinh doanh chênh lệch giá ([A] tr. 347-349)

Vì sao phản hồi âm không dập tắt được xu hướng ngay:

- không có chuông báo khi giá sai — giá hợp lý là hiện giá dòng tiền tương lai,
  bản thân nó bất định;
- **rủi ro nhà giao dịch nhiễu**: sai lệch có thể GIÃN RỘNG trước khi thu hẹp,
  và người chênh lệch giá có thể bị cắt lỗ trước khi đúng;
- đòn bẩy quá mức giết người có thông tin đúng — dẫn thẳng tới tiêu chuẩn Kelly
  (xem KB-03);
- không có chứng khoán thay thế hoàn hảo;
- vốn và quyền tự quyết của quỹ đều hữu hạn.

LTCM 1998 được nêu làm ví dụ: định giá sai họ nhận ra CUỐI CÙNG đều đúng, nhưng
đòn bẩy quá lớn khiến họ không sống nổi tới lúc đó.

## 3. Vì sao hồi quy trung bình tồn tại

### 3.1 Phản ứng QUÁ mức ([A] tr. 338-339, 361)

Tự tin thái quá + lạc quan thái quá → nhà đầu tư phản ứng quá mạnh với thông tin
riêng của mình → giá vọt quá mức hợp lý → đảo chiều có hệ thống về lại mức đó.

### 3.2 Tội của số nhỏ ([A] tr. 361-362)

Hai lỗi phán đoán ĐỐI NGHỊCH cùng sinh ra từ việc bỏ qua cỡ mẫu:

| lỗi                      | xảy ra khi                                        | hậu quả                                                                |
| ------------------------ | ------------------------------------------------- | ---------------------------------------------------------------------- |
| **ngộ nhận của con bạc** | người quan sát TIN TRƯỚC rằng chuỗi là ngẫu nhiên | thấy 5 lần tăng thì tưởng sắp giảm                                     |
| **ảo giác cụm**          | người quan sát KHÔNG có niềm tin trước            | thấy một chuỗi ngẫu nhiên tình cờ thành cụm thì tưởng là xu hướng thật |

**Đây là mô tả chính xác cái bẫy của chính dự án này.** Ảo giác cụm là tên gọi
học thuật cho việc tôi nhìn một cao nguyên tham số và tưởng đó là edge.

## 4. Bằng chứng thực nghiệm ĐÃ CÔNG BỐ về khả năng dự báo

Trích [A] tr. 352-353 — đây là danh sách các hiệu ứng có bằng chứng, dùng làm
BỘ LỌC cho mọi ý tưởng chiến lược mới:

| hiệu ứng                                  | nội dung                                                                                                                     | nguồn gốc                     |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| **momentum bền 6-12 tháng**               | mua nhóm mạnh nhất 6 tháng qua / bán nhóm yếu nhất, giữ 6 tháng → khoảng 10%/năm                                             | Jegadeesh & Titman (1993) [C] |
| **momentum đảo 3-5 năm**                  | xu hướng đo trên 3-5 năm thì ĐẢO; danh mục mua kẻ thua/bán kẻ thắng ~8%/năm trong 3 năm sau, và KHÔNG do rủi ro cao hơn      | De Bondt & Thaler [D]         |
| **momentum không đảo**                    | đo momentum bằng khoảng cách tới ĐỈNH 52 TUẦN thay vì tỉ suất sinh lời quá khứ → lợi nhuận cao hơn và KHÔNG đảo chiều        | Cooper [E]                    |
| **momentum + khối lượng**                 | kết hợp khối lượng với momentum giá thêm 2-7%/năm                                                                            | dẫn trong [A] tr. 353         |
| **bất ngờ lợi nhuận + xác nhận kỹ thuật** | tin lợi nhuận bất ngờ được xác nhận bằng giá và khối lượng ngày hôm sau → chênh lệch dài-ngắn >30%/năm trong tháng tiếp theo | dẫn trong [A] tr. 352         |

**Quan sát quan trọng cho dự án:** hiệu ứng đỉnh-52-tuần [E] là hiệu ứng
KHÔNG ĐẢO CHIỀU duy nhất trong danh sách, và cơ chế được nêu là **hiệu ứng mỏ
neo** — nhà đầu tư neo vào đỉnh cũ nên phản ứng chậm với tin mới.

Điều này liên quan trực tiếp tới `DonchianH4Breakout`: phá vỡ đỉnh N nến CHÍNH
LÀ một phiên bản của "khoảng cách tới đỉnh gần đây". Vậy chiến lược đang chạy có
một cơ chế đã được đặt tên và có bằng chứng công bố — không phải luật tự chế.
Đây là điều trước nay chưa từng được ghi vào module.

## 5. Vì sao EMH không loại trừ TA — và lỗi logic của cả hai phe

### 5.1 Tiền đề phổ biến của TA tự mâu thuẫn ([A] tr. 333)

Murphy viết tiền đề nền tảng của TA là "mọi thứ ảnh hưởng tới giá đều đã phản
ánh vào giá". Aronson chỉ ra đó chính là tiền đề của EMH — kẻ thù không đội trời
chung của TA:

> "if it were true that price did reflect all possible information, it would
> imply that price was devoid of any predictive information."

**Áp dụng:** bất kỳ comment nào trong codebase biện minh cho một chỉ báo bằng
câu "giá đã phản ánh tất cả" là tự mâu thuẫn và phải bỏ.

### 5.2 EMH tự miễn nhiễm bằng giả thuyết đặc biệt ([A] tr. 341, 354-355)

EMH chỉ nói không thể ăn hơn thị trường _sau khi hiệu chỉnh rủi ro_. Nhưng phe
EMH tự cho mình quyền nghĩ ra yếu tố rủi ro MỚI mỗi khi có chiến lược thắng:

> "proposing a new risk factor(s) after a market-beating strategy has been
> discovered is nothing more than an ad hoc hypothesis. This is an explanation
> cooked up after the fact for the specific purpose of immunizing a theory...
> from falsification."

Fama–French thêm hai yếu tố (giá/sổ sách và vốn hoá) đúng sau khi hai biến ấy
được chứng minh sinh lợi vượt trội. Aronson gọi thẳng đó là cứu một lý thuyết
đang chết.

**Áp dụng cho chính chúng ta — nguy hiểm hơn nhiều:** đây đúng là thứ tôi làm
khi một chiến lược hỏng ở holdout rồi tôi giải thích bằng "holdout nghèo cơ hội".
Giả thuyết đặc biệt sau sự việc. Quy tắc rút ra: **mọi lời giải thích cho một
thất bại phải được nêu TRƯỚC khi nhìn kết quả, nếu không thì không được tính.**

## 6. Quy tắc rút ra cho hệ thống

1. Mỗi chiến lược trong `live_strategies/` phải ghi được **cơ chế** của nó thuộc
   loại nào trong mục 2 hoặc 3, và trích nguồn. Không ghi được thì nó là luật
   quét dữ liệu, phải gắn nhãn như vậy.
2. Trục trạng thái thị trường có cơ sở là **chế độ phản hồi** (dương/âm), không
   phải chín ô hình dạng giá.
3. Cấm giải thích tín hiệu bằng tâm lý học bình dân ("hoảng loạn", "tham lam").
4. Cấm giả thuyết đặc biệt sau sự việc để cứu một kết quả hỏng.
5. Ý tưởng chiến lược mới nên bắt đầu từ bảng mục 4 — các hiệu ứng đã có bằng
   chứng — chứ không từ việc quét tổ hợp chỉ báo.
