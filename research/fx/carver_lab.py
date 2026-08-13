"""Vòng 53 — KHUNG DỰ BÁO LIÊN TỤC của Carver, đo ở M30 và H1.

VÌ SAO ĐÂY LÀ CƠ CHẾ MỚI, KHÔNG PHẢI HỌ TÍN HIỆU MỚI
=====================================================
52 vòng trước đều dùng vị thế NHỊ PHÂN: vào ±1, ra 0. Với cơ chế đó, mỗi lần tín hiệu
đổi dấu là một lượt khứ hồi đầy đủ — và đó chính là thứ đã giết mọi thử nghiệm nội
ngày. Đo được nhiều lần: gross 0,03-0,16 bps/nến so với chi phí 1,2-1,6 bps mỗi lượt.

Carver (`project-refer/carver-systematic-trading`, core/forecast.py) dùng cơ chế khác:

    dự báo THÔ      = EWMAC(nhanh) − EWMAC(chậm), chia cho σ giá
    dự báo CHUẨN    = thô × scalar sao cho trung bình |dự báo| ≈ 10
    dự báo CẮT      = kẹp trong [−20, +20]
    vị thế          = dự báo / 10 × (mục tiêu biến động / σ công cụ)
    BUFFER          = vùng chết 10% — không điều chỉnh nếu lệch dưới ngưỡng

Ba hệ quả về CHI PHÍ, không phải về tín hiệu:
  1. tín hiệu yếu đi → vị thế NHỎ đi, không phải thoát hẳn. Không có lượt khứ hồi.
  2. cap ±20 chặn vị thế phình ra ở đuôi — nơi chi phí trượt giá lớn nhất
  3. buffer 10% nuốt phần dao động nhỏ của dự báo, thứ sinh ra phần lớn vòng quay

Nên câu hỏi của vòng này KHÔNG phải "EWMAC có tín hiệu trên FX không" (đã biết là
yếu), mà là: **với cùng tín hiệu yếu đó, cơ chế vị thế liên tục có kéo được chi phí
xuống dưới gross không.** Đó là một câu hỏi khác, và nó chưa từng được đo.

BẢY HỌ QUY TẮC — tham số lấy NGUYÊN của Carver, không tinh chỉnh
================================================================
    EWMAC        6 tốc độ (2,8) (4,16) (8,32) (16,64) (32,128) (64,256)
    BREAKOUT     6 cửa sổ 10 20 40 80 160 320 — vị trí trong kênh min/max
    MEANREV      dự báo NGƯỢC dấu EWMAC nhanh — cùng cơ chế, ngược chiều
    ACCEL        đạo hàm của EWMAC: đà đang TĂNG hay đang chậm lại
    RELMOM       lợi nhuận công cụ TRỪ trung bình rổ — đã trung hoà nhân tố chung
    SKEW         độ lệch của phân phối lợi nhuận, đảo dấu (Carver Ch. 25)
    RELVOL       biến động ngắn hạn so với dài hạn — cược vào chế độ

SCALAR PHẢI HIỆU CHUẨN LẠI, KHÔNG DÙNG SỐ CỦA CARVER
=====================================================
Scalar của ông ấy hiệu chuẩn trên hợp đồng tương lai khung NGÀY. Ở M30/H1 trên FX, độ
lớn dự báo thô khác hẳn. Nên scalar được tính LẠI trên dữ liệu này — nhưng CHỈ trên
cửa sổ FORM (đến 2024-01-01). Hiệu chuẩn trên toàn mẫu là dùng thông tin OOS để chuẩn
hoá độ lớn vị thế, và Sharpe OOS báo ra sẽ cao hơn mức thực đạt được.
"""
from __future__ import annotations

import io
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

import numpy as np
import pandas as pd

from src.python.research import fx_cross_lab as LAB

pd.set_option("display.width", 260, "display.max_columns", 40, "display.max_rows", 300)
FORM_END = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports" / "fx_research"

FORECAST_CAP = 20.0          # Carver Ch. 15 — cắt cứng, không tinh chỉnh
FORECAST_TARGET = 10.0       # trung bình |dự báo| mục tiêu
BUFFER_FRACTION = 0.10       # vùng chết, Carver Ch. 11
VOL_SPAN_BARS = {"M30": 36 * 48, "H1": 36 * 24, "H4": 36 * 6, "D1": 36}

