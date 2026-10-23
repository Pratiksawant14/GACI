"""
Parameterized Cypher Query Templates for Idempotent Graph Projection.
All projection queries use MERGE to guarantee idempotent, re-entrant execution.
"""

# --- Node Merges ---
MERGE_BUSINESS = """
MERGE (b:Business {id: $id})
SET b.name = $name,
    b.currency = $currency
"""

MERGE_CUSTOMER = """
MERGE (c:Customer {id: $id})
SET c.name = $name,
    c.credit_limit = $credit_limit,
    c.business_id = $business_id
"""

MERGE_SUPPLIER = """
MERGE (s:Supplier {id: $id})
SET s.name = $name,
    s.business_id = $business_id
"""

MERGE_BANK_ACCOUNT = """
MERGE (a:BankAccount {id: $id})
SET a.name = $account_name,
    a.type = $account_type,
    a.balance = $current_balance,
    a.business_id = $business_id
"""

MERGE_INVOICE = """
MERGE (i:Invoice {id: $id})
SET i.invoice_number = $invoice_number,
    i.amount = $total_amount,
    i.paid_amount = $paid_amount,
    i.unpaid_balance = $unpaid_balance,
    i.issue_date = date($issue_date),
    i.due_date = date($due_date),
    i.status = $status,
    i.business_id = $business_id,
    i.customer_id = $customer_id
"""

MERGE_PAYMENT = """
MERGE (p:Payment {id: $id})
SET p.ref = $payment_reference,
    p.amount = $amount,
    p.payment_date = date($payment_date),
    p.method = $payment_method,
    p.status = $status,
    p.business_id = $business_id,
    p.bank_account_id = $bank_account_id
"""

MERGE_SUPPLIER_ADVANCE = """
MERGE (sa:SupplierAdvance {id: $id})
SET sa.ref = $advance_reference,
    sa.amount = $advance_amount,
    sa.fulfilled_amount = $fulfilled_amount,
    sa.unfulfilled_balance = $unfulfilled_balance,
    sa.disbursement_date = date($disbursement_date),
    sa.expected_delivery_date = date($expected_delivery_date),
    sa.status = $status,
    sa.business_id = $business_id,
    sa.supplier_id = $supplier_id
"""

MERGE_DELIVERY = """
MERGE (d:Delivery {id: $id})
SET d.ref = $delivery_reference,
    d.delivery_date = date($delivery_date),
    d.value = $delivered_value,
    d.business_id = $business_id,
    d.supplier_id = $supplier_id
"""

MERGE_OBLIGATION = """
MERGE (o:Obligation {id: $id})
SET o.name = $obligation_name,
    o.category = $category,
    o.amount = $amount,
    o.due_date = date($due_date),
    o.status = $status,
    o.business_id = $business_id
"""

# --- Relationship Merges ---
LINK_CUSTOMER_INVOICE = """
MATCH (c:Customer {id: $customer_id})
MATCH (i:Invoice {id: $invoice_id})
MERGE (c)-[:ISSUED_INVOICE]->(i)
"""

LINK_CUSTOMER_PAYMENT = """
MATCH (c:Customer {id: $customer_id})
MATCH (p:Payment {id: $payment_id})
MERGE (c)-[:MADE_PAYMENT]->(p)
"""

LINK_PAYMENT_INVOICE = """
MATCH (p:Payment {id: $payment_id})
MATCH (i:Invoice {id: $invoice_id})
MERGE (p)-[r:ALLOCATED_TO]->(i)
SET r.amount = $allocated_amount
"""

LINK_PAYMENT_BANK = """
MATCH (p:Payment {id: $payment_id})
MATCH (a:BankAccount {id: $bank_account_id})
MERGE (p)-[:DEPOSITED_IN]->(a)
"""

LINK_BUSINESS_ADVANCE = """
MATCH (b:Business {id: $business_id})
MATCH (sa:SupplierAdvance {id: $advance_id})
MERGE (b)-[:DISBURSED_ADVANCE]->(sa)
"""

LINK_ADVANCE_SUPPLIER = """
MATCH (sa:SupplierAdvance {id: $advance_id})
MATCH (s:Supplier {id: $supplier_id})
MERGE (sa)-[:PAID_TO]->(s)
"""

LINK_DELIVERY_ADVANCE = """
MATCH (d:Delivery {id: $delivery_id})
MATCH (sa:SupplierAdvance {id: $advance_id})
MERGE (d)-[:FULFILLS]->(sa)
"""

LINK_BUSINESS_OBLIGATION = """
MATCH (b:Business {id: $business_id})
MATCH (o:Obligation {id: $obligation_id})
MERGE (b)-[:COMMITTED_TO]->(o)
"""

LINK_OBLIGATION_BANK = """
MATCH (o:Obligation {id: $obligation_id})
MATCH (a:BankAccount {id: $bank_account_id})
MERGE (o)-[:PAYABLE_FROM]->(a)
"""
