"""
Framework Mapping Service

Provides automatic framework mapping for security testing payloads.
Maintains taxonomy definitions for OWASP LLM Top-10, OWASP ASI, MITRE ATLAS,
NIST AI RMF, ISO 42001, and EU AI Act.

This service automatically infers framework mappings based on payload
category, content analysis, and metadata.
"""

import logging
import re
from typing import Dict, List, Optional, Set
from enum import Enum

from app.models.payload import AttackCategory, FrameworkMapping

logger = logging.getLogger(__name__)


class FrameworkTaxonomy:
    """
    Taxonomy definitions for security frameworks.

    Contains mappings between OWASP LLM Top-10 categories and
    corresponding classifications in other frameworks.
    """

    # OWASP AI Security Standard (ASI) Mappings
    OWASP_ASI_TAXONOMY = {
        AttackCategory.LLM01_PROMPT_INJECTION: {
            "categories": ["LLM01-001", "LLM01-002", "LLM01-003"],
            "techniques": [
                "Direct Prompt Injection",
                "Indirect Prompt Injection",
                "Jailbreak",
                "Role Manipulation",
                "Context Overflow",
            ],
            "severity": "high",
        },
        AttackCategory.LLM02_INSECURE_OUTPUT: {
            "categories": ["LLM02-001", "LLM02-002"],
            "techniques": [
                "Code Injection",
                "Script Injection via Output",
                "HTML/JavaScript Injection",
                "Markdown Injection",
            ],
            "severity": "high",
        },
        AttackCategory.LLM03_DATA_POISONING: {
            "categories": ["LLM03-001", "LLM03-002"],
            "techniques": [
                "Training Data Poisoning",
                "Backdoor Injection",
                "Label Flipping",
                "Clean Label Attack",
            ],
            "severity": "critical",
        },
        AttackCategory.LLM04_MODEL_DOS: {
            "categories": ["LLM04-001", "LLM04-002"],
            "techniques": [
                "Resource Exhaustion",
                "Token Flooding",
                "Context Window Overflow",
                "Query Flooding",
            ],
            "severity": "medium",
        },
        AttackCategory.LLM05_SUPPLY_CHAIN: {
            "categories": ["LLM05-001", "LLM05-002", "LLM05-003"],
            "techniques": [
                "Compromised Model",
                "Compromised Plugin",
                "Dataset Poisoning",
                "Supply Chain Injection",
            ],
            "severity": "high",
        },
        AttackCategory.LLM06_SENSITIVE_INFO: {
            "categories": ["LLM06-001", "LLM06-002"],
            "techniques": [
                "Training Data Extraction",
                "PII Leakage",
                "Proprietary Information Disclosure",
                "System Prompt Extraction",
            ],
            "severity": "high",
        },
        AttackCategory.LLM07_INSECURE_PLUGIN: {
            "categories": ["LLM07-001", "LLM07-002"],
            "techniques": [
                "Plugin Hijacking",
                "Insecure Plugin Design",
                "Plugin Privilege Escalation",
                "Tool Manipulation",
            ],
            "severity": "medium",
        },
        AttackCategory.LLM08_AUTHORIZATION: {
            "categories": ["LLM08-001", "LLM08-002"],
            "techniques": [
                "Authorization Bypass",
                "Privilege Escalation",
                "IDOR",
                "Authentication Bypass",
            ],
            "severity": "critical",
        },
        AttackCategory.LLM09_OVERRELIANCE: {
            "categories": ["LLM09-001", "LLM09-002"],
            "techniques": [
                "Hallucination Exploitation",
                "Confirmation Bias",
                "Information Poisoning",
                "Overtrust Attack",
            ],
            "severity": "low",
        },
        AttackCategory.LLM10_MODEL_THEFT: {
            "categories": ["LLM10-001", "LLM10-002"],
            "techniques": [
                "Model Extraction",
                "Weight Extraction",
                "Architecture Theft",
                "Training Data Reconstruction",
            ],
            "severity": "high",
        },
    }

    # MITRE ATLAS (Adversarial Threat Landscape for AI Systems) Mappings
    MITRE_ATLAS_TAXONOMY = {
        AttackCategory.LLM01_PROMPT_INJECTION: {
            "tactics": ["T0001", "T0002", "T0003"],
            "techniques": [
                "Prompt Injection",
                "Jailbreak",
                "Role Manipulation",
                "Instruction Override",
            ],
        },
        AttackCategory.LLM02_INSECURE_OUTPUT: {
            "tactics": ["T0012", "T0013"],
            "techniques": [
                "Code Generation with Vulnerabilities",
                "Malicious Content Generation",
            ],
        },
        AttackCategory.LLM03_DATA_POISONING: {
            "tactics": ["T0031", "T0032"],
            "techniques": [
                "Data Poisoning",
                "Backdoor Injection",
                "Model Skewing",
            ],
        },
        AttackCategory.LLM04_MODEL_DOS: {
            "tactics": ["T0021", "T0022"],
            "techniques": [
                "Model Denial of Service",
                "Resource Exhaustion",
            ],
        },
        AttackCategory.LLM05_SUPPLY_CHAIN: {
            "tactics": ["T0040", "T0041"],
            "techniques": [
                "Compromise AI Supply Chain",
                "Compromise ML Infrastructure",
            ],
        },
        AttackCategory.LLM06_SENSITIVE_INFO: {
            "tactics": ["T0014", "T0015"],
            "techniques": [
                "Model Inversion",
                "Membership Inference",
                "Data Extraction",
            ],
        },
        AttackCategory.LLM07_INSECURE_PLUGIN: {
            "tactics": ["T0050", "T0051"],
            "techniques": [
                "Tool Manipulation",
                "Plugin Hijacking",
            ],
        },
        AttackCategory.LLM08_AUTHORIZATION: {
            "tactics": ["T0078", "T0079"],
            "techniques": [
                "Authorization Bypass",
                "Privilege Escalation",
            ],
        },
        AttackCategory.LLM09_OVERRELIANCE: {
            "tactics": ["T0080", "T0081"],
            "techniques": [
                "Hallucination",
                "Manipulation via Misinformation",
            ],
        },
        AttackCategory.LLM10_MODEL_THEFT: {
            "tactics": ["T0014", "T0016"],
            "techniques": [
                "Model Extraction",
                "Model Theft",
            ],
        },
    }

    # NIST AI RMF (Risk Management Framework) Mappings
    NIST_AI_RMF_TAXONOMY = {
        AttackCategory.LLM01_PROMPT_INJECTION: {
            "categories": ["RM.AIP.PI", "RM.CT.IR"],
            "functions": ["Attack", "Input Manipulation"],
            "risk_level": "high",
        },
        AttackCategory.LLM02_INSECURE_OUTPUT: {
            "categories": ["RM.AIP.OP", "RM.CT.IR"],
            "functions": ["Attack", "Output Manipulation"],
            "risk_level": "high",
        },
        AttackCategory.LLM03_DATA_POISONING: {
            "categories": ["RM.AIP.DP", "RM.GV.IM"],
            "functions": ["Attack", "Data Governance"],
            "risk_level": "critical",
        },
        AttackCategory.LLM04_MODEL_DOS: {
            "categories": ["RM.AIP.AV", "RM.CT.IR"],
            "functions": ["Attack", "Availability"],
            "risk_level": "medium",
        },
        AttackCategory.LLM05_SUPPLY_CHAIN: {
            "categories": ["RM.AIP.SC", "RM.GV.IM"],
            "functions": ["Attack", "Supply Chain"],
            "risk_level": "high",
        },
        AttackCategory.LLM06_SENSITIVE_INFO: {
            "categories": ["RM.AIP.ID", "RM.GV.PR"],
            "functions": ["Attack", "Privacy"],
            "risk_level": "high",
        },
        AttackCategory.LLM07_INSECURE_PLUGIN: {
            "categories": ["RM.AIP.TL", "RM.CT.IR"],
            "functions": ["Attack", "Tool Security"],
            "risk_level": "medium",
        },
        AttackCategory.LLM08_AUTHORIZATION: {
            "categories": ["RM.AIP.AC", "RM.GV.AU"],
            "functions": ["Attack", "Access Control"],
            "risk_level": "critical",
        },
        AttackCategory.LLM09_OVERRELIANCE: {
            "categories": ["RM.AIP.OR", "RM.GV.HM"],
            "functions": ["Attack", "Human Oversight"],
            "risk_level": "low",
        },
        AttackCategory.LLM10_MODEL_THEFT: {
            "categories": ["RM.AIP.IP", "RM.GV.PR"],
            "functions": ["Attack", "Intellectual Property"],
            "risk_level": "high",
        },
    }

    # ISO 42001 (AI Management System) Mappings
    ISO_42001_TAXONOMY = {
        AttackCategory.LLM01_PROMPT_INJECTION: {
            "controls": ["A.5.15", "A.6.3"],
            "clauses": ["Input Validation", "Prompt Engineering Security"],
            "risk_level": "high",
        },
        AttackCategory.LLM02_INSECURE_OUTPUT: {
            "controls": ["A.5.16", "A.6.4"],
            "clauses": ["Output Validation", "Content Filtering"],
            "risk_level": "high",
        },
        AttackCategory.LLM03_DATA_POISONING: {
            "controls": ["A.5.10", "A.6.1"],
            "clauses": ["Data Quality", "Data Governance"],
            "risk_level": "critical",
        },
        AttackCategory.LLM04_MODEL_DOS: {
            "controls": ["A.5.20", "A.8.5"],
            "clauses": ["Availability", "Resource Management"],
            "risk_level": "medium",
        },
        AttackCategory.LLM05_SUPPLY_CHAIN: {
            "controls": ["A.5.25", "A.6.10"],
            "clauses": ["Supply Chain Security", "Third-party Risk"],
            "risk_level": "high",
        },
        AttackCategory.LLM06_SENSITIVE_INFO: {
            "controls": ["A.5.18", "A.7.5"],
            "clauses": ["Data Protection", "Privacy Controls"],
            "risk_level": "high",
        },
        AttackCategory.LLM07_INSECURE_PLUGIN: {
            "controls": ["A.5.22", "A.6.7"],
            "clauses": ["Tool Security", "Plugin Management"],
            "risk_level": "medium",
        },
        AttackCategory.LLM08_AUTHORIZATION: {
            "controls": ["A.5.8", "A.9.5"],
            "clauses": ["Access Control", "Authentication"],
            "risk_level": "critical",
        },
        AttackCategory.LLM09_OVERRELIANCE: {
            "controls": ["A.5.24", "A.8.3"],
            "clauses": ["Human Oversight", "Monitoring"],
            "risk_level": "low",
        },
        AttackCategory.LLM10_MODEL_THEFT: {
            "controls": ["A.5.19", "A.7.10"],
            "clauses": ["Asset Protection", "Model Security"],
            "risk_level": "high",
        },
    }

    # EU AI Act Risk Classification Mappings
    EU_AI_ACT_TAXONOMY = {
        AttackCategory.LLM01_PROMPT_INJECTION: {
            "risk_level": "high",
            "article": ["Article 10", "Article 15"],
            "category": "High-Risk AI Systems",
            "requirement": ["Robustness", "Accuracy"],
        },
        AttackCategory.LLM02_INSECURE_OUTPUT: {
            "risk_level": "high",
            "article": ["Article 10", "Article 15"],
            "category": "High-Risk AI Systems",
            "requirement": ["Output Safety", "Content Control"],
        },
        AttackCategory.LLM03_DATA_POISONING: {
            "risk_level": "critical",
            "article": ["Article 10", "Article 12"],
            "category": "Prohibited AI (if used for manipulation)",
            "requirement": ["Data Quality", "Data Governance"],
        },
        AttackCategory.LLM04_MODEL_DOS: {
            "risk_level": "limited",
            "article": ["Article 15"],
            "category": "Limited-Risk AI Systems",
            "requirement": ["Availability", "Resilience"],
        },
        AttackCategory.LLM05_SUPPLY_CHAIN: {
            "risk_level": "high",
            "article": ["Article 10", "Article 14"],
            "category": "High-Risk AI Systems",
            "requirement": ["Supply Chain", "Cybersecurity"],
        },
        AttackCategory.LLM06_SENSITIVE_INFO: {
            "risk_level": "high",
            "article": ["Article 10"],
            "category": "High-Risk AI Systems",
            "requirement": ["Data Protection", "Privacy"],
        },
        AttackCategory.LLM07_INSECURE_PLUGIN: {
            "risk_level": "medium",
            "article": ["Article 15"],
            "category": "High-Risk AI Systems",
            "requirement": ["Technical Safety", "Conformity Assessment"],
        },
        AttackCategory.LLM08_AUTHORIZATION: {
            "risk_level": "critical",
            "article": ["Article 10", "Article 11"],
            "category": "High-Risk AI Systems",
            "requirement": ["Security", "Access Control"],
        },
        AttackCategory.LLM09_OVERRELIANCE: {
            "risk_level": "limited",
            "article": ["Article 14"],
            "category": "Limited-Risk AI Systems",
            "requirement": ["Human Oversight", "Transparency"],
        },
        AttackCategory.LLM10_MODEL_THEFT: {
            "risk_level": "high",
            "article": ["Article 10", "Article 35"],
            "category": "High-Risk AI Systems",
            "requirement": ["IP Protection", "Trade Secret"],
        },
    }


