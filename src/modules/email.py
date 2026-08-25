import configparser
from pathlib import Path
import imaplib
import poplib
import email
from email.header import decode_header


config_path = Path(__file__).with_name("email_config.ini")

config = configparser.ConfigParser()
config.read(config_path)

class ImapEmail:
    def __init__(self) -> None:
        self.IMAP_SERVER = config.get("imap", "server")
        self.IMAP_PORT = config.getint("imap", "port")
        self.USER = config.get("auth", "user")
        self.PASS = config.get("auth", "password")
        print(self.IMAP_PORT, self.IMAP_SERVER)

    def get_emails(self, n_emails=5):

        mail = imaplib.IMAP4_SSL(self.IMAP_SERVER, self.IMAP_PORT)
        mail.login(self.USER, self.PASS)
        mail.select("INBOX")
        status, data = mail.search(None, "ALL")
        mail_ids = data[0].split()
        print(status, mail_ids)
        for mail_id in mail_ids[-5:]:  # últimos 5 correos
            status, msg_data = mail.fetch(mail_id, "(RFC822)")
            raw_email = msg_data[0][1]
            message = email.message_from_bytes(raw_email)
            print(message)
            # Continuar parseo de correo


class PopEmail:
    def __init__(self) -> None:
        self.POP_SERVER = config.get("pop", "server")
        self.POP_PORT = config.getint("pop", "port")
        self.USER = config.get("auth", "user")
        self.PASS = config.get("auth", "password")
        print(self.POP_PORT, self.POP_SERVER)
        self.mail = poplib.POP3_SSL(self.POP_SERVER, self.POP_PORT)
        self.mail.user(self.USER)
        self.mail.pass_(self.PASS)

    def get_mails(self, n_emails=5):
        num_messages = len(self.mail.list()[1])
        for i in range(num_messages - 4, num_messages):  # últimos 5
            response, lines, octets = self.mail.retr(i + 1)
            raw_email = b"\r\n".join(lines)
            message = email.message_from_bytes(raw_email)
            print(message)
            # Continuar parseo de correo
