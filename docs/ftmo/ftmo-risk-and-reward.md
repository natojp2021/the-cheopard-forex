# Q&A Về Quản Trị Rủi Ro Và Vận Hành Quỹ FTMO (The Cheopard)

Tài liệu này lưu trữ nội dung hỏi đáp chuyên sâu (Q&A) về quy định vận hành, giới hạn rủi ro và chiến lược rút tiền (Claim Cycle) khi vận hành hệ thống **The Cheopard** trên tài khoản quỹ **FTMO $100,000**.

> **Nguồn chuẩn khi có xung đột:**
>
> - Quản lý rủi ro FTMO: [`core/infra/ftmo.py`](../../src/python/core/infra/ftmo.py)
> - Quyết định chế độ tài khoản: [`core/infra/target_mode.py`](../../src/python/core/infra/target_mode.py)
> - Phân bổ vị thế & Sizing: [`core/execution/portfolio_allocation.py`](../../src/python/core/execution/portfolio_allocation.py)

---

# Phần I: Các Quy Định Rủi Ro & Drawdown Trên Tài Khoản FTMO

## 🛡️ Câu hỏi I.1: Sau khi pass và cầm tài khoản FTMO $100k, nếu giao dịch bị lỗ 1%, 2%, 3% thì có bị phạt không?

**Hỏi:** Tôi muốn hỏi sau khi pass và được cầm quỹ FTMO, nếu giao dịch bị lỗ nhỏ 1%, 2%, 3% thì có bị phạt không?

**Đáp:**
**KHÔNG!** Sau khi pass và được cấp tài khoản FTMO (FTMO Account), nếu tài khoản âm `-1%`, `-2%` hay `-3%` thì bạn hoàn toàn không bị phạt hay bị khóa tài khoản chỉ vì bị lỗ. Nguyên tắc tối thượng là: **Bạn chỉ bị phạt khi vi phạm các giới hạn Drawdown (Sức chịu đựng rủi ro) của loại tài khoản.**

### 1. Bảng giới hạn rủi ro chuẩn (FTMO 2-Step $100,000)

- **Maximum Daily Loss (Lỗ tối đa theo ngày):** `5%` vốn ban đầu ($5,000).
- **Maximum Loss (Lỗ tối đa tổng):** `10%` vốn ban đầu ($10,000).
- **Profit Target (Mục tiêu lợi nhuận):** `0%` (Không yêu cầu chỉ tiêu lợi nhuận bắt buộc sau khi đã pass).

| Tình Trạng DD          | Equity Tài Khoản | Có Vi Phạm Không? | Ghi Chú Đánh Giá                                      |
| :--------------------- | :--------------: | :---------------: | :---------------------------------------------------- |
| **−1%**                |     $99,000      |     ✅ Không      | Bình thường (Normal DD)                               |
| **−2%**                |     $98,000      |     ✅ Không      | Bình thường (Normal DD)                               |
| **−3%**                |     $97,000      |     ✅ Không      | Mức cảnh báo (Caution)                                |
| **−4%**                |     $96,000      |     ✅ Không      | Mức rủi ro cao (High Risk)                            |
| **−4.9% (trong ngày)** |     $95,100      |     ✅ Không      | Cận kề vạch đỏ, kích hoạt Defensive Mode              |
| **−5%+ (trong ngày)**  |    < $95,000     |  ❌ **VI PHẠM**   | Vi phạm Daily Loss Limit (Tự động mất account)        |
| **−10% (tổng)**        |     $90,000      |  ❌ **VI PHẠM**   | Vi phạm Maximum Loss Limit (Khóa tài khoản vĩnh viễn) |

> [!IMPORTANT]
> **Lưu ý về Daily Loss:** Giới hạn rủi ro ngày được tính theo **Equity realtime** (bao gồm cả Floating P/L, phí Commissions và Swaps), được reset/tính lại vào đầu mỗi ngày giao dịch theo giờ server FTMO.

---

### 2. Mô hình máy trạng thái rủi ro (Risk State Machine) trong The Cheopard

Hệ thống The Cheopard không bao giờ đặt mục tiêu "không được phép âm". Thay vào đó, Risk Engine được thiết kế phân tầng trạng thái tài khoản (`Account State`) cực kỳ rõ ràng:

```
[+5% / +2%]  --> HEALTHY       (Sizing 100% chuẩn)
   [ 0% ]    --> NEUTRAL       (Trạng thái cân bằng)
[-1% / -2%]  --> NORMAL DD     (Khởi động quản trị drawdown nhẹ)
  [ -3% ]    --> CAUTION       (Giảm 25% risk per trade)
  [ -4% ]    --> HIGH RISK     (Giảm 50% risk per trade, siết chặt filter)
  [-4.5%]    --> DEFENSIVE     (Chỉ cho phép chiến lược Win-rate cao)
  [ -5% ]    --> HARD STOP     (Cầu dao tự động đóng sạch vị thế)
```

