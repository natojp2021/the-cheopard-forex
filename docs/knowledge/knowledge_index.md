# Knowledge Index — Knowledge Anchor của dự án

Đây là nguồn tri thức **ưu tiên cao nhất** khi thiết kế và tối ưu hệ thống.
Khi tài liệu mâu thuẫn với source code hoặc với một quyết định cũ, tài liệu
thắng.

## Thứ tự ưu tiên nguồn tri thức

1. Sách và tài liệu nghiên cứu trong `D:\project-learning\documents`
2. Paper học thuật uy tín được cung cấp
3. Tài liệu đặc tả của dự án (`docs/research/specs/`)
4. Source code hiện tại
5. Suy luận của AI — thấp nhất, và phải ghi rõ là suy luận

## Bản đồ chủ đề

| file                                                           | trạng thái  | nguồn chính đã đọc                        |
| -------------------------------------------------------------- | ----------- | ----------------------------------------- |
| [trading_principles.md](trading_principles.md)                 | vòng 1 xong | Aronson ch.7                              |
| [statistical_validation.md](statistical_validation.md)         | vòng 1 xong | Aronson ch.6                              |
| [psychology.md](psychology.md)                                 | vòng 1 xong | Aronson ch.2                              |
| [backtesting.md](backtesting.md)                               | vòng 1 xong | Aronson ch.8-9; AFML ch.11; Wright ch.2   |
| [research_process.md](research_process.md)                     | vòng 1 xong | AFML ch.1, ch.11                          |
| [risk_management.md](risk_management.md)                       | vòng 1 xong | AFML ch.15, ch.10; Kelly                  |
| [trend_following.md](trend_following.md)                       | vòng 1 xong | Chan ch.6                                 |
| [market_structure.md](market_structure.md)                     | chờ         |                                           |
| [position_management.md](position_management.md)               | vòng 1 xong | Chan ch.8                                 |
| [machine_learning.md](machine_learning.md)                     | vòng 1 xong | AFML ch.3, ch.7                           |
| [component_provenance_audit.md](component_provenance_audit.md) | vòng 1 xong | **bảng truy vết nguồn gốc 37 thành phần** |

## Kho tài liệu và tiến độ đọc

Nguồn: `D:\project-learning\documents`. Bản `.md` do người dùng chuyển từ PDF —
là OCR thô, không có tiêu đề markdown; định vị chương bằng header chạy trang.
Chỗ nào OCR hỏng thì đối chiếu PDF gốc và ghi chú lại.

### Ưu tiên 1 — phương pháp luận và định lượng

| tài liệu                                                                      | tiến độ                                                     |
| ----------------------------------------------------------------------------- | ----------------------------------------------------------- |
| Aronson, D. (2007) _Evidence-Based Technical Analysis_                        | ch.2, 6, 8, 9 XONG · ch.7 XONG (3/4) · còn ch.1, 3, 4, 5    |
| López de Prado, M. (2018) _Advances in Financial Machine Learning_            | ch.1, 3, 7, 11, 15 XONG · còn ch.2, 4-6, 8-10, 12-14, 16-22 |
| Chan, E. (2013) _Algorithmic Trading: Winning Strategies and Their Rationale_ | ch.6, 8 XONG · còn ch.1-5, 7                                |
| Wright, K. (2013) _Building Reliable Trading Systems_                         | ch.2 XONG · còn ch.1, 3-16                                  |
| _Successful Algorithmic Trading_                                              | chờ                                                         |
| 9 paper pairs-trading / stat-arb (EECS545)                                    | chờ                                                         |

### Ưu tiên 2 — thực hành giao dịch

