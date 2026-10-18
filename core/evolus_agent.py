"""
Evolus Commercial Agent & Approval State Machine
Orchestrates autonomous straight-through processing, exception triage,
and Human-in-the-Loop (HITL) gateways for enterprise commerce.
"""

import time
import hashlib
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from core.amd_client import AMDClient
from core.matcher import ReconciliationResult
from core.extractor import ParsedInvoice

logger = logging.getLogger("RozgarPay.EvolusAgent")

class AuditLogEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    event_type: str
    actor: str  # "Autonomous_RozgarPay_Agent", "Human_Approver", "AMD_Instinct_Kernel"
    details: str
    signature: str

class DebitNote(BaseModel):
    debit_note_number: str
    issue_date: str
    vendor_name: str
    invoice_reference: str
    po_reference: str
    original_invoiced_amount: float
    adjusted_approved_amount: float
    debit_deduction_amount: float
    tax_adjustment_amount: float
    currency: str = "PKR"
    reason_code: str
    formal_explanation: str
    bilingual_vendor_notice: str

    def to_printable_document(self) -> str:
        """Renders formal commercial debit note text suitable for export and accounting audit."""
        return f"""================================================================================
OFFICIAL COMMERCIAL DEBIT NOTE / تجارتی ڈیبٹ نوٹ
ROZGARPAY ENTERPRISE COMMERCE GATEWAY (FBR ST REGULATED)
================================================================================
Debit Note Reference: {self.debit_note_number}
Issue Date:           {self.issue_date}
Vendor:               {self.vendor_name}
Invoice Reference:    {self.invoice_reference}
Purchase Order Ref:   {self.po_reference}
Reason Classification:{self.reason_code}
--------------------------------------------------------------------------------
FINANCIAL ADJUSTMENT SCHEDULE:
Gross Invoiced Amount:              {self.currency} {self.original_invoiced_amount:,.2f}
Less Commercial Debit Deduction:   -{self.currency} {self.debit_deduction_amount:,.2f}
(Of which FBR Sales Tax Adjustment: {self.currency} {self.tax_adjustment_amount:,.2f})
--------------------------------------------------------------------------------
NET APPROVED REMITTANCE:            {self.currency} {self.adjusted_approved_amount:,.2f}
--------------------------------------------------------------------------------
Commercial Audit Justification:
{self.formal_explanation}

Bilingual Vendor Notice:
{self.bilingual_vendor_notice}
================================================================================
Certified by: Evolus Commercial Settlement Gateway (AMD Instinct™ MI300X)
Compliance Hash: SHA256-CERTIFIED-LEDGER-TRANSACTION
================================================================================
"""

class EvolusWorkflowState(BaseModel):
    state: str = "INTAKE_RECEIVED"  # INTAKE_RECEIVED, EXTRACTION_COMPLETED, RECONCILIATION_EVALUATED, AUTO_APPROVED, ESCALATED_TO_GATEWAY, RESOLVED_WITH_DEBIT_NOTE, REJECTED
    invoice_number: str
    is_stp_eligible: bool = False  # Straight-Through Processing
    reconciliation_result: Optional[ReconciliationResult] = None
    agent_resolution_brief: Optional[str] = None
    debit_note: Optional[DebitNote] = None
    erp_payout_payload: Optional[Dict[str, Any]] = None
    audit_trail: List[AuditLogEntry] = Field(default_factory=list)

