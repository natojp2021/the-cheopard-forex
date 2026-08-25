"""asia_sweep_filters.py — Vòng 72. Lọc "setup xấu" của Asia Range Sweep. Có cứu được không?

VÌ SAO CÓ VÒNG NÀY
==================
Vòng 71 (`asia_sweep_lab.py`) đo hiện tượng THÔ và kết luận âm: biên Á bị quét ở 99,4%
phiên nhưng một mức bất kỳ cách đó 0,35 biên cũng bị quét 91,6%, và R trung bình mỗi
lệnh fade TRƯỚC chi phí là +0,10 / -0,05 / -0,04 (EURUSD/GBPUSD/USDJPY) so với control
+0,04 / +0,05 / -0,04. Chi phí thật 0,20-0,30 R.

Nhưng vòng 71 đo đúng cú chạm ĐẦU TIÊN, mà cú đó có độ sâu trung vị 1,85 pip — tức
phần lớn "cú quét" chỉ là nhiễu quanh biên. Đặc tả người dùng cung cấp KHÔNG nói thế:
nó đòi xuyên 2-25 pip, râu nến chiếm >= 50% thân, đóng lại trong biên, thuận xu hướng
H1, biên Á 15-35 pip. Vòng này đo đúng luật đó, và đo TOÀN BỘ bề mặt lọc.

BỘ LỌC ĐƯỢC ĐẶC TẢ TRƯỚC, TỪNG CÁI CÓ NGUỒN — KHÔNG QUÉT TÌM Ô ĐẸP
==================================================================
Đây là điều kiện bắt buộc của dự án (`Aronson 2007`, ch. 6): 6.402 luật quét trên
S&P 500 cho đúng 5% "có ý nghĩa" bằng test đơn luật, và KHÔNG luật nào sống sót hiệu
chỉnh data-mining. Lưới ở đây có ~6 chiều lọc x 3 cặp; nếu chọn ô tốt nhất thì con số
tìm được là rác. Nên mọi ngưỡng dưới đây được ấn định TRƯỚC khi chạy, lấy từ nguồn:

    F1  xu hướng H1     đặc tả người dùng: chỉ fade THUẬN xu hướng H1. Đo cả ba
                        nhánh (thuận / ngược / không lọc) vì 70 vòng trước của dự án
                        kết luận mọi họ THUẬN chiều đều thua trên FX.
    F2  biên Á rộng/hẹp Crabel qua Kirkpatrick & Dahlquist 2011 tr. 386 (Raschke):
                        HV6 < 50% HV100 mới đủ điều kiện nhận tín hiệu NR4. Ở đây
                        chuẩn hoá bằng biên Á / trung vị 20 phiên: hẹp < 0,80 ·
                        thường · rộng > 1,25. LƯU Ý HƯỚNG: Crabel tìm điều kiện cho
                        BREAKOUT tốt (nén), nên chiều FADE kỳ vọng ngược lại — biên
                        RỘNG mới là chỗ breakout thất bại. Đặc tả người dùng nói
                        ngược (bỏ biên > 40 pip). Đo để phân xử.
    F3  giờ quét        Osler sr150: hiệu ứng dòng lệnh điều kiện MẠNH HƠN khi thanh
                        khoản THẤP. Lien 2008 tr. 73: biên độ 08:00-12:00 EST chiếm
                        70% biên phiên Âu. Hai nguồn nói ngược nhau về cửa sổ tốt
                        nhất -> đo ba cửa sổ 07-10 / 10-13 / 13-16 UTC.
    F4  độ sâu xuyên    đặc tả: 2-25 pip (EUR) / 3-35 pip (GBP). Osler: 62% giá trị
                        lệnh stop RẤT LỚN nằm trong đuôi [90,100] và [01,09] quanh
                        mốc tròn, tức túi stop nằm trong ~10 pip.
    F5  râu / thân      đặc tả: râu >= 50% thân. Wyckoff qua Villahermosa 2019 tr.
                        209: nến "significant" phải ĐÓNG ở NỬA TRÊN (hoặc dưới) biên
                        nến — đây là ngưỡng đo được DUY NHẤT mà Wyckoff cho.
    F6  thứ trong tuần  ICT 2022 tr. 380: CBDR chính xác nhất Thứ Ba-Thứ Năm.

ĐỊNH NGHĨA CÚ QUÉT — KHÁC VÒNG 71 Ở BA ĐIỂM, VÀ CẢ BA ĐỀU CÓ LÝ DO
==================================================================
    khung M15, không M1     Osler: cửa sổ đảo chiều < 30 phút = 2 nến M15. M1 bắt
                            mọi cú poke 2 pip; H1 thì đến muộn hết cửa sổ.
    đòi ĐÓNG lại trong biên NGAY trong nến quét, không phải "một lúc nào đó sau đó".
                            ICT tr. 86-87: "phá rồi quay ngay vào range" KHÔNG phải
                            displacement — đúng cái ta cần cho chiều fade.
    đòi độ sâu tối thiểu    max(2,0 pip · 0,05 x biên Á) — bỏ nhiễu quanh biên.

Grimes 2012 tr. 183 gọi thẳng kế hoạch "đảo chiều khi mức phá vỡ không giữ" là
"a futile plan", vì xuyên lại mức là hành vi BÌNH THƯỜNG của một breakout tốt. Vòng
này vì vậy không fade theo "giá xuyên lại mức" mà theo "nến quét ĐÓNG lại trong biên"
— tiêu chí chặt hơn, và là tiêu chí Grimes gợi ý (thất bại của nhịp phản ứng đầu tiên).

BẰNG CHỨNG PHẢN BÁC PHẢI GHI TRƯỚC KHI ĐO
=========================================
Kho tài liệu của dự án nghiêng về phía NGƯỢC với hướng fade:

  · Curcio & Goodhart (1992) "When Support/Resistance Levels are Broken, Can Profits
    be Made?", LSE FMG DP No. 142. DEM/GBP/JPY vs USD, nến GIỜ, 10/04-29/06/1989.
    Lợi nhuận theo HƯỚNG PHÁ VỠ luôn dương, t = 1,27-2,85, DEM >= 5x trung bình mẫu;
    sống sót chi phí 0,03%/lượt (rộng hơn 99% spread quan sát). Và mức S/R họ dùng
    được cập nhật ĐÚNG tại giờ mở London và Tokyo — đúng biên mà ta định fade.
    D:/project-learning/documents/forex-strategies/DP142.md
  · Crabel qua Kirkpatrick & Dahlquist (2011) tr. 388: sau NR2, giá KHÔNG quay lại
    open khi đã rời đi; setup wide-range thua xa setup NR; breakout xuyên SỚM trong
    ngày có xác suất thành công CAO HƠN.
  · Chan (2013) "Algorithmic Trading" tr. 167-168 tóm lược Osler: khi S/R bị xuyên,
    giá ĐI TIẾP do cụm stop — vi cấu trúc ủng hộ momentum, không ủng hộ fade.

Cái duy nhất trong kho ủng hộ: Lien (2008) tr. 69 — "large investment banks and hedge
funds are known to try to use the Asian session to run important stop and option
barrier levels" — một lập luận cơ chế, KHÔNG kèm số. Theo `CLAUDE.md` đó là nguồn ưu
tiên 3, đang đứng đối diện một paper FX dữ liệu giờ có t-stat kết luận ngược.

Nên vòng này là cơ hội cuối của hướng fade: nếu bộ lọc đặc tả trước không tạo ra một
tập con dương SAU chi phí trên CẢ ba cặp, hướng này vào `REJECTED_DIRECTIONS`.
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

from src.python.shared import asset_profile as AP
from src.python.shared import fx_data as D
from research.fx.asia_sweep_lab import SESSION_ANCHOR_HOUR, load, m_of

pd.set_option("display.width", 260, "display.max_columns", 40,
              "display.max_rows", 500)

OUT = ROOT / "reports" / "fx_research"
PAIRS = ("EURUSD", "GBPUSD", "USDJPY")
FORM_END = pd.Timestamp("2024-01-01")

ASIA_START_UTC, ASIA_END_UTC = 0.0, 7.0
EXEC_END_UTC = 16.0          # hết cửa sổ TÌM tín hiệu
FLAT_UTC = 20.0              # đóng mọi vị thế — chiến lược TRONG phiên
SL_BUFFER_PIPS = 3.0
MIN_DEPTH_PIPS = 2.0
MIN_DEPTH_FRAC = 0.05        # và >= 5% biên Á


# ═══════════════════════════════════════════════════════════════ tiện ích
def to_m15(df: pd.DataFrame) -> pd.DataFrame:
    """M1 -> M15. `spread_usd` lấy TRUNG BÌNH: chi phí phải trả là spread lúc khớp."""
    o = df.resample("15min").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), spread_usd=("spread_usd", "mean"),
        n=("close", "size"))
    return o[o["n"] > 0].drop(columns="n")


def to_h1(df: pd.DataFrame) -> pd.DataFrame:
    o = df.resample("1h").agg(open=("open", "first"), high=("high", "max"),
                              low=("low", "min"), close=("close", "last"),
                              n=("close", "size"))
    return o[o["n"] > 0].drop(columns="n")


def session_of(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return (idx - pd.Timedelta(hours=SESSION_ANCHOR_HOUR)).normalize()


def minute_of(idx: pd.DatetimeIndex) -> np.ndarray:
    s = idx - pd.Timedelta(hours=SESSION_ANCHOR_HOUR)
    return ((s - s.normalize()).total_seconds() // 60).to_numpy().astype(np.int32)


# ═══════════════════════════════════════════════════════════════ sinh sự kiện
@dataclass
class Trade:
    session: pd.Timestamp
    t_entry: pd.Timestamp
    symbol: str
    side: int                # +1 MUA · -1 BÁN  (chiều LỆNH, đã là chiều fade)
    sweep_side: int          # +1 quét biên TRÊN · -1 biên DƯỚI
    asia_rng_pips: float
    asia_rng_rel: float      # biên Á / trung vị 20 phiên
    depth_pips: float
    depth_frac: float
    wick_body: float         # râu ngoài biên / thân nến quét
    close_pos: float         # vị trí đóng trong biên nến quét (0=đáy, 1=đỉnh)
    sweep_hour: int
    dow: int
    h1_bias: int             # +1 tăng · -1 giảm (H1 close vs EMA50 tại 07:00 UTC)
    aligned: bool            # lệnh THUẬN xu hướng H1
    sl_pips: float
    tp_pips: float
    rr: float
    cost_pips: float
    cost_r: float
    outcome: str             # TP | SL | FLAT
    r_gross: float
    r_net: float
    minutes: float


def build_trades(symbol: str, asia_start: float = ASIA_START_UTC,
                 asia_end: float = ASIA_END_UTC) -> pd.DataFrame:
    pip = AP.get(symbol).pip
    prof = AP.get(symbol)
    with D.parquet_only():
        m1 = D.load_m1(symbol)

    m15 = to_m15(m1)
    h1 = to_h1(m1)
    h1["ema50"] = h1["close"].ewm(span=50, adjust=False).mean()

    m15["session"] = session_of(m15.index)
    m15["m"] = minute_of(m15.index)
    ma0, ma1 = m_of(asia_start), m_of(asia_end)
    mexec, mflat = m_of(EXEC_END_UTC), m_of(FLAT_UTC)

    # ── biên Á từng phiên, trên M1 (chính xác hơn M15)
    s1 = pd.DataFrame({"session": session_of(m1.index), "m": minute_of(m1.index),
                       "high": m1["high"].to_numpy(), "low": m1["low"].to_numpy()},
                      index=m1.index)
    a = s1[(s1["m"] >= ma0) & (s1["m"] < ma1)]
    g = a.groupby("session")
    asia = pd.DataFrame({"hi": g["high"].max(), "lo": g["low"].min(),
                         "nbar": g.size()})
    asia = asia[asia["nbar"] >= int(0.70 * (ma1 - ma0))]
    asia["rng"] = asia["hi"] - asia["lo"]
    # trung vị 20 phiên TRƯỚC (mở rộng, không nhìn trước)
    asia["rng_med20"] = asia["rng"].rolling(20, min_periods=10).median().shift(1)

    # ── thiên hướng H1: close vs EMA50 tại nến H1 ĐÃ ĐÓNG lúc 07:00 UTC
    h1s = pd.DataFrame({"session": session_of(h1.index), "m": minute_of(h1.index),
                        "close": h1["close"].to_numpy(),
                        "ema50": h1["ema50"].to_numpy()}, index=h1.index)
    bias_bar = h1s[h1s["m"] == ma1 - 60]
    bias = pd.Series(np.where(bias_bar["close"] > bias_bar["ema50"], 1, -1),
                     index=bias_bar["session"].to_numpy())
    bias = bias[~bias.index.duplicated()]

    rows: List[Trade] = []
    for sess, blk in m15.groupby("session", sort=True):
        if sess not in asia.index or sess not in bias.index:
            continue
        row = asia.loc[sess]
        rng = float(row["rng"])
        med = float(row["rng_med20"])
        if not (rng > 0) or not np.isfinite(med) or med <= 0:
            continue
        hi, lo = float(row["hi"]), float(row["lo"])
        b = int(bias.loc[sess])

        w = blk[(blk["m"] >= ma1) & (blk["m"] < mexec)]
        if len(w) < 4:
            continue
        after = blk[blk["m"] >= ma1]
        min_depth = max(MIN_DEPTH_PIPS * pip, MIN_DEPTH_FRAC * rng)

        # cú quét ĐẦU TIÊN đủ điều kiện của phiên — MỘT lệnh mỗi phiên
        for t, bar in w.iterrows():
            o, h, l, c = (float(bar["open"]), float(bar["high"]),
                          float(bar["low"]), float(bar["close"]))
            up = (h - hi) >= min_depth and c < hi        # xuyên TRÊN rồi ĐÓNG trong biên
            dn = (lo - l) >= min_depth and c > lo
            if not (up or dn):
                continue
            sw = +1 if up else -1
            side = -sw                                   # fade
            depth = (h - hi) if up else (lo - l)
            body = abs(c - o)
            wick = depth
            rngbar = max(h - l, 1e-12)
            cpos = (c - l) / rngbar

            nxt = after[after["m"] > bar["m"]]
            if nxt.empty:
                break
            e = float(nxt.iloc[0]["open"])
            spread = float(nxt.iloc[0]["spread_usd"])
            if up:
                sl, tp = h + SL_BUFFER_PIPS * pip, lo
                risk, reward = sl - e, e - tp
            else:
                sl, tp = l - SL_BUFFER_PIPS * pip, hi
                risk, reward = e - sl, tp - e
            if risk <= 0 or reward <= 0:
                break

            fwd = nxt[nxt["m"] <= mflat]
            if fwd.empty:
                break
            fh, fl = fwd["high"].to_numpy(), fwd["low"].to_numpy()
            if up:
                i_sl = np.flatnonzero(fh > sl)
                i_tp = np.flatnonzero(fl < tp)
            else:
                i_sl = np.flatnonzero(fl < sl)
                i_tp = np.flatnonzero(fh > tp)
            i_sl = int(i_sl[0]) if i_sl.size else 10**9
            i_tp = int(i_tp[0]) if i_tp.size else 10**9

            rr = reward / risk
            if i_tp < i_sl:
                outcome, rg, k = "TP", rr, i_tp
            elif i_sl < 10**9:
                outcome, rg, k = "SL", -1.0, i_sl
            else:
                k = len(fwd) - 1
                outcome = "FLAT"
                rg = side * (float(fwd.iloc[k]["close"]) - e) / risk

            # chi phí: spread thật lúc khớp + commission khứ hồi, quy về R
            cost_price = spread + prof.commission_price_units(e)
            rows.append(Trade(
                session=sess, t_entry=nxt.index[0], symbol=symbol, side=side,
                sweep_side=sw, asia_rng_pips=rng / pip, asia_rng_rel=rng / med,
                depth_pips=depth / pip, depth_frac=depth / rng,
                wick_body=(wick / body if body > 0 else np.inf),
                close_pos=cpos,
                sweep_hour=int((bar["m"] // 60 + SESSION_ANCHOR_HOUR) % 24),
                dow=int(pd.Timestamp(t).dayofweek), h1_bias=b,
                aligned=bool(side == b),
                sl_pips=risk / pip, tp_pips=reward / pip, rr=rr,
                cost_pips=cost_price / pip, cost_r=cost_price / risk,
                outcome=outcome, r_gross=rg, r_net=rg - cost_price / risk,
                minutes=float((fwd.index[k] - nxt.index[0]).total_seconds() / 60)))
            break

    T = pd.DataFrame([t.__dict__ for t in rows])
    return T


# ═══════════════════════════════════════════════════════════════ tổng hợp
def agg(T: pd.DataFrame) -> pd.Series:
    r = T["r_net"].dropna()
    g = T["r_gross"].dropna()
    return pd.Series({
        "n": len(T),
        "thắng%": 100.0 * (T["outcome"] == "TP").mean() if len(T) else np.nan,
        "RR TV": T["rr"].median() if len(T) else np.nan,
        "SL pip TV": T["sl_pips"].median() if len(T) else np.nan,
        "phí R TV": T["cost_r"].median() if len(T) else np.nan,
        "R gộp": g.mean() if len(g) else np.nan,
        "R ròng": r.mean() if len(r) else np.nan,
        "t ròng": (r.mean() / r.std(ddof=1) * np.sqrt(len(r))
                   if len(r) > 2 and r.std(ddof=1) > 0 else np.nan),
        "giữ (p)": T["minutes"].median() if len(T) else np.nan,
    })


def by(T: pd.DataFrame, keys) -> pd.DataFrame:
    return T.groupby(keys, observed=True).apply(agg, include_groups=False)


def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    for s in PAIRS:
        T = build_trades(s)
        print(f"{s}: {len(T)} lệnh")
        frames.append(T)
    A = pd.concat(frames, ignore_index=True)
    A.to_csv(OUT / "asia_sweep_F_trades.csv", index=False, encoding="utf-8-sig")

    hdr = lambda s: (print(), print("=" * 150), print(s), print("=" * 150))

    hdr("0. LUẬT ĐẶC TẢ NGUYÊN VĂN — xuyên >= max(2 pip, 5% biên) rồi ĐÓNG lại trong "
        "biên M15 · SL = cực trị nến quét + 3 pip · TP = biên Á đối diện · thoát 20:00 UTC")
    print(by(A, "symbol").round(3).to_string())
    print()
    print("   FORM (< 2024-01-01) / OOS")
    print(by(A[A["session"] < FORM_END], "symbol").round(3).to_string())
    print(by(A[A["session"] >= FORM_END], "symbol").round(3).to_string())

    hdr("F1. XU HƯỚNG H1 — thuận (đặc tả) vs ngược vs không lọc")
    print(by(A, ["symbol", "aligned"]).round(3).to_string())

    hdr("F2. BIÊN Á RỘNG/HẸP (biên / trung vị 20 phiên) — Crabel nói nén tốt cho "
        "BREAKOUT, nên chiều FADE kỳ vọng ngược")
    A2 = A.copy()
    A2["biên"] = pd.cut(A2["asia_rng_rel"], [0, 0.80, 1.25, 99.0],
                        labels=["hẹp<0,80", "thường", "rộng>1,25"])
    print(by(A2, ["symbol", "biên"]).round(3).to_string())

    hdr("F3. CỬA SỔ GIỜ QUÉT (UTC)")
    A3 = A.copy()
    A3["cửa sổ"] = pd.cut(A3["sweep_hour"], [6, 9, 12, 15],
                          labels=["07-09", "10-12", "13-15"])
    print(by(A3, ["symbol", "cửa sổ"]).round(3).to_string())

    hdr("F4. ĐỘ SÂU XUYÊN (pip) — đặc tả: 2-25 pip EUR / 3-35 pip GBP")
    A4 = A.copy()
    A4["sâu"] = pd.cut(A4["depth_pips"], [0, 5, 10, 25, 1e4],
                       labels=["<5", "5-10", "10-25", ">25"])
    print(by(A4, ["symbol", "sâu"]).round(3).to_string())

    hdr("F5. ĐÓNG NẾN TRONG BIÊN NẾN QUÉT — Wyckoff tr. 209: phải đóng ở NỬA đối diện")
    A5 = A.copy()
    A5["đóng"] = np.where(
        ((A5["sweep_side"] == 1) & (A5["close_pos"] < 0.5)) |
        ((A5["sweep_side"] == -1) & (A5["close_pos"] > 0.5)),
        "nửa ĐÚNG", "nửa SAI")
    print(by(A5, ["symbol", "đóng"]).round(3).to_string())

    hdr("F6. THỨ TRONG TUẦN (0=Hai)")
    print(by(A, ["symbol", "dow"]).round(3).to_string())

    hdr("G. GỘP MỌI LỌC TỐT NHẤT THEO ĐẶC TẢ (thuận H1 + sâu 5-25 pip + 07-09 UTC + "
        "đóng nửa đúng) — đây là setup mà đặc tả gọi là A+")
    m = (A["aligned"] & A["depth_pips"].between(5, 25) &
         A["sweep_hour"].between(7, 9) &
         (((A["sweep_side"] == 1) & (A["close_pos"] < 0.5)) |
          ((A["sweep_side"] == -1) & (A["close_pos"] > 0.5))))
    B = A[m]
    print(by(B, "symbol").round(3).to_string())
    print()
    print("   gộp 3 cặp:")
    print(agg(B).round(3).to_string())
    print()
    print("   FORM / OOS của tập A+:")
    print(agg(B[B["session"] < FORM_END]).round(3).to_string())
    print(agg(B[B["session"] >= FORM_END]).round(3).to_string())

    hdr("H. ĐẾM Ô DƯƠNG — Aronson 2007 ch.6: ở p<0,05 kỳ vọng 5% ô dương do MAY MẮN")
    cells = []
    for name, frame, key in (("F1", A, ["symbol", "aligned"]),
                             ("F2", A2, ["symbol", "biên"]),
                             ("F3", A3, ["symbol", "cửa sổ"]),
                             ("F4", A4, ["symbol", "sâu"]),
                             ("F5", A5, ["symbol", "đóng"]),
                             ("F6", A, ["symbol", "dow"])):
        t = by(frame, key)
        t = t[t["n"] >= 30]
        cells.append(pd.DataFrame({"lọc": name, "R ròng": t["R ròng"],
                                   "t": t["t ròng"], "n": t["n"]}))
    C = pd.concat(cells)
    print(f"   ô có n >= 30: {len(C)}")
    print(f"   ô R ròng > 0: {int((C['R ròng'] > 0).sum())} "
          f"({100.0 * (C['R ròng'] > 0).mean():.1f}%)")
    print(f"   ô t > 2,0:    {int((C['t'] > 2.0).sum())}")
    print(f"   ô t < -2,0:   {int((C['t'] < -2.0).sum())}")
    C.round(3).to_csv(OUT / "asia_sweep_G_cells.csv", encoding="utf-8-sig")

    print()
    print(f"xong trong {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
