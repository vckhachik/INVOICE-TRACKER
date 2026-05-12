from urllib.parse import quote_plus

from .api import get, post


def map_invoice(invoice_id: int):
    return post(f"/mapping/invoices/{invoice_id}/map")


def fetch_mapping_rules():
    return get("/mapping/rules")


def test_match(raw_text: str):
    encoded_text = quote_plus(raw_text)
    return post(f"/mapping/match-test?raw_text={encoded_text}")


def create_mapping_rule(raw_text: str, entity_id: int, project_id: int = None, priority: int = 0):
    query = (
        f"/mapping/rules?raw_text={quote_plus(raw_text)}"
        f"&entity_id={entity_id}"
        f"&priority={priority}"
    )

    if project_id is not None:
        query += f"&project_id={project_id}"

    return post(query)