# KB — Quy trình nghiên cứu: backtest KHÔNG phải công cụ tìm kiếm

## References

| #   | nguồn                                                                            | chương / trang                                   | nguyên lý lấy ra                                             |
| --- | -------------------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------ |
| [A] | López de Prado, M. (2018). _Advances in Financial Machine Learning_. Wiley.      | Ch. 1.2 tr. 4-5                                  | nghịch lý Sisyphus và mô hình siêu-chiến-lược                |
| [B] | López de Prado (2018)                                                            | Ch. 11 "The Dangers of Backtesting", tr. 151-159 | backtest không phải công cụ nghiên cứu; sáu khuyến nghị; PBO |
| [C] | Luo, Y. và cộng sự (2014). "Seven Sins of Quantitative Investing". Deutsche Bank | dẫn trong [B] tr. 152                            | bảy tội của đầu tư định lượng                                |
| [D] | Bailey, D., Borwein, J., López de Prado, M. & Zhu, Q. (2017a)                    | dẫn trong [B] tr. 155-156                        | CSCV để ước lượng xác suất overfit backtest                  |
| [E] | Bailey, D. & López de Prado, M. (2014b)                                          | dẫn trong [B] tr. 154                            | Deflated Sharpe Ratio                                        |

File này là phần đối chiếu trực tiếp với cách dự án đang làm việc. Xem thêm
`backtesting.md` (Aronson ch.8-9) và `psychology.md`.

---

## 1. Backtest không phải công cụ nghiên cứu — [B] tr. 153

Trích nguyên văn, đoạn nặng nhất đối với dự án:

> "**a backtest is not a research tool.** It provides us with very little insight
> into the reason why a particular strategy would have made money. Just as a
> lottery winner may feel he has done something to deserve his luck, there is
> always some ex-post story... Authors claim to have found hundreds of 'alphas'
> and 'factors,' and there is always some convoluted explanation for them.
> **Instead, what they have found are the lottery tickets that won the last
> game.** The winner has cashed out, and those numbers are useless for the next
> round... Those authors never tell us about all the tickets that were sold, that
> is, the millions of simulations it took to find these 'lucky' alphas."

> "**The purpose of a backtest is to discard bad models, not to improve them.**
> Adjusting your model based on the backtest results is a waste of time... and
> it is dangerous. Invest your time and effort in getting all the components
> right... **By the time you are backtesting, it is too late. Never backtest
> until your model has been fully specified. If the backtest fails, start all
> over.**"

Định luật thứ hai của tác giả, [B] tr. 154:

> **"Backtesting while researching is like drinking and driving. Do not research
> under the influence of a backtest."**

### Đối chiếu với phiên 03/08 — vi phạm trực tiếp và có hệ thống

Quy trình tôi dùng cả ngày: chạy backtest, xem kết quả, sửa giả thuyết, chạy
lại. Đúng 90 lần. Đó chính xác là "nghiên cứu dưới ảnh hưởng của backtest".

Ví dụ rõ nhất: giả thuyết "bán vào nhịp bật" không có nguồn nào đề xuất trước.
Nó nảy ra _sau khi_ tôi thấy báo nhầm dồn vào cú hồi trong một backtest trước
đó. Rồi tôi lại kiểm nó bằng backtest. Cả chuỗi suy luận nằm trọn bên trong
vòng lặp mà tài liệu cấm.

Điều tài liệu yêu cầu thay vào đó: xác định đầy đủ mô hình TRƯỚC — cấu trúc dữ
liệu, gán nhãn, trọng số, ensemble, kiểm định chéo, tầm quan trọng đặc trưng,
cỡ lệnh — rồi backtest MỘT lần để loại bỏ, không phải để cải thiện.

Công cụ nghiên cứu đúng, theo [B] tr. 153, là **tầm quan trọng đặc trưng**, vì
nó tính được TRƯỚC khi mô phỏng hiệu suất lịch sử.

## 2. Bảy tội của đầu tư định lượng — [C] dẫn trong [B] tr. 152

