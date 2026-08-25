"""asia_sweep.py — AsiaSweepH1. CHIẾN LƯỢC DUY NHẤT của The Cheopard Forex.

EURUSD · GBPUSD · USDJPY  ·  bối cảnh H1  ·  phát hiện & KHỚP LỆNH H1  ·  BOTH
Asia Range Sweep / ICT Judas Swing — vào NGƯỢC cú quét thanh khoản biên phiên Á.

┌─ QUY TẮC VÀO LỆNH ────────────────────────────────────────────────────────────┐
│  BỐI CẢNH  (chốt lúc 07:00 UTC, không vào lệnh trước mốc này)                 │
│     L2 biên Á      = high/low của M1 trong 00:00-06:59 UTC                    │
│     L3 thanh khoản = PDH/PDL + cực trị 5 phiên đã đóng                        │
│     L6 thiên hướng = close H1 vs EMA50 tại nến đóng lúc 07:00 UTC             │
│                                                                               │
│  VÀO   (đủ CẢ, trên nến H1 ĐÃ ĐÓNG, cửa sổ 07:00-20:00 UTC)                   │
│     a. biên Á trong dải pip của cặp                                           │
│     b. nến H1 xuyên biên trong dải độ sâu                                     │
│     c. nến đó ĐÓNG trở lại TRONG biên Á       ← quét THẤT BẠI, không breakout │
│     d. MSS xác nhận trong 3 nến               ← BỘ LỌC QUYẾT ĐỊNH             │
│     e. hạng setup >= A                                                        │
│     f. còn chỗ tới biên Á đối diện            ← chưa đi hết biên              │
│     g. NGOÀI ±30 phút quanh NFP · CPI · FOMC · ECB · BOE                      │
│     → khớp tại giá MỞ nến H1 KẾ TIẾP NẾN XÁC NHẬN MSS                         │
│                                                                               │
│  THOÁT   MỘT dừng lỗ, MỘT chốt lời, MỘT lần dời breakeven. Hết.               │
│     SL  = cực trị nến quét ± đệm pip, trên SERVER broker CÙNG lệnh mở         │
│     TP  = giá vào + 3R, chốt TOÀN BỘ vị thế         → R:R cố định 1:3         │
│     BE  = khi đạt +1R, dời SL về giá vào + ĐÚNG phí khứ hồi                   │
│     đóng hết 20:00 UTC — chiến lược TRONG PHIÊN                                │
│                                                                               │
│  VỊ THẾ  tối đa 1 / công cụ · tối đa 1 lần vào lệnh / công cụ / phiên          │
│  CHẶN    rủi ro mở <= 1,50%/đồng tiền và <= 4,00%/ngày · spread vượt trần ·    │
│          dữ liệu ôi · mọi cổng `entry_gate` (fail-closed)                      │
└───────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
BỘ LỌC MSS LÀ TOÀN BỘ GIÁ TRỊ CỦA CHIẾN LƯỢC NÀY — VÀ NÓ ĐƯỢC ĐO
═══════════════════════════════════════════════════════════════════════════════
Cùng bộ luật, chỉ khác việc CÓ đòi MSS xác nhận hay không. Đủ chi phí (spread THẬT
tại phút khớp + commission $7/lot khứ hồi), 11,5 năm EURUSD / 6,5 năm hai cặp kia:

    hạng A (CÓ MSS)        n = 462 · thắng 58,2% · R gộp +0,0601 · R ròng +0,0124
    hạng B (KHÔNG MSS)     n = 2.437 · thắng 15-19% · R ròng -0,56 đến -0,70
                                                     (t = -22,4 / -16,9 / -13,7)

Chênh lệch 0,7 R mỗi lệnh. MSS không phải một chỉ báo trang trí — nó là điều kiện
phân biệt cú quét THẤT BẠI (giá đảo và xác nhận bằng một close) với cú quét THÀNH
CÔNG (giá chảy tiếp, đúng như Osler sr150 dự đoán). Không có nó, chiến lược này là
một cái máy mất tiền có ý nghĩa thống kê.

⚠️ MỘT LỖI NHÌN TRƯỚC ĐÃ BỊ BẮT Ở ĐÚNG CHỖ NÀY, 25/08/2026
==========================================================
Bản đầu của `_mss_confirm` trả `bool` "có MSS trong 3 nến sau cú quét", nhưng lệnh
khớp ở giá MỞ nến ngay sau nến quét — tức dùng CLOSE của 1 đến 3 GIỜ SAU khi vào
lệnh. Nó cho ra một kết quả trông rất giống phát hiện:

    hạng A   thắng 73,0% / 77,0% / 67,8% · R ròng +0,74 / +0,76 / +0,71
             t = +14,6 / +12,6 / +8,1

Tách hạng hoàn hảo trên cả ba cặp với t hai chữ số là chữ ký VÒNG LẶP KÍN: "MSS đã
xảy ra" nghĩa là giá ĐÃ đi đúng chiều sau khi vào lệnh. Bản sửa khớp lệnh ở nến KẾ
TIẾP nến xác nhận, và toàn bộ hiệu ứng biến mất — còn +0,0124 R. Chi tiết ở docstring
`asia_sweep_core._mss_confirm`.

═══════════════════════════════════════════════════════════════════════════════
SỐ ĐO ĐẦY ĐỦ — ĐỌC TRƯỚC KHI NẠP TIỀN
═══════════════════════════════════════════════════════════════════════════════
preset MSS — ĐANG BẬT. Đủ chi phí (spread THẬT tại phút khớp + commission $7/lot
khứ hồi), 11,5 năm EURUSD / 6,5 năm hai cặp kia, cùng đường code với live.

    công cụ    n    lệnh/tuần  thắng%  SL pip  phí R   R gộp    R ròng    t
    EURUSD    620     1,03      44,35   27,0   0,037  +0,0564  +0,0177  +0,43
    GBPUSD    323     0,96      39,94   35,0   0,042  +0,0503  +0,0049  +0,09
    USDJPY    313     0,92      47,60   32,2   0,041  +0,0640  +0,0187  +0,34
    rổ 3 cặp 1256     2,91      44,03   31,0   0,040  +0,0567  +0,0147  +0,52

    R:R KHAI 3,00 (hằng số) · R:R THỰC HIỆN 1,32
    lãi TB thắng +0,873R · lỗ TB thua -0,660R · winrate hoà vốn 43,1% (đang 44,0%)
    Profit Factor 1,040 · chuỗi thua dài nhất 14 · giữ trung vị 300 phút
    8/12 năm dương

    FORM (< 2024-01-01)  -0,0023 (n = 882)      OOS  +0,0547 (n = 374)

⚠️ ĐỌC HAI DÒNG FORM/OOS TRƯỚC MỌI DÒNG KHÁC. FORM gần đúng BẰNG KHÔNG trên 882 lệnh;
toàn bộ phần dương nằm ở 374 lệnh OOS. Đó KHÔNG phải chữ ký overfit thông thường
(thường là FORM đẹp, OOS sụp), nhưng nó nói một điều rõ ràng: giai đoạn hiệu chỉnh
KHÔNG có biên nào, và t = +0,52 toàn mẫu không phân biệt được với ngẫu nhiên.

CHỈ 3,7% LỆNH CHẠM ĐƯỢC TP 3R. Phân bố kết cục: 58,5% đóng ở mốc 20:00 UTC (+0,306 R
trung bình) · 28,0% dừng lỗ (-1,041) · 10,0% breakeven (0,000) · 3,7% chốt lời
(+2,948). Nguyên nhân cơ học: SL trung vị 31 pip nên TP 3R cách 93 pip, và một chiến
lược đóng trong phiên chỉ còn khoảng 4 giờ để đi hết khoảng đó.

Quy ra tiền, tài khoản FTMO $100.000, lãi KÉP trên 4.212 ngày:

    rủi ro/lệnh    lãi/năm   MaxDD từ đỉnh   ngày tệ nhất   ghi chú
    0,20%          +0,30%     -6,47%         -0,629%
    0,25%          +0,36%     -8,06%         -0,787%        mức có đệm
    0,27%          +0,39%     -8,70%         -0,849%        TRẦN tuân thủ sàn 9%
    0,30%          +0,42%     -9,64%         -0,944%        vượt sàn 9%
    0,35% ĐANG     +0,48%    -11,21%         -1,101%        vượt sàn 9% VÀ luật 10%

⚠️⚠️ MỨC RỦI RO ĐANG DÙNG VƯỢT CẢ HAI HẠN MỨC — QUYẾT ĐỊNH ĐƯỢC KHAI BÁO

    MaxDD từ đỉnh  -11,21%   vs sàn nội bộ -9,00%  vs luật FTMO -10,00%   VƯỢT CẢ HAI
    ngày tệ nhất    -1,101%  vs trần nội bộ -4,00%  vs mốc ngày -5,00%     đạt
    mục tiêu lợi nhuận FTMO 10%                                            KHÔNG ĐẠT

Chủ tài khoản chọn 0,35% sau khi đã được trình bày bảng trên, với lập luận rằng số
backtest chỉ mang tính tham khảo. Quyết định ghi ở
`registry.PORTFOLIO["dd_floor_override"]`, và `tests/test_portfolio_single_leg.py` đòi
khoá đó phải tồn tại khi MaxDD đo được vượt sàn — nên việc vượt sàn KHÔNG đi qua âm
thầm, nó phải được ai đó viết ra. Trần tuân thủ nếu muốn quay lại: **0,27%**.

Và MaxDD thật sẽ còn sâu hơn -11,21%: backtest không có trượt giá, không có spread
giãn, không có gap cuối tuần và không có lệnh bị broker từ chối.

+0,48%/năm thì một vòng thử thách 10% mất khoảng hai mươi mốt năm.

═══
XUNG ĐỘT VỚI YÊU CẦU 4-8 LỆNH/TUẦN — PHẢI NÓI RÕ
═══════════════════════════════════════════════════════════════════════════════
Trên H1 với ba cặp, tần suất bị chặn cứng bởi số phiên có nến H1 vừa xuyên biên, vừa
đóng lại trong biên, VÀ có MSS xác nhận trong 3 nến. Đo được:

    preset       lệnh/tuần   R ròng/lệnh   ghi chú
    MSS (bật)      1,08        +0,0903     hạng A + một SL một TP + cổng tin
    FREQ           7,90        -0,0835     nhận cả hạng B; đạt 4-8 nhưng MẤT TIỀN
    SPEC           0,58        -0,1654     ngưỡng hẹp của tài liệu tham khảo

Đạt 4-8 lệnh/tuần đòi nhận hạng B, và hạng B mất **0,65 R mỗi lệnh** với t = -22.
Ở 7,90 lệnh/tuần và 0,60% rủi ro, đó là -0,40%/tuần đơn điệu — chạm sàn 9% sau
khoảng 5 tháng. Nên preset MSS được chọn, và tần suất 1,10 lệnh/tuần là HỆ QUẢ của
việc lọc, không phải một lựa chọn.

Ba đường HỢP LỆ để tăng tần suất mà không nhận hạng B:
  1. thêm cặp — bốn cặp Tier 2 (AUDUSD, USDCAD, USDCHF, NZDUSD) hiện KHÔNG có parquet
     M1 trong `D:/data-ticks-train/_m1/`; phải dựng lại từ tick trước.
  2. hạ khung khớp lệnh xuống M15 — nhiều nến hơn thì nhiều lần xác nhận MSS hơn.
     Đã đo: M15 cho R ròng -0,2446 (SL 10,6 pip, chi phí ăn 0,114 R), TỆ HƠN H1
     (SL 28 pip, chi phí 0,046 R). Không nên.
  3. nới `mss_max_bars` 3 -> 6: thêm ~0,3 lệnh/tuần. KHÔNG CHỌN vì con số 3 có
     NGUỒN (Chesler 2004 hikkake, qua Kirkpatrick & Dahlquist tr. 379-380: đảo chiều
     phải xảy ra trong 3 nến) còn 6 là con số chọn theo kết quả. Không đáng đổi một
     tham số có nguồn thành một bậc tự do.

═══════════════════════════════════════════════════════════════════════════════
⚠️ HƯỚNG NÀY NẰM TRONG `registry.REJECTED_DIRECTIONS`
═══════════════════════════════════════════════════════════════════════════════
Tên `AsiaRangeSweepFade`. Bằng chứng: 4.963 lệnh (bản KHÔNG có cổng MSS), 0/54 ô lọc
đạt t > +2, 0/24 định nghĩa cửa sổ phiên Á cho R ròng dương, 24/24 ô có t < -2.
Osler (2003, FRBNY SR150) — nguồn mà hai file docs tham khảo trích làm cơ sở — kết
luận NGƯỢC: cụm stop-loss làm giá CHẢY TIẾP (còn ý nghĩa >= 2 giờ), đảo chiều thuộc
cụm take-profit và chết DƯỚI 30 phút. Neely & Weller (JIMF 2003) và Hsu-Taylor-Wang
(JIE 2016) cùng phía. Số đo đầy đủ: `docs/the-asia-sweep/00_KET_QUA_DO_LUONG.md`.

Cổng MSS, việc bỏ chốt-một-phần, và cổng tin ±30 phút đưa hướng này từ **-0,65 R mỗi
lệnh** lên **+0,0903 R mỗi lệnh (t = +1,99)**, FORM và OOS đều dương. Đó là một cải
thiện THẬT và đo được — nhưng t = 1,99 trên 453 lệnh vẫn chưa qua ngưỡng của một phát
hiện, và +1,47%/năm chưa đủ cho một vòng thử thách 10%.

    stage = FORWARD_TEST, và KHÔNG được nâng lên LIVE cho tới khi demo cho số
    dương qua đủ 6 kiểm định + cổng PBO ở `docs/knowledge/research_process.md`.

`ftmo_leverage_policy.LEVERAGE_MAX` và `target_mode.NOTIONAL_GAP_WARN_X` được hiệu
chỉnh cho một danh mục KHÔNG có SL theo giá. Chiến lược này có SL cứng nên rủi ro
quản bằng **% equity mỗi lệnh** (`RISK_PCT_PER_TRADE`), không bằng đòn bẩy phơi
nhiễm — hai con số đó không còn ràng buộc đúng đại lượng nào. Xem
`registry.PORTFOLIO["can_do_lai"]`.

NGUỒN
=====
Đầy đủ ở docstring `asia_sweep_core`. Bốn nguồn quyết định thiết kế ở đây:
  · Osler (2003) FRBNY SR150 — cụm stop nằm trong ~10 pip quanh mốc; cơ sở dải độ
    sâu xuyên và đệm SL 3-4 pip; cửa sổ đảo chiều < 30 phút
  · Chesler (2004) hikkake qua Kirkpatrick & Dahlquist (2011) tr. 379-380 — đảo
    chiều phải xảy ra TRONG 3 NẾN; nguồn của `mss_max_bars = 3`
  · ICT 2022 Mentorship tr. 50-51 — MSS phải có displacement VÀ candle CLOSE
  · Grimes (2012) tr. 183-186 — fade theo việc giá xuyên LẠI mức là "a futile plan";
    tiêu chí đúng là THẤT BẠI của nhịp đầu tiên. Đây chính là cổng MSS.
"""
from __future__ import annotations

