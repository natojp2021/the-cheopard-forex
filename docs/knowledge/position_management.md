# KB — Đòn bẩy, cỡ lệnh và bảo hiểm danh mục

## References

| #   | nguồn                                                                                    | chương / trang                       | nguyên lý lấy ra                                                 |
| --- | ---------------------------------------------------------------------------------------- | ------------------------------------ | ---------------------------------------------------------------- |
| [A] | Chan, E.P. (2013). _Algorithmic Trading: Winning Strategies and Their Rationale_. Wiley. | Ch. 8 "Risk Management", tr. 169-186 | đòn bẩy tối ưu; Kelly; CPPI; cắt lỗ                              |
| [B] | Thorp, E. (1997) — trình bày công thức Kelly                                             | dẫn trong [A] tr. 172                | `f = m/s²`                                                       |
| [C] | Kahneman, D. (2011)                                                                      | dẫn trong [A] tr. 169                | người ta cần tiềm năng lãi $2 để bù rủi ro mất $1                |
| [D] | Khandani, A. & Lo, A. (2007)                                                             | dẫn trong [A] tr. 171                | "bán vào lúc lỗ" gây lây lan trong sụp đổ quỹ định lượng 08/2007 |

---

## 1. Mục tiêu đúng: tối đa tăng trưởng dài hạn, không phải tránh lỗ — [A] tr. 169

> "To novice traders, risk management is driven by 'loss aversion': we simply
> don't like the feeling of losing money. In fact, research has suggested that the
> average human being needs to have the potential for making \$2 to compensate for
> the risk of losing \$1, **which may explain why a Sharpe ratio of 2 is so
> emotionally appealing** (Kahneman, 2011). However, **this dislike of risk in
> itself is not rational.** Our goal should be the maximization of long-term
> equity growth, and we avoid risk only insofar as it interferes with this goal."

**Áp dụng — nhưng có ngoại lệ quan trọng cho dự án.** Với tài khoản FTMO, xuyên
sàn **không phải** một khoản lỗ có thể phục hồi; nó chấm dứt tài khoản. Nên
"tránh rủi ro chỉ khi nó cản trở tăng trưởng" không áp dụng nguyên vẹn: ở đây
tránh xuyên sàn LÀ điều kiện tiên quyết để có tăng trưởng.

## 2. Công thức Kelly và ba giả định — [A] tr. 170-172

```
f = m / s²        m = lợi suất vượt trội trung bình,  s² = phương sai
```

Chan xếp ba giả định theo mức độ ràng buộc tăng dần ([A] tr. 170):

1. phân phối lợi suất **thị trường** tương lai giống quá khứ;
2. phân phối lợi suất **của chính chiến lược** giống quá khứ;
3. phân phối ấy là **Gaussian** — ràng buộc nhất, và cho lời giải đẹp nhất.

### Sai số ước lượng có hậu quả BẤT ĐỐI XỨNG — [A] tr. 172

> "The consequence of using an overestimated mean or an underestimated variance
> is dire: Either case will lead to an overestimated optimal leverage, and if this
> overestimated leverage is high enough, **it will eventually lead to ruin**...
> However, the consequence of using an **underestimated** leverage is merely a
> submaximal compounded growth rate."

Vì vậy thông lệ là **nửa-Kelly**.

### Kelly là CẬN TRÊN, không phải mức phải dùng — [A] tr. 172

> "My actual experience using Kelly's optimal leverage is that **it is best viewed
> as an upper bound rather than as the leverage that must be used.** Often, the
> Kelly leverage given by the backtest is so high that it far exceeds the maximum
> leverage allowed by our brokers. At other times, **the Kelly leverage would have
> bankrupted us even in backtest**, due to the non-Gaussian distributions of
> returns."

## 3. CPPI — và đây CHÍNH LÀ công thức sizing của dự án

### Định nghĩa — [A] tr. 180

Với đòn bẩy Kelly `f` và mức sụt vốn tối đa cho phép `D`:

- tách `D` phần vốn ra làm **tài khoản con giao dịch**, áp đòn bẩy `f` lên nó;
- `1 − D` còn lại nằm tiền mặt;
- chạm đỉnh vốn mới → **nạp lại** tài khoản con về đúng `D` của tổng vốn;
- đang lỗ → **KHÔNG** chuyển thêm tiền vào.

> "in addition to limiting our drawdown, **this scheme serves as a graceful,
> principled way to wind down a losing strategy.** (The more common, less optimal,
> way to wind down a strategy is driven by the emotional breakdown of the
> portfolio manager.)"

### Vì sao nó KHÁC với việc chỉ hạ đòn bẩy xuống `f·D` — [A] tr. 181

