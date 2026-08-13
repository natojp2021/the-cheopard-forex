# -*- coding: utf-8 -*-
"""ftmo.py — TẦNG RÀNG BUỘC FTMO. Nguồn sự thật DUY NHẤT cho mọi luật của quỹ.

TÀI LIỆU MỎ NEO: `docs/ftmo/ftmo.md`
=====================================
Đó là văn bản luật gốc của FTMO. Khi có bất kỳ mâu thuẫn nào giữa file này và
tài liệu đó, TÀI LIỆU ĐÚNG — sửa code, đừng sửa cách hiểu.

Ba con số trong ví dụ $200.000 của tài liệu (190.000 / 194.000 / 192.000) đã được
tái tạo đúng từng đồng trong `tests/test_ftmo_official_examples_20260801.py`, cùng
với ví dụ then chốt "balance $92.000 + lỗ trôi $2.001 = vi phạm" (chứng minh luật
đo trên EQUITY chứ không phải balance) và kịch bản qua đêm mà tài liệu cảnh báo.
Bộ test đó là cầu nối giữa văn bản luật và code — đổi hằng số nào ở đây mà làm
lệch khỏi tài liệu thì nó đỏ ngay.

CHUYỂN HƯỚNG 31/07: The Cheopard không còn là bot tài khoản cá nhân $1.500
chạy target-lock 4%→2% để nhân vốn. Nó là **bot quỹ FTMO $100.000**, và toàn bộ
mô hình rủi ro đảo ngược:

    Trước:  tối đa hoá tăng trưởng, chấp nhận DD 48%, risk 7,5%/lệnh
    Nay:    tối đa hoá XÁC SUẤT SỐNG SÓT, DD mục tiêu ≤4%, risk 0,25-0,5%/lệnh

NGUYÊN TẮC TỐI THƯỢNG (thứ tự tuyệt đối, mọi xung đột giải theo thứ tự này):

    Account Survival > FTMO Compliance > Risk Control
        > Consistency > Long-term Reward > Profit Maximization

Nghĩa là: nếu một phương án có Expected Return cao hơn NHƯNG làm tăng xác suất
vi phạm giới hạn FTMO, phải loại bỏ phương án đó. Một tháng không giao dịch tốt
hơn một tháng mất tài khoản.

BA ĐIỂM DỄ SAI NHẤT, ghi ở đây vì sai một trong ba là mất tài khoản
-------------------------------------------------------------------
1. **MÚI GIỜ NGÀY GIAO DỊCH.** FTMO chốt ngày theo CE(S)T (giờ Praha), KHÔNG
   phải UTC. Hệ thống cũ reset bộ đếm ngày theo UTC. Lệch 1-2 giờ nghĩa là bộ
   đếm daily-loss của bot và của FTMO nói về hai khoảng thời gian khác nhau —
   bot tưởng đã sang ngày mới và mở lệnh, trong khi FTMO vẫn tính vào ngày cũ
   đã lỗ 4%. Đây là cách tài khoản nổ mà không ai hiểu vì sao.

2. **DAILY LOSS TÍNH CẢ FLOATING.** FTMO so equity HIỆN TẠI (gồm lãi/lỗ chưa
   chốt) với equity ĐẦU NGÀY. Không phải PnL đã chốt. Một vị thế đang lỗ chưa
   đóng vẫn tính đủ vào giới hạn 5%.

3. **MAX LOSS LÀ TĨNH.** Mốc là balance BAN ĐẦU ($100.000), không phải đỉnh
   equity. Lãi lên $110k rồi tụt về $89.9k là vi phạm — dù từ đỉnh mới chỉ giảm
   18%. Ngược lại, mốc không trôi theo lãi nên càng lãi càng có đệm.

VÌ SAO LÀ MODULE RIÊNG, KHÔNG NHÉT VÀO `target_mode.py`
--------------------------------------------------------
`target_mode` là SSOT của việc QUY ĐỔI rủi ro sang cỡ lệnh, xây quanh khái niệm
"target-lock": nhân vốn tới mốc rồi hạ risk. FTMO là một mô hình KHÁC HẲN —
vốn cố định, risk cố định thấp, và ràng buộc thật nằm ở drawdown chứ không ở
mục tiêu tăng trưởng. Trộn hai mô hình vào một file sẽ tạo hai nguồn sự thật
delay cùng một quyết định.

Thay vào đó: module này sở hữu LUẬT, `target_mode` gọi sang để lấy con số. Mọi
điểm vào lệnh hiện có không phải sửa một dòng nào.
"""
from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from src.python.core.infra import ftmo_risk_state as _risk_state
from src.python.utils.logger import log, log_error

# ---------------------------------------------------------------- đặc tả tài khoản
ACCOUNT_SIZE = 100_000.0
ACCOUNT_TYPE = "SWING"              # đòn bẩy tài khoản 1:30
# Vì sao SWING chứ không Standard, dù Standard có đòn bẩy cao gấp ba (forex 1:100
# so 1:30): danh mục 27 chân chạy trên M30/H1/H4/D1 và GIỮ LỆNH QUA ĐÊM cũng như
# QUA CUỐI TUẦN ở mọi chân — time-stop ngắn nhất là 12 nến H4 (2 ngày), dài nhất
# là tái cân bằng 21 ngày của hai chân D1. Standard hạn chế giữ lệnh qua tin và
# qua cuối tuần trên tài khoản funded, tức nó cấm đúng thứ mọi chân đang làm.
# (Ví dụ SwingDon/TomXau ở đây trước 14/08/2026 là chiến lược của hệ XAUUSD, không
#  tồn tại trong repo này — đã thay bằng thời gian giữ lệnh thật của 27 chân.)
#
# Đòn bẩy KHÔNG phải ràng buộc của hệ này. Danh mục hai chân chạy phơi nhiễm gộp
# ~0,9 đơn vị rủi ro với biến động 3,2%/năm; ràng buộc thật là DRAWDOWN, không phải
# ký quỹ — đúng như tài liệu FTMO nói.
LEVERAGE_ACCOUNT = 30               # Swing: 1:30 (FX majors)

# SYMBOL ĐƯỢC PHÉP — VIẾT LẠI 13/08/2026.
# Bản cũ ghim `SYMBOL = "XAUUSD"` là symbol DUY NHẤT. Hệ hiện tại là danh mục
# tiền tệ cắt ngang: nó BẮT BUỘC phải giữ nhiều cặp cùng lúc, vì bản chất chiến
# lược là xếp hạng 8 đồng tiền với nhau (xem `strategies/currency_reversal.py`).
# Một symbol duy nhất không chỉ sai — nó làm chiến lược không định nghĩa được.
SYMBOLS_ALLOWED = frozenset({
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
})

# Khung thời gian ĐƯỢC PHÉP. M1/M5/M15 bị cấm: nhiễu cao, phụ thuộc spread/
# latency, và tần suất lệnh lớn dễ chạm ngưỡng "quá nhiều hành động/ngày" mà
# FTMO theo dõi.
TIMEFRAMES_ALLOWED = frozenset({"M30", "H1", "H4", "D1"})
TIMEFRAMES_BANNED = frozenset({"M1", "M5", "M15"})

# Múi giờ chốt ngày giao dịch của FTMO (trụ sở Praha). Xem điểm dễ sai #1.
FTMO_TZ = ZoneInfo("Europe/Prague")

# ---------------------------------------------------------------- giới hạn cứng
DAILY_LOSS_HARD = 0.05              # vi phạm = mất tài khoản
MAX_LOSS_HARD = 0.10                # vi phạm = mất tài khoản

# CÔNG THỨC ĐÚNG CỦA FTMO — kiểm chứng lại với tài liệu chính thức 31/07, và
# bản triển khai đầu tiên của tôi ĐÃ SAI theo hướng NGUY HIỂM.
#
#   Maximum Daily Loss (2-Step):
#       ngưỡng = (BALANCE lúc 00:00 CE(S)T hôm trước) − 5% × VỐN BAN ĐẦU
#
#   Maximum Loss (2-Step):
#       ngưỡng = VỐN BAN ĐẦU × 90%   — TĨNH, không trôi theo lãi
#       (bản trôi theo đỉnh là của Challenge 1-Step, KHÔNG áp dụng ở đây)
#
# HAI CHỖ TÔI ĐÃ SAI, cả hai đều làm hệ thống DỄ DÃI HƠN luật thật:
#
#   a) Mẫu số. Tôi tính "lỗ ngày" theo TỶ LỆ của equity đầu ngày. FTMO cho một
#      hạn mức TUYỆT ĐỐI = 5% của vốn BAN ĐẦU, tức $5.000 và không đổi. Ở equity
#      $115.000, công thức của tôi cho phép lỗ $5.750 — vượt $750 so với luật.
#      Càng lãi thì sai số càng lớn, tức lỗi chỉ lộ ra đúng lúc có nhiều thứ để
#      mất nhất.
#
#   b) Mốc đầu ngày. Tôi chụp EQUITY ở chu kỳ đầu tiên của ngày mới. FTMO dùng
#      BALANCE lúc nửa đêm. Nếu nửa đêm đang giữ một vị thế lỗ $3.000 thì
#      balance = $100.000 còn equity = $97.000: ngưỡng thật là $95.000, ngưỡng
#      của tôi là $92.150 — dễ hơn $2.850. Đó đúng là kịch bản mất tài khoản.
#
# Nay đo theo hạn mức TUYỆT ĐỐI trên mốc BALANCE, giống hệt FTMO.
# Giá trị MẶC ĐỊNH cho tài khoản $100.000. Con số THẬT lấy từ
# `initial_balance()` — xem ngay bên dưới.
DAILY_LOSS_AMOUNT = DAILY_LOSS_HARD * ACCOUNT_SIZE   # $5.000
MAX_LOSS_FLOOR = ACCOUNT_SIZE * (1.0 - MAX_LOSS_HARD)  # $90.000

# NGƯỠNG TỰ ĐẶT — luôn cách xa giới hạn cứng. Drawdown không phải hạn mức để
# tiêu delay hết; nó là tín hiệu cảnh báo hệ thống.
#
# `DAILY_NORMAL` KHÔNG có nhánh chặn riêng, và đó là đúng: nó đánh dấu ranh giới
# "vẫn bình thường", tức vùng KHÔNG cần hành động. Nhưng nó vẫn phải được ĐỌC —
# `daily_zone()` dùng nó để gọi tên vùng cho log/email/GUI. Một hằng số chỉ nằm
# trong chú thích là một hằng số không ai kiểm được (đo 08/08: nó từng có 0 nơi
# đọc, cùng họ với `TIMEFRAMES_BANNED` và hai mục tiêu KPI).
DAILY_NORMAL = 0.01
DAILY_WARNING = 0.02
DAILY_DANGER = 0.03
DAILY_EMERGENCY = 0.04

TOTAL_PREFERRED = 0.04
TOTAL_WARNING = 0.06
# Ngưỡng ĐÓNG SẠCH theo tổng drawdown dự báo. Đặt ở 8%: còn 2 điểm phần trăm
# đệm tới sàn $90.000, đủ để lệnh khớp xong mà chưa chạm giới hạn cứng.
TOTAL_FLATTEN_PROJECTED = 0.08

# Ngân sách rủi ro theo TUẦN và THÁNG (tài liệu §Weekly Risk Budget / §Monthly
# Survival Rule). Khác daily/tổng ở chỗ chúng không phải luật FTMO — chúng là
# tín hiệu cho thấy CẤU HÌNH đang sai chứ không phải một ngày xui.
# ---------------------------------------------------------------- chốt NỘI BỘ
# TÀI LIỆU `docs/ftmo/ftmo-risk-and-reward.md` §III.2 bảng "Bộ thông số mục tiêu":
#
#     Internal Daily Stop (Chặn nội bộ)   1.0% – 1.5%   (FTMO: 5.0%)
#     Internal Monthly DD Stop            3.0% – 4.0%   (FTMO: 10.0%)
#
# Đây KHÔNG phải luật FTMO — chúng là chốt tự đặt, và chính vì thế mới quan
# trọng: giới hạn của FTMO là vạch CHẾT, không phải vạch để giao dịch tới.
#
# VÌ SAO TRƯỚC 07/08 KHÔNG CÓ: `DAILY_DANGER = 3%` là ngưỡng chặn sớm nhất theo
# ngày, tức gấp đôi mức tài liệu nêu, và tầng tháng chặn ở 5% thay vì 3-4%.
# Khoảng cách ấy không phải chi tiết: ở 0,5% risk/lệnh, lỗ ngày 3% nghĩa là đã
# thua 6 lệnh liên tiếp trong một ngày — với danh mục ra ~4,4 lệnh/THÁNG thì đó
# không còn là một ngày xui, đó là cấu hình đã hỏng.
#
# CHỌN CẬN TRÊN của khoảng tài liệu (1,5% và 4,0%), không phải cận dưới. Cận
# dưới 1,0% chỉ cách 2 lệnh thua ở risk tối đa 0,5%, nên một chuỗi thua hoàn
# toàn bình thường về mặt thống kê cũng đủ khoá cả ngày. Chốt nội bộ phải chặn
# thứ BẤT THƯỜNG, không chặn thứ bình thường — nếu nó kêu mỗi tuần thì người
# vận hành sẽ nới nó ra, và lúc đó nó thành vô dụng.
#
# HỆ QUẢ nói rõ để không ai ngạc nhiên: bot ngừng mở lệnh mới sớm hơn hẳn trước
# đây. Đó là chủ đích. Ngày mai bộ đếm reset; tài khoản mất thì không.
INTERNAL_DAILY_STOP = 0.015
INTERNAL_MONTHLY_STOP = 0.04

