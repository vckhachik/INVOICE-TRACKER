import streamlit as st

from config import API_BASE_URL
from services.api import get

st.set_page_config(
    page_title="Invoice Tracker",
    page_icon="🧾",
    layout="wide",
)

st.title("🧾 Invoice Tracker")
st.caption("Internal invoice intake, extraction, mapping, and tracking")

st.markdown("---")

# Simple backend health check
api_ok = get("/invoices") is not None

if api_ok:
    st.success(f"Backend connected: {API_BASE_URL}")
else:
    st.error(f"Backend not reachable: {API_BASE_URL}")

st.markdown(
    """
Welcome to the invoice tracking tool.

Use the sidebar to move between the core workflows:
- **Invoice Register** to review and manage invoices
- **Upload Invoice** to add new files and trigger extraction
- **Dashboard** to monitor pipeline totals and statuses
"""
)

st.markdown("## Overview")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 📋 Invoice Register")
    st.write("Browse all invoices, filter by status, and review extracted data.")

with col2:
    st.markdown("### 📤 Upload Invoice")
    st.write("Upload a new invoice file and trigger OCR / extraction.")

with col3:
    st.markdown("### 📊 Dashboard")
    st.write("Track volume, review queues, and operational progress.")

st.markdown("---")

st.markdown("## Suggested workflow")
st.markdown(
    """
1. Upload a new invoice  
2. Run extraction  
3. Review mapped entity and project  
4. Update payment / VAT statuses  
5. Monitor progress in the dashboard
"""
)

st.markdown("---")
st.caption("Use the sidebar to navigate between pages.")