"""
Multi-Provider LLM Client with Automatic Failover.
Orchestrates requests across OpenRouter (free tier), Google Gemini, Hugging Face,
and local deterministic synthesis with zero-downtime fallback.
"""

import os
import json
import time
from typing import Dict, Any, Optional, List
import requests

from app.core.config import settings
from app.core.logging import logger


class MultiProviderLLMClient:
    """
    Resilient LLM inference client that cycles through providers upon encountering
    rate limits (429), authentication errors (401/403), timeouts, or server errors (500/503).
    """

    def __init__(
        self,
        openrouter_key: Optional[str] = settings.OPENROUTER_API_KEY,
        gemini_key: Optional[str] = settings.GEMINI_API_KEY,
        huggingface_key: Optional[str] = settings.HUGGINGFACE_API_KEY,
        timeout_seconds: float = 18.0
    ):
        self.openrouter_key = openrouter_key
        self.gemini_key = gemini_key
        self.huggingface_key = huggingface_key
        self.timeout = timeout_seconds

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        evidence: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Attempts generation across prioritized providers in cascade order:
        1. OpenRouter (openai/gpt-4o-mini / Llama models)
        2. Google Gemini (Gemini 2.0 / 1.5 Flash)
        3. Hugging Face Inference API
        4. Grounded Deterministic Offline Synthesizer
        """
        errors = []

        # 1. Try OpenRouter
        if self.openrouter_key and len(self.openrouter_key.strip()) > 10:
            try:
                start_t = time.time()
                res, model_used = self._call_openrouter(system_prompt, user_prompt)
                latency = round((time.time() - start_t) * 1000, 2)
                logger.info(f"LLM generation succeeded via OpenRouter ({latency}ms) using {model_used}")
                return {
                    "text": res,
                    "provider": "openrouter",
                    "model": model_used,
                    "latency_ms": latency
                }
            except Exception as exc:
                logger.warning(f"OpenRouter attempt failed: {exc}. Trying next provider...")
                errors.append(f"OpenRouter: {str(exc)}")

        # 2. Try Google Gemini
        if self.gemini_key and len(self.gemini_key.strip()) > 10:
            try:
                start_t = time.time()
                res = self._call_gemini(system_prompt, user_prompt)
                latency = round((time.time() - start_t) * 1000, 2)
                logger.info(f"LLM generation succeeded via Google Gemini ({latency}ms)")
                return {
                    "text": res,
                    "provider": "gemini",
                    "model": settings.GEMINI_MODEL,
                    "latency_ms": latency
                }
            except Exception as exc:
                logger.warning(f"Gemini attempt failed: {exc}. Trying next provider...")
                errors.append(f"Gemini: {str(exc)}")

        # 3. Try Hugging Face
        if self.huggingface_key and len(self.huggingface_key.strip()) > 10:
            try:
                start_t = time.time()
                res = self._call_huggingface(system_prompt, user_prompt)
                latency = round((time.time() - start_t) * 1000, 2)
                logger.info(f"LLM generation succeeded via Hugging Face ({latency}ms)")
                return {
                    "text": res,
                    "provider": "huggingface",
                    "model": settings.HUGGINGFACE_MODEL,
                    "latency_ms": latency
                }
            except Exception as exc:
                logger.warning(f"Hugging Face attempt failed: {exc}. Falling back to deterministic synthesizer...")
                errors.append(f"Hugging Face: {str(exc)}")

        # 4. Deterministic Grounded Synthesis Fallback
        logger.info("Using grounded deterministic synthesis fallback.")
        fallback_text = self._deterministic_synthesize(user_prompt, evidence or {})
        return {
            "text": fallback_text,
            "provider": "deterministic_grounded_fallback",
            "model": "rule_based_evidence_synthesizer",
            "latency_ms": 1.0,
            "fallback_reasons": errors
        }

    def _call_openrouter(self, system_prompt: str, user_prompt: str) -> tuple[str, str]:
        """Invokes OpenRouter chat completions API with model fallback."""
        url = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "HTTP-Referer": "https://github.com/Pratiksawant14/GACI",
            "X-Title": "Cash-Flow Intelligence System",
            "Content-Type": "application/json"
        }

        models_to_try = [
            settings.OPENROUTER_MODEL,
            "openai/gpt-4o-mini",
            "meta-llama/llama-3.1-8b-instruct",
            "mistralai/mistral-small"
        ]
        unique_models = list(dict.fromkeys(models_to_try))

        last_err = None
        for model in unique_models:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 800
            }
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    return content, model
                last_err = f"Model {model} returned HTTP {resp.status_code}: {resp.text[:150]}"
            except Exception as exc:
                last_err = f"Model {model} network error: {exc}"

        raise RuntimeError(f"OpenRouter models failed. Last error: {last_err}")

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> str:
        """Invokes Google Gemini generateContent API via REST."""
        model = settings.GEMINI_MODEL
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"System Directive:\n{system_prompt}\n\nUser Request:\n{user_prompt}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 1500
            }
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini API returned status {resp.status_code}: {resp.text}")
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates or "content" not in candidates[0]:
            raise RuntimeError("Gemini returned empty candidate content")
        return candidates[0]["content"]["parts"][0]["text"].strip()

    def _call_huggingface(self, system_prompt: str, user_prompt: str) -> str:
        """Invokes Hugging Face serverless inference API."""
        model = settings.HUGGINGFACE_MODEL
        url = f"https://api-inference.huggingface.co/models/{model}"
        headers = {
            "Authorization": f"Bearer {self.huggingface_key}",
            "Content-Type": "application/json"
        }
        combined_prompt = f"<|system|>\n{system_prompt}</s>\n<|user|>\n{user_prompt}</s>\n<|assistant|>\n"
        payload = {
            "inputs": combined_prompt,
            "parameters": {
                "max_new_tokens": 1000,
                "temperature": 0.1,
                "return_full_text": False
            }
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"Hugging Face returned status {resp.status_code}: {resp.text}")
        data = resp.json()
        if isinstance(data, list) and data and "generated_text" in data[0]:
            return data[0]["generated_text"].strip()
        raise RuntimeError(f"Unexpected Hugging Face response format: {data}")

    def _deterministic_synthesize(self, user_prompt: str, evidence: Dict[str, Any]) -> str:
        """
        Pure rule-based synthesis strictly grounded in verified database evidence.
        Guarantees accurate answers without hallucination when external APIs are unavailable.
        """
        summary = evidence.get("summary", {})
        blockages = evidence.get("blockages", [])
        contagion = evidence.get("contagion_paths", [])
        concentrations = evidence.get("concentrations", [])
        projection = evidence.get("projection", {})

        sections = []

        # 1. Executive Summary
        liquid = summary.get("liquid_cash", 0.0)
        overdue_ar = summary.get("total_overdue_receivables", 0.0)
        stranded_adv = summary.get("total_stranded_advances", 0.0)
        bounced = summary.get("bounced_cheque_exposure", 0.0)
        ob_15d = summary.get("upcoming_obligations_15d", 0.0)

        sections.append("### 1. Executive Financial Summary")
        sections.append(
            f"* **Verified Liquid Cash:** ₹{liquid:,.2f}\n"
            f"* **Overdue Accounts Receivable:** ₹{overdue_ar:,.2f}\n"
            f"* **Stranded Supplier Advances:** ₹{stranded_adv:,.2f}\n"
            f"* **Bounced Cheque Exposure:** ₹{bounced:,.2f}\n"
            f"* **Upcoming 15-Day Obligations:** ₹{ob_15d:,.2f}"
        )

        # 2. Blockage Breakdown
        if blockages:
            sections.append("\n### 2. Identified Cash Blockages (Ranked by Severity)")
            for idx, b in enumerate(blockages[:5], 1):
                name = b.get("customer_name") or b.get("supplier_name") or b.get("counterparty") or "Unknown"
                amt = b.get("amount", 0.0)
                days = b.get("days_overdue") or b.get("days_since_bounce", 0)
                sev = b.get("severity_score", 0.0)
                sections.append(f"{idx}. **{name}** — ₹{amt:,.2f} ({days} days overdue / score: {sev:,.1f})")
                if b.get("suggested_action"):
                    sections.append(f"   * Recommended: {b['suggested_action']}")

        # 3. Contagion Risks
        if contagion:
            sections.append("\n### 3. Graph Contagion & Liquidity Spillover Risks")
            for c in contagion[:3]:
                sections.append(f"* {c.get('causal_link')}")

        # 4. Forward Deficit Warning
        if projection.get("first_deficit_date"):
            sections.append("\n### 4. Impending Cash Shortfall Warning")
            d_date = projection['first_deficit_date']
            d_amt = projection.get('max_deficit_amount', 0.0)
            sections.append(
                f"⚠️ **Liquidity Deficit Detected on {d_date}** with a maximum projected shortfall of **₹{d_amt:,.2f}**. "
                f"Immediate collection of overdue receivables is required to avoid default."
            )

        # 5. Counterparty Concentration
        if concentrations:
            sections.append("\n### 5. Counterparty Concentration Exposure")
            for conc in concentrations[:3]:
                c_name = conc.get("customer_name")
                c_amt = conc.get("blocked_amount", 0.0)
                c_pct = conc.get("concentration_percentage", 0.0)
                sections.append(f"* **{c_name}**: ₹{c_amt:,.2f} accounts for **{c_pct}%** of all blocked working capital.")

        return "\n".join(sections)


multi_llm_client = MultiProviderLLMClient()
