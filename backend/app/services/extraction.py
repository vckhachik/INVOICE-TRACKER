import os
import logging
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

AZURE_ENDPOINT = os.getenv("AZURE_FORM_RECOGNIZER_ENDPOINT")
AZURE_KEY = os.getenv("AZURE_FORM_RECOGNIZER_KEY")

MAX_RAW_TEXT_CHARS = 8000


def get_client():
    if not AZURE_ENDPOINT or not AZURE_KEY:
        raise ValueError("Missing Azure Form Recognizer endpoint or key.")
    return DocumentAnalysisClient(
        endpoint=AZURE_ENDPOINT,
        credential=AzureKeyCredential(AZURE_KEY),
    )


def extract_invoice(file_path: str) -> dict:
    client = get_client()

    try:
        with open(file_path, "rb") as f:
            poller = client.begin_analyze_document("prebuilt-invoice", document=f)
        result = poller.result()
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")
    except HttpResponseError as e:
        raise RuntimeError(f"Azure analysis failed: {e}") from e

    if not result.documents:
        return {
            "status": "no_document_extracted",
            "extracted_fields": {},
            "confidence_scores": {},
            "raw_field_count": 0,
            "line_items": [],
            "raw_text": "",
        }

    doc = result.documents[0]
    fields = doc.fields

    def get_field(name):
        field = fields.get(name)
        if not field:
            return {"value": None, "confidence": None, "content": None}
        value = getattr(field, "value", None)
        return {
            "value": value,
            "content": field.content,
            "confidence": field.confidence,
        }

    extracted = {}
    confidence = {}

    mapping = {
        "VendorName": "supplier_name_raw",
        "CustomerName": "paying_entity_raw",
        "InvoiceId": "invoice_number",
        "InvoiceDate": "invoice_date",
        "DueDate": "due_date",
        "InvoiceTotal": "gross_amount",
        "TotalTax": "vat_amount",
        "SubTotal": "net_amount",
    }

    for azure_name, output_name in mapping.items():
        field = get_field(azure_name)
        extracted[output_name] = (
            field["value"] if field["value"] is not None else field["content"]
        )
        confidence[output_name] = field["confidence"]

    # Extract currency from InvoiceTotal CurrencyValue object.
    # Azure returns amount fields as CurrencyValue with .currency_code and .currency_symbol.
    extracted["currency_code"] = None
    extracted["currency_symbol"] = None
    invoice_total_field = fields.get("InvoiceTotal")
    if invoice_total_field:
        cv = getattr(invoice_total_field, "value", None)
        if cv is not None:
            extracted["currency_code"] = getattr(cv, "currency_code", None)
            extracted["currency_symbol"] = getattr(cv, "symbol", None) or getattr(cv, "currency_symbol", None)

    # Extract line items
    items_field = fields.get("Items")
    line_items = []

    if items_field and items_field.value:
        for item in items_field.value:
            item_fields = getattr(item, "value", {}) or {}
            line_items.append({
                "description": item_fields.get("Description").content
                    if item_fields.get("Description") else None,
                "quantity": item_fields.get("Quantity").value
                    if item_fields.get("Quantity") else None,
                "unit_price": item_fields.get("UnitPrice").value
                    if item_fields.get("UnitPrice") else None,
                "amount": item_fields.get("Amount").value
                    if item_fields.get("Amount") else None,
            })

    # Build raw text for Claude fallback
    raw_text = ""
    try:
        raw_text_parts = []
        for page in result.pages:
            if hasattr(page, "lines") and page.lines:
                page_text = "\n".join(
                    line.content for line in page.lines if line.content
                )
                raw_text_parts.append(page_text)
        raw_text = "\n\n--- PAGE BREAK ---\n\n".join(raw_text_parts).strip()
        raw_text = raw_text[:MAX_RAW_TEXT_CHARS]
    except Exception as e:
        raw_text = ""
        logger.warning(f"Could not build raw_text from OCR result: {e}")

    return {
        "status": "ok",
        "extracted_fields": extracted,
        "confidence_scores": confidence,
        "raw_field_count": len(fields),
        "line_items": line_items,
        "raw_text": raw_text,
    }