> "**As long as we have a drawdown, CPPI will decrease order size much faster than
> the alternative**, thus making it almost impossible... that the account would
> approach the maximum drawdown −D."

Số liệu mô phỏng 100.000 ngày với `D = 0,5` ([A] tr. 181):

|                                      | tốc độ tăng trưởng / ngày |          sụt vốn tối đa |
| ------------------------------------ | ------------------------: | ----------------------: |
| CPPI                                 |                  0,002484 | **< 0,5** theo thiết kế |
| hạ đòn bẩy xuống `f·D`, không cắt lỗ |                  0,002525 |                 **0,9** |

Tức **gần như cùng tốc độ tăng trưởng, nhưng sụt vốn bằng một nửa**.

### Đối chiếu: dự án đã cài CPPI mà chưa gọi tên

Công thức sizing hiện tại:

```
risk = k × min(equity − sàn_tổng, equity − sàn_ngày),  kẹp bởi trần mỗi lệnh
```

`equity − sàn` chính là **đệm** (cushion) trong ngôn ngữ CPPI, và `k` là **hệ số
nhân**. Đây đúng là CPPI, với hai khác biệt so với bản của Chan:

|            | Chan                                 | dự án                                |
| ---------- | ------------------------------------ | ------------------------------------ |
| đệm        | `D` × vốn, nạp lại khi chạm đỉnh mới | khoảng cách tới **sàn tĩnh** FTMO    |
| hệ số nhân | Kelly `f`                            | `k = 0,10` đặt tay                   |
| trần       | đòn bẩy môi giới                     | `RISK_ABSOLUTE_MAX = 0,50%` mỗi lệnh |

Sàn FTMO là **tĩnh** và không nạp lại, nên đệm chỉ nở ra khi có lãi — nghiêm ngặt
hơn bản của Chan. Điều này giải thích vì sao Monte Carlo cho `P(cháy) = 0%` ở mọi
`k` từ 0,05 tới 0,30: cấu trúc CPPI làm cỡ lệnh co về 0 khi đệm co về 0.

**Giá trị của việc gọi đúng tên:** giờ có thể so `k = 0,10` với Kelly. Nếu `k`
thấp hơn nhiều so với nửa-Kelly thì đang bỏ lỡ tăng trưởng mà không đổi lại được
gì về an toàn — vì an toàn đã do cấu trúc CPPI đảm bảo, không phải do `k` nhỏ.

### CẢNH BÁO: CPPI chỉ dành cho tài khoản MỘT chiến lược — [A] tr. 182

> "**Note that this scheme should only be applied to an account with one strategy
> only.** If it is a multistrategy account, it is quite possible that the
> profitable strategies are '**subsidizing**' the nonprofitable ones such that the
> drawdown is never large enough to shut down the complete slate of strategies.
> This is obviously not an ideal situation unless you think that the losing
> strategy will somehow return to health at some point."

**Dự án chạy BỐN chiến lược trên MỘT tài khoản với đệm dùng chung.** Đây đúng
tình huống Chan cảnh báo: cơ chế "ngừng chiến lược thua một cách có nguyên tắc"
bị vô hiệu, vì đệm chung không bao giờ co đủ để tắt chiến lược nào cả.

→ Việc phải làm: theo dõi đệm **theo từng chiến lược**, không chỉ theo tài khoản.
Dự án đã có `operational_health` và `allocation_policy` — cần kiểm xem chúng có
thực hiện đúng vai trò này không.

### Giới hạn chung với cắt lỗ — [A] tr. 182

> "It can't prevent a big drawdown from occurring **during the overnight gap** or
> whenever trading in a market has been suspended."

Vàng có khoảng trống cuối tuần. SL không bảo vệ qua đó.

## 4. Phân bổ vốn giữa nhiều chiến lược — [A] tr. 173-175

Công thức Kelly nhiều chiến lược: `F = C⁻¹M` (nghịch đảo ma trận hiệp phương sai
nhân véc-tơ lợi suất vượt trội trung bình).

### Phát hiện quan trọng khi có TRẦN đòn bẩy — [A] ví dụ 8.2, tr. 174-175

Hai chiến lược, lợi suất/biến động lần lượt 30%/26% và 60%/35%, không tương quan.
Kelly cho `F = [4,4 ; 4,9]`, tổng gộp 9,3. Nhưng môi giới chỉ cho tối đa 2.

| cách phân bổ                                        | tốc độ tăng trưởng `g` |
| --------------------------------------------------- | ---------------------: |
| chia tỉ lệ theo Kelly → `[0,95 ; 1,05]`             |                   0,82 |
| **dồn toàn bộ vào chiến lược tốt nhất** → `[0 ; 2]` |               **0,96** |

