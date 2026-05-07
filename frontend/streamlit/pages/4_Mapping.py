import streamlit as st

from services.api import get
from services.mapping import fetch_mapping_rules, test_match, create_mapping_rule

st.set_page_config(page_title="Mapping", page_icon="🧠", layout="wide")
st.title("🧠 Mapping")
st.caption("Test entity matching, manage mapping rules, and inspect projects and entities")

st.markdown("---")

# Load reference data once
entities = get("/entities/") or []
projects = get("/projects/") or []
rules = fetch_mapping_rules() or []

entity_options = {e.get("name"): e.get("id") for e in entities if e.get("name")}
project_options = {p.get("name"): p.get("id") for p in projects if p.get("name")}

tab1, tab2, tab3 = st.tabs(["🔍 Match Test", "📋 Mapping Rules", "🏢 Entities & Projects"])

# ── Tab 1: Match Test ──────────────────────────────────────────────────
with tab1:
    st.subheader("Test Entity Match")
    st.write("Enter raw text to test how the matching engine maps it to an entity and project.")

    with st.form("match_test_form"):
        raw_text = st.text_input(
            "Raw entity name",
            placeholder="e.g. VC PCL1 Limited"
        )
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

# ── Tab 2: Mapping Rules ───────────────────────────────────────────────
with tab2:
    st.subheader("Mapping Rules")

    if rules:
        st.markdown(f"**{len(rules)} active rule(s)**")

        for rule in rules:
            raw_text_pattern = rule.get("raw_text_pattern") or "-"
            mapped_entity_id = rule.get("mapped_entity_id") or "-"
            mapped_project_id = rule.get("mapped_project_id") or "-"
            priority = rule.get("priority", 0)

            with st.container():
                st.markdown(
                    f"**Pattern:** `{raw_text_pattern}`  \n"
                    f"**Entity ID:** {mapped_entity_id}  \n"
                    f"**Project ID:** {mapped_project_id}  \n"
                    f"**Priority:** {priority}"
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
            rule_text = st.text_input(
                "Raw text pattern",
                placeholder="e.g. ROC Club Holdings Ltd"
            )

            selected_entity = st.selectbox(
                "Map to Entity",
                options=list(entity_options.keys())
            )

            selected_project = st.selectbox(
                "Map to Project",
                options=list(project_options.keys())
            )

            priority = st.number_input(
                "Priority (higher = checked first)",
                min_value=0,
                value=0,
                step=1,
            )

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

# ── Tab 3: Entities & Projects ─────────────────────────────────────────
with tab3:
    st.subheader("Entities & Projects")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Projects")

        if projects:
            for project in projects:
                st.write(
                    f"**{project.get('name') or '-'}** "
                    f"(ID: {project.get('id') or '-'})"
                )
        else:
            st.info("No projects found.")

    with col2:
        st.markdown("### Entities")

        if entities:
            for entity in entities:
                st.write(
                    f"**{entity.get('name') or '-'}** "
                    f"(ID: {entity.get('id') or '-'}) — "
                    f"Project ID: {entity.get('project_id_default') or '-'}"
                )
        else:
            st.info("No entities found.")