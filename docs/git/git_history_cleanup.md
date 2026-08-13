# Hướng dẫn Dọn dẹp Git History & Gom Commit vào Tag Gần Nhất

Tài liệu này hướng dẫn quy trình thu gom các commit lẻ/trôi nổi (fix bug nhỏ, sửa typo, cập nhật tài liệu...) sau khi phát hành phiên bản và **gộp (squash/amend) chúng trực tiếp vào Tag gần nhất**, giúp cho Git history luôn sạch gọn và chỉ lưu giữ các điểm mốc mốc quan trọng (các commit có gắn Tag).

---

## 🎯 Triết lý & Mục đích

- **Tránh Git History bị bẩn**: Sau khi vừa tạo/release Tag phiên bản, nếu phát sinh các chỉnh sửa nhỏ (sửa docs, chỉnh giao diện, fix lỗi nhỏ...), tránh tạo thêm các commit lặt vặt trôi nổi.
- **Gom về điểm mốc gần nhất**: Gom toàn bộ thay đổi nhỏ đó nhập làm một với commit của **Tag phiên bản gần nhất**.
- **Đồng bộ Lịch sử**: Giúp lịch sử repository luôn gọn gàng, rõ ràng và chuyên nghiệp trên cả Local và Remote.

---

## 🛠️ Hướng dẫn Quy trình Gom Commit

> **Lưu ý**: Thay `<tag_gần_nhất>` bằng Tag phát hành gần đây nhất của bạn (ví dụ: `v6.1.6`, `v6.2.0`...).

### 1. Gom các commit phát sinh sau Tag gần nhất (Soft Reset & Amend)

1. **Khôi phục trạng thái commit về Tag gần nhất (vẫn giữ nguyên các thay đổi trong Staged):**

   ```bash
   git reset --soft <tag_gần_nhất>
   ```

2. **Gộp toàn bộ thay đổi mới vào commit của Tag gần nhất:**

   ```bash
   # Nếu muốn giữ nguyên message commit của Tag:
   git commit --amend --no-edit

   # Hoặc nếu muốn cập nhật lại mô tả nội dung cho phù hợp với các sửa đổi mới:
   git commit --amend -m "release: <tag_gần_nhất> - <mô_tả_tổng_hợp_nội_dung>"
   ```

3. **Cập nhật lại Tag trỏ vào commit mới:**

   ```bash
   git tag -fa <tag_gần_nhất> -m "release: <tag_gần_nhất> - <mô_tả_tổng_hợp_nội_dung>"
   ```

4. **Push cập nhật lên Remote Repository:**

   ```bash
   # Force push nhánh main/working branch
   git push origin main --force-with-lease

   # Force push cập nhật Tag lên Remote
   git push origin <tag_gần_nhất> --force
   ```

---

## 🤖 Quy định thực thi tự động (Cho AI / Agent)

Khi người dùng yêu cầu gom các commit trôi nổi / làm sạch lịch sử Git:

1. **Xác định Tag gần nhất** (`<tag_gần_nhất>`).
2. **Gom commit**: Thực hiện `git reset --soft <tag_gần_nhất>`, sau đó `git commit --amend` (hoặc tạo commit squashed chứa toàn bộ thay đổi phát sinh).
3. **Cập nhật Tag**: Cập nhật lại `<tag_gần_nhất>` bằng `git tag -fa <tag_gần_nhất>`.
4. **Push làm sạch Remote**: Tự động push cả branch và Tag lên remote:
   ```bash
   git push origin main --force-with-lease
   git push origin <tag_gần_nhất> --force
   ```

---

## 🔄 Mẹo cho công việc hàng ngày (Best Practice)

Khi bạn vừa thực hiện chỉnh sửa nhỏ ngay sau khi tạo Tag:

- Có thể dùng ngay `git commit --amend` và cập nhật lại Tag trước khi push.
- Giữ lịch sử Git theo từng cột mốc Tag rõ ràng, không để dư thừa commit trung gian trôi nổi.
