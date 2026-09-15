import boto3
import imaplib
import email
from email.mime.text import MIMEText
from botocore.exceptions import ClientError

class EmailService:
    def __init__(self, credentials):
        self.creds = credentials or {}
        self.ses_client = boto3.client('ses', region_name='us-east-1')
        self.verified_sender = "kalugampitige@gmail.com"

    def fetch_unread_emails(self):
        """Fetches unread emails from Gmail IMAP."""
        username = self.creds.get("EMAIL_USERNAME")
        password = self.creds.get("EMAIL_PASSWORD")
        imap_server = self.creds.get("IMAP_SERVER", "imap.gmail.com")

        if not username or not password:
            print("Error: EMAIL_USERNAME or EMAIL_PASSWORD missing in credentials.")
            return []

        try:
            mail = imaplib.IMAP4_SSL(imap_server)
            mail.login(username, password)
            mail.select("INBOX")
            
            status, messages = mail.search(None, "UNSEEN")
            email_list = []
            
            if status == "OK" and messages[0]:
                for num in messages[0].split():
                    _, data = mail.fetch(num, "(RFC822)")
                    raw_email = data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode(errors="ignore")
                                break
                    else:
                        body = msg.get_payload(decode=True).decode(errors="ignore")
                        
                    email_list.append({
                        "id": num.decode(),
                        "subject": msg.get("Subject", "(No Subject)"),
                        "sender": msg.get("From", ""),
                        "body": body
                    })
                    
            mail.logout()
            return email_list
        except Exception as e:
            print(f"Error fetching emails via IMAP: {e}")
            return []

    def fetch_todays_inbox(self):
        return self.fetch_unread_emails()

    def forward_email(self, email_id, target_email):
        """Sends forward message via Amazon SES."""
        try:
            return self.ses_client.send_email(
                Source=self.verified_sender,
                Destination={'ToAddresses': [target_email]},
                Message={
                    'Subject': {'Data': f"Fwd: Email ID {email_id}"},
                    'Body': {'Text': {'Data': f"Forwarded automatically by AI Mail Clerk for Email ID: {email_id}"}}
                }
            )
        except ClientError as e:
            print(f"Error forwarding email via SES: {e.response['Error']['Message']}")
            raise e