import dataclasses
from typing import Dict, List, Tuple

import pandas as pd

from src.python.strategies import asia_sweep_core as SC

NAME = "AsiaSweepH1"
TIMEFRAME = "H1"
EXECUTION_TF = "H1"

# Rổ giao dịch — ba cặp có rào chi phí THẤP NHẤT đo được (spread/ATR_H1 trung vị,
# H1 2020+): EURUSD 2,44% · USDJPY 2,73% · GBPUSD 5,00%. Bốn cặp Tier 2 có rào cao
# gấp 3,5-4 lần VÀ hiện KHÔNG có dữ liệu M1 trong `D:/data-ticks-train/_m1/` — phải
# dựng lại parquet từ tick trước khi thêm chúng vào rổ.
INSTRUMENTS: Tuple[str, ...] = ("EURUSD", "GBPUSD", "USDJPY")

# Rủi ro mỗi lệnh, % equity. Biến điều khiển rủi ro DUY NHẤT của chiến lược này —
# Đòn bẩy phơi nhiễm là HỆ QUẢ của nó, không phải đầu vào.
#
# ⚠️ 0,35% VƯỢT CẢ HAI HẠN MỨC. Đây là quyết định được KHAI BÁO, không phải sơ suất.
#
#     rủi ro/lệnh   MaxDD (lãi kép)   ghi chú
#        0,25%          -8,06%        mức có đệm
#        0,27%          -8,70%        TRẦN tuân thủ sàn 9%
#        0,30%          -9,64%        vượt sàn nội bộ 9%
#        0,35%         -11,21%        ĐANG DÙNG — vượt sàn 9% VÀ luật FTMO 10%
#
# Quyết định ghi ở `registry.PORTFOLIO["dd_floor_override"]`, và
# `tests/test_portfolio_single_leg.py` đòi khoá đó tồn tại khi MaxDD vượt sàn — nên
# việc vượt sàn phải do ai đó VIẾT RA, không đi qua âm thầm.
#
# Và MaxDD thật sẽ còn sâu hơn: backtest không có trượt giá, không có spread giãn,
# không có gap cuối tuần và không có lệnh bị broker từ chối.
RISK_PCT_PER_TRADE = 0.35

# Ba cặp cùng vào lệnh là 1,05% equity rủi ro mở. Hai trần chặn phía trên:
# `order_plan._DAILY_RISK_CAP_PCT` (4,00%) theo NGÀY và `_CURRENCY_RISK_CAP_PCT`
# (1,50%) theo ĐỒNG TIỀN — cái thứ hai cần vì cả ba cặp đều có chân USD, nên ba lệnh
# cùng chiều USD là MỘT cược gấp ba. Cả hai chặn được TRƯỚC khi gửi lệnh vì dừng lỗ
# cứng làm rủi ro mỗi lệnh là số ĐÃ BIẾT TRƯỚC.
MAX_CONCURRENT_POSITIONS = len(INSTRUMENTS)


# ═══════════════════════════════════════════════════════════ tham số theo cặp
# Ngưỡng gốc lấy từ bảng §III của `docs/the-asia-sweep/H1_INDUCEMENT_SWEEP_SPEC.md`
# (tài liệu THAM KHẢO, không phải đặc tả ràng buộc). USDJPY tài liệu không có số, nên
# suy theo ĐÚNG tỷ lệ hai cặp kia dùng so với biên Á trung vị ĐO ĐƯỢC:
#     biên Á trung vị   EURUSD 25,3 pip · GBPUSD 32,8 · USDJPY 45,3
#     dải tài liệu      EURUSD 15-45 = [0,59; 1,78] x TV · GBPUSD 20-55 = [0,61; 1,68]
#     suy cho USDJPY    27-80 pip    = [0,60; 1,77] x TV
# Đây là phép quy đổi ĐƠN VỊ, không phải một bậc tự do mới.
_SPEC: Dict[str, Dict[str, float]] = {
    "EURUSD": dict(range_min_pips=15.0, range_max_pips=45.0,
                   depth_min_pips=2.0, depth_max_pips=25.0,
                   sl_buffer_pips=3.0),
    "GBPUSD": dict(range_min_pips=20.0, range_max_pips=55.0,
                   depth_min_pips=3.0, depth_max_pips=35.0,
                   sl_buffer_pips=4.0),
    "USDJPY": dict(range_min_pips=27.0, range_max_pips=80.0,
                   depth_min_pips=3.0, depth_max_pips=35.0,
                   sl_buffer_pips=4.0),
}