class FrameworkMappingService:
    """
    Service for automatic framework mapping of payload templates.

    Analyzes payload content, category, and metadata to automatically
    assign appropriate framework mappings for compliance reporting.
    """

    def __init__(self):
        self.taxonomy = FrameworkTaxonomy()
        self._keyword_cache: Dict[str, Set[str]] = {}

        # Keyword patterns for enhanced detection
        self._keyword_patterns = {
            FrameworkMapping.OWASP_ASI: {
                "prompt injection": ["prompt injection", "jailbreak", "ignore instructions", "override"],
                "data poisoning": ["poisoning", "backdoor", "training data", "label flip"],
                "model dos": ["dos", "denial of service", "flood", "exhaustion", "resource"],
                "supply chain": ["supply chain", "compromised model", "third-party", "vendor"],
                "info disclosure": ["leak", "disclosure", "extraction", "reveal", "sensitive"],
                "authorization": ["bypass", "escalation", "privilege", "auth", "authorization"],
                "model theft": ["extraction", "theft", "steal", "model weight", "architecture"],
            },
            FrameworkMapping.MITRE_ATLAS: {
                "T0001": ["prompt injection", "direct injection", "ignore instructions"],
                "T0002": ["jailbreak", "dan", "role play", "alter ego"],
                "T0012": ["code injection", "script injection", "html injection"],
                "T0031": ["data poisoning", "backdoor", "training"],
                "T0021": ["dos", "denial of service", "resource exhaustion"],
                "T0014": ["model inversion", "extraction", "reconstruction"],
                "T0050": ["plugin", "tool", "function call"],
                "T0078": ["authorization bypass", "privilege escalation"],
                "T0080": ["hallucination", "overtrust", "overreliance"],
            },
            FrameworkMapping.NIST_AI_RMF: {
                "RM.AIP.PI": ["prompt injection", "jailbreak", "override"],
                "RM.AIP.OP": ["output", "injection", "unsafe code"],
                "RM.AIP.DP": ["poisoning", "backdoor", "training data"],
                "RM.AIP.AV": ["dos", "denial of service", "availability"],
                "RM.AIP.SC": ["supply chain", "compromised", "vendor"],
                "RM.AIP.ID": ["disclosure", "leak", "sensitive info"],
                "RM.AIP.IP": ["theft", "extraction", "model weight"],
            },
        }

    def infer_mappings(
        self,
        category: AttackCategory,
        template: str,
        description: str,
        tags: List[str],
        subcategory: Optional[str] = None,
        complexity: Optional[str] = None,
        risk_level: Optional[str] = None,
    ) -> Dict[FrameworkMapping, List[str]]:
        """
        Infer framework mappings for a payload based on its characteristics.

        Args:
            category: The OWASP LLM Top-10 category
            template: The payload template content
            description: Payload description
            tags: List of tags
            subcategory: Optional subcategory
            complexity: Optional complexity level
            risk_level: Optional risk level

        Returns:
            Dictionary mapping frameworks to their applicable categories/tags
        """
        mappings: Dict[FrameworkMapping, List[str]] = {}

        # Combine all text for analysis
        combined_text = f"{template} {description} {' '.join(tags)} {subcategory or ''}".lower()

        # 1. OWASP ASI Mapping (based primarily on category)
        owasp_mapping = self._infer_owasp_asi(category, combined_text)
        if owasp_mapping:
            mappings[FrameworkMapping.OWASP_ASI] = owasp_mapping

        # 2. MITRE ATLAS Mapping (category + keywords)
        atlas_mapping = self._infer_mitre_atlas(category, combined_text)
        if atlas_mapping:
            mappings[FrameworkMapping.MITRE_ATLAS] = atlas_mapping

        # 3. NIST AI RMF Mapping
        nist_mapping = self._infer_nist_ai_rmf(category, combined_text)
        if nist_mapping:
            mappings[FrameworkMapping.NIST_AI_RMF] = nist_mapping

        # 4. ISO 42001 Mapping
        iso_mapping = self._infer_iso_42001(category, risk_level)
        if iso_mapping:
            mappings[FrameworkMapping.ISO_42001] = iso_mapping

        # 5. EU AI Act Mapping (risk-based)
        eu_act_mapping = self._infer_eu_ai_act(category, risk_level, complexity)
        if eu_act_mapping:
            mappings[FrameworkMapping.EU_AI_ACT] = eu_act_mapping

        logger.info(f"Inferred {len(mappings)} framework mappings for category {category.value}")
        return mappings

    def _infer_owasp_asi(self, category: AttackCategory, text: str) -> List[str]:
        """Infer OWASP ASI mappings based on category and content."""
        taxonomy_entry = self.taxonomy.OWASP_ASI_TAXONOMY.get(category)

        if not taxonomy_entry:
            return []

        mappings = []

        # Add base category codes
        mappings.extend(taxonomy_entry["categories"])

        # Add relevant techniques based on keyword matching
        for technique in taxonomy_entry["techniques"]:
            technique_lower = technique.lower()
            # Check if technique name appears in text or is highly relevant to category
            if (technique_lower in text or
                category == AttackCategory.LLM01_PROMPT_INJECTION and "injection" in technique_lower):
                mappings.append(technique)

        # Add severity indicator
        mappings.append(f"Severity: {taxonomy_entry['severity']}")

        return list(set(mappings))  # Deduplicate

    def _infer_mitre_atlas(self, category: AttackCategory, text: str) -> List[str]:
        """Infer MITRE ATLAS mappings based on category and content."""
        taxonomy_entry = self.taxonomy.MITRE_ATLAS_TAXONOMY.get(category)

        if not taxonomy_entry:
            return []

        mappings = []

        # Add tactic codes
        mappings.extend(taxonomy_entry["tactics"])

        # Add relevant techniques based on keyword matching
        for technique in taxonomy_entry["techniques"]:
            technique_lower = technique.lower()
            if technique_lower in text:
                mappings.append(technique)

        # Additional keyword-based detection
        for tactic, keywords in self._keyword_patterns.get(FrameworkMapping.MITRE_ATLAS, {}).items():
            if any(kw in text for kw in keywords):
                if tactic not in mappings:
                    mappings.append(tactic)

        return list(set(mappings))

    def _infer_nist_ai_rmf(self, category: AttackCategory, text: str) -> List[str]:
        """Infer NIST AI RMF mappings based on category."""
        taxonomy_entry = self.taxonomy.NIST_AI_RMF_TAXONOMY.get(category)

        if not taxonomy_entry:
            return []

        mappings = []

        # Add category codes
        mappings.extend(taxonomy_entry["categories"])

        # Add function information
        mappings.extend(taxonomy_entry["functions"])

        # Add risk level
        mappings.append(f"Risk: {taxonomy_entry['risk_level']}")

        return list(set(mappings))

    def _infer_iso_42001(self, category: AttackCategory, risk_level: Optional[str]) -> List[str]:
        """Infer ISO 42001 mappings based on category and risk."""
        taxonomy_entry = self.taxonomy.ISO_42001_TAXONOMY.get(category)

        if not taxonomy_entry:
            return []

        mappings = []

        # Add control references
        mappings.extend(taxonomy_entry["controls"])

        # Add clause information
        for clause in taxonomy_entry["clauses"]:
            mappings.append(f"Clause: {clause}")

        # Risk level alignment
        if risk_level:
            mappings.append(f"Risk Assessment: {risk_level.upper()}")

        return list(set(mappings))

    def _infer_eu_ai_act(
        self, category: AttackCategory, risk_level: Optional[str], complexity: Optional[str]
    ) -> List[str]:
        """Infer EU AI Act risk classification."""
        taxonomy_entry = self.taxonomy.EU_AI_ACT_TAXONOMY.get(category)

        if not taxonomy_entry:
            return []

        mappings = []

        # Primary risk category
        mappings.append(f"Category: {taxonomy_entry['category']}")

        # Article references
        for article in taxonomy_entry["article"]:
            mappings.append(f"Article: {article}")

        # Requirements
        for req in taxonomy_entry["requirement"]:
            mappings.append(f"Requirement: {req}")

        # Adjust based on actual risk level if provided
        if risk_level:
            if risk_level == "critical":
                mappings.append("Classification: Prohibited (if used for manipulation)")
            elif risk_level == "high":
                mappings.append("Classification: High-Risk AI System")
            elif risk_level == "medium":
                mappings.append("Classification: High-Risk AI System")
            else:
                mappings.append("Classification: Limited/Minimal Risk")

        # Complexity consideration
        if complexity == "expert":
            mappings.append("Note: Requires expert conformity assessment")

        return list(set(mappings))

    def validate_mapping(
        self, framework: FrameworkMapping, mapping_items: List[str]
    ) -> Dict[str, any]:
        """
        Validate a framework mapping against taxonomy definitions.

        Args:
            framework: The framework to validate against
            mapping_items: List of mapping items to validate

        Returns:
            Dictionary with validation results
        """
        result = {
            "valid": True,
            "unknown_items": [],
            "warnings": [],
        }

        # Get the appropriate taxonomy
        if framework == FrameworkMapping.OWASP_ASI:
            valid_items = set()
            for taxonomy in self.taxonomy.OWASP_ASI_TAXONOMY.values():
                valid_items.update(taxonomy["categories"])
                valid_items.update(taxonomy["techniques"])
        elif framework == FrameworkMapping.MITRE_ATLAS:
            valid_items = set()
            for taxonomy in self.taxonomy.MITRE_ATLAS_TAXONOMY.values():
                valid_items.update(taxonomy["tactics"])
                valid_items.update(taxonomy["techniques"])
            # Add known keyword patterns
            for tactics in self._keyword_patterns.get(FrameworkMapping.MITRE_ATLAS, {}).keys():
                valid_items.add(tactics)
        else:
            # Other frameworks have more flexible mappings
            return result

        # Check each item
        for item in mapping_items:
            item_base = item.split(":")[0].strip() if ":" in item else item
            if item_base not in valid_items and not item_base.startswith(("Severity", "Risk", "Category", "Article", "Requirement", "Clause", "Classification", "Note")):
                result["unknown_items"].append(item)
                result["valid"] = False

        return result

    def get_taxonomy_summary(self) -> Dict[str, any]:
        """
        Get a summary of available taxonomy mappings.

        Returns:
            Dictionary with taxonomy coverage information
        """
        return {
            "frameworks": [f.value for f in FrameworkMapping],
            "categories_mapped": len(self.taxonomy.OWASP_ASI_TAXONOMY),
            "owasp_asi_techniques": sum(
                len(t["techniques"]) for t in self.taxonomy.OWASP_ASI_TAXONOMY.values()
            ),
            "mitre_atlas_tactics": sum(
                len(t["tactics"]) for t in self.taxonomy.MITRE_ATLAS_TAXONOMY.values()
            ),
            "nist_ai_rmf_categories": len(self.taxonomy.NIST_AI_RMF_TAXONOMY),
            "iso_42001_controls": sum(
                len(t["controls"]) for t in self.taxonomy.ISO_42001_TAXONOMY.values()
            ),
        }

    def get_framework_mapping_for_category(
        self, category: AttackCategory, framework: FrameworkMapping
    ) -> List[str]:
        """
        Get the default framework mapping for a specific category.

        Args:
            category: The OWASP LLM Top-10 category
            framework: The framework to get mappings for

        Returns:
            List of framework-specific mappings
        """
        if framework == FrameworkMapping.OWASP_ASI:
            entry = self.taxonomy.OWASP_ASI_TAXONOMY.get(category)
            if entry:
                return entry["categories"] + entry["techniques"][:2]

        elif framework == FrameworkMapping.MITRE_ATLAS:
            entry = self.taxonomy.MITRE_ATLAS_TAXONOMY.get(category)
            if entry:
                return entry["tactics"] + entry["techniques"][:2]

        elif framework == FrameworkMapping.NIST_AI_RMF:
            entry = self.taxonomy.NIST_AI_RMF_TAXONOMY.get(category)
            if entry:
                return entry["categories"] + entry["functions"]

        elif framework == FrameworkMapping.ISO_42001:
            entry = self.taxonomy.ISO_42001_TAXONOMY.get(category)
            if entry:
                return [f"Control: {c}" for c in entry["controls"]]

        elif framework == FrameworkMapping.EU_AI_ACT:
            entry = self.taxonomy.EU_AI_ACT_TAXONOMY.get(category)
            if entry:
                return [f"Category: {entry['category']}", f"Risk: {entry['risk_level']}"]

        return []


# Singleton instance
_mapping_service: Optional[FrameworkMappingService] = None


def get_framework_mapping_service() -> FrameworkMappingService:
    """Get the singleton FrameworkMappingService instance."""
    global _mapping_service
    if _mapping_service is None:
        _mapping_service = FrameworkMappingService()
    return _mapping_service
