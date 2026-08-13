"""ftmo_leverage_policy.py — đòn bẩy thích ứng theo đệm lợi nhuận, cho FTMO $100k.

VẤN ĐỀ MÀ ĐÒN BẨY CỐ ĐỊNH KHÔNG GIẢI ĐƯỢC
==========================================
Đo lần đầu (`scratch/ftmo_leverage_frontier.py`, danh mục HAI chân, mục tiêu Phase 1
+10% trong 252 ngày, 86 cửa sổ trượt):

    đòn bẩy   PASS     VI PHẠM
      2x      15,1%     3,5%
      3x      37,2%     9,3%
      4x      59,3%    18,6%
      5x      69,8%    20,9%

ĐO LẠI 14/08 TRÊN DANH MỤC 27 CHÂN với hằng số hiện tại (trần 3,7x, sàn nội bộ 9%),
428 cửa sổ trượt 252 ngày:

    chính sách hiện tại   PASS 80,4%  ·  expire 19,6%  ·  VI PHẠM 0,0%
    nếu để trần cũ 6,0x   PASS 83,4%  ·  expire 16,6%  ·  VI PHẠM 0,0%

Hạ trần xuống 3,7x mất 3,0 điểm phần trăm tỷ lệ PASS và đổi lấy MaxDD 8,98% thay
vì 10,74%. Đó là mức giá phải trả, và nó rẻ.

HAI ĐIỀU BẢNG TRÊN KHÔNG NÓI, ĐO RIÊNG:
  * Chạy từ MỌI thời điểm khởi động (713 cửa sổ), **14,4% cửa sổ chạm ngưỡng HALT**
    giữa chừng. HALT không phải vi phạm — nó là hệ tự dừng — nhưng nó nghĩa là ở
    một phần bảy số kịch bản, hệ ngừng giao dịch trước khi hết 252 ngày.
  * MaxDD tệ nhất trong mọi cửa sổ là **12,14% tính từ ĐỈNH**, mà vẫn không vi phạm
    FTMO. Không mâu thuẫn: mốc 10% của FTMO neo vào **balance ban đầu tĩnh**, không
    trôi theo đỉnh equity — đúng cái bẫy thứ ba ghi ở đầu `core/infra/ftmo.py`.

Đòn bẩy cố định buộc ta chọn một điểm trên đường đánh đổi đó và giữ nguyên suốt kỳ
thi. Nhưng rủi ro vi phạm KHÔNG cố định theo thời gian:

  * Ngày đầu tiên: equity = $100.000, sàn = $90.000 → đệm đúng 10%. Đây là lúc
    NGUY HIỂM NHẤT, và đòn bẩy cao ở đây là nơi gần như toàn bộ xác suất vi phạm
    được sinh ra.
  * Sau khi lãi 6%: equity = $106.000, sàn vẫn $90.000 → đệm 15,1%. Cùng một mức
    đòn bẩy giờ an toàn hơn hẳn, và ta lại đang dùng đúng mức cũ.

Vậy nên đòn bẩy phải là hàm của **ĐỆM CÒN LẠI TỚI SÀN**, không phải một hằng số.
Đây chính là nguyên tắc anti-martingale mà `docs/ftmo/ftmo-the-cheopard.md` đặt ra
(Normal → Conservative → Capital Preservation → Payout Protection), diễn đạt lại
cho danh mục vol-target thay vì cho rủi ro từng lệnh.

NGUYÊN TẮC THỨ TỰ (bất biến của dự án, `docs/ftmo/`)
====================================================
    Account Survival > FTMO Compliance > Risk Control
        > Consistency > Long-term Reward > Profit Maximization

Mọi xung đột giải theo thứ tự này. Cụ thể ở đây: khi đệm mỏng, GIẢM đòn bẩy kể cả
khi điều đó gần như chắc chắn làm trượt mục tiêu lợi nhuận — trượt kỳ thi thì thi
lại được, vi phạm thì mất tài khoản.

HAI SÀN PHẢI THEO DÕI CÙNG LÚC
==============================
FTMO có hai giới hạn độc lập và chúng ràng buộc ở hai thang thời gian khác nhau:
  * **Max Loss 10%** — sàn TUYỆT ĐỐI $90.000, không bao giờ reset
  * **Daily Loss 5%** — mốc tính lại mỗi 00:00 CE(S)T theo balance đầu ngày
Đòn bẩy cho phép là GIÁ TRỊ NHỎ HƠN trong hai ràng buộc, tính lại mỗi ngày.

SÀN NỘI BỘ 9% — CHẶT HƠN LUẬT FTMO, CÓ CHỦ Ý
=============================================
Chính sách này KHÔNG dùng mốc 10% của FTMO làm sàn tính toán. Nó dùng **9%**.

Lý do là một lỗ hổng đo được ngày 14/08: ba ràng buộc bên dưới đều bó **một ngày
hoặc một cửa sổ 21 ngày**, không cái nào bó **drawdown TÍCH LUỸ**. Chạy danh mục
27 chân qua chính sách cũ cho đòn bẩy 4,85x — ngày tệ nhất chỉ −3,85% (an toàn
dưới mốc 5%) nhưng **MaxDD đạt −10,74%**, tức chuỗi ngày xấu liên tiếp vượt trần
tổng trong khi không ngày nào riêng lẻ vi phạm.

Bảng đo trên danh mục 27 chân, 2020-01 → 2026-08:

    đòn bẩy   MaxDD    ngày tệ nhất   lãi/năm
      3,00x    7,74%      −$2.381      +18,1%
      3,71x    9,00%      −$2.943      +22,3%   ← trần
      4,00x    9,47%      −$3.174      +24,1%
      4,85x   10,74%      −$3.849      +29,2%   VI PHẠM

Sàn 9% để lại biên 10% dưới mốc thật. Biên đó không phải cho đẹp: backtest không
có trượt giá khi tin ra, spread giãn lúc thanh khoản mỏng, hay lệnh bị từ chối —
nên MaxDD thật LUÔN sâu hơn MaxDD đo được, và 10,74% vs 10% thì không còn chỗ sai.

"ĐÒN BẨY" Ở ĐÂY KHÔNG PHẢI ĐÒN BẨY CỦA BROKER
==============================================
Hai đại lượng cùng tên nhưng khác hẳn nhau, và lẫn chúng là cách nhanh nhất để
đọc sai mọi con số trong file này:

  * **hệ số phơi nhiễm** (thứ hàm này trả về) = tổng notional ÷ equity. Nó quyết
    định LÃI/LỖ: ở 3,7x, danh mục lãi lỗ gấp 3,7 lần biến động của chính nó.
  * **đòn bẩy broker** (FTMO Swing: forex 1:30, XAU và indices 1:15, hàng hoá và
    crypto 1:1) chỉ quyết định KÝ QUỸ cần để mở vị thế. Nó KHÔNG đổi lãi/lỗ trên
    mỗi lot.

Ở hệ số 3,7x trên rổ toàn forex, ký quỹ dùng = 3,7 / 30 = **12,3% equity**. Trần
1:30 của FTMO còn cách rất xa, nên nó KHÔNG phải ràng buộc chặn ở đây — ràng buộc
chặn là drawdown, không phải margin. Nếu sau này danh mục thêm XAU hay chỉ số
(trần 1:15) thì phải tính lại phần ký quỹ theo từng nhóm tài sản.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from src.python.core.infra import ftmo

# Số σ ngày dùng khi quy đệm equity thành đòn bẩy cho phép.
# 3,0σ ≈ phân vị 99,9% một phía: ta muốn xác suất chạm sàn TRONG MỘT NGÀY là rất
# nhỏ, vì chạm sàn không phải một khoản lỗ — nó là mất tài khoản.
SAFETY_SIGMA_DAILY = 3.0

# Số σ cho ràng buộc tổng, đo trên cửa sổ dài hơn nên cần biên rộng hơn.
# 21 ngày là chu kỳ tái cân bằng của chiến lược — tức khoảng thời gian mà vị thế
# KHÔNG đổi và ta phải chịu trọn biến động của nó.
SAFETY_HORIZON_DAYS = 21
SAFETY_SIGMA_TOTAL = 2.5

# Biên an toàn cho ràng buộc ĐUÔI: đòn bẩy phải sao cho ngày tệ nhất ĐÃ THẤY, nhân
# lên, vẫn không chạm mốc lỗ ngày. 1,3 vì ngày tệ nhất TƯƠNG LAI có thể tệ hơn ngày
# tệ nhất đã quan sát — mẫu 6,5 năm không phải giới hạn của phân phối.
TAIL_BUFFER = 1.2
# ⚠️ HẠ 1,3 → 1,2 NGÀY 15/08/2026 — CHỌN THEO ĐIỂM GÃY, KHÔNG THEO LỢI NHUẬN.
#
# `research/fx/risk_budget_tune.py` quét hệ số này trên toàn mẫu 2020–2026, đo
# tỷ lệ cửa sổ 252 ngày BỊ CẮT (chạm sàn nội bộ 9% hoặc mốc ngày 4%):
#
#     tail   lev THỰC   2026 lãi   MaxDD 2026   cửa sổ CHẾT   cửa sổ BỊ CẮT
#     1,3      4,84x     +12,32%      6,36%         0,0%           0,0%
#     1,2      5,25x     +13,19%      6,55%         0,0%           0,0%   ← chọn
#     1,1      5,72x     +14,24%      6,71%         0,0%          23,5%   VỠ
#     1,0      6,00x     +14,87%      6,78%         0,0%          23,5%   VỠ
#
# Từ 1,2 xuống 1,1 tỷ lệ bị cắt nhảy **0% → 23,5%** — gần một phần tư số lần thi
# hỏng. Đó là ĐIỂM GÃY của cấu trúc, không phải nhiễu: nó lặp lại y hệt ở 1,0 và
# nhảy bậc chứ không trôi dần.
#
# Chọn 1,2 vì nó là mức CUỐI CÙNG trước điểm gãy, và cách điểm gãy trọn một bậc
# lưới. Đây là chọn theo CẤU TRÚC của bài toán, khác hẳn việc quét lưới rồi lấy
# ô có lợi nhuận cao nhất — thứ CLAUDE.md liệt vào nhóm bị từ chối thẳng.
#
# KHÔNG hạ tiếp: 1,1 lãi hơn 1,05 điểm % nhưng đổi lấy 23,5% số lần thi hỏng.
# Theo thứ tự ưu tiên (Account Survival > FTMO Compliance > … > Profit), đó là
# đánh đổi BỊ TỪ CHỐI.

# Sàn NỘI BỘ, chặt hơn mốc 10% của FTMO. Mọi phép tính đệm neo vào con số này, không
# neo vào `ftmo.MAX_LOSS_HARD` — xem phần đầu file cho bảng đo dẫn tới nó.
DD_SELF_CAP = 0.09

# Trần cứng — đòn bẩy LỚN NHẤT có XÁC SUẤT MẤT TÀI KHOẢN bằng 0 trên mẫu.
#
# ⚠️ NÂNG 3,5 → 4,0 NGÀY 15/08/2026, VÀ ĐỔI LUÔN TIÊU CHÍ ĐO.
#
# TIÊU CHÍ CŨ SAI CHỖ NÀO
# ------------------------
# Bảng cũ chọn trần theo "MaxDD từ ĐỈNH < 9%":
#
#     3,0x  MaxDD 8,01%   ·  3,51x MaxDD 9,00% ← trần cũ  ·  3,7x MaxDD 9,35% VƯỢT
#
# Nhưng luật FTMO neo max loss vào SỐ DƯ BAN ĐẦU TĨNH, không trôi theo đỉnh: tài
# khoản lên $130k rồi rơi về $95k là DD 27% từ đỉnh mà VẪN HỢP LỆ. Đo bằng MaxDD
# từ đỉnh là tự phạt mình ở đúng những chuỗi đã lãi nhiều — cùng lỗi đã sửa ở
# `research/fx/account_report.py`.
#
# Quan trọng hơn: tiêu chí cũ bỏ qua LỚP CẮT NỘI BỘ. `ftmo_guard.check()` đóng
# sạch vị thế ở 9% tổng / 4,0% lỗ ngày thực — TRƯỚC luật 10% / 5%. Nhờ nó, chạm
# sàn nội bộ và chạm luật là hai kết cục khác hẳn:
#
#     chạm sàn nội bộ  → BỊ CẮT. Lần thi hỏng, tài khoản CÒN, thi lại được.
#     chạm luật FTMO   → MẤT TÀI KHOẢN. Hết.
#
# TIÊU CHÍ MỚI: P(mất tài khoản) = 0
# -----------------------------------
# `research/fx/leverage_by_phase.py` quét mọi cửa sổ, mỗi cửa sổ là một lần thi,
# dừng ở PASS / bị cắt / chết / hết hạn. Đo trên toàn mẫu 2020–2026 với chi phí
# cross MỚI (đắt hơn 2–3 lần), pha CHALLENGE mục tiêu +10%:
#
#     đòn bẩy   PASS    bị CẮT   CHẾT    thời gian TV
#     3,5x     71,6%     2,0%    0,0%      7,0 tháng   ← trần cũ
#     4,0x     80,4%     3,9%    0,0%      6,5 tháng   ← TRẦN MỚI
#     4,5x     85,3%     2,9%    2,0%      5,8 tháng   VƯỢT — bắt đầu chết
#     5,0x     86,3%     4,9%    2,9%      5,1 tháng   VƯỢT
#
# 4,0x là mức CUỐI CÙNG còn P(chết) = 0. Đổi lại: tỷ lệ pass 71,6% → 80,4% và
# nhanh hơn nửa tháng, mà không thêm một cửa sổ mất tài khoản nào.
#
# KHÔNG LẤY MỨC CAO HƠN DÙ BẢNG THÔ TRÔNG NHƯ CHO PHÉP
# -----------------------------------------------------
# Bảng thô còn cho 5,5x và 6,0x chết 1,0% — THẤP HƠN 4,5x (2,0%) và 5,0x (2,9%).
# Rủi ro không thể giảm khi đòn bẩy tăng; đó là nhiễu của mẫu ~100 cửa sổ. Lấy
# mức cao trong vùng ấy là chọn đỉnh nhiễu — đúng thứ `REJECTED_DIRECTIONS` đã
# ghi lại một lần. Nên chọn theo ĐƠN ĐIỆU: dừng ở mức đầu tiên vượt ngân sách.
#
# HAI LỚP CẮT LÀ ĐIỀU KIỆN CỦA CON SỐ NÀY
# ----------------------------------------
# 4,0x chỉ an toàn KHI `ftmo_guard` còn chạy mỗi chu kỳ và còn đóng được lệnh.
# Bỏ lớp cắt đi thì trần này quá cao. Hai thứ đi cùng nhau, đừng tách:
#
#     ftmo.DAILY_FLATTEN_REALIZED = 4,0%   (luật 5%)
#     DD_SELF_CAP                 = 9,0%   (luật 10%)
#
# NÂNG TIẾP 4,0 → 5,0 (cùng ngày, sau khi quét qua CHÍNH SÁCH THẬT)
# ------------------------------------------------------------------
# Hai bảng trước quét đòn bẩy CỐ ĐỊNH. `research/fx/leverage_scan_full.py` chạy
# `decide()` mỗi ngày trên toàn mẫu 2020–2026 — tức đúng thứ live làm — và cho
# một kết quả mà đòn bẩy cố định không thấy được:
#
#     trần    số dư cuối   MaxDD   lev THỰC TB   2026     CHẾT   bị cắt
#     3,5x     $314.673   11,88%      3,50x     +9,08%    0,0%    0,0%
#     4,0x     $369.924   13,47%      4,00x    +10,32%    0,0%    0,0%
#     4,5x     $434.658   15,04%      4,50x    +11,54%    0,0%    0,0%
#     5,0x     $485.518   16,10%      4,84x    +12,32%    0,0%    0,0%
#     6,0x     $485.518   16,10%      4,84x    +12,32%    0,0%    0,0%   ← y hệt
#     8,0x     $485.518   16,10%      4,84x    +12,32%    0,0%    0,0%   ← y hệt
#
# NÂNG TIẾP 5,0 → 6,0 cùng ngày, sau khi hạ TAIL_BUFFER xuống 1,2: điểm bão hoà
# dịch từ 4,84x lên 5,25x, nên trần 5,0 lại trở thành ràng buộc. 6,0x đưa nó về
# đúng vai trò cũ — một chặn trên KHÔNG bị chạm, để công thức đuôi quyết định.
#
# CHÍNH SÁCH TỰ BÃO HOÀ Ở 4,84x. Từ 5,0x trở lên, trần cứng không còn là ràng
# buộc — ràng buộc ĐUÔI chặn trước:
#
#     lev_tail = đệm_ngày / (TAIL_BUFFER × |ngày tệ nhất|)
#              = 5,0% / (1,3 × 0,794%) = 4,84x
#
# Nên 5,0 KHÔNG phải con số chọn vì kết quả đẹp — nó là mức mà trần cứng vừa hết
# tác dụng. Đặt cao hơn là để một hằng số không còn ý nghĩa nằm trong mã nguồn;
# đặt thấp hơn là chặn bằng trần cứng thứ mà công thức đuôi đã chặn tốt hơn (vì
# đuôi thu hẹp THEO ĐỆM CÒN LẠI, còn trần cứng thì không).
#
# MaxDD toàn mẫu 16,10% là rút từ ĐỈNH, KHÔNG phải vi phạm: số dư cuối $485.518
# nên rơi 16% từ đỉnh vẫn còn xa $91.000. Hai cột quyết định là CHẾT và bị cắt,
# cả hai bằng 0 ở mọi mức quét.
#
# ⚠️ 5,0x AN TOÀN CHỈ KHI `worst_day_bps` CÒN ĐÚNG. Toàn bộ lập luận trên đứng
# trên ngày tệ nhất đã quan sát (79,4 bps). Thêm hay bớt một chân là phải đo lại —
# `research/fx/leverage_scan_full.py` chạy lại được bất cứ lúc nào.
LEVERAGE_MAX = 6.0
LEVERAGE_MIN = 0.0          # đệm quá mỏng -> dừng hẳn, không giao dịch


@dataclass(frozen=True)
class LeverageDecision:
    leverage: float
    state: str                  # NORMAL | CONSERVATIVE | PRESERVATION | HALT
    buffer_total_pct: float     # đệm tới sàn tuyệt đối, % equity hiện tại
    buffer_daily_pct: float     # đệm tới mốc lỗ ngày, % equity hiện tại
    binding: str                # ràng buộc nào đang chặn
    reason: str


def decide(equity: float, day_start_balance: float, daily_vol_bps: float, *,
           account_size: float = 100_000.0,
           leverage_max: float = LEVERAGE_MAX,
           worst_day_bps: Optional[float] = None) -> LeverageDecision:
    """Đòn bẩy cho phiên hiện tại, từ đệm equity và biến động chiến lược.

    `daily_vol_bps` = std lợi nhuận NGÀY của danh mục ở đòn bẩy 1,0 (bps) —
    đúng đơn vị `currency_carry.combined()` trả về.

    BA ràng buộc, lấy giá trị NHỎ NHẤT:
        đòn bẩy_ngày  = đệm_ngày / (SAFETY_SIGMA_DAILY × σ_ngày)
        đòn bẩy_tổng  = đệm_tổng / (SAFETY_SIGMA_TOTAL × σ_ngày × √21)
        đòn bẩy_đuôi  = đệm_ngày / (TAIL_BUFFER × |ngày tệ nhất đã thấy|)

    Ràng buộc thứ ba THÊM 13/08 sau khi mô phỏng thất bại. Hai ràng buộc đầu giả
    định phân phối chuẩn qua hệ số σ, nhưng chuỗi thật có đuôi dày hơn nhiều: danh
    mục ba chân có σ = 0,504%/ngày mà **ngày tệ nhất −5,47%**, tức 10,9σ. Ở đòn bẩy
    1,73x mà hai ràng buộc đầu cho phép, ngày đó thành −9,47% — vượt cả giới hạn
    lỗ ngày 5% của FTMO, và đo được nó gây vi phạm ở **55,9%** cửa sổ tài khoản funded.

    `worst_day_bps` = tổn thất ngày tệ nhất ĐÃ QUAN SÁT của chiến lược (giá trị âm
    hoặc dương đều được, hàm lấy trị tuyệt đối). Truyền None thì bỏ qua ràng buộc
    này — chỉ nên làm khi chiến lược thật sự có đuôi mỏng, và điều đó phải được ĐO.
    """
    # Sàn NỘI BỘ 9%, không phải mốc 10% của FTMO — dừng trước khi chạm luật, không
    # dừng khi đã chạm. `ftmo.MAX_LOSS_HARD` vẫn là sự thật về luật; đây là biên tự đặt.
    floor_abs = account_size * (1.0 - min(DD_SELF_CAP, ftmo.MAX_LOSS_HARD))
    floor_daily = day_start_balance * (1.0 - ftmo.DAILY_LOSS_HARD)
    # Mốc lỗ ngày chỉ có ý nghĩa khi nó nằm TRÊN sàn tuyệt đối.
    floor_eff_daily = max(floor_daily, floor_abs)

    if equity <= floor_abs:
        return LeverageDecision(0.0, "HALT", 0.0, 0.0, "MAX_LOSS",
                                f"equity chạm sàn nội bộ {DD_SELF_CAP:.0%} — dừng hẳn "
                                f"(luật FTMO là {ftmo.MAX_LOSS_HARD:.0%}, còn biên)")

    buf_total_pct = (equity - floor_abs) / equity * 100.0
    buf_daily_pct = max(0.0, (equity - floor_eff_daily) / equity * 100.0)

    sigma = max(daily_vol_bps, 1e-9) / 100.0            # % mỗi ngày
    lev_daily = buf_daily_pct / (SAFETY_SIGMA_DAILY * sigma)
    lev_total = buf_total_pct / (SAFETY_SIGMA_TOTAL * sigma * np.sqrt(SAFETY_HORIZON_DAYS))
    lev_tail = float("inf")
    if worst_day_bps is not None:
        wd = abs(float(worst_day_bps)) / 100.0
        if wd > 0:
            lev_tail = buf_daily_pct / (TAIL_BUFFER * wd)

    cands = {"DAILY_LOSS": lev_daily, "MAX_LOSS": lev_total, "ĐUÔI": lev_tail}
    binding = min(cands, key=lambda k: cands[k])
    lev = float(min(lev_daily, lev_total, lev_tail, leverage_max))
    lev = max(LEVERAGE_MIN, lev)
    if lev >= leverage_max:
        binding = "TRẦN CỨNG"

    # Nhãn trạng thái theo đệm tổng — cùng thang với máy trạng thái trong
    # `docs/ftmo/ftmo-the-cheopard.md`, diễn đạt lại theo đệm thay vì theo lãi tháng.
    # ⚠️ HẠ NGƯỠNG HALT 4,0% → 1,0% NGÀY 15/08/2026.
    #
    # Ngưỡng cũ dừng hệ QUÁ SỚM, và đo được: đệm tổng đầy chỉ 9% (sàn nội bộ), nên
    # "đệm còn 4%" nghĩa là ĐÃ MẤT 5,35% — hệ dừng hẳn khi mới dùng 5,35/9 ngân
    # sách rủi ro. Vòng 2026 lộ ra hậu quả: equity chạm $94.651 ở ngày thứ 30 rồi
    # HALT, và **168/198 ngày còn lại không giao dịch gì** (đòn bẩy trung bình
    # 0,61x dù trần 4,0x). Danh mục kết thúc −5,35% trong khi chuỗi lợi nhuận thô
    # của chính nó là +250 bps.
    #
    # HALT CỨNG Ở 4% LÀ THỪA — cơ chế TỶ LỆ đã làm đúng việc đó rồi:
    #
    #     lev_tail = đệm_ngày / (1,3 × |ngày tệ nhất|)
    #
    # nên đệm mỏng thì đòn bẩy tự tụt. Ở đệm 1,0% với ngày tệ nhất 79,4 bps,
    # lev_tail ≈ 0,97x — đã bảo thủ hơn nhiều so với trần 4,0x, mà không cắt hẳn
    # khả năng gỡ lại. Chồng thêm một ngưỡng cứng lên trên là phanh hai lần.
    #
    # 1,0% là mức mà đòn bẩy tỷ lệ đã về dưới 1,0x, tức hệ gần như đứng ngoài rồi.
    # Dưới nữa thì `equity <= floor_abs` ở đầu hàm đã bắt.
    #
    # Ba nhãn trạng thái giữ nguyên thang cũ để `docs/ftmo/ftmo-the-cheopard.md`
    # và thẻ giao diện không phải đổi theo.
    if buf_total_pct >= 12.0:
        state = "NORMAL"
    elif buf_total_pct >= 8.0:
        state = "CONSERVATIVE"
    elif buf_total_pct >= 1.0:
        state = "PRESERVATION"
    else:
        state = "HALT"
        lev = 0.0
        binding = "ĐỆM CẠN"

    return LeverageDecision(
        leverage=round(lev, 4), state=state,
        buffer_total_pct=round(buf_total_pct, 3),
        buffer_daily_pct=round(buf_daily_pct, 3),
        binding=binding,
        reason=(f"đệm tổng {buf_total_pct:.2f}% / ngày {buf_daily_pct:.2f}% · "
                f"σ_ngày {sigma:.3f}% · chặn bởi {binding}"))


def simulate_path(daily_returns_bps, daily_vol_bps: float, *,
                  account_size: float = 100_000.0,
                  target_pct: Optional[float] = 0.10,
                  max_days: int = 252,
                  leverage_max: float = LEVERAGE_MAX,
                  worst_day_bps: Optional[float] = None):
    """Chạy một đường equity dưới chính sách này. Trả (kết quả, số ngày, equity cuối).

    Kết quả: "PASS" | "MAX_LOSS" | "DAILY" | "expire".
    Dùng cho cả kỳ thi (`target_pct` đặt) lẫn tài khoản funded (`target_pct=None`).
    """
    equity = float(account_size)
    day_start = equity
    floor_abs = account_size * (1.0 - ftmo.MAX_LOSS_HARD)
    for i, x in enumerate(daily_returns_bps):
        if i >= max_days:
            return "expire", i, equity
        d = decide(equity, day_start, daily_vol_bps,
                   account_size=account_size, leverage_max=leverage_max,
                   worst_day_bps=worst_day_bps)
        day_start = equity
        equity *= (1.0 + float(x) * d.leverage / 1e4)
        if equity <= floor_abs:
            return "MAX_LOSS", i, equity
        if equity < day_start * (1.0 - ftmo.DAILY_LOSS_HARD):
            return "DAILY", i, equity
        if target_pct is not None and equity >= account_size * (1.0 + target_pct):
            return "PASS", i, equity
    return "expire", max_days, equity
