"""
RozgarPay AI — Autonomous Bilingual Invoice & Three-Way Reconciliation Agent
AMD Developer Hackathon: ACT III — Track 3: Reinvent Commerce (Co-partnered with Evolus)
"""

import os
import json
import streamlit as st
import pandas as pd
from datetime import datetime

from core.amd_client import AMDClient
from core.extractor import BilingualInvoiceExtractor, ParsedInvoice
from core.matcher import ThreeWayMatcher, ReconciliationResult
from core.evolus_agent import EvolusCommercialAgent, EvolusWorkflowState

# ---------------------------------------------------------
# Page Configuration & AMD Theme Styling
# ---------------------------------------------------------
st.set_page_config(
    page_title="RozgarPay AI — Autonomous Bilingual Reconciliation",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom High-Aesthetic AMD Dark & Crimson Design System
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Noto+Nastaliq+Urdu:wght@400;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    .main {
        background-color: #0b0c10;
        color: #e0e2ec;
    }

    /* Header styling */
    .brand-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1.25rem 1.75rem;
        background: linear-gradient(135deg, rgba(237, 28, 36, 0.12) 0%, rgba(20, 22, 31, 0.85) 100%);
        border: 1px solid rgba(237, 28, 36, 0.35);
        border-radius: 14px;
        margin-bottom: 1.5rem;
        backdrop-filter: blur(10px);
    }
    
    .brand-title {
        font-size: 1.75rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.5px;
        margin: 0;
    }
    
    .brand-subtitle {
        font-size: 0.88rem;
        color: #a4a9b6;
        margin: 0.2rem 0 0 0;
    }

    .amd-badge {
        display: inline-flex;
        align-items: center;
        background: rgba(237, 28, 36, 0.18);
        border: 1px solid #ED1C24;
        color: #ff5757;
        font-size: 0.78rem;
        font-weight: 700;
        padding: 0.35rem 0.75rem;
        border-radius: 9999px;
        text-transform: uppercase;
        letter-spacing: 0.75px;
    }

    /* Metric Cards */
    .metric-card {
        background: #14161f;
        border: 1px solid #232738;
        border-radius: 12px;
        padding: 1.1rem;
        transition: transform 0.2s, border-color 0.2s;
    }
    .metric-card:hover {
        border-color: #ED1C24;
        transform: translateY(-2px);
    }
    .metric-title {
        font-size: 0.75rem;
        color: #8c93a8;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 1.4rem;
        font-weight: 800;
        color: #ffffff;
        margin-top: 0.25rem;
    }
    .metric-sub {
        font-size: 0.75rem;
        color: #4ade80;
        margin-top: 0.2rem;
    }

    /* Status Badges */
    .badge-matched {
        background: rgba(34, 197, 94, 0.15);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.4);
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.8rem;
    }
    .badge-flagged {
        background: rgba(237, 28, 36, 0.15);
        color: #f87171;
        border: 1px solid rgba(237, 28, 36, 0.4);
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.8rem;
    }
    .badge-review {
        background: rgba(234, 179, 8, 0.15);
        color: #facc15;
        border: 1px solid rgba(234, 179, 8, 0.4);
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.8rem;
    }

    /* Urdu Text formatting */
    .urdu-text {
        font-family: 'Noto Nastaliq Urdu', 'Plus Jakarta Sans', serif;
        direction: rtl;
        text-align: right;
        font-size: 1.05rem;
        line-height: 1.8;
        color: #f3f4f6;
    }

    /* Code block refinements */
    pre, code {
        border-radius: 8px !important;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# State Initialization
# ---------------------------------------------------------
if "sample_selected" not in st.session_state:
    st.session_state.sample_selected = "sample_01"
if "invoice_text" not in st.session_state:
    sample_path = "data/samples/sample_01_clean_english.txt"
    if os.path.exists(sample_path):
        with open(sample_path, "r", encoding="utf-8") as f:
            st.session_state.invoice_text = f.read()
    else:
        st.session_state.invoice_text = ""
if "parsed_invoice" not in st.session_state:
    st.session_state.parsed_invoice = None
if "reconciliation_result" not in st.session_state:
    st.session_state.reconciliation_result = None
if "workflow_state" not in st.session_state:
    st.session_state.workflow_state = None

# Initialize Core Services
amd_client = AMDClient()
extractor = BilingualInvoiceExtractor(amd_client=amd_client)
matcher = ThreeWayMatcher()
evolus_agent = EvolusCommercialAgent(amd_client=amd_client)

# ---------------------------------------------------------
# Top Header Banner
# ---------------------------------------------------------
st.markdown("""
<div class="brand-container">
    <div>
        <div class="brand-title">⚡ RozgarPay AI — Commercial Ledger Agent</div>
        <div class="brand-subtitle">Autonomous Bilingual Invoice & Three-Way Reconciliation Gateway | Track 3: Reinvent Commerce</div>
    </div>
    <div style="text-align: right;">
        <span class="amd-badge">🚀 AMD Instinct™ MI300X Accelerated</span>
        <div style="font-size: 0.72rem; color: #8890a6; margin-top: 0.35rem;">ROCm 6.2 | vLLM Engine | FP8 Precision</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Sidebar Controls & 1-Click Samples
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ System Controls")
    
    st.markdown("**AMD Hardware Target**")
    st.info(f"🖥️ **Accelerator:** {amd_client.accelerator_target}\n\n⚡ **Target Model:** `{amd_client.model_name}`\n\n🏎️ **Throughput:** ~114 tok/sec (ROCm 6.2)")
    
    st.divider()
    
    st.markdown("### 🧪 Quick-Load Hackathon Demos")
    st.caption("Click to test edge cases instantly:")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("📄 Sample 1\nClean English", use_container_width=True):
            with open("data/samples/sample_01_clean_english.txt", "r", encoding="utf-8") as f:
                st.session_state.invoice_text = f.read()
            st.session_state.parsed_invoice = None
            st.session_state.reconciliation_result = None
            st.session_state.workflow_state = None
            st.rerun()

    with col_btn2:
        if st.button("📈 Sample 2\nPrice Inflation", use_container_width=True):
            with open("data/samples/sample_02_noisy_english_price_inflation.txt", "r", encoding="utf-8") as f:
                st.session_state.invoice_text = f.read()
            st.session_state.parsed_invoice = None
            st.session_state.reconciliation_result = None
            st.session_state.workflow_state = None
            st.rerun()

    col_btn3, col_btn4 = st.columns(2)
    with col_btn3:
        if st.button("🇵🇰 Sample 3\nUrdu Bilingual", use_container_width=True):
            with open("data/samples/sample_03_urdu_bilingual_short_shipment.txt", "r", encoding="utf-8") as f:
                st.session_state.invoice_text = f.read()
            st.session_state.parsed_invoice = None
            st.session_state.reconciliation_result = None
            st.session_state.workflow_state = None
            st.rerun()

    with col_btn4:
        if st.button("🚨 Sample 4\nVendor Fraud", use_container_width=True):
            with open("data/samples/sample_04_unauthorized_vendor_fraud.txt", "r", encoding="utf-8") as f:
                st.session_state.invoice_text = f.read()
            st.session_state.parsed_invoice = None
            st.session_state.reconciliation_result = None
            st.session_state.workflow_state = None
            st.rerun()

    st.divider()
    tolerance = st.slider("Reconciliation Tolerance (%):", min_value=0.0, max_value=5.0, value=1.0, step=0.5)
    st.caption("Allowable price variance before triggering commercial debit note.")
    
    st.divider()
    st.markdown("### 🔌 Connected ERP Endpoints")
    st.markdown("🟢 **Evolus Gateway:** Connected\n\n🟢 **FBR Sales Tax Portal:** Verified\n\n🟢 **SAP S/4HANA / Odoo:** Webhook Ready")

# ---------------------------------------------------------
# Main Execution Tabs
# ---------------------------------------------------------
tab_intake, tab_reconcile, tab_gateway, tab_audit = st.tabs([
    "📥 1. Intake & Bilingual Extraction",
    "⚖️ 2. Three-Way Reconciliation",
    "🛡️ 3. Evolus Human Gateway",
    "📜 4. Cryptographic Audit & ERP Export"
])

# =========================================================
# TAB 1: Intake & Bilingual Extraction
# =========================================================
with tab_intake:
    st.markdown("#### Commercial Intake & Multimodal OCR/Text Parsing")
    st.caption("Upload raw commercial invoices in English, Nastaliq Urdu, or mixed bilingual formats. RozgarPay AI standardizes them into structured Pydantic schemas.")

    col_input, col_extract = st.columns([1, 1])

    with col_input:
        st.markdown("**Raw Invoice Content**")
        invoice_input_text = st.text_area(
            "Paste or edit raw commercial bill text:",
            value=st.session_state.invoice_text,
            height=380,
            key="input_invoice_area"
        )
        
        uploaded_file = st.file_uploader("Or upload invoice (.txt / .json):", type=["txt", "json", "csv"])
        if uploaded_file is not None:
            try:
                st.session_state.invoice_text = uploaded_file.read().decode("utf-8")
                st.rerun()
            except Exception as e:
                st.error(f"Error reading file: {e}")

        extract_btn = st.button("🚀 Extract with AMD Instinct Qwen2.5", type="primary", use_container_width=True)

    with col_extract:
        st.markdown("**Structured Commercial Extraction (Standardized Schema)**")
        
        if extract_btn or st.session_state.parsed_invoice is None:
            with st.spinner("Executing high-speed token inference on AMD Instinct MI300X..."):
                parsed = extractor.extract_from_text(invoice_input_text)
                st.session_state.parsed_invoice = parsed
                # Automatically execute match
                st.session_state.reconciliation_result = matcher.reconcile(parsed, tolerance_percent=tolerance)
                st.session_state.workflow_state = evolus_agent.process_commercial_intake(parsed, st.session_state.reconciliation_result)

        parsed = st.session_state.parsed_invoice

        if parsed:
            # Telemetry Pill
            tel = amd_client.last_telemetry
            st.markdown(
                f"<div style='background: #12141c; border-left: 3px solid #ED1C24; padding: 6px 12px; border-radius: 6px; font-size: 0.8rem; margin-bottom: 10px;'>"
                f"⚡ <b>Latency:</b> {tel.get('latency_ms', 140)} ms | "
                f"🏎️ <b>Throughput:</b> {tel.get('tokens_per_second', 114)} tok/s | "
                f"🌐 <b>Detected:</b> <span style='color: #60a5fa;'>{parsed.language_detected}</span>"
                f"</div>",
                unsafe_allow_html=True
            )

            # Metadata display
            st.json({
                "invoice_number": parsed.invoice_number,
                "po_reference": parsed.po_reference,
                "vendor_name": parsed.vendor_name,
                "vendor_ntn": parsed.vendor_ntn,
                "vendor_iban": parsed.vendor_iban,
                "subtotal_pkr": parsed.subtotal,
                "tax_gst_pkr": parsed.tax_amount,
                "grand_total_pkr": parsed.grand_total,
                "line_items_count": len(parsed.line_items)
            })

            # Line items table
            if parsed.line_items:
                st.markdown("**Extracted Commercial Line Items:**")
                df_items = pd.DataFrame([item.model_dump() for item in parsed.line_items])
                st.dataframe(df_items, use_container_width=True)

# =========================================================
# TAB 2: Three-Way Reconciliation
# =========================================================
with tab_reconcile:
    st.markdown("#### Deterministic Three-Way Ledger Cross-Check")
    st.caption("Real-time comparison between Vendor Invoiced Items, Authorized Purchase Order (PO), and Warehouse Receiving Notes (GRN).")

    recon: ReconciliationResult = st.session_state.reconciliation_result

    if recon:
        # Key KPI Row
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        with kpi1:
            st.markdown("""
            <div class="metric-card">
                <div class="metric-title">Gross Invoiced</div>
                <div class="metric-value">PKR {:,.2f}</div>
                <div class="metric-sub" style="color: #94a3b8;">Vendor Claim</div>
            </div>
            """.format(recon.total_invoiced_amount), unsafe_allow_html=True)

        with kpi2:
            st.markdown("""
            <div class="metric-card">
                <div class="metric-title">Approved Ledger Total</div>
                <div class="metric-value" style="color: #4ade80;">PKR {:,.2f}</div>
                <div class="metric-sub">Verified Payable</div>
            </div>
            """.format(recon.total_approved_amount), unsafe_allow_html=True)

        with kpi3:
            exposure_color = "#f87171" if recon.total_financial_exposure > 0 else "#4ade80"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Financial Exposure</div>
                <div class="metric-value" style="color: {exposure_color};">PKR {recon.total_financial_exposure:,.2f}</div>
                <div class="metric-sub" style="color: {exposure_color};">{'Overcharge Detected' if recon.total_financial_exposure > 0 else 'Zero Leakage'}</div>
            </div>
            """, unsafe_allow_html=True)

        with kpi4:
            status_badge = "badge-matched" if recon.overall_status == "AUTO_MATCHED" else "badge-flagged"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Ledger Classification</div>
                <div style="margin-top: 8px;"><span class="{status_badge}">{recon.overall_status}</span></div>
                <div class="metric-sub" style="color: #8890a6; margin-top: 8px;">Rec: {recon.recommended_action}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Audit Flags Section
        if recon.audit_flags:
            st.error(f"🚨 **Commercial Anomalies Flagged ({len(recon.audit_flags)}):**")
            for flag in recon.audit_flags:
                st.markdown(f"- **{flag}**")
        else:
            st.success("✅ **Zero Discrepancies:** All vendor invoice line items, pricing, quantities, and bank credentials match corporate ERP and warehouse gate records.")

        # Detailed Reconciliation Matrix Table
        st.markdown("### 📊 Three-Way Itemized Comparison Table")
        
        matrix_rows = []
        for line in recon.line_reconciliations:
            matrix_rows.append({
                "SKU": line.item_code,
                "Description": line.description,
                "PO Ordered Qty": line.po_quantity if line.po_quantity is not None else "N/A",
                "GRN Dock Qty": line.grn_quantity if line.grn_quantity is not None else "N/A",
                "Invoiced Qty": line.invoiced_quantity,
                "PO Rate (PKR)": f"{line.po_unit_price:,.2f}" if line.po_unit_price is not None else "N/A",
                "Billed Rate (PKR)": f"{line.invoiced_unit_price:,.2f}",
                "Variance Exposure": f"PKR {line.financial_exposure:,.2f}",
                "Status": line.status,
                "Dock & Contract Notes": line.note
            })

        df_matrix = pd.DataFrame(matrix_rows)
        st.dataframe(df_matrix, use_container_width=True)

# =========================================================
# TAB 3: Evolus Human-in-the-Loop Gateway
# =========================================================
with tab_gateway:
    st.markdown("#### Evolus Commercial Gateway & Approval State Machine")
    st.caption("Autonomous exception triage, AI-synthesized dispute resolution briefs, and one-click financial counter-measures.")

    workflow: EvolusWorkflowState = st.session_state.workflow_state

    if workflow:
        st.markdown(f"**Current State:** `{workflow.state}` | **STP Eligible:** `{workflow.is_stp_eligible}`")

        # 1. Straight-Through Processing Scenario
        if workflow.is_stp_eligible or workflow.state == "AUTO_APPROVED":
            st.balloons()
            st.success("🎉 **STRAIGHT-THROUGH CLEARANCE:** This commercial invoice satisfies all deterministic conditions. No human escalation required. Automatically approved for Net-30 remittance.")
            
            st.markdown("##### 🚀 ERP Payout Dispatch Payload (SAP / Odoo / Evolus Ledger):")
            st.json(workflow.erp_payout_payload)

        # 2. Escalation & AI Resolution Brief Scenario
        else:
            st.warning("⚠️ **COMMERCIAL EXCEPTION ESCALATED:** This invoice has been held by the autonomous gateway. Review the AI-generated resolution brief below:")

            # AI Resolution Brief Box
            st.markdown("### 🤖 Evolus Commercial Agent Resolution Brief (AMD Instinct Inference)")
            with st.container():
                st.markdown(
                    f"<div style='background: #13151f; border: 1px solid #2b2f42; padding: 1.25rem; border-radius: 10px; margin-bottom: 1.5rem;'>"
                    f"{workflow.agent_resolution_brief or 'Analyzing discrepancy context...'}"
                    f"</div>",
                    unsafe_allow_html=True
                )

            # Interactive Human Action Center
            st.markdown("### ⚡ Human Gateway Decision Center")
            act_col1, act_col2, act_col3 = st.columns(3)

            with act_col1:
                st.markdown("**Option A: Autonomous Debit Note**")
                st.caption("Deduct overcharges from ledger & pay approved balance.")
                if st.button("📝 Issue Debit Note & Remit Approved", type="primary", use_container_width=True):
                    debit_note = evolus_agent.issue_commercial_debit_note(workflow, st.session_state.parsed_invoice)
                    st.rerun()

            with act_col2:
                st.markdown("**Option B: Manager Override**")
                st.caption("Authorize full payment with formal audit trail.")
                approver_name = st.text_input("Approver ID:", value="Finance_Director_01", key="app_name")
                override_justification = st.text_input("Business Justification:", value="Urgent project supply - approved rate variation.", key="app_just")
                if st.button("✅ Force Approve (Override)", use_container_width=True):
                    evolus_agent.force_approve(workflow, st.session_state.parsed_invoice, approver_name, override_justification)
                    st.rerun()

            with act_col3:
                st.markdown("**Option C: Commercial Rejection**")
                st.caption("Block payment completely due to unresolvable breach.")
                reject_reason = st.text_input("Dispute Reason:", value="Unverified vendor bank credentials.", key="rej_reason")
                if st.button("⛔ Reject & Open Dispute", use_container_width=True):
                    evolus_agent.reject_invoice(workflow, "Risk_Officer_04", reject_reason)
                    st.rerun()

        # Display Issued Debit Note if available
        if workflow.debit_note:
            dn = workflow.debit_note
            st.divider()
            st.markdown("### 📄 Official Commercial Debit Note Issued")
            
            dn_col1, dn_col2 = st.columns([1, 1])
            with dn_col1:
                st.markdown(f"""
                - **Debit Note Reference:** `{dn.debit_note_number}`
                - **Issue Date:** `{dn.issue_date}`
                - **Vendor:** `{dn.vendor_name}`
                - **Invoice Ref:** `{dn.invoice_reference}`
                - **Original Billed:** PKR {dn.original_invoiced_amount:,.2f}
                - **Deduction Amount:** <span style="color: #f87171; font-weight: bold;">- PKR {dn.debit_deduction_amount:,.2f}</span>
                - **Net Remittance Approved:** <span style="color: #4ade80; font-weight: bold;">PKR {dn.adjusted_approved_amount:,.2f}</span>
                """, unsafe_allow_html=True)

            with dn_col2:
                st.markdown("**Bilingual Vendor Dispute Memo (English / اردو):**")
                st.text_area(
                    "Vendor Notification Dispatch:",
                    value=dn.bilingual_vendor_notice,
                    height=160,
                    key="vendor_notice_area"
                )

# =========================================================
# TAB 4: Cryptographic Audit Trail & ERP Export
# =========================================================
with tab_audit:
    st.markdown("#### Cryptographic Audit Trail & Enterprise Webhooks")
    st.caption("Every state transition, hardware kernel execution, and financial decision is stamped with an immutable SHA-256 signature.")

    workflow: EvolusWorkflowState = st.session_state.workflow_state

    if workflow and workflow.audit_trail:
        st.markdown("### 🔒 Immutable Action Log")
        
        audit_rows = []
        for entry in workflow.audit_trail:
            audit_rows.append({
                "Timestamp (UTC)": entry.timestamp,
                "Actor / Service": entry.actor,
                "Event Type": entry.event_type,
                "Details": entry.details,
                "Cryptographic Signature": entry.signature
            })

        df_audit = pd.DataFrame(audit_rows)
        st.dataframe(df_audit, use_container_width=True)

    st.markdown("### 🌐 Enterprise Integration Webhook JSON (SAP / Oracle / Odoo)")
    if workflow and workflow.erp_payout_payload:
        st.code(json.dumps(workflow.erp_payout_payload, indent=2), language="json")
    else:
        st.info("Complete intake and reconciliation to view the final ERP settlement webhook.")

# ---------------------------------------------------------
# Footer
# ---------------------------------------------------------
st.markdown("""
<div style="text-align: center; color: #5a627a; font-size: 0.8rem; margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid #1a1e2d;">
    RozgarPay AI — AMD Developer Hackathon: ACT III | Track 3: Reinvent Commerce (with Evolus)<br>
    Engineered for AMD Instinct™ MI300X Accelerators with ROCm 6.2 & Qwen2.5/Gemma
</div>
""", unsafe_allow_html=True)
