# KB — Rủi ro chiến lược, tần suất và cỡ lệnh

## References

| # | nguồn | chương / trang | nguyên lý lấy ra |
|---|---|---|---|
| [A] | López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley. | Ch. 15 "Understanding Strategy Risk", tr. 211-220 | công thức Sharpe theo độ chính xác và tần suất; rủi ro chiến lược khác rủi ro danh mục; xác suất chiến lược thất bại |
| [B] | López de Prado (2018) | Ch. 10 "Bet Sizing", tr. 141-149 | cỡ lệnh từ xác suất dự báo |
| [C] | Kelly, J.L. (1956) — tiêu chuẩn Kelly | dẫn trong Aronson ch.7 tr. 348 | tỉ lệ đặt cược tối ưu; hậu quả của vượt quá |
| [D] | Aronson, D. (2007). *Evidence-Based Technical Analysis*. Wiley. | Ch. 7 tr. 347-349 | giới hạn của chênh lệch giá; đòn bẩy giết người có thông tin đúng |

---

## 1. Rủi ro CHIẾN LƯỢC không phải rủi ro DANH MỤC — [A] tr. 216

Trích nguyên văn:

> "**Strategy risk should not be confused with portfolio risk.** Most firms and
> investors compute, monitor, and report portfolio risk without realizing that
> **this tells us nothing about the risk of the strategy itself.** Strategy risk
> is not the risk of the underlying portfolio, as computed by the chief risk
> officer. **Strategy risk is the risk that the investment strategy will fail to
> succeed over time**, a question of far greater relevance to the chief
> investment officer."

**Áp dụng — đây là một lỗ hổng khái niệm của hệ thống.** Toàn bộ tầng rủi ro của
dự án (`risk_guard`, `target_mode`, sizing theo đệm tới sàn FTMO, Monte Carlo
P(cháy) = 0%) đo **rủi ro danh mục**: xác suất xuyên sàn, drawdown, lỗ ngày.

Không có chỗ nào đo **rủi ro chiến lược**: xác suất tỉ lệ thắng thật thấp hơn
mức cần để có lãi. Hai câu hỏi khác hẳn nhau, và câu thứ hai chưa từng được hỏi.

## 2. Sharpe là hàm của ĐỘ CHÍNH XÁC và TẦN SUẤT — [A] tr. 211-213

### 2.1 Payout đối xứng

Với `n` lệnh độc lập mỗi năm, thắng `+π` xác suất `p`, thua `−π`:

```
θ[p, n] = (2p − 1) / (2·√(p(1−p))) · √n
```

Điểm đáng chú ý: **`π` triệt tiêu**. Sharpe không phụ thuộc quy mô lãi/lỗ khi
payout đối xứng, chỉ phụ thuộc `p` và `n`.

> "even for a small p > ½, the Sharpe ratio can be made high for a sufficiently
> large n. **This is the economic basis for high-frequency trading**, where p
> can be barely above .5, and the key to a successful business is to increase n."

Aronson [A] tr. 212 cũng nhấn: Sharpe là hàm của **precision**, không phải
accuracy — bỏ qua một cơ hội (negative) không bị thưởng cũng không bị phạt.

Ví dụ trong sách: `p = 0,55` cần **396 lệnh/năm** để đạt Sharpe 2.

### 2.2 Đánh đổi độ chính xác ↔ tần suất

```
p = ½ · (1 + √(1 − n/(θ² + n)))
```

Ví dụ trong sách: chiến lược chỉ ra lệnh hàng tuần (`n = 52`) cần `p = 0,6336`
để đạt Sharpe 2.

### 2.3 Payout BẤT ĐỐI XỨNG — trường hợp của dự án

Thắng `π₊` xác suất `p`, thua `π₋` (với `π₋ < π₊`):

```
θ[p, n, π₋, π₊] = ((π₊ − π₋)·p + π₋) / ((π₊ − π₋)·√(p(1−p))) · √n
```

Giải ngược ra độ chính xác cần thiết (`binHR` trong [A] tr. 214-215):

```
a = (n + θ²)·(π₊ − π₋)²
b = (2n·π₋ − θ²·(π₊ − π₋))·(π₊ − π₋)
c = n·π₋²
p = (−b + √(b² − 4ac)) / (2a)
```

**Đã kiểm chứng cài đặt:** với ví dụ của sách `n = 260, π₋ = −0,01, π₊ = 0,005,
p = 0,7` công thức cho `θ = 1,173` (sách ghi 1,173) và `p` cần cho `θ = 2` là
`0,722` (sách ghi 0,72). Khớp.

## 3. Áp vào bốn chiến lược LIVE — số liệu thật