> "when we have two or more strategies with very different independent growth
> rates, and when we have a **maximum leverage constraint that is much lower than
> the Kelly leverage**, it is often optimal to just apply all of our buying power
> on the strategy that has the highest growth rate."

**Áp dụng trực tiếp — và nó mâu thuẫn với thiết kế danh mục hiện tại.** Dự án có
trần cứng (0,50%/lệnh) thấp hơn nhiều so với Kelly, và bốn chiến lược có tốc độ
tăng trưởng khác nhau rõ rệt (biên an toàn từ +0,083 tới +0,195, xem
`risk_management.md` §3).

Theo [A] ví dụ 8.2, trong tình huống này **chia đều vốn cho bốn chiến lược có
thể kém hơn dồn vào chiến lược mạnh nhất**. Chưa từng kiểm.

Lưu ý phản biện: ví dụ của Chan giả định hai chiến lược **không tương quan** và
biết chắc tốc độ tăng trưởng. Với bốn chiến lược cùng bám xu hướng trên cùng một
tài sản, tương quan cao và ước lượng tốc độ tăng trưởng có sai số lớn — hai điều
đều đẩy về phía đa dạng hoá. **[suy luận của ta]**

## 5. Cắt lỗ: hai cách dùng, một cách gây tranh cãi — [A] tr. 182-183

| cách dùng | mô tả                                                                | đánh giá của Chan                                                                       |
| --------- | -------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| phổ biến  | thoát một vị thế khi lỗ chưa thực hiện vượt ngưỡng; được vào lại sau | dùng được                                                                               |
| ít gặp    | thoát HẲN chiến lược khi sụt vốn vượt ngưỡng                         | "awkward" — chỉ xảy ra một lần trong đời chiến lược; **CPPI tốt hơn cho cùng mục đích** |

Và về hồi quy trung bình, [A] tr. 183:

> "**I have never backtested any mean-reverting strategy whose APR or Sharpe ratio
> is increased by imposing a stop loss.**"

Trùng với kết luận ở `trend_following.md` §4.1 — SL nhất quán với momentum, mâu
thuẫn với hồi quy trung bình.

## 6. Yêu cầu đòn bẩy KHÔNG ĐỔI, và cái giá xã hội của nó — [A] tr. 170-171

> "the one central theme is that **the leverage should be kept constant.** This is
> necessary to optimize the growth rate whether or not we have the maximum
> drawdown constraint."

Ví dụ 8.1: vốn 100 nghìn, đòn bẩy 5 → vị thế 500 nghìn. Mất 10 nghìn → vốn 90
nghìn, vị thế còn 490 nghìn → phải **thanh lý thêm 40 nghìn** để về 450 nghìn.

> "Many analysts believe that this 'selling into losses' feature of the risk
> management techniques causes contagion in financial crises. (In particular, this
> was cited as a cause of the August 2007 meltdown of quant funds; see Khandani
> and Lo, 2007)... **self-preservation ('risk management') for one fund can lead
> to catastrophe for all.**"

## 7. Việc phải làm

| #   | việc                                                                                                                                             | mức ưu tiên | căn cứ        |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ----------- | ------------- |
| 1   | Tính **Kelly `f = m/s²`** cho từng chiến lược và so với `k = 0,10` hiện tại — nếu `k` thấp hơn nhiều nửa-Kelly thì đang bỏ lỡ tăng trưởng vô ích | cao         | [A] tr. 172   |
| 2   | Kiểm cơ chế "ngừng chiến lược thua" theo TỪNG chiến lược — CPPI trên tài khoản đa chiến lược bị vô hiệu do trợ cấp chéo                          | cao         | [A] tr. 182   |
| 3   | So sánh **chia đều vốn** với **dồn vào chiến lược mạnh nhất** dưới trần 0,50%                                                                    | trung bình  | [A] ví dụ 8.2 |
| 4   | Ghi nhận trong tài liệu rằng sizing hiện tại LÀ CPPI, có tên và có tài liệu                                                                      | thấp        | [A] tr. 180   |

---

# Phần II — Van Tharp, _Trade Your Way to Financial Freedom_ (2nd ed. 2006)

## References bổ sung

| #   | nguồn                                                                           | chương / trang                                          | nguyên lý lấy ra                                                                                        |
| --- | ------------------------------------------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| [E] | Tharp, V.K. (2006). _Trade Your Way to Financial Freedom_, 2nd ed. McGraw-Hill. | Ch. 12 "What Do You Mean Position Sizing?", tr. 282-310 | định nghĩa định cỡ vị thế; bảng hồi phục sụt vốn; mô hình % biến động; quét tham số trên hệ thống 55/21 |
| [F] | Tharp (2006)                                                                    | Ch. 4 tr. 74-76; Ch. 6                                  | định nghĩa kỳ vọng toán; bội số R; phân tích cấu thành kỳ vọng                                          |
| [G] | Vince, R. — thí nghiệm 40 tiến sĩ chơi trò có kỳ vọng dương                     | dẫn trong [E] ch. 2 và tr. 283                          | 95% thua tiền dù kỳ vọng dương                                                                          |

**Lưu ý về chất lượng nguồn:** bản `.md` của cuốn này là OCR hai cột bị trộn.
Các con số trong cột đô-la của bảng 12-6 bị lỗi ký tự ở vài dòng; hai cột
**% lợi nhuận/năm** và **% sụt vốn tối đa** thì đọc được sạch, và chỉ hai cột ấy
được trích ở đây.

---

## 18. Định nghĩa kỳ vọng toán — [F] tr. 74

> "**Expectancy is the average amount of money you will make in your system over
> many, many trades — per dollar risked.**"

Đây đúng là **R trung bình mỗi lệnh** mà dự án đang dùng. Thuật ngữ khớp, định
nghĩa khớp — không cần đổi gì.

Hai hệ quả Tharp rút ra mà dự án chưa khai thác:

**(a) Kỳ vọng do THOÁT LỆNH quyết định** ([F] tr. 74):

> "expectancy is controlled by your **exits**. Thus, the best systems have three
> or four different exits."

Bốn chiến lược LIVE có một hoặc hai lối thoát (SL + hạn giữ, hoặc SL + TP).
Tharp nói hệ thống tốt nhất có ba tới bốn. **[chưa kiểm — ghi nhận, không áp
dụng cho tới khi có phép đo]**

**(b) Phải mổ xẻ CẤU THÀNH của kỳ vọng** ([F] tr. 75):

> "look at your system results trade by trade. What is the makeup of the
> expectancy? Is it mostly made up of a lot of 1:1- or 2:1-reward-to-risk ratio
> trades? **Or do you find that one or two really big trades make up most of the
> expectancy?**"

Dự án đã làm đúng phép này một lần — với `SqueezeBreakdown`, phát hiện ba năm
tốt nhất chiếm 138% tổng lợi nhuận, và đó là một trong các căn cứ bác bỏ. Tharp
xác nhận đây là phép chẩn đoán tiêu chuẩn, không phải sáng kiến riêng.

Nhưng lưu ý Tharp diễn giải theo **hướng ngược lại** cho hệ thống dài hạn
([F] tr. 75):

> "If it is long term and you **do not have enough contribution from big
> trades**, then you probably need to modify your exits so that you can capture
> some of those big trades."

Tức với chiến lược bám xu hướng, việc lợi nhuận tập trung vào ít lệnh lớn là
**đặc điểm mong muốn**, không phải khuyết điểm. Điều làm `SqueezeBreakdown` bị
bác bỏ không phải sự tập trung ấy, mà là LCB95 âm cộng với nửa sau mẫu âm.

Cần phân biệt hai thứ khi dùng phép chẩn đoán này:

- tập trung vào ít **lệnh** lớn → bình thường với bám xu hướng;
- tập trung vào ít **giai đoạn** lịch sử → dấu hiệu chiến lược chỉ chạy trong
  một chế độ thị trường không lặp lại.

## 19. Bội số R và hình dạng phân phối lợi nhuận — [F] tr. 75-76

> "one 10-R trade can be profitable with as many as **7 1-R losses** — even when
> you take transaction costs into consideration."

Ví dụ Tharp nêu: vào lệnh ba lần trong giai đoạn tích luỹ, mỗi lần dừng lỗ 0,75
đô; lần thứ tư lãi 10 đô, tức **12,5R**. Tổng: +10 − 2,25 = +7,75, gấp hơn ba
lần tổng lỗ. Tỉ lệ thắng 25%.

> "Most people would hate it because they are 'wrong' too many times."

**Đối chiếu:** bốn chiến lược LIVE có tỉ lệ thắng 0,459-0,507 và lãi trung bình
+1,41R tới +2,04R — tức nằm ở vùng "1:1 tới 2:1" mà Tharp nói, KHÔNG phải vùng
bội số R lớn. Đây là một mô tả khách quan về danh mục, chưa phải phán xét.

## 20. Bảng hồi phục sụt vốn — [E] bảng 12-1, tr. 284

| sụt vốn | mức lãi cần để về vốn |
| ------: | --------------------: |
|      5% |                  5,3% |
|     10% |                 11,1% |
|     15% |                 17,6% |
|     20% |                   25% |
|     25% |                   33% |
|     30% |                 42,9% |
|     40% |                 66,7% |
|     50% |                  100% |
|     60% |                  150% |
|     75% |                  300% |
|     90% |                  900% |

> "losses up to 20 percent only require a moderately larger gain (i.e., no more
> than 25 percent bigger) to get back to even. But a 40 percent drawdown..."

**Áp dụng cho FTMO:** trần sụt vốn 10% của FTMO nằm đúng trong vùng "hồi phục
vừa phải" — cần 11,1% để về vốn. Đây là lý do định lượng ủng hộ việc đặt trần
thấp, độc lập với luật của FTMO.

## 21. Thí nghiệm Ralph Vince — [G] dẫn trong [E] tr. 283

40 tiến sĩ chơi một trò chơi có **kỳ vọng dương**. Kết quả: **95% thua tiền.**

> "The reasons had to do with their psychology and with poor position sizing."

Cơ chế Tharp mô tả: sau ba lần thua liên tiếp, người chơi nghĩ "đã thua ba lần
rồi, chắc sắp thắng" — **ngộ nhận của con bạc**, vì xác suất thắng vẫn là 60% —
rồi tăng cược. Thua tiếp thì rơi vào vùng phải lãi 150% mới hoà.

Trùng khớp với Aronson ch.2 tr.361-362 về tội của số nhỏ (xem `psychology.md`
§3.2) — hai nguồn độc lập mô tả cùng một lỗi.

## 22. Ẩn dụ hòn tuyết — vì sao trần tuyệt đối là cần thiết — [E] tr. 283

> "if one black snowball that is bigger than the wall is thrown at the wall, then
> the wall will be destroyed. **It does not matter how favorable the ratio of
> white to black snow is** — one black snowball bigger than the wall will destroy
> the wall."

Đây là lập luận có nguồn cho `RISK_ABSOLUTE_MAX`: kỳ vọng dương không bảo vệ
được khỏi một lệnh đủ lớn. Trần tuyệt đối mỗi lệnh không phải sự thận trọng thừa
mà là điều kiện cần.

## 23. Mô hình 4: định cỡ theo PHẦN TRĂM BIẾN ĐỘNG — [E] tr. 298

Đây là mô hình khớp đúng cách dự án đang làm.

> "If you equate the volatility of each position that you take, by making it a
> **fixed percentage of your equity**, then you are basically equalizing the
> possible market fluctuations of each portfolio element."

Ví dụ Tharp nêu **trên chính vàng** ([E] tr. 298):

- vàng 400 đô/ounce, biên độ ngày 3 đô, hợp đồng 100 ounce → biến động
  **300 đô/hợp đồng**;
- cho phép biến động tối đa **2% vốn**; 2% của 50.000 đô = 1.000 đô;
- 1.000 / 300 = **3,3 hợp đồng** → mua 3.

Đo biến động bằng **trung bình động 10 ngày của average true range** (Wilder).

**Đối chiếu với dự án:** công thức sizing hiện tại quy rủi ro về khoảng cách SL
tính bằng ATR, tức cùng một họ mô hình. Khác biệt: dự án nhân thêm hệ số đệm
CPPI (Chan ch.8), còn Tharp dùng phần trăm vốn cố định.

## 24. Bảng 12-6 — quét tham số định cỡ trên hệ thống Donchian 55/21

Đây là bảng có giá trị nhất trong chương, và nó gần như **trùng khớp với
`SwingDon`** của dự án (Donchian 55/20).

Thiết lập: hệ thống phá vỡ 55/21, danh mục **10 hàng hoá**, **11 năm**, định cỡ
theo phần trăm biến động, biến động đo bằng trung bình động 20 ngày của ATR.
Chỉ đổi duy nhất thuật toán định cỡ giữa các dòng.

| % biến động cho phép | % lợi nhuận/năm |     sụt vốn tối đa |
| -------------------: | --------------: | -----------------: |
|                 0,10 |           3,30% |              6,10% |
|                 0,25 |           9,50% |             17,10% |
|                 0,50 |          20,30% |             30,60% |
|                 0,75 |          30,30% |             40,90% |
|                 1,00 |          40,00% |             49,50% |
|                 1,75 |          67,90% |             69,70% |
|                 2,50 |          86,10% |             85,50% |
|                 5,00 |          90,70% |             92,50% |
|             **7,50** |       **0,00%** | **119,80% — CHÁY** |

Ba điều đọc được:

**(a) Quan hệ lợi nhuận ↔ sụt vốn gần như một-một ở vùng trên.** Từ 1,00% trở
lên, mỗi điểm phần trăm lợi nhuận thêm phải trả bằng xấp xỉ một điểm sụt vốn.

**(b) Có điểm gãy.** Từ 5,00% lên 7,50%, lợi nhuận sụp từ 90,7%/năm xuống 0 và
sụt vốn vượt 100% — cháy tài khoản. Đây là hiện tượng Chan ch.8 tr.172 mô tả:
vượt Kelly thì rủi ro tăng mà tăng trưởng không tăng, rồi phá sản.

**(c) Ràng buộc FTMO chọn giúp ta mức tham số.** Trần sụt vốn tổng của FTMO là
10%. Chiếu vào bảng, mức ấy nằm giữa dòng 0,10% (sụt 6,1%) và dòng 0,25% (sụt
17,1%) — tức khoảng **0,15-0,20% biến động cho phép**, cho **khoảng 5-7%
lợi nhuận/năm**.

**Cảnh báo khi chuyển sang dự án — [suy luận của ta]:** bảng của Tharp là danh
mục **10 hàng hoá**, còn hệ thống chỉ giao dịch **một** symbol. Đa dạng hoá 10
thị trường làm giảm sụt vốn ở cùng mức rủi ro, nên với một symbol thì **cùng
một mức % sẽ cho sụt vốn LỚN HƠN** bảng này. Con số 0,15-0,20% vì thế là **cận
trên lạc quan**, không phải mục tiêu.

Dự án đang dùng trần 0,50% mỗi lệnh với `MAX_OPEN = 1` cho mỗi chiến lược — tức
rủi ro đồng thời tối đa khoảng 2% nếu cả bốn cùng mở. Bảng của Tharp gợi ý mức
ấy tương ứng vùng sụt vốn 30-50% **cho danh mục 10 thị trường**, và cao hơn nữa
cho một thị trường.

Nhưng ba điều khiến so sánh trực tiếp không hợp lệ, phải nói rõ:

1. dự án dùng CPPI theo đệm tới sàn, nên rủi ro **tự co** khi tới gần sàn — bảng
   của Tharp dùng phần trăm vốn cố định, không co;
2. bốn chiến lược của dự án là **mua/đứng-ngoài**, không phải đảo chiều liên tục;
3. Monte Carlo 4.000 đường đời của dự án cho `P(cháy) = 0%` ở mọi `k` từ 0,05
   tới 0,30 — mâu thuẫn biểu kiến với bảng này, và lời giải thích là điểm 1.

→ **Việc phải làm:** tái lập bảng 12-6 trên chính dữ liệu XAUUSD và chính công
thức CPPI của dự án, để có bảng đánh đổi lợi nhuận ↔ sụt vốn **của hệ thống này**
thay vì mượn của Tharp. Đây là phép đo thay thế đúng cho câu hỏi "tăng `k` được
không" mà `k = 0,10` hiện chưa có căn cứ.

## 25. Việc phải làm rút ra từ Van Tharp

| #   | việc                                                                                                                                          | mức ưu tiên                                            | căn cứ        |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ | ------------- |
| 17  | Tái lập bảng đánh đổi lợi nhuận ↔ sụt vốn theo mức rủi ro, trên dữ liệu XAUUSD và công thức CPPI của dự án                                    | **cao** — lấp trực tiếp lỗ hổng `k = 0,10` Unsupported | [E] bảng 12-6 |
| 18  | Phân biệt hai kiểu tập trung khi mổ xẻ kỳ vọng: tập trung theo LỆNH (bình thường với bám xu hướng) và tập trung theo GIAI ĐOẠN (dấu hiệu xấu) | trung bình                                             | [F] tr. 75    |
| 19  | Ghi nhận `RISK_ABSOLUTE_MAX` có căn cứ: ẩn dụ hòn tuyết — kỳ vọng dương không bảo vệ khỏi một lệnh đủ lớn                                     | thấp — chỉ ghi tài liệu                                | [E] tr. 283   |
| 20  | Xem xét thêm lối thoát thứ ba/thứ tư — Tharp nói hệ thống tốt nhất có 3-4 lối thoát. CHƯA kiểm, không áp dụng khi chưa đo                     | thấp                                                   | [F] tr. 74    |

---

# Phần III — Murphy, _Technical Analysis of the Financial Markets_ (1999)

## References bổ sung

| #   | nguồn                                                                                                                                                         | chương / trang                                             | nguyên lý lấy ra                                                                                             |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| [E] | Murphy, J.J. (1999). _Technical Analysis of the Financial Markets: A Comprehensive Guide to Trading Methods and Applications_. New York Institute of Finance. | Ch. 16 "Money Management and Trading Tactics", tr. 393-410 | ba yếu tố của giao dịch thành công; giới hạn phân bổ vốn; đa dạng hoá giả; tỉ lệ lãi-lỗ; nhiều đơn vị vị thế |

**Ghi chú nguồn:** bản `.md` này do người dùng OCR lại ngày 03/08 từ PDF quét
ảnh 585 trang (bản cũ trong kho là 0 KB). Chất lượng đọc được, có đánh dấu số
trang; vài chỗ OCR sót ký tự đã được bỏ qua khi trích.

---

