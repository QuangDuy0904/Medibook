# Nhật ký tiến độ: Medibook (Web đặt lịch khám bệnh)

Công nghệ: Django 6, PostgreSQL, Bootstrap. Repo: https://github.com/QuangDuy0904/Medibook

Quyết định thiết kế: hệ thống phục vụ **một bệnh viện duy nhất** (đúng SRS). "Phòng khám" trong SRS hiểu là các phòng khám bệnh trong cùng bệnh viện, nên không có model cơ sở hay chi nhánh.

---

## 2026-11-19

### Đã làm

- **1.4**: trang quản lý hồ sơ khám cho bệnh nhân: xem, thêm, sửa, xóa hồ sơ người thân; hồ sơ "Bản thân" không xóa được và không đổi được quan hệ; mỗi người chỉ truy cập được hồ sơ của mình (gõ URL hồ sơ người khác sẽ ra 404).
- Chuyển `settings.py` từ SQLite sang PostgreSQL, đọc thông tin từ `.env`, migrate lại.
- **2.1**: model `Specialty` (chuyên khoa), `DoctorProfile` (học hàm, kinh nghiệm, phí khám, số phút mỗi khung).
- **2.2**: model `WorkSchedule` (ngày, ca sáng/chiều), `DayOff` (nghỉ phép, báo bận).
- **2.3**: `TimeSlot` và hàm `generate_slots()` tự chia ca làm việc thành khung 15 hoặc 30 phút; khung giờ bị ẩn khi bác sĩ báo nghỉ (FR-08).
- **2.4, 2.5**: trang tìm bác sĩ (lọc theo tên, chuyên khoa, ngày, ca) và trang chi tiết bác sĩ hiển thị lịch trống 14 ngày tới.
- **3.1 đến 3.5**: model `Appointment` với `UniqueConstraint` chống đặt trùng slot (BR-01); sinh mã hẹn duy nhất (FR-10); service `book_appointment` (khóa dòng, kiểm tra BR-01, BR-02, BR-03, khóa tài khoản); `cancel_appointment`, `reschedule_appointment` (hủy rồi đặt mới trong một transaction); máy trạng thái FR-12; có test.
- **3.6, 3.7**: hoàn tất chạy thử luồng đặt lịch trên web, trang "Lịch hẹn của tôi" (xem, hủy, đổi giờ), mã QR sinh tức thời.
- **4.1, 4.3**: trang quầy tiếp tân (`/reception/`): check-in nhanh bằng quét mã QR hoặc nhập mã hẹn (`APT-...`), cấp số thứ tự vào phòng khám, lọc và điều phối hàng đợi theo bác sĩ/ngày/ca; ẩn mục "Lịch hẹn của tôi" trên thanh topbar đối với nhân viên tiếp tân.
- **4.2** (đã viết code, đang chạy thử): luồng tạo nhanh hồ sơ và đặt lịch trực tiếp cho khách vãng lai tại quầy (FR-14).
- **5.1, 5.2, 5.3**: khu vực bác sĩ: xem danh sách bệnh nhân theo ca khám, chuyển trạng thái `IN_CONSULTATION` $\rightarrow$ `COMPLETED`, nhập chẩn đoán sơ bộ và lời dặn sau khám (`ConsultationNote`), bệnh nhân xem lại lịch sử khám (FR-15, FR-16).
- **5.4**: trang quản lý lịch làm việc cho bác sĩ (`/doctor/schedule/`): tạo ca làm việc sinh tự động khung giờ (FR-07) và đăng ký báo nghỉ đột xuất/nghỉ phép, tự động ẩn khung giờ trống và hủy các cuộc hẹn trùng lịch nghỉ (FR-08).
- **6.1, 6.2**: tác vụ tự động quét các cuộc hẹn quá giờ 15 phút chưa check-in để chuyển `NO_SHOW` và nhả slot (BR-04); tự động khóa quyền đặt lịch 30 ngày nếu có từ 2 lần `NO_SHOW` trong 30 ngày (BR-05).
- **6.3**: gửi email thông báo hủy lịch tự động khi bác sĩ báo nghỉ đột xuất (đã chạy thử thành công) và gửi email nhắc lịch trước 24 giờ kèm cờ `reminder_sent_at` chống gửi trùng (đã viết code, đang chạy thử).
- Tạo custom console email backend (`ReadableConsoleEmailBackend`) trong `MAILERS` để giải mã tiêu đề và nội dung tiếng Việt in thẳng ra terminal khi debug.
- Phí khám hiển thị dạng `200.000 VNĐ`; form tạo user trong admin có thêm họ tên.
- Đổi múi giờ sang `Asia/Ho_Chi_Minh`, ngôn ngữ tiếng Việt.
- Tách phiên đăng nhập của `/admin/` khỏi trang bệnh nhân bằng middleware (cookie `admin_sessionid` riêng), có test.

