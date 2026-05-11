from collections import defaultdict
import streamlit as st

from services.api import get
from services.mapping import fetch_mapping_rules, test_match, create_mapping_rule


def render_mapping():
    st.title("🧠 Mapping")
    st.caption("Test entity matching, manage mapping rules, and inspect projects and entities")
    st.markdown("---")

    entities = get("/entities/") or []
    projects = get("/projects/") or []
    rules = fetch_mapping_rules() or []

    entity_options = {e.get("name"): e.get("id") for e in entities if e.get("name")}
    project_options = {p.get("name"): p.get("id") for p in projects if p.get("name")}

    tab1, tab2, tab3 = st.tabs(["🔍 Match Test", "📋 Mapping Rules", "🏢 Entities & Projects"])

    with tab1:
        st.subheader("Test Entity Match")
        st.write("Enter raw text to test how the matching engine maps it to an entity and project.")
        with st.form("match_test_form"):
            raw_text = st.text_input("Raw entity name", placeholder="e.g. VC PCL1 Limited")
            run_match = st.form_submit_button("🔍 Test Match")

        if run_match:
            if not raw_text or not raw_text.strip():
                st.warning("Please enter some raw text to test.")
            else:
                with st.spinner("Matching..."):
                    result = test_match(raw_text.strip())
                if result:
                    metric_col1, metric_col2, metric_col3 = st.columns(3)
                    with metric_col1:
                        st.metric("Matched", "Yes" if result.get("matched") else "No")
                    with metric_col2:
                        st.metric("Match Type", result.get("match_type") or "-")
                    with metric_col3:
                        st.metric("Confidence", result.get("confidence") or "-")
                    st.markdown("---")
                    entity = result.get("entity") or {}
                    project = result.get("project") or {}
                    detail_col1, detail_col2 = st.columns(2)
                    with detail_col1:
                        st.write(f"**Raw Text:** {result.get('raw_text') or raw_text}")
                        st.write(f"**Matched Entity:** {entity.get('name') or 'No match'}")
                        st.write(f"**Entity ID:** {entity.get('id') or '-'}")
                    with detail_col2:
                        st.write(f"**Matched Project:** {project.get('name') or 'No match'}")
                        st.write(f"**Project ID:** {project.get('id') or '-'}")
                else:
                    st.error("Match test failed.")

    with tab2:
        st.subheader("Mapping Rules")
        if rules:
            st.markdown(f"**{len(rules)} active rule(s)**")
            for rule in rules:
                with st.container():
                    st.markdown(
                        f"**Pattern:** `{rule.get('raw_text_pattern') or '-'}`  \n"
                        f"**Entity ID:** {rule.get('mapped_entity_id') or '-'}  \n"
                        f"**Project ID:** {rule.get('mapped_project_id') or '-'}  \n"
                        f"**Priority:** {rule.get('priority', 0)}"
                    )
                    st.markdown("---")
        else:
            st.info("No mapping rules yet.")

        st.subheader("Create New Rule")
        if not entities:
            st.warning("No entities available. Seed entities first before creating rules.")
        elif not projects:
            st.warning("No projects available. Seed projects first before creating rules.")
        else:
            with st.form("create_rule_form"):
                rule_text = st.text_input("Raw text pattern", placeholder="e.g. ROC Club Holdings Ltd")
                selected_entity = st.selectbox("Map to Entity", options=list(entity_options.keys()))
                selected_project = st.selectbox("Map to Project", options=list(project_options.keys()))
                priority = st.number_input("Priority (higher = checked first)", min_value=0, value=0, step=1)
                submit_rule = st.form_submit_button("💾 Save Rule")

            if submit_rule:
                if not rule_text or not rule_text.strip():
                    st.warning("Please enter a raw text pattern.")
                else:
                    result = create_mapping_rule(
                        raw_text=rule_text.strip(),
                        entity_id=entity_options[selected_entity],
                        project_id=project_options[selected_project],
                        priority=int(priority),
                    )
                    if result:
                        st.success(f"Rule created: '{rule_text}' → {selected_entity}")
                        st.rerun()
                    else:
                        st.error("Could not create rule.")

    with tab3:
        st.subheader("Entities & Projects")

        if not projects and not entities:
            st.info("No projects or entities found.")
            return

        project_id_to_name = {p["id"]: p["name"] for p in projects if p.get("id")}

        entities_by_project = defaultdict(list)
        unassigned = []
        for e in entities:
            pid = e.get("project_id_default")
            if pid and pid in project_id_to_name:
                entities_by_project[pid].append(e)
            else:
                unassigned.append(e)

        for project in sorted(projects, key=lambda p: p.get("name", "")):
            pid = project.get("id")
            pname = project.get("name", "-")
            project_entities = entities_by_project.get(pid, [])
            count = len(project_entities)
            with st.expander(f"**{pname}** — {count} entit{'y' if count == 1 else 'ies'}", expanded=False):
                if project_entities:
                    for e in sorted(project_entities, key=lambda x: x.get("name", "")):
                        aliases = e.get("aliases") or []
                        alias_str = f"  *(aliases: {', '.join(aliases)})*" if aliases else ""
                        st.write(f"• {e['name']}{alias_str}")
                else:
                    st.caption("No entities assigned to this project.")

        if unassigned:
            with st.expander(f"**Unassigned entities** — {len(unassigned)}", expanded=False):
                for e in sorted(unassigned, key=lambda x: x.get("name", "")):
                    st.write(f"• {e['name']}")
