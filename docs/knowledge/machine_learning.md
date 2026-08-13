# KB — Học máy trong tài chính: gán nhãn, meta-label, kiểm định chéo

## References

| # | nguồn | chương / trang | nguyên lý lấy ra |
|---|---|---|---|
| [A] | López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley. | Ch. 3 "Labeling", tr. 43-57 | phương pháp ba rào; meta-labeling; bỏ nhãn hiếm |
| [B] | López de Prado (2018) | Ch. 7 "Cross-Validation in Finance", tr. 103-111 | vì sao k-fold hỏng trong tài chính; thanh trừng; cấm vận |
| [C] | López de Prado (2018) | Ch. 4 "Sample Weights", tr. 59-73 | tính duy nhất của mẫu; bootstrap tuần tự |
| [D] | López de Prado (2018) | Ch. 6 "Ensemble Methods", tr. 93-102 | bagging, dư thừa quan sát |

---

## 1. Phương pháp BA RÀO — [A] tr. 45-47

Gán nhãn một quan sát theo **rào chạm đầu tiên** trong ba rào:

* hai rào ngang: chốt lời và cắt lỗ, **là hàm động của biến động ước lượng**;
* một rào dọc: số nến đã trôi qua kể từ khi vào lệnh (hạn giữ).

Chạm rào trên → nhãn `1`; rào dưới → `−1`; rào dọc → hoặc dấu của lợi suất, hoặc
`0`. Tác giả thích cách thứ nhất.

> "the triple-barrier method is **path-dependent**. In order to label an
> observation, we must take into account the entire path spanning [t₀, t₀+h]."

Ký hiệu cấu hình `[pt, sl, t1]`, `1` là bật, `0` là tắt. Tám cấu hình, chia ba
nhóm ([A] tr. 46):

| nhóm | cấu hình | ý nghĩa |
|---|---|---|
| **hữu ích** | `[1,1,1]` | chuẩn: có chốt lời, có cắt lỗ, có hạn giữ |
| | `[0,1,1]` | thoát sau N nến trừ khi bị cắt lỗ trước |
| | `[1,1,0]` | chốt lời miễn chưa bị cắt lỗ — giữ vô thời hạn, hơi thiếu thực tế |
| ít thực tế | `[0,0,1]` | tương đương chân trời thời gian cố định |
| | `[1,0,1]` | giữ tới khi có lãi hoặc hết hạn, bỏ qua lỗ chưa thực hiện |
| | `[1,0,0]` | giữ tới khi có lãi — có thể kẹt lệnh thua nhiều năm |
| **phi lý** | `[0,1,0]` | giữ tới khi bị cắt lỗ — vô định hướng |
| | `[0,0,0]` | không rào nào; khoá vĩnh viễn, không sinh nhãn |

### Đối chiếu: hệ thống ĐÃ dùng đúng cấu trúc này mà chưa từng gọi tên

| chiến lược | pt | sl | t1 | cấu hình | xếp loại theo [A] |
|---|---|---|---|---|---|
| `DonchianH4Breakout` | không | 1,5×ATR | 12 nến H4 | `[0,1,1]` | **hữu ích** |
| `SwingDon` | không | 2,5×ATR | trailing Chandelier | `[0,1,0]`+trailing | xem ghi chú |
| `PaPullbackH4` | 2R | 1×ATR | — | `[1,1,0]` | **hữu ích** |
| `SqueezeBreakdown` (đã bác bỏ) | không | 1,5×ATR | 48 nến H1 | `[0,1,1]` | **hữu ích** |

Ghi chú `SwingDon`: nếu chỉ nhìn ba rào tĩnh thì nó là `[0,1,0]` — nhóm "phi
lý" theo [A]. Nhưng nó có **trailing stop**, tức rào dưới di chuyển lên theo
đỉnh. Tài liệu không xét trường hợp rào động; trailing biến `[0,1,0]` thành một
cơ chế thoát có giới hạn thực tế. **[suy luận của ta]** — không kết luận
`SwingDon` sai thiết kế, nhưng ghi nhận nó là cấu hình duy nhất không nằm gọn
trong khung của tài liệu.

**Giá trị của việc gọi tên:** ba rào cho một *ngôn ngữ chung* để so sánh chiến
lược, và quan trọng hơn, nó là **cách sinh nhãn cho mô hình học máy** — điều dự
án chưa khai thác.

## 2. META-LABELING — [A] tr. 50-53

### Vấn đề mà nó giải

> "Suppose that you have a model for setting the side of the bet (long or short).
> You just need to learn the **size** of that bet, which includes the possibility
> of **no bet at all** (zero size)... We do not want the ML algorithm to learn the
> side, just to tell us what is the appropriate size."

Mô hình **sơ cấp** quyết định CHIỀU. Mô hình **thứ cấp** học từ nhãn nhị phân
`{0, 1}`: lệnh mà mô hình sơ cấp đề xuất có sinh lãi không?

Khác biệt then chốt về gán nhãn ([A] tr. 51):

```
Trường hợp 1 (không có 'side'): nhãn ∈ {−1, 1} — gán theo hành động giá
Trường hợp 2 (có 'side'):       nhãn ∈ {0, 1}  — gán theo lãi/lỗ (meta-label)
```

Và một ràng buộc dễ bỏ sót ([A] tr. 48, 50):

* Khi **học chiều**: rào ngang **phải đối xứng** — vì chưa biết chiều thì không
  phân biệt được đâu là chốt lời đâu là cắt lỗ.
* Khi **meta-label**: chiều đã biết, nên rào ngang **được phép bất đối xứng**.

### Áp được vào đâu — và phải xem lại kết luận cũ

> "You can always add a meta-labeling layer to **any** primary model, whether
> that is an ML algorithm, an econometric equation, **a technical trading rule**,
> a fundamental analysis, etc."

Bốn chiến lược LIVE đều là luật kỹ thuật sinh CHIỀU. Chúng là mô hình sơ cấp
hoàn chỉnh theo đúng nghĩa [A] dùng. Tầng meta-label sẽ học *khi nào nên bỏ qua
tín hiệu*, và trả về xác suất dùng để định cỡ lệnh.

Nhật ký dự án ghi meta_label "kết luận âm tính" (23/07). **Cần kiểm lại xem bản
cài đặt ấy có đúng cấu trúc trong [A] không** — cụ thể ba điểm:

1. nhãn có phải `{0,1}` theo lãi/lỗ của lệnh sơ cấp, hay vẫn là `{−1,1}` theo
   hành động giá;
2. rào có phải ba rào với hạn giữ đúng bằng hạn giữ thật của chiến lược;
3. xác suất đầu ra có được dùng để **định cỡ** không, hay chỉ dùng làm cổng
   chặn nhị phân.

Nếu bản cũ chỉ là cổng chặn nhị phân thì nó không phải meta-labeling theo [A],
và kết luận âm tính không áp dụng cho phương pháp thật.

Tác giả nhấn mạnh lý do thứ tư khiến meta-labeling đáng giá ([A] tr. 53):

> "achieving high accuracy on small bets and low accuracy on large bets will ruin
> you. As important as identifying good opportunities is to size them properly,
> so it makes sense to develop an ML algorithm solely focused on getting that
> critical decision (sizing) right."

## 3. Vì sao k-fold CV HỎNG trong tài chính — [B] tr. 104-105

> "By now you may have read quite a few papers in finance that present k-fold CV
> evidence that an ML algorithm performs well. **Unfortunately, it is almost
> certain that those results are wrong.**"

Hai nguyên nhân:

1. **Quan sát không độc lập cùng phân phối.** Đặc trưng `X` có tự tương quan nên
   `Xₜ ≈ Xₜ₊₁`; nhãn dựng trên dữ liệu chồng lấn nên `Yₜ ≈ Yₜ₊₁`. Đặt `t` và
   `t+1` vào hai tập khác nhau là **rò rỉ thông tin**.
2. Tập kiểm thử bị dùng nhiều lần trong quá trình phát triển → kiểm định bội và
   thiên lệch chọn lọc.

Điều kiện chính xác của rò rỉ ([B] tr. 105) — đáng chú ý vì nó hẹp hơn ta tưởng:

> "Consider the case where Xᵢ and Xⱼ are formed on overlapping information...
> Is this a case of informational leakage? **Not necessarily, as long as Yᵢ and
> Yⱼ are independent.** For leakage to take place, it must occur that
> (Xᵢ,Yᵢ) ≈ (Xⱼ,Yⱼ), and it does not suffice that Xᵢ ≈ Xⱼ or even Yᵢ ≈ Yⱼ."