WEEKLY_DEFENSIVE = 0.03     # tụt >3% trong tuần -> Defensive Mode (risk x0.5)
MONTHLY_REVIEW = 0.05       # tụt >5% trong tháng -> dừng, đòi Full System Review

# THÊM 03/08 — CẦU DAO THÁNG THEO DỰ BÁO.
#
# Nguồn: Elder, A. (2014). *The New Trading for a Living*, ch.51 "The Six Percent
# Rule", tr.208: "The 6% Rule prohibits you from opening any new trades for the
# rest of the month when **the sum of your losses for the current month AND the
# risks in open trades** reach 6% of your account equity."
#
# Dự án đã áp đúng logic này ở TẦNG NGÀY (`projected_daily_loss` = lỗ đã thực
# hiện + rủi ro đang mở, chặn ở `DAILY_EMERGENCY`), và bình luận ở phần
# `DAILY_FLATTEN_PROJECTED` giải thích rõ vì sao chặn theo lỗ đã thực hiện là
# không đủ: các vị thế đang mở vẫn có thể cùng chạm SL sau đó.
#
# Lập luận ấy đúng y hệt ở tầng tháng, nhưng tầng tháng chỉ có
# `monthly_dd = max(0, −monthly_profit)` — thuần lỗ đã phản ánh vào equity. Một
# tháng đang lỗ 4,5% với 0,9% rủi ro đang mở thực chất đã ở 5,4%, vượt ngưỡng
# review, mà hệ thống vẫn cho mở lệnh mới.
#
# NGƯỠNG DÙNG CHUNG `MONTHLY_REVIEW`, không đặt số riêng: nhánh dự báo nằm TRƯỚC
# trong chuỗi kiểm tra nên nó bắt sớm hơn (dự báo >= thực hiện luôn đúng). Hai
# nhánh khác nhau ở HỆ QUẢ chứ không ở ngưỡng:
#   * dự báo chạm  -> ngừng mở lệnh mới, vị thế cũ vẫn được quản lý bình thường
#   * thực hiện chạm -> dừng hẳn, đòi Full System Review
# Đặt hai ngưỡng khác nhau sẽ làm một trong hai nhánh thành mã chết — đúng loại
# lỗi mà bình luận ở `DAILY_EMERGENCY` đã ghi lại (nhánh 4% không bao giờ chạy
# vì nhánh flatten bắt trước).
MONTHLY_PROJECTED_BLOCK = MONTHLY_REVIEW

# ĐÓNG LỆNH CHỦ ĐỘNG — lớp bảo vệ MẠNH NHẤT, và là lớp duy nhất thực sự bảo đảm
# không vi phạm giới hạn ngày.
#
# VÌ SAO CHẶN ENTRY LÀ KHÔNG ĐỦ. Ở mốc daily drawdown 4%, dừng mở lệnh mới vẫn
# để lại các vị thế ĐANG MỞ với tổng rủi ro tới `MAX_OPEN_RISK` = 2%. Nếu tất cả
# cùng chạm SL trong cùng ngày đó: 4% + 2% = 6% > giới hạn cứng 5%. Tài khoản
# chết mà mọi lớp bảo vệ đều "đã hoạt động đúng thiết kế".
#
# Nên ở đây có HAI cơ chế, không phải một:
#   * DỰ BÁO  — `projected_daily_loss()`: lỗ đã thực hiện CỘNG rủi ro đang mở.
#               Đây mới là con số phải so với giới hạn, không phải lỗ hiện tại.
#   * ĐÓNG    — khi dự báo chạm `DAILY_FLATTEN_PROJECTED`, đóng SẠCH vị thế.
#
# Đóng lệnh chốt lỗ ở mức hiện tại và bỏ mất khả năng hồi. Đó là đánh đổi CÓ CHỦ
# Ý: một ngày lỗ 4% còn giao dịch tiếp được, một lần vi phạm 5% là hết.
DAILY_FLATTEN_PROJECTED = 0.045   # lỗ ngày DỰ BÁO chạm 4,5% -> đóng sạch
DAILY_FLATTEN_REALIZED = 0.04     # hoặc lỗ ngày THỰC chạm 4,0% -> đóng sạch

# ---------------------------------------------------------------- rủi ro mỗi lệnh
# SIẾT XUỐNG 31/07 SAU KHI ĐO — không phải chọn cho "an toàn hơn cho chắc".
#
# `scratch/dd_tightening_2026-07-31.py` phát lại đúng chuỗi 183 lệnh của danh
# mục ở nhiều mức risk. Drawdown tính bằng R do chuỗi lệnh quyết định và không
# đổi, nên DD tính bằng % tỷ lệ gần như tuyến tính với risk mỗi lệnh:
#
#     risk/lệnh   DD đỉnh   lỗ ngày   lãi 3,5 năm
#       0,50%      6,63%     2,16%      +114,7%
#       0,35%      4,68%     1,21%       +71,3%
#       0,30%      4,03%     0,96%       +58,8%
#       0,25%      3,37%     0,74%       +47,1%     <- CHỌN
#       0,20%      2,70%     0,55%       +36,3%
#
# Chọn 0,25% vì đây là mức cao nhất còn nằm TRỌN trong cả hai mục tiêu (DD tối
# đa <=4%, lỗ ngày <=1%) với biên dự phòng thật, chứ không vừa chạm vạch như
# 0,30%. Backtest luôn lạc quan hơn live; một cấu hình đặt đúng ranh giới trong
# backtest là cấu hình sẽ vượt ranh giới ngoài đời.
#
# Cái giá đã biết và chấp nhận: lãi 3,5 năm từ +114,7% xuống +47,1%, tức
# ~0,9%/tháng và cần ~10-12 tháng để đạt +10% của Challenge. Challenge không có
# giới hạn thời gian nên đó là cái giá chấp nhận được — mất tài khoản thì không.
#
# ĐÃ THỬ VÀ BÁC BỎ: vol-targeting (scale risk nghịch với biến động thực hiện).
# Giả thuyết là drawdown tụ vào cụm biến động cao nên cắt size ở đó hiệu quả hơn
# hạ risk phẳng. ĐO ĐƯỢC NGƯỢC LẠI: ở CÙNG mức DD đỉnh, hạ phẳng cho nhiều lợi
# nhuận hơn 14-25 điểm phần trăm. Lý do rõ khi nhìn lại: danh mục toàn
# trend-following, mà lệnh thắng lớn nhất của trend đến ĐÚNG trong giai đoạn
# biến động cao — cắt size ở đó là cắt vào phần lãi, không phải phần lỗ.
# `RISK_PREFERRED` (0,25%) và `RISK_MIN` (0,125%) ĐÃ XOÁ 09/08. Chúng thuộc mô
# hình risk-theo-tỷ-lệ-equity, đã bị mô hình SIZING THEO ĐỆM bên dưới thay thế:
# ngân sách nay là `buffer_k × min(đệm tổng, đệm ngày)`, không còn mốc "risk bình
# thường" hay "sàn risk" nào.
#
# Không hằng nào trong hai hằng ấy còn được đọc — nhưng cả hai vẫn nằm trong
# `governed_constants` với mô tả nói chúng đang điều tiết risk mỗi lệnh, và
# docstring `risk_fraction()` vẫn khai có kẹp sàn `RISK_MIN`. Ba bề mặt cùng mô
# tả một cơ chế không tồn tại: ai siết `RISK_MIN` qua đường quản trị sẽ thấy hệ
# thống nhận thay đổi rồi không có gì xảy ra. Xoá đúng hơn là giữ một con số chỉ
# để nhìn cho yên tâm.
#
# 0,50% — trần tuyệt đối MỖI LỆNH. PHẢI nhỏ hơn hẳn `MAX_OPEN_RISK` (1,00%),
# nếu không nó không còn ràng buộc thêm gì so với trần danh mục: một lệnh đơn lẻ
# được phép chiếm 100% ngân sách rủi ro của cả danh mục thì "trần mỗi lệnh" chỉ
# là một cái tên. Đặt 0,50% cho phép tối thiểu 2 vị thế cùng lúc.
RISK_ABSOLUTE_MAX = 0.005

# ============================================================ SIZING THEO ĐỆM
# THAY ĐỔI THIẾT KẾ 31/07 (đợt 3) — sửa một sai lầm về KHUNG QUY CHIẾU.
#
# Sizing "x% của equity" ngầm giả định dư địa rủi ro tỷ lệ với equity. Với FTMO
# thì KHÔNG: Max Loss là sàn TĨNH $90.000, không trôi theo đỉnh. Dư địa thật là
# KHOẢNG CÁCH TỚI SÀN, và khoảng cách đó thay đổi hoàn toàn khác equity:
#
#     equity $100.000 -> đệm $10.000
#     equity $108.000 -> đệm $18.000   (lãi rồi thì có nhiều đệm hơn hẳn)
#     equity  $94.000 -> đệm  $4.000   (lỗ rồi thì còn rất ít)
#
# Risk theo đệm có một tính chất mà risk theo equity không có: nó **tự tiến về
# 0 khi equity tiến về sàn**, nên về mặt toán học không thể vi phạm giới hạn
# tổng. Đó là đảm bảo CẤU TRÚC, không phải một ngưỡng ai đó phải nhớ kiểm.
#
# Hai ràng buộc phải xét CÙNG LÚC, lấy cái chặt hơn:
#     đệm_tổng = equity − vốn_ban_đầu × 90%
#     đệm_ngày = equity − (balance_nửa_đêm − 5% × vốn_ban_đầu)
#
# VÌ SAO HAI HỆ SỐ KHÁC NHAU THEO PHA — và đây không phải "liều hơn lúc thi":
#     Trượt Challenge  = mất phí Challenge.
#     Mất tài khoản funded = mất cả dòng thu nhập nhiều năm.
# Hai mất mát đó khác nhau hàng bậc độ lớn, nên mức rủi ro hợp lý cũng phải
# khác. Đi nhanh qua pha thi CHÍNH LÀ phục vụ mục tiêu dài hạn: được cấp vốn
# sớm rồi vận hành thận trọng, thay vì thận trọng suốt pha thi rồi không bao
# giờ tới được chỗ sinh lời thật.
#
# Con số lấy từ `scratch/ftmo_optimizer_2026-07-31.py` — quét 36 thời điểm bắt
# đầu, chấm theo luật FTMO theo đúng thứ tự thời gian:
#
#     k       P(pass)  P(rớt)  ngày(trung vị)  DD xấu nhất  biên tổng còn
#    0,05      91,7%     0%         262            3,37%        68,3%
#    0,075    100,0%     0%         176            5,04%        52,6%
#    0,10     100,0%     0%         144            6,61%        37,7%   ← pha thi
#    0,15     100,0%     0%          91            9,63%        18,7%   <- quá sát
#
# Chọn 0,10 cho pha thi: mức NHANH NHẤT còn giữ được hơn một phần ba hạn mức
# tổng làm dự phòng. Backtest luôn lạc quan hơn live nên biên đó là bắt buộc,
# không phải cho đẹp. 0,15 nhanh hơn nhiều nhưng chỉ còn 18,7% biên — một chuỗi
# thua tệ hơn quá khứ một chút là chạm sàn.
#
# Chọn 0,05 cho funded: DD 3,37%, đúng mục tiêu <=4%, và nó bảo vệ thứ đáng bảo
# vệ nhất — dòng payout.
#
# ĐO LẠI 03/08 BẰNG ĐÚNG CƠ CHẾ NÀY (`scratch/ftmo_cppi_two_mode_2026-08-03.py`)
# ----------------------------------------------------------------------------
# Mọi phép đo Monte Carlo trước đó (kể cả bảng ngay trên) mô phỏng RISK CỐ ĐỊNH
# — mỗi lệnh mạo hiểm cùng một tỷ lệ equity. Production không làm thế. Chạy lại
# 5.000 đường block-bootstrap trên 5.472 lệnh của 5 chiến lược LIVE, lần này
# dùng đúng công thức CPPI bên dưới:
#
#     pha thi (mục tiêu +10%, sàn tĩnh 90%, lỗ ngày 5%)
#       k       risk lệnh 1   P(PASS)   n lệnh   tháng   kỳ vọng kể cả thi lại
#      0,04       0,200%       100,0%     138      6,7          6,7
#      0,10       0,500%        99,8%      66      3,2          3,2   <- đang dùng
#      0,30       0,500%        85,4%      50      2,4          2,9
#
#     pha funded (chạy ~0,8 năm rồi đo)
#       k       risk lệnh 1   P(mất TK)   lãi trung vị
#      0,05       0,250%         0,0%        13,9%          <- đang dùng
#      0,10       0,500%         0,0%        23,1%
#
# Vì sao P(hỏng) gần 0 ở đây trong khi mô phỏng risk-cố-định trước đó cho 28%:
# risk theo đệm tự co lại khi equity xuống, nên đường equity TIỆM CẬN sàn chứ
# không cắt qua. Đó là tính chất cấu trúc đã nói ở đầu khối này, và nó chỉ hiện
# ra khi mô phỏng đúng cơ chế.
#
# GIỚI HẠN của phép đo — để không ai đọc bảng trên rồi tăng k một cách vô tư:
# mô phỏng giả định mỗi lệnh thua đúng 1R. Gap cuối tuần và trượt giá vượt qua
# dừng lỗ đều làm mất NHIỀU HƠN 1R, và CPPI không bảo vệ được trước cú nhảy
# rời rạc. Đó là lý do vẫn giữ trần `RISK_ABSOLUTE_MAX` thay vì thả cho công
# thức đệm tự quyết.
RISK_BUFFER_K_CHALLENGE = 0.10
RISK_BUFFER_K_FUNDED = 0.05