# Sáu ngưỡng được NỚI để chiến lược có đủ mẫu chạy. Giữ RIÊNG khỏi `_SPEC` để đọc
# một cái là biết cái kia khác gì. Mỗi dòng ghi giá trị của tài liệu tham khảo.
#
# Đo được: dải hẹp của tài liệu + cổng MSS chỉ còn **9 lệnh trong 11,5 năm** — không
# phải một chiến lược, là một mẫu quá nhỏ để nói bất cứ điều gì.
_WIDE_BANDS: Dict[str, object] = dict(
    exec_end_utc=20.0,          # tài liệu: 15:00 (§III) / 12:00 (bộ luật rút gọn)
    use_bias=False,             # tài liệu đòi thuận H1 — đo được TẮT tốt hơn ở cả 3 cặp
    wick_body_min=0.0,          # tài liệu đòi râu >= 50% thân
    range_min_pips=8.0, range_max_pips=90.0,
    depth_min_pips=1.0, depth_max_pips=60.0,
)

# Cổng MSS — thứ tạo ra toàn bộ chênh lệch 0,7 R giữa hạng A và hạng B.
_MSS_GATE: Dict[str, object] = dict(require_mss=True, min_grade="A",
                                    mss_max_bars=3)

# KILLZONE — quyết định người vận hành 25/08/2026: chỉ săn tín hiệu trong hai cửa
# sổ thanh khoản mở phiên, KHÔNG dùng cửa sổ liên tục rộng của `_WIDE_BANDS` nữa.
#
#     London Open   14:00-17:00 giờ VN  = 07:00-10:00 UTC
#     NY Open       19:00-21:00 giờ VN  = 12:00-14:00 UTC
#
# `_WIDE_BANDS` nới `exec_end_utc` tới 20:00 UTC để có đủ mẫu (1.256 lệnh/11,5 năm)
# nhưng khoảng trũng thanh khoản 10:00-12:00 UTC và sau 14:00 UTC vẫn nằm TRONG cửa
# sổ đó — đúng loại "Late Sweep" mà lý thuyết vi cấu trúc thị trường cảnh báo, và
# t-stat đo được của preset MSS (+0,52) không đủ ý nghĩa thống kê để bác lại cảnh
# báo đó. Killzone áp dụng SAU `_WIDE_BANDS` nên `exec_start_utc`/`exec_end_utc` của
# nó bị bỏ qua — `exec_windows_utc` là nguồn chân lý khi đã khai báo.
#
# CHƯA ĐO expectancy của cấu hình này trên dữ liệu M1 thật — cần chạy lại
# `research/fx/asia_sweep_lab.py` trước khi coi đây là kết luận, không chỉ giả định.
_KILLZONE: Dict[str, object] = dict(
    exec_windows_utc=((7.0, 10.0), (12.0, 14.0)))

