"""Báo cáo TỔNG KẾT PHIÊN — CLONE `email_reporter.send_session_report` hệ XAUUSD.

VÌ SAO CẦN
===========
Ba nhóm thư kia đều báo MỘT sự kiện: một lệnh vào, một lệnh ra, một ngưỡng bị
chạm. Không nhóm nào trả lời câu hỏi mà người vận hành hỏi cuối mỗi ngày: *hôm nay
hệ đã làm gì, và kết quả ra sao*. Đọc hai chục thư lẻ rồi tự cộng lại không phải
câu trả lời — đó là cách bỏ sót đúng những ngày đáng nhìn nhất.

NGUỒN DỮ LIỆU: `logs/decisions/decisions_YYYY-MM.jsonl`
=======================================================
Hệ XAUUSD đọc `trade_journal.jsonl`, và nếu thiếu thì rơi về CSV của EA cũ. Hệ này
KHÔNG có EA, và mọi lệnh đã đóng đều đi qua đúng một cửa — `exit_manager.record_close`
ghi vào `decision_log` dưới nhãn `ClosedTrades`. Một nguồn thì không có chuyện hai
nguồn lệch nhau, nên bỏ luôn nhánh dự phòng thay vì port một nhánh không bao giờ chạy.

ĐƠN VỊ LÀ **bps**, KHÔNG PHẢI USD
==================================
`ClosedTrade.gross_bps` là lợi nhuận theo ĐIỂM CƠ BẢN trên giá, vì đó là thứ chiến
lược sinh ra và là thứ so được với backtest. Quy sang USD cần lot, notional và tỷ
giá quy đổi tại thời điểm đóng — ba thứ có thể trôi, và một con số USD sai trong báo
cáo tổng kết còn tệ hơn không có. Báo cáo giữ bps làm đơn vị chính, kèm ước tính USD
khi có đủ dữ liệu và ghi rõ đó là ƯỚC TÍNH.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.python.shared.notifications.emails import (
    _bot, _emit, _footer_line, _kv_row, _block, _card_style, _now_local, _version,
)

# Ngưỡng phân loại phiên. Không có "hoà": 0,0 bps là phiên KHÔNG LỖ, và gộp nó vào
# nhóm lỗ sẽ làm màu thư nói sai về một ngày bình thường.
BORDER_WIN = "#1e874b"
BORDER_LOSS = "#c0392b"


def _load_closed(day: str) -> List[Dict[str, Any]]:
    """Mọi lệnh đã đóng trong ngày `day` (YYYY-MM-DD, theo UTC của `exit_bar_utc`)."""
    try:
        from src.python.execution import decision_log as DLOG

        rows = DLOG.load(month=day[:7], strategy="ClosedTrades")
    except Exception:
        return []
    out = []
    for r in rows:
        # `decision_log.record_many` bọc bản ghi; chấp nhận cả hai hình dạng để
        # báo cáo không im lặng rỗng khi cấu trúc sổ đổi.
        row = r.get("decision", r) if isinstance(r, dict) else {}
        if not isinstance(row, dict):
            continue
        if str(row.get("exit_bar_utc", "")).startswith(day):
            out.append(row)
    return out


def build_metrics(day: str) -> Dict[str, Any]:
    """Chỉ số phiên của một ngày. Luôn trả về dict, kể cả khi không có lệnh nào.

    Trả dict rỗng-nhưng-hợp-lệ chứ không trả `None`: "hôm nay không vào lệnh nào"
    là trạng thái BÌNH THƯỜNG của danh mục tái cân bằng theo lịch, và phân biệt nó
    với "không đọc được sổ" là việc của `error`, không phải của `None`.
    """
    closed = _load_closed(day)
    wins = [c for c in closed if float(c.get("gross_bps", 0)) > 0]
    losses = [c for c in closed if float(c.get("gross_bps", 0)) <= 0]
    gp = sum(float(c.get("gross_bps", 0)) for c in wins)
    gl = abs(sum(float(c.get("gross_bps", 0)) for c in losses))
    n = len(closed)

    by_reason: Dict[str, int] = {}
    for c in closed:
        r = str(c.get("reason", "?"))
        by_reason[r] = by_reason.get(r, 0) + 1

    return {
        "date": day,
        "closed": closed,
        "total_trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": (len(wins) / n * 100.0) if n else 0.0,
        "gross_profit_bps": gp,
        "gross_loss_bps": gl,
        "net_bps": gp - gl,
        # Profit factor bằng vô cực khi chưa có lệnh thua nào — trả `None` để bên
        # hiển thị ghi "—" thay vì in "inf", thứ trông như lỗi.
        "profit_factor": (gp / gl) if gl > 0 else None,
        "avg_win_bps": (gp / len(wins)) if wins else 0.0,
        "avg_loss_bps": (-gl / len(losses)) if losses else 0.0,
        "largest_win_bps": max((float(c.get("gross_bps", 0)) for c in wins), default=0.0),
        "largest_loss_bps": min((float(c.get("gross_bps", 0)) for c in losses), default=0.0),
        "by_reason": by_reason,
    }


def _pf_txt(pf: Optional[float]) -> str:
    return "—" if pf is None else f"{pf:.2f}"


def _trade_table(closed: List[Dict[str, Any]]) -> str:
    if not closed:
        return ('<div style="margin:0 28px 18px 28px;color:#8a94a6;font-size:13px">'
                'Không có lệnh nào đóng trong phiên.</div>')
    head = ("".join(f'<th style="padding:8px 10px;font-size:11px;color:#5a6472;'
                    f'text-transform:uppercase;letter-spacing:.5px;text-align:left">{h}</th>'
                    for h in ("#", "Chân", "Công cụ", "Chiều", "Vào", "Ra",
                              "Nến", "bps", "Lý do")))
    rows = ""
    for i, c in enumerate(closed, 1):
        bps = float(c.get("gross_bps", 0))
        win = bps > 0
        bg = "#ffffff" if i % 2 else "#f6f8fb"
        color = "#1e874b" if win else "#c0392b"
        rows += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:8px 10px;font-size:12px">{i}</td>'
            f'<td style="padding:8px 10px;font-size:12px">{c.get("leg", "")}</td>'
            f'<td style="padding:8px 10px;font-size:12px">{c.get("symbol", "")}</td>'
            f'<td style="padding:8px 10px;font-size:12px">{c.get("side", "")}</td>'
            f'<td style="padding:8px 10px;font-size:12px;text-align:right">'
            f'{float(c.get("entry_price", 0)):.5f}</td>'
            f'<td style="padding:8px 10px;font-size:12px;text-align:right">'
            f'{float(c.get("exit_price", 0)):.5f}</td>'
            f'<td style="padding:8px 10px;font-size:12px;text-align:right">'
            f'{c.get("bars_held", 0)}</td>'
            f'<td style="padding:8px 10px;font-size:12px;text-align:right;'
            f'font-weight:600;color:{color}">{bps:+.1f}</td>'
            f'<td style="padding:8px 10px;font-size:12px">{c.get("reason", "")}</td>'
            f'</tr>')
    return ('<div style="margin:0 28px 18px 28px;overflow-x:auto">'
            '<table style="width:100%;border-collapse:collapse">'
            f'<thead><tr style="border-bottom:2px solid #e2e8f0">{head}</tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


def send(day: Optional[str] = None, *, equity: float = 0.0,
         balance: float = 0.0) -> bool:
    """Gửi báo cáo tổng kết phiên của `day` (mặc định: hôm nay theo UTC)."""
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    m = build_metrics(day)
    net = float(m["net_bps"])
    is_win = net >= 0
    border = BORDER_WIN if is_win else BORDER_LOSS
    head = "✅ PHIÊN LÃI" if is_win else "❌ PHIÊN LỖ"

    metrics = _block("① Chỉ số phiên",
                     _kv_row("Tổng số lệnh đóng", m["total_trades"])
                     + _kv_row("Lệnh thắng / thua", f'{m["wins"]} / {m["losses"]}')
                     + _kv_row("Tỷ lệ thắng (Winrate)", f'{m["win_rate"]:.1f}%')
                     + _kv_row("Profit Factor", _pf_txt(m["profit_factor"]))
                     + _kv_row("Tổng lãi (Gross Profit)",
                               f'+{m["gross_profit_bps"]:.1f} bps', color="#1e874b")
                     + _kv_row("Tổng lỗ (Gross Loss)",
                               f'-{m["gross_loss_bps"]:.1f} bps', color="#c0392b")
                     + _kv_row("Lãi/lỗ ròng", f"{net:+.1f} bps", color=border)
                     + _kv_row("Lệnh thắng TB", f'{m["avg_win_bps"]:+.1f} bps')
                     + _kv_row("Lệnh thua TB", f'{m["avg_loss_bps"]:+.1f} bps')
                     + _kv_row("Lệnh lãi lớn nhất", f'{m["largest_win_bps"]:+.1f} bps')
                     + _kv_row("Lệnh lỗ lớn nhất", f'{m["largest_loss_bps"]:+.1f} bps'))

    # LÝ DO ĐÓNG là khối RIÊNG, và nó quan trọng hơn vẻ ngoài của nó.
    #
    # Đây là thứ đầu tiên phải nhìn khi live lệch khỏi backtest (xem
    # `exit_manager.summarise`): tỷ lệ TIMESTOP khác backtest nghĩa là đồng hồ
    # time-stop đang sai, còn DISASTER_STOP xuất hiện thường xuyên nghĩa là cầu
    # chì đặt quá gần. Cả hai đều KHÔNG nhìn ra được từ đường equity.
    reason_rows = "".join(_kv_row(k, v) for k, v in
                          sorted(m["by_reason"].items(), key=lambda kv: -kv[1]))
    reasons = _block("② Lý do đóng lệnh",
                     reason_rows or _kv_row("(không có)", "—"))

    account = _block("③ Tài khoản",
                     _kv_row("Số dư (Balance)", f"{balance:,.2f} USD" if balance else "—")
                     + _kv_row("Vốn thực tế (Equity)", f"{equity:,.2f} USD" if equity else "—")
                     + _kv_row("Build", _version()))

    html = f"""<!doctype html>
