import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class AuditLogger:
    def log_action(self, email_id, action, status, details=None):
        logging.info(f"Email ID: {email_id} | Action: {action} | Status: {status} | Details: {details}")