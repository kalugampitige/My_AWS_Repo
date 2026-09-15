import os
import json
import boto3
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
SECRET_NAME = os.getenv("SECRET_NAME", "mail-clerk/credentials")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.85"))
TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"

def load_institutes(filepath="institutes.json"):
    """Loads department/institute routing configurations from a local JSON file."""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load {filepath}, error: {e}")
        return []

def get_credentials():
    """Retrieves secret credentials from AWS Secrets Manager or falls back to local environment variables."""
    try:
        client = boto3.client("secretsmanager", region_name=AWS_REGION)
        secret_value = client.get_secret_value(SecretId=SECRET_NAME)
        return json.loads(secret_value["SecretString"])
    except Exception as e:
        print(f"AWS Secrets Manager retrieval failed ({e}), falling back to local .env variables...")
        return {
            "EMAIL_USERNAME": os.getenv("EMAIL_USERNAME", ""),
            "EMAIL_PASSWORD": os.getenv("EMAIL_PASSWORD", ""),
            "IMAP_SERVER": os.getenv("IMAP_SERVER", "imap.gmail.com"),
            "SMTP_SERVER": os.getenv("SMTP_SERVER", "smtp.gmail.com")
        }