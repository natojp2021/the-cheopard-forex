"""asia_sweep_lab.py — Vòng 71. ĐO hiện tượng quét biên độ phiên Á TRƯỚC KHI code chiến lược.

VÌ SAO VÒNG NÀY TỒN TẠI, VÀ VÌ SAO NÓ KHÔNG PHẢI MỘT BACKTEST
==============================================================
Yêu cầu là code "Asia Range Sweep" thành chiến lược duy nhất. Trước khi viết một dòng
chiến lược nào, phải trả lời ba câu mà KHÔNG cần bất kỳ tham số nào được hiệu chỉnh:

    1. Biên độ phiên Á có bị quét thường xuyên hơn một mức giá BẤT KỲ không?
    2. Sau khi quét, giá HỒI (đảo chiều) hay CHẢY TIẾP (cascade)?
    3. Nếu có hồi, nó hồi ĐỦ SÂU và ĐỦ LÂU để giao dịch được sau chi phí không?

Đây là "chẩn đoán đo được trước khi backtest" — nguồn bằng chứng ưu tiên 2 của dự án,
thứ đã chấm dứt 57 vòng quét mù. Không tham số nào ở đây được chọn theo lợi nhuận.

BẰNG CHỨNG HỌC THUẬT NÓI NGƯỢC VỚI TRUYỀN THUYẾT ICT — GHI RÕ TỪ ĐẦU
=====================================================================
`docs/the-asia-sweep/H1_INDUCEMENT_SWEEP_SPEC.md` trích Carol Osler làm cơ sở cho luật
"quét rồi ĐẢO CHIỀU". Đọc bản gốc thì kết luận chính của Osler NGƯỢC LẠI:

    Osler (2003) "Stop-Loss Orders and Price Cascades in Currency Markets",
    FRBNY Staff Report 150. USD/JPY · USD/DEM · GBP/USD, quote phút-theo-phút,
    giờ New York 09:00-16:00, 01/1996-04/1998. Stop-loss = 43% tổng khối lượng
    lệnh, 45% theo giá trị.
    docs/the-asia-sweep/references/Carol_Osler_FED_NY_sr150_StopLoss_Orders.md

    · Cụm STOP-LOSS làm giá CHẢY TIẾP, không đảo. USD/DEM đi trung bình 0,061%
      trong 15 phút sau khi XUYÊN QUA mốc tròn, so với 0,054% sau mốc bất kỳ
      (p < 0,001%). Hiệu ứng chảy tiếp còn ý nghĩa thống kê ÍT NHẤT 2 GIỜ.
    · Đảo chiều là chuyện của cụm TAKE-PROFIT, và nó NHỎ: tần suất đảo chiều
      59,3% tại mốc tròn so với 54,8% tại mốc bất kỳ — hơn 4,5 điểm phần trăm.
      Và nó chỉ còn ý nghĩa thống kê DƯỚI 30 PHÚT (Bảng VIII.A).
    · Stop-loss nằm NGAY BÊN NGOÀI mốc tròn (14,3% lệnh stop-buy có giá khớp
      đuôi [01,10] so với 6,9% ở đuôi [91,00]); take-profit nằm ĐÚNG mốc tròn
      (9,9% so với 3,8%). Với lệnh RẤT LỚN (>= $50M): 62% giá trị stop-loss nằm
      trong đuôi [90,100] và [01,09].
    · Hiệu ứng của dòng lệnh điều kiện MẠNH HƠN khi thanh khoản THẤP (chiều New
      York mạnh hơn sáng New York, dù khối lượng lệnh mở buổi chiều nhỏ hơn).

Ba hệ quả ĐỊNH LƯỢNG cho thiết kế, cả ba phải kiểm chứng ở đây:

    (a) Cú quét biên Á, nơi stop bán lẻ nằm ngay bên ngoài, theo Osler thì phải
        CHẢY TIẾP. Fade nó là đánh ngược vi cấu trúc đã có bằng chứng. Nên điều
        kiện phân biệt KHÔNG phải "có quét" mà là "quét rồi THẤT BẠI".
    (b) Cửa sổ đảo chiều ~ 30 PHÚT. Trên H1 đó là NỬA nến. Tín hiệu chờ nến H1
        đóng lại trong biên đến muộn 0-60 phút, tức phần lớn đã hết cửa sổ. Đây
        đúng cơ chế đã giết `NewsOverreaction` của dự án (vào muộn 1 nến làm t
        tụt 1,64 -> 0,47). Vậy H1 chỉ được là khung BỐI CẢNH; khớp lệnh phải
        nhanh hơn. Script này đo trên M1 để biết cửa sổ thật rộng bao nhiêu.
    (c) Thanh khoản thấp làm hiệu ứng mạnh hơn -> cú quét CUỐI phiên Á có thể
        tốt hơn cú quét lúc London mở. Đo cả hai, không mặc định.

BẰNG CHỨNG NỘI BỘ ĐÃ CÓ (vòng 69-70, `asian_range_breakout.py`)
================================================================
Phá biên độ cửa sổ 3 tiếng phiên Á rồi vào THUẬN chiều, đủ chi phí:
    USDJPY +0,319 Sharpe (t = 0,98) · EURUSD -0,225 · GBPUSD -0,545
    và 4 cặp Tier 2 từ -0,655 tới -1,353 — 6/7 cặp ÂM.
Quét giờ bắt đầu cửa sổ: giờ 00 cho net -32,59 bps/lệnh, giờ 01 -21,64, giờ 02 -9,21.
Tức phá biên độ khung Á SỚM là mất tiền một cách hệ thống — chiều FADE có lãi GỘP
dương rất lớn ở đúng những giờ đó. Đó là lý do vòng này đo chiều fade.

CÁI GÌ ĐƯỢC ĐO Ở ĐÂY
=====================
Với mỗi phiên và mỗi cặp: biên Á -> cú chạm ĐẦU TIÊN ra ngoài biên trong cửa sổ quan
sát -> độ sâu xuyên -> có "reclaim" (ĐÓNG lại trong biên) không và SAU BAO LÂU ->
cuộc đua TP/SL của nhánh fade, và lợi nhuận chảy tiếp của nhánh không reclaim.

HAI CONTROL, theo đúng thiết kế RRN-vs-RAN của Osler:
    C1  biên Á TRỄ    dùng biên Á của phiên d-5 áp lên phiên d. Giữ nguyên mọi
                      thứ trừ việc "biên Á HÔM NAY có ý nghĩa gì".
    C2  mức BẤT KỲ    mức = biên Á +- 0,35 x biên độ. Trả lời "chính cái mức đó
                      đặc biệt, hay bất kỳ mức nào quanh đó cũng vậy".

Cửa sổ phiên được QUÉT và báo cáo TOÀN BỘ bề mặt, không lấy ô đẹp nhất — bài học
vòng 70, nơi mốc 03:00-06:00 hoá ra chỉ là một ô may mắn trong lưới 24 giờ.
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

pd.set_option("display.width", 250, "display.max_columns", 40,
              "display.max_rows", 400)

OUT = ROOT / "reports" / "fx_research"
PAIRS = ("EURUSD", "GBPUSD", "USDJPY")

# Mốc neo PHIÊN: 21:00 UTC. Trước Tokyo mở (00:00 UTC) và sau khi New York đóng,
# nên mọi cửa sổ quan tâm (Á, London, NY) nằm trong CÙNG một phiên và không cửa sổ
# nào bị cắt qua nửa đêm. Đây là quyết định KỸ THUẬT, không phải tham số chiến lược.
SESSION_ANCHOR_HOUR = 21


def m_of(hour_utc: float) -> int:
    """Phút-trong-phiên của một giờ UTC. 00:00 UTC = phút 180."""
    return int(round((hour_utc - SESSION_ANCHOR_HOUR) % 24 * 60))


@dataclass(frozen=True)
class Windows:
    """Định nghĩa cửa sổ, tính bằng GIỜ UTC. Được QUÉT, không được hiệu chỉnh."""
    asia_start: float = 0.0      # biên Á tính từ giờ này
    asia_end: float = 7.0        # tới giờ này (không bao gồm)
    obs_end: float = 16.0        # cửa sổ quan sát cú quét kết thúc ở đây
    label: str = ""

    @property
    def ma0(self) -> int:
        return m_of(self.asia_start)

    @property
    def ma1(self) -> int:
        return m_of(self.asia_end)

    @property
    def mobs(self) -> int:
        return m_of(self.obs_end)

    def name(self) -> str:
        return self.label or (f"A{self.asia_start:02.0f}-{self.asia_end:02.0f}"
                              f"/obs{self.obs_end:02.0f}")


# ═══════════════════════════════════════════════════════════════════ nạp dữ liệu
def load(symbol: str) -> pd.DataFrame:
    """M1 kèm phút-trong-phiên và id phiên. CHỈ parquet — cần mẫu cố định."""
    with D.parquet_only():
        df = D.load_m1(symbol).copy()
    shifted = df.index - pd.Timedelta(hours=SESSION_ANCHOR_HOUR)
    df["session"] = shifted.normalize()
    df["m"] = ((shifted - shifted.normalize()).total_seconds() // 60).astype(np.int32)
    return df


# ═════════════════════════════════════════════════════════════ đo một phiên
@dataclass
class Event:
    session: pd.Timestamp
    side: int                      # +1 quét biên TRÊN (fade = BÁN) · -1 biên DƯỚI
    rng_pips: float
    sweep_m: int                   # phút-trong-phiên lúc chạm ra ngoài
    depth_pips: float              # độ sâu xuyên TỐI ĐA trước khi reclaim
    reclaim_min: Optional[int]     # phút từ lúc quét tới lúc ĐÓNG lại trong biên
    entry_px: float = np.nan
    spread_pips: float = np.nan
    fade_outcome: str = ""         # TP | SL | OPEN
    fade_r: float = np.nan         # kết quả theo R (CHƯA trừ chi phí)
    fade_minutes: float = np.nan
    fade_rr: float = np.nan        # R:R có sẵn lúc vào lệnh
    cont_bps_60: float = np.nan    # chảy tiếp 60 phút từ lúc quét
    cont_bps_120: float = np.nan


def _first_touch(arr: np.ndarray, level: float, above: bool) -> int:
    """Chỉ số ĐẦU TIÊN vượt mức. -1 nếu không có."""
    hit = (arr > level) if above else (arr < level)
    w = np.flatnonzero(hit)
    return int(w[0]) if w.size else -1


def scan_session(m: np.ndarray, o: np.ndarray, h: np.ndarray, l: np.ndarray,
                 c: np.ndarray, sp: np.ndarray, w: Windows, pip: float,
                 session: pd.Timestamp, *,
                 level_hi: Optional[float] = None,
                 level_lo: Optional[float] = None,
                 sl_buffer_pips: float = 3.0) -> Optional[Event]:
    """Một phiên -> cú quét ĐẦU TIÊN (hoặc None).

    `level_hi/level_lo` cho phép thay biên Á bằng mức của control — CÙNG đường code,
    nên control không thể khác chiến lược vì lý do hiện thực. Đây là bài học đã ghi
    trong `REJECTED_DIRECTIONS` (mục ZBandGBPCAD_H4): lab và sản xuất phải một đường.
    """
    a = (m >= w.ma0) & (m < w.ma1)
    if int(a.sum()) < int(0.70 * (w.ma1 - w.ma0)):
        return None                     # phiên thiếu dữ liệu (lễ, cuối tuần)

    hi = float(h[a].max()) if level_hi is None else level_hi
    lo = float(l[a].min()) if level_lo is None else level_lo
    if not (hi > lo):
        return None

    ob = (m >= w.ma1) & (m < w.mobs)
    if int(ob.sum()) < 60:
        return None
    oh, ol, oc, oo, osp, om = h[ob], l[ob], c[ob], o[ob], sp[ob], m[ob]

    i_up = _first_touch(oh, hi, True)
    i_dn = _first_touch(ol, lo, False)
    if i_up < 0 and i_dn < 0:
        return None
    if i_dn < 0 or (0 <= i_up < i_dn):
        side, level, opp, i0 = +1, hi, lo, i_up
    else:
        side, level, opp, i0 = -1, lo, hi, i_dn

    n = len(oc)
    # reclaim = ĐÓNG nến M1 trở lại trong biên. Đóng nến, không phải chạm — nếu chỉ
    # cần chạm thì mọi cú xuyên đều "reclaim" ngay phút sau và điều kiện thành vô nghĩa.
    if side > 0:
        back = np.flatnonzero(oc[i0:n] < level)
    else:
        back = np.flatnonzero(oc[i0:n] > level)
    j = int(i0 + back[0]) if back.size else -1

    seg_end = j if j >= 0 else n - 1
    depth = (float(oh[i0:seg_end + 1].max() - level) if side > 0
             else float(level - ol[i0:seg_end + 1].min()))

    ev = Event(session=session, side=side, rng_pips=(hi - lo) / pip,
               sweep_m=int(om[i0]), depth_pips=depth / pip,
               reclaim_min=(int(om[j] - om[i0]) if j >= 0 else None))

    # ── lợi nhuận CHẢY TIẾP từ lúc quét, để đối chiếu trực tiếp với Osler
    base = float(oc[i0])
    for hz, fld in ((60, "cont_bps_60"), (120, "cont_bps_120")):
        k = min(i0 + hz, n - 1)
        setattr(ev, fld, side * (float(oc[k]) - base) / base * 1e4)

    if j < 0 or j + 1 >= n:
        return ev

    # ── nhánh FADE: vào ở giá MỞ nến M1 kế tiếp sau nến reclaim (không nhìn trước)
    e = float(oo[j + 1])
    ev.entry_px = e
    ev.spread_pips = float(osp[j + 1]) / pip
    # SL neo vào ĐỈNH/ĐÁY CỦA CÚ QUÉT + đệm (Osler: stop nằm ngay ngoài mốc)
    if side > 0:
        sl, tp = level + depth + sl_buffer_pips * pip, opp
        risk, reward = sl - e, e - tp
    else:
        sl, tp = level - depth - sl_buffer_pips * pip, opp
        risk, reward = e - sl, tp - e
    if risk <= 0 or reward <= 0:
        return ev

    fh, fl, fm = oh[j + 1:], ol[j + 1:], om[j + 1:]
    if side > 0:
        i_sl, i_tp = _first_touch(fh, sl, True), _first_touch(fl, tp, False)
    else:
        i_sl, i_tp = _first_touch(fl, sl, False), _first_touch(fh, tp, True)

    ev.fade_rr = reward / risk
    if i_tp >= 0 and (i_sl < 0 or i_tp < i_sl):
        ev.fade_outcome, ev.fade_r = "TP", ev.fade_rr
        ev.fade_minutes = float(fm[i_tp] - om[j + 1])
    elif i_sl >= 0:
        ev.fade_outcome, ev.fade_r = "SL", -1.0
        ev.fade_minutes = float(fm[i_sl] - om[j + 1])
    else:
        last = len(fh) - 1
        ev.fade_outcome = "OPEN"
        ev.fade_r = (-side) * (float(oc[j + 1 + last]) - e) / risk
        ev.fade_minutes = float(fm[last] - om[j + 1])
    return ev


def run(symbol: str, w: Windows, *, mode: str = "asia",
        lag_sessions: int = 5, arb_frac: float = 0.35,
        df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Quét toàn bộ mẫu. `mode`: asia | lagged | arbitrary."""
    if df is None:
        df = load(symbol)
    pip = AP.get(symbol).pip
    g = df.groupby("session", sort=True)
    keys = list(g.groups.keys())

    levels: Dict[pd.Timestamp, Tuple[float, float]] = {}
    packs: Dict[pd.Timestamp, tuple] = {}
    need = int(0.70 * (w.ma1 - w.ma0))
    for k in keys:
        d = g.get_group(k)
        m = d["m"].to_numpy()
        hh, ll = d["high"].to_numpy(), d["low"].to_numpy()
        packs[k] = (m, d["open"].to_numpy(), hh, ll, d["close"].to_numpy(),
                    d["spread_usd"].to_numpy())
        a = (m >= w.ma0) & (m < w.ma1)
        if int(a.sum()) >= need:
            levels[k] = (float(hh[a].max()), float(ll[a].min()))

    rows: List[Event] = []
    for i, k in enumerate(keys):
        m, o, h, l, c, sp = packs[k]
        hi = lo = None
        if mode == "lagged":
            if i < lag_sessions:
                continue
            prev = keys[i - lag_sessions]
            if prev not in levels or k not in levels:
                continue
            hi, lo = levels[prev]
        elif mode == "arbitrary":
            if k not in levels:
                continue
            h0, l0 = levels[k]
            r0 = h0 - l0
            hi, lo = h0 + arb_frac * r0, l0 - arb_frac * r0
        ev = scan_session(m, o, h, l, c, sp, w, pip, k, level_hi=hi, level_lo=lo)
        if ev is not None:
            rows.append(ev)

    T = pd.DataFrame([e.__dict__ for e in rows])
    if T.empty:
        return T
    T["symbol"], T["mode"], T["window"] = symbol, mode, w.name()
    T["reclaimed"] = T["reclaim_min"].notna()
    T["sweep_hour"] = ((T["sweep_m"] // 60 + SESSION_ANCHOR_HOUR) % 24).astype(int)
    return T


# ═══════════════════════════════════════════════════════════════════ tổng hợp
def summarise(T: pd.DataFrame, n_sessions: int) -> Dict[str, object]:
    rec = T[T["reclaimed"]]
    fade = rec[rec["fade_outcome"].isin(("TP", "SL", "OPEN"))]
    won = fade[fade["fade_outcome"] == "TP"]
    r = fade["fade_r"].dropna()
    return {
        "phiên": n_sessions,
        "có quét": len(T),
        "quét %": 100.0 * len(T) / max(n_sessions, 1),
        "reclaim %": 100.0 * len(rec) / max(len(T), 1),
        "reclaim<=30p %": (100.0 * (rec["reclaim_min"] <= 30).mean()
                           if len(rec) else np.nan),
        "reclaim TV(p)": rec["reclaim_min"].median() if len(rec) else np.nan,
        "sâu TV(pip)": T["depth_pips"].median(),
        "biên TV(pip)": T["rng_pips"].median(),
        "n fade": len(fade),
        "TP %": 100.0 * len(won) / max(len(fade), 1),
        "RR TV": fade["fade_rr"].median() if len(fade) else np.nan,
        "R TB": r.mean() if len(r) else np.nan,
        "R t": (r.mean() / r.std(ddof=1) * np.sqrt(len(r))
                if len(r) > 2 and r.std(ddof=1) > 0 else np.nan),
        "spread TV(pip)": fade["spread_pips"].median() if len(fade) else np.nan,
        "cont60 KHÔNG-rec": T.loc[~T["reclaimed"], "cont_bps_60"].mean(),
        "cont60 CÓ-rec": T.loc[T["reclaimed"], "cont_bps_60"].mean(),
    }


def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    base = Windows(0, 7, 16)

    print("=" * 145)
    print("VÒNG 71 · A. HIỆN TƯỢNG QUÉT BIÊN Á — THẬT SỰ vs HAI CONTROL")
    print(f"   biên Á {base.asia_start:02.0f}:00-{base.asia_end:02.0f}:00 UTC · "
          f"quan sát tới {base.obs_end:02.0f}:00 UTC · SL = đỉnh cú quét + 3,0 pip "
          f"· TP = biên Á đối diện · R CHƯA trừ chi phí")
    print("=" * 145)

    allT: List[pd.DataFrame] = []
    rows: List[Dict[str, object]] = []
    for sym in PAIRS:
        df = load(sym)
        n_sess = int(df.groupby("session").size().gt(600).sum())
        for mode in ("asia", "lagged", "arbitrary"):
            T = run(sym, base, mode=mode, df=df)
            if T.empty:
                continue
            allT.append(T)
            s = summarise(T, n_sess)
            s["symbol"], s["mode"] = sym, mode
            rows.append(s)
    S = pd.DataFrame(rows).set_index(["symbol", "mode"])
    print(S.round(2).to_string())
    S.round(4).to_csv(OUT / "asia_sweep_A_phenomenon.csv", encoding="utf-8-sig")

    TT = pd.concat(allT, ignore_index=True)
    TT.to_csv(OUT / "asia_sweep_events.csv", index=False, encoding="utf-8-sig")
    A = TT[TT["mode"] == "asia"]

    print()
    print("=" * 145)
    print("B. GIỜ XẢY RA CÚ QUÉT (UTC) — thanh khoản thấp mạnh hơn, hay London mở mạnh hơn?")
    print("=" * 145)
    by_h = A.groupby(["symbol", "sweep_hour"]).agg(
        n=("side", "size"),
        reclaim_pct=("reclaimed", lambda s: 100.0 * s.mean()),
        R_TB=("fade_r", "mean"),
        TP_pct=("fade_outcome", lambda s: 100.0 * (s == "TP").mean()))
    print(by_h.round(2).to_string())
    by_h.round(4).to_csv(OUT / "asia_sweep_B_hours.csv", encoding="utf-8-sig")

    print()
    print("=" * 145)
    print("C. THỜI GIAN RECLAIM — Osler nói cửa sổ đảo chiều < 30 PHÚT. Kiểm chứng.")
    print("=" * 145)
    A2 = A[A["reclaimed"]].copy()
    A2["nhóm reclaim"] = pd.cut(A2["reclaim_min"],
                                [0, 5, 15, 30, 60, 120, 240, 10_000])
    by_r = A2.groupby(["symbol", "nhóm reclaim"], observed=True).agg(
        n=("side", "size"), R_TB=("fade_r", "mean"),
        TP_pct=("fade_outcome", lambda s: 100.0 * (s == "TP").mean()),
        sau_pip=("depth_pips", "median"), RR_TV=("fade_rr", "median"))
    print(by_r.round(2).to_string())
    by_r.round(4).to_csv(OUT / "asia_sweep_C_reclaim_time.csv", encoding="utf-8-sig")

    print()
    print("=" * 145)
    print("D. ĐỘ SÂU XUYÊN BIÊN — quét thanh khoản, hay breakout thật?")
    print("=" * 145)
    A3 = A.copy()
    A3["nhóm sâu"] = pd.cut(A3["depth_pips"] / A3["rng_pips"],
                            [0, 0.05, 0.10, 0.20, 0.35, 0.60, 100.0])
    by_d = A3.groupby(["symbol", "nhóm sâu"], observed=True).agg(
        n=("side", "size"),
        reclaim_pct=("reclaimed", lambda s: 100.0 * s.mean()),
        R_TB=("fade_r", "mean"),
        TP_pct=("fade_outcome", lambda s: 100.0 * (s == "TP").mean()))
    print(by_d.round(2).to_string())
    by_d.round(4).to_csv(OUT / "asia_sweep_D_depth.csv", encoding="utf-8-sig")

    print()
    print(f"xong trong {time.time() - t0:.0f}s · CSV -> {OUT}")


if __name__ == "__main__":
    main()
