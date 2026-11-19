from django.conf import settings


class SeparateAdminSessionMiddleware:
    """Tách phiên đăng nhập của /admin/ khỏi phần còn lại của website.

    - Request vào /admin/: đọc cookie 'admin_sessionid' thay cho 'sessionid'.
    - Response từ /admin/: đổi tên cookie phiên thành 'admin_sessionid', giới hạn path /admin/.
    Phải đặt TRƯỚC SessionMiddleware trong MIDDLEWARE.
    """

    ADMIN_PREFIX = "/admin/"
    ADMIN_COOKIE = "admin_sessionid"

    def __init__(self, get_response):
        self.get_response = get_response
        self.default_name = settings.SESSION_COOKIE_NAME

    def __call__(self, request):
        is_admin = request.path.startswith(self.ADMIN_PREFIX)

        if is_admin:
            value = request.COOKIES.get(self.ADMIN_COOKIE)
            if value is not None:
                request.COOKIES[self.default_name] = value
            else:
                # Không cho phiên của trang bệnh nhân lọt vào admin
                request.COOKIES.pop(self.default_name, None)

        response = self.get_response(request)

        if is_admin and self.default_name in response.cookies:
            old = response.cookies.pop(self.default_name)
            response.cookies[self.ADMIN_COOKIE] = old.value
            new = response.cookies[self.ADMIN_COOKIE]
            for attr in ("expires", "max-age", "domain", "secure", "httponly", "samesite"):
                if old[attr]:
                    new[attr] = old[attr]
            new["path"] = self.ADMIN_PREFIX
        return response