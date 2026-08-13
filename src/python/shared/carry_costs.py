"""carry_costs.py — mô hình phí swap/carry qua đêm cho danh mục FX.

VÌ SAO MODULE NÀY TỒN TẠI — BÀI HỌC TỪ `project-refer/carver-systematic-trading`
================================================================================
Repo tham chiếu đó ghi lại một quá trình nghiên cứu kết thúc bằng kết luận phủ định,
và kết luận ấy đắt giá hơn nhiều kết quả dương:

    "EWMAC trend following on retail CFDs is not viable after swap costs."
    "Swap alone turns +$130K gross profit into -$80K net loss."

Bảng kết quả của họ nói rõ trình tự sụp đổ:
    Gross (không chi phí)              Sharpe  0,314
    Net (chỉ spread + commission)      Sharpe  0,216   <- vẫn sống
    Net (đủ chi phí, có swap)          Sharpe −0,456   <- CHẾT
Tức spread và commission KHÔNG phải thứ giết chiến lược; **swap mới là**.

`currency_reversal` giữ vị thế **21 ngày** = ~21 đêm swap mỗi chu kỳ. Cho đến trước
module này, backtest chỉ tính spread + commission — đúng cột "Sharpe 0,216" của Carver,
tức đúng cái cột trông vẫn ổn ngay trước khi sụp.

VÀ CÓ MỘT LÝ DO CẤU TRÚC KHIẾN CHIẾN LƯỢC NÀY DỄ TỔN THƯƠNG
============================================================
Reversal cắt ngang **mua đồng vừa YẾU, bán đồng vừa MẠNH**. Theo cơ chế carry trade
(Brière & Drut; Menkhoff et al.), đồng lãi suất CAO có xu hướng tăng giá trong giai
đoạn bình lặng. Nên "đồng vừa mạnh" thường là đồng lãi suất cao → chiến lược có xu
hướng **SHORT đồng lãi cao và LONG đồng lãi thấp** = **short carry hệ thống**.

Đó là một giả thuyết, không phải một sự thật — và nó phải được ĐO. Đó là việc của
module này.

CÁCH TÍNH
=========
Với một vị thế long đồng X / short đồng Y, phí carry mỗi năm ≈ (r_X − r_Y), tức chênh
lệch lãi suất. Với danh mục có tỷ trọng `w` trên 8 đồng tiền (tổng = 0):

    carry năm =  Σ w_i · r_i          [r_i = lãi suất chính sách của đồng i]
    carry ngày = carry năm / 365 · SWAP_CALENDAR_MULTIPLIER

`SWAP_CALENDAR_MULTIPLIER = 365/252` lấy nguyên từ Carver `core/costs.py`: swap tính
theo 365 ngày LỊCH nhưng backtest chỉ lặp qua ~252 ngày GIAO DỊCH, nên phải nhân bù
cho cuối tuần và ngày lễ. Bỏ qua hệ số này là hạ thấp chi phí thật đi ~31%.

⚠️ SPREAD BROKER TRÊN SWAP. Broker retail không trả đúng chênh lệch liên ngân hàng: họ
cộng một biên vào cả hai chiều, nên chiều phải trả thì trả nhiều hơn và chiều được nhận
thì nhận ít hơn. `broker_markup_pct` mô hình hoá điều đó, và mặc định KHÔNG bằng 0.

NGUỒN DỮ LIỆU LÃI SUẤT
======================
`D:/data-ticks-train` chỉ có giá, không có lãi suất. Bảng dưới đây là **lãi suất chính
sách công bố của ngân hàng trung ương**, dữ liệu công khai, ghi theo mốc thay đổi. Đây
là xấp xỉ cho lãi suất tiền gửi qua đêm mà swap thật neo vào — đủ chính xác để trả lời
câu hỏi "chiến lược này có bị carry giết không", chưa đủ để hạch toán P&L đến từng pip.

Ở live, KHÔNG dùng bảng này: đọc thẳng `SymbolInfo.swap_long` / `swap_short` từ MT5,
đó là con số broker thật sự tính.
"""
from __future__ import annotations

from typing import Dict, Optional, Sequence

import numpy as np
import pandas as pd

# Swap tính 365 ngày lịch, backtest lặp 252 ngày giao dịch (Carver core/costs.py).
SWAP_CALENDAR_MULTIPLIER = 365.0 / 252.0

# Biên broker cộng thêm vào swap, tính bằng %/năm trên notional MỖI CHIỀU.
# Retail FX điển hình 0,5-1,5%/năm; lấy 1,0% làm mặc định thận trọng.
# ĐO THẬT 14/08/2026 trên MT5: biên trung vị 0.382 %/năm trên 27 symbol
# (`reports/broker_costs.csv`). Giả định cũ 1,0%/năm ĐẮT GẤP 2.6 LẦN thực tế.
# Giữ 1,0 làm MẶC ĐỊNH có chủ ý: số đo là trên tài khoản DEMO, và biên phân tán rất
# rộng giữa các symbol (p25 0,248 · p75 1,431 · max 2,762 ở AUDCHF). Báo cáo chính
# thức dùng 1,0; độ nhạy đo ở 0,0-3,0 để thấy vùng an toàn.
DEFAULT_BROKER_MARKUP_PCT = 1.0
MEASURED_BROKER_MARKUP_PCT = 0.382   # đo được, dùng khi cần con số thực tế