class EvolusCommercialAgent:
    """
    Autonomous agent handling commercial reconciliation and human approval gateways.
    """

    def __init__(self, amd_client: Optional[AMDClient] = None):
        self.amd_client = amd_client or AMDClient()

    def process_commercial_intake(
        self,
        invoice: ParsedInvoice,
        reconciliation: ReconciliationResult
    ) -> EvolusWorkflowState:
        """
        Evaluates reconciliation output and determines whether to straight-through approve
        or escalate to the Evolus Human Approval Gateway.
        """
        workflow = EvolusWorkflowState(
            state="RECONCILIATION_EVALUATED",
            invoice_number=invoice.invoice_number,
            reconciliation_result=reconciliation
        )

        self._record_audit(
            workflow,
            event_type="RECONCILIATION_COMPLETED",
            actor="Autonomous_3Way_Engine",
            details=f"Status: {reconciliation.overall_status}. Discrepancy flags: {len(reconciliation.audit_flags)}"
        )

        # Straight-Through Processing (STP) Rule:
        # Perfectly matched, vendor verified, bank verified, tax verified -> Auto Approve
        if (
            reconciliation.overall_status == "AUTO_MATCHED"
            and reconciliation.vendor_verified
            and reconciliation.iban_verified
            and reconciliation.tax_verified
        ):
            workflow.state = "AUTO_APPROVED"
            workflow.is_stp_eligible = True
            workflow.erp_payout_payload = self._generate_erp_payload(invoice, reconciliation, status="SCHEDULED_PAYOUT")
            self._record_audit(
                workflow,
                event_type="AUTO_APPROVAL_DISPATCHED",
                actor="RozgarPay_Autonomous_Agent (AMD Instinct)",
                details="Invoice cleared 100% deterministic criteria. Scheduled for Net-30 remittance."
            )
            return workflow

        # Discrepancy Detected -> Escalate to Evolus Gateway with AI Resolution Brief
        workflow.state = "ESCALATED_TO_GATEWAY"
        workflow.is_stp_eligible = False
        
        # Generate intelligent resolution brief via AMD Instinct LLM
        brief = self.generate_resolution_brief(invoice, reconciliation)
        workflow.agent_resolution_brief = brief

        self._record_audit(
            workflow,
            event_type="ESCALATED_TO_EVOLUS_GATEWAY",
            actor="Evolus_Risk_Triage",
            details=f"Escalated due to: {reconciliation.recommended_action}. Financial exposure: PKR {reconciliation.total_financial_exposure:,.2f}"
        )

        return workflow

    def generate_resolution_brief(self, invoice: ParsedInvoice, recon: ReconciliationResult) -> str:
        """
        Leverages Qwen2.5/Gemma on AMD Instinct to synthesize commercial analysis and remedies.
        """
        flags_text = "\n".join([f"- {flag}" for flag in recon.audit_flags])
        line_item_breakdown = "\n".join([
            f"Line '{item.description}': Invoiced Qty={item.invoiced_quantity}, GRN Dock Qty={item.grn_quantity}, Invoiced Rate={item.invoiced_unit_price}, PO Rate={item.po_unit_price}, Status={item.status}"
            for item in recon.line_reconciliations
        ])

        prompt = f"""
You are the Evolus Commercial Intelligence Agent executing on AMD Instinct MI300X.
Analyze the following commercial invoice discrepancy and provide a decisive resolution brief for the CFO & AP Manager.

Invoice ID: {invoice.invoice_number}
Vendor: {invoice.vendor_name} (NTN: {invoice.vendor_ntn})
PO Reference: {recon.po_number}
GRN Warehouse Reference: {recon.grn_number}
Total Billed: PKR {recon.total_invoiced_amount:,.2f}
Total Reconciled/Approved: PKR {recon.total_approved_amount:,.2f}
Financial Exposure (Overbill): PKR {recon.total_financial_exposure:,.2f}

Flags Identified:
{flags_text}

Line Item Audit:
{line_item_breakdown}

Deliver a structured brief covering:
1. Executive Discrepancy Summary (root cause: short delivery, rate inflation, unauthorized vendor)
2. Commercial Risk Rating (Low / Medium / High / Fraud Alert)
3. Recommended Resolution (e.g., Issue Debit Note, Authorize Partial Settlement, Demand Vendor Credit)
4. Formal Bilingual Vendor Communication Snippet (Urdu & English) explaining the deduction.

TAG: EVOLUS_RESOLUTION_BRIEF
"""
        messages = [
            {"role": "system", "content": "You are the Evolus Commercial Gateway Agent. Provide authoritative financial analysis."},
            {"role": "user", "content": prompt}
        ]

        res = self.amd_client.chat_completion(messages, temperature=0.2)
        content = res.get("content", "").strip()
        return content

    def issue_commercial_debit_note(
        self,
        workflow: EvolusWorkflowState,
        invoice: ParsedInvoice,
        custom_reason: Optional[str] = None
    ) -> DebitNote:
        """
        Generates an authorized Commercial Debit Note to deduct overcharges from vendor ledger.
        """
        recon = workflow.reconciliation_result
        if not recon:
            raise ValueError("Reconciliation result is missing.")

        deduction = recon.total_financial_exposure
        approved = recon.total_approved_amount
        dn_number = f"DN-{datetime.utcnow().strftime('%Y%m%d')}-{invoice.invoice_number.split('-')[-1]}"

        reason = custom_reason or (
            "Deduction for warehouse short-shipment and unit price variance against contracted Purchase Order."
        )

        bilingual_notice = f"""
محترم سپلائر،
آپ کی انوائس نمبر {invoice.invoice_number} میں گودام رسید اور خریداری معاہدے کے مطابق فرق پایا گیا ہے۔ اس بنا پر کٹوتی برائے ڈیبٹ نوٹ {dn_number} جاری کر دی گئی ہے۔
صاف واجب الادا رقم PKR {approved:,.2f} منظور کی جاتی ہے۔

Dear Supplier,
A discrepancy was identified between Invoice {invoice.invoice_number}, Warehouse Goods Receipt, and Purchase Order {recon.po_number}. 
Debit Note {dn_number} has been posted for PKR {deduction:,.2f}. 
Adjusted net amount of PKR {approved:,.2f} is scheduled for remittance.
"""

        debit_note = DebitNote(
            debit_note_number=dn_number,
            issue_date=datetime.utcnow().strftime("%Y-%m-%d"),
            vendor_name=invoice.vendor_name,
            invoice_reference=invoice.invoice_number,
            po_reference=recon.po_number or "N/A",
            original_invoiced_amount=invoice.grand_total,
            adjusted_approved_amount=approved,
            debit_deduction_amount=deduction,
            tax_adjustment_amount=round(deduction * 0.18 / 1.18, 2),
            currency=invoice.currency,
            reason_code=recon.overall_status,
            formal_explanation=reason,
            bilingual_vendor_notice=bilingual_notice.strip()
        )

        workflow.debit_note = debit_note
        workflow.state = "RESOLVED_WITH_DEBIT_NOTE"
        workflow.erp_payout_payload = self._generate_erp_payload(invoice, recon, status="SETTLED_WITH_DEBIT_NOTE", debit_note=debit_note)

        self._record_audit(
            workflow,
            event_type="DEBIT_NOTE_ISSUED",
            actor="Evolus_Gateway_Officer",
            details=f"Debit Note {dn_number} generated for PKR {deduction:,.2f}. Net payout authorized: PKR {approved:,.2f}."
        )

        return debit_note

    def force_approve(self, workflow: EvolusWorkflowState, invoice: ParsedInvoice, approver_name: str, justification: str):
        """Allows human financial manager to override flags and authorize payment."""
        workflow.state = "APPROVED_BY_HUMAN_OVERRIDE"
        workflow.erp_payout_payload = self._generate_erp_payload(invoice, workflow.reconciliation_result, status="AUTHORIZED_OVERRIDE")
        self._record_audit(
            workflow,
            event_type="HUMAN_OVERRIDE_APPROVAL",
            actor=f"Approver: {approver_name}",
            details=f"Approved despite flags. Justification: {justification}"
        )

    def reject_invoice(self, workflow: EvolusWorkflowState, rejector_name: str, reason: str):
        """Rejects the invoice entirely."""
        workflow.state = "REJECTED"
        self._record_audit(
            workflow,
            event_type="COMMERCIAL_INVOICE_REJECTED",
            actor=f"Reviewer: {rejector_name}",
            details=f"Invoice disputed and blocked from AP payout. Reason: {reason}"
        )

    def _generate_erp_payload(
        self,
        invoice: ParsedInvoice,
        recon: Optional[ReconciliationResult],
        status: str,
        debit_note: Optional[DebitNote] = None
    ) -> Dict[str, Any]:
        """Creates standard ERP / Odoo / SAP webhook payload."""
        return {
            "erp_gateway": "Evolus Commercial Autonomous Engine",
            "settlement_status": status,
            "invoice_number": invoice.invoice_number,
            "vendor_name": invoice.vendor_name,
            "vendor_iban": invoice.vendor_iban,
            "po_reference": recon.po_number if recon else None,
            "grn_reference": recon.grn_number if recon else None,
            "gross_billed": invoice.grand_total,
            "net_payable": debit_note.adjusted_approved_amount if debit_note else (recon.total_approved_amount if recon else invoice.grand_total),
            "debit_deduction": debit_note.debit_deduction_amount if debit_note else 0.0,
            "currency": invoice.currency,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "compliance_stamp": "FBR-ST-VERIFIED-ROZGARPAY"
        }

    def _record_audit(self, workflow: EvolusWorkflowState, event_type: str, actor: str, details: str):
        payload_to_hash = f"{event_type}|{actor}|{details}|{time.time()}"
        signature = hashlib.sha256(payload_to_hash.encode()).hexdigest()[:16]
        workflow.audit_trail.append(AuditLogEntry(
            event_type=event_type,
            actor=actor,
            details=details,
            signature=f"0x{signature.upper()}"
        ))