| tài liệu                                                        | tiến độ |
| --------------------------------------------------------------- | ------- |
| Elder, A. (2002) _Come Into My Trading Room_                    | chờ     |
| Coulling, A. (2013) _A Complete Guide To Volume Price Analysis_ | chờ     |
| Grimes, A. (2011) _Attacking Currency Trends_                   | chờ     |
| Bulkowski, T. (2005) _Encyclopedia of Chart Patterns_           | chờ     |
| Nison, S. (1994) _Beyond Candlesticks_                          | chờ     |
| Lien, K. _Day Trading and Swing Trading the Currency Market_    | chờ     |
| _Forex Patterns and Probabilities_ (2007)                       | chờ     |
| _High Probability Trading Strategies_ (2008)                    | chờ     |

### Ưu tiên 3 — bối cảnh, tâm lý, phản biện

| tài liệu                                     | tiến độ |
| -------------------------------------------- | ------- |
| Taleb, N. (2005) _Fooled by Randomness_      | chờ     |
| Malkiel, B. _A Random Walk Down Wall Street_ | chờ     |
| Mackay, C. _Extraordinary Popular Delusions_ | chờ     |

### Không ưu tiên

Các cuốn "For Dummies", sách kể chuyện (_Boomerang_, _Adventures of a Currency
Trader_, _Buffett_), sách về crypto và cổ phiếu giá trị — không liên quan tới
XAUUSD giao dịch thuật toán. Quét nhanh tìm ý lạ, không đọc kỹ.

## Nguyên tắc ghi chép

1. Trích **nguyên văn** đoạn quan trọng kèm số trang, để đối chiếu được bản gốc.
2. Phân biệt rõ: đâu là nguyên lý của tác giả, đâu là suy luận áp dụng của ta.
3. Mỗi nguyên lý kết thúc bằng mục **"áp dụng vào đâu"**. Không áp được thì
   không ghi.
4. Khi tài liệu mâu thuẫn với code hoặc quyết định cũ → ghi rõ mâu thuẫn, ưu
   tiên tài liệu.
5. Không tự bổ sung kiến thức tài liệu chưa đề cập. Nếu buộc phải suy luận thì
   đánh dấu **[suy luận của ta]**.

## Nhật ký mâu thuẫn tài liệu ↔ hệ thống

Bảng này là đầu ra chính của toàn bộ việc đọc — nơi ghi mọi chỗ hệ thống đi lệch
khỏi tài liệu, và đã xử lý ra sao.

