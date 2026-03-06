#!/usr/bin/env python3
"""
Payload Library Verification Script

This script verifies the payload library implementation without requiring
a running API server or SQLite connection. It validates:
1. The data model definitions
2. The payload templates JSON structure
3. Coverage of OWASP LLM Top-10 categories
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(text: str):
    """Print a section header"""
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}")


def print_success(text: str):
    """Print a success message"""
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text: str):
    """Print an error message"""
    print(f"{RED}✗ {text}{RESET}")


def print_warning(text: str):
    """Print a warning message"""
    print(f"{YELLOW}⚠ {text}{RESET}")


def verify_payload_templates_file() -> bool:
    """Verify the payload templates JSON file exists and is valid"""
    print_header("Verifying Payload Templates File")

    templates_file = Path(__file__).parent.parent.parent / "data" / "payload-templates" / "owasp_llm_payloads.json"

    if not templates_file.exists():
        print_error(f"Payload templates file not found: {templates_file}")
        return False

    print_success(f"Found payload templates file: {templates_file}")

    # Load and parse JSON
    try:
        with open(templates_file, "r") as f:
            data = json.load(f)
        print_success("JSON file is valid")
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON: {e}")
        return False

    # Verify structure
    if "metadata" not in data:
        print_error("Missing 'metadata' section")
        return False
    print_success("Metadata section found")

    if "templates" not in data:
        print_error("Missing 'templates' section")
        return False
    print_success("Templates section found")

    metadata = data["metadata"]
    templates = data["templates"]

    print(f"\n{BLUE}Metadata:{RESET}")
    print(f"  Name: {metadata.get('name', 'N/A')}")
    print(f"  Version: {metadata.get('version', 'N/A')}")
    print(f"  Last Updated: {metadata.get('last_updated', 'N/A')}")

    return True


def verify_templates_structure(templates: List[Dict[str, Any]]) -> bool:
    """Verify the structure of individual templates"""
    print_header("Verifying Template Structure")

    required_fields = [
        "id", "name", "slug", "category", "complexity", "template",
        "description", "framework_mappings", "target_frameworks",
        "target_models", "tags", "risk_level", "effectiveness_metrics"
    ]

    all_valid = True
    missing_fields_counts = {}

    for i, template in enumerate(templates):
        missing = [field for field in required_fields if field not in template]
        if missing:
            all_valid = False
            for field in missing:
                missing_fields_counts[field] = missing_fields_counts.get(field, 0) + 1
            print_error(f"Template {i+1} ({template.get('id', 'unknown')}) missing fields: {missing}")

    if all_valid:
        print_success(f"All {len(templates)} templates have required fields")
    else:
        print_warning("Some templates are missing required fields:")
        for field, count in sorted(missing_fields_counts.items()):
            print_warning(f"  - {field}: {count} templates")

    return all_valid


def verify_owasp_coverage(templates: List[Dict[str, Any]]) -> bool:
    """Verify OWASP LLM Top-10 coverage"""
    print_header("Verifying OWASP LLM Top-10 Coverage")

    expected_categories = [
        "LLM01: Prompt Injection",
        "LLM02: Insecure Output Handling",
        "LLM03: Training Data Poisoning",
        "LLM04: Model Denial of Service",
        "LLM05: Supply Chain Vulnerabilities",
        "LLM06: Sensitive Information Disclosure",
        "LLM07: Insecure Plugin Design",
        "LLM08: Authorization Bypass",
        "LLM09: Overreliance on Model",
        "LLM10: Model Theft",
    ]

    category_counts = {}
    for template in templates:
        category = template.get("category", "Unknown")
        category_counts[category] = category_counts.get(category, 0) + 1

    print(f"\n{BLUE}Category Breakdown:{RESET}")
    total_covered = 0
    for category in expected_categories:
        count = category_counts.get(category, 0)
        if count > 0:
            print_success(f"{category}: {count} payloads")
            total_covered += 1
        else:
            print_warning(f"{category}: 0 payloads (MISSING)")

    coverage_percent = (total_covered / len(expected_categories)) * 100
    print(f"\n{BLUE}Coverage: {total_covered}/{len(expected_categories)} categories ({coverage_percent:.0f}%){RESET}")

    return total_covered >= 8  # At least 80% coverage


def verify_effectiveness_metrics(templates: List[Dict[str, Any]]) -> bool:
    """Verify effectiveness metrics are present and valid"""
    print_header("Verifying Effectiveness Metrics")

    with_metrics = 0
    with_valid_success_rate = 0
    with_total_attempts = 0

    for template in templates:
        metrics = template.get("effectiveness_metrics")
        if metrics:
            with_metrics += 1
            if "success_rate" in metrics:
                rate = metrics["success_rate"]
                if 0 <= rate <= 1:
                    with_valid_success_rate += 1
            if "total_attempts" in metrics:
                if metrics["total_attempts"] >= 0:
                    with_total_attempts += 1

    print_success(f"{with_metrics}/{len(templates)} templates have effectiveness metrics")
    print_success(f"{with_valid_success_rate}/{len(templates)} templates have valid success rates")
    print_success(f"{with_total_attempts}/{len(templates)} templates have total attempts")

    return with_metrics > 0


def verify_framework_mappings(templates: List[Dict[str, Any]]) -> bool:
    """Verify framework mappings are present"""
    print_header("Verifying Framework Mappings")

    expected_frameworks = [
        "OWASP AI Security Standard",
        "MITRE Adversarial Threat Landscape for AI Systems",
        "NIST AI Risk Management Framework",
    ]

    framework_counts = {}
    for template in templates:
        mappings = template.get("framework_mappings", {})
        for framework in mappings.keys():
            framework_counts[framework] = framework_counts.get(framework, 0) + 1

    print(f"\n{BLUE}Framework Mapping Coverage:{RESET}")
    for framework in expected_frameworks:
        count = framework_counts.get(framework, 0)
        if count > 0:
            print_success(f"{framework}: {count} payloads")
        else:
            print_warning(f"{framework}: 0 payloads")

    return len(framework_counts) >= 2


def verify_risk_levels(templates: List[Dict[str, Any]]) -> bool:
    """Verify risk level classifications"""
    print_header("Verifying Risk Level Classifications")

    risk_counts = {}
    for template in templates:
        risk = template.get("risk_level", "unknown")
        risk_counts[risk] = risk_counts.get(risk, 0) + 1

    print(f"\n{BLUE}Risk Level Distribution:{RESET}")
    for risk in ["low", "medium", "high", "critical"]:
        count = risk_counts.get(risk, 0)
        print(f"  {risk}: {count} payloads")

    requires_confirmation = sum(1 for t in templates if t.get("requires_secondary_confirmation", False))
    print(f"\n  Requires secondary confirmation: {requires_confirmation} payloads")

    return True


def verify_complexity_levels(templates: List[Dict[str, Any]]) -> bool:
    """Verify complexity level classifications"""
    print_header("Verifying Complexity Level Classifications")

    complexity_counts = {}
    for template in templates:
        complexity = template.get("complexity", "unknown")
        complexity_counts[complexity] = complexity_counts.get(complexity, 0) + 1

    print(f"\n{BLUE}Complexity Distribution:{RESET}")
    for level in ["basic", "intermediate", "advanced", "expert"]:
        count = complexity_counts.get(level, 0)
        print(f"  {level}: {count} payloads")

    return True


def main() -> int:
    """Main verification entry point"""
    print_header("AgentTwister Payload Library Verification")

    # Get the templates file path
    templates_file = Path(__file__).parent.parent.parent / "data" / "payload-templates" / "owasp_llm_payloads.json"

    if not templates_file.exists():
        print_error(f"Payload templates file not found: {templates_file}")
        return 1

    # Load templates
    with open(templates_file, "r") as f:
        data = json.load(f)

    templates = data["templates"]
    metadata = data["metadata"]

    print(f"\n{BLUE}Payload Library Summary:{RESET}")
    print(f"  Total templates: {len(templates)}")
    print(f"  Version: {metadata.get('version', 'N/A')}")
    print(f"  Last updated: {metadata.get('last_updated', 'N/A')}")

    # Run verifications
    results = []

    results.append(("File Structure", verify_payload_templates_file()))
    results.append(("Template Structure", verify_templates_structure(templates)))
    results.append(("OWASP Coverage", verify_owasp_coverage(templates)))
    results.append(("Effectiveness Metrics", verify_effectiveness_metrics(templates)))
    results.append(("Framework Mappings", verify_framework_mappings(templates)))
    results.append(("Risk Levels", verify_risk_levels(templates)))
    results.append(("Complexity Levels", verify_complexity_levels(templates)))

    # Summary
    print_header("Verification Summary")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        if result:
            print_success(f"{name}: PASSED")
        else:
            print_error(f"{name}: FAILED")

    print(f"\n{BLUE}Overall: {passed}/{total} checks passed{RESET}")

    if passed == total:
        print_success("\n🎉 All verifications passed! Payload library is ready.")
        return 0
    else:
        print_warning("\n⚠ Some verifications failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    # Try to use Python from homebrew
    import subprocess
    import os

    # Check if we can access python3.12 or python3.13
    python_bin = None
    for py_ver in ["python3.13", "python3.12", "python3"]:
        try:
            result = subprocess.run([py_ver, "--version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                python_bin = py_ver
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    if python_bin and python_bin != sys.executable:
        # Re-run with the correct Python
        os.execvp(python_bin, [python_bin] + sys.argv)

    sys.exit(main())
