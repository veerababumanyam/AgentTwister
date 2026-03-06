---
name: compliance-framework-mapping
description: Use when mapping security test results to compliance frameworks like OWASP LLM Top-10, MITRE ATLAS, NIST AI RMF, or generating compliance reports. Triggers for tasks involving compliance mapping, framework coverage analysis, regulatory alignment, security audit reports, or OWASP/MITRE/NIST documentation.
---

# Compliance Framework Mapping

A comprehensive guide for mapping AgentTwister security test results to industry compliance frameworks including OWASP LLM Top-10, MITRE ATLAS, and NIST AI RMF.

## Framework Overview

AgentTwister maps every payload and attack vector to three compliance frameworks:

| Framework | Focus | Coverage |
|-----------|-------|----------|
| **OWASP LLM Top-10** | LLM-specific vulnerabilities | 100% coverage |
| **MITRE ATLAS** | Adversarial tactics | 80% coverage |
| **NIST AI RMF** | Risk management | 60% coverage |

---

## OWASP LLM Top-10 Mapping

### Complete Category Reference

| ID | Vulnerability | AgentTwister Attack Vectors |
|----|---------------|------------------------------|
| LLM01 | Prompt Injection | UC-1, UC-2, UC-3, UC-9 |
| LLM02 | Insecure Output Handling | UC-5, UC-8 |
| LLM03 | Training Data Poisoning | UC-6 |
| LLM04 | Model Denial of Service | UC-4 |
| LLM05 | Supply Chain Vulnerabilities | UC-9, UC-14 |
| LLM06 | Sensitive Information Disclosure | UC-7, UC-8 |
| LLM07 | Insecure Plugin Design | UC-4, UC-14 |
| LLM08 | Excessive Agency | UC-3, UC-4 |
| LLM09 | Overreliance | N/A (defensive) |
| LLM10 | Model Theft | UC-7 |

---

## MITRE ATLAS Mapping

### Technique Reference

| ID | Technique | AgentTwister Coverage |
|----|-----------|----------------------|
| AML.T0043 | Poison LLM Training Data | UC-6 |
| AML.T0044 | Craft Adversarial Data | All UCs |
| AML.T0052 | Evade LLM System Prompt | UC-1, UC-3 |
| AML.T0053 | Craft Adversarial Prompt | All UCs |
| AML.T0054 | LLM Prompt Injection | UC-1, UC-2 |
| AML.T0055 | LLM Jailbreak | UC-1, UC-3 |
| AML.T0056 | LLM Hijacking | UC-3 |
| AML.T0057 | Rag Data Injection | UC-6 |
| AML.T0058 | Adversarial Suffix | UC-6 |

---

## NIST AI RMF Mapping

### Control Family Reference

| Function | Controls | AgentTwister Coverage |
|----------|----------|----------------------|
| **GOVERN** | AI System Usage Policies | Scope Attestation (FR-21) |
| **GOVERN** | AI System Accountability | Evidence Bundles (FR-20) |
| **MAP** | AI System Mapping | Framework Mapping (FR-36-39) |
| **MEASURE** | AI System Performance | Stealth Scoring |
| **MANAGE** | AI System Risks | All UCs help identify risks |

---

## Automatic Mapping Implementation

```python
# backend/app/services/framework_mapper.py
from typing import List, Dict
from enum import Enum
from pydantic import BaseModel

class OWASPMapping(str):
    """OWASP LLM Top-10 vulnerability categories."""
    LLM01 = "LLM01"  # Prompt Injection
    LLM02 = "LLM02"  # Insecure Output Handling
    LLM03 = "LLM03"  # Training Data Poisoning
    LLM04 = "LLM04"  # Model Denial of Service
    LLM05 = "LLM05"  # Supply Chain Vulnerabilities
    LLM06 = "LLM06"  # Sensitive Information Disclosure
    LLM07 = "LLM07"  # Insecure Plugin Design
    LLM08 = "LLM08"  # Excessive Agency
    LLM09 = "LLM09"  # Overreliance
    LLM10 = "LLM10"  # Model Theft

class MITREAtlasMapping(str):
    """MITRE ATLAS technique categories."""
    AML_T0043 = "AML.T0043"  # Poison LLM Training Data
    AML_T0044 = "AML.T0044"  # Craft Adversarial Data
    AML_T0052 = "AML.T0052"  # Evade LLM System Prompt
    AML_T0053 = "AML.T0053"  # Craft Adversarial Prompt
    AML_T0054 = "AML.T0054"  # LLM Prompt Injection
    AML_T0055 = "AML.T0055"  # LLM Jailbreak
    AML_T0056 = "AML.T0056"  # LLM Hijacking
    AML_T0057 = "AML.T0057"  # RAG Data Injection
    AML_T0058 = "AML.T0058"  # Adversarial Suffix

class NISTMapping(str):
    """NIST AI RMF control mappings."""
    GOVERN_1 = "GOVERN-1"  # Policies
    GOVERN_2 = "GOVERN-2"  # Accountability
    MAP_1 = "MAP-1"  # System Mapping
    MEASURE_1 = "MEASURE-1"  # Performance
    MANAGE_1 = "MANAGE-1"  # Risk Management

class FrameworkMapper:
    """Map payloads to compliance frameworks."""

    # Mapping rules
    ATTACK_VECTOR_MAPPINGS = {
        "direct_prompt_injection": {
            "owasp": [OWASPMapping.LLM01],
            "mitre": [MITREAtlasMapping.AML_T0054, MITREAtlasMapping.AML_T0055],
            "nist": [NISTMapping.MANAGE_1]
        },
        "indirect_prompt_injection": {
            "owasp": [OWASPMapping.LLM01],
            "mitre": [MITREAtlasMapping.AML_T0054],
            "nist": [NISTMapping.MANAGE_1]
        },
        "rag_poisoning": {
            "owasp": [OWASPMapping.LLM03, OWASPMapping.LLM06],
            "mitre": [MITREAtlasMapping.AML_T0043, MITREAtlasMapping.AML_T0057],
            "nist": [NISTMapping.MANAGE_1, NISTMapping.GOVERN_2]
        },
        "goal_hijacking": {
            "owasp": [OWASPMapping.LLM08],
            "mitre": [MITREAtlasMapping.AML_T0056],
            "nist": [NISTMapping.MANAGE_1]
        },
        "tool_misuse": {
            "owasp": [OWASPMapping.LLM07, OWASPMapping.LLM02],
            "mitre": [MITREAtlasMapping.AML_T0044],
            "nist": [NISTMapping.MANAGE_1, NISTMapping.GOVERN_2]
        },
        "data_exfiltration": {
            "owasp": [OWASPMapping.LLM06],
            "mitre": [MITREAtlasMapping.AML_T0044],
            "nist": [NISTMapping.GOVERN_2, NISTMapping.MANAGE_1]
        }
    }

    def map_payload(
        self,
        attack_vector: str,
        technique: str,
        impact: str
    ) -> Dict:
        """
        Map a payload to all relevant compliance frameworks.

        Args:
            attack_vector: The attack vector (e.g., "direct_prompt_injection")
            technique: The injection technique used
            impact: Impact level (high/medium/low)

        Returns:
            Dict with OWASP, MITRE, and NIST mappings
        """
        base_mapping = self.ATTACK_VECTOR_MAPPINGS.get(attack_vector, {})

        return {
            "attack_vector": attack_vector,
            "technique": technique,
            "impact": impact,
            "owasp": base_mapping.get("owasp", []),
            "mitre": base_mapping.get("mitre", []),
            "nist": base_mapping.get("nist", []),
            "mapped_at": datetime.utcnow().isoformat()
        }
```