# LUẬT THOÁT: TP cố định 1:3, breakeven ở +1R.
#
#   TP        = giá vào + 3R  (không phụ thuộc cấu trúc giá, nên R:R là HẰNG SỐ)
#   BE        = khi giá đi được +1R -> dời dừng lỗ về giá vào + ĐÚNG phí khứ hồi
#   trailing  = TẮT (dừng lỗ nằm im ở mức breakeven sau khi kích hoạt)
#
# Mức BE cộng phí THẬT của chính lệnh đó, không phải một hằng số pip: spread lúc khớp
# của GBPUSD gấp đôi EURUSD, nên một hằng số dùng chung sẽ thiếu ở cặp này và thừa ở
# cặp kia. Chạm BE nghĩa là HOÀ THẬT sau phí, không phải hoà gộp rồi âm.
#
# Hệ quả phải biết: TP cố định làm mọi lệnh có cùng R:R, nên KHÔNG còn cổng nào lọc
# theo R:R được. Trạng thái `RR_TOO_LOW` biến mất và số lệnh tăng 2,8 lần (453 ->
# 1.256 trên 11,5 năm), tức tỷ lệ phiên có tín hiệu đi từ 7% lên 20%. Kỳ vọng mỗi lệnh
# loãng đi tương ứng, nên MỨC RỦI RO phải hạ để giữ MaxDD trong ngân sách.
_EXIT_RULE: Dict[str, object] = dict(
    tp_r_multiple=3.0, be_trigger_r=1.0, be_extra_pips=0.0, trail_r=0.0)

PRESETS: Tuple[str, ...] = ("MSS", "FREQ", "SPEC")

# Preset ĐANG CHẠY. Đổi ở ĐÂY, không đổi rải rác ở nơi gọi.
#   MSS   dải rộng + CỔNG MSS. 1,10 lệnh/tuần · R ròng +0,0124 · gộp +0,0601
#   FREQ  dải rộng, KHÔNG cổng MSS. 7,90 lệnh/tuần · R ròng -0,0835 (t = -3,26)
#   SPEC  ngưỡng tài liệu tham khảo. 0,58 lệnh/tuần · R ròng -0,1654
ACTIVE_PRESET = "MSS"


def _config(instrument: str, preset: str = "") -> SC.SweepConfig:
    if instrument not in _SPEC:
        raise KeyError(
            f"{instrument!r} không thuộc rổ {INSTRUMENTS}. Thêm ngưỡng vào `_SPEC` "
            f"kèm biên Á trung vị ĐO ĐƯỢC của cặp đó — port thẳng ngưỡng của cặp "
            f"khác là sai đơn vị (xem `shared/asset_profile.py`).")
    preset = (preset or ACTIVE_PRESET).upper()
    if preset not in PRESETS:
        raise ValueError(f"preset {preset!r} lạ; chỉ có {PRESETS}")
    cfg = SC.SweepConfig(name=f"{NAME}:{instrument}", instrument=instrument,
                         exec_tf=EXECUTION_TF, exec_end_utc=15.0,
                         **_SPEC[instrument])
    if preset in ("MSS", "FREQ"):
        cfg = dataclasses.replace(cfg, **_WIDE_BANDS)
    if preset == "MSS":
        cfg = dataclasses.replace(cfg, **_MSS_GATE, **_EXIT_RULE, **_KILLZONE)
    return cfg