# ═════════════════════════════════════════════════════════ lãi suất chính sách
# (ngày hiệu lực, lãi suất %/năm). Dữ liệu công khai của NHTW, ghi theo mốc đổi.
# Chỉ cần độ phân giải tháng — swap thật đổi hàng ngày nhưng chênh lệch giữa các
# đồng tiền thì đi theo chu kỳ chính sách, không theo nhiễu ngày.
POLICY_RATES: Dict[str, Dict[str, float]] = {
    "USD": {"2019-12-01": 1.75, "2020-03-15": 0.25, "2022-03-17": 0.50,
            "2022-06-16": 1.75, "2022-09-22": 3.25, "2022-12-15": 4.50,
            "2023-03-23": 5.00, "2023-07-27": 5.50, "2024-09-19": 5.00,
            "2024-12-19": 4.50, "2025-09-18": 4.25, "2026-01-29": 4.00},
    "EUR": {"2019-12-01": -0.50, "2022-07-27": 0.00, "2022-10-27": 1.50,
            "2022-12-21": 2.00, "2023-03-22": 3.00, "2023-06-21": 3.50,
            "2023-09-20": 4.00, "2024-06-12": 3.75, "2024-10-23": 3.25,
            "2025-01-30": 2.75, "2025-06-05": 2.00},
    "GBP": {"2019-12-01": 0.75, "2020-03-19": 0.10, "2022-02-03": 0.50,
            "2022-06-16": 1.25, "2022-11-03": 3.00, "2023-02-02": 4.00,
            "2023-06-22": 5.00, "2023-08-03": 5.25, "2024-08-01": 5.00,
            "2024-11-07": 4.75, "2025-02-06": 4.50, "2025-08-07": 4.00},
    "JPY": {"2019-12-01": -0.10, "2024-03-19": 0.10, "2024-07-31": 0.25,
            "2025-01-24": 0.50, "2026-01-23": 0.75},
    "AUD": {"2019-12-01": 0.75, "2020-03-20": 0.25, "2020-11-03": 0.10,
            "2022-05-03": 0.35, "2022-08-02": 1.85, "2022-11-01": 2.85,
            "2023-02-07": 3.35, "2023-06-06": 4.10, "2023-11-07": 4.35,
            "2025-02-18": 4.10, "2025-05-20": 3.85, "2025-08-12": 3.60},
    "CAD": {"2019-12-01": 1.75, "2020-03-27": 0.25, "2022-03-02": 0.50,
            "2022-06-01": 1.50, "2022-09-07": 3.25, "2022-12-07": 4.25,
            "2023-07-12": 5.00, "2024-06-05": 4.75, "2024-10-23": 3.75,
            "2024-12-11": 3.25, "2025-03-12": 2.75, "2025-09-17": 2.50},
    "CHF": {"2019-12-01": -0.75, "2022-06-16": -0.25, "2022-09-22": 0.50,
            "2022-12-15": 1.00, "2023-06-22": 1.75, "2024-03-21": 1.50,
            "2024-06-20": 1.25, "2024-09-26": 1.00, "2024-12-12": 0.50,
            "2025-03-20": 0.25, "2025-06-19": 0.00},
    "NZD": {"2019-12-01": 1.00, "2020-03-16": 0.25, "2021-10-06": 0.50,
            "2022-04-13": 1.50, "2022-08-17": 3.00, "2022-11-23": 4.25,
            "2023-04-05": 5.25, "2023-05-24": 5.50, "2024-08-14": 5.25,
            "2024-11-27": 4.25, "2025-02-19": 3.75, "2025-05-28": 3.25},
}


def rate_series(index: pd.DatetimeIndex,
                currencies: Sequence[str] = tuple(POLICY_RATES)) -> pd.DataFrame:
    """Bảng lãi suất chính sách %/năm theo ngày, forward-fill từ mốc thay đổi."""
    out = {}
    for ccy in currencies:
        table = POLICY_RATES.get(ccy)
        if not table:
            out[ccy] = pd.Series(0.0, index=index)
            continue
        s = pd.Series(table)
        s.index = pd.to_datetime(s.index)
        out[ccy] = s.sort_index().reindex(
            s.index.union(index)).ffill().reindex(index).bfill()
    return pd.DataFrame(out)