# ---------------------------------------------------------------------------
# HAI MODE CẤU HÌNH QUA .env (yêu cầu người dùng 03/08)
# ---------------------------------------------------------------------------
# "Mode thi ưu tiên nhanh, mode giao dịch ưu tiên chắc" — hệ thống ĐÃ có đúng
# hai mode đó từ trước dưới dạng `RISK_BUFFER_K_CHALLENGE`/`_FUNDED`, chọn tự
# động theo `phase`. Phần thêm ở đây chỉ là cho phép chỉnh qua `.env`.
#
# THIẾT KẾ: mode SUY TỪ `phase`, `.env` chỉ ĐỔI GIÁ TRỊ hoặc ÉP mode.
# Cố ý KHÔNG tạo một biến "mode" độc lập song song với `phase`: hai nguồn sự
# thật cho cùng một quyết định sẽ lệch nhau, và lúc lệch thì cái sai là cái
# quyết định cỡ lệnh thật.
#
#     FTMO_RISK_MODE          auto (mặc định) | speed | safe
#                             auto  = theo phase: CHALLENGE/VERIFICATION -> speed,
#                                     FUNDED -> safe
#                             speed = luôn dùng k của pha thi
#                             safe  = luôn dùng k của pha funded (dùng khi muốn
#                                     chạy thận trọng ngay trong pha thi)
#     FTMO_RISK_K_CHALLENGE   số thực, mặc định 0.10
#     FTMO_RISK_K_FUNDED      số thực, mặc định 0.05
#
# Giá trị sai (không phải số, <= 0, hoặc > K_MAX) làm hệ thống DỪNG NGAY lúc
# khởi động thay vì lặng lẽ quay về mặc định. Sai cấu hình rủi ro mà chạy tiếp
# với con số khác cái người vận hành tưởng là kịch bản tệ nhất.
K_MAX = 0.50            # trần vệ sinh: k>0,5 thì đệm ngày cạn sau 2 lệnh thua
_VALID_MODES = ("auto", "speed", "safe")


def _doc_k_env(var_name: str, default_value: float) -> float:
    """Đọc cấu hình hệ số k từ biến môi trường."""
    import os
    raw = os.environ.get(var_name)
    if raw is None or not raw.strip():
        return default_value
    try:
        v = float(raw.strip())
    except ValueError as e:
        raise ValueError(
            f"{var_name}={raw!r} trong .env không phải số thực. "
            f"Đây là hệ số quyết định cỡ lệnh — dừng thay vì đoán.") from e
    if not (0.0 < v <= K_MAX):
        raise ValueError(
            f"{var_name}={v} nằm ngoài khoảng hợp lệ (0, {K_MAX}]. "
            f"k<=0 làm mọi lệnh có cỡ 0; k>{K_MAX} làm đệm ngày cạn chỉ sau "
            f"vài lệnh thua.")
    return v


RISK_BUFFER_K_CHALLENGE = _doc_k_env("FTMO_RISK_K_CHALLENGE",
                                     RISK_BUFFER_K_CHALLENGE)
RISK_BUFFER_K_FUNDED = _doc_k_env("FTMO_RISK_K_FUNDED", RISK_BUFFER_K_FUNDED)


def risk_mode() -> str:
    """'speed' | 'safe' — mode đang hiệu lực, CHƯA xét pha.

    Trả 'auto' nghĩa là để pha quyết định; hàm này quy về giá trị cuối nên
    caller không phải xử lý 'auto'.
    """
    import os
    raw = (os.environ.get("FTMO_RISK_MODE") or "auto").strip().lower()
    if raw not in _VALID_MODES:
        raise ValueError(
            f"FTMO_RISK_MODE={raw!r} không hợp lệ. Chọn một trong "
            f"{_VALID_MODES}.")
    return raw


def buffer_k(st: Optional[Dict[str, Any]] = None) -> float:
    """Hệ số đệm đang hiệu lực — SSOT cho `buffer_risk_usd`.

    Thứ tự quyết định: `.env` ép mode (nếu có) -> nếu không thì suy từ `phase`.
    """
    mode = risk_mode()
    if mode == "speed":
        return RISK_BUFFER_K_CHALLENGE
    if mode == "safe":
        return RISK_BUFFER_K_FUNDED
    st = st if st is not None else _read_state()
    return (RISK_BUFFER_K_FUNDED if st.get("phase") == PHASE_FUNDED
            else RISK_BUFFER_K_CHALLENGE)

# Tổng rủi ro của MỌI vị thế đang mở. Hạ 2% -> 1% cùng đợt siết risk 31/07: ở
# 0,25%/lệnh, trần 1% cho phép 4 vị thế mở đồng thời. Nếu TẤT CẢ cùng chạm SL
# trong một ngày thì tổn thất là -1%, nằm trọn trong "vùng bình thường" của bảng
# ngưỡng, thay vì -2% là vùng cảnh báo như trước.
#
# Con số này quyết định kịch bản xấu nhất trong MỘT ngày, nên phải đặt từ phía
# HẬU QUẢ (lỗ ngày tối đa chấp nhận được) chứ không từ phía tiện lợi (muốn mở
# được bao nhiêu lệnh cùng lúc).
#
# NÂNG 1% -> 2% NGÀY 01/08, và lý do KHÔNG phải "muốn mở nhiều lệnh hơn".
# ----------------------------------------------------------------------------
# Lập luận đặt ra con số 1% (viết ngay phía trên) là: chặn entry ở mốc lỗ ngày 4%
# vẫn để lại vị thế đang mở tới `MAX_OPEN_RISK`, nên 4% + 1% = 5% vừa đúng giới
# hạn cứng. Lập luận đó BỎ SÓT lớp bảo vệ mạnh nhất của chính hệ thống:
# `DAILY_FLATTEN_PROJECTED = 4,5%` đóng SẠCH vị thế dựa trên lỗ đã thực hiện
# CỘNG rủi ro đang mở. Nghĩa là tổng đó bị chặn ĐỘNG trước khi chạm 5%, bất kể
# `MAX_OPEN_RISK` bằng bao nhiêu. Trần tĩnh 1% đang phòng lại một kịch bản mà
# lớp dự báo đã phòng rồi — phòng hai lần cùng một thứ, và lần thứ hai tốn tiền.
#
# CÁI GIÁ ĐO ĐƯỢC của trần 1% — BẰNG CHỨNG TỪ HỆ XAUUSD, giữ lại vì nó là lý do
# lịch sử của con số 2%, KHÔNG phải phép đo trên hệ Forex:
#   `gold_directional` = 70% × 1% = 0,7% equity mà mỗi lệnh tới 0,5% — chỉ 1,4
#   lệnh vừa trần. Kỳ thi 2026: lệnh XauR 22/01 (thắng lớn nhất, +8,0R) bị cắt
#   còn $291 thay vì $425 vì hai vị thế SwingDon đã lấp trần, trong khi mọi lệnh
#   THUA đứng một mình đều được cấp đủ. Hệ cấp vốn NGƯỢC.
#
# Ở HỆ FOREX lập luận trên KHÔNG áp dụng nguyên: 27 chân không có dừng lỗ theo
# giá, nên "rủi ro mở" không đo được bằng tổng khoảng cách tới SL. Đại lượng thay
# thế là tổn thất một ngày ở phân vị xấu — xem `portfolio_sizing.open_risk_estimate`,
# và ràng buộc thật sự chặn là trần đòn bẩy 3,7x trong `ftmo_leverage_policy`.
#
# KIỂM LẠI AN TOÀN Ở MỨC 2%:
#   * Kịch bản chuỗi: lỗ dần tới 4,5% dự báo -> `ftmo_guard` đóng sạch. Trượt giá
#     khi đóng ước tính 0,2-0,3% -> tổng ~4,8% < 5%. Không đổi so với mức 1%,
#     vì lớp chặn là DỰ BÁO chứ không phải trần tĩnh.
#   * Kịch bản gap: mọi vị thế cùng nhảy qua SL trong một cú gap. 2% × hệ số
#     trượt 1,5 = 3% tức thời. Còn cách sàn 10% rất xa, và cách giới hạn ngày 5%
#     một khoảng đủ để sống nếu lỗ ngày trước đó dưới 2%.
#   * `RISK_ABSOLUTE_MAX` (0,5%) vẫn nhỏ hơn hẳn, nên trần mỗi lệnh còn nguyên
#     ý nghĩa ràng buộc.
#
# 2% cho phép 4 lệnh đồng thời ở 0,5% — đúng cấu hình danh mục 4-6 chiến lược.
MAX_OPEN_RISK = 0.02

# ---------------------------------------------------------------- mục tiêu từng pha
PHASE_CHALLENGE = "CHALLENGE"
PHASE_VERIFICATION = "VERIFICATION"
PHASE_FUNDED = "FUNDED"
PHASE_TARGETS = {PHASE_CHALLENGE: 0.10, PHASE_VERIFICATION: 0.05, PHASE_FUNDED: None}
MIN_TRADING_DAYS = 4

# KHÔNG CÓ THỜI HẠN TỐI ĐA — ràng buộc quan trọng nhất cho thiết kế theo trạng
# thái thị trường, xác nhận trên ftmo.com ngày 02/08/2026.
#
# FTMO đã bỏ giới hạn 30/60 ngày lịch: "There is no time limit to reach the
# Profit Target, as the Trading Period is unlimited." Ràng buộc hoạt động duy
# nhất là MIN_TRADING_DAYS ở trên — 4 ngày giao dịch, không cần liên tiếp.
#
# Hệ quả thiết kế: "KHÔNG giao dịch trong trạng thái bất lợi rồi chờ" là một
# chiến lược HỢP LỆ và có thể thắng. Hệ thống không cần kiếm tiền trong nhịp
# giảm của vàng; nó chỉ cần không lỗ và đợi trạng thái thuận. Điều này khớp
# chính xác với thứ tự ưu tiên đã chốt: bảo vệ tài khoản trước, tăng trưởng sau.
#
# Không có hằng số nào cho điều này vì không có gì để kiểm tra: không có thời
# hạn nghĩa là KHÔNG có luật nào phải thực thi. Một hằng `KHONG_CO_THOI_HAN =
# True` mà không ai đọc chỉ là ghi chú đội lốt mã.

