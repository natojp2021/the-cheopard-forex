# The Cheopard Forex — Săn tìm chiến lược M30/H1: 9 hướng, và lý do cấu trúc khiến chúng đổ

> Ngày 13/08/2026 · Yêu cầu: _"phải tìm được chiến lược cho m30, đặc biệt là H1"_
> Kết quả: **chưa tìm được chiến lược nội ngày nào qua được cổng kiểm định.**
> Tài liệu này ghi lại đầy đủ những gì đã thử, đo được bao nhiêu, và VÌ SAO.

---

## 0. Kết luận thẳng

Tôi đã thử **9 hướng** ở khung M30/H1. Không hướng nào qua được cổng. Và có một
phép đo giải thích tất cả:

> **Quét hệ số thông tin (IC) trên 7 cặp × 15 đặc trưng × 5 horizon ở H1:
> |IC| lớn nhất = 0,0180.**

Với chi phí khứ hồi 0,9–2,9 bps ở H1, một IC cỡ đó không đủ để trả chi phí. Đây
không phải "chưa tìm ra cách" — đây là một đặc tính đo được của dữ liệu.

Tôi **không** báo cáo một chiến lược nội ngày để đáp ứng yêu cầu, vì làm vậy sẽ là
đưa một thứ đã trượt kiểm định vào tiền thật.

---

## 1. Số học chi phí — gốc rễ của toàn bộ vấn đề

| khung           | chi phí khứ hồi     | tín hiệu đo được  | tỷ lệ         |
| --------------- | ------------------- | ----------------- | ------------- |
| H1 (rổ 7 cặp)   | **1,657 bps**       | 0,1–0,5 bps       | **0,06–0,30** |
| H1 (EURUSD đơn) | 0,89 bps            | ~0,2 bps          | 0,22          |
| D1, giữ 21 ngày | 1,657 bps / 21 ngày | 2,3 bps/ngày × 21 | **~29**       |

Chiến lược D1 thắng không phải vì tín hiệu mạnh hơn, mà vì nó **chia chi phí cho
21 ngày**. Ở H1 không có cách nào làm điều đó mà vẫn còn là H1.

---

## 2. Chín hướng đã thử

| #   | hướng                                | cơ sở                             | kết quả                                                                   |
| --- | ------------------------------------ | --------------------------------- | ------------------------------------------------------------------------- |
| 1   | 8 price-action family (từ hệ XAUUSD) | The Cheopard                      | 28/33 NO_INFORMATION; MFE/\|MAE\| ≈ 1,00                                  |
| 2   | Fix reversal theo giờ                | Krohn _JoF_ 2024                  | tín hiệu THẬT (t = −3,83) nhưng ≈ 1 lượt khứ hồi; OOS −1,34; DSR = 0,0000 |
| 3   | RSI-difference pairs H1              | Jirapongpan IEEE                  | chính tác giả báo không đạt; không lặp lại                                |
| 4   | ML lọc lệnh                          | —                                 | < 60% CV, OOS bất định                                                    |
| 5   | Cắt ngang cuộn H1                    | mở rộng từ chiến lược D1 đã thắng | \|t\| max 1,75 / 72 phép thử                                              |
| 6   | Cắt ngang neo phiên                  | Breedon & Ranaldo SNB             | gross 0,1–0,36 bps vs chi phí 1,657                                       |
| 7   | Đảo chiều có điều kiện khối lượng    | Campbell-Grossman-Wang _QJE_ 1993 | **dự đoán bị bác bỏ** (chi tiết §3)                                       |
| 8   | Cắt ngang lưới H1, backtest đủ       | GEMINI (project-refer)            | reversal DEV −0,24/OOS +1,43 bất ổn; momentum **mọi ô âm**                |
| 9   | Fade phản ứng thái quá sau tin       | vi cấu trúc thông báo             | edge THẬT nhưng **không với tới được** (§4)                               |

---

## 3. Hướng 7 — một giả thuyết tốt bị dữ liệu bác bỏ

Campbell, Grossman & Wang (1993) cho một cơ chế đẹp: khối lượng phân biệt dịch
chuyển do THÔNG TIN với dịch chuyển do THANH KHOẢN.

**Dự đoán ghi TRƯỚC khi nhìn số:**

```
dịch chuyển lớn + khối lượng THẤP  -> thanh khoản -> fade CÓ LÃI
dịch chuyển lớn + khối lượng CAO   -> thông tin   -> fade LỖ
```

**Đo được (trung bình 7 cặp, H1, tick volume chuẩn hoá theo giờ):**

```
VOL_THẤP  cost_ratio −0,079        <- dự đoán DƯƠNG
VOL_CAO   cost_ratio +0,264        <- dự đoán ÂM
```

