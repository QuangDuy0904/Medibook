# Nhật ký tiến độ: Medibook (Web đặt lịch khám bệnh)

Công nghệ: Django, PostgreSQL, Bootstrap. Repo: https://github.com/QuangDuy0904/Medibook

---

## 2026-11-18

### Đã làm

- Phân tích SRS, chốt kiến trúc 5 app: `accounts`, `clinics`, `appointments`, `medical_records`, `analytics`.
- Lập kế hoạch triển khai 10 giai đoạn (0 đến 9), có bảng theo dõi tiến độ.
- **Giai đoạn 0**: khởi tạo project `medibook`, dùng `.venv` có sẵn, cài thư viện, tạo 5 app, đặt hằng số nghiệp vụ `BOOKING_RULES` trong `settings.py` (BR-02 đến BR-05).
- **0.1b**: cài PostgreSQL, tạo database `medibook` bằng pgAdmin, cấu hình `.env` (`SECRET_KEY`, thông tin DB).
- **1.1**: model `User` tùy chỉnh (role, phone, email, `booking_locked_until`).
- **1.2**: model `PatientProfile` (hồ sơ bản thân và người thân), ràng buộc mỗi tài khoản chỉ có 1 hồ sơ "Bản thân".
- **1.3**: đăng ký, đăng nhập bằng SĐT hoặc email (`IdentifierBackend`), tự tạo hồ sơ "Bản thân" khi đăng ký, giao diện Bootstrap.
- Đưa code lên GitHub, `.env` được chặn bởi `.gitignore` nên không bị lộ.
- **1.4**: trang quản lý hồ sơ khám cho bệnh nhân: xem danh sách, thêm, sửa, xóa hồ sơ người thân; hồ sơ "Bản thân" không xóa được và không đổi được quan hệ; mỗi người chỉ truy cập được hồ sơ của mình (người khác gõ URL sẽ ra 404).
- Chuyển cấu hình `settings.py` từ SQLite sang PostgreSQL, đọc thông tin từ `.env`, migrate lại vào PostgreSQL.
  **2.1**: model `Specialty` (chuyên khoa), `DoctorProfile` (học hàm, kinh nghiệm, phí khám, số phút mỗi khung).
- **2.2**: model `WorkSchedule` (ngày, ca sáng/chiều), `DayOff` (nghỉ phép, báo bận).
- **2.3**: `TimeSlot` và hàm `generate_slots()` tự chia ca làm việc thành khung 15 hoặc 30 phút; khung giờ bị ẩn khi bác sĩ báo nghỉ (FR-08).
- **2.4, 2.5**: trang tìm bác sĩ (lọc theo tên, chuyên khoa, ngày, ca) và trang chi tiết bác sĩ hiển thị lịch trống 14 ngày tới.
- Phí khám hiển thị dạng `200.000 VNĐ`; form tạo user trong admin có thêm họ tên.

### Lỗi gặp và cách sửa

| Lỗi                                                     | Nguyên nhân                                                        | Cách sửa                                                            |
| ------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------- |
| pip gỡ Django 6.1.2                                     | Lệnh cài ghim `django>=5.0,<6`                                     | Cài lại bản đang dùng: `pip install "django==6.1.2"`                |
| Chưa có PostgreSQL                                      | Nhầm pgAdmin (công cụ giao diện) với server                        | Cài PostgreSQL, tạo database, điền `.env`                           |
| `fields.E304` (xung đột `auth.User` và `accounts.User`) | Thiếu dòng `AUTH_USER_MODEL = "accounts.User"` trong `settings.py` | Thêm dòng đó rồi chạy lại `check`                                   |
| VS Code báo `Import "django.db" could not be resolved`  | Chọn sai Python interpreter (không phải `.venv`)                   | `Python: Select Interpreter` rồi trỏ tới `.venv\Scripts\python.exe` |
| `remote origin already exists`                          | Lỡ chạy nguyên dòng mẫu `ten-ban/medibook.git`                     | `git remote set-url origin <địa chỉ đúng>`                          |

| `migrate` tạo bảng trong `db.sqlite3` thay vì PostgreSQL | `settings.py` vẫn dùng `DATABASES` mặc định (SQLite) | Thay khối `DATABASES` bằng cấu hình PostgreSQL đọc từ `.env`, chạy lại `migrate` | |
Form "Add user" trong admin không có ô họ tên | `add_fieldsets` chưa khai báo `first_name`, `last_name` | Thêm hai trường vào `add_fieldsets` trong `accounts/admin.py` |

### Bài học

- Phải khai báo `AUTH_USER_MODEL` trước lần `migrate` đầu tiên khi dùng User tùy chỉnh.
- Không bao giờ đưa `.env` lên GitHub; luôn kiểm tra bằng `git check-ignore -v .env`.
- Commit sau mỗi phần nhỏ chạy được để lịch sử thể hiện quá trình làm việc.

### Việc tiếp theo

- Giai đoạn 2: `Specialty`, `DoctorProfile`, `WorkSchedule`, `DayOff`, sinh `TimeSlot`.
- Giai đoạn 3: đặt lịch, chống trùng slot (BR-01).

---

## Bảng tiến độ tổng

| #   | Việc                                                      | Trạng thái                     |
| --- | --------------------------------------------------------- | ------------------------------ |
| 0   | Khởi tạo project, PostgreSQL, 5 app                       | ✅                             |
| 1.1 | Custom `User`                                             | ✅                             |
| 1.2 | `PatientProfile`                                          | ✅                             |
| 1.3 | Đăng ký / đăng nhập SĐT hoặc email                        | 🔄 Đã viết code, đang chạy thử |
| 1.4 | Trang hồ sơ và người thân                                 | ✅                             |
| 2   | Clinics: chuyên khoa, bác sĩ, lịch làm việc, tìm kiếm     | ✅                             |
| 3   | Appointments: đặt lịch, chống trùng slot, hủy, trạng thái | ⬜                             |
| 4   | Lễ tân: check-in, đặt lịch trực tiếp                      | ⬜                             |
| 5   | Bác sĩ: danh sách bệnh nhân, ghi chú sau khám             | ⬜                             |
| 6   | Tự động hóa: No-show, khóa 30 ngày (Celery)               | ⬜                             |
| 7   | Phân quyền theo vai trò                                   | ⬜                             |
| 8   | Báo cáo và thống kê                                       | ⬜                             |
| 9   | Kiểm thử, dữ liệu mẫu, README                             | ⬜                             |

Chú thích: ✅ xong, 🔄 đang làm, ⬜ chưa làm.