## 8. Ba yếu tố của một chương trình giao dịch — [E] tr. 393-394

> "Any successful trading program must take into account three important factors:
> **price forecasting, timing, and money management.**"

| yếu tố                  | trả lời câu hỏi       | trạng thái dự án                           |
| ----------------------- | --------------------- | ------------------------------------------ |
| dự báo giá              | mua hay bán           | tín hiệu Donchian, có nguồn (Aronson ch.8) |
| chiến thuật / định thời | vào và ra ở đâu       | khớp lệnh thị trường tại nến đóng          |
| **quản lý vốn**         | **cam kết bao nhiêu** | CPPI theo đệm (Chan ch.8)                  |

> "Money management deals with the question of **survival.** It tells the trader
> how to handle his or her money. Any good trader should win in the long run.
> **Money management increases the odds that the trader will survive to reach
> the long run.**"

Trùng ý với Van Tharp ch.12 (định cỡ vị thế chiếm phần lớn biến thiên hiệu suất
giữa các nhà giao dịch chuyên nghiệp) — hai nguồn độc lập cùng xếp quản lý vốn
lên trên tín hiệu.

## 9. Bốn giới hạn phân bổ vốn — [E] tr. 395-396

Murphy ghi rõ đây là thông lệ ngành hợp đồng tương lai, có thể điều chỉnh:

| #   | giới hạn                                               | trên tài khoản 100.000 |
| --- | ------------------------------------------------------ | ---------------------- |
| 1   | tổng vốn đưa vào thị trường ≤ **50%** tổng vốn         | 50.000                 |
| 2   | cam kết vào **một thị trường** ≤ 10-15% tổng vốn       | 10.000-15.000          |
| 3   | **rủi ro** trên một thị trường ≤ **5%** tổng vốn       | 5.000                  |
| 4   | ký quỹ trong **một nhóm thị trường** ≤ 20-25% tổng vốn | 20.000-25.000          |

**Đối chiếu với dự án:** trần rủi ro mỗi lệnh 0,50% thấp hơn giới hạn 3 của
Murphy **mười lần**. Điều đó hợp lý vì FTMO có sàn tĩnh 10% còn Murphy viết cho
tài khoản tự doanh không có sàn cứng.

Giới hạn 4 — nhóm thị trường — là thứ dự án **chưa có** và sẽ cần ngay khi mở
rộng sang forex. Xem mục kế tiếp.

## 10. Đa dạng hoá GIẢ — và nó giải thích đúng kết quả đa thị trường ngày 03/08

Trích nguyên văn [E] tr. 396-397:

> "**Holding long positions in four foreign currency markets at the same time
> would not be a good example of diversification, since foreign currencies
> usually trend in the same direction against the U.S. dollar.**"

Và về nhóm thị trường ([E] tr. 396):

> "Markets within groups tend to move together. Gold [and silver] ... usually
> trend in the same direction. Putting on full positions in each market in the
> same group would frustrate the principle of diversification."

Cùng với cảnh báo ngược chiều ([E] tr. 396-397):

> "While diversification is one way to limit risk exposure, **it can be
> overdone.** If a trader has trading commitments in too many markets at the same
> time, a few profitable trades may be diluted by a larger number of losing
> trades."

### Vì sao đoạn này quan trọng với phép kiểm vừa chạy

Ngày 03/08 tôi áp `DonchianH4Breakout` sang 9 thị trường và báo "3/9 dương". Đọc
theo Murphy thì con số ấy **gây hiểu lầm**, vì chín thị trường không phải chín
phép thử độc lập:

| nhóm                  | thị trường                                     | kết quả          |
| --------------------- | ---------------------------------------------- | ---------------- |
| kim loại              | XAUUSD, XAGUSD                                 | cả hai **dương** |
| cặp rủi ro so với USD | AUDUSD, NZDUSD, GBPUSD, EURUSD, USDCAD, USDCHF | cả sáu **âm**    |
| yên Nhật              | USDJPY                                         | **dương**        |

Sáu thị trường âm về cơ bản là **một phép thử lặp lại sáu lần**, đúng như Murphy
mô tả năm 1999. Nên "3/9" thực chất gần với "2 trên 3 nhóm".

**Nhưng điều này KHÔNG cho phép đảo ngược phán quyết.** Hai lý do:

1. Tiêu chí "≥5/9" đã ghi TRƯỚC khi chạy. Đọc lại nó theo cách có lợi sau khi
   thấy kết quả là đúng thứ Aronson ch.7 tr.354-355 chỉ trích.
2. Quan trọng hơn: **phép kiểm White's Reality Check đã xử lý đúng vấn đề này
   rồi.** Nó dùng CÙNG một bộ mốc bootstrap cho cả chín chuỗi, nên cấu trúc
   tương quan giữa các thị trường được giữ nguyên (Aronson ch.6 tr.328). Kết quả
   p = 0,0338 với duy nhất XAUUSD sống sót đã tính đến việc sáu cặp USD là một
   nhóm.