<html><body style="margin:0;padding:0;font-family:Segoe UI,Arial,sans-serif;color:#172033">
  <div style="{_card_style(border)}">
    <div style="background:linear-gradient(135deg,#0b1736,#142a57);padding:24px 28px;color:#ffffff">
      <table style="width:100%;border-collapse:collapse">
        <tr>
          <td>
            <div style="font-size:12px;text-transform:uppercase;letter-spacing:1.2px;color:#9fb4dd">Session Report</div>
            <div style="margin-top:6px;font-size:24px;font-weight:700">{head} — {day}</div>
          </td>
          <td align="right" valign="top">
            <span style="display:inline-block;padding:8px 14px;border-radius:999px;background:{border};color:#ffffff;font-size:14px;font-weight:700">{net:+.1f} bps</span>
          </td>
        </tr>
      </table>
    </div>
    <div style="padding:24px 28px 18px 28px">
      <div style="font-size:12px;color:#748096;text-transform:uppercase;letter-spacing:0.8px">Danh mục</div>
      <div style="margin-top:4px;font-size:22px;font-weight:800;color:#102044">{_bot()}</div>
    </div>
    <div style="padding:0 0 8px">
      {metrics}
      {reasons}
      {account}
      <div style="margin:0 28px 6px 28px;font-size:12px;font-weight:700;color:#94a3b8;
                  text-transform:uppercase;letter-spacing:0.6px">④ Chi tiết lệnh đã đóng</div>
      {_trade_table(m["closed"])}
    </div>
    {_footer_line()}
  </div>
