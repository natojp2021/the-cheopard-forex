"""portfolio.py — DANH MỤC NĂM CHÂN của The Cheopard Forex. Điểm vào duy nhất cho live.

═══════════════════════════════════════════════════════════════════════════════
1. NĂM CHÂN, VÀ VÌ SAO CHIA ĐỀU
═══════════════════════════════════════════════════════════════════════════════
    CurrencyReversal    D1 → H1   long đồng vừa yếu / short đồng vừa mạnh
    CurrencyCarry       D1 → H1   long đồng lãi cao / short đồng lãi thấp
    CrossMeanReversion  H1 → H1   mean reversion TỪNG cross so với CHÍNH NÓ
    CrossMomentum       D1 → H1   xếp hạng cắt ngang 20 cross theo momentum
    CrossXsReversion    H4 → H4   xếp hạng cắt ngang 20 cross theo z-score

Hai chân cross cuối dùng cùng một rổ 20 cross nhưng ngược chiều nhau về thang thời
gian (momentum 63 ngày vs reversion 5 ngày) nên tương quan đo được chỉ +0,004.

Ba nguồn ĐỘC LẬP kết luận rằng chia đều nhiều chân không tương quan là cách ghép
tốt nhất, và lợi ích chính là **CẮT DRAWDOWN** chứ không phải tăng lợi nhuận:

    Olszweski & Zhou (2014)   momentum 0,79 + carry 0,63  →  0,98
                              MaxDD −17,4%/−29,2%  →  **−8,95%**
    Burnside/Eichenbaum/Rebelo (NBER w16942)
                              carry 0,41 + momentum 0,62  →  **0,98**
                              "phản ánh tương quan THẤP giữa hai chiến lược"
    đo được ở đây             0,544 / 0,364 / 1,145  →  **1,199**
                              MaxDD giảm **65%** so với chân tốt nhất

Cả hai nguồn cũng chứng minh **chia đều thắng tối ưu hoá mean-variance** (Olszweski
& Zhou đo Max-Utility cho Sharpe 0,70 < 0,79 của momentum đơn lẻ, vì sai số ước
lượng kỳ vọng lợi nhuận). Nên tỷ trọng ở đây là 1/3 cố định — KHÔNG tối ưu hoá.

Ma trận tương quan đo được (gần trực giao hoàn hảo — đây là lý do nó hoạt động):

                  reversal    carry   cross_H1
    reversal         1,000   −0,097     +0,054
    carry           −0,097    1,000     +0,008
    cross_H1        +0,054   +0,008      1,000

═══════════════════════════════════════════════════════════════════════════════
2. CHUẨN HOÁ BIẾN ĐỘNG TRƯỚC KHI CHIA ĐỀU — KHÔNG PHẢI CHI TIẾT
═══════════════════════════════════════════════════════════════════════════════
Ba chân có biến động rất khác nhau ở đòn bẩy 1,0. Cộng thẳng thì chân biến động lớn
nhất áp đảo và "chia đều" chỉ là chia đều trên giấy. Mỗi chân vì vậy được chia cho
độ lệch chuẩn của chính nó (ước lượng trên cửa sổ FORM, KHÔNG dùng dữ liệu OOS) rồi
mới chia đều.

Đây là dùng **biến động** để chia tỷ trọng — được phép; dùng **kỳ vọng lợi nhuận**
thì không (xem §1).

═══════════════════════════════════════════════════════════════════════════════
3. GỘP VỊ THẾ TRƯỚC KHI TÍNH CHI PHÍ
═══════════════════════════════════════════════════════════════════════════════
Burnside et al. mô tả đúng cơ chế cần dùng:

    "Khi hai chiến lược ĐỒNG THUẬN về dấu, vị thế ròng cho đồng tiền đó là ±1/n.
     Khi chúng BẤT ĐỒNG, vị thế ròng cho đồng tiền đó là ZERO."

Hai chân D1 chạy trên CÙNG 7 cặp USD nên chúng chồng lấn và phải gộp tỷ trọng trước
khi tính phí — `currency_carry.combined()` làm việc đó, và đo được nó tiết kiệm
**+0,595%/năm** so với cộng hai chuỗi lợi nhuận đã tính phí riêng.

Chân H1 chạy trên **cặp chéo**, tức công cụ khác hẳn, nên nó KHÔNG chồng lấn với
hai chân kia ở tầng vị thế. Ba chân vì vậy gộp ở tầng RỦI RO (chuẩn hoá + chia đều),
không ở tầng tỷ trọng cặp.

⚠️ Ngoại lệ cần biết: một vị thế EURGBP ngầm mang phơi nhiễm EUR long + GBP short,
nên về mặt kinh tế nó KHÔNG hoàn toàn độc lập với hai chân D1. Tương quan đo được
(+0,054 và +0,008) cho thấy phần chồng lấn thực tế là nhỏ, nhưng nó không bằng 0 và
`exposure_report()` tồn tại để theo dõi điều đó ở live.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.python.execution import decision_log as DLOG
from src.python.strategies.d1 import currency_carry as CY
from src.python.strategies.d1 import currency_reversal as CR
from src.python.strategies.h1 import cross_mean_reversion as XMR

# Tỷ trọng CỐ ĐỊNH — chia đều, không tối ưu hoá. Xem §1.
# MƯỜI MỘT CHIẾN LƯỢC, TÁM NHÓM RỦI RO.
#
# Sáu chân Z-Band mới (13/08/2026) chạy cùng một luật trên ba CÔNG CỤ ở hai khung.
# Đo được hai cặp cùng công cụ tương quan cao:
#     zb_audcad_h1 ↔ zb_audcad_m30   +0,712   ← VƯỢT ngưỡng độc lập 0,70
#     zb_nzdcad_h1 ↔ zb_nzdcad_m30   +0,628
#
# Trên ngưỡng 0,70 thì hai chân là MỘT cược ở hai nhịp: chia đều cho chúng như hai
# chân độc lập là tự nhân đôi phơi nhiễm vào AUDCAD mà tưởng đang đa dạng hoá.
#
# Cách xử lý: gộp theo CÔNG CỤ. Ba nhóm z-band (AUDCAD · NZDCAD · GBPAUD) mỗi nhóm
# nhận MỘT suất, chia đôi giữa hai khung bên trong nhóm. Tổng tám suất bằng nhau.
# Đây là lý do tỷ trọng z-band là 1/16 chứ không phải 1/11 — không phải tinh chỉnh.
_UNIT = 1.0 / 21.0                # HAI MỐT nhóm rủi ro, chia đều
_HALF = _UNIT / 2.0               # nhóm hai khung  → chia đôi
_THIRD = _UNIT / 3.0              # nhóm ba khung   → chia ba

LEG_WEIGHTS: Dict[str, float] = {
    "reversal": _UNIT, "carry": _UNIT, "cross_h1": _UNIT,
    "cross_mom": _UNIT, "cross_xs_h4": _UNIT,
    # AUDCAD và GBPAUD có chân ở BA khung → mỗi chân một phần ba suất của nhóm
    "zb_audcad_h1": _THIRD, "zb_audcad_m30": _THIRD, "zb_audcad_h4": _THIRD,
    "zb_gbpaud_h1": _THIRD, "zb_gbpaud_m30": _THIRD, "zb_gbpaud_h4": _THIRD,
    "zb_nzdcad_h1": _HALF, "zb_nzdcad_m30": _HALF,
    # GBPNZD chỉ có chân H4 — bản M30 loại vì FORM/OOS chênh 6,5 lần, bản H1 loại
    # vì OOS ÂM (−0,119) dù vùng tham số đẹp nhất toàn bộ dự án (18/18 ô dương)
    "zb_gbpnzd_h4": _UNIT,
    # Ba chân H1 thêm 14/08 — mỗi công cụ chỉ có MỘT khung nên nhận nguyên một suất
    "zb_eurchf_h1": _UNIT, "zb_gbpusd_h1": _UNIT, "zb_eurgbp_h1": _UNIT,
    # Bốn chân HỌ MỚI (14/08) — mỗi chân một nhóm riêng vì chúng đọc đại lượng khác
    # hẳn nhau VÀ khác họ Z-Band. |tương quan| chéo tối đa 0,206.
    "streak_gbpcad_h1": _UNIT, "streak_gbpaud_h1": _UNIT,
    "volreg_gbpaud_h1": _UNIT,
    # RsiDiv NZDCAD có chân ở CẢ H1 và M30, tương quan 0,303 → chung một suất
    "rsidiv_nzdcad_h1": _HALF, "rsidiv_nzdcad_m30": _HALF,
    # Sáu chân thêm 14/08 (vòng 68) — mỗi chân một nhóm riêng
    "rsidiv_gbpnzd_m30": _UNIT, "streak_audcad_m30": _UNIT,
    "volreg_gbpchf_m30": _UNIT, "volreg_audchf_m30": _UNIT,
    "accel_gbpnzd_h1": _UNIT,
}

# Nhóm rủi ro — dùng cho báo cáo và cho kiểm tra độc lập ở tầng NHÓM, vì ngưỡng 0,70
# phải áp cho nhóm chứ không cho từng chân sau khi đã gộp.
RISK_GROUPS: Dict[str, Tuple[str, ...]] = {
    "CurrencyReversal": ("reversal",), "CurrencyCarry": ("carry",),
    "CrossMeanRev_H1": ("cross_h1",), "CrossMomentum": ("cross_mom",),
    "CrossXsRev_H4": ("cross_xs_h4",),
    "ZBand_AUDCAD": ("zb_audcad_h1", "zb_audcad_m30", "zb_audcad_h4"),
    "ZBand_NZDCAD": ("zb_nzdcad_h1", "zb_nzdcad_m30"),
    "ZBand_GBPAUD": ("zb_gbpaud_h1", "zb_gbpaud_m30", "zb_gbpaud_h4"),
    "ZBand_GBPNZD": ("zb_gbpnzd_h4",),
    "ZBand_EURCHF": ("zb_eurchf_h1",),
    "ZBand_GBPUSD": ("zb_gbpusd_h1",),
    "ZBand_EURGBP": ("zb_eurgbp_h1",),
    "RsiDiv_NZDCAD": ("rsidiv_nzdcad_h1", "rsidiv_nzdcad_m30"),
    "Streak_GBPCAD": ("streak_gbpcad_h1",),
    "Streak_GBPAUD": ("streak_gbpaud_h1",),
    "VolRegime_GBPAUD": ("volreg_gbpaud_h1",),
    "RsiDiv_GBPNZD": ("rsidiv_gbpnzd_m30",),
    "Streak_AUDCAD": ("streak_audcad_m30",),
    "VolRegime_GBPCHF": ("volreg_gbpchf_m30",),
    "VolRegime_AUDCHF": ("volreg_audchf_m30",),
    "Accel_GBPNZD": ("accel_gbpnzd_h1",),
}

# ═══════════════════════════════════════════════════════════════════════════════
# 22 CHÂN MỘT-CÔNG-CỤ — ánh xạ khoá chân sang TÊN chiến lược trong registry
# ═══════════════════════════════════════════════════════════════════════════════
# THÊM 14/08/2026 SAU KHI PHÁT HIỆN MỘT LỖ HỔNG NGHIÊM TRỌNG.
#
# `backtest()` dùng đủ 27 chân (Sharpe 3,313 · +22,3%/năm ở 3,7x). Nhưng
# `live_targets()` trước hôm nay chỉ phát ra mục tiêu của BA chân: hai chân D1 qua
# `pair_weights` và chân `cross_h1` qua `cross_decisions`. Hai chân xếp hạng còn lại
# chỉ được GHI LOG, và 22 chân dưới đây thì không có gì gọi tới — dù mỗi chân đều đã
# có sẵn `live_decision()` và `registry.PORTFOLIO["entry_points"]` khai đủ 27 đường.
#
# Hậu quả nếu không sửa: mọi con số báo cáo mô tả một danh mục mà đường live KHÔNG
# dựng được. Đó là dạng sai tệ nhất — không có exception, không có test đỏ, chỉ có
# một hệ chạy khác hẳn hệ đã kiểm định.
#
# Đường import lấy từ registry chứ không hardcode ở đây: registry là SSOT cho câu
# hỏi "chân này vào lệnh bằng hàm nào".
SINGLE_LEGS: Dict[str, str] = {
    "zb_audcad_h1": "ZBandAUDCADH1", "zb_audcad_m30": "ZBandAUDCADM30",
    "zb_audcad_h4": "ZBandAUDCADH4",
    "zb_gbpaud_h1": "ZBandGBPAUDH1", "zb_gbpaud_m30": "ZBandGBPAUDM30",
    "zb_gbpaud_h4": "ZBandGBPAUDH4",
    "zb_nzdcad_h1": "ZBandNZDCADH1", "zb_nzdcad_m30": "ZBandNZDCADM30",
    "zb_gbpnzd_h4": "ZBandGBPNZDH4",
    "zb_eurchf_h1": "ZBandEURCHFH1", "zb_gbpusd_h1": "ZBandGBPUSDH1",
    "zb_eurgbp_h1": "ZBandEURGBPH1",
    "rsidiv_nzdcad_h1": "RsiDivNZDCADH1", "rsidiv_nzdcad_m30": "RsiDivNZDCADM30",
    "rsidiv_gbpnzd_m30": "RsiDivGBPNZDM30",
    "streak_gbpcad_h1": "StreakGBPCADH1", "streak_gbpaud_h1": "StreakGBPAUDH1",
    "streak_audcad_m30": "StreakAUDCADM30",
    "volreg_gbpaud_h1": "VolRegimeGBPAUDH1", "volreg_gbpchf_m30": "VolRegimeGBPCHFM30",
    "volreg_audchf_m30": "VolRegimeAUDCHFM30",
    "accel_gbpnzd_h1": "AccelGBPNZDH1",
}

FORM_END = pd.Timestamp("2024-01-01")
PORTFOLIO_NAME = "TwentySevenLegFX"


@dataclass
class PortfolioResult:
    """Kết quả danh mục, trong HAI đơn vị — đừng lẫn chúng.

    `net`      — chuỗi CHUẨN HOÁ. Đơn vị là "số lần σ_FORM của từng chân". Dùng để
                 đọc Sharpe/Calmar/tương quan (bất biến theo đòn bẩy). **KHÔNG** quy
                 sang % equity bằng cách nhân hằng số — đó là lỗi đơn vị.
    `net_bps`  — chuỗi bps THẬT ở đòn bẩy 1,0, tức mỗi chân nhận đúng 1/3 vốn danh
                 mục. Đây là chuỗi duy nhất dùng được cho sizing và mô phỏng FTMO.

    Hai chuỗi khác nhau vì ba chân có biến động rất lệch nhau ở đòn bẩy 1,0:
        reversal 4,45%/năm · carry 4,27%/năm · cross_h1 **22,46%/năm**
    Bản chuẩn hoá cho mỗi chân đóng góp rủi ro bằng nhau (đúng tinh thần chia đều
    của Olszweski & Zhou); bản `net_bps` là những gì thật sự xảy ra trên tài khoản
    nếu chia vốn đều mà không chuẩn hoá.
    """
    net: pd.Series                              # đã chuẩn hoá (σ đơn vị)
    net_bps: pd.Series                          # bps thật, đòn bẩy 1,0
    legs: Dict[str, pd.Series] = field(default_factory=dict)
    legs_normalised: Dict[str, pd.Series] = field(default_factory=dict)
    leg_vol: Dict[str, float] = field(default_factory=dict)
    leg_scale: Dict[str, float] = field(default_factory=dict)

    def risk_parity_bps(self, target_vol_pct_annual: float = 8.0) -> pd.Series:
        """Chuỗi bps thật khi mỗi chân góp rủi ro BẰNG NHAU, biến động danh mục
        đưa về `target_vol_pct_annual`.

        Đây là cách gộp đúng cho vận hành: nó vừa giữ tính chia-đều-rủi-ro (nên
        cross_h1 không áp đảo) vừa cho ra đơn vị % equity dùng được cho FTMO.
        """
        sd = float(self.net.std(ddof=1))
        if sd <= 0:
            return self.net * 0.0
        # net (σ đơn vị) -> bps: nhân với biến động ngày mục tiêu tính bằng bps
        target_daily_bps = target_vol_pct_annual * 100.0 / np.sqrt(252)
        return self.net / sd * target_daily_bps


def _leg_series(start: str = "2020-01-01",
                broker_markup_pct: float = 1.0) -> Dict[str, pd.Series]:
    """Chuỗi lợi nhuận ròng theo ngày của từng chân, đơn vị bps, đòn bẩy 1,0.

    Mọi index được ép về `datetime64[ns]` đã chuẩn hoá về ngày: các chân trả về đơn
    vị thời gian khác nhau (`[ms]` từ panel, `[ns]` từ `entry_time` của chân H1), và
    ghép index lệch đơn vị làm pandas đổi đơn vị rồi TRÀN BIÊN datetime.
    """
    from src.python.strategies.d1 import cross_momentum as CM
    from src.python.strategies.h4 import cross_xs_reversion as XXS

    def _day(s: pd.Series) -> pd.Series:
        s = s.copy()
        s.index = pd.DatetimeIndex(s.index).as_unit("ns").normalize()
        return s.groupby(s.index).sum()

    rev = CR.backtest(start=start, broker_markup_pct=broker_markup_pct).net
    car = CY.backtest(start=start, broker_markup_pct=broker_markup_pct).net
    xh1 = XMR.daily_pnl(XMR.backtest(cfg=XMR.Config(
        broker_markup_pct=broker_markup_pct), start=start))
    mom = CM.daily_pnl(CM.Config(broker_markup_pct=broker_markup_pct), start)
    xxs = XXS.daily_pnl(XXS.Config(broker_markup_pct=broker_markup_pct), start)
    from src.python.strategies.h1 import (zband_audcad as ZA_H1,
                                          zband_nzdcad as ZN_H1,
                                          zband_gbpaud as ZG_H1)
    from src.python.strategies.m30 import (zband_gbpaud as ZG_M30,
                                           zband_audcad as ZA_M30,
                                           zband_nzdcad as ZN_M30)
    from src.python.strategies.h4 import (zband_gbpnzd as ZP_H4,
                                          zband_audcad as ZA_H4,
                                          zband_gbpaud as ZG_H4)
    from src.python.strategies.h1 import (zband_eurchf as ZC_H1,
                                          zband_gbpusd as ZU_H1,
                                          zband_eurgbp as ZE_H1,
                                          rsi_div_nzdcad as RD_H1,
                                          streak_gbpcad as SC_H1,
                                          streak_gbpaud as SA_H1,
                                          vol_regime_gbpaud as VR_H1)
    zb = {f"zb_{n}": m.daily_pnl(start, broker_markup_pct=broker_markup_pct)
          for n, m in (("audcad_h1", ZA_H1), ("nzdcad_h1", ZN_H1),
                       ("gbpaud_h1", ZG_H1), ("gbpaud_m30", ZG_M30),
                       ("audcad_m30", ZA_M30), ("nzdcad_m30", ZN_M30),
                       ("gbpnzd_h4", ZP_H4), ("audcad_h4", ZA_H4),
                       ("gbpaud_h4", ZG_H4),
                       ("eurchf_h1", ZC_H1), ("gbpusd_h1", ZU_H1),
                       ("eurgbp_h1", ZE_H1))}
    zb.update({f"{n}": m.daily_pnl(start, broker_markup_pct=broker_markup_pct)
               for n, m in (("rsidiv_nzdcad_h1", RD_H1),
                            ("streak_gbpcad_h1", SC_H1),
                            ("streak_gbpaud_h1", SA_H1),
                            ("volreg_gbpaud_h1", VR_H1))})
    from src.python.strategies.h1 import accel_gbpnzd as AG_H1
    from src.python.strategies.m30 import (rsi_div_gbpnzd as RG_M, streak_audcad as SU_M,
                                           vol_regime_gbpchf as VC_M,
                                           vol_regime_audchf as VA_M,
                                           rsi_div_nzdcad as RN_M)
    zb.update({n: m.daily_pnl(start, broker_markup_pct=broker_markup_pct)
               for n, m in (("accel_gbpnzd_h1", AG_H1), ("rsidiv_gbpnzd_m30", RG_M),
                            ("streak_audcad_m30", SU_M), ("volreg_gbpchf_m30", VC_M),
                            ("volreg_audchf_m30", VA_M), ("rsidiv_nzdcad_m30", RN_M))})
    return {k: _day(v) for k, v in ({"reversal": rev, "carry": car,
                                     "cross_h1": xh1, "cross_mom": mom,
                                     "cross_xs_h4": xxs, **zb}).items()}


def backtest(start: str = "2020-01-01", *,
             broker_markup_pct: float = 1.0,
             weights: Optional[Dict[str, float]] = None,
             vol_window_end: pd.Timestamp = FORM_END) -> PortfolioResult:
    """Danh mục ba chân. Biến động chuẩn hoá ước lượng trên FORM, không dùng OOS.

    `vol_window_end` là điểm quan trọng về tính trung thực: nếu chuẩn hoá bằng độ
    lệch chuẩn TOÀN MẪU thì tỷ trọng đã dùng thông tin của giai đoạn OOS, và Sharpe
    OOS báo cáo ra sẽ cao hơn thực tế đạt được. Ước lượng trên FORM là điều một
    người vận hành thật sự làm được vào đầu giai đoạn OOS.
    """
    w = weights or LEG_WEIGHTS
    legs = _leg_series(start=start, broker_markup_pct=broker_markup_pct)
    idx = None
    for s in legs.values():
        idx = s.index if idx is None else idx.union(s.index)
    legs = {k: v.reindex(idx).fillna(0.0) for k, v in legs.items()}

    vol, norm = {}, {}
    for k, s in legs.items():
        form = s[s.index < vol_window_end]
        sd = float(form.std(ddof=1)) if len(form) > 30 else float(s.std(ddof=1))
        vol[k] = sd
        norm[k] = s / sd if sd > 0 else s * 0.0

    net = sum(w.get(k, 0.0) * v for k, v in norm.items())
    net_bps = sum(w.get(k, 0.0) * v for k, v in legs.items())
    scale = {k: (round(1.0 / v, 5) if v > 0 else 0.0) for k, v in vol.items()}
    return PortfolioResult(net=net.dropna(), net_bps=net_bps.dropna(), legs=legs,
                           legs_normalised=norm, leg_vol=vol, leg_scale=scale)


def stats(pnl: pd.Series, label: str = "") -> Dict[str, object]:
    """Chỉ số của chuỗi ĐÃ CHUẨN HOÁ — đơn vị là "độ lệch chuẩn ngày", không phải bps.

    Sharpe/Calmar bất biến theo đòn bẩy nên đọc được trực tiếp; lợi nhuận tuyệt đối
    thì phải qua `execution/portfolio_sizing.py` mới có nghĩa.
    """
    if len(pnl) < 30:
        return {"label": label, "n": len(pnl)}
    cum = pnl.cumsum()
    dd = cum.cummax() - cum
    sd = float(pnl.std(ddof=1))
    down = float(pnl[pnl < 0].std(ddof=1)) if (pnl < 0).any() else np.nan
    mdd = float(dd.max())
    return {
        "label": label, "n_days": len(pnl),
        "sharpe": round(float(pnl.mean()) / sd * np.sqrt(252), 3) if sd > 0 else np.nan,
        "sortino": round(float(pnl.mean()) / down * np.sqrt(252), 3) if down and down > 0 else np.nan,
        "max_dd_sd": round(mdd, 2),
        "calmar": round(float(pnl.mean()) * 252 / mdd, 3) if mdd > 0 else np.nan,
        "hit_rate": round(float((pnl > 0).mean()), 3),
        "worst_day_sd": round(float(pnl.min()), 2),
    }


def correlation_matrix(res: PortfolioResult) -> pd.DataFrame:
    """Tương quan giữa các chân — điều kiện để đa dạng hoá có tác dụng.

    Theo dõi ở live: nếu tương quan tăng lên đáng kể thì lợi ích đa dạng hoá đang
    biến mất, và đó là cảnh báo sớm hơn nhiều so với việc chờ Sharpe tụt.
    """
    return pd.DataFrame(res.legs).corr().round(3)


# ═════════════════════════════════════════════════════════ giao diện LIVE
@dataclass
class PortfolioTargets:
    """Mục tiêu của cả danh mục cho phiên hiện tại."""
    asof: str
    pair_weights: pd.Series                 # 7 cặp USD, từ hai chân D1
    cross_decisions: List[object]           # EntryDecision của 20 cross
    leg_scale: Dict[str, float]             # hệ số chuẩn hoá đang dùng
    regime: str
    # THÊM 14/08/2026 — ba trường dưới đây là phần còn thiếu của đường live. Trước
    # đó `live_targets()` chỉ phát ra ba chân đầu tiên, trong khi `backtest()` dùng
    # cả 27; xem chú thích ở `SINGLE_LEGS`.
    single_decisions: Dict[str, object] = field(default_factory=dict)
    rank_weights: Dict[str, pd.Series] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)


def live_targets(start: str = "2020-01-01", *,
                 broker_markup_pct: float = 1.0,
                 bars_held: Optional[Dict[str, int]] = None,
                 log: bool = True) -> PortfolioTargets:
    """Mục tiêu của CẢ 27 CHÂN cho phiên hiện tại + ghi sổ quyết định.

    Bốn loại mục tiêu, vì bốn họ chân giao dịch bốn kiểu công cụ khác nhau:
      * `pair_weights`     — tỷ trọng 7 cặp USD, hai chân D1 đã gộp sẵn
      * `cross_decisions`  — vào/ra từng cross, chân CrossMeanReversion H1
      * `rank_weights`     — tỷ trọng cross của hai chân XẾP HẠNG (mom · xs_h4)
      * `single_decisions` — quyết định của 22 chân MỘT công cụ

    Gọi `target_weights()` trên kết quả để ra vector tỷ trọng RÒNG theo công cụ —
    đó mới là thứ đưa vào `execution/portfolio_sizing.size_portfolio()`.

    `bars_held` = số nến đã giữ vị thế của từng chân, đọc từ tài khoản THẬT. Thiếu
    nó thì mọi chân bị coi như đang trống, và chân đang giữ lệnh sẽ trả `HOLD` mà
    không ai biết chiều — xem `_side_of()`.

    `log=True` ghi MỌI quyết định vào `logs/decisions/` — kể cả HOLD/SKIP, vì câu
    hỏi vận hành hay gặp nhất là "vì sao hôm nay không có lệnh nào".
    """
    notes: List[str] = []

    # ── hai chân D1: gộp tỷ trọng trước khi tính chi phí (Burnside)
    _, _, W = CY.combined(start=start, weight_reversal=0.5,
                          broker_markup_pct=broker_markup_pct)
    P = CR.pair_weights(W)
    F, _ = CR.currency_returns(start=start)
    crisis = bool(CR.regime_is_crisis(F, CR.Config()).iloc[-1])
    regime = "CRISIS (hai chân D1 đứng ngoài)" if crisis else "CALM"

    # ── chân H1: quyết định trên từng cross
    cfg = XMR.Config(broker_markup_pct=broker_markup_pct)
    decisions = XMR.live_decisions(cfg=cfg, start=start)

    res = backtest(start=start, broker_markup_pct=broker_markup_pct)
    scale = res.leg_scale

    if log:
        # Chân H1 — bản ghi riêng vì nó có trạng thái `was_outside_band` theo cross
        DLOG.record_many(decisions, strategy="CrossMeanReversion_H1",
                         extra={"portfolio": PORTFOLIO_NAME, "regime": regime})
        # BỐN chân XẾP HẠNG — bản ghi QUY TẮC đầy đủ cho TỪNG công cụ, kể cả công cụ
        # KHÔNG được chọn. Trước đây bốn chân này chỉ có một dòng tổng hợp, và dòng
        # đó không tái lập được quyết định (thiếu tín hiệu, thứ hạng, ngưỡng cắt).
        from src.python.strategies.d1 import cross_momentum as CM
        from src.python.strategies.h4 import cross_xs_reversion as XXS
        for mod, nm in ((CR, "CurrencyReversal"), (CY, "CurrencyCarry"),
                        (CM, "CrossMomentum"), (XXS, "CrossXsReversion")):
            try:
                tr = mod.explain_decisions(start=start)
                DLOG.record_many([x.to_row() for x in tr], strategy=nm,
                                 extra={"portfolio": PORTFOLIO_NAME})
                notes.append(f"{nm}: ghi {len(tr)} bản ghi quy tắc")
            except Exception as exc:      # pragma: no cover
                notes.append(f"{nm}: KHÔNG ghi được log quy tắc — {exc}")

    # ── HAI CHÂN XẾP HẠNG: lấy TỶ TRỌNG, không chỉ ghi log
    # Trước 14/08/2026 hai chân này chỉ được `explain_decisions()` ghi vào sổ quyết
    # định rồi thôi — có bản ghi nhưng không có mục tiêu, nên chúng không bao giờ ra
    # lệnh. Đây là hai trong 24 chân bị bỏ sót.
    from src.python.strategies.d1 import cross_momentum as CM
    from src.python.strategies.h4 import cross_xs_reversion as XXS

    rank_weights: Dict[str, pd.Series] = {}
    for leg, mod, cfg_cls in (("cross_mom", CM, CM.Config),
                              ("cross_xs_h4", XXS, XXS.Config)):
        try:
            rank_weights[leg] = mod.live_targets(
                cfg_cls(broker_markup_pct=broker_markup_pct), start)
        except Exception as exc:                       # pragma: no cover
            notes.append(f"{leg}: KHÔNG lấy được tỷ trọng — {exc}")

    # ── 22 CHÂN MỘT CÔNG CỤ
    single = single_leg_decisions(start, bars_held=bars_held)
    n_err = sum(1 for v in single.values() if isinstance(v, Exception))
    n_open = sum(1 for v in single.values()
                 if not isinstance(v, Exception)
                 and str(getattr(v, "action", "")) in ("BUY", "SELL"))
    notes.append(f"22 chân đơn lẻ: {n_open} có tín hiệu vào lệnh"
                 + (f" · {n_err} chân LỖI không đọc được" if n_err else ""))
    if log:
        rows = [d.to_row() for d in single.values() if not isinstance(d, Exception)]
        if rows:
            DLOG.record_many(rows, strategy="SingleInstrumentLegs",
                             extra={"portfolio": PORTFOLIO_NAME, "regime": regime})

    # ── CỔNG TIN VĨ MÔ — MẶC ĐỊNH TẮT, xem `ai/news_guard` phần đầu docstring.
    # Đo được ở vòng 63: chặn ngày tin làm Sharpe trung vị 0,811 → 0,622 vì cross
    # không chứa USD phản ứng thái quá với tin Mỹ rồi HỒI VỀ — đó chính là edge.
    # Gọi vẫn giữ ở đây để khi bật (NEWS_GUARD=1) thì đường code đã sẵn và đã test.
    from src.python.ai import news_guard as NG
    guard = NG.decide(instruments=list(P.index))
    if guard.blocked:
        notes.append(f"CỔNG TIN CHẶN: {guard.reason}")
        blocked_legs = [s for s in P.index if guard.blocks_instrument(str(s))]
        if blocked_legs:
            P.loc[P.index[-1], blocked_legs] = 0.0
            notes.append(f"  → không mở lệnh mới trên: {', '.join(map(str, blocked_legs))}")
        decisions = [d for d in decisions
                     if not guard.blocks_instrument(str(getattr(d, "cross", "")))]
    if log:
        DLOG.record_many([guard.to_row()], strategy="NewsGuard",
                         extra={"portfolio": PORTFOLIO_NAME})

    n_act = sum(1 for d in decisions if getattr(d, "action", "") in ("BUY", "SELL"))
    notes.append(f"{n_act}/{len(decisions)} cross có tín hiệu vào lệnh")
    if crisis:
        notes.append("cổng chế độ ĐANG CHẶN hai chân D1 — chỉ chân H1 hoạt động")

    return PortfolioTargets(
        asof=str(W.index[-1].date()), pair_weights=P.iloc[-1],
        cross_decisions=decisions, leg_scale=scale, regime=regime,
        single_decisions=single, rank_weights=rank_weights, notes=notes)


# ═══════════════════════════════════════════════════════════════════════════════
# TỪ QUYẾT ĐỊNH CỦA 27 CHÂN → MỘT VECTOR TỶ TRỌNG THEO CÔNG CỤ
# ═══════════════════════════════════════════════════════════════════════════════
def single_leg_decisions(start: str = "2020-01-01", *,
                         bars_held: Optional[Dict[str, int]] = None
                         ) -> Dict[str, object]:
    """Gọi `live_decision()` của 22 chân MỘT công cụ. Trả {khoá chân: EntryDecision}.

    `bars_held` là số nến đã giữ vị thế của từng chân, đọc từ trạng thái THẬT của tài
    khoản. Không truyền thì coi như đang không có vị thế nào — đúng cho lần chạy đầu,
    SAI cho mọi lần sau, nên bên gọi phải truyền.

    Đường import lấy từ `registry.PORTFOLIO["entry_points"]`: registry là SSOT cho câu
    hỏi "chân này vào lệnh bằng hàm nào", và nhờ vậy thêm chân mới chỉ phải sửa một chỗ.
    """
    from importlib import import_module

    from src.python.strategies import registry as REG

    held = bars_held or {}
    out: Dict[str, object] = {}
    for leg, name in SINGLE_LEGS.items():
        target = REG.PORTFOLIO["entry_points"][name]
        mod_path, _, fn = target.partition(":")
        try:
            out[leg] = getattr(import_module(mod_path), fn)(
                start=start, bars_held=int(held.get(leg, 0)))
        except Exception as exc:                       # pragma: no cover
            # Fail-closed: chân nào không đọc được thì KHÔNG có mục tiêu, không phải
            # "giữ nguyên vị thế cũ". Im lặng bỏ qua ở tầng này là cách một chân chết
            # âm thầm mà danh mục vẫn báo đủ 27.
            out[leg] = exc
    return out


def _side_of(decision: object, previous: int = 0) -> int:
    """Chiều mục tiêu từ một `EntryDecision`: +1 mua · −1 bán · 0 đứng ngoài.

    `HOLD` nghĩa là "giữ nguyên cái đang có" — bản thân quyết định KHÔNG mang chiều,
    nên phải lấy từ vị thế hiện tại. Suy đoán chiều ở đây là cách tạo ra lệnh đảo
    chiều không ai yêu cầu.
    """
    action = str(getattr(decision, "action", "")).upper()
    if action == "BUY":
        return 1
    if action == "SELL":
        return -1
    if action == "HOLD":
        return int(previous)
    return 0


def target_weights(targets: "PortfolioTargets", *,
                   positions: Optional[Dict[str, int]] = None) -> pd.Series:
    """Tỷ trọng RÒNG theo CÔNG CỤ của cả 27 chân — đầu vào của `size_portfolio()`.

    HAI VIỆC, VÀ CẢ HAI ĐỀU BẮT BUỘC
    =================================
    1. GỘP đủ 27 chân. Trước 14/08/2026 hàm này không tồn tại và `live_targets()`
       chỉ phát ra ba chân, trong khi `backtest()` dùng cả 27 — tức mọi con số công
       bố mô tả một danh mục mà đường live không dựng được.
    2. TRIỆT TIÊU chân ngược chiều TRƯỚC khi gửi lệnh. Hai chân cùng công cụ ngược
       chiều nhau mà gửi cả hai thì trả HAI lần spread cho một phơi nhiễm ròng bằng
       không. Burnside et al. (NBER w16942) mô tả đúng cơ chế: "khi hai chiến lược
       BẤT ĐỒNG, vị thế ròng cho đồng tiền đó là ZERO". Đo được ở hai chân D1 của
       chính hệ này: gộp trước khi tính phí tiết kiệm +0,595%/năm.

    Tỷ trọng mỗi chân = `LEG_WEIGHTS[chân] × leg_scale[chân] × chiều`, rồi chuẩn hoá
    để tổng TRỊ TUYỆT ĐỐI bằng 1,0. `leg_scale` là 1/σ_FORM — cùng hệ số mà
    `backtest()` dùng, nên tỷ trọng live và tỷ trọng backtest là một.

    `positions` = chiều đang giữ của từng chân (+1/−1/0), cần cho chân trả `HOLD`.
    """
    scale = targets.leg_scale
    pos = positions or {}
    raw: Dict[str, float] = {}

    def add(instrument: str, leg: str, signed: float) -> None:
        if abs(signed) < 1e-12:
            return
        k = LEG_WEIGHTS.get(leg, 0.0) * scale.get(leg, 0.0)
        raw[instrument] = raw.get(instrument, 0.0) + signed * k

    # ── hai chân D1: đã gộp sẵn thành tỷ trọng trên 7 cặp USD
    for sym, w in targets.pair_weights.items():
        add(str(sym), "reversal", float(w) * 0.5)
        add(str(sym), "carry", float(w) * 0.5)

    # ── chân CrossMeanReversion H1: quyết định trên từng cross
    for d in targets.cross_decisions:
        name = str(getattr(d, "cross", "") or getattr(d, "instrument", ""))
        if name:
            add(name, "cross_h1", float(_side_of(d, pos.get(f"cross_h1:{name}", 0))))

    # ── hai chân xếp hạng: tỷ trọng đã chuẩn hoá sẵn trong chính chân
    for leg, series in (("cross_mom", targets.rank_weights.get("cross_mom")),
                        ("cross_xs_h4", targets.rank_weights.get("cross_xs_h4"))):
        if series is None:
            continue
        for sym, w in series.items():
            add(str(sym), leg, float(w))

    # ── 22 chân một công cụ
    for leg, d in targets.single_decisions.items():
        if isinstance(d, Exception):
            continue
        name = str(getattr(d, "instrument", ""))
        if name:
            add(name, leg, float(_side_of(d, pos.get(leg, 0))))

    s = pd.Series(raw, dtype=float).sort_index()
    gross = float(s.abs().sum())
    return (s / gross).round(6) if gross > 0 else s


def netting_report(targets: "PortfolioTargets",
                   positions: Optional[Dict[str, int]] = None) -> pd.DataFrame:
    """Trước/sau triệt tiêu, theo công cụ — để thấy phí đã tiết kiệm được bao nhiêu.

    `gross_legs` là tổng trị tuyệt đối đóng góp của từng chân lên công cụ đó;
    `net` là phần thực sự phải gửi lệnh. Chênh lệch chính là phần KHÔNG phải trả phí.
    """
    scale = targets.leg_scale
    pos = positions or {}
    rows: Dict[str, Dict[str, float]] = {}

    def bump(instrument: str, leg: str, signed: float) -> None:
        if abs(signed) < 1e-12:
            return
        k = LEG_WEIGHTS.get(leg, 0.0) * scale.get(leg, 0.0)
        r = rows.setdefault(instrument, {"gross_legs": 0.0, "net": 0.0, "n_legs": 0.0})
        r["gross_legs"] += abs(signed * k)
        r["net"] += signed * k
        r["n_legs"] += 1.0

    for sym, w in targets.pair_weights.items():
        bump(str(sym), "reversal", float(w) * 0.5)
        bump(str(sym), "carry", float(w) * 0.5)
    for d in targets.cross_decisions:
        name = str(getattr(d, "cross", "") or getattr(d, "instrument", ""))
        if name:
            bump(name, "cross_h1", float(_side_of(d, pos.get(f"cross_h1:{name}", 0))))
    for leg, series in (("cross_mom", targets.rank_weights.get("cross_mom")),
                        ("cross_xs_h4", targets.rank_weights.get("cross_xs_h4"))):
        if series is not None:
            for sym, w in series.items():
                bump(str(sym), leg, float(w))
    for leg, d in targets.single_decisions.items():
        if isinstance(d, Exception):
            continue
        name = str(getattr(d, "instrument", ""))
        if name:
            bump(name, leg, float(_side_of(d, pos.get(leg, 0))))

    df = pd.DataFrame(rows).T
    if df.empty:
        return df
    df["saved"] = df["gross_legs"] - df["net"].abs()
    return df.sort_values("saved", ascending=False).round(6)


def exposure_report(targets: PortfolioTargets) -> pd.DataFrame:
    """Phơi nhiễm tiền tệ RÒNG của cả danh mục, gồm cả phần ngầm từ cross.

    Vì sao cần: một vị thế EURGBP ngầm mang EUR long + GBP short. Không cộng phần
    đó vào thì báo cáo phơi nhiễm sẽ thiếu, và giới hạn rủi ro theo đồng tiền trở
    nên vô nghĩa. Đây là Currency Exposure Engine ở tầng danh mục.
    """
    from src.python.shared import asset_profile as AP
    expo: Dict[str, float] = {}

    for sym, w in targets.pair_weights.items():
        if abs(float(w)) < 1e-9:
            continue
        prof = AP.get(sym)
        expo[prof.base] = expo.get(prof.base, 0.0) + float(w)
        expo[prof.quote] = expo.get(prof.quote, 0.0) - float(w)

    for d in targets.cross_decisions:
        act = getattr(d, "action", "")
        if act not in ("BUY", "SELL"):
            continue
        name = getattr(d, "cross", "")
        if len(name) != 6:
            continue
        sgn = 1.0 if act == "BUY" else -1.0
        expo[name[:3]] = expo.get(name[:3], 0.0) + sgn
        expo[name[3:]] = expo.get(name[3:], 0.0) - sgn

    df = pd.DataFrame({"net_exposure": pd.Series(expo)}).sort_values(
        "net_exposure", ascending=False)
    df["abs"] = df["net_exposure"].abs()
    return df.round(4)


def group_correlation(res: PortfolioResult) -> pd.DataFrame:
    """Tương quan ở tầng NHÓM RỦI RO — đây mới là bảng để áp ngưỡng 0,70.

    Bảng theo từng chân sẽ báo động giả ở hai chân cùng công cụ khác khung: chúng
    ĐƯỢC PHÉP tương quan cao vì đã gộp lại thành một suất, và điều cần kiểm là các
    NHÓM có độc lập với nhau không.
    """
    cols = {}
    for g, legs in RISK_GROUPS.items():
        s = None
        for lg in legs:
            v = res.legs_normalised.get(lg)
            if v is None:
                continue
            s = v.copy() if s is None else s.add(v, fill_value=0.0)
        if s is not None:
            cols[g] = s / max(len(legs), 1)
    return pd.DataFrame(cols).fillna(0.0).corr()