| #   | tội                                                                   | tình trạng dự án                                                           |
| --- | --------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| 1   | thiên lệch sống sót                                                   | không áp dụng — một symbol                                                 |
| 2   | thiên lệch nhìn trước                                                 | đã kiểm soát: khớp ở giá đóng nến cộng spread, tái tạo đúng cơ chế live    |
| 3   | **kể chuyện** — bịa lời giải thích sau sự việc cho một mẫu ngẫu nhiên | **vi phạm nhiều lần**                                                      |
| 4   | khai thác và dò dẫm dữ liệu                                           | đang xử lý — `reality_check.py`                                            |
| 5   | chi phí giao dịch                                                     | có spread thật theo giờ trong SimBroker                                    |
| 6   | **ngoại lai** — dựa vào vài kết quả cực đoan khó lặp lại              | **đã phát hiện**: 3 năm tốt nhất chiếm 138% lợi nhuận của SqueezeBreakdown |
| 7   | bán khống — chi phí vay và khả dụng                                   | không áp dụng — CFD vàng                                                   |

Tác giả nhận xét về danh sách này ([B] tr. 152): _"These are just a few basic
errors that most papers published in journals make routinely."_

## 3. Ngay cả backtest hoàn hảo cũng có thể sai — [B] tr. 152-153

> "this flawless backtest is probably wrong. Why? **Because only an expert can
> produce a flawless backtest. Becoming an expert means that you have run tens of
> thousands of backtests over the years.** In conclusion, this is not the first
> backtest you produce, so we need to account for the possibility that this is a
> false discovery."

> "**The maddening thing about backtesting is that, the better you become at it,
> the more likely false discoveries will pop up.**"

## 4. Sáu khuyến nghị chống overfit backtest — [B] tr. 154

| #   | khuyến nghị                                                                                                    | tình trạng dự án                                                                                             |
| --- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| 1   | Xây mô hình cho **cả lớp tài sản**, không cho một chứng khoán cụ thể                                           | áp dụng có điều kiện — xem §5; hệ thống chỉ GIAO DỊCH XAU (đúng), nhưng cũng chỉ KIỂM CHỨNG trên XAU (thiếu) |
| 2   | Dùng **bagging**; nếu bagging làm hiệu suất tệ đi thì chiến lược vốn đã overfit vào ít quan sát hoặc ngoại lai | chưa làm                                                                                                     |
| 3   | Không backtest cho tới khi nghiên cứu hoàn tất                                                                 | **vi phạm** — xem §1                                                                                         |
| 4   | **Ghi lại MỌI backtest** đã chạy trên tập dữ liệu, để ước lượng PBO và giảm phát Sharpe theo số lần thử        | chưa có sổ tập trung                                                                                         |
| 5   | **Mô phỏng kịch bản thay vì lịch sử**                                                                          | một phần — có bootstrap khối cho sizing, chưa có cho tín hiệu                                                |
| 6   | Backtest hỏng thì **làm lại từ đầu**, không tái sử dụng kết quả                                                | **vi phạm** — mỗi thất bại đều thành đầu vào cho giả thuyết kế tiếp                                          |

Về khuyến nghị 5, trích [B] tr. 154:

> "A standard backtest is a historical simulation, which can be easily overfit.
> **History is just the random path that was realized, and it could have been
> entirely different.** Your strategy should be profitable under a wide range of
> scenarios, not just the anecdotal historical path. **It is harder to overfit
> the outcome of thousands of 'what if' scenarios.**"

## 5. Khuyến nghị 1 — chỗ vi phạm nặng nhất và sửa được ngay

Trích [B] tr. 154:

> "Develop models for **entire asset classes or investment universes**, rather
> than for specific securities. Investors diversify, hence they do not make
> mistake X only on security Y. **If you find mistake X only on security Y, no
> matter how apparently profitable, it is likely a false discovery.**"

### Làm rõ phạm vi — hệ thống VẪN chỉ giao dịch XAU