# NHƯNG có điều khoản BẤT HOẠT ĐỘNG. Điều khoản của FTMO nói prolonged inactivity
# CÓ THỂ dẫn tới chấm dứt Challenge/Verification; con số ngày cụ thể không được
# công bố rõ trong tài liệu công khai, nên 21 ngày ở đây là ngưỡng CẢNH BÁO tự
# đặt, chọn thấp hơn con số 30 ngày thường được nhắc để còn thời gian xử lý.
#
# Ngưỡng này KHÔNG được dùng để ép vào lệnh. Vào một lệnh chỉ để giữ tài khoản
# sống là vào lệnh không có edge, và đó đúng là thứ cả hệ thống này được dựng lên
# để tránh. Nó chỉ dùng để BÁO cho người vận hành, người có thể xin freeze tài
# khoản (FTMO cho phép) hoặc chấp nhận rủi ro.
INACTIVITY_WARNING_DAYS = 21

# Các cỡ tài khoản FTMO bán ra. Dùng để phát hiện việc chốt nhầm vốn ban đầu —
# xem `update_baselines`.
# Các cỡ tài khoản dùng để LÀM TRÒN LÊN khi chốt vốn ban đầu — xem
# `_resolve_initial_balance()`. Mở rộng 08/08 để phủ tài khoản lớn (người dùng
# nêu 200k/400k) và các mức gộp nhiều tài khoản mà FTMO cho phép.
STANDARD_ACCOUNT_SIZES = (10_000.0, 25_000.0, 50_000.0, 100_000.0, 200_000.0,
                          400_000.0, 600_000.0, 1_000_000.0, 2_000_000.0)

# BEST DAY RULE — mục tiêu giao dịch tôi đã BỎ SÓT ở bản đầu, phát hiện khi tra
# lại tài liệu FTMO hiện hành. Áp dụng cho CẢ hai pha của 2-Step VÀ tài khoản
# funded:
#
#     ngày lãi lớn nhất <= 50% TỔNG lãi của mọi ngày dương
#
# Vượt ngưỡng KHÔNG phải vi phạm — nó chỉ khiến pha chưa được duyệt, và cách gỡ
# duy nhất là giao dịch tiếp cho tới khi tỷ lệ tụt xuống dưới 50%.
#
# VÌ SAO ĐIỀU NÀY QUAN TRỌNG VỚI ĐÚNG HỆ THỐNG NÀY: danh mục hiện tại ra ~4,4
# lệnh/tháng với Reward:Risk 3,0. Ở tần suất và tỷ lệ đó, một ngày thắng lớn rất
# dễ chiếm quá nửa tổng lãi các ngày dương — tức hệ thống có thể chạm +10% mà
# VẪN không được duyệt.
BEST_DAY_MAX_SHARE = 0.50

# ---------------------------------------------------------------- Payout Protection
# Càng lãi nhiều trong tháng, càng ít lý do mạo hiểm phần đã kiếm được. Bảng này
# là "Payout Protection Mode" trong tài liệu: đổi HÀNH VI theo lãi tháng, không
# chỉ đổi con số.
MONTHLY_PROFIT_TIERS = (
    (0.08, "PAYOUT_PROTECTION", 0.40),   # >8%: chỉ tín hiệu xuất sắc, risk x0.40
    (0.06, "CAPITAL_PRESERVATION", 0.60),
    (0.04, "CONSERVATIVE", 0.80),
    (0.00, "NORMAL", 1.00),
)

_lock = threading.RLock()
_STATE_FILE: Optional[Path] = None


def _state_file() -> Path:
    """Lấy đường dẫn tới file lưu trạng thái FTMO."""
    global _STATE_FILE
    if _STATE_FILE is None:
        from src.python.core.config import LIVE_DIR
        _STATE_FILE = Path(LIVE_DIR) / "ftmo_state.json"
    return _STATE_FILE


def _now() -> datetime:
    """Đồng hồ hệ thống — qua `get_clock()` để backtest/SimBroker dùng được."""
    from src.python.core.infra.clock import get_clock
    return get_clock().now()


def trading_day(when: Optional[datetime] = None) -> date:
    """Ngày giao dịch theo ĐÚNG múi giờ FTMO. Xem điểm dễ sai #1 ở đầu file."""
    t = when or _now()
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(FTMO_TZ).date()


def _default_state() -> Dict[str, Any]:
    """Khởi tạo trạng thái mặc định của FTMO."""
    return {
        "phase": PHASE_CHALLENGE,
        "initial_balance": 0.0,
        "day": None,                     # ISO date theo giờ FTMO
        "day_baseline_exact": False,     # mốc ngày đã dựng từ lịch sử deal chưa
        "day_start_balance": 0.0,
        "trading_days": [],              # các ngày ĐÃ mở ít nhất 1 lệnh
        "week": None,                    # "YYYY-Www" (ISO)
        "week_start_equity": 0.0,
        "month": None,                   # "YYYY-MM"
        "month_start_equity": 0.0,
        "monthly_profit_lock": 0.0,           # Profit Lock — xem `monthly_mode()`
    }


def _read_state() -> Dict[str, Any]:
    """Đọc state, có đường phục hồi từ bản `.bak`.

    Phải dùng thư viện đọc state có hỗ trợ phục hồi từ bản `.bak` (như
    `load_json()`) thay vì đọc thô `read_text()`. Khi file chính bị lỗi,
    nếu không có cơ chế phục hồi, state sẽ âm thầm reset về mặc định,
    gây sai lệch giới hạn ngày.
    """
    global _state_read_failed
    base = _default_state()
    try:
        from src.python.core.infra.state_store import load_json
        st = load_json(str(_state_file()))
        if isinstance(st, dict):
            base.update(st)
            if _state_read_failed:
                _state_read_failed = False
                log("🏦 [FTMO] đọc lại state THÀNH CÔNG — gỡ cờ suy giảm ĐỌC.")
    except Exception as e:
        # ĐỌC LỖI PHẢI FAIL-CLOSED.
        # ------------------------------------------------------------------
        # Nếu đọc state lỗi và không cảnh báo (ví dụ im lặng trả về mặc định),
        # bot có thể báo daily_dd = 0.00% trong khi thực tế đã lỗ 4.00%.
        # Khi đó, bot sẽ giao dịch xuyên qua giới hạn an toàn.
        #
        # Bật cờ suy giảm ở đây sẽ giúp nhánh kiểm tra chặn entry ngay lập tức,
        # tránh giao dịch mù.
        if not _state_read_failed:
            log_error(
                f"❌ [FTMO] KHÔNG đọc được state ({e}) — bật cờ SUY GIẢM, chặn "
                f"entry mới cho tới khi đọc lại được. KHÔNG dùng giá trị mặc "
                f"định để tính lỗ ngày: mốc sai sẽ báo daily_dd 0% ngay sau một "
                f"ngày thua và hạ sàn tuyệt đối xuống dưới sàn thật của FTMO.")
        _state_read_failed = True
    return base


# Cờ suy giảm: bật khi KHÔNG ghi được state. Xem `_write_state`.
_state_degraded = False

# Cờ suy giảm ĐỌC — TÁCH RIÊNG khỏi cờ ghi.
# Dùng chung một cờ thì hai đường đọc/ghi có thể đánh nhau.
_state_read_failed = False


def _write_state(st: Dict[str, Any]) -> None:
    """Ghi state. Ghi hỏng -> bật cờ suy giảm để `evaluate()` fail-closed.

    QUAN TRỌNG: Phải kiểm tra giá trị trả về của `save_json_atomic()`.
    Hàm đó không tự raise ngoại lệ mà bắt lỗi bên trong và trả về False.
    Nếu bỏ qua, state không được lưu nhưng hệ thống vẫn tưởng đã lưu thành công,
    kéo theo hậu quả: `_read_state()` luôn lấy state cũ, mốc day_start_balance
    liên tục lấy bằng balance hiện tại, làm mọi chỉ báo rủi ro về 0.
    """
    global _state_degraded
    try:
        from src.python.core.infra.state_store import save_json_atomic
        ok = bool(save_json_atomic(str(_state_file()), st))
    except Exception as e:
        ok = False
        log_error(f"❌ [FTMO] ngoại lệ khi ghi state: {e}")
    if not ok:
        if not _state_degraded:
            log_error("❌ [FTMO] KHÔNG GHI ĐƯỢC STATE — mọi thước đo drawdown "
                      "không còn đáng tin. Chặn vào lệnh (fail-closed) cho tới "
                      "khi ghi lại được. Kiểm tra dung lượng/quyền ghi LIVE_DIR.")
        _state_degraded = True
    elif _state_degraded:
        _state_degraded = False
        log("✅ [FTMO] Ghi state đã hoạt động trở lại.")


# ============================================================ mốc ngày / tháng
def _resolve_initial_balance(observed: float) -> float:
    """Vốn ban đầu THẬT của tài khoản. Đây là MẪU SỐ của mọi giới hạn FTMO.

    QUY TẮC AN TOÀN: KHI KHÔNG CHẮC, LÀM TRÒN LÊN
    ==============================================
    Sàn Max Loss = vốn ban đầu × 90%. Hai chiều sai KHÔNG đối xứng:

        ước THẤP  -> sàn thấp hơn sàn THẬT -> bot giao dịch xuyên qua vạch chết
                     của FTMO trong khi mọi lớp bảo vệ báo xanh -> MẤT TÀI KHOẢN
        ước CAO   -> sàn cao hơn sàn thật -> bot dừng sớm -> mất cơ hội

    Nên mọi phép suy đoán ở đây phải nghiêng về phía CAO.

    LÀM TRÒN LÊN VỀ MỐC CHUẨN ĐỂ ĐẢM BẢO AN TOÀN
    ============================================
    Không được làm tròn về mốc chuẩn GẦN NHẤT vì mốc đó có thể NHỎ HƠN số quan sát.
    Ví dụ:

        quan sát    chốt thành   sàn code tính   sàn THẬT
        $400.000    $200.000       $180.000      $360.000   <- thấp hơn 180k
        $300.000    $200.000       $180.000      $270.000   <- thấp hơn  90k
        $150.000    $100.000        $90.000      $135.000   <- thấp hơn  45k

    Nếu chốt nhỏ hơn, tài khoản $400.000 có thể giao dịch tiếp tới $180.000
    (180 nghìn đô dưới vạch chết) mà không ai cản.

    THỨ TỰ QUYẾT ĐỊNH
    =================
    1. `.env FTMO_INITIAL_BALANCE` — người vận hành biết chắc thì họ đúng.
       (Bản cũ có dòng log BẢO người dùng đặt biến này, nhưng KHÔNG code nào
       đọc nó. Làm theo hướng dẫn không có tác dụng gì — đúng lúc cần nhất.)
    2. Số quan sát nếu nó TRÙNG một cỡ chuẩn trong sai số 2% (ngày đầu bình thường).
    3. Làm TRÒN LÊN mốc chuẩn gần nhất >= số quan sát (gắn vào tài khoản đang
       chạy dở / mất state -> vốn ban đầu chắc chắn >= equity hiện tại).
    4. Vượt mọi mốc trong bảng -> dùng chính số quan sát, và BÁO TO: đó là cận
       dưới đúng, nhưng nếu tài khoản đang lỗ thì nó vẫn thấp hơn vốn thật.
    """
    import os

    raw = (os.environ.get("FTMO_INITIAL_BALANCE") or "").strip()
    if raw:
        try:
            v = float(raw.replace(",", "").replace("_", ""))
        except ValueError as e:
            raise ValueError(
                f"FTMO_INITIAL_BALANCE={raw!r} không phải số. Đây là MẪU SỐ của "
                f"mọi giới hạn FTMO — dừng thay vì đoán.") from e
        if v <= 0:
            raise ValueError(f"FTMO_INITIAL_BALANCE={v} phải > 0.")
        log(f"🏦 [FTMO] Vốn ban đầu lấy từ .env: ${v:,.2f} (đè lên số quan sát "
            f"${observed:,.2f}) — sàn tuyệt đối ${v * (1 - MAX_LOSS_HARD):,.2f}")
        return v

    exact = min(STANDARD_ACCOUNT_SIZES, key=lambda x: abs(x - observed))
    if abs(exact - observed) / exact <= 0.02:
        return float(observed)

    mixed = [x for x in STANDARD_ACCOUNT_SIZES if x >= observed]
    if mixed:
        chosen = min(mixed)
        log_error(
            f"⚠️ [FTMO] Số dư quan sát ${observed:,.2f} không khớp cỡ tài khoản "
            f"chuẩn nào. Nhiều khả năng đây KHÔNG phải ngày đầu (mất state? gắn "
            f"vào tài khoản đang chạy dở?). LÀM TRÒN LÊN ${chosen:,.0f} — sàn "
            f"${chosen * (1 - MAX_LOSS_HARD):,.0f}. Làm tròn XUỐNG sẽ đặt sàn dưới "
            f"vạch chết thật của FTMO. Biết chắc vốn thật thì đặt "
            f"FTMO_INITIAL_BALANCE trong .env.")
        return float(chosen)

    log_error(
        f"⚠️ [FTMO] Số dư quan sát ${observed:,.2f} LỚN HƠN mọi cỡ trong bảng "
        f"chuẩn (tối đa ${max(STANDARD_ACCOUNT_SIZES):,.0f}). Dùng chính số quan "
        f"sát làm vốn ban đầu — đó là CẬN DƯỚI đúng, nhưng nếu tài khoản đang lỗ "
        f"thì vốn thật CAO HƠN và sàn thật cũng cao hơn. ĐẶT "
        f"FTMO_INITIAL_BALANCE trong .env để chắc chắn.")
    return float(observed)


