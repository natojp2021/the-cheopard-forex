"""`shared/` — Shared Production Libraries (tầng nền dùng chung).

TẦNG NÀY LÀ GÌ
--------------
Thư viện production **không có state nghiệp vụ riêng**, được dùng bởi CẢ hai
phía: live runtime (`core/`, `live_strategies/`, `ai/`, `utils/`) và nghiên cứu
(`research/`, `scratch/`). Ví dụ: chỉ báo kỹ thuật, resample khung thời gian,
schema feature ML, xác minh model bundle, gửi email, tính macro.

VÌ SAO TẦNG NÀY TỒN TẠI (refactor 27/07)
----------------------------------------
Trước refactor, toàn bộ các module này nằm trong `research/`, khiến live runtime
có **57 import trực tiếp vào `research/`** — vi phạm rule cứng của
`docs/optimize/cheopard-architecture-boundary.md`:

    "Production runtime must not import directly from `research/` or `scratch/`."

Vi phạm này không phải lỗi hình thức: nó khiến rule trên **không thể enforce**
(mọi import research đều trông "hợp lệ" vì thật sự cần thiết), nên cũng không
phát hiện được import research THẬT SỰ sai nếu có. Sau khi tách, rule trở thành
kiểm tra được — xem `tests/test_architecture_boundary.py`.

QUY TẮC CHO TẦNG NÀY
--------------------
Module trong `shared/` ĐƯỢC:
  - import stdlib, thư viện ngoài (pandas/numpy/polars/...)
  - import `src.python.utils.logger`
  - import `src.python.shared.paths` cho MỌI hằng số đường dẫn

Module trong `shared/` KHÔNG ĐƯỢC:
  - import `src.python.core.config`                   (xem lý do ngay dưới)
  - import `src.python.research.*` hoặc `scratch/*`   (ngược hướng phân tầng)
  - import `src.python.live_strategies.*`             (tầng trên)
  - import `src.python.core.broker.*`, `core.intelligence.*`, `ai.*`
  - giữ state nghiệp vụ (vị thế, risk, lệnh) — state thuộc `core/`
  - gọi broker / gửi lệnh

SỬA 29/07 — trước đây dòng trên ghi `core.config` là ĐƯỢC PHÉP ("hằng số đường
dẫn"). Nay CẤM, vì `core/config.py` không phải file hằng số: import nó sẽ
monkeypatch toàn bộ `MetaTrader5`, `load_env_file()`,
`install_global_exception_handler()` (kéo theo `email_reporter.py` 2.400 dòng)
và `AccountController.initialize()` (tạo thư mục state runtime). Đo được:
`shared/macro/features.py` chỉ cần biết thư mục gốc để đọc một parquet nhưng
import nó sẽ khởi tạo MT5 + account.

`shared/paths.py` giải đúng nhu cầu đó bằng stdlib thuần, không side effect.
Cưỡng chế bằng `tests/test_architecture_import_hygiene_20260729.py::
test_shared_khong_import_core_config` — nên nếu ai đọc tài liệu này rồi viết
code theo bản CŨ thì test sẽ đỏ ngay, không phải đợi phát hiện bằng mắt.

Nếu một module cần một trong các thứ bị cấm ở trên thì nó KHÔNG thuộc `shared/`.

`execution_rules/` — DỜI VÀO ĐÂY 28/07 (`refactor.md` §1)
---------------------------------------------------------
Trước 28/07 package này là `src/python/execution_core/`, tức NGANG HÀNG với `core/`
nhưng lại chứa logic execution — đúng thứ §1 gọi là "nhiều lớp kiến trúc song
song": người đọc không biết `core/execution/` và `execution_core/` khác nhau ở đâu,
và tên `execution_core` gợi ý "lõi thực thi production" trong khi 5/8 module chỉ
dùng cho backtest.

Nó thuộc `shared/` vì thoả ĐÚNG định nghĩa tầng này: chỉ chứa HÀM THUẦN (không
I/O, không MT5, không state), và được dùng bởi CẢ backtest LẪN production. Sau khi
dời, bản đồ tầng không còn package nào ngang hàng `core/` mà chứa logic execution.

Ranh giới được enforce bằng
`tests/test_refactor_md_compliance_20260728.py` — production chỉ được import 3
module đã duyệt (`day_risk`, `exit_rules`, `pyramid_policy`); `entry_filters`/
`entry_policy` là backtest-only và import chúng từ production sẽ FAIL, vì đó đúng
là kịch bản "hai nơi cùng quyết định có được vào lệnh" mà §1 cảnh báo.

ĐẶT TÊN — LƯU Ý QUAN TRỌNG
--------------------------
Package này CỐ Ý không đặt tên `platform/`: `live_server.py` được khởi chạy
bằng `python src/python/live_server.py`, khiến Python đặt `src/python/` vào
`sys.path[0]`; một package tên `platform` ở đó sẽ SHADOW module stdlib
`platform`, mà `core/runtime_meta.py`, `research/reports/run_manifest.py`,
`research/ml/train_offline_model.py` và `shared/model_bundle.py` đều
`import platform` thật. Đó là lỗi làm sập live, không phải chuyện thẩm mỹ.
"""