Và điểm nguy hiểm nhất:

> "If X is a predictive feature, leakage will **enhance** the performance of an
> already valuable strategy. **The problem is leakage in the presence of
> irrelevant features, as this leads to false discoveries.**"

## 4. Thanh trừng và cấm vận — [B] tr. 105-108

**Thanh trừng (purging):** loại khỏi tập huấn luyện mọi quan sát có nhãn **chồng
lấn thời gian** với nhãn trong tập kiểm thử. Nhãn `Yᵢ = f[[tᵢ₀, tᵢ₁]]` chồng lấn
với `Yⱼ` nếu thoả một trong ba điều kiện:

```
1.  t_{j,0} ≤ t_{i,0} ≤ t_{j,1}
2.  t_{j,0} ≤ t_{i,1} ≤ t_{j,1}
3.  t_{i,0} ≤ t_{j,0} ≤ t_{j,1} ≤ t_{i,1}
```

**Cấm vận (embargo):** loại thêm các quan sát huấn luyện nằm **ngay sau** tập
kiểm thử, vì chuỗi tài chính có tự tương quan kiểu ARMA. Chỉ cần chặn phía sau,
không cần phía trước — nhãn kết thúc trước khi kiểm thử bắt đầu chỉ chứa thông
tin đã có tại thời điểm kiểm thử.

> "A small value h ≈ .01T often suffices to prevent all leakage."

### Phép chẩn đoán rò rỉ — dùng được ngay, không cần cài gì

> "When leakage takes place, **performance improves merely by increasing k → T**,
> where T is the number of bars... In many cases, purging suffices to prevent
> leakage: Performance will improve as we increase k, because we allow the model
> to recalibrate more often. But beyond a certain value k\*, performance will not
> improve, indicating that the backtest is not profiting from leaks."

**Áp dụng:** đây là một phép kiểm rẻ và mạnh mà dự án chưa từng chạy — tăng số
fold và xem hiệu suất có tăng vô hạn không. Nếu có, đang rò rỉ.

## 5. Hai cách giảm rò rỉ ngoài thanh trừng — [B] tr. 105

1. Loại khỏi tập huấn luyện mọi quan sát `i` mà `Yᵢ` là hàm của thông tin dùng
   để xác định `Yⱼ` với `j` thuộc tập kiểm thử.
2. **Tránh overfit bộ phân loại** — kể cả có rò rỉ thì nó cũng không khai thác
   được:
   * dừng sớm các bộ ước lượng cơ sở;
   * bagging có kiểm soát lấy mẫu quá mức trên ví dụ dư thừa: đặt `max_samples`
     bằng **độ duy nhất trung bình**, và dùng **bootstrap tuần tự** ([C]).

## 6. Bỏ nhãn quá hiếm — [A] tr. 54

Một số bộ phân loại hoạt động kém khi lớp quá mất cân bằng. Hàm `dropLabels` loại
đệ quy các lớp xuất hiện dưới một tỉ lệ `minPct` (mặc định 5%), trừ khi chỉ còn
hai lớp.

**Liên quan tới dự án:** `SqueezeBreakdown` có tỉ lệ thắng 22%, `MeanRevDip` 24,8%
— chưa tới mức phải bỏ nhãn, nhưng đủ mất cân bằng để cần trọng số lớp.

## 7. Việc phải làm

| # | việc | mức ưu tiên | căn cứ |
|---|---|---|---|
| 1 | Kiểm lại bản `meta_label` cũ có đúng cấu trúc [A] không (nhãn `{0,1}` theo lãi/lỗ, ba rào khớp hạn giữ thật, xác suất dùng để định cỡ) | cao | [A] tr. 50-53 |
| 2 | Chạy **phép chẩn đoán rò rỉ**: tăng `k` và xem hiệu suất có tăng vô hạn không | cao | [B] tr. 106 |
| 3 | Nếu có tầng ML nào dùng CV, thay bằng **purged k-fold có cấm vận** `h ≈ 0,01T` | cao | [B] tr. 105-108 |
| 4 | Ghi cấu hình ba rào `[pt, sl, t1]` vào docstring từng chiến lược — ngôn ngữ chung để so sánh | thấp | [A] tr. 46 |
| 5 | Xem lại `SwingDon`: cấu hình `[0,1,0]` cộng trailing, nằm ngoài khung tài liệu | thấp | [A] tr. 46 |
