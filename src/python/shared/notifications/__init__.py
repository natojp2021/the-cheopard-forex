"""Kênh thông báo NGOÀI giao diện — email cho người vận hành khi họ không ngồi
trước màn hình.

Cố ý RỖNG: `emails.py` kéo theo `core.config` (để đọc SMTP và `BOT_NAME`), nên
import ở đây sẽ tạo vòng import cho mọi module `shared/` khác. Bên gọi import
thẳng `shared.notifications.emails`.
"""