def update_baselines(equity: float, balance: Optional[float] = None) -> Dict[str, Any]:
    """Chốt mốc đầu ngày / tuần / tháng nếu vừa sang kỳ mới. Idempotent.

    Gọi được từ hot path: khi chưa sang kỳ mới thì chỉ so sánh chuỗi rồi thoát.

    `equity` = equity HIỆN TẠI gồm floating.
    `balance` = số dư HIỆN TẠI (chỉ lệnh đã đóng). Bỏ trống -> dùng `equity`.

    VÌ SAO MỐC NGÀY PHẢI LÀ BALANCE, KHÔNG PHẢI EQUITY
    ---------------------------------------------------
    FTMO chốt hạn mức lỗ ngày bằng **balance lúc 00:00 CE(S)T**. Nếu nửa đêm
    đang giữ một vị thế lỗ, equity thấp hơn balance — chụp equity sẽ cho một mốc
    THẤP HƠN mốc thật, tức hệ thống tưởng mình còn nhiều dư địa hơn thực tế.

    HẠN CHẾ CÒN LẠI, ghi ở đây thay vì để nó im lặng: mốc được chụp ở chu kỳ
    ĐẦU TIÊN của ngày mới mà bot còn sống, không phải đúng 00:00. Bot tắt qua
    nửa đêm và bật lại lúc 08:00 với một vị thế đã đóng lỗ trong đêm sẽ chụp
    nhầm mốc thấp hơn. `ftmo_guard.midnight_balance()` dựng lại mốc đúng từ lịch
    sử deal và ghi đè qua `set_day_baseline()`; hàm này chỉ là phương án dự
    phòng khi không đọc được lịch sử.
    """
    d = trading_day()
    today = d.isoformat()
    iso = d.isocalendar()
    week = f"{iso[0]}-W{iso[1]:02d}"
    month = today[:7]
    base_balance = float(balance if balance is not None else equity)
    # Cùng lý do với `set_day_baseline()`: mốc ngày dưới đây được ghi thẳng khi
    # sang ngày mới, không qua phép so nào chặn được NaN. MT5 trả equity hỏng
    # lúc mất kết nối là chuyện có thật.
    if not math.isfinite(base_balance) or base_balance <= 0:
        log_error(f"⚠️ [FTMO] balance/equity = {base_balance!r} không dùng được — "
                  f"BỎ QUA cập nhật mốc chuẩn (giữ mốc cũ, không ghi số hỏng).")
        return
    with _lock:
        st = _read_state()
        changed = False
        if float(st.get("initial_balance") or 0.0) <= 0 and base_balance > 0:
            st["initial_balance"] = _resolve_initial_balance(base_balance)
            changed = True
            log(f"🏦 [FTMO] Chốt vốn ban đầu ${base_balance:,.2f} — hạn mức lỗ ngày "
                f"${DAILY_LOSS_HARD * base_balance:,.0f}, sàn tuyệt đối "
                f"${base_balance * (1 - MAX_LOSS_HARD):,.2f}")
        if st.get("day") != today:
            st["day"] = today
            st["day_start_balance"] = base_balance
            st["day_baseline_exact"] = False
            changed = True
            # PHẢI dùng `daily_loss_amount(st)`, KHÔNG phải hằng số module
            # `DAILY_LOSS_AMOUNT`. Hằng số đó là giá trị MẶC ĐỊNH cho tài khoản
            # $100.000; trên tài khoản kích thước khác nó sai theo đúng tỷ lệ
            # lệch. Đo được trên tài khoản $10.000: log báo hạn mức $5.000 và
            # sàn equity $5.000 — tức thông báo cho người vận hành rằng họ được
            # phép mất 50% trong một ngày, trong khi hạn mức thật là $500.
            #
            # Đây "chỉ" là dòng log, nhưng nó là dòng người vận hành đọc để biết
            # còn cách giới hạn bao xa. Một lớp bảo vệ báo sai biên an toàn của
            # chính nó thì tệ hơn là không báo gì.
            _limit_usd = daily_loss_amount(st)
            log(f"🏦 [FTMO] Ngày giao dịch mới {today} (giờ Praha) — mốc balance "
                f"${base_balance:,.2f}, hạn mức lỗ ngày ${_limit_usd:,.0f} "
                f"(sàn equity ${base_balance - _limit_usd:,.2f})")
        if st.get("week") != week:
            st["week"] = week
            st["week_start_equity"] = float(equity)
            changed = True
        if st.get("month") != month:
            st["month"] = month
            st["month_start_equity"] = float(equity)
            st["monthly_profit_lock"] = 0.0
            changed = True
            log(f"🏦 [FTMO] Tháng mới {month} — equity đầu tháng ${equity:,.2f}")
        # Mốc chưa chụp được (đọc broker lỗi -> 0) thì thử lại chu kỳ sau.
        if st.get("day_start_balance", 0.0) <= 0 and base_balance > 0:
            st["day_start_balance"] = base_balance
            changed = True
        if changed:
            _write_state(st)
        return st


def day_baseline_is_exact() -> bool:
    """Mốc balance đầu ngày đã được dựng từ lịch sử deal cho ĐÚNG ngày hôm nay chưa."""
    st = _read_state()
    return bool(st.get("day_baseline_exact")) and st.get("day") == trading_day().isoformat()


def set_day_baseline(balance: float, *, exact: bool = True) -> None:
    """Ghi đè mốc balance đầu ngày bằng giá trị dựng lại từ lịch sử deal.

    Chỉ ghi đè MỘT LẦN mỗi ngày (`day_baseline_exact`): mốc chính xác dựng từ
    lịch sử phải thắng mốc xấp xỉ chụp lúc khởi động, nhưng không được để một
    lần đọc lịch sử lỗi về sau ghi đè ngược lại mốc đã đúng.

    LÝ DO PHẢI DÙNG CON SỐ ĐÚNG TỪ LỊCH SỬ DEAL
    ------------------------------------------
    Không được dùng `min(mốc cũ, mốc mới)` để lấy ngưỡng an toàn. Lý do:
    sàn = mốc − 5% vốn ban đầu.
    Mốc THẤP hơn cho sàn THẤP hơn -> bot được lơi tay hơn, vi phạm sớm hơn.
    Phải luôn lấy giá trị chính xác dựng từ lịch sử làm chân lý.
    """
    # HỮU HẠN là điều kiện đầu tiên, không phải phép so.
    # -------------------------------------------------------------------------
    # `not balance` và `balance <= 0` đều KHÔNG bắt được `NaN`: NaN là truthy và
    # mọi so sánh với nó đều False. Nó chỉ không lọt tới đây nhờ TÌNH CỜ — phép
    # `abs(new - old) > 0.005` bên dưới cũng trả False cho NaN. Nhưng vế thứ hai
    # của cùng điều kiện, `or not st.get("day_baseline_exact")`, ngắn mạch thành
    # True ngay khi mốc chưa được đánh dấu chính xác, và lúc đó NaN được ghi
    # thẳng vào mốc chuẩn.
    #
    # Hậu quả: sàn tuyệt đối và hạn mức lỗ ngày đều tính từ mốc này, nên một NaN
    # ở đây làm MỌI ngưỡng dừng lỗ im lặng ngừng chặn cùng lúc — màn hình vẫn
    # hiện số, log vẫn chạy, chỉ các cổng là thôi hoạt động.
    if balance is None or not math.isfinite(float(balance)) or float(balance) <= 0:
        return
    with _lock:
        st = _read_state()
        old = float(st.get("day_start_balance") or 0.0)
        # Kiểm CẢ NGÀY, không chỉ cờ. Cờ `day_baseline_exact` chỉ
        # được reset trong `update_baselines()`, nên ở chu kỳ ĐẦU TIÊN của ngày
        # mới nó vẫn mang giá trị True TỪ HÔM QUA -> mốc đúng vừa dựng từ lịch
        # sử deal bị vứt bỏ, đúng chu kỳ nó cần nhất (bot khởi động lại sau nửa
        # đêm, sau một đêm có lệnh đóng lỗ).
        if (st.get("day_baseline_exact") and exact
                and st.get("day") == trading_day().isoformat()):
            return
        new = float(balance)
        today = trading_day().isoformat()
        # ĐÓNG DẤU NGÀY TRƯỚC, độc lập với việc giá trị mốc có đổi hay không.
        # Nếu chỉ ghi khi mốc thay đổi, trường hợp mốc đúng TRÙNG mốc đang có
        # (bot khởi động lại mà đêm qua không có deal nào) sẽ không đóng dấu,
        # và `update_baselines()` chạy sau đó tưởng vừa sang ngày mới rồi
        # ghi đè bằng balance hiện tại.
        if st.get("day") != today and exact:
            st["day"] = today
            _write_state(st)
        if abs(new - old) > 0.005 or not st.get("day_baseline_exact"):
            st["day_start_balance"] = new
            st["day_baseline_exact"] = bool(exact)
            # GHI LUÔN `st["day"]`.
            # Tránh trường hợp `evaluate()` gọi `update_baselines()` ngay sau đó,
            # thấy `st["day"]` chưa đổi nên lại đè `day_start_balance` bằng số hiện tại.
            _write_state(st)
            if abs(new - old) > 0.005:
                direction = "CHẶT HƠN" if new > old else "lỏng hơn"
                log(f"🏦 [FTMO] Mốc balance đầu ngày dựng lại từ lịch sử deal: "
                    f"${old:,.2f} -> ${new:,.2f} ({direction}; sàn equity "
                    f"${new - daily_loss_amount(st):,.2f})")


def record_trading_day() -> None:
    """Đánh dấu hôm nay là một Trading Day (đã mở ít nhất 1 lệnh mới)."""
    today = trading_day().isoformat()
    with _lock:
        st = _read_state()
        if today not in st["trading_days"]:
            st["trading_days"].append(today)
            _write_state(st)
    # Chu kỳ rút tiền 14 ngày của FTMO bắt đầu từ NGÀY GIAO DỊCH ĐẦU TIÊN — đây
    # là điểm duy nhất trong hệ thống biết ngày đó. `mark_first_trading_day()`
    # idempotent nên gọi mỗi ngày cũng không dời mốc. Fail-soft tuyệt đối: đây
    # là module PHỤ, không được phép làm gãy việc ghi Trading Day.
    try:
        from src.python.core.infra import ftmo_reward
        ftmo_reward.mark_first_trading_day(today)
    except Exception as e:
        log_error(f"⚠️ [FTMO] không đánh dấu được mốc chu kỳ rút tiền (bỏ qua): {e}")


def days_since_last_trade(st: Optional[Dict[str, Any]] = None,
                         today: Optional[date] = None) -> int:
    """Số ngày kể từ Trading Day gần nhất. `-1` nếu chưa có ngày nào.

    Phân biệt "chưa từng giao dịch" với "đã lâu không giao dịch" bằng `-1` thay
    vì một số lớn: hai tình huống này cần xử lý khác nhau, và trả về một con số
    lớn cho tài khoản mới sẽ kích hoạt cảnh báo bất hoạt động ngay ngày đầu.
    """
    st = st if st is not None else _read_state()
    days = st.get("trading_days") or []
    if not days:
        return -1
    today = today or trading_day()
    try:
        latest = max(date.fromisoformat(d) for d in days)
    except (TypeError, ValueError):
        return -1
    return max(0, (today - latest).days)