Giá trị của Murphy ở đây là **giải thích cơ chế** đằng sau con số, và cho một
quy tắc thiết kế: nếu sau này chạy nhiều thị trường thì phải áp trần theo
**nhóm**, không chỉ theo từng thị trường.

## 11. Tỉ lệ lãi trên rủi ro — [E] tr. 397-398

> "**The best futures traders make money on only 40% of their trades.** That is
> right. Most trades wind up being losers."

> "A commonly used yardstick is a **3 to 1 reward-to-risk ratio.** The profit
> potential must be at least three times the possible loss if a trade is to be
> considered."

**Đối chiếu với bốn chiến lược LIVE:**

| chiến lược           | tỉ lệ thắng | lãi TB | tỉ lệ lãi/lỗ xấp xỉ |
| -------------------- | ----------: | -----: | ------------------: |
| `DonchianH4Breakout` |       45,9% | +2,04R |                ~2,0 |
| `SwingDon`           |       48,8% | +1,88R |                ~1,9 |
| `PaPullbackH4`       |       49,5% | +1,43R |                ~1,4 |
| `PaDonchianH4`       |       50,7% | +1,41R |                ~1,4 |

Cả bốn **dưới ngưỡng 3:1** của Murphy, nhưng **tỉ lệ thắng cao hơn** mức 40% ông
nêu. Hai thứ bù nhau — đây là mô tả khách quan, không phải khiếm khuyết. Điều
đáng ghi là danh mục nằm ở vùng "thắng thường xuyên, lãi vừa phải" chứ không ở
vùng "thắng ít, lãi lớn" mà Murphy và Van Tharp cùng mô tả là đặc trưng của bám
xu hướng dài hạn.

## 12. Nhiều đơn vị vị thế: phần "xu hướng" và phần "giao dịch" — [E] tr. 398-399

> "One way to resolve that problem is to always **trade in multiple units.** Those
> units can be divided into **trading and trending positions.** The trending
> portion of the position is held for the long [pull]... These are the positions
> that produce the largest profits in the long run. The trading portion of the
> portfolio is earmarked for shorter term in-and-out trading."

> "**It is best to avoid trading only one unit at a time.** The increased
> flexibility that is achieved from trading multiple units makes a big difference
> in overall trading results."

**Mâu thuẫn với thiết kế hiện tại:** mọi chiến lược đặt `MAX_OPEN = 1`, tức đúng
một đơn vị mỗi lần.

Nhưng dự án đã **cân nhắc và bác bỏ** hướng này một lần: nhật ký 15/07 ghi pivot
từ xé lệnh sang "một lệnh, TP 3R, hoà vốn tại 1R, trail ATR, nhồi khi đã miễn
rủi ro". Đó là quyết định có cơ sở thực nghiệm riêng.

Ghi nhận mâu thuẫn, **không tự đảo ngược**. Nếu mở lại thì phải là một phép kiểm
có ghi tiêu chí trước, không phải vì đọc được một câu trong sách.

## 13. Đặt dừng lỗ — [E] tr. 397

> "The trader must consider the **volatility of the market. The more volatile the
> market is, the looser the stop that must be employed.**... Protective stops
> placed too close may result in unwanted liquidation on short term market swings
> (or 'noise'). Protective stops placed too far away may avoid the noise factor,
> but will result in larger losses."

Đây chính là lý do của dừng lỗ theo ATR — công thức hoá nguyên tắc "biến động
cao thì nới dừng lỗ". Dự án dùng `SL = k × ATR`, tức đã theo đúng nguyên tắc này.
**Verified.**

## 14. Việc phải làm rút ra từ Murphy

| #   | việc                                                                                                                  | mức ưu tiên                      | căn cứ          |
| --- | --------------------------------------------------------------------------------------------------------------------- | -------------------------------- | --------------- |
| 30  | Nếu mở rộng nhiều thị trường: áp **trần rủi ro theo NHÓM** (kim loại / cặp USD / JPY), không chỉ theo từng thị trường | **cao** — cần ngay khi bật forex | [E] tr. 396     |
| 31  | Ghi nhận SL theo ATR là **Verified** — công thức hoá nguyên tắc "biến động cao thì nới dừng lỗ"                       | thấp, chỉ ghi tài liệu           | [E] tr. 397     |
| 32  | Ghi nhận mâu thuẫn `MAX_OPEN=1` với khuyến nghị nhiều đơn vị; KHÔNG tự đảo ngược quyết định 15/07                     | thấp                             | [E] tr. 398-399 |