EWMAC_SPEEDS: Tuple[Tuple[int, int], ...] = (
    (2, 8), (4, 16), (8, 32), (16, 64), (32, 128), (64, 256))
BREAKOUT_WINDOWS: Tuple[int, ...] = (10, 20, 40, 80, 160, 320)


# ═══════════════════════════════════════════════════════ dự báo thô
def _vol(logp: pd.DataFrame, span: int) -> pd.DataFrame:
    """σ của lợi nhuận log, làm mượt hàm mũ. Đơn vị: cùng đơn vị lợi nhuận log."""
    return logp.diff().ewm(span=span, min_periods=span // 4).std()


def raw_ewmac(logp: pd.DataFrame, fast: int, slow: int, vol: pd.DataFrame
              ) -> pd.DataFrame:
    """EWMAC thô đã chuẩn hoá theo biến động — công thức Carver core/forecast.py."""
    ema_f = logp.ewm(span=fast, min_periods=fast).mean()
    ema_s = logp.ewm(span=slow, min_periods=slow).mean()
    return (ema_f - ema_s) / vol.replace(0, np.nan)


def raw_breakout(logp: pd.DataFrame, window: int) -> pd.DataFrame:
    """Vị trí trong kênh min/max, ánh xạ về [−1, +1] rồi làm mượt.

    Carver làm mượt bằng EWMA span = window/4: kênh thô nhảy bậc mỗi khi giá chạm
    biên, và bậc nhảy đó là vòng quay thuần tuý, không phải thông tin.
    """
    hi = logp.rolling(window, min_periods=window // 2).max()
    lo = logp.rolling(window, min_periods=window // 2).min()
    mid = (hi + lo) / 2.0
    rng = (hi - lo).replace(0, np.nan)
    return ((logp - mid) / rng).ewm(span=max(window // 4, 2), min_periods=2).mean()


def raw_accel(logp: pd.DataFrame, fast: int, slow: int, vol: pd.DataFrame
              ) -> pd.DataFrame:
    """Gia tốc = biến thiên của EWMAC. Đà đang MẠNH LÊN hay đang chậm lại."""
    e = raw_ewmac(logp, fast, slow, vol)
    return e - e.shift(slow)


def raw_relmom(logp: pd.DataFrame, window: int, vol: pd.DataFrame) -> pd.DataFrame:
    """Momentum TƯƠNG ĐỐI: lợi nhuận công cụ trừ trung bình rổ.

    Trừ trung bình rổ khử nhân tố chung (với cross là "khẩu vị rủi ro toàn cầu"), nên
    phần còn lại là thứ riêng của công cụ đó.
    """
    r = logp - logp.shift(window)
    return (r.sub(r.mean(axis=1), axis=0)) / (vol.replace(0, np.nan) * np.sqrt(window))


def raw_skew(logp: pd.DataFrame, window: int) -> pd.DataFrame:
    """Độ lệch phân phối lợi nhuận, ĐẢO DẤU (Carver Ch. 25).

    Công cụ có skew ÂM được trả phần bù rủi ro (nó thỉnh thoảng sụp), nên mua nó.
    Dấu trừ ở đây là luật của ông ấy, không phải kết quả tinh chỉnh.
    """
    return -logp.diff().rolling(window, min_periods=window // 2).skew()


def raw_relvol(logp: pd.DataFrame, short: int, long_: int) -> pd.DataFrame:
    """Biến động ngắn hạn so với dài hạn, đảo dấu — biến động cao thì giảm vị thế."""
    v_s = logp.diff().rolling(short, min_periods=short // 2).std()
    v_l = logp.diff().rolling(long_, min_periods=long_ // 2).std()
    return -(v_s / v_l.replace(0, np.nan) - 1.0)


# ═══════════════════════════════════════════════════════ chuẩn hoá + cắt
def scale_and_cap(raw: pd.DataFrame, form_end: pd.Timestamp = FORM_END
                  ) -> pd.DataFrame:
    """Nhân scalar để trung bình |dự báo| ≈ 10, rồi cắt ở ±20.

    Scalar tính TRÊN CỬA SỔ FORM và áp cho cả mẫu — hiệu chuẩn trên toàn mẫu là dùng
    thông tin OOS để chuẩn hoá độ lớn vị thế, và Sharpe OOS sẽ cao hơn thực tế.
    """
    form = raw[raw.index < form_end]
    mad = float(form.abs().stack().median()) if len(form) else np.nan
    if not np.isfinite(mad) or mad <= 0:
        mad = float(raw.abs().stack().median())
    if not np.isfinite(mad) or mad <= 0:
        return raw * 0.0
    scalar = FORECAST_TARGET / mad
    return (raw * scalar).clip(-FORECAST_CAP, FORECAST_CAP)


def forecast_to_position(fc: pd.DataFrame, vol: pd.DataFrame,
                         target_vol_bar: float) -> pd.DataFrame:
    """Dự báo → vị thế, chuẩn hoá theo biến động từng công cụ.

    Vị thế tỷ lệ THUẬN với dự báo và NGHỊCH với biến động: hai công cụ có cùng dự báo
    nhưng khác biến động phải mang cùng RỦI RO, không cùng notional.
    """
    scale = target_vol_bar / vol.replace(0, np.nan)
    pos = (fc / FORECAST_TARGET) * scale
    return pos.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def apply_buffer(pos: pd.DataFrame, fraction: float = BUFFER_FRACTION
                 ) -> pd.DataFrame:
    """Vùng chết Carver: chỉ điều chỉnh khi lệch quá `fraction` × vị thế cơ sở.

    Đây là nơi phần lớn tiết kiệm chi phí đến từ. Dự báo dao động liên tục quanh một
    mức; không có buffer thì mỗi dao động nhỏ là một lệnh điều chỉnh.
    """
    P = pos.to_numpy(dtype=float)
    n, m = P.shape
    base = np.nanmean(np.abs(P), axis=0)
    base = np.where(np.isfinite(base) & (base > 0), base, 1.0)
    thr = fraction * base
    out = np.zeros_like(P)
    cur = np.zeros(m)
    for i in range(n):
        want = P[i]
        move = np.abs(want - cur) > thr
        cur = np.where(move, want, cur)
        out[i] = cur
    return pd.DataFrame(out, index=pos.index, columns=pos.columns)


# ═══════════════════════════════════════════════════════ họ quy tắc
@dataclass(frozen=True)
class RuleFamily:
    name: str
    build: object              # (logp, vol, bars_per_day) -> DataFrame dự báo thô


def build_families(bars_per_day: int) -> List[RuleFamily]:
    """Bảy họ, tham số quy đổi sang số NẾN của khung đang đo."""
    fams: List[RuleFamily] = []
    for f, s in EWMAC_SPEEDS:
        fams.append(RuleFamily(
            f"ewmac_{f}_{s}",
            (lambda f_, s_: lambda lp, v, _bpd: raw_ewmac(lp, f_, s_, v))(f, s)))
    for w in BREAKOUT_WINDOWS:
        fams.append(RuleFamily(
            f"breakout_{w}",
            (lambda w_: lambda lp, v, _bpd: raw_breakout(lp, w_))(w)))
    fams.append(RuleFamily(
        "meanrev_fast", lambda lp, v, _bpd: -raw_ewmac(lp, 4, 16, v)))
    fams.append(RuleFamily(
        "meanrev_slow", lambda lp, v, _bpd: -raw_ewmac(lp, 16, 64, v)))
    fams.append(RuleFamily(
        "accel", lambda lp, v, _bpd: raw_accel(lp, 8, 32, v)))
    for d in (5, 21):
        fams.append(RuleFamily(
            f"relmom_{d}d",
            (lambda d_: lambda lp, v, bpd: raw_relmom(lp, max(d_ * bpd, 5), v))(d)))
    fams.append(RuleFamily(
        "skew", lambda lp, v, bpd: raw_skew(lp, max(63 * bpd, 60))))
    fams.append(RuleFamily(
        "relvol", lambda lp, v, bpd: raw_relvol(lp, max(5 * bpd, 10),
                                                max(63 * bpd, 60))))
    return fams


# ═══════════════════════════════════════════════════════ đo
def sharpe(s: pd.Series, lo: Optional[pd.Timestamp] = None,
           hi: Optional[pd.Timestamp] = None) -> float:
    if lo is not None:
        s = s[s.index >= lo]
    if hi is not None:
        s = s[s.index < hi]
    sd = float(s.std(ddof=1))
    return float(s.mean()) / sd * np.sqrt(252) if sd > 0 and len(s) > 60 else np.nan


def run_timeframe(tf: str, bars_per_day: int, target_vol_bar: float = 1.0
                  ) -> Tuple[pd.DataFrame, Dict[str, pd.Series]]:
    panel = LAB.build_panel(tf, start="2020-01-01")
    logp = panel.logp
    vol = _vol(logp, VOL_SPAN_BARS[tf])
    rows, series = [], {}

    for fam in build_families(bars_per_day):
        try:
            raw = fam.build(logp, vol, bars_per_day)
        except Exception as exc:                          # pragma: no cover
            print(f"    {fam.name}: LỖI {exc}")
            continue
        fc = scale_and_cap(raw)
        pos = apply_buffer(forecast_to_position(fc, vol, target_vol_bar))
        # chuẩn hoá gross exposure về 1 để so sánh công bằng giữa các họ
        gross = pos.abs().sum(axis=1).replace(0, np.nan)
        pos = pos.div(gross, axis=0).fillna(0.0)

        res = LAB.simulate_positions(panel, pos, name=fam.name)
        d = res.pnl_daily
        series[f"{tf}|{fam.name}"] = d
        rows.append({
            "tf": tf, "rule": fam.name,
            "ALL": round(sharpe(d), 3),
            "FORM": round(sharpe(d, hi=FORM_END), 3),
            "OOS": round(sharpe(d, lo=FORM_END), 3),
            "gross": round(res.gross_bps_bar, 4),
            "phi": round(res.trade_cost_bps_bar + res.carry_cost_bps_bar, 4),
            "phi%": round((res.trade_cost_bps_bar + res.carry_cost_bps_bar)
                          / max(res.gross_bps_bar, 1e-9) * 100, 1),
            "turn/năm": round(res.turnover_per_year, 1),
            "%tt": round(res.time_in_market, 3)})
    return pd.DataFrame(rows), series


def main() -> None:
    t0 = time.time()
    all_rows, all_series = [], {}
    for tf, bpd in (("H1", 24), ("M30", 48)):
        print(f"── {tf} …", flush=True)
        T, S = run_timeframe(tf, bpd)
        all_rows.append(T)
        all_series.update(S)
        print(f"   {len(T)} họ, {time.time() - t0:.0f}s", flush=True)

    T = pd.concat(all_rows, ignore_index=True)
    T.to_csv(OUT / "carver_lab.csv", index=False)

    print()
    print("=" * 130)
    print("KẾT QUẢ — cơ chế dự báo liên tục + buffer")
    print("=" * 130)
    print(T.sort_values("ALL", ascending=False).to_string(index=False))

    print()
    print("=" * 130)
    print("CỔNG: FORM>0 & OOS>0 & ALL>0,40")
    print("=" * 130)
    k = T[(T["FORM"] > 0) & (T["OOS"] > 0) & (T["ALL"] > 0.40)].sort_values(
        "ALL", ascending=False)
    print(k.to_string(index=False) if len(k) else "  KHÔNG CÓ")

    print()
    print("── SO SÁNH VÒNG QUAY với cơ chế nhị phân đã đo ở vòng 50-51")
    print(f"   nhị phân (zscore band H1): 6,6 vòng/năm · xếp hạng M30: 9,9-24,9")
    print(f"   liên tục + buffer:         {T['turn/năm'].min():.1f}-"
          f"{T['turn/năm'].max():.1f} vòng/năm  "
          f"(trung vị {T['turn/năm'].median():.1f})")
    print(f"   chi phí trên gross: trung vị {T['phi%'].median():.1f}%")

    if len(k):
        import pickle
        with open(OUT / "carver_lab_pnl.pkl", "wb") as fh:
            pickle.dump({kk: all_series[kk] for kk in
                         (f"{r.tf}|{r.rule}" for _, r in k.iterrows())}, fh)
        print(f"\n   đã lưu P&L của {len(k)} ứng viên để kiểm định vòng sau")
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
