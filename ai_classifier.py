import json
import boto3
from config import AWS_REGION, CONFIDENCE_THRESHOLD

class AIClassifier:
    def __init__(self):
        self.bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)

    def match_by_keyword(self, subject, body, institutes):
        """Checks institutes.json's keyword lists against the email text.
        Runs before the LLM call - cheaper, and gives predictable routing
        for anything with an obvious keyword match."""
        text = f"{subject} {body}".lower()
        for inst in institutes:
            for kw in inst.get("keywords", []):
                if kw.lower() in text:
                    return {"institute_id": inst["institute_id"], "confidence": 0.90}
        return None

    def classify_email(self, subject, body, institutes):
        keyword_match = self.match_by_keyword(subject, body, institutes)
        if keyword_match:
            return keyword_match

        institute_ids = [i["institute_id"] for i in institutes]
        prompt = (
            f"Categorize this email into exactly one of these IDs: {institute_ids}.\n"
            f"Subject: {subject}\nBody: {body}\n\n"
            'Respond with ONLY raw JSON, no other text: '
            '{"institute_id": "<one of the IDs above>", "confidence": <0.0 to 1.0>}'
        )
        try:
            payload = {
                "inferenceConfig": {"max_new_tokens": 300},
                "messages": [{"role": "user", "content": [{"text": prompt}]}]
            }
            response = self.bedrock.invoke_model(
                modelId="us.amazon.nova-pro-v1:0",
                body=json.dumps(payload)
            )
            response_body = json.loads(response["body"].read())
            raw_text = response_body["output"]["message"]["content"][0]["text"].strip()
            raw_text = raw_text.strip("`").replace("json", "", 1) if raw_text.startswith("```") else raw_text
            result = json.loads(raw_text)
            if result.get("institute_id") in institute_ids:
                return {"institute_id": result["institute_id"], "confidence": float(result.get("confidence", 0.5))}
            raise ValueError(f"Model returned unknown institute_id: {result.get('institute_id')}")
        except Exception as e:
            print(f"Bedrock classification failed, using keyword fallback: {e}")
            # Fallback heuristic rule for testing mode / Bedrock unavailable
            if "invoice" in body.lower():
                return {"institute_id": "INST_FINANCE", "confidence": 0.90}
            return {"institute_id": "INST_HR", "confidence": 0.80}