CONFIGS: Dict[str, SC.SweepConfig] = {s: _config(s) for s in INSTRUMENTS}

# ═══════════════════════════════════════════════════════════ bằng chứng đo được
# Hai hằng số này đi thẳng vào thẻ luật VÀ vào docstring đầu file, nên chúng là MỘT
# nguồn. Số của preset đang bật.
#
# ⚠️ ĐO TRƯỚC KHI ÁP `_KILLZONE` (25/08/2026) — cửa sổ khớp lệnh lúc đo là dải liên
# tục 07:00-20:00 UTC của `_WIDE_BANDS`, KHÔNG PHẢI hai killzone rời rạc đang chạy
# bây giờ. Tần suất/kỳ vọng dưới đây sẽ đổi (nhiều khả năng THẤP hơn — killzone bỏ
# đúng khoảng trũng thanh khoản giữa hai phiên). Chạy lại
# `research/fx/asia_sweep_lab.py` trên cấu hình mới rồi thay số ở đây; đừng report
# số cũ như thể nó mô tả đúng hành vi hiện tại.
EXPECTANCY = (
    "R ròng/lệnh +0,0147 (t = +0,52) · R gộp +0,0567 · thắng 44,0% · R:R khai 1:3, "
    "thực hiện 1,32 · Profit Factor 1,040 · FORM -0,0023 -> OOS +0,0547 · "
    "lãi/năm +0,48% · MaxDD -11,21% ở rủi ro 0,35%/lệnh — VƯỢT sàn nội bộ 9%"
)
FREQUENCY = "1.256 lệnh trong 11,5 năm ≈ 2,91 lệnh/tuần trên rổ 3 cặp"

_SOURCE = ("Osler (2003) FRBNY SR150 · Chesler (2004) hikkake qua Kirkpatrick & "
           "Dahlquist (2011) tr. 379-380 · ICT 2022 tr. 50-51 · Grimes (2012) "
           "tr. 183-186 · Lien (2008) tr. 69, 73")

# Thẻ luật của TỪNG công cụ — ba cặp chung LUẬT, khác NGƯỠNG, nên mỗi cặp một thẻ.
RULEBOOKS: Dict[str, object] = {
    s: SC.rulebook(c, expectancy=EXPECTANCY, frequency=FREQUENCY, source=_SOURCE)
    for s, c in CONFIGS.items()}


