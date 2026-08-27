import configparser
from pathlib import Path
import imaplib
import poplib
import email
import smtplib
import re
from email.header import decode_header
from email.utils import parsedate_to_datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import ssl

from . import db
from . import crypto


config_path = Path(__file__).with_name("email_config.ini")


DEFAULT_CONFIG = {
    "imap": {
        "server": "imap.gmail.com",
        "port": "993",
        "folder": "INBOX",
    },
    "pop": {
        "server": "pop.gmail.com",
        "port": "995",
    },
    "auth": {
        "user": "",
        "password": "",
    },
    "app": {
        "protocol": "imap",
        "days": "14",
    },
    "smtp": {
        "server": "smtp.gmail.com",
        "port": "465",
    },
}


def ensure_config():
    """
    Crea email_config.ini con la configuración por defecto
    únicamente si el archivo todavía no existe.
    """
    if config_path.exists():
        return

    initial_config = configparser.ConfigParser()
    initial_config.read_dict(DEFAULT_CONFIG)

    with config_path.open("w", encoding="utf-8") as f:
        initial_config.write(f)


# Crear configuración inicial si no existe.
ensure_config()

# Cargar configuración.
config = configparser.ConfigParser()
config.read(config_path)


def get_email_body(msg):
    body = ""
    is_html = False

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if content_type == "text/html" and "attachment" not in content_disposition:
                body = part.get_payload(decode=True).decode(
                    "utf-8",
                    errors="ignore",
                )
                is_html = True
                break

            elif content_type == "text/plain" and "attachment" not in content_disposition:
                if not body:
                    body = part.get_payload(decode=True).decode(
                        "utf-8",
                        errors="ignore",
                    )

    else:
        body = msg.get_payload(decode=True).decode(
            "utf-8",
            errors="ignore",
        )

        if msg.get_content_type() == "text/html":
            is_html = True

    return body, is_html


def decode_mime_words(s):
    if not s:
        return ""

    try:
        decoded_words = decode_header(s)
        res = []

        for word, encoding in decoded_words:
            if isinstance(word, bytes):
                res.append(
                    word.decode(
                        encoding or "utf-8",
                        errors="ignore",
                    )
                )
            else:
                res.append(word)

        return "".join(res)

    except Exception:
        return str(s)