def inactivity_warning(st: Optional[Dict[str, Any]] = None,
                           today: Optional[date] = None) -> str:
    """Cảnh báo khi tài khoản im lặng quá lâu. Rỗng nghĩa là không sao.

    KHÔNG CHẶN VÀ KHÔNG ÉP VÀO LỆNH — chỉ báo. Vì FTMO bỏ thời hạn tối đa nên
    "không giao dịch trong trạng thái bất lợi" là nước đi hợp lệ và là trụ cột
    của thiết kế theo trạng thái thị trường; điều duy nhất cần canh là điều khoản
    prolonged inactivity. Biến một cảnh báo hành chính thành lệnh ép giao dịch sẽ
    phá đúng thứ mà cả hệ thống được dựng lên để bảo vệ.
    """
    n = days_since_last_trade(st, today)
    if n < INACTIVITY_WARNING_DAYS:
        return ""
    return (f"Đã {n} ngày không có Trading Day nào (ngưỡng cảnh báo "
            f"{INACTIVITY_WARNING_DAYS}). FTMO có điều khoản prolonged "
            f"inactivity — cân nhắc xin freeze tài khoản. KHÔNG vào lệnh chỉ để "
            f"giữ tài khoản sống.")


def sync_phase_from_env() -> Optional[str]:
    """Đồng bộ pha tài khoản từ `.env` (`FTMO_PHASE`). Gọi lúc engine khởi động.

    VÌ SAO CẦN — HAI CHẾ ĐỘ VẬN HÀNH KHÔNG CHUYỂN ĐƯỢC CHO NHAU NẾU KHÔNG CÓ CƠ CHẾ NÀY
    -------------------------------------------------------------------
    Trong môi trường live, nếu chỉ gán cứng pha ban đầu, hệ thống sẽ kẹt ở CHALLENGE.
    Hậu quả:
      1. Rủi ro tăng gấp đôi so với thực tế (pha Challenge thường rủi ro cao hơn).
      2. Bot tự khoá vĩnh viễn khi đạt +10% lợi nhuận thay vì giao dịch tiếp
         dưới quyền Funded account.

    THIẾT KẾ: `.env` LÀ NGUỒN, KHÔNG TỰ ĐỘNG SUY
    ---------------------------------------------
    Cố ý KHÔNG tự dò pha từ số dư hay từ việc đã đạt mục tiêu. Chỉ FTMO mới
    quyết định một pha đã qua hay chưa, và tín hiệu đó đến qua email cho con
    người — không có API nào để bot đọc. Tự suy sẽ tạo ra một business rule
    không có căn cứ, đúng thứ bị cấm.

    Người vận hành đặt `FTMO_PHASE=FUNDED` trong `.env` khi nhận được duyệt.
    Nhất quán với `FTMO_RISK_MODE` (cùng khuôn: `.env` khai báo sự thật bên
    ngoài mà hệ thống không tự biết được).

    Giá trị sai làm hệ thống DỪNG NGAY lúc khởi động — pha quyết định cả hệ số
    rủi ro lẫn việc có được giao dịch hay không.
    """
    import os
    raw = (os.environ.get("FTMO_PHASE") or "").strip().upper()
    if not raw:
        return None
    if raw not in PHASE_TARGETS:
        raise ValueError(
            f"FTMO_PHASE={raw!r} không hợp lệ. Chọn một trong "
            f"{tuple(PHASE_TARGETS)}. Pha quyết định hệ số rủi ro và điều kiện "
            f"dừng — không đoán.")
    current = _read_state().get("phase")
    if current != raw:
        log(f"🏦 [FTMO] `.env` khai báo pha {raw} (state đang {current}) — "
            f"đồng bộ. Hệ số đệm sẽ đổi theo: "
            f"{RISK_BUFFER_K_FUNDED if raw == PHASE_FUNDED else RISK_BUFFER_K_CHALLENGE}")
        set_phase(raw)
    return raw


def set_phase(phase: str) -> None:
    """Đặt pha tài khoản (CHALLENGE / VERIFICATION / FUNDED).

    Live: gọi qua `sync_phase_from_env()` lúc khởi động (người vận hành khai báo
    trong `.env` sau khi FTMO duyệt). Backtest: quyết định xem điều kiện "đã đạt
    mục tiêu -> dừng" có áp dụng hay không — mô phỏng nhiều năm phải chạy ở
    FUNDED, nếu không toàn bộ giai đoạn sau lần chạm +10% đầu tiên sẽ là một
    đường thẳng và ta không đo được gì về chiến lược.
    """
    if phase not in PHASE_TARGETS:
        raise ValueError(f"pha không hợp lệ: {phase}")
    with _lock:
        st = _read_state()
        if st.get("phase") != phase:
            st["phase"] = phase
            _write_state(st)
            log(f"🏦 [FTMO] Chuyển pha -> {phase}")


def record_daily_realized(profit: float, day: Optional[str] = None) -> None:
    """Ghi lãi/lỗ ĐÃ CHỐT của một ngày giao dịch (GHI ĐÈ, không cộng dồn).

    Caller truyền TỔNG lãi đã chốt của ngày chứ không phải từng lệnh — nhờ vậy
    gọi lại nhiều lần trong ngày là idempotent, và bỏ lỡ một chu kỳ không làm
    mất số liệu.
    """
    key = day or trading_day().isoformat()
    with _lock:
        st = _read_state()
        book = dict(st.get("daily_realized") or {})
        if book.get(key) != float(profit):
            book[key] = float(profit)
            st["daily_realized"] = book
            _write_state(st)


def best_day_share(st: Optional[Dict[str, Any]] = None) -> float:
    """Tỷ lệ ngày lãi lớn nhất trên TỔNG lãi của mọi ngày dương.

    Trả `0.0` khi chưa có ngày dương nào — chưa có gì để vi phạm. KHÔNG trả 1.0
    ở trường hợp đó, vì như vậy một tài khoản mới sẽ bị coi là đang vi phạm ngay
    trước lệnh đầu tiên.
    """
    st = st if st is not None else _read_state()
    gains = [float(v) for v in (st.get("daily_realized") or {}).values() if float(v) > 0]
    total = sum(gains)
    return (max(gains) / total) if total > 0 else 0.0


def best_day_ok(st: Optional[Dict[str, Any]] = None) -> bool:
    """Kiểm tra điều kiện Best Day Rule đã được thoả mãn chưa."""
    return best_day_share(st) <= BEST_DAY_MAX_SHARE


# ============================================================ đo lường drawdown
@dataclass(frozen=True)
class ComplianceState:
    """Ảnh chụp tuân thủ FTMO tại một thời điểm."""
    equity: float
    daily_dd: float          # tỷ lệ (0.02 = -2% so với đầu ngày)
    total_dd: float           # so với balance BAN ĐẦU (tĩnh)
    monthly_profit: float
    phase: str
    mode: str
    risk_multiplier: float
    survival: float
    block_reason: str = ""
    trading_days: int = 0
    weekly_dd: float = 0.0
    monthly_dd: float = 0.0
    best_day: float = 0.0
    open_risk: float = 0.0        # tổng rủi ro vị thế đang mở, tỷ lệ equity
    projected_monthly: float = 0.0  # monthly_dd + open_risk (Elder ch.51 tr.208)
    projected_daily: float = 0.0  # daily_dd + open_risk — con số phải canh
    flatten_reason: str = ""      # khác rỗng = ĐÓNG SẠCH vị thế NGAY
    # Bậc trên thang trạng thái CÓ TÊN của tài liệu §I.2 (HEALTHY ... HARD_STOP).
    # Con số `risk_multiplier` ở trên nói "giảm bao nhiêu"; hai trường này nói
    # "đang ở đâu và vì sao" — thứ người vận hành đọc để biết còn cách cầu dao
    # bao xa. Xem `core/infra/ftmo_risk_state.py`.
    risk_state: str = ""
    risk_state_reason: str = ""

    @property
    def must_flatten(self) -> bool:
        """Cần đóng toàn bộ lệnh ngay lập tức hay không."""
        return bool(self.flatten_reason)

    @property
    def entries_allowed(self) -> bool:
        """Cho phép mở thêm lệnh mới hay không."""
        return not self.block_reason


def initial_balance(st: Optional[Dict[str, Any]] = None) -> float:
    """Vốn ban đầu THẬT của tài khoản — mẫu số của mọi ngưỡng FTMO.

    Neo cứng vào `ACCOUNT_SIZE` là sai ở hai chỗ, và cả hai đều gặp thật:
      * người dùng đổi sang tài khoản $50.000 hay $200.000 sau Scaling Plan;
      * backtest chạy trên số vốn khác để so sánh.
    Trong cả hai, mọi ngưỡng sẽ tính trên $100.000 trong khi tài khoản là số
    khác — với tài khoản nhỏ hơn thì `_total_dd` cho ra một con số vô nghĩa
    (một tài khoản $10.000 lành lặn bị coi là đang lỗ 90%) và hệ thống chặn
    sạch mọi lệnh mà không nói được vì sao.

    Giá trị được chốt MỘT LẦN vào state ở lần đầu quan sát được số dư, rồi giữ
    nguyên — đúng ngữ nghĩa "Initial Simulated Capital" của FTMO, vốn không đổi
    suốt vòng đời tài khoản.
    """
    st = st if st is not None else _read_state()
    v = float(st.get("initial_balance") or 0.0)
    return v if v > 0 else ACCOUNT_SIZE


def daily_zone(daily_dd: float) -> str:
    """Tên vùng lỗ ngày, cho log/email/GUI. KHÔNG dùng để quyết định.

    Bốn ngưỡng nội bộ (`DAILY_NORMAL` .. `DAILY_EMERGENCY`) mô tả một thang liên
    tục, nhưng chuỗi `if/elif` trong `_block_reason()` chỉ chạm tới ba cái trên —
    `DAILY_NORMAL` đánh dấu vùng KHÔNG cần hành động nên không có nhánh nào.

    Hàm này cho nó một chỗ dùng thật: người vận hành đọc "vùng BÌNH THƯỜNG" dễ
    hơn đọc "lỗ ngày 0,80%", và khi vùng đổi tên thì họ biết đã bước qua một
    ranh giới có ý nghĩa.

    QUYẾT ĐỊNH vẫn thuộc `_block_reason()` và `ftmo_risk_state.classify()` —
    hàm này chỉ đặt tên, không được dùng để chặn (nếu không sẽ có hai nguồn sự
    thật cho cùng một quyết định).
    """
    import math as _m

    if daily_dd is None or not _m.isfinite(float(daily_dd)):
        return "KHÔNG ĐO ĐƯỢC"
    d = float(daily_dd)
    if d >= DAILY_EMERGENCY:
        return "KHẨN CẤP"
    if d >= DAILY_DANGER:
        return "NGUY HIỂM"
    if d >= DAILY_WARNING:
        return "CẢNH BÁO"
    if d >= DAILY_NORMAL:
        return "SỤT NHẸ"
    return "BÌNH THƯỜNG"


def daily_loss_amount(st: Optional[Dict[str, Any]] = None) -> float:
    """Hạn mức lỗ ngày tuyệt đối = 5% VỐN BAN ĐẦU (không phải vốn hiện tại)."""
    return DAILY_LOSS_HARD * initial_balance(st)


def max_loss_floor(st: Optional[Dict[str, Any]] = None) -> float:
    """Sàn equity tuyệt đối = vốn ban đầu × 90%. Tĩnh với Challenge 2-Step."""
    return initial_balance(st) * (1.0 - MAX_LOSS_HARD)


def daily_loss_limit(st: Dict[str, Any]) -> float:
    """Mức equity SÀN của hôm nay theo đúng công thức FTMO.

        balance lúc 00:00 CE(S)T hôm trước − 5% × vốn ban đầu

    Chạm hoặc xuống dưới mức này là VI PHẠM. Trả `0.0` khi chưa có mốc — caller
    phải coi đó là "không đo được" và fail-closed, KHÔNG phải "không sao".
    """
    base = float(st.get("day_start_balance") or 0.0)
    if base <= 0:
        return 0.0
    return base - daily_loss_amount(st)


def _daily_dd(equity: float, st: Dict[str, Any]) -> float:
    """Phần hạn mức lỗ ngày ĐÃ TIÊU, theo tỷ lệ của chính hạn mức đó.

    Trả 1.0 nghĩa là đã dùng trọn $5.000 — tức chạm giới hạn cứng. Mọi ngưỡng
    nội bộ (`DAILY_WARNING` 2%, `DAILY_DANGER` 3%...) được diễn giải trên cùng
    thang "% vốn ban đầu" nên vẫn so sánh trực tiếp được: hàm này trả về phần
    trăm VỐN BAN ĐẦU đã mất trong ngày.
    """
    base = float(st.get("day_start_balance") or 0.0)
    if base <= 0:
        # KHÔNG trả 0.0 ("hôm nay chưa lỗ gì") — `daily_loss_limit()` ngay trên
        # đã nói rõ thiếu mốc phải coi là "không đo được", và fail-closed. Trả
        # NaN để `evaluate()` phân biệt được với 0 thật.
        return float("nan")
    return max(0.0, (base - equity) / initial_balance(st))