def _family_rulebook() -> object:
    """Thẻ luật của CẢ HỌ. Rổ phải là đủ ba cặp, nếu không nó mô tả sai cái
    đang chạy.

    Ngưỡng in ra là ngưỡng EURUSD; ba cặp khác nhau ở dải pip nên dải của từng
    cặp được liệt kê thêm vào mục CHỈ BÁO. Thẻ riêng của từng cặp ở `RULEBOOKS`.
    """
    rb = RULEBOOKS["EURUSD"]
    bands = tuple(
        f"ngưỡng {s}: biên Á {c.range_min_pips:.0f}-{c.range_max_pips:.0f} pip · "
        f"xuyên {c.depth_min_pips:.1f}-{c.depth_max_pips:.1f} pip · đệm SL "
        f"{c.sl_buffer_pips:.1f} pip"
        for s, c in CONFIGS.items())
    return dataclasses.replace(
        rb, universe=INSTRUMENTS, traded=INSTRUMENTS,
        indicators=rb.indicators + bands)


RULEBOOK = _family_rulebook()


# ═══════════════════════════════════════════════════════════ nạp dữ liệu
def _load(instrument: str) -> pd.DataFrame:
    """M1 THẬT. Live đọc MT5 (`FX_BARS_FROM_MT5=1`), backtest đọc parquet."""
    from src.python.shared import fx_data as D
    return D.load_m1(instrument)


# ═══════════════════════════════════════════════════════════ giao diện chuẩn
def backtest(instrument: str, *, preset: str = "") -> SC.BacktestResult:
    from src.python.shared import fx_data as D
    with D.parquet_only():
        m1 = _load(instrument)
    return SC.run(m1, _config(instrument, preset))


def stats(instrument: str, *, preset: str = "") -> Dict[str, object]:
    return SC.stats(backtest(instrument, preset=preset))


def stats_by_grade(instrument: str, *, preset: str = "") -> pd.DataFrame:
    """Kỳ vọng theo HẠNG setup — bảng cho thấy MSS làm gì. Xem docstring đầu file."""
    return SC.stats_by_grade(backtest(instrument, preset=preset))


def live_decision(instrument: str, *, preset: str = "") -> SC.SweepDecision:
    """Quyết định cho phiên hiện tại — CÙNG đường code với backtest."""
    return SC.live_decision(_load(instrument), _config(instrument, preset))


def live_decisions(*, preset: str = "") -> Dict[str, SC.SweepDecision]:
    """Quyết định của CẢ RỔ. Điểm vào mà `portfolio.live_targets()` gọi."""
    return {s: live_decision(s, preset=preset) for s in INSTRUMENTS}


def explain_decisions(*, preset: str = "") -> List[SC.SweepDecision]:
    return list(live_decisions(preset=preset).values())


def daily_pnl(instrument: str, *, preset: str = "") -> pd.Series:
    """Lợi nhuận theo NGÀY, đơn vị R. Nhân `RISK_PCT_PER_TRADE` để ra % equity."""
    T = backtest(instrument, preset=preset).trades
    if T.empty:
        return pd.Series(dtype=float)
    return T.set_index("t_exit")["r_net"].resample("1D").sum()


def portfolio_daily_pnl(*, preset: str = "") -> pd.Series:
    """Lợi nhuận NGÀY của cả rổ, đơn vị **% equity** ở `RISK_PCT_PER_TRADE`.

    ⚠️ ĐƠN VỊ. `daily_pnl` trả R; một R bằng `RISK_PCT_PER_TRADE` PHẦN TRĂM equity,
    nên phép quy đổi là NHÂN với con số đó — không chia thêm 100. Chia hai lần là lỗi
    đã xảy ra: MaxDD báo -0,09% trong khi số thật là -8,90%, tức rủi ro trông nhẹ
    hơn thực tế 100 lần và vẫn "hợp lý" đủ để không ai nhìn lại.
    """
    parts = [daily_pnl(s, preset=preset) for s in INSTRUMENTS]
    total = pd.concat(parts, axis=1).fillna(0.0).sum(axis=1)
    return total * RISK_PCT_PER_TRADE


if __name__ == "__main__":
    import json
    import sys

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(RULEBOOK.render())
    for sym in INSTRUMENTS:
        print(json.dumps(stats(sym), indent=2, ensure_ascii=False, default=str))
    for d in explain_decisions():
        print()
        print(d.explain())
