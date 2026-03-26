import os
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from dotenv import load_dotenv

load_dotenv()

AZURE_ENDPOINT = os.getenv("AZURE_FORM_RECOGNIZER_ENDPOINT")
AZURE_KEY = os.getenv("AZURE_FORM_RECOGNIZER_KEY")


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

    return {
        "status": "ok",
        "extracted_fields": extracted,
        "confidence_scores": confidence,
        "raw_field_count": len(fields),
        "line_items": line_items,
    }