"""Chống GỬI TRÙNG cho email cảnh báo — tối đa một thư mỗi chủ đề trong một TTL.

VÌ SAO PHẢI CÓ TẦNG NÀY
========================
Sự kiện cảnh báo sinh ra từ VÒNG LẶP, và vòng lặp chạy mỗi vài chục giây. Một lần
mất kết nối MT5 kéo dài hai tiếng là hàng trăm chu kỳ cùng thấy "đang mất kết nối".
Không chặn thì hộp thư nhận hàng trăm bản sao của cùng một thư — và người vận hành
sẽ lọc cả chủ đề đó vào thùng rác, tức mất luôn kênh cảnh báo. Cảnh báo lặp lại là
cảnh báo không ai đọc.

MỐC PHẢI SỐNG QUA RESTART
==========================
Giữ mốc trong RAM là hỏng ở đúng ca cần nhất: tiến trình chết rồi bật lại (watchdog,
VPS reboot) thì mốc về rỗng và thư gửi lại từ đầu. Mà "tiến trình chết rồi bật lại"
lại chính là thứ hay đi kèm với sự cố đang được cảnh báo. Nên mốc ghi ra đĩa.

GỬI LỖI THÌ CHO THỬ LẠI SỚM
============================
Nếu `mailer` trả `False` (SMTP hỏng, mạng rớt) thì lùi mốc lại để chu kỳ sau thử
tiếp thay vì im lặng suốt cả TTL — cảnh báo chưa tới tay ai thì chưa tính là đã gửi.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Callable, Dict

from src.python.shared.paths import LOG_DIR
from src.python.utils.logger import log

_LOCK = threading.Lock()
_last_sent: Dict[str, float] = {}

DEFAULT_TTL_SEC = 3600.0
# Chỉ dọn khi vượt ngưỡng này — dưới đó chi phí quét không đáng.
_MAX_TOPIC = 200
# Mốc cũ hơn 24h không còn ảnh hưởng quyết định nào (TTL dài nhất đang dùng là 1h),
# nên xoá là an toàn tuyệt đối về hành vi.
_TTL_MAX_HOLD = 24 * 3600.0

# Tiền tố khoá cho MỐC GỬI THÀNH CÔNG, nằm chung từ điển với mốc chống trùng.
# Xem `once()` và `recently_sent()` — hai mốc này trả lời hai câu khác nhau.
_OK_PREFIX = "ok:"

STATE_PATH = LOG_DIR / "live" / "alert_dedup.json"


def _load_from_disk() -> None:
    """Hoà mốc trên đĩa vào bộ nhớ. Lấy giá trị MỚI HƠN giữa hai bên.

    Lấy `max` chứ không ghi đè: có thể có tiến trình khác (script, phiên GUI thứ
    hai) vừa gửi thư cho cùng chủ đề, và mốc mới hơn của họ phải được tôn trọng.
    """
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k, v in data.items():
                _last_sent[k] = max(_last_sent.get(k, 0.0), float(v))
    except Exception:
        pass


def _save_to_disk() -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(STATE_PATH) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_last_sent, f)
        os.replace(tmp, STATE_PATH)
    except Exception:
        pass


def once(topic: str, sender: Callable[[], bool],
         ttl_sec: float = DEFAULT_TTL_SEC) -> bool:
    """Chạy `sender()` nếu chủ đề `topic` chưa gửi trong `ttl_sec` giây.

    `sender` là hàm KHÔNG tham số trả `bool` — thường là một `functools.partial`
    quanh `shared.notifications.emails.*`. Nhận hàm chứ không nhận sẵn nội dung là
    có chủ ý: dựng nội dung thư cũng tốn công (đọc tài khoản, đọc build), và khi bị
    chặn vì trùng thì không nên tốn công đó.
    """
    now = time.time()
    with _LOCK:
        _load_from_disk()
        if now - _last_sent.get(topic, 0.0) < ttl_sec:
            return False
        _last_sent[topic] = now
        if len(_last_sent) > _MAX_TOPIC:
            for k in [k for k, v in _last_sent.items()
                      if now - float(v) > _TTL_MAX_HOLD]:
                _last_sent.pop(k, None)
        _save_to_disk()

    try:
        ok = bool(sender())
    except Exception as exc:
        log(f"[ALERT] chủ đề {topic!r} ném lỗi: {type(exc).__name__}: {exc}")
        ok = False
    with _LOCK:
        if ok:
            # MỐC THÀNH CÔNG, sổ riêng. `_last_sent[topic]` KHÔNG nói được thư có
            # tới tay ai không: nhánh hỏng bên dưới cũng ghi vào đó (lùi lại còn 5
            # phút để thử lại), nên hai trạng thái trái ngược nhau dùng chung một
            # con số. `recently_sent()` cần phân biệt được chúng — xem docstring ở đó.
            #
            # Tiền tố trong CÙNG từ điển thay vì thêm tệp thứ hai: định dạng trên đĩa
            # vẫn là dict phẳng, tệp cũ vẫn đọc được, và `_MAX_TOPIC` vẫn dọn theo
            # tuổi như trước.
            _last_sent[_OK_PREFIX + topic] = now
        else:
            # Chưa tới tay ai thì chưa tính là đã gửi — cho thử lại sau 5 phút.
            _last_sent[topic] = now - ttl_sec + 300.0
        _save_to_disk()
    return ok


def recently_sent(topic: str, ttl_sec: float = DEFAULT_TTL_SEC) -> bool:
    """Chủ đề `topic` ĐÃ gửi trong `ttl_sec` giây gần đây chưa.

    VÌ SAO CẦN — `once()` TRẢ `False` VÌ HAI LÝ DO KHÁC HẲN NHAU
    ============================================================
        · bị chặn vì TRÙNG — thư ĐÃ gửi rồi, mọi thứ đang chạy tốt
        · `sender()` trả `False` — thư KHÔNG gửi được (chưa cấu hình SMTP,
          `APP_ENV` khác PROD, hoặc SMTP lỗi)

    Một giá trị `False` duy nhất cho cả hai buộc bên gọi phải ĐOÁN, và ngày
    16/08/2026 nó đoán sai theo hướng tệ nhất: nhật ký VPS in

        📨 [Email] chỉ GHI LOG (APP_ENV=PROD, cần PROD để gửi thật)

    Câu này tự mâu thuẫn — nó vừa nói `APP_ENV=PROD` vừa đòi phải là PROD. Sự thật
    là thư khởi động đã gửi thành công 4 phút trước và lần này bị chặn vì trùng
    (`ttl_sec=600`). Người vận hành đọc dòng đó thì kết luận kênh email đang tắt,
    trong khi nó vẫn chạy — một báo động giả dẫn thẳng tới việc đi sửa một thứ
    không hỏng.

    Hàm này cho bên gọi phân biệt được hai trường hợp, để nói đúng chuyện đã xảy ra.
    """
    with _LOCK:
        _load_from_disk()
        return (time.time() - _last_sent.get(_OK_PREFIX + topic, 0.0)) < ttl_sec


def reset(topic: str) -> None:
    """Xoá mốc của một chủ đề để lần sau gửi ngay.

    Dùng cho cặp sự kiện ĐỐI XỨNG: khi kết nối trở lại thì xoá mốc "mất kết nối",
    để lần rớt kế tiếp báo ngay chứ không bị TTL của lần trước nuốt mất.
    """
    with _LOCK:
        _load_from_disk()
        # Xoá CẢ mốc thành công: để sót nó thì `recently_sent()` vẫn báo "vừa gửi"
        # sau khi đã reset, và bên gọi lại rơi vào đúng nhánh giải thích sai mà
        # `_OK_PREFIX` sinh ra để tránh.
        gone = [_last_sent.pop(k, None) for k in (topic, _OK_PREFIX + topic)]
        if any(g is not None for g in gone):
            _save_to_disk()
