"""fx_cross_pairs.py — mean reversion trên CẶP CHÉO tổng hợp, khung H1.

PHÁT HIỆN CẤU TRÚC DẪN TỚI MODULE NÀY
=====================================
`fx_cointegration` đo được: spread EURUSD − β·GBPUSD có mean reversion thật
(control p = 0,0233, OOS Sharpe 0,949) nhưng biên rất mỏng vì phải trả chi phí
**HAI CHÂN**:

    phí giao dịch 2 chân   2,14 bps
    swap 2 chân            6,29 bps      <- biên broker tính trên CẢ HAI vị thế
    ─────────────────────────────────
    net                    +9,94 bps  trên gross +18,37

Nhưng spread đó CHÍNH LÀ tỷ giá chéo EURGBP. Giao dịch nó như một công cụ duy nhất
trả **một** spread và **một** biên swap:

    EURUSD/GBPUSD  →  EURGBP
    EURUSD/USDJPY  →  EURJPY
    USDJPY/GBPUSD  →  GBPJPY

Đây không phải xấp xỉ: arbitrage tam giác giữ tỷ giá chéo khớp với tích/thương hai
cặp USD tới từng pip. Thứ DUY NHẤT phải ước lượng là chi phí giao dịch của chính
cross đó, vì `D:/data-ticks-train` không có chuỗi cross.

Và đây cũng chính là vũ trụ mà Zheng Nan (2025) giao dịch — 22 cặp cointegrate của
họ đều là **cross JPY** (ZARJPY/NOKJPY, GBPJPY/EURJPY…), không phải cặp USD.

⚠️ GIỚI HẠN PHẢI GHI RÕ
========================
Chuỗi GIÁ của cross là chính xác (suy từ hai cặp USD). Chuỗi CHI PHÍ là ƯỚC LƯỢNG
từ bảng spread điển hình của broker retail. Vì vậy mọi kết quả ở đây là **có điều
kiện trên giả định chi phí**, và bài stress chi phí không phải một phép kiểm phụ —
nó là phép kiểm chính. Trước khi triển khai phải đọc spread thật của cross từ MT5.

Spread điển hình dùng ở đây (pip, tài khoản raw/ECN, giờ thanh khoản tốt):
    EURGBP 0,9 · EURJPY 1,0 · GBPJPY 1,8 · AUDJPY 1,3 · EURAUD 1,6 · EURCHF 1,3
Nguồn: bảng công bố của các broker raw-spread lớn. Đây là mức THẬN TRỌNG-TRUNG BÌNH;
broker tệ có thể gấp đôi, và cột stress ×2 trong báo cáo tồn tại vì lý do đó.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.python.shared import asset_profile as AP
from src.python.shared import fx_data as D

# ── định nghĩa cross: (tên, cặp tử, cặp mẫu, cách dựng)
# "ratio": cross = P(a)/P(b)   dùng khi cả hai là XXXUSD  -> EUR/GBP = EURUSD/GBPUSD
# "mult" : cross = P(a)*P(b)   dùng khi a là XXXUSD và b là USDXXX -> EUR/JPY = EURUSD*USDJPY
# "inv"  : cross = P(b)/P(a) nghịch đảo
CROSS_DEFS: Tuple[Tuple[str, str, str, str], ...] = (
    ("EURGBP", "EURUSD", "GBPUSD", "ratio"),
    ("EURAUD", "EURUSD", "AUDUSD", "ratio"),
    ("EURNZD", "EURUSD", "NZDUSD", "ratio"),
    ("GBPAUD", "GBPUSD", "AUDUSD", "ratio"),
    ("GBPNZD", "GBPUSD", "NZDUSD", "ratio"),
    ("AUDNZD", "AUDUSD", "NZDUSD", "ratio"),
    ("EURJPY", "EURUSD", "USDJPY", "mult"),
    ("GBPJPY", "GBPUSD", "USDJPY", "mult"),
    ("AUDJPY", "AUDUSD", "USDJPY", "mult"),
    ("NZDJPY", "NZDUSD", "USDJPY", "mult"),
    ("EURCHF", "EURUSD", "USDCHF", "mult"),
    ("GBPCHF", "GBPUSD", "USDCHF", "mult"),
    ("AUDCHF", "AUDUSD", "USDCHF", "mult"),
    ("EURCAD", "EURUSD", "USDCAD", "mult"),
    ("GBPCAD", "GBPUSD", "USDCAD", "mult"),
    ("AUDCAD", "AUDUSD", "USDCAD", "mult"),
    ("NZDCAD", "NZDUSD", "USDCAD", "mult"),
    ("CADJPY", "USDJPY", "USDCAD", "inv"),
    ("CHFJPY", "USDJPY", "USDCHF", "inv"),
    ("CADCHF", "USDCHF", "USDCAD", "inv"),
)

# Spread ĐO THẬT trên MT5 ngày 14/08/2026 (`scripts/measure_broker_costs.py`),
# trung vị của 20.000 tick gần nhất mỗi symbol. Trước đây đây là ƯỚC LƯỢNG lấy từ
# bảng công bố của broker, và ước lượng đó ĐẮT GẤP 2,9 LẦN thực tế (tỷ lệ trung vị
# thật/ước = 0,342) — nghĩa là mọi backtest chạy trước ngày này đều BI QUAN về chi phí.
#
# ⚠️ ĐO TRÊN TÀI KHOẢN DEMO MetaQuotes. Spread demo thường TỐT HƠN tài khoản thật, và
# tài khoản FTMO có điều kiện riêng. Phải đo lại trên chính tài khoản sẽ giao dịch
# trước khi cấp vốn; `scripts/measure_broker_costs.py` chạy lại được bất cứ lúc nào.
# Vì lý do đó `SPREAD_SAFETY_FACTOR` bên dưới nhân thêm biên an toàn khi backtest.
TYPICAL_SPREAD_PIPS: Dict[str, float] = {
    "EURGBP": 0.3, "EURAUD": 0.6, "EURNZD": 1.0, "GBPAUD": 0.9, "GBPNZD": 1.0,
    "AUDNZD": 0.4, "EURJPY": 0.4, "GBPJPY": 0.9, "AUDJPY": 0.5, "NZDJPY": 0.5,
    "EURCHF": 0.3, "GBPCHF": 0.5, "AUDCHF": 0.4, "EURCAD": 0.5, "GBPCAD": 0.6,
    "AUDCAD": 0.6, "NZDCAD": 0.4, "CADJPY": 0.7, "CHFJPY": 0.7, "CADCHF": 1.0,
}

# Hệ số an toàn nhân vào spread ĐO ĐƯỢC trên demo. Không đo được từ chính demo —
# nó là biên phòng vệ cho khoảng cách demo ↔ tài khoản thật.
#
# ⚠️ NÂNG 1,5 → 3,0 NGÀY 15/08/2026, VÀ THÊM SÀN THEO TỪNG CẶP.
#
# Đối chiếu bảng spread tham chiếu FTMO 2025 cho thấy **16/18 cross bị đánh giá
# THẤP chi phí ngay cả SAU khi nhân 1,5**:
#
#     NZDCAD   0,40 × 1,5 = 0,60  ·  FTMO ~1,3   → thiếu 2,2 lần
#     EURCHF   0,30 × 1,5 = 0,45  ·  FTMO ~1,0   → thiếu 2,2 lần
#     AUDNZD   0,40 × 1,5 = 0,60  ·  FTMO ~1,2   → thiếu 2,0 lần
#     EURJPY   0,40 × 1,5 = 0,60  ·  FTMO ~1,2   → thiếu 2,0 lần
#
# Tác động đo trên vòng 2026 (631 lệnh cross): thiếu **224,7 bps**, tức lợi nhuận
# thật thấp hơn báo cáo khoảng 0,36 điểm %. Riêng NZDCAD gánh 145/225 bps thiếu
# hụt — mà đó là công cụ của `RsiDivNZDCADM30`, chân đóng góp lớn thứ hai.
#
# VÌ SAO KHÔNG CHỈ NÂNG HỆ SỐ CHO TO
# ===================================
# Nhân đều một hệ số cho mọi cặp là sai cách, và đo được là sai: 3,0 vẫn hụt
# EURCHF và NZDCAD, trong khi đã làm EURGBP đắt hơn tham chiếu FTMO 50%
# (0,3 × 3,0 = 0,90 so với ~0,7). Phải nâng tới 3,5 mới phủ hết, và lúc đó EURGBP
# đắt gấp rưỡi thực tế — tức PHẠT OAN những cặp mà demo đo đúng, có thể loại nhầm
# một chân tốt.
#
# Lý do gốc: khoảng cách demo ↔ thật KHÔNG đồng đều giữa các cặp. Cặp thanh khoản
# cao (EURGBP) thì demo gần thật; cặp mỏng (NZDCAD, EURCHF) thì demo lạc quan hơn
# nhiều. Một hệ số nhân không diễn tả được điều đó.
#
# Nên: `spread_pips()` lấy **giá trị LỚN HƠN** giữa (đo được × hệ số) và SÀN tham
# chiếu. Mỗi cặp nhận đúng mức thận trọng nó cần, không hơn.
SPREAD_SAFETY_FACTOR: float = 3.0

# SÀN chi phí theo từng cặp (pip) — không bao giờ tính rẻ hơn mức này.
#
# Nguồn: bảng spread tham chiếu FTMO 2025 (commission $2,50/lot/chiều từ
# 29/09/2025; spread hạ + Volume Bands từ 15/09/2025). Đây là **ước lượng để mô
# hình hoá**, KHÔNG phải số liệu FTMO công bố — trang Symbols của họ chỉ cho xem
# spread LIVE, không có bảng trung bình năm.
#
# Vì là ước lượng, nó chỉ dùng làm SÀN chứ không thay số đo: chỗ nào demo đo ra
# đắt hơn thì tôn trọng số đo. Khi `scripts/measure_broker_costs.py` chạy được
# trên chính tài khoản FTMO thì bảng này bị thay bằng số đo thật và cả hệ số lẫn
# sàn đều về gần 1,0.
FTMO_SPREAD_FLOOR_PIPS: Dict[str, float] = {
    "EURGBP": 0.7, "EURAUD": 1.2, "EURNZD": 1.5, "GBPAUD": 1.5, "GBPNZD": 1.8,
    "AUDNZD": 1.2, "EURJPY": 1.2, "GBPJPY": 1.3, "AUDJPY": 1.0, "NZDJPY": 1.2,
    "EURCHF": 1.0, "GBPCHF": 1.3, "AUDCHF": 1.2, "EURCAD": 1.3, "GBPCAD": 1.5,
    "AUDCAD": 1.0, "NZDCAD": 1.3, "CADJPY": 1.1, "CHFJPY": 1.4, "CADCHF": 1.3,
}


def spread_pips(cross: str) -> float:
    """Spread dùng cho backtest — LỚN HƠN giữa (đo được × hệ số) và sàn tham chiếu.

    Lấy max chứ không lấy một trong hai: số đo demo bắt được cặp nào broker này
    thật sự rẻ, còn sàn bắt được cặp nào demo lạc quan quá mức. Bỏ vế nào cũng mất
    một nửa thông tin.
    """
    measured = TYPICAL_SPREAD_PIPS.get(cross, 1.0) * SPREAD_SAFETY_FACTOR
    return max(measured, FTMO_SPREAD_FLOOR_PIPS.get(cross, 0.0))


COMMISSION_USD_PER_LOT_RT = 7.0


@dataclass(frozen=True)
class CrossSpec:
    name: str
    base: str
    quote: str
    pip: float
    spread_pips: float

    @property
    def cost_1rt_bps_at(self):
        """Hàm tính chi phí khứ hồi (bps) tại một mức giá."""
        def _f(price: float) -> float:
            # spread quy về bps: pip / price * 1e4 * so_pip
            spread_bps = self.spread_pips * self.pip / price * 1e4
            # commission: $7/lot trên 100.000 đơn vị base -> 0,70 pip tương đương
            comm_bps = (COMMISSION_USD_PER_LOT_RT / 100_000.0) / price * 1e4 \
                if self.quote == "USD" else (0.70 * self.pip) / price * 1e4
            return spread_bps + comm_bps
        return _f


def _spec(name: str) -> CrossSpec:
    base, quote = name[:3], name[3:]
    pip = 0.01 if quote == "JPY" else 0.0001
    return CrossSpec(name=name, base=base, quote=quote, pip=pip,
                     spread_pips=spread_pips(name))


def build_crosses(timeframe: str = "H1", start: str = "2020-01-01"
                  ) -> Tuple[pd.DataFrame, Dict[str, CrossSpec]]:
    """Chuỗi giá cross tổng hợp + đặc tả từng cross.

    Giá dựng từ hai cặp USD nên CHÍNH XÁC (arbitrage tam giác). Chỉ chi phí là ước lượng.
    """
    px: Dict[str, pd.Series] = {}
    for sym in AP.FX_ALL:
        b = D.build_bars(D.load_m1(sym), timeframe)
        px[sym] = b[b.index >= start]["close"]
    base = pd.DataFrame(px).dropna()

    # NÓI TÊN CÔNG CỤ ĐÃ LÀM RỖNG RỔ. Không có dòng này thì rổ 20 cross trả về
    # một khung (0, 20) hoàn toàn hợp lệ về kiểu, và lỗi chỉ lộ ra ở tận
    # `evaluate_cross` dưới dạng `IndexError: index -1 ... size 0` — không tệp,
    # không tên công cụ. Ngày 20/08/2026 mất khoảng một giờ chỉ để lần ra rằng
    # thủ phạm là EURUSD (200.000 nến M1, 0 nến H1, vì spread NaN).
    #
    # `dropna()` lấy GIAO của 7 cột, nên MỘT cột rỗng là đủ xoá tất cả.
    if base.empty:
        empty = [s for s in px if len(px[s]) == 0]
        short = {s: len(px[s]) for s in px if 0 < len(px[s])}
        from src.python.utils.logger import log_error

        log_error(
            f"[CROSS] rổ {timeframe} RỖNG sau khi giao 7 cặp USD. "
            f"Công cụ KHÔNG có nến nào: {empty or 'không có'}. "
            f"Số nến từng cặp: {short}. "
            f"Mọi chân cross sẽ đứng ngoài cho tới khi công cụ đó có dữ liệu.")

    out, specs = {}, {}
    for name, a, b, how in CROSS_DEFS:
        if a not in base.columns or b not in base.columns:
            continue
        if how == "mult":
            # a là XXXUSD, b là USDYYY:  XXX/YYY = (XXX/USD) × (USD/YYY)
            s = base[a] * base[b]
        else:
            # "ratio" (cả hai XXXUSD) và "inv" (cả hai USDXXX) DÙNG CHUNG công thức.
            # ratio: EURGBP = (EUR/USD) / (GBP/USD)
            # inv  : CADJPY = (JPY/USD) / (CAD/USD) = USDJPY / USDCAD
            # Bản đầu viết `base[b]/base[a]` cho nhánh "inv" — sai chiều, cho ra giá
            # 0,009 thay vì 111, và chi phí quy theo bps phồng lên 22.000 bps.
            s = base[a] / base[b]
        out[name] = s
        specs[name] = _spec(name)
    return pd.DataFrame(out), specs


# ═══════════════════════════════════════════════════════ chiến lược
@dataclass(frozen=True)
class Config:
    """Luật lấy từ Zheng Nan, áp cho MỘT chuỗi thay vì spread hai chân."""
    lookback_hl_mult: float = 3.0     # cửa sổ Bollinger = HL × hệ số
    entry_sigma: float = 2.0
    min_hl_bars: int = 4
    max_hl_bars: int = 120
    reestimate_bars: int = 500
    require_reentry: bool = True
    markup_pct: float = 1.0           # biên swap broker, MỘT chân


def half_life(x: np.ndarray) -> float:
    s = x[~np.isnan(x)]
    if len(s) < 30:
        return float("inf")
    ds, lag = np.diff(s), s[:-1]
    A = np.column_stack([lag, np.ones(len(lag))])
    coef, *_ = np.linalg.lstsq(A, ds, rcond=None)
    a = float(coef[0])
    if a >= 0 or (1.0 + a) <= 0:
        return float("inf")
    return float(np.log(2.0) / abs(np.log(1.0 + a)))


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    side: int
    entry_z: float
    exit_reason: str
    gross_bps: float
    cost_bps: float
    bars_held: int


def simulate(name: str, price: pd.Series, spec: CrossSpec,
             cfg: Config = Config()) -> List[Trade]:
    """Mean reversion trên log giá cross. MỘT chân — chi phí một spread, một swap.

    Khác `fx_cointegration.simulate_pair` ở đúng chỗ đó: không có hedge ratio để
    ước lượng (cross tự nó là spread), và chi phí không nhân đôi.
    """
    p = price.dropna()
    lp = np.log(p).to_numpy()
    idx = p.index
    n = len(lp)
    trades: List[Trade] = []
    pos = 0
    entry_i = -1
    entry_lp = 0.0
    entry_z = 0.0
    was_outside = 0
    hl = window = None
    last_fit = -10 ** 9

    for i in range(600, n):
        if i - last_fit >= cfg.reestimate_bars:
            w = lp[max(0, i - 2000):i]
            h = half_life(w - np.mean(w))
            if cfg.min_hl_bars <= h <= cfg.max_hl_bars:
                hl = h
                window = int(np.ceil(h * cfg.lookback_hl_mult))
            last_fit = i
        if window is None:
            continue

        hist = lp[max(0, i - window):i]
        if len(hist) < max(20, window // 2):
            continue
        mu, sd = float(np.mean(hist)), float(np.std(hist, ddof=1))
        if sd <= 0:
            continue
        z = (lp[i] - mu) / sd

        if pos != 0:
            crossed = (pos == 1 and lp[i] >= mu) or (pos == -1 and lp[i] <= mu)
            timeout = (i - entry_i) >= int(np.ceil(hl * cfg.lookback_hl_mult))
            if crossed or timeout:
                gross = pos * (lp[i] - entry_lp) * 1e4
                cost = spec.cost_1rt_bps_at(float(p.iloc[i]))
                trades.append(Trade(idx[entry_i], idx[i], pos, round(entry_z, 2),
                                    "MEAN" if crossed else "TIMESTOP",
                                    round(gross, 3), round(cost, 3), i - entry_i))
                pos = 0
            continue

        if cfg.require_reentry:
            if z > cfg.entry_sigma:
                was_outside = 1
            elif z < -cfg.entry_sigma:
                was_outside = -1
            elif was_outside == 1 and z <= cfg.entry_sigma:
                pos, entry_i, entry_lp, entry_z = -1, i, lp[i], z
                was_outside = 0
            elif was_outside == -1 and z >= -cfg.entry_sigma:
                pos, entry_i, entry_lp, entry_z = +1, i, lp[i], z
                was_outside = 0
        else:
            if z > cfg.entry_sigma:
                pos, entry_i, entry_lp, entry_z = -1, i, lp[i], z
            elif z < -cfg.entry_sigma:
                pos, entry_i, entry_lp, entry_z = +1, i, lp[i], z
    return trades