</body></html>
"""
    lines = "".join(
        f'  {i:>2}. {c.get("leg", ""):22} {c.get("symbol", ""):8} '
        f'{c.get("side", ""):4} {c.get("bars_held", 0):>3} nến '
        f'{float(c.get("gross_bps", 0)):+8.1f} bps  {c.get("reason", "")}\n'
        for i, c in enumerate(m["closed"], 1))
    text = (
        f"{head} — {day}\n\n"
        f"① CHỈ SỐ PHIÊN\n"
        f"  - Tổng số lệnh đóng: {m['total_trades']}\n"
        f"  - Thắng / thua: {m['wins']} / {m['losses']} (winrate {m['win_rate']:.1f}%)\n"
        f"  - Profit Factor: {_pf_txt(m['profit_factor'])}\n"
        f"  - Gross Profit: +{m['gross_profit_bps']:.1f} bps | "
        f"Gross Loss: -{m['gross_loss_bps']:.1f} bps\n"
        f"  - Lãi/lỗ ròng: {net:+.1f} bps\n"
        f"  - Thắng TB: {m['avg_win_bps']:+.1f} bps | Thua TB: {m['avg_loss_bps']:+.1f} bps\n\n"
        f"② LÝ DO ĐÓNG LỆNH\n"
        + ("".join(f"  - {k}: {v}\n" for k, v in
                   sorted(m["by_reason"].items(), key=lambda kv: -kv[1]))
           or "  - (không có)\n")
        + f"\n③ TÀI KHOẢN\n"
        f"  - Balance: {balance:,.2f} USD | Equity: {equity:,.2f} USD\n"
        f"  - Build: {_version()}\n\n"
        f"④ CHI TIẾT LỆNH ĐÃ ĐÓNG\n"
        + (lines or "  (không có lệnh nào đóng trong phiên)\n")
        + f"\nThời điểm gửi: {_now_local()} (GMT +7)\n"
    )
    subject = (f"{'✅ Phiên lãi' if is_win else '❌ Phiên lỗ'} {day} — "
               f"{m['total_trades']} lệnh, {net:+.1f} bps")
    return _emit(subject, html, text)


def should_send(now_utc: Optional[datetime] = None) -> Optional[str]:
    """Ngày cần gửi báo cáo, hoặc `None` nếu chưa tới giờ / đã gửi.

    Gửi sau khi phiên New York đóng (21:00 UTC) cho ngày VỪA KẾT THÚC. Hệ XAUUSD
    chốt 16:30 GMT vì nó không giữ lệnh qua đêm; danh mục này có chân M30 chạy tới
    hết phiên Mỹ, nên chốt sớm là bỏ sót nửa cuối ngày.

    Cuối tuần KHÔNG gửi: thị trường đóng, không lệnh nào đóng được, và một thư
    rỗng đều đặn mỗi thứ Bảy là cách làm người đọc bỏ qua cả chủ đề.
    """
    now = now_utc or datetime.now(timezone.utc)
    if now.hour < 21:
        return None
    day = now.strftime("%Y-%m-%d")
    if now.weekday() >= 5:              # thứ Bảy, Chủ Nhật
        return None
    return day