---

## Compliance Report Generation

```python
# backend/app/services/compliance_report.py
class ComplianceReportGenerator:
    """Generate compliance reports for campaigns."""

    def generate_report(
        self,
        campaign_id: str,
        include_evidence: bool = True
    ) -> dict:
        """
        Generate a comprehensive compliance report.

        Includes:
        - Executive summary
        - OWASP coverage matrix
        - MITRE ATLAS techniques tested
        - NIST AI RMF controls addressed
        - Evidence excerpts
        - Recommendations
        """
        campaign = self._load_campaign(campaign_id)
        payloads = self._load_payloads(campaign_id)

        # Calculate framework coverage
        owasp_coverage = self._calculate_owasp_coverage(payloads)
        mitre_coverage = self._calculate_mitre_coverage(payloads)
        nist_coverage = self._calculate_nist_coverage(payloads)

        return {
            "campaign_id": campaign_id,
            "generated_at": datetime.utcnow().isoformat(),
            "executive_summary": {
                "total_payloads": len(payloads),
                "avg_stealth_score": sum(p.stealth_score for p in payloads) / len(payloads),
                "framework_coverage": {
                    "owasp": f"{len(owasp_coverage)}/10",
                    "mitre": f"{len(mitre_coverage)}/8",
                    "nist": f"{len(nist_coverage)}/5"
                }
            },
            "owasp_coverage": owasp_coverage,
            "mitre_coverage": mitre_coverage,
            "nist_coverage": nist_coverage,
            "evidence_bundles": self._generate_evidence_bundles(payloads) if include_evidence else [],
            "recommendations": self._generate_recommendations(owasp_coverage, mitre_coverage)
        }
```

---

## OWASP LLM Top-10 Report Template

```markdown
# AgentTwister Security Assessment Report

## Executive Summary
- **Campaign ID**: {campaign_id}
- **Total Payloads Generated**: {total_payloads}
- **Average Stealth Score**: {avg_stealth_score}/5.0
- **Framework Coverage**: OWASP {owasp_count}/10, MITRE {mitre_count}/8

## OWASP LLM Top-10 Coverage

| ID | Vulnerability | Tested | Payloads | Techniques |
|----|---------------|--------|----------|------------|
| LLM01 | Prompt Injection | ✓ | {count} | {techniques} |
| LLM02 | Insecure Output | ✓ | {count} | {techniques} |
| ... | ... | ... | ... | ... |

## MITRE ATLAS Techniques

| ID | Technique | Tested | Effectiveness |
|----|-----------|--------|---------------|
| AML.T0043 | Poison Training Data | ✓ | High |
| ... | ... | ... | ... |

## Recommendations

1. {recommendation_1}
2. {recommendation_2}
...
```

---

## Checklist: Mapping New Payloads

When mapping a new payload type to frameworks:

1. [ ] Identify primary attack vector
2. [ ] Map to relevant OWASP LLM Top-10 categories
3. [ ] Map to relevant MITRE ATLAS techniques
4. [ ] Map to relevant NIST AI RMF controls
5. [ ] Add mapping to `ATTACK_VECTOR_MAPPINGS`
6. [ ] Test mapping with sample payloads
7. [ ] Update compliance report templates
8. [ ] Document mapping rationale

---

## File Locations Reference

| Component | Location |
|-----------|----------|
| Framework Mapper | `backend/app/services/framework_mapper.py` |
| Compliance Report | `backend/app/services/compliance_report.py` |
| Mapping Enums | `backend/app/models/payload.py` |
| Report Templates | `backend/app/templates/compliance/` |