Nguồn: sổ lệnh SimBroker 2004-2026 trong `scratch/logs_doc_lap/`. `π₋` là trung
bình phần THUA thực tế, không phải hằng số −1R.

| chiến lược | n | năm | n/năm | p | thắng TB | θ (AFML) | Sharpe thực | p\* (θ=0) | biên an toàn |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `SwingDon` | 168 | 21,7 | 7,7 | 0,488 | +1,88R | +1,09 | +0,80 | 0,293 | **+0,195** |
| `DonchianH4Breakout` | 111 | 21,2 | 5,2 | 0,459 | +2,04R | +0,68 | +0,56 | 0,312 | +0,147 |
| `PaDonchianH4` | 217 | 21,1 | 10,3 | 0,507 | +1,41R | +0,59 | +0,48 | 0,415 | +0,092 |
| `PaPullbackH4` | 275 | 20,8 | 13,2 | 0,495 | +1,43R | +0,60 | +0,53 | 0,412 | **+0,083** |

`p*` là tỉ lệ thắng tối thiểu để `θ = 0`; khoảng cách `p − p*` là **biên an
toàn** của chiến lược.

### Ba điều đọc được, chưa từng đo trước đây

**(a) `θ` theo mô hình nhị thức cao hơn Sharpe thực ở cả bốn chiến lược.** Mô
hình giả định đúng hai kết cục; thực tế lãi/lỗ có phân phối, phương sai lớn hơn.
Nên `θ` của AFML là **cận trên lạc quan**, dùng để so sánh tương đối giữa các
cấu hình chứ không phải để dự báo Sharpe.

**(b) `PaPullbackH4` là mắt xích yếu nhất — biên an toàn +0,083.** Tỉ lệ thắng
chỉ cần tụt từ 0,495 xuống 0,412 là hết lãi. Trích [A] tr. 217 về đúng tình
huống này:

> "a relatively small drop in p (from p = .7 to p = .67) will wipe out all the
> profits. **The strategy is intrinsically risky, even if the holdings are not.**"

**(c) `SwingDon` bền nhất** (+0,195) dù tần suất thấp thứ ba — nhờ payout
+1,88R kết hợp tỉ lệ thắng gần 0,5.

Lưu ý kỹ thuật: với `SwingDon`, biểu thức `b² − 4ac` âm ở một số mục tiêu `θ`,
cho nghiệm phức. Nghĩa là **không tồn tại** tỉ lệ thắng nào đạt được `θ` đó với
cặp `(π₋, π₊, n)` hiện có — một thông tin hữu ích chứ không phải lỗi.

## 4. Bài toán tần suất — câu trả lời có công thức

Câu hỏi lặp lại của người dùng: danh mục quá chậm, trung vị 668 ngày qua Phase 1.

Công thức [A] tr. 212 cho câu trả lời chính xác: **`θ` tỉ lệ với `√n`**, với `p`
và tỉ lệ payout giữ nguyên.

Tăng tần suất `DonchianH4Breakout` từ 5,2 lên 37,4 lệnh/năm nhân Sharpe với
`√(37,4/5,2) = 2,68` — **nếu** `p` và `π₊/π₋` không đổi.

Nhưng chúng KHÔNG giữ nguyên. Quét 108 tổ hợp ngày 03/08 cho thấy cấu hình
`N=34, SL 1,0, giữ 6` tăng tần suất 7,2 lần nhưng đồng thời hạ payout trung bình
(hạn giữ 6 nến cắt bớt đuôi phải). Hai hiệu ứng ngược chiều nhau, và **công thức
này là cách đúng để cân chúng** — thay vì so R/năm như tôi đã làm, vì R/năm bỏ
qua phương sai.

→ Việc phải làm: tính lại `θ` theo công thức [A] cho từng cấu hình trong cao
nguyên, thay vì xếp hạng theo R/năm.

## 5. Xác suất chiến lược THẤT BẠI — [A] tr. 216-218

Thuật toán:

1. Từ chuỗi kết quả `{π_t}`, ước lượng `π₋ = E[π | π ≤ 0]` và `π₊ = E[π | π > 0]`.
   (Hoặc khớp hỗn hợp hai Gaussian bằng thuật toán EF3M.)
2. Tần suất năm `n = T / y`.
3. Bootstrap phân phối của `p`: lặp `I` lần, mỗi lần rút `⌊n·k⌋` mẫu có hoàn lại
   từ `{π_t}` (với `k` là số năm mô phỏng), tính `p` của mẫu đó.
4. `P[thất bại] = P[p < p_θ*]`, với `p_θ*` là tỉ lệ thắng tối thiểu cho mục tiêu
   `θ*`.