class ImapEmail:
    def __init__(self) -> None:
        self.IMAP_SERVER = config.get(
            "imap",
            "server",
            fallback="imap.gmail.com",
        )
        self.IMAP_PORT = config.getint(
            "imap",
            "port",
            fallback=993,
        )
        self.USER = config.get(
            "auth",
            "user",
            fallback="",
        )
        self.PASS = config.get(
            "auth",
            "password",
            fallback="",
        )
        self.DAYS = config.getint(
            "app",
            "days",
            fallback=14,
        )

    def _connect(self):
        if not self.USER or not self.PASS:
            return None

        mail = imaplib.IMAP4_SSL(
            self.IMAP_SERVER,
            self.IMAP_PORT,
        )
        mail.login(
            self.USER,
            self.PASS,
        )
        return mail

    @staticmethod
    def _quote_mailbox(mailbox):
        escaped = str(mailbox).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def get_mailboxes(self):
        mail = None
        mailboxes = []

        try:
            mail = self._connect()
            if mail is None:
                return []

            status, lines = mail.list()
            if status != "OK":
                return []

            special_uses = {
                "\\Sent",
                "\\Drafts",
                "\\Junk",
                "\\Trash",
                "\\Archive",
                "\\All",
                "\\Important",
                "\\Flagged",
            }

            for line in lines or []:
                decoded = line.decode("utf-8", errors="replace")
                match = re.match(
                    r'^\((?P<attributes>[^)]*)\)\s+(?:"[^"]*"|NIL)\s+(?P<name>.+)$',
                    decoded,
                )
                if not match:
                    continue

                name = match.group("name").strip()
                if name.startswith('"') and name.endswith('"'):
                    name = name[1:-1].replace(r'\"', '"')

                attributes = set(match.group("attributes").split())
                if "\\Noselect" in attributes:
                    continue

                special_use = next(
                    (item for item in special_uses if item in attributes),
                    None,
                )
                mailboxes.append({
                    "name": name,
                    "special_use": special_use,
                })

            return mailboxes

        except Exception as e:
            print(f"Error listando mailboxes IMAP: {e}")
            return []

        finally:
            if mail is not None:
                try:
                    mail.logout()
                except Exception:
                    pass

    def get_emails(self, n_emails=5, mailbox="INBOX"):
        mail = None

        try:
            mail = self._connect()
            if mail is None:
                return

            status, _ = mail.select(self._quote_mailbox(mailbox))
            if status != "OK":
                return

            response, values = mail.response("UIDVALIDITY")
            uidvalidity = ""
            if response and values:
                value = values[0]
                if isinstance(value, bytes):
                    value = value.decode("ascii", errors="ignore")
                uidvalidity = str(value)

            # Buscar correos de las últimas N jornadas.
            date_since = (
                datetime.now() - timedelta(days=self.DAYS)
            ).strftime("%d-%b-%Y")

            status, data = mail.uid(
                "SEARCH",
                None,
                f'(SINCE "{date_since}")',
            )

            mail_ids = data[0].split() if status == "OK" and data else []
            if n_emails is not None:
                mail_ids = mail_ids[-n_emails:]

            print(
                status,
                len(mail_ids),
                "correos encontrados (IMAP)",
            )

            for mail_id in mail_ids:
                status, msg_data = mail.uid(
                    "FETCH",
                    mail_id,
                    "(FLAGS BODY.PEEK[])",
                )

                if status == "OK":
                    payload = next(
                        (
                            item for item in msg_data
                            if isinstance(item, tuple)
                            and len(item) > 1
                        ),
                        None,
                    )
                    if payload is None:
                        continue

                    metadata, raw_email = payload
                    is_read = b"\\Seen" in metadata

                    message = email.message_from_bytes(
                        raw_email
                    )

                    uid = mail_id.decode("ascii")

                    self._save_to_db(
                        uid,
                        message,
                        mailbox,
                        uidvalidity,
                        is_read,
                    )

        except Exception as e:
            print(f"Error IMAP: {e}")

        finally:
            if mail is not None:
                try:
                    mail.logout()
                except Exception:
                    pass

    def mark_as_read(self, mailbox, uid, uidvalidity=""):
        mail = None

        try:
            mail = self._connect()
            if mail is None:
                return False

            status, _ = mail.select(self._quote_mailbox(mailbox))
            if status != "OK":
                return False

            status, _ = mail.uid(
                "STORE",
                str(uid),
                "+FLAGS.SILENT",
                "(\\Seen)",
            )
            if status != "OK":
                return False

            db.mark_email_as_read(
                "imap",
                self.USER,
                mailbox,
                uidvalidity,
                uid,
            )
            return True

        except Exception as e:
            print(f"Error marcando correo IMAP como leído: {e}")
            return False

        finally:
            if mail is not None:
                try:
                    mail.logout()
                except Exception:
                    pass

    def _save_to_db(
        self,
        uid,
        message,
        mailbox="INBOX",
        uidvalidity="",
        is_read=False,
    ):
        subject = decode_mime_words(
            message.get("Subject", "")
        )

        sender = decode_mime_words(
            message.get("From", "")
        )

        date = decode_mime_words(
            message.get("Date", "")
        )

        body, is_html = get_email_body(
            message
        )

        # Desencriptar si corresponde.
        contact_key = db.get_contact_key(
            sender
        )

        if contact_key:
            body = crypto.decrypt_message(
                body.strip(),
                contact_key,
            )

        db.save_email(
            uid=uid,
            account=self.USER,
            sender=sender,
            subject=subject,
            date=date,
            body=body,
            protocol="imap",
            mailbox=mailbox,
            uidvalidity=uidvalidity,
            is_read=is_read,
        )