| #   | thành phần trong hệ thống                                                                  | mâu thuẫn với                                                                                                                                                  | nguồn                                           | xử lý                                                                |
| --- | ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- | -------------------------------------------------------------------- |
| 1   | `shared/regime/states9.py` — 9 trạng thái theo hình dạng giá                               | trục có cơ sở là CHẾ ĐỘ PHẢN HỒI (dương → xu hướng, âm → hồi quy)                                                                                              | Aronson ch.7 tr.369                             | chưa xử lý — xem `trading_principles.md` §1                          |
| 2   | đối chứng ngẫu nhiên trong `scratch/` chỉ so luật thắng với MỘT luật ngẫu nhiên            | phân phối đúng là của CỰC ĐẠI trên N luật                                                                                                                      | Aronson ch.6 tr.275-277                         | ĐÃ SỬA — `research/validation/reality_check.py`                      |
| 3   | `downtrend-evidence-2026-08-03.md` giải thích thất bại holdout bằng "holdout nghèo cơ hội" | giả thuyết đặc biệt sau sự việc; giải thích mặc định phải là sai lệch khai thác dữ liệu                                                                        | Aronson ch.6 tr.262-264, ch.7 tr.354-355        | chưa sửa tài liệu                                                    |
| 4   | 7 trục trong `states9.py` — 4 trục tự nghĩ, chưa chứng minh giá trị dự báo                 | không được tự bổ sung kiến thức ngoài tài liệu                                                                                                                 | —                                               | đã đính chính trong `Q&A-system.md`                                  |
| 5   | backtest tính lợi suất trên giá GỐC (có drift)                                             | phải tính trên dữ liệu ĐÃ KHỬ XU HƯỚNG để loại méo do thiên lệch một chiều                                                                                     | Aronson ch.9 tr.448                             | chưa làm — đây là gốc của "long-bias artifact" đã vấp 3 lần          |
| 6   | danh mục champion là kết quả sống sót qua hàng chục vòng nghiên cứu                        | thiên lệch dò dẫm nghiên cứu trước: không đếm được số luật đã thử → mọi p-value không diễn giải được                                                           | Aronson ch.9 tr.449                             | chưa ghi nhận công khai                                              |
| 7   | toàn bộ nghiên cứu chỉ quét luật ĐƠN                                                       | 82% luật đạt ý nghĩa là luật PHỨC HỢP (Hsu & Kuan, 39.832 luật)                                                                                                | Aronson ch.9 tr.450                             | chưa chuyển hướng                                                    |
| 8   | `DonchianH4Breakout` có bộ lọc "nén biến động" `atr < atr_ma`                              | kênh giá đã tự co giãn theo biến động — bộ lọc thừa về lý thuyết                                                                                               | Aronson ch.8 tr.398                             | quét 03/08 xác nhận: bỏ lọc thì R/năm tăng                           |
| 9   | backtest dùng làm CÔNG CỤ TÌM KIẾM — 90 lần trong một ngày                                 | _"Do not research under the influence of a backtest"_; backtest chỉ để LOẠI BỎ                                                                                 | AFML ch.11 tr.153-154                           | chưa đổi quy trình                                                   |
| 10  | KIỂM CHỨNG chỉ trên XAUUSD dù kho có 9 symbol                                              | dùng symbol khác làm kiểm chứng ngoài mẫu (KHÔNG giao dịch chúng)                                                                                              | AFML ch.11 tr.154                               | chưa làm — nhưng xem ghi chú giới hạn trong `research_process.md` §5 |
| 11  | tầng rủi ro chỉ đo rủi ro DANH MỤC (xuyên sàn, DD)                                         | thiếu rủi ro CHIẾN LƯỢC = P[p < p\*]                                                                                                                           | AFML ch.15 tr.216                               | chưa cài; biên an toàn đã đo — `PaPullbackH4` mỏng nhất +0,083       |
| 12  | xếp hạng cấu hình bằng R/năm                                                               | phải dùng θ theo công thức tần suất-độ chính xác, vì R/năm bỏ qua phương sai                                                                                   | AFML ch.15 tr.213                               | chưa đổi                                                             |
| 13  | `meta_label` kết luận "âm tính" (23/07)                                                    | cần kiểm bản cài có đúng cấu trúc không: nhãn `{0,1}` theo lãi/lỗ, ba rào khớp hạn giữ thật, xác suất dùng để ĐỊNH CỠ chứ không chỉ chặn                       | AFML ch.3 tr.50-53                              | chưa kiểm                                                            |
| 14  | chưa từng chạy phép chẩn đoán rò rỉ (tăng k xem hiệu suất có tăng vô hạn)                  | phép kiểm rẻ và mạnh, phát hiện rò rỉ nhãn chồng lấn                                                                                                           | AFML ch.7 tr.106                                | chưa chạy                                                            |
| 25  | không có trần rủi ro theo NHÓM thị trường                                                  | _"foreign currencies usually trend in the same direction against the U.S. dollar"_; Murphy đặt trần nhóm 20-25% tổng vốn                                       | Murphy ch.16 tr.396                             | cần ngay khi bật forex                                               |
| 26  | cổng chặn dựa trên đánh giá LLM                                                            | bỏ qua tín hiệu chỉ hợp lệ khi dựa trên tiêu chí KỸ THUẬT ĐỘC LẬP định nghĩa trước, không phải phán đoán tình huống                                            | Pring ch.29 tr.539                              | chưa kiểm                                                            |
| 27  | SimBroker chỉ mô phỏng spread — chưa có trượt giá, từ chối lệnh, thị trường đóng cửa       | _"back-testing will not necessarily simulate what actually would have happened"_                                                                               | Pring ch.29 tr.541 · Chan ch.8 tr.182           | chưa làm                                                             |
| 28  | chưa có phép kiểm TÍNH GIÒN (luật không bao giờ kích hoạt)                                 | mất một ngày vì `SqueezeBreakdown` ra 0 lệnh bốn lần liên tiếp mà không test nào bắt được                                                                      | Kirkpatrick & Dahlquist ch.22 tr.549            | chưa làm                                                             |
| 29  | chỉ so HIỆU SUẤT giữa trong-mẫu và ngoài-mẫu                                               | phải so cả CẤU TRÚC: thời gian giữ TB, chuỗi thắng/thua dài nhất, lệnh thua tệ nhất — hiệu suất được phép giảm, cấu trúc thì không                             | Kirkpatrick & Dahlquist ch.22 tr.549            | chưa làm                                                             |
| 30  | chưa chạy phép kiểm nhất quán theo PHẦN MƯỜI                                               | chia mẫu thành 10 khúc cho 10 điểm quan sát thay vì 2; _"consistency of results"_ quan trọng hơn lợi nhuận tuyệt đối                                           | Kirkpatrick & Dahlquist ch.22 tr.547            | chưa chạy                                                            |
| 15  | kết luận "tăng tần suất 5,2 → 37,4 lệnh/năm"                                               | _"rebalance every day doesn't make the trading signals more independent"_ — phải đo ĐỘ ĐỘC LẬP trước, vì θ ∝ √n chỉ đúng với lệnh độc lập                      | Chan ch.6 tr.151                                | chưa đo                                                              |
| 16  | Monte Carlo bootstrap từ lịch sử đã quan sát                                               | thiếu kịch bản **momentum sụp đổ nhiều năm sau khủng hoảng** — sau 1929 một chiến lược momentum mất >30 năm mới về đỉnh cũ                                     | Daniel & Moskowitz (2011) dẫn trong Chan tr.151 | chưa có                                                              |
| 17  | `PaPullbackH4` có hard TP 2R                                                               | Chan gọi việc áp trần lợi nhuận cho chiến lược momentum là _"ill-advised"_; số liệu biên an toàn của dự án khớp — hai chiến lược KHÔNG TP có biên cao nhất     | Chan ch.6 tr.153                                | chưa xử lý                                                           |
| 19  | CPPI (sizing theo đệm) áp cho tài khoản BỐN chiến lược                                     | _"this scheme should only be applied to an account with one strategy only"_ — chiến lược lãi TRỢ CẤP chiến lược lỗ nên cơ chế ngừng-chiến-lược-thua bị vô hiệu | Chan ch.8 tr.182                                | chưa kiểm                                                            |
| 20  | `k = 0,10` đặt tay, chưa từng so với Kelly                                                 | Kelly là CẬN TRÊN; nếu `k` thấp hơn nhiều nửa-Kelly thì bỏ lỡ tăng trưởng mà không đổi lại được an toàn (an toàn do cấu trúc CPPI đảm bảo, không do `k` nhỏ)   | Chan ch.8 tr.172                                | chưa tính                                                            |
| 21  | chia vốn đều cho 4 chiến lược dưới trần 0,50%                                              | khi trần THẤP HƠN NHIỀU so với Kelly, dồn vào chiến lược mạnh nhất thường tối ưu hơn (ví dụ 8.2: g 0,96 so với 0,82)                                           | Chan ch.8 tr.174-175                            | chưa so                                                              |
| 18  | chọn tham số Donchian bằng quét BACKTEST                                                   | Chan cho cách hợp lệ: lưới tương quan lookback-holding trên dữ liệu KHÔNG chồng lấn, tính TRƯỚC backtest                                                       | Chan ch.6 tr.135-137                            | chưa làm — đây là lối thoát cụ thể khỏi vòng lặp                     |
