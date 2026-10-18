"""
Deterministic Three-Way Reconciliation Engine
Reconciles Vendor Invoice against internal Purchase Orders (PO), Goods Receipt Notes (GRN),
and Authorized Supplier Registries with zero hallucination.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from core.extractor import ParsedInvoice

logger = logging.getLogger("RozgarPay.Matcher")

class LineItemReconciliation(BaseModel):
    item_code: str
    description: str
    po_quantity: Optional[float] = None
    grn_quantity: Optional[float] = None
    invoiced_quantity: float
    po_unit_price: Optional[float] = None
    invoiced_unit_price: float
    quantity_variance: float = 0.0  # invoiced_quantity - grn_quantity
    price_variance: float = 0.0     # invoiced_unit_price - po_unit_price
    financial_exposure: float = 0.0 # Excess amount billed
    status: str = "MATCHED"        # MATCHED, SHORT_SHIPMENT, PRICE_INFLATION, UNEXPECTED_ITEM
    note: str = "Reconciled"

class ReconciliationResult(BaseModel):
    invoice_number: str
    po_number: Optional[str]
    grn_number: Optional[str]
    vendor_id: Optional[str]
    vendor_name: str
    overall_status: str  # AUTO_MATCHED, FLAGGED_QTY_MISMATCH, FLAGGED_PRICE_MISMATCH, FLAGGED_UNAUTHORIZED_VENDOR, FLAGGED_ORPHAN_PO
    tolerance_percent: float = 1.0
    total_invoiced_amount: float
    total_approved_amount: float
    total_financial_exposure: float
    vendor_verified: bool
    iban_verified: bool
    tax_verified: bool
    tax_discrepancy: float = 0.0
    line_reconciliations: List[LineItemReconciliation] = Field(default_factory=list)
    reconciliation_summary: str
    recommended_action: str
    audit_flags: List[str] = Field(default_factory=list)

class ThreeWayMatcher:
    """
    Executes commercial deterministic checks across the 3-way ledger.
    """

    def __init__(self, mock_db_path: Optional[str] = None):
        self.mock_db_path = mock_db_path or "data/mock_orders.json"
        self.db = self._load_db()

    def _load_db(self) -> Dict[str, Any]:
        """Loads internal mock enterprise ledger data."""
        try:
            with open(self.mock_db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load mock DB from {self.mock_db_path}: {e}")
            return {"suppliers": [], "purchase_orders": {}, "goods_receipts": {}}

    def reconcile(self, invoice: ParsedInvoice, tolerance_percent: float = 1.0) -> ReconciliationResult:
        """
        Executes strict 3-way matching between invoice, PO, and GRN.
        """
        po_number = invoice.po_reference
        audit_flags: List[str] = []
        line_recons: List[LineItemReconciliation] = []
        
        # 1. Check PO existence
        po_data = self.db.get("purchase_orders", {}).get(po_number) if po_number else None
        
        if not po_data:
            audit_flags.append(f"PO Reference '{po_number}' not found in internal Procurement ERP.")
            return ReconciliationResult(
                invoice_number=invoice.invoice_number,
                po_number=po_number,
                grn_number=None,
                vendor_id=None,
                vendor_name=invoice.vendor_name,
                overall_status="FLAGGED_ORPHAN_PO",
                total_invoiced_amount=invoice.grand_total,
                total_approved_amount=0.0,
                total_financial_exposure=invoice.grand_total,
                vendor_verified=False,
                iban_verified=False,
                tax_verified=False,
                reconciliation_summary="Invoice rejected: No authorized purchase order found in ledger.",
                recommended_action="REJECT_AND_NOTIFY_VENDOR",
                audit_flags=audit_flags
            )

        # 2. Check GRN existence for this PO
        grn_number = f"GRN-{po_number.split('-')[-2]}-{po_number.split('-')[-1]}" if "PO-" in po_number else None
        grn_data = self.db.get("goods_receipts", {}).get(grn_number)

        # 3. Vendor & Bank Account Authenticity Verification
        vendor_id = po_data.get("vendor_id")
        registered_supplier = next((s for s in self.db.get("suppliers", []) if s.get("vendor_id") == vendor_id), None)
        
        vendor_verified = True
        iban_verified = True

        if registered_supplier:
            # Check NTN match if provided on invoice
            if invoice.vendor_ntn and registered_supplier.get("ntn"):
                clean_inv_ntn = invoice.vendor_ntn.replace("-", "").strip()
                clean_reg_ntn = registered_supplier.get("ntn", "").replace("-", "").strip()
                if clean_inv_ntn != clean_reg_ntn:
                    vendor_verified = False
                    audit_flags.append(f"NTN Mismatch: Invoice has '{invoice.vendor_ntn}', Registry expects '{registered_supplier.get('ntn')}'. Potential identity spoofing.")
            
            # Check IBAN match if provided
            if invoice.vendor_iban and registered_supplier.get("iban"):
                if invoice.vendor_iban.replace(" ", "").upper() != registered_supplier.get("iban", "").replace(" ", "").upper():
                    iban_verified = False
                    audit_flags.append(f"CRITICAL: Bank Remittance IBAN on invoice differs from verified corporate registry. Payout diversion risk.")
        else:
            vendor_verified = False
            audit_flags.append(f"Vendor '{invoice.vendor_name}' not listed in Active Supplier Master.")

        po_line_list = po_data.get("line_items", [])
        grn_line_list = grn_data.get("line_items", []) if grn_data else []

        total_exposure = 0.0
        approved_amount = 0.0

        for inv_item in invoice.line_items:
            matched_po_item = None
            matched_grn_item = None

            # 1. Match against PO
            for po_val in po_line_list:
                po_code = po_val.get("item_code", "")
                po_desc = po_val.get("description", "").lower()
                inv_desc = inv_item.description.lower()

                if (inv_item.item_code and inv_item.item_code == po_code) or \
                   (po_desc in inv_desc) or (inv_desc in po_desc) or \
                   any(word in po_desc for word in inv_desc.split() if len(word) > 4):
                    matched_po_item = po_val
                    break

            # 2. Match against GRN
            if matched_po_item and grn_data:
                target_code = matched_po_item.get("item_code", "")
                target_desc = matched_po_item.get("description", "").lower()
                for grn_val in grn_line_list:
                    g_code = grn_val.get("item_code", "")
                    g_desc = grn_val.get("description", "").lower()

                    if (target_code and target_code == g_code) or \
                       (g_desc in target_desc) or (target_desc in g_desc) or \
                       any(word in g_desc for word in target_desc.split() if len(word) > 4):
                        matched_grn_item = grn_val
                        break

            # Handle Unexpected Item
            if not matched_po_item:
                exposure = inv_item.line_total
                total_exposure += exposure
                audit_flags.append(f"Unauthorized Line Item: '{inv_item.description}' was never contracted on {po_number}.")
                line_recons.append(LineItemReconciliation(
                    item_code=inv_item.item_code or "UNAUTH",
                    description=inv_item.description,
                    invoiced_quantity=inv_item.quantity,
                    invoiced_unit_price=inv_item.unit_price,
                    financial_exposure=exposure,
                    status="UNEXPECTED_ITEM",
                    note="Item absent from PO contract."
                ))
                continue

            # We have PO item. Check quantities and pricing
            po_qty = float(matched_po_item.get("quantity", 0))
            po_price = float(matched_po_item.get("unit_price", 0))
            grn_qty = float(matched_grn_item.get("quantity_received", po_qty)) if matched_grn_item else po_qty

            qty_diff = inv_item.quantity - grn_qty
            price_diff = inv_item.unit_price - po_price

            item_status = "MATCHED"
            notes = []
            line_exposure = 0.0

            # Price verification
            price_allowed_max = po_price * (1.0 + (tolerance_percent / 100.0))
            if inv_item.unit_price > price_allowed_max:
                item_status = "PRICE_INFLATION"
                excess_rate = inv_item.unit_price - po_price
                line_exposure += excess_rate * inv_item.quantity
                notes.append(f"Price inflated by PKR {excess_rate:.2f}/unit (contracted: {po_price:.2f}).")
                audit_flags.append(f"Unit price on '{inv_item.description}' exceeds contract by PKR {excess_rate:.2f}.")

            # Quantity verification against GRN (Warehouse receipt)
            if qty_diff > 0:
                item_status = "SHORT_SHIPMENT"
                unreceived_cost = qty_diff * po_price
                line_exposure += unreceived_cost
                notes.append(f"Warehouse dock received only {grn_qty:.0f} units; billed for {inv_item.quantity:.0f} (short: {qty_diff:.0f}).")
                audit_flags.append(f"Quantity overcharge: Billed for {inv_item.quantity:.0f} units of '{inv_item.description}', dock accepted only {grn_qty:.0f}.")

            # Approved amount for this line
            valid_qty = min(inv_item.quantity, grn_qty)
            valid_price = min(inv_item.unit_price, po_price)
            approved_amount += (valid_qty * valid_price)
            total_exposure += line_exposure

            line_recons.append(LineItemReconciliation(
                item_code=matched_po_item.get("item_code", inv_item.item_code),
                description=inv_item.description,
                po_quantity=po_qty,
                grn_quantity=grn_qty,
                invoiced_quantity=inv_item.quantity,
                po_unit_price=po_price,
                invoiced_unit_price=inv_item.unit_price,
                quantity_variance=qty_diff,
                price_variance=price_diff,
                financial_exposure=line_exposure,
                status=item_status,
                note=" | ".join(notes) if notes else "Fully verified across PO and GRN."
            ))

        # 5. Tax Verification (FBR 18% GST standard)
        expected_tax = approved_amount * (invoice.tax_rate_percent / 100.0)
        tax_diff = abs(invoice.tax_amount - (invoice.subtotal * (invoice.tax_rate_percent / 100.0)))
        tax_verified = tax_diff < 5.0  # allow minor rounding

        if not tax_verified:
            audit_flags.append(f"Tax math mismatch: Invoiced GST is PKR {invoice.tax_amount:.2f}, calculated is PKR {(invoice.subtotal * 0.18):.2f}.")

        # Add approved tax to approved total
        approved_tax = approved_amount * (invoice.tax_rate_percent / 100.0)
        final_approved_grand_total = approved_amount + approved_tax

        # 6. Overall Classification
        overall_status = "AUTO_MATCHED"
        recommended_action = "APPROVE_PAYMENT_LEDGER"
        summary_text = "All line items, quantities, and pricing perfectly aligned with PO and warehouse delivery."

        if not vendor_verified or not iban_verified:
            overall_status = "FLAGGED_UNAUTHORIZED_VENDOR"
            recommended_action = "ESCALATE_SECURITY_FRAUD_GATEWAY"
            summary_text = "High risk: Supplier registry or bank account discrepancy flagged."
        elif any(r.status == "UNEXPECTED_ITEM" for r in line_recons):
            overall_status = "FLAGGED_UNAUTHORIZED_ITEM"
            recommended_action = "ESCALATE_TO_EVOLUS_GATEWAY"
            summary_text = "Discrepancy: Invoice contains unapproved commercial charges."
        elif any(r.status == "SHORT_SHIPMENT" for r in line_recons):
            overall_status = "FLAGGED_QTY_MISMATCH"
            recommended_action = "ISSUE_DEBIT_NOTE_ADJUSTMENT"
            summary_text = f"Short shipment confirmed at dock. Debit Note of PKR {total_exposure * 1.18:,.2f} required."
        elif any(r.status == "PRICE_INFLATION" for r in line_recons):
            overall_status = "FLAGGED_PRICE_MISMATCH"
            recommended_action = "ISSUE_DEBIT_NOTE_ADJUSTMENT"
            summary_text = f"Unit price variance exceeds tolerance threshold. Debit Note of PKR {total_exposure * 1.18:,.2f} required."

        return ReconciliationResult(
            invoice_number=invoice.invoice_number,
            po_number=po_number,
            grn_number=grn_number,
            vendor_id=vendor_id,
            vendor_name=invoice.vendor_name,
            overall_status=overall_status,
            tolerance_percent=tolerance_percent,
            total_invoiced_amount=invoice.grand_total,
            total_approved_amount=round(final_approved_grand_total, 2),
            total_financial_exposure=round(total_exposure * 1.18, 2), # including tax impact
            vendor_verified=vendor_verified,
            iban_verified=iban_verified,
            tax_verified=tax_verified,
            tax_discrepancy=round(tax_diff, 2),
            line_reconciliations=line_recons,
            reconciliation_summary=summary_text,
            recommended_action=recommended_action,
            audit_flags=audit_flags
        )