---

## 📈 Câu hỏi I.2: Khi tài khoản bị sụt giảm (Drawdown), FTMO xử lý thế nào và bot phải phục hồi ra sao?

**Hỏi:** Khi tài khoản bị âm, FTMO có tự bù tiền không? Hệ thống The Cheopard sẽ xử lý việc gỡ lỗ như thế nào?

**Đáp:**
FTMO **KHÔNG bù tiền** vào tài khoản khi bạn bị lỗ. Bạn phải tự giao dịch để phục hồi lại khoản lỗ đó.

### 1. Bài toán phần trăm phục hồi (Recovery Percentage Math)

Nếu tài khoản $100,000 bị lỗ `-3%` xuống còn $97,000:
$$\text{Tỷ lệ cần tăng trưởng để về hòa vốn} = \frac{\$3,000}{\$97,000} \approx +3.093\%$$

| Tình Trạng Tài Khoản    | FTMO Làm Gì?                               | Bạn / Bot Cần Làm Gì?                       |
| :---------------------- | :----------------------------------------- | :------------------------------------------ |
| **Account −2%**         | Không bù                                   | Tiếp tục giao dịch theo quy trình chuẩn     |
| **Account −5% (Daily)** | Chờ reset ngày mới (hoặc khóa nếu vi phạm) | ⚠️ Giảm Sizing, bật chế độ phòng thủ tối đa |
| **Chạm Max Loss −10%**  | Khóa tài khoản (Breach)                    | ❌ Mất tài khoản, không thể giao dịch tiếp  |

---

### 2. Triết lý chống "Gỡ Lỗ" (Anti-Martingale Principle)

> [!WARNING]
> **Quy tắc sinh tồn:** The Cheopard **tuyệt đối KHÔNG** sử dụng logic kiểu: _"Âm −3% thì phải tăng risk/gỡ lệnh để nhanh về vốn"_.

Ngược lại, hệ thống vận hành theo triết lý **Anti-Martingale**:
$$\text{Tài khoản âm (Drawdown tăng)} \longrightarrow \text{Tự động thu hẹp Risk per trade} \longrightarrow \text{Bảo toàn dư địa vốn (Buffer)} \longrightarrow \text{Chờ Edge thuận lợi để phục hồi tự nhiên}$$

---

## 🛡️ Câu hỏi I.3: Hệ thống đang có chiếc khiên follow theo DD của FTMO như thế nào?

**Hỏi:** Hệ thống đang có chiếc khiên follow theo Drawdown (DD) của FTMO như thế nào để đảm bảo không bao giờ vi phạm luật?

**Đáp:**
FTMO đưa ra 2 giới hạn "tử thần": **Lỗ tối đa ngày (5%)** và **Lỗ tối đa tổng (10%)**. Để tuyệt đối không bao giờ chạm tay vào 2 sợi dây điện này, The Cheopard được trang bị một **Khiên chắn nội bộ (Internal Shield)** kết nối trực tiếp với Risk Engine.

Logic và tỷ lệ cắt giảm rủi ro này được lập trình vô cùng nghiêm ngặt (Hard-code) tại file `src/python/core/infra/ftmo_risk_state.py`:

### 1. Phanh an toàn nội bộ (Internal Stop)

Hệ thống không bao giờ chạy sát mép vực. Nó tự dựng lên một "bờ rào" an toàn từ rất xa để trừ hao cho trượt giá (Slippage):

- **DEFENSIVE (Phòng thủ):** Khi lỗ ngày chạm `4.5%` hoặc lỗ tổng chạm `7.0%`, hệ thống bị cấm mở lệnh mới, chỉ duy trì lệnh cũ.
- **HARD STOP (Cầu dao tự động):** Ngay khi lỗ ngày chạm mốc `5.0%` hoặc lỗ tổng vừa chạm `8.0%` (cách rất xa giới hạn 10% của quỹ), hệ thống lập tức **Đóng sạch (Flatten)** toàn bộ vị thế đang có trên tài khoản.

### 2. Auto-Scale Risk (Phòng thủ chủ động theo State Machine)

Đúng với triết lý Anti-Martingale, chiếc khiên này tự động siết hầu bao trước cả khi chạm mốc Defensive:

- Chế độ **CAUTION (Cảnh báo)**: Kích hoạt khi lỗ ngày `>= 3.0%` hoặc lỗ tổng `>= 4.0%`. Mọi chiến lược tự động bị cắt giảm khối lượng xuống còn **75% (Risk Multiplier = 0.75)**.
- Chế độ **HIGH RISK (Rủi ro cao)**: Kích hoạt khi lỗ ngày `>= 4.0%` hoặc lỗ tổng `>= 6.0%`. Khối lượng lệnh bị chặt đứt một nửa, chỉ còn **50% (Risk Multiplier = 0.50)**.

---

# Phần II: Luật Giao Dịch Thuật Toán (EA / Bot) Trên FTMO

## 🤖 Câu hỏi II.1: FTMO có cho phép chạy Bot tự động qua MT5 như The Cheopard không?

**Hỏi:** FTMO có đồng ý cho giao dịch tự động bằng bot chạy qua MetaTrader 5 (MT5) không? Kiến trúc The Cheopard có đáp ứng quy định không?

**Đáp:**
**CÓ!** FTMO hoàn toàn cho phép và ủng hộ việc giao dịch thuật toán (Algorithmic / Automated Trading).

### 1. Các hình thức được FTMO chính thức cho phép

- **Automated Trading & EA (Expert Advisors)** trên MT4/MT5.
- **Algorithmic Trading** sử dụng các ngôn ngữ bên ngoài (Python / C++) kết nối qua API.
- **Custom Proprietary Trading Systems** (Hệ thống tự phát triển riêng).

### 2. Đánh giá độ tương thích kiến trúc (Compliance Matrix)

Luồng xử lý dữ liệu của The Cheopard:
$$\text{Python Decision Engine} \longrightarrow \text{Hard Market Regime} \longrightarrow \text{Risk Engine} \longrightarrow \text{FTMO Compliance Gate} \longrightarrow \text{MT5 Execution}$$

| Thành Phần / Chiến Lược                    | Trạng Thái FTMO | Đánh Giá & Lưu Ý                               |
| :----------------------------------------- | :-------------: | :--------------------------------------------- |
| **Python Decision Engine**                 |     ✅ Đạt      | Khuyến khích sử dụng xử lý logic sâu           |
| **MT5 Execution**                          |     ✅ Đạt      | Hạ tầng thực thi chuẩn                         |
| **Custom Strategy (Proprietary)**          |     ✅ Đạt      | Ưu thế lớn so với mua EA trôi nổi trên mạng    |
| **Hard Market Regime & Dynamic Risk**      |     ✅ Đạt      | Phù hợp triết lý kiểm soát rủi ro của FTMO     |
| **DCA / Grid Trading**                     |   ⚠️ Cảnh báo   | Cần kiểm soát chặt khối lượng và số tầng       |
| **Martingale (Gấp thép)**                  |   ❌ **CẤM**    | Rủi ro cháy tài khoản cực cao                  |
| **Hyperactive Order Modification**         |   ❌ **CẤM**    | Vi phạm giới hạn 2,000 request/ngày của server |
| **Latency Arbitrage / Price Feed Exploit** |   ❌ **CẤM**    | Hành vi gian lận hạ tầng data                  |

---

## 🛑 Câu hỏi II.2: Cần xây dựng "FTMO Compliance Layer" như thế nào để tránh vi phạm chính sách server?

**Hỏi:** Các điểm yếu cần phải rào lại khi đưa The Cheopard lên sàn FTMO là gì?

**Đáp:**
Để đảm bảo bot vận hành ổn định 24/7 mà không gặp bất kỳ cảnh báo nào từ phòng Risk của FTMO, hệ thống xây dựng một lớp **FTMO Compliance Gate** đứng trước lệnh gửi tới MT5.

### 1. 4 Điểm rủi ro kỹ thuật cần rào chặn

1. **Chống Spam Request (Hyperactivity Limit):**
   - _Quy định FTMO:_ Giới hạn **2,000 requests/ngày** (mở, sửa, xóa lệnh, modify SL/TP).
   - _Giải pháp Cheopard:_ Không update Trailing Stop / SL theo từng tick (Tick-by-tick modification). Chỉ tính toán trailing trên Python và chỉ gửi lệnh Modify SL khi khoảng cách dời vượt quá ngưỡng tối thiểu `> 0.5 * ATR`.
2. **Cấm Arbitrage & Exploit Data:** Chiến lược phải dựa trên yếu tố kỹ thuật/vĩ mô thực sự có thể replicate trên môi trường live thật.
3. **Tránh trùng lặp IP/Footprint EA thương mại:** The Cheopard là code tự phát triển (Proprietary Code), không bị dính án phạt trùng vị thế với hàng ngàn trader khác như các EA bán sẵn trên MQL5 Market.
4. **FTMO Compliance Gate Checklist:**
   ```
   [Tín hiệu Entry] ──> [Check Daily DD] ──> [Check Max DD] ──> [Check Correlation] ──> [Check Request Rate] ──> [Pass: Gửi MT5]
   ```

