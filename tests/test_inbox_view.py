"""Tests for the Inbox page: it lives as its own top-level view (views/inbox.py)
routed from the app's existing left-navigation sidebar radio in
streamlit_app.py — not as a tab inside the Invoice Register page. Only queues
expressible as a single existing Register status preset get a "View in
Register" button; the rest (needs_manual_check, unmapped) show rows only,
since the Register has no matching filter for either today."""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from views.inbox import INBOX_QUEUE_TO_REGISTER_PRESET, INBOX_QUEUES
from views.invoices import STATUS_PRESETS


def test_only_awaiting_approval_and_approved_unpaid_have_a_register_handoff():
    assert set(INBOX_QUEUE_TO_REGISTER_PRESET.keys()) == {"awaiting_approval", "approved_unpaid"}


def test_needs_manual_check_and_unmapped_have_no_handoff():
    assert "needs_manual_check" not in INBOX_QUEUE_TO_REGISTER_PRESET
    assert "unmapped" not in INBOX_QUEUE_TO_REGISTER_PRESET


def test_handoff_preset_labels_are_real_register_presets():
    """Catches drift immediately if a Register preset label is ever
    renamed without updating the Inbox's hand-off mapping."""
    for preset_label in INBOX_QUEUE_TO_REGISTER_PRESET.values():
        assert preset_label in STATUS_PRESETS


def test_handoff_maps_to_the_correct_preset_per_queue():
    assert INBOX_QUEUE_TO_REGISTER_PRESET["awaiting_approval"] == "Awaiting approval"
    assert INBOX_QUEUE_TO_REGISTER_PRESET["approved_unpaid"] == "Approved, unpaid"


def test_inbox_queues_are_exactly_the_four_specified_in_order():
    assert [key for key, _ in INBOX_QUEUES] == [
        "needs_manual_check", "unmapped", "awaiting_approval", "approved_unpaid",
    ]
    # No fifth "VAT to recover" queue in this phase.
    assert len(INBOX_QUEUES) == 4


# ── Inbox is a top-level page, not a Register tab ───────────────────────────

def test_invoice_register_module_no_longer_defines_any_inbox_symbols():
    """The Inbox implementation must live entirely in views/inbox.py now —
    nothing Inbox-related should remain in views/invoices.py."""
    import views.invoices as invoices_module

    assert not hasattr(invoices_module, "INBOX_QUEUES")
    assert not hasattr(invoices_module, "INBOX_QUEUE_TO_REGISTER_PRESET")
    assert not hasattr(invoices_module, "_render_inbox")


def test_register_tabs_are_the_original_five_with_no_inbox_tab():
    source = open(os.path.join(ROOT, "views", "invoices.py"), encoding="utf-8").read()
    tree = ast.parse(source)

    tab_call = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "tabs"
        and isinstance(node.args[0], ast.List)
        and any("Register" in elt.value for elt in node.args[0].elts if isinstance(elt, ast.Constant))
    )
    tab_labels = [elt.value for elt in tab_call.args[0].elts]

    assert not any("Inbox" in label for label in tab_labels)
    assert len(tab_labels) == 5
    assert any("Register" in label for label in tab_labels)
    assert any("Upload" in label for label in tab_labels)
    assert any("Manual Entry" in label for label in tab_labels)
    assert any("Mapping" in label for label in tab_labels)
    assert any("Recurring" in label for label in tab_labels)


# ── Inbox is reachable through the existing main navigation ─────────────────

def test_inbox_is_registered_in_the_main_sidebar_navigation():
    source = open(os.path.join(ROOT, "streamlit_app.py"), encoding="utf-8").read()

    assert "from views.inbox import render_inbox" in source
    assert '"Inbox"' in source
    assert 'elif page == "Inbox"' in source and "render_inbox()" in source


def test_inbox_is_positioned_before_invoice_register_in_nav_options():
    tree = ast.parse(open(os.path.join(ROOT, "streamlit_app.py"), encoding="utf-8").read())
    nav_assignment = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "nav_options" for t in node.targets)
    )
    nav_options = [elt.value for elt in nav_assignment.value.elts]

    assert "Inbox" in nav_options
    assert "Invoice Register" in nav_options
    assert nav_options.index("Inbox") < nav_options.index("Invoice Register")
