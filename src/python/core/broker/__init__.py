"""Hạ tầng NÓI CHUYỆN VỚI BROKER — ngắt mạch và máy trạng thái lệnh.

ĐỔI TÊN TỪ `core/execution/` NGÀY 15/08/2026
============================================
Repo có hai gói tên `execution` và chúng làm việc khác hẳn nhau:

    src/python/execution/       ĐƯỜNG LIVE của hệ Forex — order_plan, order_router,
                                entry_gate, portfolio_sizing, disaster_stop…
    src/python/core/execution/  hạ tầng port từ hệ XAUUSD

Hai tên giống nhau ở hai tầng khác nhau là đúng loại nhầm lẫn đã nêu trong
`shared/__init__.py`: người đọc không biết gói nào là đường ra lệnh thật, và người
sửa dễ thêm hằng số vào nhầm gói.

Gói này nay chỉ còn ĐÚNG hai module, và cả hai đều trả lời cùng một câu hỏi —
"nói chuyện với broker thế nào cho an toàn":

    circuit_breaker.py      ngắt mạch khi broker từ chối liên tiếp; phân loại
                            retcode FATAL (không tự khỏi) và RETRIABLE (tạm thời)
    order_state_machine.py  vòng đời một lệnh + khoá idempotent, chống gửi trùng
                            khi tiến trình chết giữa lúc chờ broker trả lời

Ba module còn lại đã bị XOÁ cùng ngày, sau khi đối chiếu với hệ XAUUSD:

    entry_pipeline.py             1.476 dòng — đường vào lệnh của XAU. Hệ Forex đi
                                  qua `execution/order_plan.py`, nên chỉ còn 2 hàm
                                  hiển thị được gọi, và chúng nằm trong nhánh đã
                                  chết vì thiếu `regime_engine`.
    position_execution_service.py   898 dòng — KHÔNG import được (thiếu
                                  `position_lifecycle`, `management_command_log`,
                                  `shared/execution_rules`). Nút break-even trên
                                  giao diện gọi nó và im lặng hỏng suốt.
    signal_intent.py                241 dòng — không nơi nào import.
"""
