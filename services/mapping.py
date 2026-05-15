from urllib.parse import quote_plus
from typing import Optional

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


def create_project(name: str, group_name: Optional[str] = None, description: Optional[str] = None):
    payload = {"name": name}
    if group_name:
        payload["group_name"] = group_name
    if description:
        payload["description"] = description
    return post("/projects/", data=payload)


def create_entity(
    name: str,
    project_id_default: Optional[int] = None,
    aliases: Optional[list] = None,
    show_as_project: bool = False,
):
    payload: dict = {"name": name, "show_as_project": show_as_project}
    if project_id_default is not None:
        payload["project_id_default"] = project_id_default
    if aliases:
        payload["aliases"] = aliases
    return post("/entities/", data=payload)