Khuyến nghị này **không** đề xuất giao dịch nhiều symbol. Danh mục sản xuất giữ
nguyên: xAUUSD, đúng ràng buộc FTMO.

Điều tài liệu nói là dùng các symbol khác làm **kiểm chứng ngoài mẫu miễn phí**.
Bạc và các cặp FX đóng vai trò tập dữ liệu thứ hai để trả lời một câu duy nhất:
_cơ chế này có thật, hay chỉ khớp riêng vào lịch sử của vàng?_ Không có lệnh nào
được đặt trên chúng.

Kho dữ liệu đã có sẵn chín symbol: `AUDUSD, EURUSD, GBPUSD, NZDUSD, USDCAD,
USDCHF, USDJPY, XAGUSD, XAUUSD` — tức tám tập kiểm chứng đang không được dùng.

### Giới hạn của lập luận này với riêng vàng — [suy luận của ta]

Cần ghi nhận một điểm mà tài liệu không bàn tới. López de Prado viết trong bối
cảnh **cắt ngang nhiều chứng khoán**, nơi lập luận là "nhà đầu tư đa dạng hoá
nên họ không phạm sai lầm X chỉ trên chứng khoán Y" — tức sai lầm hành vi lan ra
cả vũ trụ.

Vàng có động lực riêng mà EURUSD không chia sẻ: lãi suất thực, mua vào của ngân
hàng trung ương, dòng trú ẩn, và không có dòng tiền nội tại. Một hiệu ứng chỉ
xuất hiện trên vàng vì thế **không tự động là khám phá giả**.

Kết luận cân bằng: nhân bản được sang thị trường khác là bằng chứng **mạnh** ủng
hộ; không nhân bản được là bằng chứng **yếu** phản đối — yếu hơn so với bối cảnh
cổ phiếu chéo mà tài liệu viết. Nên dùng nó như một tín hiệu cảnh báo cần giải
thích, không phải một cổng loại bỏ tự động.

Nặng hơn: dự án ĐÃ từng làm phép nhân bản này cho `SqueezeBreakdown` — 4/8 thị
trường dương, trung vị −0,158R, chênh lệch thuận-nghịch đi sai hướng — rồi vẫn
đưa nó vào danh mục với lý do "FTMO chỉ giao dịch XAUUSD, và breakout vốn mạnh
ở kim loại hơn FX". Theo [B] tr. 154, lý lẽ ấy không hợp lệ: không nhân bản
được là bằng chứng của khám phá giả, không phải một đặc thù cần bào chữa.

Phán quyết bác bỏ ngày 03/08 (LCB95 âm) rốt cuộc trùng với điều tài liệu đã
tiên đoán từ dấu hiệu nhân bản.

## 6. Walk-forward dễ bị overfit — [B] tr. 155

> "One disadvantage of the walk-forward method is that **it can be easily
> overfit. The reason is that without random sampling, there is a single path of
> testing that can be repeated over and over until a false positive appears.**"

**Áp dụng:** dự án dùng dev/holdout một đường duy nhất (2003-2017 / 2017-2026),
và tôi đã mở holdout ấy nhiều lần trong cùng một ngày. Theo đoạn trên, đó chính
là cơ chế sinh dương tính giả — và nó giải thích vì sao vài cấu hình "qua
holdout" mà vẫn không đáng tin.

Giải pháp tài liệu đề xuất: **kiểm định chéo tổ hợp có thanh trừng** (ch.12),
tạo NHIỀU đường kiểm thử thay vì một.

## 7. PBO qua CSCV — [D] dẫn trong [B] tr. 155-156

1. Dựng ma trận `M` cỡ `T × N`: mỗi cột là chuỗi lãi/lỗ của MỘT cấu hình đã thử;
   mọi cột cùng trục thời gian, đồng bộ theo hàng.
2. Chia `M` theo hàng thành `S` khối rời rạc bằng nhau (`S` chẵn).
3. Lập MỌI tổ hợp chọn `S/2` khối làm tập huấn luyện. Với `S = 16` được 12.870
   tổ hợp.
