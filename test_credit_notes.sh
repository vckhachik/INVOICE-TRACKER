#!/bin/bash
# Smoke test for credit notes Phase A — runs all CRUD + edge cases

set -e

API="http://127.0.0.1:8000"
ADMIN_EMAIL="akhachik@valprecapital.com"
FINANCE_EMAIL="mademoisellehavana@gmail.com"

read -s -p "Admin password: " ADMIN_PW
echo
read -s -p "Finance user password: " FINANCE_PW
echo

PASS=0
FAIL=0

check() {
  local label="$1"
  local got="$2"
  local want="$3"
  if [[ "$got" == "$want" ]]; then
    echo "  ✅ $label (got $got)"
    ((PASS++))
  else
    echo "  ❌ $label — expected $want, got $got"
    ((FAIL++))
  fi
}

login() {
  curl -s -X POST "$API/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$1\",\"password\":\"$2\"}" \
    | python3 -c "import sys, json; print(json.load(sys.stdin).get('session_token',''))"
}

echo "=== Logging in ==="
ADMIN_TOKEN=$(login "$ADMIN_EMAIL" "$ADMIN_PW")
FINANCE_TOKEN=$(login "$FINANCE_EMAIL" "$FINANCE_PW")
[[ -z "$ADMIN_TOKEN" ]] && echo "❌ Admin login failed" && exit 1
[[ -z "$FINANCE_TOKEN" ]] && echo "❌ Finance login failed (does the user exist with that password?)" && exit 1
echo "  ✅ Both logins succeeded"
echo

# Get an existing invoice ID + gross to test linking against
echo "=== Finding a real invoice to link against ==="
INVOICE_DATA=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$API/invoices/?limit=1" | python3 -c "
import sys, json
items = json.load(sys.stdin)
if not items:
    print('NONE NONE')
else:
    inv = items[0]
    print(inv['id'], inv.get('gross_amount') or '0')
")
INVOICE_ID=$(echo "$INVOICE_DATA" | awk '{print $1}')
INVOICE_GROSS=$(echo "$INVOICE_DATA" | awk '{print $2}')
if [[ "$INVOICE_ID" == "NONE" ]]; then
  echo "  ⚠️  No invoices found. Create one first, then re-run."
  exit 1
fi
echo "  Will use invoice_id=$INVOICE_ID (gross=$INVOICE_GROSS) for link tests"
echo

# Step 1: Create credit note manually
echo "=== Step 1: POST /credit-notes/manual ==="
CN_RESPONSE=$(curl -s -X POST "$API/credit-notes/manual" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "supplier_name_raw": "Test Supplier (smoke test)",
    "credit_number": "CN-SMOKE-001",
    "credit_date": "2026-05-07",
    "gross_amount": 100.00,
    "project_id": null
  }')
CN_ID=$(echo "$CN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
if [[ -z "$CN_ID" ]]; then
  echo "  ❌ Could not create credit note. Response:"
  echo "$CN_RESPONSE"
  exit 1
fi
echo "  ✅ Created credit_note_id=$CN_ID"
echo

# Step 2: List
echo "=== Step 2: GET /credit-notes/ (list) ==="
LIST_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $ADMIN_TOKEN" "$API/credit-notes/")
check "list returns 200" "$LIST_CODE" "200"
echo

# Step 3: Detail fetch
echo "=== Step 3: GET /credit-notes/$CN_ID ==="
DETAIL_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $ADMIN_TOKEN" "$API/credit-notes/$CN_ID")
check "detail fetch returns 200" "$DETAIL_CODE" "200"
echo

# Step 4: Edit supplier
echo "=== Step 4: PATCH /credit-notes/$CN_ID (edit) ==="
PATCH_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$API/credit-notes/$CN_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"supplier_name_raw":"Edited Supplier"}')
check "edit returns 200" "$PATCH_CODE" "200"
EDITED=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$API/credit-notes/$CN_ID" | python3 -c "import sys, json; print(json.load(sys.stdin).get('supplier_name_raw',''))")
check "supplier name persisted" "$EDITED" "Edited Supplier"
echo

# Step 5: Status toggle (admin can do everything)
echo "=== Step 5: PATCH /credit-notes/$CN_ID/status as admin ==="
STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$API/credit-notes/$CN_ID/status" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_approved_to_pay":true,"is_paid":true}')
check "admin status toggle returns 200" "$STATUS_CODE" "200"
echo