---

# Phần III: Chu Kỳ Rút Lợi Nhuận (Claim Cycle) & Lãi Dự Kiến

## 💰 Câu hỏi III.1: Chu kỳ rút tiền (Claim Cycle) của FTMO hoạt động như thế nào?

**Hỏi:** Khi nào tôi được rút tiền lợi nhuận (Payout/Reward) từ FTMO? Có phải chờ đúng cuối tháng không?

**Đáp:**
**KHÔNG cần chờ cuối tháng calendar!** FTMO áp dụng cơ chế rút tiền linh hoạt theo chu kỳ tối thiểu **14 ngày**.

### 1. Quy trình Claim Reward chuẩn

```
[01/08] Giao dịch ngày đầu tiên ────────> [14/08] Đủ điều kiện 14 ngày
                                                  │
                                                  ▼
                                       [Từ 15/08] Đủ điều kiện CLAIM
                                                  │ (Vị thế phải đóng hết)
                                                  ▼
                                       [Review 1-2 ngày] FTMO Approve
                                                  │
                                                  ▼
                                       [Nhận tiền 80%] ~18/08-19/08
```

### 2. Bảng phân chia lợi nhuận ví dụ (Account $100k)

Giả sử sau 14 ngày giao dịch, tài khoản tăng trưởng **+5%** ($105,000):

$$\text{Tổng Lợi Nhuận (Gross Profit)} = \$5,000$$
$$\text{Tỷ lệ chia chuẩn FTMO 2-Step (80%)} = \$5,000 \times 80\% = \$4,000 \text{ (Trader nhận)}$$

---

## 🎯 Câu hỏi III.2: Với tài khoản $100k, mục tiêu lợi nhuận và quản trị vốn bao nhiêu là hợp lý & bền vững?

**Hỏi:** Với tài khoản $100k, nên giao dịch như thế nào để tài khoản sống lâu, rút tiền đều đặn?

**Đáp:**
Mục tiêu hàng đầu của hệ thống Quant chuyên nghiệp trên FTMO là: **Tối đa hóa khả năng sống sót (Survivability) $\times$ Tính ổn định (Consistency)** chứ không phải săn tìm phần trăm lợi nhuận khủng.

### 1. Bộ thông số mục tiêu của The Cheopard trên FTMO $100k

| Chỉ Tiêu Giao Dịch                    |      Mức Hướng Tới Bền Vững       | Ngưỡng Giới Hạn Của FTMO |
| :------------------------------------ | :-------------------------------: | :----------------------: |
| **Mục tiêu tháng trung bình**         |         `+2.0%` – `+4.0%`         |      Không bắt buộc      |
| **Tháng rất tốt**                     |         `+5.0%` – `+7.0%`         |      Không bắt buộc      |
| **Tháng thị trường xấu**              |         `-1.0%` – `-2.0%`         |      Không bị phạt       |
| **Rủi ro mỗi lệnh (Per-trade Risk)**  |        `0.125%` – `0.50%`         |  Không quy định cụ thể   |
| **Internal Daily Stop (Chặn nội bộ)** | `1.0%` – `1.5%` ($1,000 – $1,500) |     `5.0%` ($5,000)      |
| **Internal Monthly DD Stop**          | `3.0%` – `4.0%` ($3,000 – $4,000) |    `10.0%` ($10,000)     |

---

### 2. Kỳ vọng thu nhập thực tế trong 1 năm ($100k Account, Split 80%)

Một bức tranh lợi nhuận thực tế đạt khoảng **+22.4% Gross/năm**:

```
Tháng 1:  +3.0%     Tháng 5:  +2.5%     Tháng 9:  +2.8%
Tháng 2:  +2.1%     Tháng 6:  -0.8%     Tháng 10: -1.0%
Tháng 3:  -1.2%     Tháng 7:  +3.2%     Tháng 11: +4.5%
Tháng 4:  +4.0%     Tháng 8:  +1.5%     Tháng 12: +1.8%
-------------------------------------------------------
Tổng Gross Lợi Nhuận: ~ +22.4% ($22,400 USD)
Lợi nhuận thực nhận (80% Profit Split): ~$17,920 USD / năm
```

> [!TIP]
> **Triết lý vận hành:** Một bot đem lại **+2.5%/tháng với Max DD 3%** có giá trị thương mại và độ an toàn cao hơn gấp nhiều lần một bot đem lại **+8%/tháng nhưng Max DD lên tới 8-9%**. Trên FTMO, **Account Survival (Sự sống sót của tài khoản) chính là tài sản quý giá nhất!**