### Lỗi gặp và cách sửa

| Lỗi                                                                                       | Nguyên nhân                                                                         | Cách sửa                                                                                         |
| ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `migrate` tạo bảng trong `db.sqlite3` thay vì PostgreSQL                                  | `settings.py` vẫn dùng `DATABASES` mặc định (SQLite)                                | Thay khối `DATABASES` bằng cấu hình PostgreSQL đọc từ `.env`, chạy lại `migrate`                 |
| Form "Add user" trong admin không có ô họ tên                                             | `add_fieldsets` chưa khai báo `first_name`, `last_name`                             | Thêm hai trường vào `add_fieldsets` trong `accounts/admin.py`                                    |
| `TemplateDoesNotExist` khi đổi giờ và xem "Lịch hẹn của tôi"                              | Đặt sai tên file: `rescheule.html` (thiếu chữ d), `card.html` (thiếu dấu gạch dưới) | Đổi thành `reschedule.html` và `_card.html`                                                      |
| Khung giờ lệch 7 tiếng                                                                    | `TIME_ZONE` mặc định là UTC                                                         | Đổi sang `Asia/Ho_Chi_Minh`, xóa và sinh lại khung giờ                                           |
| Đăng nhập admin kéo theo đăng nhập trang bệnh nhân (và ngược lại)                         | Dùng chung một cookie `sessionid`                                                   | Middleware tách cookie `admin_sessionid` cho `/admin/`, đặt trước `SessionMiddleware`            |
| Test tách phiên fail ở `assertIn("admin_sessionid", ...)`                                 | Middleware chưa được đăng ký hoặc đặt sau `SessionMiddleware`                       | Đặt đúng thứ tự trong `MIDDLEWARE`; viết lại test kiểm tra đúng người dùng thay vì chỉ mã trả về |
| `PermissionDenied` khi vào `/reception/`                                                  | Tài khoản superuser mặc định có `role = PATIENT`                                    | Đổi `role` sang `RECEPTIONIST` trong admin và mở riêng tab ẩn danh để test luồng lễ tân          |
| Nội dung email in ra terminal bị mã hóa Base64 khó đọc                                    | Django mặc định encode `utf-8` sang Base64 khi xuất console                         | Viết `ReadableConsoleEmailBackend` giải mã header và body tiếng Việt                             |
| `ImproperlyConfigured: Deprecated email settings are not allowed when MAILERS is defined` | Django 6 dùng cấu hình `MAILERS` mới, xung đột với `EMAIL_BACKEND` cũ               | Xóa `EMAIL_BACKEND` và khai báo backend trong `MAILERS["default"]["BACKEND"]`                    |

### Bài học

- Phải khai báo `AUTH_USER_MODEL` trước lần `migrate` đầu tiên khi dùng User tùy chỉnh.
- Ràng buộc chống trùng slot phải loại cả `CANCELLED` lẫn `NO_SHOW` khỏi điều kiện unique, nếu không slot không thể mở lại.
- Khóa dòng (`select_for_update`) trước khi kiểm tra và đếm, để hai request song song không qua mặt nhau.
- Test qua chưa chắc đúng: hai test cũ vẫn "OK" khi middleware chưa chạy, nên phải kiểm tra đúng người dùng đang đăng nhập.
- Tên file template phải khớp tuyệt đối với tên trong view.
- Django 6 thay `EMAIL_BACKEND` bằng dictionary `MAILERS`; không khai báo song song cả hai.

### Việc tiếp theo

- Hoàn tất chạy thử **4.2** (đặt lịch khách vãng lai) và **6.3** (email nhắc lịch trước 24 giờ).
- **Giai đoạn 7**: rà soát và khóa chặt phân quyền theo vai trò (`PATIENT`, `DOCTOR`, `RECEPTIONIST`, `ADMIN`) trên toàn bộ view/URL.
- **Giai đoạn 8**: trang báo cáo & thống kê lượt khám, tỷ lệ vắng mặt (FR-17, FR-18).
- **Giai đoạn 9**: kiểm thử đồng thời (Concurrency), lệnh tạo dữ liệu mẫu và hoàn thiện `README.md`.

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

### Lỗi gặp và cách sửa

| Lỗi                                                     | Nguyên nhân                                                        | Cách sửa                                                            |
| ------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------- |
| pip gỡ Django 6.1.2                                     | Lệnh cài ghim `django>=5.0,<6`                                     | Cài lại bản đang dùng: `pip install "django==6.1.2"`                |
| Chưa có PostgreSQL                                      | Nhầm pgAdmin (công cụ giao diện) với server                        | Cài PostgreSQL, tạo database, điền `.env`                           |
| `fields.E304` (xung đột `auth.User` và `accounts.User`) | Thiếu dòng `AUTH_USER_MODEL = "accounts.User"` trong `settings.py` | Thêm dòng đó rồi chạy lại `check`                                   |
| VS Code báo `Import "django.db" could not be resolved`  | Chọn sai Python interpreter (không phải `.venv`)                   | `Python: Select Interpreter` rồi trỏ tới `.venv\Scripts\python.exe` |
| `remote origin already exists`                          | Lỡ chạy nguyên dòng mẫu `ten-ban/medibook.git`                     | `git remote set-url origin <địa chỉ đúng>`                          |

### Bài học

- Không bao giờ đưa `.env` lên GitHub; luôn kiểm tra bằng `git check-ignore -v .env`.
- Commit sau mỗi phần nhỏ chạy được để lịch sử thể hiện quá trình làm việc.

---

## Bảng tiến độ tổng

| #        | Việc                                                                   | Trạng thái                     |
| -------- | ---------------------------------------------------------------------- | ------------------------------ |
| 0        | Khởi tạo project, PostgreSQL, 5 app                                    | ✅                             |
| 1        | Accounts: User, hồ sơ bệnh nhân, đăng ký/đăng nhập, quản lý người thân | ✅                             |
| 2        | Clinics: chuyên khoa, bác sĩ, lịch làm việc, tìm kiếm, lịch trống      | ✅                             |
| 3        | Appointment: đặt/hủy/đổi lịch, máy trạng thái, QR, test                | ✅                             |
| 4.1, 4.3 | Lễ tân: check-in mã hẹn/QR, cấp số thứ tự, hàng đợi                    | ✅                             |
| 4.2      | Lễ tân: đặt lịch cho khách vãng lai                                    | 🔄 Đã viết code, đang chạy thử |
| 5        | Bác sĩ: ca khám, ghi chú sau khám, lịch sử, tạo lịch & báo nghỉ (5.4)  | ✅                             |
| 6.1, 6.2 | Tự động hóa: No-show tự động, khóa 30 ngày                             | ✅                             |
| 6.3      | Email hủy lịch khi báo nghỉ (✅) & email nhắc lịch trước 24 giờ (🔄)   | 🔄 Đang chạy thử nhắc lịch     |
| 7        | Phân quyền chặt theo vai trò                                           | ⬜                             |
| 8        | Báo cáo và thống kê                                                    | ⬜                             |
| 9        | Kiểm thử (gồm test đồng thời), dữ liệu mẫu, README                     | ⬜                             |

Chú thích: ✅ xong, 🔄 đang làm, ⬜ chưa làm.
