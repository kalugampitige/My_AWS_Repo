import imaplib
import email
from email.header import decode_header
from config import load_institutes, CONFIDENCE_THRESHOLD, get_credentials
from email_service import EmailService
from ai_classifier import AIClassifier
from audit_logger import AuditLogger

class MailClerkAgent:
    def __init__(self):
        # Retrieve credentials from Secrets Manager/env vars - single source
        # of truth, used by both EmailService and this class's own IMAP fallback.
        self.creds = get_credentials()
        self.email_username = self.creds.get("EMAIL_USERNAME")
        self.app_password = self.creds.get("EMAIL_PASSWORD")
        self.imap_server = self.creds.get("IMAP_SERVER", "imap.gmail.com")

        self.email_service = EmailService(self.creds)
        self.classifier = AIClassifier()
        self.logger = AuditLogger()
        self.institutes = load_institutes()

    def classify_text(self, text_content):
        """Processes and classifies direct string payloads (e.g., from Streamlit)."""
        classification = self.classifier.classify_email("Streamlit Direct Test", text_content, self.institutes)
        target = next((i for i in self.institutes if i["institute_id"] == classification.get("institute_id")), None)
        target_name = target["name"] if target else "Finance & Billing Department"
        
        return {
            "id": "MSG_DIRECT_101",
            "status": "FORWARDED",
            "target": target_name,
            "confidence": classification.get("confidence", 0.95),
            "summary": text_content
        }

    def fetch_unread_via_imap(self):
        """Connects directly to Gmail via IMAP to pull unread incoming emails."""
        fetched_emails = []
        if not self.email_username or not self.app_password:
            print("IMAP fetch skipped: EMAIL_USERNAME/EMAIL_PASSWORD not set (check Lambda environment variables or Secrets Manager).")
            return fetched_emails
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server)
            mail.login(self.email_username, self.app_password)
            mail.select("inbox")

            # Search for unread emails (or filter by specific sender e.g., janethra127@gmail.com)
            status, messages = mail.search(None, 'UNSEEN')
            email_ids = messages[0].split()

            for e_id in email_ids:
                status, msg_data = mail.fetch(e_id, '(RFC822)')
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        # Extract Subject
                        subject = "No Subject"
                        if msg["Subject"]:
                            decoded_subject, encoding = decode_header(msg["Subject"])[0]
                            if isinstance(decoded_subject, bytes):
                                subject = decoded_subject.decode(encoding or "utf-8", errors="ignore")
                            else:
                                subject = str(decoded_subject)

                        # Extract Body Text
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))
                                if content_type == "text/plain" and "attachment" not in content_disposition:
                                    body = part.get_payload(decode=True).decode(errors="ignore")
                                    break
                        else:
                            body = msg.get_payload(decode=True).decode(errors="ignore")

                        fetched_emails.append({
                            "id": e_id.decode("utf-8"),
                            "subject": subject,
                            "body": body
                        })

            mail.logout()
        except Exception as e:
            print(f"IMAP Fetching Error: {str(e)}")
            
        return fetched_emails

    def process_incoming_emails(self):
        """Processes unread emails using EmailService or IMAP fallback."""
        # Attempt to fetch emails via primary EmailService, fallback to IMAP if empty
        emails = self.email_service.fetch_unread_emails() if hasattr(self.email_service, "fetch_unread_emails") else []
        if not emails:
            emails = self.fetch_unread_via_imap()

        results = []
        for email_item in emails:
            classification = self.classifier.classify_email(
                email_item.get("subject", ""), 
                email_item.get("body", ""), 
                self.institutes
            )
            
            if classification.get("confidence", 0) >= CONFIDENCE_THRESHOLD:
                target = next((i for i in self.institutes if i["institute_id"] == classification.get("institute_id")), None)
                target_email = target["contact_email"] if target else "kalugampitige2@gmail.com"
                target_name = target["name"] if target else "Finance & Billing Department"

                forward_ok = True
                forward_error = None
                if hasattr(self.email_service, "forward_email"):
                    try:
                        self.email_service.forward_email(email_item["id"], target_email)
                    except Exception as forward_err:
                        # Don't let one bad/unverified address wipe out this
                        # email's real subject/body - log it and keep going.
                        forward_ok = False
                        forward_error = str(forward_err)
                        self.logger.log_action(email_item["id"], "FORWARD", "FAILED", forward_error)

                self.logger.log_action(email_item["id"], "FORWARD", "SUCCESS" if forward_ok else "FAILED", target_email)
                results.append({
                    "id": email_item["id"],
                    "status": "FORWARDED" if forward_ok else "FORWARD_FAILED",
                    "target": target_name,
                    "target_email": target_email,
                    "error": forward_error,
                    "summary": f"Subject: {email_item.get('subject')}\nBody: {email_item.get('body')}"
                })
            else:
                self.logger.log_action(email_item["id"], "FLAG_HUMAN_REVIEW", "LOW_CONFIDENCE", classification)
                results.append({
                    "id": email_item["id"],
                    "status": "FLAGGED",
                    "target": "Needs Human Review",
                    "reason": "Low confidence",
                    "confidence": classification.get("confidence", 0),
                    "summary": f"Subject: {email_item.get('subject')}\nBody: {email_item.get('body')}"
                })

        return results

if __name__ == "__main__":
    agent = MailClerkAgent()
    print(agent.process_incoming_emails())