4. Mỗi tổ hợp: chọn cấu hình tốt nhất trên tập huấn luyện (`n*`), rồi tính hạng
   tương đối của `n*` trên tập kiểm thử (phần bù).
5. Tính `λ = log(ω / (1 − ω))` với `ω` là hạng tương đối đó. `λ = 0` nghĩa là
   cấu hình thắng trong mẫu rơi đúng trung vị ngoài mẫu.
6. **PBO = xác suất `λ < 0`** — xác suất cấu hình tối ưu trong mẫu lại dưới
   trung bình ngoài mẫu.

Ưu điểm so với một đường walk-forward: nó dùng _phân phối_ của hạng ngoài mẫu
trên hàng nghìn cách chia, nên không lặp lại được cho tới khi ra dương tính giả.

**Trạng thái dự án:** `research/validation/overfitting_stats.py` đã có hàm
`probability_of_backtest_overfitting`. Cần kiểm nó có cài đúng CSCV không.

## 8. Nghịch lý Sisyphus — [A] tr. 4-5

> "let us hire 50 PhDs and demand that each of them produce an investment
> strategy within six months. This approach always backfires, because each PhD
> will frantically search for investment opportunities and eventually settle for
> (1) **a false positive that looks great in an overfit backtest** or (2)
> standard factor investing, which is an overcrowded strategy with a low Sharpe
> ratio, but at least has academic support."

Thay vào đó là **mô hình siêu-chiến-lược**: một _nhà máy nghiên cứu_ với các
trạm chuyên môn hoá, thay vì một người ôm cả dây chuyền.

> "**It takes almost as much effort to produce one true investment strategy as
> to produce a hundred**, and the complexities are overwhelming: data curation
> and processing, HPC infrastructure, software development, feature analysis,
> execution simulators, backtesting, etc."

Các trạm mà [A] tr. 6-9 liệt kê: người quản lý dữ liệu, nhà phân tích đặc trưng,
người xây chiến lược, người backtest, đội triển khai, quản lý danh mục.

**Áp dụng — chẩn đoán có nguồn cho đúng hiện tượng người dùng đã quan sát.** Mỗi
phiên nghiên cứu ở đây là một tác nhân chạy toàn bộ dây chuyền dưới áp lực phải
ra chiến lược, và kết cục đúng như tài liệu mô tả: dương tính giả trong một
backtest overfit.

Cách chữa theo tài liệu không phải "cố gắng hơn" hay "quét nhiều hơn", mà là
**tách trạm**: xác định đặc trưng và tầm quan trọng của chúng trước, độc lập với
backtest; backtest chỉ là trạm cuối để loại bỏ.

## 9. Việc phải làm

| #   | việc                                                                          | mức ưu tiên | căn cứ                                            |
| --- | ----------------------------------------------------------------------------- | ----------- | ------------------------------------------------- |
| 1   | Dùng 8 symbol còn lại làm **kiểm chứng ngoài mẫu** (vẫn chỉ giao dịch XAU)    | cao         | [B] tr. 154 khuyến nghị 1, có ghi chú giới hạn §5 |
| 2   | Lập **sổ ghi mọi backtest** đã chạy, để tính PBO và giảm phát Sharpe          | rất cao     | [B] tr. 154 khuyến nghị 4                         |
| 3   | Dừng dùng backtest làm công cụ tìm kiếm; chuyển sang tầm quan trọng đặc trưng | rất cao     | [B] tr. 153                                       |
| 4   | Kiểm `probability_of_backtest_overfitting` có đúng CSCV không                 | cao         | [D] §7                                            |
| 5   | Thay dev/holdout một đường bằng **CV tổ hợp có thanh trừng**                  | cao         | [B] tr. 155                                       |
| 6   | Mô phỏng kịch bản, không chỉ một đường lịch sử                                | trung bình  | [B] tr. 154 khuyến nghị 5                         |
| 7   | Thử bagging như phép kiểm overfit                                             | trung bình  | [B] tr. 154 khuyến nghị 2                         |