class PopEmail:
    def __init__(self) -> None:
        self.POP_SERVER = config.get(
            "pop",
            "server",
            fallback="pop.gmail.com",
        )

        self.POP_PORT = config.getint(
            "pop",
            "port",
            fallback=995,
        )

        self.USER = config.get(
            "auth",
            "user",
            fallback="",
        )

        self.PASS = config.get(
            "auth",
            "password",
            fallback="",
        )

        self.DAYS = config.getint(
            "app",
            "days",
            fallback=14,
        )

        self.mail = None

        if not self.USER or not self.PASS:
            return

        try:
            self.mail = poplib.POP3_SSL(
                self.POP_SERVER,
                self.POP_PORT,
            )

            self.mail.user(
                self.USER
            )

            self.mail.pass_(
                self.PASS
            )

        except Exception as e:
            print(
                f"Error iniciando POP: {e}"
            )

            if self.mail is not None:
                try:
                    self.mail.quit()
                except Exception:
                    pass
            self.mail = None

    def get_mails(self, n_emails=None):
        if not self.mail:
            return

        try:
            num_messages = len(
                self.mail.list()[1]
            )

            limit_date = (
                datetime.now()
                - timedelta(days=self.DAYS)
            )

            limit_date = limit_date.replace(
                tzinfo=None
            )

            uid_by_number = {}
            try:
                _, uid_lines, _ = self.mail.uidl()
                for line in uid_lines:
                    number, uid = line.split(maxsplit=1)
                    uid_by_number[int(number)] = uid.decode(
                        "ascii",
                        errors="replace",
                    )
            except Exception as e:
                print(f"UIDL no disponible, usando Message-ID: {e}")

            # Aplicar un límite únicamente si se solicita explícitamente.
            fetch_count = (
                num_messages
                if n_emails is None
                else min(num_messages, n_emails)
            )

            for i in range(
                num_messages - fetch_count,
                num_messages,
            ):
                response, lines, octets = self.mail.retr(
                    i + 1
                )

                raw_email = b"\r\n".join(
                    lines
                )

                message = email.message_from_bytes(
                    raw_email
                )

                # Filtrar por fecha localmente.
                date_str = message.get(
                    "Date"
                )

                if date_str:
                    try:
                        msg_date = parsedate_to_datetime(
                            date_str
                        ).replace(
                            tzinfo=None
                        )

                        if msg_date < limit_date:
                            continue

                    except Exception:
                        pass

                uid = uid_by_number.get(i + 1)
                if uid is None:
                    uid = message.get(
                        "Message-ID",
                        str(i + 1),
                    )

                self._save_to_db(
                    uid,
                    message,
                )

        except Exception as e:
            print(
                f"Error leyendo POP3: {e}"
            )

        finally:
            try:
                self.mail.quit()
            except Exception as e:
                print(f"Error cerrando POP3: {e}")
            self.mail = None

    def _save_to_db(self, uid, message):
        subject = decode_mime_words(
            message.get("Subject", "")
        )

        sender = decode_mime_words(
            message.get("From", "")
        )

        date = decode_mime_words(
            message.get("Date", "")
        )

        body, is_html = get_email_body(
            message
        )

        contact_key = db.get_contact_key(
            sender
        )

        if contact_key:
            body = crypto.decrypt_message(
                body.strip(),
                contact_key,
            )

        db.save_email(
            uid=uid,
            account=self.USER,
            sender=sender,
            subject=subject,
            date=date,
            body=body,
            protocol="pop",
            mailbox="INBOX",
            uidvalidity="",
            is_read=False,
        )


class SmtpSender:
    def __init__(self):
        self.SMTP_SERVER = config.get(
            "smtp",
            "server",
            fallback="smtp.gmail.com",
        )

        self.SMTP_PORT = config.getint(
            "smtp",
            "port",
            fallback=465,
        )

        self.USER = config.get(
            "auth",
            "user",
            fallback="",
        )

        self.PASS = config.get(
            "auth",
            "password",
            fallback="",
        )

    def send_email(
        self,
        to_email,
        subject,
        body_text,
    ):
        if not self.USER or not self.PASS:
            return False, "Faltan credenciales"

        # Encriptar cuerpo si tenemos clave de contacto.
        contact_key = db.get_contact_key(
            to_email
        )

        if contact_key:
            body_text = crypto.encrypt_message(
                body_text,
                contact_key,
            )

        msg = MIMEMultipart()

        msg["From"] = self.USER
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(
            MIMEText(
                body_text,
                "plain",
            )
        )

        context = ssl.create_default_context()

        try:
            with smtplib.SMTP_SSL(
                self.SMTP_SERVER,
                self.SMTP_PORT,
                context=context,
            ) as server:

                server.login(
                    self.USER,
                    self.PASS,
                )

                server.sendmail(
                    self.USER,
                    to_email,
                    msg.as_string(),
                )

            return True, "Enviado correctamente"

        except Exception as e:
            print(
                f"SMTP Error: {e}"
            )

            return False, str(e)


def update_config_file(config_data):
    for section, values in config_data.items():
        if not config.has_section(section):
            config.add_section(section)

        for key, value in values.items():
            config.set(
                section,
                key,
                str(value),
            )

    with config_path.open(
        "w",
        encoding="utf-8",
    ) as f:
        config.write(f)
