"""
Seed script — loads projects and entities from your spreadsheet.
Run from the backend folder:
    python seed_data.py
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal
from app.models.models import Project, Entity


SEED_DATA = [
    {
        "project": "The Roc Club",
        "aliases": ["ROC", "Roc Club"],
        "entities": [
            "ROC NEWCO 1 LIMITED",
            "VC PBSA 1 LIMITED",
            "ROC NEWCO 2 LIMITED",
            "ROC DEVCO LIMITED",
            "VC PBSA 2 LIMITED",
        ],
    },
    {
        "project": "Three King's Mayfair",
        "aliases": ["TKY", "Three Kings", "3KY"],
        "entities": [
            "VC TKY LIMITED",
            "3KY MAYFAIR LIMITED",
        ],
    },
    {
        "project": "Yeoman's Square Knightsbridge",
        "aliases": ["YSK", "Yeomans", "Yeoman's Square"],
        "entities": [
            "VC PCL1 Limited",
            "YSK FREEHOLD CO LIMITED",
        ],
    },
    {
        "project": "VCDREF",
        "aliases": ["VCDREF", "Asset"],
        "entities": [
            "ASSET RESI 3 LIMITED",
            "Asset Commercial 2 Limited",
            "Asset 401 Capel Limited",
            "Asset Resi Limited",
            "Asset Resi 2 Limited",
        ],
    },
    {
        "project": "EVC Energy",
        "aliases": ["EVC"],
        "entities": [
            "EVC KILT LIMITED",
        ],
    },
    {
        "project": "Athens Aparthotel",
        "aliases": ["Athens"],
        "entities": [],
    },
    {
        "project": "10 Newmarket Square",
        "aliases": ["Newmarket", "NREK"],
        "entities": [
            "NREK 1 LIMITED",
        ],
    },
    {
        "project": "Camden Town",
        "aliases": ["Camden"],
        "entities": [],
    },
    {
        "project": "OTHER",
        "aliases": ["Other"],
        "entities": [
            "31 AMELIA STREET",
        ],
    },
]


def normalise_list(values):
    return [v.strip() for v in values if v and str(v).strip()]


def get_or_create_project(db, project_name: str):
    project = db.query(Project).filter(Project.name == project_name).first()

    if not project:
        project = Project(
            name=project_name,
            group_name="VC Group",
        )
        db.add(project)
        db.flush()
        print(f"✅ Created project: {project_name}")
    else:
        print(f"⏭️  Project already exists: {project_name}")

    return project


def get_or_create_entity(db, entity_name: str, aliases: list, project_id: int):
    entity_name = entity_name.strip()

    entity = db.query(Entity).filter(Entity.name == entity_name).first()

    if not entity:
        entity = Entity(
            name=entity_name,
            aliases=aliases,
            project_id_default=project_id,
        )
        db.add(entity)
        print(f"   ✅ Created entity: {entity_name}")
    else:
        updated = False

        if hasattr(entity, "project_id_default") and entity.project_id_default != project_id:
            entity.project_id_default = project_id
            updated = True

        if hasattr(entity, "aliases"):
            existing_aliases = entity.aliases or []
            merged_aliases = sorted(set(existing_aliases + aliases))
            if merged_aliases != existing_aliases:
                entity.aliases = merged_aliases
                updated = True

        if updated:
            print(f"   🔄 Updated entity: {entity_name}")
        else:
            print(f"   ⏭️  Entity already exists: {entity_name}")

    return entity


def seed():
    db = SessionLocal()

    try:
        for item in SEED_DATA:
            project_name = item["project"].strip()
            aliases = normalise_list(item.get("aliases", []))
            entity_names = normalise_list(item.get("entities", []))

            project = get_or_create_project(db, project_name)

            for entity_name in entity_names:
                get_or_create_entity(
                    db=db,
                    entity_name=entity_name,
                    aliases=aliases,
                    project_id=project.id,
                )

        db.commit()
        print("\n🎉 Seed complete!")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Seed failed: {e}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed()
