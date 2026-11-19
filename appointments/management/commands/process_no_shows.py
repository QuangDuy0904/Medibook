import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from appointments.services import process_overdue_appointments, send_due_reminders


class Command(BaseCommand):
    help = ("Quét định kỳ: đánh dấu vắng mặt và khóa tài khoản (BR-04, BR-05), "
            "gửi email nhắc lịch (6.3).")

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true",
                            help="Chạy liên tục thay vì chạy một lần")
        parser.add_argument("--interval", type=int, default=60,
                            help="Số giây giữa hai lần quét khi dùng --loop")

    def handle(self, *args, **options):
        try:
            while True:
                no_shows = process_overdue_appointments()
                reminders = send_due_reminders()
                if no_shows or reminders:
                    stamp = timezone.localtime().strftime("%H:%M:%S")
                    self.stdout.write(
                        f"[{stamp}] Vắng mặt: {no_shows} · Email nhắc đã gửi: {reminders}")
                if not options["loop"]:
                    break
                time.sleep(options["interval"])
        except KeyboardInterrupt:
            self.stdout.write("Đã dừng.")