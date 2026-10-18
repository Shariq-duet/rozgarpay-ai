"""
Bilingual Extraction Module (English & Urdu)
Extracts structured invoice and commercial PO data using AMD Instinct-accelerated LLMs.
Handles messy scans, noisy text, Nastaliq/Urdu terminology, and standardizes commercial schemas.
"""

import re
import json
import logging
from typing import List, Optional, Union
from pydantic import BaseModel, Field
from core.amd_client import AMDClient

logger = logging.getLogger("RozgarPay.Extractor")

class InvoiceLineItem(BaseModel):
    item_code: Optional[str] = Field(default="ITEM-GEN", description="SKU or item identifier")
    description: str = Field(..., description="Item description in English or Urdu")
    quantity: float = Field(..., description="Quantity invoiced")
    unit: str = Field(default="units", description="Unit of measure (e.g., pcs, bags, kg)")
    unit_price: float = Field(..., description="Unit price contracted/invoiced")
    line_total: float = Field(..., description="Line total before tax")

class ParsedInvoice(BaseModel):
    invoice_number: str = Field(..., description="Vendor commercial invoice identifier")
    po_reference: Optional[str] = Field(None, description="Linked Purchase Order number")
    invoice_date: str = Field(..., description="Invoice issue date (YYYY-MM-DD or standard format)")
    vendor_name: str = Field(..., description="Vendor trading name")
    vendor_ntn: Optional[str] = Field(None, description="National Tax Number / Tax ID")
    vendor_iban: Optional[str] = Field(None, description="Bank IBAN for commercial payout")
    currency: str = Field(default="PKR", description="Currency (PKR, USD, etc.)")
    line_items: List[InvoiceLineItem] = Field(default_factory=list, description="Extracted line items")
    subtotal: float = Field(..., description="Subtotal before taxes")
    tax_rate_percent: float = Field(default=18.0, description="Applicable GST / Sales Tax rate")
    tax_amount: float = Field(default=0.0, description="Tax charged on invoice")
    grand_total: float = Field(..., description="Total payable amount")
    language_detected: str = Field(default="English", description="Linguistic origin (English, Urdu, Mixed)")
    raw_text: Optional[str] = Field(None, description="Raw input text or OCR payload")

class BilingualInvoiceExtractor:
    """
    Orchestrates bilingual document parsing leveraging Qwen2.5/Gemma via AMDClient.
    """

    def __init__(self, amd_client: Optional[AMDClient] = None):
        self.amd_client = amd_client or AMDClient()

    def extract_from_text(self, document_text: str) -> ParsedInvoice:
        """
        Parses commercial invoice text (English, Urdu, or mixed bilingual) into structured JSON.
        """
        prompt = f"""
You are RozgarPay AI's High-Precision Commercial Extraction Engine running on AMD Instinct Accelerators.
Parse the following commercial invoice or receipt text into a strict JSON object.

Key Linguistic Guidance:
- Handles Urdu commercial terms: 'انوائس نمبر' (Invoice No), 'خریداری آرڈر' (PO Ref), 'سیلز ٹیکس' (Sales Tax/GST), 'تعداد' (Quantity), 'قیمت فی اکائی' (Unit Price), 'میزان' (Subtotal), 'کل رقم' (Grand Total).
- Normalize Pakistani Rupee amounts (PKR / Rs / روپئے).
- Map all line items accurately with numeric quantities and unit prices.

Document Content:
\"\"\"
{document_text}
\"\"\"

Respond ONLY with a valid JSON object matching this schema:
{{
  "invoice_number": "string",
  "po_reference": "string or null",
  "invoice_date": "YYYY-MM-DD",
  "vendor_name": "string",
  "vendor_ntn": "string or null",
  "vendor_iban": "string or null",
  "currency": "PKR",
  "line_items": [
    {{
      "item_code": "string",
      "description": "string",
      "quantity": float,
      "unit": "string",
      "unit_price": float,
      "line_total": float
    }}
  ],
  "subtotal": float,
  "tax_rate_percent": float,
  "tax_amount": float,
  "grand_total": float,
  "language_detected": "string"
}}
TAG: EXTRACT_INVOICE_JSON
"""
        messages = [
            {"role": "system", "content": "You are a bilingual commercial document extraction engine on AMD Instinct MI300X. Return only raw JSON."},
            {"role": "user", "content": prompt}
        ]

        response = self.amd_client.chat_completion(messages, temperature=0.0, response_format="json")
        content = response.get("content", "").strip()

        # Clean JSON from markdown fences if returned
        clean_json_str = self._clean_json_fence(content)

        try:
            parsed_dict = json.loads(clean_json_str)
            parsed_dict["raw_text"] = document_text
            return ParsedInvoice(**parsed_dict)
        except Exception as e:
            logger.error(f"Failed to parse model output into ParsedInvoice: {e}. Raw content: {content[:200]}")
            # Fallback to deterministic extraction
            fallback_dict = self.amd_client._mock_invoice_extraction(document_text)
            fallback_dict["raw_text"] = document_text
            return ParsedInvoice(**fallback_dict)

    def _clean_json_fence(self, text: str) -> str:
        """Strips markdown ```json and ``` code fences if present."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
