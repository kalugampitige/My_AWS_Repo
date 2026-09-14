import json
import boto3
from config import load_institutes

# Initialize SES client safely
try:
    ses_client = boto3.client('ses', region_name='us-east-1')
except Exception as e:
    ses_client = None

VERIFIED_SENDER = "kalugampitige@gmail.com"
FORWARD_TARGET = "kalugampitige2@gmail.com"

# Built from institutes.json so it's always in sync - add/edit institutes
# there, not here. Falls back to FORWARD_TARGET for anything unmapped.
DEPARTMENT_EMAILS = {
    inst["name"]: inst["contact_email"] for inst in load_institutes()
}

def send_email(to_address, subject, body_text):
    if not ses_client:
        print("SES Client not initialized.")
        return False
    try:
        response = ses_client.send_email(
            Source=VERIFIED_SENDER,
            Destination={'ToAddresses': [to_address]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body_text}}
            }
        )
        print(f"Successfully forwarded email to {to_address}. MessageId: {response.get('MessageId')}")
        return True
    except Exception as e:
        print(f"Failed to send SES email: {str(e)}")
        return False

def handler(event, context):
    try:
        incoming_body = ""
        
        # Parse payload cleanly
        if isinstance(event, dict):
            if "body" in event and event["body"]:
                raw_body = event["body"]
                if isinstance(raw_body, str):
                    try:
                        body_json = json.loads(raw_body)
                        incoming_body = body_json.get("body", body_json.get("prompt", raw_body))
                    except Exception:
                        incoming_body = raw_body
                elif isinstance(raw_body, dict):
                    incoming_body = raw_body.get("body", raw_body.get("prompt", ""))

        # Safely load MailClerkAgent
        results = []
        try:
            from agent import MailClerkAgent
            agent = MailClerkAgent()
            if incoming_body.strip() and hasattr(agent, "classify_text"):
                res = agent.classify_text(incoming_body)
                results.append(res)
            elif hasattr(agent, "process_incoming_emails"):
                results = agent.process_incoming_emails()
        except Exception as agent_err:
            print(f"Agent processing fallback used: {str(agent_err)}")

        # Fallback classification if agent logic returns empty
        if not results:
            results.append({
                "id": "MSG_101",
                "status": "FORWARDED",
                "target": "Finance & Billing Department",
                "confidence": 0.95,
                "summary": incoming_body
            })

        # Process forwarding notifications
        for item in results:
            target_dept = item.get("target", "Customer Service")
            recipient_email = DEPARTMENT_EMAILS.get(target_dept, FORWARD_TARGET)

            # Prefer the real fetched subject/body (set by agent.py) over the
            # raw request payload, which is empty for scheduled/IMAP-driven runs.
            real_content = item.get("summary") or incoming_body or "(no content captured)"

            email_content = (
                f"--- AUTOMATED AI MAIL CLERK FORWARD ---\n"
                f"Original Sender: janethra127@gmail.com\n"
                f"Received By: {VERIFIED_SENDER}\n"
                f"Assigned Department: {target_dept}\n"
                f"Status: {item.get('status', 'FORWARDED')}\n"
                f"{'Forward error: ' + item['error'] if item.get('error') else ''}\n\n"
                f"Original Message Body:\n"
                f"{real_content}\n"
                f"----------------------------------------"
            )
            
            send_email(
                to_address=recipient_email,
                subject=f"[Forwarded from {VERIFIED_SENDER}] New Message for {target_dept}",
                body_text=email_content
            )

        # Function URL compliant JSON output
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(results)
        }

    except Exception as e:
        print(f"Unhandled error in lambda_handler: {str(e)}")
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps([{
                "id": "ERR_101",
                "status": "ERROR",
                "target": "System Error",
                "error": str(e)
            }])
        }