**Ngược hoàn toàn.** 0/7 cặp vượt chi phí ở bất kỳ ô nào của lưới (4 ngưỡng sốc ×
4 thời gian giữ).

Đây là kết quả có giá trị: nó nói rằng trên FX giao ngay, **tick volume không mang
thông tin phân biệt** như volume thật trên thị trường tập trung. Hợp lý — tick
volume đếm số lần báo giá đổi, và báo giá đổi nhiều nhất khi thị trường CĂNG THẲNG,
tức nó đo cùng thứ với biến động chứ không đo dòng lệnh.

---

## 4. Hướng 9 — edge thật nhưng không với tới được

Đây là hướng nội ngày gần thành công nhất, và cách nó thất bại đáng ghi lại.

**Tín hiệu có thật, rất mạnh:**

- Nến M30 chứa tin dịch chuyển **4–6 lần** bình thường:
  EURUSD 15,88 bps (NFP) vs nền 3,12 · USDJPY 19,96 vs 3,46 · GBPUSD 17,47 vs 3,53
- Fade cú sốc đó cho net **+3,05 bps sau chi phí** (hold 4 nến M30)
- **Control: p = 0,0000, phân vị 100%** — 200 lần rút thời điểm ngẫu nhiên, không
  lần nào đạt tới kết quả thật

**Nhưng nó không giao dịch được:**

| vào lệnh                   | t-stat    |
| -------------------------- | --------- |
| ngay nến tin (delay = 0)   | **+1,64** |
| chậm 1 nến M30 (delay = 1) | **+0,47** |
| chậm 2 nến M30             | −0,44     |

Edge nằm **đúng ở nến có spread rộng nhất trong ngày**. Chờ 30 phút cho spread co
lại thì edge biến mất. Backtest dùng spread TRUNG VỊ của cặp — tức đã đánh giá thấp
chi phí thật ở chính thời điểm đó.

Cộng thêm: OOS t chỉ 0,10–0,74; chết ở chi phí ×5; và phụ thuộc nặng vào 2022
(+12,66 bps) trong khi 2023 (−2,60) và 2026 (−1,69) âm.

➤ Đây là dạng thất bại đặc trưng của alpha nội ngày FX: **edge tồn tại đúng ở nơi
chi phí lớn nhất**, và hai thứ đó triệt tiêu nhau không phải ngẫu nhiên — người tạo
lập giãn spread CHÍNH VÌ họ biết ở đó có rủi ro chọn lọc bất lợi.

---

## 5. Một lỗi tôi mắc và đã bắt được — ghi lại để không tái diễn

Ở vòng 20, script backtest H1 momentum cho **Sharpe +1,744, DEV 1,955 / OOS 1,335,
7/7 năm dương, control p = 0,0000**. Trông như đã tìm được chiến lược H1.

Nó sai. Lỗi look-ahead:

```python
if i >= lb and i % hold == 0:
    s, v = Sv[i], Vv[i]      # tín hiệu TẠI bar i — chứa F[i]
W[i] = held
gross[i] = W[i] · F[i]        # rồi ăn chính F[i]
```

Với momentum, đồng có `F[i]` cao nhất được gán trọng số long, rồi ăn đúng `F[i]` đó
— tức "dự báo F[i] bằng F[i]".

Sau khi sửa thành `Sv[i-1], Vv[i-1]`: **mọi ô đều âm** (−0,54 đến −1,38), không ô
nào có cả DEV lẫn OOS dương.

Đã kiểm lại toàn bộ module đang dùng: `currency_reversal.target_weights` dùng
`signal.iloc[i-1]`, `regime_is_crisis` dùng `.shift(1)` ở cả giá trị lẫn ngưỡng,
`news_overreaction` tính sốc từ nến đã đóng rồi vào ở close nến đó. **Không module
nào trong hệ đang chạy dính lỗi này.**

---

## 6. Bằng chứng cấu trúc: quét IC

Nếu tồn tại alpha H1, nó phải hiện ra ở tương quan giữa MỘT đặc trưng nào đó với
lợi nhuận tương lai. Quét 15 đặc trưng (lợi nhuận trễ 1-120 bar, biên độ, khối
lượng, spread, khoảng cách EMA, IBS, RSI, giờ, thứ) × 5 horizon × 7 cặp:

```
|IC| lớn nhất = 0,0180        (ret_120 → h24, nhất quán 7/7 cặp)
```

Các đặc trưng nhất quán nhất, tất cả đều ÂM (tức đảo chiều):
| đặc trưng | horizon | IC trung bình | nhất quán |
| --------- | ------- | ------------- | --------- |
| ret_120 | h24 | −0,0180 | **7/7** |
| ibs | h1 | −0,0148 | 6/7 |
| ret_1 | h1 | −0,0131 | 6/7 |
| vol_x_ret | h1 | −0,0108 | 6/7 |

