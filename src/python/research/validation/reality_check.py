"""reality_check.py — kiểm định ý nghĩa thống kê cho luật tìm được BẰNG CÁCH QUÉT.

NGUỒN — đọc trước khi sửa bất cứ dòng nào
==========================================
Toàn bộ module này cài đặt lại đúng đặc tả trong tài liệu, KHÔNG phải phương pháp
tự nghĩ ra. Đối chiếu được:

  [1] Aronson, D. (2007). *Evidence-Based Technical Analysis: Applying the
      Scientific Method and Statistical Inference to Trading Signals*. Wiley.
      — Chương 6 "Data-Mining Bias: The Fool's Gold of Objective TA",
        tr. 323-330: đặc tả từng bước của WRC (tr. 325-326), MCP (tr. 327-328),
        và công thức co ngót Markowitz–Xu (tr. 323-324).
      — Năm yếu tố quyết định độ lớn sai lệch: tr. 288-289.
  [2] White, H. (2000). "A Reality Check for Data Snooping".
      *Econometrica* 68(5), 1097-1126. — bài gốc của WRC.
  [3] Hansen, P.R. (2005). "A Test for Superior Predictive Ability".
      *Journal of Business & Economic Statistics* 23(4), 365-380.
      — chỉ ra WRC mất lực kiểm định khi vũ trụ luật chứa luật tệ hơn mốc chuẩn.
  [4] Romano, J.P. & Wolf, M. (2005). "Stepwise Multiple Testing as Formalized
      Data Snooping". *Econometrica* 73(4), 1237-1282.
      — bản từng bước, tăng lực kiểm định và tìm được NHIỀU luật đạt chứ không
        chỉ luật tốt nhất.
  [5] Markowitz, H. & Xu, G. (1994). "Data Mining Corrections".
      *Journal of Portfolio Management* 21(1), 60-69. — công thức co ngót.

Ghi chép đọc tài liệu: `docs/research/literature-review-2026-08.md` §1.1.

VÌ SAO MODULE NÀY TỒN TẠI
==========================
Dự án đã có `overfitting_stats.py` (Deflated Sharpe Ratio và PBO của López de
Prado). Cả hai đều hiệu chỉnh theo SỐ LẦN THỬ, nhưng không dùng chính lợi suất
của các luật đã thử để dựng phân phối null.

Thiếu sót cụ thể phát hiện ngày 03/08: các phép đối chứng ngẫu nhiên trong
`scratch/` chỉ so luật THẮNG với phân phối của MỘT luật ngẫu nhiên. Nhưng đại
lượng thực sự quan sát được là *cực đại trên N luật*. Aronson [1] tr. 275-277
gọi đúng đây là sai lầm cốt lõi:

    "the data miner requires the sampling distribution of the maximum mean
    among a multitude of means because that is the statistic being considered
    when evaluating the best rule found by data mining."

Dùng phân phối của một trung bình để kiểm định một cực đại thì bác bỏ giả thuyết
không nhiều hơn hẳn mức ý nghĩa đã đặt — tức hiệu chỉnh THIẾU.

CHI TIẾT DỄ BỎ SÓT
==================
Với MCP, phép xáo trộn phải dùng **CÙNG một hoán vị cho toàn bộ vũ trụ luật**
([1] tr. 328). Xáo riêng từng luật sẽ phá cấu trúc tương quan giữa các luật; mà
tương quan cao làm GIẢM sai lệch (yếu tố 3), nên xáo riêng ước lượng sai lệch
CAO hơn thực tế và loại oan luật tốt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional, Sequence

import numpy as np


@dataclass
class RealityCheckResult:
    """Kết quả một lượt kiểm định cực đại."""

    best_rule: str
    best_stat: float
    p_value: float
    null_median: float
    null_p95: float
    n_rules: int
    n_draws: int
    method: str
    # Romano–Wolf: mọi luật bị bác bỏ giả thuyết không, theo thứ tự bác bỏ.
    rejected: Dict[str, float] = field(default_factory=dict)

    @property
    def significant(self) -> bool:
        return self.p_value < 0.05

    def summary(self) -> str:
        rows = (f"[{self.method}] {self.n_rules} luật × {self.n_draws} lần rút — "
                f"tốt nhất '{self.best_rule}' = {self.best_stat:+.4f}, "
                f"null trung vị {self.null_median:+.4f} / p95 {self.null_p95:+.4f}, "
                f"p = {self.p_value:.4f} "
                f"{'ĐẠT' if self.significant else 'KHÔNG ĐẠT'}")
        if self.rejected:
            rows += f"\n  Romano–Wolf bác bỏ {len(self.rejected)} luật: " +\
                    ", ".join(f"{k} (p≤{v:.4f})" for k, v in self.rejected.items())
        return rows


def _to_matrix(rule_returns: Mapping[str, Sequence[float]]):
    """(tên luật, ma trận N_luật × T) — mọi luật phải cùng độ dài lịch sử.

    Cùng độ dài là BẮT BUỘC, không phải tiện tay: cả WRC lẫn MCP đều lấy cùng
    một bộ chỉ số thời gian cho mọi luật để giữ cấu trúc tương quan ([1] tr. 328).
    """
    names = list(rule_returns.keys())
    if not names:
        raise ValueError("rule_returns rỗng — không có luật nào để kiểm định.")
    lens = {len(rule_returns[n]) for n in names}
    if len(lens) != 1:
        raise ValueError(
            f"Các luật có độ dài lịch sử khác nhau: {sorted(lens)}. WRC/MCP đòi "
            f"cùng một trục thời gian cho mọi luật — hãy căn về cùng lịch giao "
            f"dịch và điền 0 cho ngày không có vị thế.")
    mat = np.asarray([np.asarray(rule_returns[n], dtype=np.float64) for n in names])
    if not np.isfinite(mat).all():
        raise ValueError("rule_returns chứa NaN/inf — làm sạch trước khi kiểm định.")
    return names, mat


def whites_reality_check(
    rule_returns: Mapping[str, Sequence[float]],
    n_boot: int = 1000,
    seed: int = 0,
    stepwise: bool = True,
) -> RealityCheckResult:
    """White's Reality Check — [1] tr. 325-326, [2].

    Giả thuyết không: MỌI luật trong vũ trụ đã quét đều có lợi suất kỳ vọng 0.

    Trình tự đúng như sách:
      1. Trừ trung bình của chính nó khỏi từng luật → áp đặt kỳ vọng 0.
      2. Lấy mẫu CÓ HOÀN LẠI các mốc thời gian, độ dài bằng lịch sử gốc, và
         dùng CÙNG bộ mốc ấy cho mọi luật.
      3. Tính trung bình từng luật, lấy giá trị LỚN NHẤT → một điểm của phân phối.
      4. Lặp `n_boot` lần.
      5. p = tỉ lệ điểm ≥ trung bình QUAN SÁT (chưa trừ) của luật tốt nhất.

    Args:
        rule_returns: {tên luật: chuỗi lợi suất từng kỳ}. Kỳ nào cũng được
            (ngày/tuần/lệnh) miễn mọi luật dùng chung một trục.
        n_boot: số lần bootstrap. Sách khuyến nghị ≥ 500.
        stepwise: bật bản từng bước Romano–Wolf [4] để tìm MỌI luật đạt, không
            chỉ luật đầu bảng. Tắt nếu chỉ cần p cho luật tốt nhất.
    """
    names, mat = _to_matrix(rule_returns)
    n_rules, T = mat.shape
    means = mat.mean(axis=1)

    # Bước 1 — áp đặt giả thuyết không lên TỪNG luật.
    centered = mat - means[:, None]

    rng = np.random.default_rng(seed)
    # Bước 2-4. Ma trận `draws` là n_boot × n_rules để bản từng bước dùng lại
    # được CÙNG bộ mẫu bootstrap — Romano–Wolf đòi vậy, không được rút mới.
    draws = np.empty((n_boot, n_rules), dtype=np.float64)
    for b in range(n_boot):
        idx = rng.integers(0, T, size=T)
        draws[b] = centered[:, idx].mean(axis=1)

    return _finalize(names, means, draws, "WRC", stepwise)


def monte_carlo_permutation(
    rule_states: Mapping[str, Sequence[float]],
    market_returns: Sequence[float],
    n_perm: int = 1000,
    seed: int = 0,
    stepwise: bool = True,
) -> RealityCheckResult:
    """Hoán vị Monte Carlo — [1] tr. 327-328.

    Giả thuyết không KHÁC với WRC: ở đây là "trạng thái đầu ra của luật tương
    quan ngẫu nhiên với biến động tương lai của thị trường", chứ không phải
    "lợi suất kỳ vọng bằng 0". Giả thuyết này sát với câu hỏi giao dịch hơn.

    Trình tự:
      1. Lấy chuỗi trạng thái của mọi luật (+1 mua, −1 bán, 0 đứng ngoài).
      2. Xáo trộn lợi suất thị trường — **CÙNG một hoán vị cho mọi luật**.
      3. Lợi suất mỗi luật = trạng thái × lợi suất đã xáo; lấy trung bình.
      4. Lấy giá trị lớn nhất trong N luật → một điểm của phân phối.
      5. Lặp `n_perm` lần; p = tỉ lệ điểm ≥ trung bình quan sát của luật tốt nhất.

    Khác WRC ở chỗ hoán vị là KHÔNG HOÀN LẠI (đúng nghĩa hoán vị), và không cần
    dịch phân phối về 0 — trung bình của phân phối null tự nó đã là lợi suất kỳ
    vọng của một luật vô dụng trong đúng cuộc quét này.

    MCP không dựng được khoảng tin cậy ([1] tr. 328) vì nó không kiểm giả thuyết
    về giá trị trung bình. Cần khoảng tin cậy thì dùng `whites_reality_check`.
    """
    names, states = _to_matrix(rule_states)
    mkt = np.asarray(market_returns, dtype=np.float64)
    if mkt.shape[0] != states.shape[1]:
        raise ValueError(
            f"market_returns dài {mkt.shape[0]} nhưng chuỗi trạng thái dài "
            f"{states.shape[1]} — hai thứ phải cùng trục thời gian.")
    if not np.isfinite(mkt).all():
        raise ValueError("market_returns chứa NaN/inf.")

    observed = (states * mkt[None, :]).mean(axis=1)

    rng = np.random.default_rng(seed)
    n_rules, T = states.shape
    draws = np.empty((n_perm, n_rules), dtype=np.float64)
    for b in range(n_perm):
        # MỘT hoán vị dùng chung — xem ghi chú "CHI TIẾT DỄ BỎ SÓT" ở đầu file.
        perm = rng.permutation(T)
        draws[b] = (states * mkt[perm][None, :]).mean(axis=1)

    return _finalize(names, observed, draws, "MCP", stepwise)


def _finalize(names, observed, draws, method: str, stepwise: bool
              ) -> RealityCheckResult:
    """Tính p cho luật tốt nhất, và (tuỳ chọn) chạy bản từng bước Romano–Wolf."""
    best_i = int(np.argmax(observed))
    best_stat = float(observed[best_i])
    max_draws = draws.max(axis=1)
    n_draws = draws.shape[0]
    # +1 ở tử và mẫu: ước lượng p không chệch cho phép kiểm hoán vị, tránh p = 0
    # tuyệt đối vốn là điều không một phép kiểm hữu hạn nào chứng minh được.
    p = float((np.sum(max_draws >= best_stat) + 1) / (n_draws + 1))

    rejected: Dict[str, float] = {}
    if stepwise:
        # ROMANO–WOLF TỪNG BƯỚC [4].
        #
        # Bản một bước chỉ trả lời được về luật đầu bảng. Bản từng bước: sau khi
        # bác bỏ luật tốt nhất, LOẠI nó khỏi vũ trụ rồi tính lại cực đại null
        # trên phần CÒN LẠI, dùng ĐÚNG bộ mẫu bootstrap/hoán vị cũ (không rút
        # mới — rút mới sẽ làm hỏng kiểm soát sai lầm loại I toàn cục).
        #
        # Nhờ đó ngưỡng nới dần sau mỗi lần bác bỏ, và ta tìm được MỌI luật đạt
        # thay vì chỉ một. Đây cũng là câu trả lời cho phê bình Hansen [3]: vũ
        # trụ chứa luật tệ làm phình cực đại null ở bản một bước, nhưng bản từng
        # bước gỡ dần nên bớt mất lực kiểm định.
        remaining = list(range(len(names)))
        while remaining:
            sub = draws[:, remaining]
            sub_max = sub.max(axis=1)
            j_local = int(np.argmax(observed[remaining]))
            j = remaining[j_local]
            stat = float(observed[j])
            p_j = float((np.sum(sub_max >= stat) + 1) / (n_draws + 1))
            if p_j >= 0.05:
                break
            rejected[names[j]] = p_j
            remaining.remove(j)

    return RealityCheckResult(
        best_rule=names[best_i], best_stat=best_stat, p_value=p,
        null_median=float(np.median(max_draws)),
        null_p95=float(np.percentile(max_draws, 95)),
        n_rules=len(names), n_draws=n_draws, method=method, rejected=rejected)


def markowitz_xu_shrinkage(
    rule_returns: Mapping[str, Sequence[float]],
    best_rule: Optional[str] = None,
) -> Dict[str, float]:
    """Co ngót Markowitz–Xu — [1] tr. 323-324, [5].

        H' = R + B·(H − R)

    `H` hiệu suất quan sát của luật thắng, `R` trung bình của MỌI luật đã thử,
    `B ∈ [0, 1]` hệ số co ngót. B → 0 nghĩa là con số của luật thắng gần như
    toàn bộ là may mắn, ước lượng tụt về trung bình chung; B → 1 nghĩa là không
    phát hiện sai lệch.

    Aronson gọi thẳng đây là *rough guideline* và cảnh báo có điều kiện cho kết
    quả sai nặng — dùng để cảm nhận độ lớn, KHÔNG dùng làm con số báo cáo. Muốn
    kết luận thì dùng WRC hoặc MCP.

    Hệ số B ở đây ước lượng theo tinh thần phân tích phương sai của bài gốc:
    tỉ lệ phương sai GIỮA các luật trên tổng phương sai giữa-các-luật cộng
    phương sai sai số của trung bình từng luật. Bài gốc trình bày qua bảng tính
    Excel chứ không cho công thức đóng, nên đây là bản xấp xỉ — đã ghi rõ.
    """
    names, mat = _to_matrix(rule_returns)
    n_rules, T = mat.shape
    means = mat.mean(axis=1)
    R = float(means.mean())

    if best_rule is None:
        best_i = int(np.argmax(means))
    else:
        if best_rule not in names:
            raise ValueError(f"Không có luật tên '{best_rule}'.")
        best_i = names.index(best_rule)
    H = float(means[best_i])

    # Phương sai sai số của một trung bình luật (trung bình trên các luật).
    var_within = float(np.mean(mat.var(axis=1, ddof=1) / T))
    var_between_obs = float(means.var(ddof=1)) if n_rules > 1 else 0.0
    # Phần phương sai giữa các luật thuộc về CÔNG LỰC THẬT = quan sát trừ nhiễu.
    var_merit = max(var_between_obs - var_within, 0.0)
    B = var_merit / var_between_obs if var_between_obs > 0 else 0.0

    return {
        "H_quan_sat": H,
        "R_trung_bình_mỗi_luật": R,
        "B_he_so_co_ngot": B,
        "H_hieu_chinh": R + B * (H - R),
        "sai_lệch_ước_tính": H - (R + B * (H - R)),
        "n_luat": n_rules,
        "n_ky": T,
    }
