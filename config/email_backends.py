from email.header import decode_header
from django.core.mail.backends.console import EmailBackend


class ReadableConsoleEmailBackend(EmailBackend):
    def write_message(self, message):
        msg = message.message()
        # Giải mã tiêu đề (Subject)
        subject_parts = decode_header(msg["Subject"] or "")
        subject = "".join(
            part.decode(enc or "utf-8") if isinstance(part, bytes) else part
            for part, enc in subject_parts
        )
        # Giải mã nội dung (Body)
        body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

        self.stream.write("=" * 60 + "\n")
        self.stream.write(f"From   : {msg['From']}\n")
        self.stream.write(f"To     : {msg['To']}\n")
        self.stream.write(f"Subject: {subject}\n")
        self.stream.write("-" * 60 + "\n")
        self.stream.write(f"{body}\n")
        self.stream.write("=" * 60 + "\n")