Mọi thứ đều chỉ về **đảo chiều**, và tín hiệu mạnh nhất là ở horizon **DÀI NHẤT**
(ret_120 → h24, tức 5 ngày dự báo 1 ngày). Đó chính là hiệu ứng mà chiến lược D1
đang khai thác — và nó **mạnh dần theo thời gian giữ**, không phải yếu đi.

➤ Kết luận cấu trúc: **đảo chiều tiền tệ là hiện tượng thang NHIỀU NGÀY.** Cố ép
nó xuống H1 làm giảm tín hiệu và tăng chi phí cùng lúc.

---

## 7. Vậy H1 đóng vai trò gì trong hệ này

H1 **không** phải nơi sinh tín hiệu, nhưng nó không phải trang trí:

1. **Chọn giờ khớp lệnh** — đo được: 15:00 UTC 1,6567 bps vs 22:00 UTC 2,3043 bps
   (đắt hơn 1,39 lần). Cấm giao dịch 20:00–23:00 UTC (cửa sổ rollover).
2. **Cổng chặn thực thi** — `currency_reversal.execution_ok()` đánh giá theo nến H1,
   tách khỏi tầng tín hiệu (Dempster & Leemans 2004 tầng 1 vs tầng 2).
3. **Giám sát rủi ro** — chính sách đòn bẩy tính lại mỗi ngày trên equity thật.

Đây là vai trò mà bằng chứng ủng hộ. Gán cho H1 vai trò sinh tín hiệu sẽ là gán một
việc mà dữ liệu nói nó không làm được.

---

## 8. Nếu muốn tiếp tục săn alpha nội ngày — cần gì

Chín hướng đã thử đều dùng **dữ liệu OHLCV + lịch tin**. Để có cơ hội thật ở H1/M30
cần nguồn dữ liệu mà hiện chưa có:

1. **Dòng lệnh thật (order flow)** — không phải tick volume. Đây là biến giải thích
   phần lớn biến động tỷ giá ngắn hạn trong tài liệu vi cấu trúc (Evans & Lyons).
   Cần dữ liệu từ nền tảng liên ngân hàng (EBS/Reuters) — retail không có.
2. **Độ sâu sổ lệnh** — để biết spread rộng vì thiếu thanh khoản hay vì rủi ro.
3. **Dữ liệu đồng thuận dự báo** — để đo BẤT NGỜ của tin (actual − consensus) thay
   vì chỉ đo phản ứng giá. Đây là thứ sẽ cứu hướng 9: biết bất ngờ thì vào được
   TRƯỚC khi spread giãn, thay vì phản ứng sau.
4. **Vũ trụ rộng hơn** — 7 cặp là mặt cắt hẹp. Thêm SEK/NOK/cross làm phép xếp hạng
   có nhiều bậc tự do hơn.

Trong bốn thứ đó, **(3) khả thi nhất với chi phí hợp lý** (nhiều nhà cung cấp lịch
kinh tế bán kèm consensus) và nó nhắm đúng hướng đã chứng minh có tín hiệu thật.

---

## 9. Trạng thái danh mục

```
CHIẾN LƯỢC ĐÃ ĐĂNG KÝ (src/python/strategies/registry.py)
tên                signal  exec  stage         Sharpe ALL   OOS    MaxDD
CurrencyReversal   D1      H1    FORWARD_TEST      0.576   0.395    8.27%
CurrencyCarry      D1      H1    FORWARD_TEST      0.151   0.745   10.37%

DANH MỤC VẬN HÀNH: TwoLegFX  ·  trần đòn bẩy 4x
  Sharpe ALL 0.721 · OOS 1.132 · MaxDD 5.28%

ĐÃ BÁC BỎ: 10 hướng, mỗi hướng kèm lý do và đường dẫn bằng chứng
```

Cấu trúc thư mục theo khung tín hiệu (quy ước The Cheopard):

```
src/python/strategies/
├── registry.py          SSOT — khai báo, không chứa logic
├── d1/  currency_reversal.py · currency_carry.py     ← đang dùng
├── m30/ news_overreaction.py                          ← giữ làm bản ghi, KHÔNG chạy
├── h1/  (trống — chưa có chiến lược nào qua cổng)
└── h4/  (trống)
```

`m30/news_overreaction.py` được **giữ lại có chủ ý** dù đã bác bỏ: nó là hướng nội
ngày duy nhất có control p = 0,0000, và nếu sau này có dữ liệu consensus thì đó là
điểm khởi đầu chứ không cần dựng lại từ đầu.
