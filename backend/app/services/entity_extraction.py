import os
import json
import re
import logging
import anthropic
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not API_KEY:
    raise ValueError("Missing ANTHROPIC_API_KEY")

client = anthropic.Anthropic(api_key=API_KEY)


def safe_json_load(text: str):
    try:
        return json.loads(text)
    except:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


def extract_entity_from_text(raw_text: str) -> dict:
    if not raw_text or len(raw_text.strip()) < 10:
        return {
            "entity": None,
            "confidence": "low",
            "reasoning": "insufficient text"
        }

    raw_text = raw_text[:4000]

    prompt = f"""You are an invoice processing assistant.

Identify the PAYING ENTITY (the customer being invoiced).

Rules:
- This is NOT the supplier/vendor
- Prefer fields like "Bill To", "Customer", "Invoice To"
- If multiple candidates exist, choose the most likely paying entity
- If unsure, return null

Return JSON only with:
- entity
- confidence (high, medium, low)
- reasoning

Raw invoice text:
{raw_text}
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text.strip()
        result = safe_json_load(response_text)
        return result

    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
        return {
            "entity": None,
            "confidence": "low",
            "reasoning": "Extraction failed"
        }