**Chưa cài trong dự án.** Đây là phép đo trực tiếp trả lời câu hỏi mà tầng rủi
ro hiện tại không hỏi: *xác suất chiến lược này ngừng có lãi là bao nhiêu?*

## 6. Đòn bẩy: điều kiện Kelly — [D] tr. 348, [C]

Aronson kể trò chơi "Casino Night": tung đồng xu, thắng được gấp đôi tiền cược,
thua mất tiền cược, 75 lần tung. Kỳ vọng rất thuận lợi, nhưng nhiều sinh viên
vẫn cháy vì cược quá lớn.

> "A formula worked out by Kelly... specifies the optimal fraction to bet on each
> coin flip so as to maximize the growth rate of the bettor's capital... In this
> particular game, the optimal fraction to wager on each bet is 0.25. **If this
> level is exceeded, the bettor faces greater risk without the benefit of a
> faster growth of capital.** If one were to employ a bet fraction of 0.58 it is
> likely all funds would be lost, despite the favorable expectation."

Và nối thẳng sang thị trường thật:

> "This is what happens to an arbitrageur with good information who uses too much
> leverage."

LTCM 1998 được nêu làm ví dụ ([D] tr. 347): các định giá sai họ nhận ra **cuối
cùng đều đúng**, nhưng đòn bẩy quá lớn khiến quỹ không sống nổi tới lúc đó.

**Áp dụng:** hệ thống sizing hiện tại `risk = k · min(equity − sàn_tổng, equity −
sàn_ngày)` với `k = 0,10` và trần tuyệt đối 0,50%. Cả hai ràng buộc cùng chạm
tại đệm 5.000 USD. Đây là cách tiếp cận **thận trọng hơn Kelly** — nó không tối
đa hoá tốc độ tăng vốn mà tối thiểu hoá xác suất xuyên sàn.

Với ràng buộc FTMO (sàn TĨNH, một lần xuyên là mất tài khoản), lựa chọn ấy đúng:
Kelly tối ưu cho tăng trưởng dài hạn khi không có ngưỡng phá sản cứng, còn ở đây
ngưỡng phá sản cứng tồn tại. **[suy luận của ta]** — tài liệu không bàn trực
tiếp trường hợp có sàn tĩnh kiểu prop-firm.

## 7. Việc phải làm

| # | việc | căn cứ |
|---|---|---|
| 1 | Xếp hạng cấu hình bằng **`θ` theo công thức [A]**, không bằng R/năm | [A] tr. 213-214 |
| 2 | Cài **xác suất chiến lược thất bại** `P[p < p_θ*]` cho từng chiến lược LIVE | [A] tr. 216-218 |
| 3 | Theo dõi **biên an toàn `p − p*`** như một chỉ số vận hành; `PaPullbackH4` đang mỏng nhất (+0,083) | [A] tr. 217 |
| 4 | Ghi rõ trong tài liệu rủi ro: hệ thống hiện chỉ đo rủi ro DANH MỤC, chưa đo rủi ro CHIẾN LƯỢC | [A] tr. 216 |


---

# Phần IX — Abraham, *The Trend Following Bible* (2012)

## References bổ sung

| # | nguồn | chương / trang | nguyên lý lấy ra |
|---|---|---|---|
| [W] | Abraham, A. (2012). *The Trend Following Bible: How Professional Traders Compound Wealth and Manage Risk*. John Wiley & Sons. | Ch. "Managing the Risks When Trend Following", tr. 82-91 | phân tầng trần rủi ro bốn lớp; định nghĩa "core equity"; trần rủi ro theo NGÀNH |

Tác giả điều hành quỹ quản lý tài khoản theo trend following. Giá trị của cuốn
này với dự án nằm ở chỗ nó cho **các con số vận hành thật của một người quản lý
tiền**, không phải lý thuyết.

---

## 52. Phân tầng trần rủi ro BỐN LỚP — [W] tr. 84-91

Đây là thứ dự án có một phần nhưng chưa đủ tầng.

| tầng | trần của Abraham | dự án hiện tại | nhận xét |
|---|---|---|---|
| mỗi lệnh | 0,75-1,25% core equity | **0,25%** (`RISK_PREFERRED`) | dự án **chặt hơn 4-5 lần** |
| mỗi **ngành** | **5% tổng danh mục** | `precious_metals_total` 95% **phơi nhiễm danh nghĩa** | **khác loại — xem §53** |
| tổng lãi lệnh đang mở so với core equity | **20%** → ngừng mở lệnh mới | **không có** | thiếu |
| ký quỹ trên vốn | 15% (20% khi uỷ thác) | không áp dụng (không dùng đòn bẩy ký quỹ kiểu futures) | không liên quan |
| rủi ro tuyệt đối mỗi hợp đồng | 2.000-2.500 đô | không có | xem §54 |

