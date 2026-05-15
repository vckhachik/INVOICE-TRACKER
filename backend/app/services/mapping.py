import logging
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import Entity, Invoice, MappingRule, Project

logger = logging.getLogger(__name__)


def normalise_name(name: str) -> str:
    if not name:
        return ""

    name = name.upper().strip()

    # Remove punctuation and separators
    name = re.sub(r"[^A-Z0-9]", " ", name)

    # Remove common legal suffixes entirely so LTD / LIMITED / no suffix all match
    name = re.sub(r"\b(LIMITED|LTD|PLC|LLP|INC|CORP)\b", "", name)

    # Collapse repeated whitespace
    name = re.sub(r"\s+", " ", name).strip()

    # Remove spaces completely so spacing differences do not matter
    return name.replace(" ", "")


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

    rules = (
        db.query(MappingRule)
        .filter(MappingRule.active.is_(True))
        .order_by(MappingRule.priority.desc())
        .all()
    )
    entities = db.query(Entity).all()
    projects = {project.id: project for project in db.query(Project).all()}

    # Step 1 — mapping rules (highest priority)
    for rule in rules:
        pattern = normalise_name(rule.raw_text_pattern)
        if pattern and (pattern == normalised or pattern in normalised):
            entity = next(
                (entity for entity in entities if entity.id == rule.mapped_entity_id),
                None,
            )
            project = (
                projects.get(rule.mapped_project_id)
                if rule.mapped_project_id
                else None
            )

            logger.info(
                "Rule match: '%s' -> '%s'",
                raw_name,
                entity.name if entity else None,
            )
            return {
                "matched": True,
                "entity": entity,
                "project": project,
                "match_type": "rule",
                "confidence": "high",
            }

    # Step 2 — exact normalised entity name or alias match
    for entity in entities:
        project = (
            projects.get(entity.project_id_default)
            if entity.project_id_default
            else None
        )

        if normalise_name(entity.name) == normalised:
            logger.info("Exact match: '%s' -> '%s'", raw_name, entity.name)
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
                logger.info(
                    "Alias match: '%s' -> '%s' via '%s'",
                    raw_name,
                    entity.name,
                    alias,
                )
                return {
                    "matched": True,
                    "entity": entity,
                    "project": project,
                    "match_type": "alias",
                    "confidence": "high",
                }

    # Step 3 — cautious fuzzy match (only if there is exactly one candidate)
    fuzzy_candidates = []
    for entity in entities:
        entity_norm = normalise_name(entity.name)

        if len(entity_norm) < 5 or len(normalised) < 5:
            continue

        if entity_norm in normalised or normalised in entity_norm:
            fuzzy_candidates.append(entity)

    if len(fuzzy_candidates) == 1:
        entity = fuzzy_candidates[0]
        project = (
            projects.get(entity.project_id_default)
            if entity.project_id_default
            else None
        )

        logger.info("Fuzzy match: '%s' -> '%s'", raw_name, entity.name)
        return {
            "matched": True,
            "entity": entity,
            "project": project,
            "match_type": "fuzzy",
            "confidence": "medium",
        }

    logger.info("No match for '%s'", raw_name)
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
            entity = result["entity"]
            # For show_as_project entities the paired project is a fallback only —
            # don't overwrite an explicit project_id already on the invoice.
            is_fallback = entity and getattr(entity, "show_as_project", False)
            if not is_fallback or not invoice.project_id:
                invoice.project_id = result["project"].id
        db.commit()
        db.refresh(invoice)

    return result


def save_mapping_rule(
    raw_text: str,
    entity_id: int,
    project_id: Optional[int],  # ✅ FIXED HERE
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