def _total_dd(equity: float, st: Dict[str, Any]) -> float:
    """So với vốn BAN ĐẦU — mốc TĨNH cho Challenge 2-Step. Xem điểm dễ sai #3."""
    base = initial_balance(st)
    return max(0.0, (base - equity) / base) if base > 0 else 0.0


def monthly_mode(monthly_profit: float) -> tuple:
    """(tên chế độ, hệ số risk) theo lãi tháng — Payout Protection Mode."""
    for threshold, name, multiplier in MONTHLY_PROFIT_TIERS:
        if monthly_profit >= threshold:
            return name, multiplier
    return "NORMAL", 1.0


def survival_score(daily_dd: float, total_dd: float) -> float:
    """Điểm sống sót 0-100. Càng gần giới hạn FTMO càng thấp.

    Chỉ dùng hai trục ĐO ĐƯỢC TRỰC TIẾP và có ý nghĩa nhân quả với việc mất tài
    khoản. Tài liệu liệt kê thêm Win Stability / Volatility / Regime Adaptation —
    CỐ Ý chưa đưa vào: chúng cần chuỗi lịch sử dài mới ước lượng ổn định, và gộp
    một ước lượng nhiễu vào một chỉ số điều khiển rủi ro sẽ làm risk nhảy loạn vì
    lý do không liên quan tới nguy cơ thật. Thêm khi có đủ dữ liệu live sạch.
    """
    d = min(1.0, daily_dd / DAILY_LOSS_HARD) if DAILY_LOSS_HARD else 0.0
    t = min(1.0, total_dd / MAX_LOSS_HARD) if MAX_LOSS_HARD else 0.0
    return round(100.0 * (1.0 - max(d, t)), 1)


def _block_reason(*, st: Dict[str, Any], risk_state, daily: float, total: float,
                  monthly_dd: float, projected: float, projected_monthly: float,
                  open_risk: float, score: float) -> str:
    """Lý do chặn mở lệnh mới. Rỗng = được phép. Tách khỏi `evaluate()` 07/08.

    THỨ TỰ Ở ĐÂY LÀ MỘT QUYẾT ĐỊNH, KHÔNG PHẢI NGẪU NHIÊN
    ======================================================
    Chuỗi `elif` nghĩa là nhánh ĐỨNG TRƯỚC nuốt nhánh đứng sau. Nên quy tắc là:

        ngưỡng CAO hơn / hậu quả NẶNG hơn  ->  đứng TRƯỚC

    Vi phạm quy tắc này biến nhánh sau thành mã chết. Đã xảy ra hai lần:

      * `DAILY_EMERGENCY` (4%) đứng sau `DAILY_DANGER` (3%) — ghi chú 31/07 ngay
        tại nhánh đó đã thừa nhận "gần như không bao giờ chạy".
      * Bản đầu của chốt nội bộ hôm nay (07/08) đặt `INTERNAL_MONTHLY_STOP` (4%)
        TRƯỚC `MONTHLY_REVIEW` (5%). Ba test đỏ ngay: một tháng lỗ 6% báo lý do
        của chốt 4% và MẤT hẳn câu "đòi Full System Review" — tức hậu quả nặng
        hơn bị một nhánh nhẹ hơn che mất.

    Tách thành hàm riêng để thứ tự ấy ĐỌC ĐƯỢC thành một danh sách, thay vì nằm
    lẫn giữa các phép tính trong một hàm 230 dòng.
    """
    # 1. Thang trạng thái có tên đã nói KHÔNG (DEFENSIVE/HARD_STOP).
    if not risk_state.allow_new_entries:
        return f"{risk_state.reason} — {risk_state.meaning}"

    # 2. Trục NGÀY, từ nặng xuống nhẹ.
    if daily >= DAILY_EMERGENCY:
        return (f"EMERGENCY: daily drawdown {daily:.2%} >= {DAILY_EMERGENCY:.0%} — "
                f"ngừng mở vị thế mới, chỉ quản lý lệnh đang mở "
                f"(giới hạn FTMO {DAILY_LOSS_HARD:.0%})")
    if daily >= DAILY_DANGER:
        return (f"lỗ ngày {daily:.2%} >= {DAILY_DANGER:.0%} (vùng nguy hiểm) — ngừng mở "
                f"vị thế mới hết ngày. Hạn mức FTMO ${daily_loss_amount(st):,.0f}, "
                f"còn lại ${max(0.0, (DAILY_LOSS_HARD - daily) * initial_balance(st)):,.0f}")

    # 3. Trục TỔNG.
    if total >= TOTAL_WARNING:
        return (f"tổng drawdown {total:.2%} >= soft limit {TOTAL_WARNING:.0%} — "
                f"cần Champion Review trước khi giao dịch tiếp "
                f"(giới hạn FTMO {MAX_LOSS_HARD:.0%})")
    if score < 40:
        return f"FTMO Survival Score {score} < 40 — dừng giao dịch, chờ review"

    # 4. Trục THÁNG, từ nặng xuống nhẹ.
    if monthly_dd >= MONTHLY_REVIEW:
        return (f"sụt giảm THÁNG {monthly_dd:.2%} >= {MONTHLY_REVIEW:.0%} — dừng giao dịch, "
                f"đòi Full System Review (retrain, review champion/feature/regime/risk "
                f"engine) trước khi chạy tiếp")
    if projected_monthly >= MONTHLY_PROJECTED_BLOCK:
        # Chưa lỗ đủ 5% trong tháng, nhưng cộng rủi ro đang mở thì đã tới ngưỡng.
        # Ngừng nhận rủi ro MỚI; vị thế cũ vẫn được quản lý bình thường.
        return (f"lỗ THÁNG dự báo {projected_monthly:.2%} >= "
                f"{MONTHLY_PROJECTED_BLOCK:.0%} — không mở thêm vị thế "
                f"(đã lỗ {monthly_dd:.2%} + rủi ro đang mở {open_risk:.2%}). "
                f"Nguồn: Elder ch.51 tr.208")
    if monthly_dd >= INTERNAL_MONTHLY_STOP:
        # CHỐT NỘI BỘ THÁNG (tài liệu §III.2) — nhẹ hơn hai nhánh trên nên đứng
        # sau. Nó bắt vùng 4%-5% mà trước 07/08 hoàn toàn không có gì chặn.
        return (f"lỗ THÁNG {monthly_dd:.2%} >= chốt NỘI BỘ "
                f"{INTERNAL_MONTHLY_STOP:.1%} — ngừng mở lệnh mới hết tháng, "
                f"cần review cấu hình danh mục (giới hạn FTMO {MAX_LOSS_HARD:.0%})")

    # 5. Dự báo ngày, rồi chốt nội bộ ngày (nhẹ nhất, đứng cuối).
    if projected >= DAILY_EMERGENCY:
        return (f"lỗ ngày dự báo {projected:.2%} >= {DAILY_EMERGENCY:.0%} — không mở thêm "
                f"vị thế (đã lỗ {daily:.2%} + rủi ro đang mở {open_risk:.2%})")
    if daily >= INTERNAL_DAILY_STOP:
        # CHỐT NỘI BỘ NGÀY (tài liệu §III.2). Bắt vùng 1,5%-3% mà trước 07/08
        # không có gì chặn — xem khối `INTERNAL_DAILY_STOP` ở đầu file.
        return (f"lỗ ngày {daily:.2%} >= chốt NỘI BỘ {INTERNAL_DAILY_STOP:.1%} "
                f"— ngừng mở lệnh mới hết hôm nay. Đây KHÔNG phải giới hạn FTMO "
                f"({DAILY_LOSS_HARD:.0%}) mà là chốt tự đặt để không bao giờ tới "
                f"gần giới hạn đó. Bộ đếm reset vào ngày giao dịch mới.")
    return ""


def evaluate(equity: float, open_risk_usd: float = 0.0,
             balance: Optional[float] = None) -> ComplianceState:
    """Ảnh chụp tuân thủ + quyết định cho phép vào lệnh hay không.

    KHÔNG raise. `equity <= 0` (mất kết nối) -> FAIL-CLOSED: chặn entry, vì
    không đo được drawdown thì không biết đang cách giới hạn bao xa.

    `balance` = số dư (chỉ lệnh đã đóng). QUAN TRỌNG: mốc lỗ
    ngày của FTMO tính trên BALANCE lúc nửa đêm, không phải equity. Bỏ trống thì
    `update_baselines()` phải dùng equity làm mốc — nếu đang có lệnh lỗ, sàn
    sẽ bị sai lệch.

    `open_risk_usd` = tổng khoảng cách tới SL của mọi vị thế đang mở, quy ra USD.
    Bỏ trống (0.0) thì mọi phép tính DỰ BÁO trở thành phép tính lỗ ĐÃ thực hiện —
    an toàn về mặt kiểu dữ liệu nhưng MẤT chính lớp bảo vệ quan trọng nhất, nên
    mọi caller ở đường vào lệnh phải truyền giá trị thật.
    """
    if not equity or equity <= 0:
        return ComplianceState(0.0, 0.0, 0.0, 0.0, PHASE_CHALLENGE, "UNKNOWN",
                               0.0, 0.0, "không đọc được equity — fail-closed")

    st = update_baselines(equity, balance=balance)
    daily = _daily_dd(equity, st)
    total = _total_dd(equity, st)
    # MẪU SỐ PHẢI GIỐNG `daily`. `open_risk` phải chia cho VỐN BAN ĐẦU
    # (giống cách `_daily_dd` chia) để cùng hệ quy chiếu, thay vì chia
    # cho equity khiến phép tính sai số khi tài khoản đang lãi.
    open_risk = max(0.0, float(open_risk_usd or 0.0)) / initial_balance(st)
    projected = daily + open_risk

    month_start = float(st.get("month_start_equity") or 0.0)
    monthly_profit = ((equity - month_start) / month_start) if month_start > 0 else 0.0

    # Sụt giảm theo TUẦN và THÁNG so với mốc đầu kỳ. Hai con số này không phải
    # luật FTMO — chúng là tín hiệu CẤU HÌNH SAI. Một ngày lỗ là xui; một tuần
    # lỗ 3% hay một tháng lỗ 5% với risk 0,5%/lệnh nghĩa là giả định nào đó của
    # danh mục đã hỏng, và giao dịch tiếp với cùng cấu hình chỉ nhân rộng lỗi.
    week_start = float(st.get("week_start_equity") or 0.0)
    weekly_dd = max(0.0, (week_start - equity) / week_start) if week_start > 0 else 0.0
    monthly_dd = max(0.0, -monthly_profit)
    # Lỗ tháng DỰ BÁO = đã thực hiện + rủi ro của các vị thế đang mở (Elder
    # ch.51 tr.208). Cùng khái niệm với `projected` ở tầng ngày.
    projected_monthly = monthly_dd + open_risk

    mode, tier_multiplier = monthly_mode(monthly_profit)
    score = survival_score(daily, total)

    # ---- hệ số rủi ro thích ứng ------------------------------------------
    # Giảm theo trạng thái drawdown, KHÔNG BAO GIỜ tăng để gỡ lỗ.
    multiplier = tier_multiplier
    if daily >= DAILY_DANGER or total >= TOTAL_WARNING:
        multiplier = min(multiplier, 0.25)
    elif daily >= DAILY_WARNING or total >= TOTAL_PREFERRED:
        multiplier = min(multiplier, 0.50)
    if score < 60:
        multiplier = min(multiplier, 0.25)
    # Defensive Mode theo TUẦN (tài liệu §Weekly Risk Budget). Tách khỏi chuỗi
    # if/elif ở trên có chủ đích: sụt giảm tuần là một TRỤC KHÁC với sụt giảm
    # ngày. Một tuần lỗ dần đều 0,6%/ngày không kích hoạt ngưỡng ngày nào cả,
    # nhưng vẫn là dấu hiệu cấu hình đang sai — và đó chính là kiểu chết chậm mà
    # ngưỡng ngày không bao giờ thấy.
    if weekly_dd >= WEEKLY_DEFENSIVE:
        multiplier = min(multiplier, 0.50)

    # Không đo được lỗ ngày (thiếu mốc) hoặc không ghi được state -> FAIL-CLOSED.
    # Đây là hai tình huống "không biết đang cách giới hạn bao xa", và với ràng
    # buộc mất-tài-khoản thì không biết phải xử như nguy hiểm.
    import math as _math
    if _state_degraded or _state_read_failed or not _math.isfinite(daily):
        reason = ("không ghi được state — thước đo drawdown không đáng tin"
                 if _state_degraded else
                 "KHÔNG ĐỌC ĐƯỢC state — mốc đầu ngày và vốn ban đầu đều không "
                 "đáng tin, mọi thước đo tuân thủ vô nghĩa"
                 if _state_read_failed else
                 "chưa chụp được mốc balance đầu ngày — không đo được lỗ ngày")
        return ComplianceState(
            equity=equity, daily_dd=0.0, total_dd=total, monthly_profit=monthly_profit,
            phase=st.get("phase", PHASE_CHALLENGE), mode="UNKNOWN",
            risk_multiplier=0.0, survival=0.0,
            block_reason=f"{reason} — fail-closed",
            trading_days=len(st.get("trading_days", [])))

    # ---- MÁY TRẠNG THÁI RỦI RO ----
    # `ftmo_risk_state.classify()` là hàm THUẦN cài đặt đúng thang trạng thái có
    # tên của tài liệu §I.2. Nối vào đây thay vì thay thế chuỗi if/elif bên dưới:
    # hai lớp kiểm tra ĐỘC LẬP cùng canh một thứ, và ta lấy cái NGHIÊM HƠN.
    #
    # Vì sao không gỡ chuỗi cũ đi: nó mang những nhánh mà thang trạng thái không
    # có (Best Day Rule, sụt tuần, survival score, ngân sách tháng dự báo). Gỡ
    # để "cho gọn" sẽ mất chúng — đúng loại refactor mà `refactor.md` cấm.
    risk_state = _risk_state.classify(
        daily_dd=daily, total_dd=total, period_profit=monthly_profit,
        projected_daily_dd=projected, projected_total_dd=total + open_risk)
    multiplier = min(multiplier, risk_state.risk_multiplier)

    # ---- đóng sạch vị thế (lớp mạnh nhất) ---------------------------------
    flatten = ""
    if daily >= DAILY_FLATTEN_REALIZED:
        flatten = (f"lỗ ngày THỰC {daily:.2%} >= {DAILY_FLATTEN_REALIZED:.1%} — đóng sạch "
                   f"vị thế để chốt tổn thất ngày dưới giới hạn cứng {DAILY_LOSS_HARD:.0%}")
    elif total + open_risk >= TOTAL_FLATTEN_PROJECTED:
        # LỚP ĐÓNG LỆNH CHO MAX LOSS.
        # Kịch bản trôi tới đáy mà không có bảo vệ có thể đẩy hệ thống
        # qua Max Loss nếu lỗ rải rác mỗi ngày một ít mà không vi phạm 5%/ngày.
        flatten = (f"tổng drawdown DỰ BÁO {total + open_risk:.2%} (đã mất {total:.2%} + "
                   f"rủi ro đang mở {open_risk:.2%}) >= {TOTAL_FLATTEN_PROJECTED:.0%} — "
                   f"đóng sạch, sàn tuyệt đối FTMO là {MAX_LOSS_HARD:.0%}")
    elif projected >= DAILY_FLATTEN_PROJECTED:
        flatten = (f"lỗ ngày DỰ BÁO {projected:.2%} (đã lỗ {daily:.2%} + rủi ro đang mở "
                   f"{open_risk:.2%}) >= {DAILY_FLATTEN_PROJECTED:.1%} — nếu mọi vị thế cùng "
                   f"chạm SL thì vượt giới hạn cứng {DAILY_LOSS_HARD:.0%}. Đóng sạch NGAY.")

    # ---- cổng chặn --------------------------------------------------------
    block = flatten or _block_reason(
        st=st, risk_state=risk_state, daily=daily, total=total,
        monthly_dd=monthly_dd, projected=projected,
        projected_monthly=projected_monthly, open_risk=open_risk, score=score)

    # Đã đạt mục tiêu pha + đủ số ngày -> DỪNG. Giao dịch thêm chỉ có thể làm
    # tuột khỏi mục tiêu đã đạt; không có phần thưởng nào delay việc vượt xa hơn.
    target = PHASE_TARGETS.get(st.get("phase", PHASE_CHALLENGE))
    bd_share = best_day_share(st)
    if not block and target is not None:
        base = initial_balance(st)
        phase_profit = (equity - base) / base if base > 0 else 0.0
        if phase_profit >= target and len(st.get("trading_days", [])) >= MIN_TRADING_DAYS:
            if bd_share <= BEST_DAY_MAX_SHARE:
                # NÓI RÕ CÁCH THOÁT. Trạng thái này là ĐÍCH ĐẾN mong
                # muốn của pha thi, nhưng nó chỉ kết thúc khi có người đặt
                # `FTMO_PHASE` mới trong `.env`.
                _next_phase = (PHASE_VERIFICATION if st["phase"] == PHASE_CHALLENGE
                           else PHASE_FUNDED)
                block = (f"ĐÃ ĐẠT mục tiêu {st['phase']} (+{phase_profit:.2%} >= "
                         f"+{target:.0%}) với {len(st['trading_days'])} trading days, "
                         f"Best Day {bd_share:.0%} <= {BEST_DAY_MAX_SHARE:.0%} — "
                         f"DỪNG giao dịch, chờ FTMO xét duyệt. "
                         f"KHI ĐƯỢC DUYỆT: đặt FTMO_PHASE={_next_phase} trong .env "
                         f"rồi khởi động lại — nếu không, bot sẽ KHÔNG BAO GIỜ "
                         f"giao dịch lại.")
            else:
                # KHÔNG chặn. Đã chạm mục tiêu lợi nhuận nhưng Best Day Rule chưa
                # đạt, và cách DUY NHẤT để gỡ là tích thêm ngày dương. Dừng ở đây
                # là tự khoá mình vĩnh viễn: hệ thống đứng chờ một điều kiện mà
                # chính việc đứng chờ khiến nó không bao giờ đạt được.
                #
                # Nhưng cũng không giao dịch như bình thường: mục tiêu lúc này
                # không còn là kiếm thêm lợi nhuận (đã đủ) mà là làm MẪU SỐ lớn
                # lên bằng nhiều ngày dương NHỎ. Một ngày thắng lớn nữa còn làm
                # tỷ lệ TỆ ĐI nếu nó thành Best Day mới. Hạ risk mạnh vì thế đúng
                # cả về mục tiêu lẫn về rủi ro.
                multiplier = min(multiplier, 0.25)

    return ComplianceState(
        equity=equity, daily_dd=daily, total_dd=total, monthly_profit=monthly_profit,
        phase=st.get("phase", PHASE_CHALLENGE), mode=mode,
        risk_multiplier=multiplier, survival=score, block_reason=block,
        trading_days=len(st.get("trading_days", [])),
        weekly_dd=weekly_dd, monthly_dd=monthly_dd, best_day=bd_share,
        projected_monthly=projected_monthly,
        open_risk=open_risk, projected_daily=projected, flatten_reason=flatten,
        risk_state=risk_state.state.name, risk_state_reason=risk_state.reason)


# ============================================================ giao diện sizing
def buffer_risk_usd(equity: float, st: Optional[Dict[str, Any]] = None) -> float:
    """Ngân sách rủi ro mỗi lệnh tính bằng USD, theo ĐỆM TỚI SÀN.

    Xem khối `RISK_BUFFER_K_*` ở đầu file cho lý do đầy đủ. Tóm tắt: dư địa rủi
    ro của tài khoản FTMO là khoảng cách tới sàn TĨNH, không phải một tỷ lệ của
    equity — nên risk phải tỷ lệ với khoảng cách đó.

    Lấy cái CHẶT HƠN giữa hai đệm. Trả 0.0 khi đã chạm sàn: đó chính là tính
    chất khiến sơ đồ này không thể vi phạm giới hạn tổng.
    """
    st = st if st is not None else _read_state()
    initial_capital = initial_balance(st)
    total_buffer = max(0.0, equity - initial_capital * (1.0 - MAX_LOSS_HARD))

    day_baseline = float(st.get("day_start_balance") or 0.0)
    if day_baseline > 0:
        daily_buffer = max(0.0, equity - (day_baseline - daily_loss_amount(st)))
    else:
        # Chưa có mốc ngày -> KHÔNG suy ra được đệm ngày. Fail-closed: dùng
        # nguyên hạn mức ngày làm cận trên thay vì bỏ qua ràng buộc này.
        daily_buffer = daily_loss_amount(st)

    # `buffer_k` gộp cả hai đường chọn mode (env ép / suy từ pha) — xem khối
    # "HAI MODE CẤU HÌNH QUA .env" ở đầu file.
    return buffer_k(st) * min(total_buffer, daily_buffer)


def risk_fraction(equity: float) -> float:
    """Rủi ro mỗi lệnh (tỷ lệ equity) — `target_mode` gọi sang đây.

    Ngân sách gốc tính theo ĐỆM (xem `buffer_risk_usd`), rồi quy về tỷ lệ để
    giữ nguyên giao diện mà 13 điểm vào lệnh đang dùng. Nhân hệ số thích ứng
    (drawdown/Payout Protection) rồi kẹp TRẦN `RISK_ABSOLUTE_MAX`.

    KHÔNG CÓ SÀN, và đó là điểm cốt lõi của sơ đồ theo đệm: khi đệm cạn thì ngân
    sách phải cạn theo, tiến về 0 cùng lúc với khoảng cách tới sàn tài khoản.
    Ép một mức risk tối thiểu sẽ phá đúng cái tính chất khiến sơ đồ này không thể
    vi phạm giới hạn tổng. Docstring cũ khai có kẹp `[RISK_MIN, ...]` — sai, và
    hằng số đó nay đã xoá.

    Chặn hoàn toàn -> 0.0.
    """
    # Chặn đầu vào không hữu hạn TRƯỚC mọi phép tính: `inf` cho ra
    # `inf/inf = NaN`, và NaN lọt qua mọi phép so sánh (kể cả `<= trần`) nên nó
    # sẽ đi thẳng xuống sizing rồi đầu độc lot. Fail-closed.
    import math as _m
    if not isinstance(equity, (int, float)) or not _m.isfinite(equity) or equity <= 0:
        return 0.0
    tt = evaluate(equity)
    if not tt.entries_allowed:
        return 0.0
    f = (buffer_risk_usd(equity) / equity) * tt.risk_multiplier
    if not _m.isfinite(f) or f <= 0.0:
        return 0.0
    # Sàn `RISK_MIN` CỐ Ý không áp khi đệm đã cạn: lúc đó `buffer_risk_usd` trả
    # về gần 0 và đó là hành vi ĐÚNG — ép lên sàn sẽ phá chính đảm bảo cấu trúc.
    if f <= 0.0:
        return 0.0
    return min(f, RISK_ABSOLUTE_MAX)


def is_symbol_allowed(symbol: str) -> bool:
    """Cặp tiền có nằm trong danh mục được phép không.

    Bỏ hậu tố broker trước khi so: nhiều broker thêm suffix ("EURUSD.m",
    "EURUSDx", "EURUSD_i"), và so khớp thô sẽ từ chối đúng những symbol hợp lệ.
    """
    s = str(symbol or "").upper()
    for allowed in SYMBOLS_ALLOWED:
        if s.startswith(allowed):
            return True
    return False


def is_timeframe_allowed(tf: str) -> bool:
    """Kiểm tra khung thời gian có hợp lệ không."""
    return str(tf or "").upper() in TIMEFRAMES_ALLOWED


def timeframe_rejection_reason(tf: str) -> str:
    """Vì sao khung này không được phép. `""` khi được phép.

    `TIMEFRAMES_BANNED` từng là hằng số CHẾT (đo 08/08: 0 nơi đọc). Nó mang một
    thông tin mà `TIMEFRAMES_ALLOWED` không có: phân biệt "khung bị CẤM có chủ
    đích" với "khung lạ, có thể do gõ nhầm".

    Hai tình huống đó đòi hai phản ứng khác nhau từ người vận hành: cấm thì
    phải đổi thiết kế chiến lược, gõ nhầm thì chỉ cần sửa một chuỗi.
    """
    key = str(tf or "").upper()
    if key in TIMEFRAMES_ALLOWED:
        return ""
    if key in TIMEFRAMES_BANNED:
        return (f"khung {key} bị CẤM có chủ đích: nhiễu cao, phụ thuộc spread/"
                f"latency, và tần suất lệnh lớn dễ chạm ngưỡng hành động/ngày mà "
                f"FTMO theo dõi. Khung cho phép: {sorted(TIMEFRAMES_ALLOWED)}")
    return (f"khung {key!r} không nằm trong danh sách nào — kiểm lại chính tả. "
            f"Cho phép: {sorted(TIMEFRAMES_ALLOWED)}; cấm: {sorted(TIMEFRAMES_BANNED)}")