Con số quan trọng nhất, và Abraham nói ông học được nó bằng cách mất tiền:

> "What I learned from these incidents was to **cap my sector risk. Today part of
> my risk plan is that I will only allocate 5 percent of my total portfolio to
> any sector.** Any sector means any stock sector such as tech, retail, and so
> on, or in the commodities interest rates, energies, grains, **metals**, and so
> forth."

Và ông nêu đúng ví dụ của dự án:

> "when **gold** seems to start trending it is not unreasonable to see **silver**
> start trending."

## 53. Trần "phơi nhiễm danh nghĩa" KHÔNG PHẢI trần "rủi ro theo ngành"

Dự án có `FACTOR_CAPS_PCT["precious_metals_total"] = 0,95` trong
`core/execution/factor_exposure.py`. Đọc kỹ thì đó là trần **giá trị danh nghĩa
so với vốn**, không phải trần **số tiền có thể mất**. Hai thứ khác nhau về bản
chất: một vị thế vàng danh nghĩa 95% vốn với dừng lỗ 0,25% chỉ rủi ro 0,25%.

Cái Abraham nói tới là tầng thứ hai: **tổng số tiền đang đặt cược vào nhóm kim
loại quý**. Dự án ràng buộc gián tiếp qua `MAX_OPEN_RISK` = 1% cho **toàn** danh
mục — mà danh mục hiện gần như toàn kim loại quý, nên trên thực tế rủi ro nhóm
kim loại bị chặn ở 1%, tức **chặt hơn 5 lần** so với mức 5% của Abraham.

**Kết luận: dự án ĐẠT nguyên tắc, nhưng đạt một cách tình cờ.** Ràng buộc đến từ
trần danh mục chứ không từ một trần nhóm có tên. Ngày nào danh mục thêm một
chiến lược không phải kim loại, trần 1% sẽ chia cho cả hai nhóm và ràng buộc
nhóm kim loại biến mất một cách âm thầm. Đây là đúng loại lỗi im lặng mà dự án
đã gặp nhiều lần (cổng regime bị vô hiệu hoá, `macro_state` lệch đường dẫn).

Việc cần làm: đặt trần rủi ro nhóm **tường minh**, không dựa vào việc danh mục
tình cờ đồng nhất. Tương quan vàng-bạc 0,82 (Katsanos ch.7 tr.96) là căn cứ định
lượng cho việc gộp nhóm.

## 54. "Core equity" — và vì sao FTMO làm câu chuyện này khác đi

Abraham định nghĩa rất rõ ([W] tr. 89):

> "**Core equity is the equity of all my closed positions and my cash positions.
> Core equity does not include any open profits.** If I were to include my open
> trade equity I would distort to the upside my true account balance and possibly
> take on more risk."

> "If I measure my risks against my core equity **and** my open trade equity,
> **I am enhancing my risks.**"

Dự án định cỡ theo `account.equity` — bao gồm lãi/lỗ lệnh đang mở.

**Nhưng ở đây có một điểm mà Abraham không gặp và dự án thì có:** FTMO đo Max
Loss trên **equity**, không phải balance. Nếu equity chạm 90.000 đô trong phiên
thì hỏng tài khoản, bất kể balance là bao nhiêu. Nên khi tính **đệm tới sàn**,
dùng equity là **đúng** — đó là đại lượng mà luật FTMO ràng buộc.

Vấn đề Abraham nêu vẫn còn, chỉ ở chỗ khác: lãi đang trôi làm đệm to ra → lệnh
mới to ra → nếu giá quay đầu thì vừa mất lãi trôi vừa đang cầm vị thế lớn hơn.
Đó là nhồi lệnh trên lợi nhuận chưa thực hiện.

**Cách hoà giải hai nguồn** (chưa triển khai, cần đo trước):
- **đo đệm** theo `equity` — bắt buộc, vì đó là đại lượng FTMO ràng buộc;
- **định cỡ** theo `min(equity, balance)` — để lãi chưa thực hiện không tự động
  nới cỡ lệnh mới.

Đây là một thay đổi production nên phải backtest trước, không sửa thẳng.

## 55. Chỗ Abraham YẾU — công thức risk of ruin — [W] tr. 83

Ông đưa công thức:

    R = e^(−2·a/d)     với a = lợi nhuận trung bình, d = độ lệch chuẩn