# ═════════════════════════════════════════════════════════ phí carry danh mục
def daily_carry_bps(weights: pd.DataFrame, *,
                    broker_markup_pct: float = DEFAULT_BROKER_MARKUP_PCT,
                    rates: Optional[pd.DataFrame] = None) -> pd.Series:
    """Phí carry MỖI NGÀY (bps, DƯƠNG = chi phí) cho danh mục tỷ trọng đồng tiền.

    `weights` — chỉ số ngày × cột đồng tiền, tổng mỗi hàng = 0 (dollar-neutral).

    Hai thành phần tách bạch có chủ ý:
      * chênh lệch lãi suất — có thể ÂM (tức ta NHẬN carry) nếu danh mục tình cờ
        long đồng lãi cao. Không ép nó thành chi phí.
      * biên broker — LUÔN là chi phí, tỷ lệ với TỔNG GIÁ TRỊ TUYỆT ĐỐI vị thế
        (Σ|w|), vì broker cộng biên vào cả chiều trả lẫn chiều nhận.
    """
    idx = weights.index
    R = rates if rates is not None else rate_series(idx, list(weights.columns))
    R = R.reindex(index=idx, columns=weights.columns).fillna(0.0)

    # carry ròng %/năm — dấu âm nghĩa là danh mục NHẬN tiền
    net_annual_pct = -(weights * R).sum(axis=1)
    # biên broker: luôn trả, trên tổng phơi nhiễm gộp
    markup_annual_pct = weights.abs().sum(axis=1) * broker_markup_pct

    total_annual_pct = net_annual_pct + markup_annual_pct
    return total_annual_pct / 365.0 * 100.0 * SWAP_CALENDAR_MULTIPLIER


def carry_breakdown(weights: pd.DataFrame, *,
                    broker_markup_pct: float = DEFAULT_BROKER_MARKUP_PCT,
                    rates: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Tách phí carry thành hai nguồn — để biết chi phí đến từ đâu, không chỉ bao nhiêu."""
    idx = weights.index
    R = rates if rates is not None else rate_series(idx, list(weights.columns))
    R = R.reindex(index=idx, columns=weights.columns).fillna(0.0)
    k = 1.0 / 365.0 * 100.0 * SWAP_CALENDAR_MULTIPLIER
    rate_bps = -(weights * R).sum(axis=1) * k
    markup_bps = weights.abs().sum(axis=1) * broker_markup_pct * k
    return pd.DataFrame({
        "rate_diff_bps": rate_bps,        # âm = nhận carry
        "broker_markup_bps": markup_bps,  # luôn dương
        "total_carry_bps": rate_bps + markup_bps,
    })


def pair_carry_bps(pair_weights: pd.DataFrame, pair_specs: Dict[str, tuple], *,
                   broker_markup_pct: float = DEFAULT_BROKER_MARKUP_PCT,
                   rates: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Phí carry tính trên VỊ THẾ CẶP thực giữ — bản đúng để hạch toán live.

    Vì sao phải có bản này bên cạnh `daily_carry_bps()`: broker tính swap trên
    TỪNG VỊ THẾ CẶP đang mở, không trên phơi nhiễm tiền tệ ròng. Tính trên tỷ trọng
    đồng tiền sẽ đếm dư phần trọng số USD — USD không phải một vị thế riêng mà đã
    nằm sẵn trong chân kia của mỗi cặp.

    `pair_specs[symbol] = (base_ccy, quote_ccy)`. Với vị thế long cặp XXXYYY,
    carry năm = +(r_XXX − r_YYY): giữ đồng cơ sở, tài trợ bằng đồng định giá.
    """
    idx = pair_weights.index
    ccys = sorted({c for spec in pair_specs.values() for c in spec})
    R = rates if rates is not None else rate_series(idx, ccys)
    R = R.reindex(index=idx, columns=ccys).fillna(0.0)

    net_annual = pd.Series(0.0, index=idx)
    for sym in pair_weights.columns:
        base, quote = pair_specs[sym]
        net_annual += pair_weights[sym] * (R[base] - R[quote])
    gross_exposure = pair_weights.abs().sum(axis=1)

    k = 1.0 / 365.0 * 100.0 * SWAP_CALENDAR_MULTIPLIER
    rate_bps = -net_annual * k                       # âm = nhận carry
    markup_bps = gross_exposure * broker_markup_pct * k
    return pd.DataFrame({
        "rate_diff_bps": rate_bps,
        "broker_markup_bps": markup_bps,
        "total_carry_bps": rate_bps + markup_bps,
        "gross_exposure": gross_exposure,
    })


def carry_exposure(weights: pd.DataFrame,
                   rates: Optional[pd.DataFrame] = None) -> pd.Series:
    """Phơi nhiễm carry của danh mục, %/năm. DƯƠNG = long carry (nhận tiền).

    Đây là chẩn đoán quan trọng nhất của module: nó trả lời trực tiếp câu hỏi
    "chiến lược này có short carry hệ thống không?" — nếu trung bình âm rõ rệt thì
    có, và mọi kết quả backtest chưa tính swap đều bị thổi phồng.
    """
    idx = weights.index
    R = rates if rates is not None else rate_series(idx, list(weights.columns))
    R = R.reindex(index=idx, columns=weights.columns).fillna(0.0)
    return (weights * R).sum(axis=1)
