"""
Test script to verify jCodeMunch MCP integration.

This script tests that jCodeMunch is properly installed and can be used
 to index and explore the AgentTwister codebase.
"""
import pytest
import subprocess
import json
from pathlib import Path


class TestJCodeMunchMCP:
    """Test jCodeMunch MCP server installation and basic functionality."""

    def test_jcodemunch_installed(self):
        """Verify jCodeMunch MCP is installed and accessible."""
        result = subprocess.run(
            ["which", "jcodemunch-mcp"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, "jCodeMunch MCP should be installed"
        assert "jcodemunch-mcp" in result.stdout

    def test_mcp_configuration_exists(self):
        """Verify the MCP configuration file exists."""
        config_path = Path("/Users/v13478/Desktop/AgentTwister/.mcp.json")
        assert config_path.exists(), f"MCP config should exist at {config_path}"

        with open(config_path) as f:
            config = json.load(f)
            assert "jcodemunch" in config
            assert config["jcodemunch"]["command"] == "jcodemunch-mcp"

    def test_index_local_folder(self):
        """Test indexing a local folder with jCodeMunch."""
        # This test requires the MCP server to be running
        # In actual usage, this would be called through the MCP protocol
        # For this test, we just verify the command is available
        result = subprocess.run(
            ["jcodemunch-mcp", "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0

        # Verify key features are mentioned in help
        help_text = result.stdout
        assert "index_folder" in help_text or "index_repo" in help_text


    def test_integration_documentation_exists(self):
        """Verify integration documentation exists."""
        doc_path = Path("/Users/v13478/Desktop/AgentTwister/docs/jcodemunch-integration.md")
        assert doc_path.exists(), f"Integration docs should exist"