và mô tả R là "risk of losing one standard deviation". Đây **không phải** định
nghĩa risk-of-ruin chuẩn (xác suất vốn chạm ngưỡng huỷ diệt trước khi tăng), và
công thức không chứa cả cỡ vốn lẫn ngưỡng huỷ diệt — hai đại lượng mà bất kỳ
công thức risk-of-ruin thật nào cũng phải có.

Phần ẩn dụ "cắn táo" của ông cũng sai về mặt toán: rủi ro 1% mỗi lệnh **không**
cho "100 lần cắn", vì mỗi lần rủi ro là 1% của số vốn **còn lại**, nên về lý
thuyết không bao giờ chạm 0. Ông tự nhận là "oversimplified", nhưng con số 100
vẫn dễ gây hiểu sai.

**Xử lý: không dùng công thức này.** Dự án đã có Monte Carlo bootstrap theo khối
cho cùng câu hỏi, và đó là công cụ mạnh hơn hẳn. Ghi lại mâu thuẫn để lần sau ai
đọc Abraham không đem công thức đó vào.

Đây cũng là ví dụ cho nguyên tắc phân hạng nguồn: Abraham đáng tin ở phần **vận
hành** (ông thật sự quản tiền và các trần rủi ro của ông là kinh nghiệm đắt),
nhưng không đáng tin ở phần **toán**. Không có nguồn nào đáng tin toàn phần.

## 56. Việc phải làm rút ra từ Abraham

| # | việc | mức ưu tiên | căn cứ |
|---|---|---|---|
| 58 | Đặt **trần rủi ro nhóm kim loại quý TƯỜNG MINH** thay vì dựa vào việc danh mục tình cờ toàn kim loại | **cao** — lỗi sẽ im lặng khi thêm chiến lược mới | [W] tr. 88; Katsanos ch.7 tr.96 |
| 59 | Thêm trần **tổng lãi lệnh đang mở** (Abraham: 20% core equity → ngừng mở mới) | trung bình | [W] tr. 89 |
| 60 | Đo thử định cỡ theo `min(equity, balance)` để không nhồi lệnh trên lãi chưa thực hiện; vẫn đo đệm theo `equity` vì FTMO ràng buộc equity | trung bình — cần backtest trước | [W] tr. 89 |
| 61 | KHÔNG dùng công thức risk-of-ruin của Abraham; giữ Monte Carlo bootstrap theo khối | thấp — chỉ ghi tài liệu | §55 |


---

# Phần XI — Van Tharp, *Trade Your Way to Financial Freedom* (2nd ed. 2006) ch.12

## References bổ sung

| # | nguồn | chương / trang | nguyên lý lấy ra |
|---|---|---|---|
| [Y] | Tharp, V.K. (2006). *Trade Your Way to Financial Freedom*, 2nd ed. McGraw-Hill. | Ch. 12 "What Do I Mean by Position Sizing?", tr. 286-305 | bốn mô hình định cỡ; Bảng 12-4 quét rủi ro-sụt vốn; hiện tượng lệnh bị từ chối |

## 60. Bảng 12-4 — quét rủi ro so với sụt vốn — [Y] tr. 293

Hệ 55/21 breakout (chính là họ Donchian), danh mục 1 triệu đô, 595 lệnh trong
5,5 năm:

| % rủi ro/lệnh | lãi ròng | lệnh bị từ chối | %lãi/năm | sụt vốn tối đa |
|---:|---:|---:|---:|---:|
| 0,10% | 5.327 | **410** | 0,00% | 0,36% |
| 0,25% | 80.685 | **219** | 0,70% | **2,47%** |
| 0,50% | 400.262 | 42 | 3,20% | **6,50%** |
| 0,75% | 672.717 | 10 | 4,90% | 10,20% |
| 1,00% | 1.107.906 | 4 | 7,20% | 13,20% |
| 1,75% | 2.776.044 | 1 | 13,10% | 22,00% |
| 2,50% | 5.621.132 | 0 | 19,20% | 29,10% |
| 5,00% | 18.620.657 | 0 | 38,30% | 46,70% |
| 10,00% | 304.300.000 | 0 | 70,20% | 72,70% |
| 25,00% | 1.212.000.000 | 0 | 93,50% | ~84% |

> "Notice that the best reward-to-risk ratio occurs at about 25 percent risk per
> position, **but you would have to tolerate an 84 percent drawdown** in order to
> achieve it."

### Đối chiếu với hiệu chỉnh của chính dự án — trùng khớp đáng kể

Dự án tự đo ngày 31/07 (`scratch/dd_tightening_2026-07-31.py`, phát lại 183 lệnh
thật của danh mục) và ghi kết quả vào `core/infra/ftmo.py`:

| % rủi ro/lệnh | sụt vốn — **dự án đo** | sụt vốn — **Van Tharp Bảng 12-4** |
|---:|---:|---:|
| 0,25% | **3,37%** | **2,47%** |
| 0,30% | 4,03% | — |
| 0,35% | 4,68% | — |
| 0,50% | **6,63%** | **6,50%** |

Ở mức 0,50% hai con số gần như trùng (6,63% so với 6,50%). Đây là **xác nhận độc
lập** cho hiệu chỉnh định cỡ của dự án: một hệ breakout 55/21 trên danh mục hàng
hoá của Van Tharp và một danh mục trend-following trên vàng của dự án, cách nhau
20 năm, cho cùng quan hệ rủi ro-sụt vốn.

Nó cũng xác nhận **tính gần tuyến tính** mà dự án đã giả định khi chọn 0,25%:
trong vùng rủi ro thấp, sụt vốn tăng xấp xỉ tỉ lệ với rủi ro mỗi lệnh. Van Tharp:
0,25→2,47 và 0,50→6,50 (hệ số 2,6); dự án: 0,25→3,37 và 0,50→6,63 (hệ số 2,0).
Cả hai đều hơi siêu tuyến tính, tức tăng rủi ro gấp đôi làm sụt vốn tăng **hơn**
gấp đôi. Điều này củng cố việc chọn mức thấp.

## 61. Cột "lệnh bị từ chối" — vấn đề dự án CHƯA kiểm — [Y] tr. 293

Cột dễ bỏ qua nhất của bảng lại là cột quan trọng nhất với dự án:

| % rủi ro | lệnh bị từ chối trên 595 |
|---:|---:|
| 0,10% | **410 (69%)** |
| 0,25% | **219 (37%)** |
| 0,50% | 42 (7%) |
| 1,00% | 4 |

Ở mức rủi ro thấp, cỡ vị thế tính ra nhỏ hơn đơn vị giao dịch tối thiểu và lệnh
**bị bỏ**. Van Tharp cảnh báo thẳng ([Y] tr.294):

> "Table 12-3 suggests that you probably should not trade this system unless you
> had at least $100,000 and then you probably should not risk more than about
> ½ percent per trade."

**Dự án dùng đúng mức 0,25%** — mức mà trong bảng của Van Tharp làm mất 37% số
lệnh. Nhưng đơn vị giao dịch khác nhau: ông dùng hợp đồng tương lai (một hợp đồng
vàng = 100 ounce), dự án dùng CFD với lot tối thiểu 0,01 (= 1 ounce), tức hạt
nhỏ hơn 100 lần. Nên vấn đề nhẹ hơn nhiều — nhưng **chưa được đo**.

Với tài khoản FTMO 100.000 đô, rủi ro 0,25% = 250 đô mỗi lệnh. Dừng lỗ 1,5×ATR
trên vàng ở mức ATR H4 khoảng 15 đô cho khoảng cách ~22 đô/ounce → cỡ vị thế
~11 ounce = 0,11 lot. Nằm trên hạt tối thiểu 11 lần, nên chưa phải vấn đề. Nhưng
khi ATR tăng vọt (khủng hoảng) khoảng cách dừng lỗ giãn ra và cỡ lệnh co lại —
đúng lúc thị trường có xu hướng mạnh nhất.

**Việc cần làm:** đếm số lệnh bị từ chối do làm tròn cỡ trong backtest. Nếu con
số đáng kể và tập trung vào giai đoạn biến động cao, đó là một dạng thiên lệch
sống sót ngược mà backtest hiện tại không phản ánh.

## 62. Bốn mô hình định cỡ và khuyến nghị của Van Tharp — [Y] tr. 286-303

| mô hình | mô tả | Van Tharp đánh giá |
|---|---|---|
| 1. số tiền cố định | 1 đơn vị mỗi X đô vốn | "practically amounts to no position sizing" với tài khoản nhỏ |
| 2. đơn vị giá trị bằng nhau | chia đều vốn cho các mã | thông dụng với nhà đầu tư cổ phiếu |
| 3. **% rủi ro** | cỡ = (%vốn) / (khoảng cách dừng lỗ) | **"recommended as the best model for long-term trend followers"** |
| 4. % biến động | cỡ theo ATR như phần trăm vốn | "one of the more excellent features for controlling exposure. **Few traders use it.**" |

Dự án dùng **mô hình 3** (% rủi ro theo khoảng cách dừng lỗ), đúng cái Van Tharp
khuyến nghị cho trend following. **Đây là hạng Verified.**

