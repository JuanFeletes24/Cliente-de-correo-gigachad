import configparser
from pathlib import Path
import imaplib
import poplib
import email
import smtplib
from email.header import decode_header
from email.utils import parsedate_to_datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import ssl

from . import db
from . import crypto

config_path = Path(__file__).with_name("email_config.ini")
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
                body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                is_html = True
                break
            elif content_type == "text/plain" and "attachment" not in content_disposition:
                if not body:
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
    else:
        body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
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
                res.append(word.decode(encoding or 'utf-8', errors='ignore'))
            else:
                res.append(word)
        return "".join(res)
    except Exception:
        return str(s)


class ImapEmail:
    def __init__(self) -> None:
        self.IMAP_SERVER = config.get("imap", "server", fallback="imap.gmail.com")
        self.IMAP_PORT = config.getint("imap", "port", fallback=993)
        self.USER = config.get("auth", "user", fallback="")
        self.PASS = config.get("auth", "password", fallback="")
        self.DAYS = config.getint("app", "days", fallback=14)
        print(self.IMAP_PORT, self.IMAP_SERVER)

    def get_emails(self, n_emails=5):
        if not self.USER or not self.PASS:
            return
        
        try:
            mail = imaplib.IMAP4_SSL(self.IMAP_SERVER, self.IMAP_PORT)
            mail.login(self.USER, self.PASS)
            mail.select("INBOX")
            
            # Buscar correos de las últimas 2 semanas
            date_since = (datetime.now() - timedelta(days=self.DAYS)).strftime("%d-%b-%Y")
            status, data = mail.search(None, f'(SINCE "{date_since}")')
            
            mail_ids = data[0].split()
            print(status, len(mail_ids), "correos encontrados (IMAP)")
            
            for mail_id in mail_ids:
                status, msg_data = mail.fetch(mail_id, "(RFC822)")
                if status == "OK":
                    raw_email = msg_data[0][1]
                    message = email.message_from_bytes(raw_email)
                    
                    uid = mail_id.decode()
                    self._save_to_db(uid, message)
                    
            mail.logout()
        except Exception as e:
            print(f"Error IMAP: {e}")

    def _save_to_db(self, uid, message):
        subject = decode_mime_words(message.get("Subject", ""))
        sender = decode_mime_words(message.get("From", ""))
        date = decode_mime_words(message.get("Date", ""))
        body, is_html = get_email_body(message)
        
        # Desencriptar si corresponde
        contact_key = db.get_contact_key(sender)
        if contact_key:
            body = crypto.decrypt_message(body.strip(), contact_key)

        db.save_email(uid, self.USER, sender, subject, date, body, is_new=1)


class PopEmail:
    def __init__(self) -> None:
        self.POP_SERVER = config.get("pop", "server", fallback="pop.gmail.com")
        self.POP_PORT = config.getint("pop", "port", fallback=995)
        self.USER = config.get("auth", "user", fallback="")
        self.PASS = config.get("auth", "password", fallback="")
        self.DAYS = config.getint("app", "days", fallback=14)
        print(self.POP_PORT, self.POP_SERVER)
        try:
            self.mail = poplib.POP3_SSL(self.POP_SERVER, self.POP_PORT)
            self.mail.user(self.USER)
            self.mail.pass_(self.PASS)
        except Exception as e:
            print(f"Error iniciando POP: {e}")
            self.mail = None

    def get_mails(self, n_emails=5):
        if not self.mail:
            return
            
        try:
            num_messages = len(self.mail.list()[1])
            limit_date = datetime.now() - timedelta(days=self.DAYS)
            limit_date = limit_date.replace(tzinfo=None)
            
            fetch_count = min(num_messages, 50)  # Evitar descargar miles por defecto
            
            for i in range(num_messages - fetch_count, num_messages):
                response, lines, octets = self.mail.retr(i + 1)
                raw_email = b"\r\n".join(lines)
                message = email.message_from_bytes(raw_email)
                
                # Filtrar por fecha localmente
                date_str = message.get("Date")
                if date_str:
                    try:
                        msg_date = parsedate_to_datetime(date_str).replace(tzinfo=None)
                        if msg_date < limit_date:
                            continue
                    except Exception:
                        pass
                
                uid = message.get("Message-ID", str(i+1))
                self._save_to_db(uid, message)
        except Exception as e:
            print(f"Error leyendo POP3: {e}")
            
    def _save_to_db(self, uid, message):
        subject = decode_mime_words(message.get("Subject", ""))
        sender = decode_mime_words(message.get("From", ""))
        date = decode_mime_words(message.get("Date", ""))
        body, is_html = get_email_body(message)
        
        contact_key = db.get_contact_key(sender)
        if contact_key:
            body = crypto.decrypt_message(body.strip(), contact_key)

        db.save_email(uid, self.USER, sender, subject, date, body, is_new=1)


class SmtpSender:
    def __init__(self):
        self.SMTP_SERVER = config.get("smtp", "server", fallback="smtp.gmail.com")
        self.SMTP_PORT = config.getint("smtp", "port", fallback=465)
        self.USER = config.get("auth", "user", fallback="")
        self.PASS = config.get("auth", "password", fallback="")
        
    def send_email(self, to_email, subject, body_text):
        if not self.USER or not self.PASS:
            return False, "Faltan credenciales"
            
        # Encriptar cuerpo si tenemos clave de contacto
        contact_key = db.get_contact_key(to_email)
        if contact_key:
            body_text = crypto.encrypt_message(body_text, contact_key)

        msg = MIMEMultipart()
        msg['From'] = self.USER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body_text, 'plain'))
        
        context = ssl.create_default_context()
        try:
            with smtplib.SMTP_SSL(self.SMTP_SERVER, self.SMTP_PORT, context=context) as server:
                server.login(self.USER, self.PASS)
                server.sendmail(self.USER, to_email, msg.as_string())
            return True, "Enviado correctamente"
        except Exception as e:
            print(f"SMTP Error: {e}")
            return False, str(e)

def update_config_file(config_data):
    for section, values in config_data.items():
        if not config.has_section(section):
            config.add_section(section)
        for k, v in values.items():
            config.set(section, k, str(v))
    with open(config_path, "w") as f:
        config.write(f)