# Edge case 4: Finance blocked from is_approved_to_pay
echo "=== Edge case 4: finance user blocked from is_approved_to_pay ==="
FORBID_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$API/credit-notes/$CN_ID/status" \
  -H "Authorization: Bearer $FINANCE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_approved_to_pay":false}')
check "finance is blocked (403)" "$FORBID_CODE" "403"
echo

# Step 6: Link to real invoice
echo "=== Step 6: POST /credit-notes/$CN_ID/links (real invoice) ==="
LINK_RESPONSE=$(curl -s -X POST "$API/credit-notes/$CN_ID/links" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"invoice_id\":$INVOICE_ID,\"allocated_amount\":50.00}")
LINK_ID=$(echo "$LINK_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
if [[ -n "$LINK_ID" ]]; then
  echo "  ✅ Created link_id=$LINK_ID"
  ((PASS++))
else
  echo "  ❌ Link creation failed: $LINK_RESPONSE"
  ((FAIL++))
fi
echo

# Edge case 1: Parked credit (null invoice_id)
echo "=== Edge case 1: parked credit (invoice_id=null) ==="
PARK_RESPONSE=$(curl -s -X POST "$API/credit-notes/$CN_ID/links" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"invoice_id":null,"allocated_amount":null}')
PARK_ID=$(echo "$PARK_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
if [[ -n "$PARK_ID" ]]; then
  echo "  ✅ Parked credit link created (id=$PARK_ID)"
  ((PASS++))
else
  echo "  ❌ Parked credit rejected: $PARK_RESPONSE"
  ((FAIL++))
fi
echo

# Edge case 2: Over-credit
echo "=== Edge case 2: over-credit (£999,999 against invoice $INVOICE_ID) ==="
OVER_RESPONSE=$(curl -s -X POST "$API/credit-notes/$CN_ID/links" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"invoice_id\":$INVOICE_ID,\"allocated_amount\":999999.00}")
OVER_ID=$(echo "$OVER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
if [[ -n "$OVER_ID" ]]; then
  echo "  ✅ Over-credit accepted (id=$OVER_ID)"
  ((PASS++))
else
  echo "  ❌ Over-credit rejected: $OVER_RESPONSE"
  ((FAIL++))
fi
echo

# Step 7: List links
echo "=== Step 7: GET /credit-notes/$CN_ID/links ==="
LINKS_RESPONSE=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$API/credit-notes/$CN_ID/links")
LINK_COUNT=$(echo "$LINKS_RESPONSE" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
check "should see 3 links" "$LINK_COUNT" "3"
echo

# Step 8: Delete one link (the parked one)
echo "=== Step 8: DELETE /credit-notes/$CN_ID/links/$PARK_ID ==="
UNLINK_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE -H "Authorization: Bearer $ADMIN_TOKEN" "$API/credit-notes/$CN_ID/links/$PARK_ID")
check "unlink returns 200" "$UNLINK_CODE" "200"
LINK_COUNT_AFTER=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$API/credit-notes/$CN_ID/links" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))")
check "links count drops to 2" "$LINK_COUNT_AFTER" "2"
echo

# Edge case 3: Cascade delete
echo "=== Edge case 3: cascade delete (delete credit note, links should vanish) ==="
LINKS_BEFORE=$(docker exec invoice_tracker_db psql -U invoice_user -d invoice_tracker -tAc "SELECT count(*) FROM credit_note_links;")
echo "  Total link rows in DB before delete: $LINKS_BEFORE"
DEL_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE -H "Authorization: Bearer $ADMIN_TOKEN" "$API/credit-notes/$CN_ID")
check "credit note delete returns 200" "$DEL_CODE" "200"
LINKS_AFTER=$(docker exec invoice_tracker_db psql -U invoice_user -d invoice_tracker -tAc "SELECT count(*) FROM credit_note_links;")
echo "  Total link rows in DB after delete: $LINKS_AFTER"
DROP=$((LINKS_BEFORE - LINKS_AFTER))
check "cascade dropped 2 link rows" "$DROP" "2"
echo

# Final summary
echo "==================================="
echo "  PASSED: $PASS"
echo "  FAILED: $FAIL"
echo "==================================="
if (( FAIL == 0 )); then
  echo "✅ All Phase A tests passed. Green-light Phase B."
else
  echo "❌ Some tests failed — fix before Phase B."
fi