Đáng chú ý: dự án đã **thử và bác bỏ** mô hình 4 (vol-targeting) ngày 31/07, với
lý do ghi trong `ftmo.py`: ở cùng mức sụt vốn đỉnh, hạ rủi ro phẳng cho nhiều lợi
nhuận hơn 14-25 điểm phần trăm, vì lệnh thắng lớn nhất của trend đến đúng trong
giai đoạn biến động cao. Van Tharp khen mô hình 4 nhưng không đưa số liệu so sánh
trực tiếp với mô hình 3 trên danh mục trend-following. **Giữ quyết định của dự
án** — nó dựa trên đo đạc trên chính dữ liệu của mình, còn Van Tharp chỉ nêu định
tính.

## 63. Việc phải làm rút ra từ Van Tharp

| # | việc | mức ưu tiên | căn cứ |
|---|---|---|---|
| 64 | Đếm **lệnh bị từ chối do làm tròn cỡ vị thế** trong backtest, tách theo mức biến động | **cao** — chưa từng đo, và Van Tharp cho thấy nó có thể ăn tới 37% số lệnh | [Y] tr. 293 |
| 65 | Ghi nhận Bảng 12-4 là **xác nhận độc lập** cho quan hệ rủi ro-sụt vốn dự án tự đo (0,50% → 6,50% so với 6,63%) | thấp — chỉ ghi tài liệu | [Y] tr. 293 |


---

## 72. Dừng lỗ cho chiến lược HỒI QUY TRUNG BÌNH — mâu thuẫn đã được giải

Nguồn: Chan, E. (2013). *Algorithmic Trading: Winning Strategies and Their
Rationale*. John Wiley & Sons. Ch. 8 tr. 174-176 (mục "Stop Loss").

Đây là mâu thuẫn dự án ghi nợ từ trước: chiến lược hồi quy trung bình về logic
**không nên** có dừng lỗ (giá càng đi ngược thì kỳ vọng hồi càng mạnh), nhưng
mọi quy tắc rủi ro của dự án đều đòi dừng lỗ.

Chan nêu đúng nghịch lý ([Chan] tr.174):

> "it is a matter of controversy whether we should impose stop loss for
> mean-reverting strategies. At first blush, **stop loss seems to contradict the
> central assumption of mean reversion.** For example, if prices drop and we
> enter into a long position, and prices drop some more and thus induce a loss,
> we should expect the prices to rise eventually if we believe in mean reversion."

Rồi ông chỉ ra vì sao dữ liệu **có vẻ** ủng hộ việc bỏ dừng lỗ — và đó là một
lập luận về thiên lệch sống sót rất sắc ([Chan] tr.175):

> "**Survivorship bias was in action** when I claimed earlier that stop loss
> always lowers the performance of mean-reverting strategies. It is more accurate
> to say that stop loss always lowers the performance of mean-reverting
> strategies **when the prices remain mean reverting**, but it certainly
> **improves** the performance of those strategies **when the prices suffer a
> regime change and start to trend!**"

Tức là: danh mục các chiến lược hồi quy trung bình "đã backtest thành công" tự
nó đã loại bỏ những chuỗi giá đổi trạng thái sang xu hướng. Đo trên tập đã lọc
đó thì dừng lỗ tất nhiên chỉ làm giảm hiệu suất.

### Giải pháp của Chan — [Chan] tr.175

> "Clearly, we should **impose a stop loss that is greater than the backtest
> maximum intraday drawdown.** In this case, the stop loss would never have been
> triggered [in the backtest]."

Và tóm tắt cuối chương:

> "Stop loss for mean-reverting strategies should be set so that they are **never
> triggered in backtests.** Stop loss for momentum strategies forms a natural and
> logical part of such strategies."

**Phán quyết cho dự án:** mâu thuẫn được giải, không phải bằng cách chọn một
bên mà bằng cách phân vai. Dừng lỗ của chiến lược hồi quy trung bình **không
phải công cụ quản lý lệnh** — nó là **bảo hiểm thiên nga đen**, đặt ở mức chưa
từng bị chạm trong backtest, chỉ để phòng trường hợp chuỗi giá đổi trạng thái.

Điều này khác hẳn dừng lỗ của chiến lược theo xu hướng, vốn là một phần logic
của chiến lược. Dự án hiện toàn trend-following nên chưa gặp; nhưng ứng viên
mean-reversion H4 đang treo sẽ cần đúng cách đặt này.

Ghi kèm hệ quả về định cỡ: nếu dừng lỗ đặt xa như vậy thì công thức
`cỡ = rủi ro / khoảng cách dừng lỗ` sẽ cho cỡ rất nhỏ. Với chiến lược hồi quy
trung bình phải định cỡ theo cách khác (Chan ch.8 dùng Kelly/CPPI), không dùng
khoảng cách dừng lỗ làm mẫu số.

### Cùng chương: Chan xác nhận CPPI của dự án — [Chan] tr.176

> "Do you want to ensure that your drawdown will not exceed a preset maximum, yet
> enjoy the highest possible growth rate? **Use constant proportion portfolio
> insurance.**"

Đây đúng công thức định cỡ theo đệm mà dự án chuyển sang ngày 31/07
(`risk = k × (equity − sàn)`). Xác nhận thêm rằng đó là một kỹ thuật có tên và
có nguồn, không phải sáng chế của dự án.

| # | việc | mức ưu tiên | căn cứ |
|---|---|---|---|
| 71 | Khi dựng ứng viên mean-reversion: dừng lỗ đặt **ngoài** mức sụt vốn trong phiên lớn nhất của backtest; định cỡ KHÔNG dùng khoảng cách dừng lỗ làm mẫu số | trung bình — chỉ khi làm mean-reversion | Chan ch.8 tr.175 |

---

## Gap cuối tuần — góc mà trần rủi ro theo dừng lỗ KHÔNG che (đo 04/08/2026)

`MAX_OPEN_RISK` (2%) và `RISK_ABSOLUTE_MAX` (0,50%) đều đo **khoảng cách tới
dừng lỗ**. Một cú gap thì **nhảy qua** dừng lỗ, nên hai trần ấy không ràng buộc
gì trước nó. `ftmo.py` có bàn về notional nhưng chỉ theo góc **ký quỹ**, và kết
luận đúng rằng "ràng buộc thật là drawdown, không phải ký quỹ" — góc gap chưa
được ghi ở đâu cả. Mục này lấp chỗ đó.

### Gap thật của vàng, đo trên 23 năm

1.200 phiên mở đầu tuần (Thứ Hai), dữ liệu M1 2003-05 → 2026-07:

| phân vị | \|gap\| |
| ------- | ------: |
| 50% | 0,002% |
| 90% | 0,151% |
| 99% | 0,622% |
| **lớn nhất** | **2,539%** (01/12/2003) |

Số tuần vượt 1,9%: **1/1200 (0,08%)**.

Điều này **bác bỏ** một nhận định từng được nêu trong review rằng "vàng đã gap
cuối tuần >1,9% nhiều lần trong giai đoạn 2024-2026". Đo được: đúng một lần
trong 23 năm, và là năm 2003.

### Nhưng cơ chế thì có thật

Lỗ do gap = `notional × gap`, không liên quan tới khoảng cách dừng lỗ. Với 5
chiến lược LIVE ở trần danh mục 2% (giá vàng $4.000, equity $100.000):

| chiến lược | SL (USD/oz) | notional | lỗ nếu gap 2,539% |
| ---------- | ----------: | -------: | ----------------: |
| SwingDon (2,5×ATR_D1) | 112 | $17.778 | $451 |
| H4Metals (1% giá) | 40 | $50.000 | $1.270 |
| PaDonchianH4 (~2×ATR_H4) | 24 | $83.333 | $2.116 |
| PaPullbackH4 (~2×ATR_H4) | 24 | $83.333 | $2.116 |
| DonchianH4Breakout (1,5×ATR_H4) | 18 | $111.111 | $2.821 |

Chặn bởi `MAX_OPEN_RISK` 2%, notional thực tế tối đa ≈ **2,76× equity** →
gap kỷ lục gây lỗ **7,02% equity**, vượt giới hạn ngày 5% ⇒ **mất tài khoản**.

Chiến lược SL càng hẹp thì notional càng lớn cho cùng một mức rủi ro — nên phơi
nhiễm gap tập trung ở nhóm H4, không ở SwingDon.

### Ngưỡng suy ra, và vì sao CHƯA chặn cứng

    notional ≤ 5% / 2,539% ≈ 1,97 × equity

Đây là phép chia hai con số đã có (luật FTMO và gap đo được), không phải ngưỡng
tự đặt. Cài đặt: `target_mode.canh_bao_notional_gap()`, hiện **chỉ cảnh báo**.

Chưa chặn cứng vì xác suất khớp cả hai điều kiện — danh mục đầy VÀ gặp gap kỷ
lục — rất thấp: riêng vế gap đã là 1/1200 tuần, và các chiến lược này tần suất
thấp nên hiếm khi cùng mở. Đặt trần cứng khi chưa đo được nó bó buộc bao nhiêu
lần trong vận hành thật sẽ là thêm một quy tắc nghiệp vụ không có căn cứ. Thu số
liệu từ cảnh báo trước; nếu nó kêu thường xuyên thì lúc đó mới đủ căn cứ siết.
