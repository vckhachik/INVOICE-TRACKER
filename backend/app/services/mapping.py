import logging
from sqlalchemy.orm import Session
from app.models.models import Entity, Project, MappingRule, Invoice

logger = logging.getLogger(__name__)


def normalise_name(name: str) -> str:
    if not name:
        return ""
    return " ".join(name.strip().lower().split())


def find_entity_match(raw_name: str, db: Session) -> dict:
    if not raw_name or not raw_name.strip():
        return {
            "matched": False,
            "entity": None,
            "project": None,
            "match_type": None,
            "confidence": "low",
        }

    normalised = normalise_name(raw_name)

    # Load once, reuse
    rules = (
        db.query(MappingRule)
        .filter(MappingRule.active.is_(True))
        .order_by(MappingRule.priority.desc())
        .all()
    )
    entities = db.query(Entity).all()
    projects = {p.id: p for p in db.query(Project).all()}

    # Step 1 — mapping rules (highest priority)
    for rule in rules:
        pattern = normalise_name(rule.raw_text_pattern)
        if pattern and (pattern == normalised or pattern in normalised):
            entity = next((e for e in entities if e.id == rule.mapped_entity_id), None)
            project = projects.get(rule.mapped_project_id) if rule.mapped_project_id else None
            logger.info(f"Rule match: '{raw_name}' -> '{entity.name if entity else None}'")
            return {
                "matched": True,
                "entity": entity,
                "project": project,
                "match_type": "rule",
                "confidence": "high",
            }

    # Step 2 — exact name or alias match
    for entity in entities:
        project = projects.get(entity.project_id_default) if entity.project_id_default else None

        if normalise_name(entity.name) == normalised:
            logger.info(f"Exact match: '{raw_name}' -> '{entity.name}'")
            return {
                "matched": True,
                "entity": entity,
                "project": project,
                "match_type": "exact",
                "confidence": "high",
            }

        aliases = entity.aliases or []
        for alias in aliases:
            if normalise_name(alias) == normalised:
                logger.info(f"Alias match: '{raw_name}' -> '{entity.name}' via '{alias}'")
                return {
                    "matched": True,
                    "entity": entity,
                    "project": project,
                    "match_type": "alias",
                    "confidence": "high",
                }

    # Step 3 — cautious fuzzy (only if exactly one candidate)
    fuzzy_candidates = []
    for entity in entities:
        entity_norm = normalise_name(entity.name)
        if len(entity_norm) < 5 or len(normalised) < 5:
            continue
        if entity_norm in normalised or normalised in entity_norm:
            fuzzy_candidates.append(entity)

    if len(fuzzy_candidates) == 1:
        entity = fuzzy_candidates[0]
        project = projects.get(entity.project_id_default) if entity.project_id_default else None
        logger.info(f"Fuzzy match: '{raw_name}' -> '{entity.name}'")
        return {
            "matched": True,
            "entity": entity,
            "project": project,
            "match_type": "fuzzy",
            "confidence": "medium",
        }

    logger.info(f"No match for '{raw_name}'")
    return {
        "matched": False,
        "entity": None,
        "project": None,
        "match_type": None,
        "confidence": "low",
    }


def apply_mapping_to_invoice(invoice: Invoice, db: Session) -> dict:
    raw_entity = invoice.paying_entity_raw
    result = find_entity_match(raw_entity, db)

    if result["matched"]:
        if result["entity"]:
            invoice.paying_entity_id = result["entity"].id
        if result["project"]:
            invoice.project_id = result["project"].id
        db.commit()
        db.refresh(invoice)

    return result


def save_mapping_rule(
    raw_text: str,
    entity_id: int,
    project_id: int,
    db: Session,
    priority: int = 0,
) -> MappingRule:
    if not raw_text or not raw_text.strip():
        raise ValueError("raw_text is required")

    cleaned_text = raw_text.strip()

    existing = db.query(MappingRule).filter(
        MappingRule.raw_text_pattern == cleaned_text
    ).first()

    if existing:
        existing.mapped_entity_id = entity_id
        existing.mapped_project_id = project_id
        existing.priority = priority
        existing.active = True
        db.commit()
        db.refresh(existing)
        return existing

    rule = MappingRule(
        raw_text_pattern=cleaned_text,
        mapped_entity_id=entity_id,
        mapped_project_id=project_id,
        priority=priority,
        active=True,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule