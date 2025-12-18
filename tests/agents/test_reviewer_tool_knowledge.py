"""
Unit tests for the Tool Knowledge Registry and Reviewer Agent enhancements.
"""
import pytest
from app.utils.tool_knowledge import (
    TOOL_KNOWLEDGE,
    WORKER_AUDIT_RULES,
    get_tool_knowledge,
    get_tools_for_worker,
    get_tool_validation_prompt,
    get_worker_audit_rules
)


class TestToolKnowledgeRegistry:
    """Tests for the tool knowledge registry."""
    
    def test_all_workers_have_tools(self):
        """Verify all 4 workers have tools defined."""
        workers = {"sales_worker", "payment_worker", "support_worker", "admin_worker"}
        defined_workers = {info["worker"] for info in TOOL_KNOWLEDGE.values()}
        assert workers == defined_workers, f"Missing workers: {workers - defined_workers}"
    
    def test_sales_worker_has_all_tools(self):
        """Verify sales worker has all 7 expected tools."""
        expected_tools = {
            "search_products",
            "check_product_stock",
            "detect_product_from_image",
            "retrieve_user_memory",
            "save_user_interaction",
            "search_text_products",
            "process_image_for_search"
        }
        sales_tools = set(get_tools_for_worker("sales_worker"))
        assert expected_tools == sales_tools, f"Sales tool mismatch: {expected_tools ^ sales_tools}"
    
    def test_payment_worker_has_all_tools(self):
        """Verify payment worker has all expected tools."""
        expected_tools = {
            "calculate_delivery_fee",
            "generate_payment_link",
            "create_order_record",
            "validate_and_extract_delivery",
            "check_delivery_ready",
            "request_delivery_details"
        }
        payment_tools = set(get_tools_for_worker("payment_worker"))
        assert expected_tools == payment_tools, f"Payment tool mismatch: {expected_tools ^ payment_tools}"
    
    def test_support_worker_has_all_tools(self):
        """Verify support worker has all 3 expected tools."""
        expected_tools = {
            "lookup_order_history",
            "create_support_ticket",
            "escalate_to_manager"
        }
        support_tools = set(get_tools_for_worker("support_worker"))
        assert expected_tools == support_tools, f"Support tool mismatch: {expected_tools ^ support_tools}"
    
    def test_admin_worker_has_all_tools(self):
        """Verify admin worker has all 10 expected tools."""
        expected_tools = {
            "generate_comprehensive_report",
            "list_pending_approvals",
            "approve_order",
            "reject_order",
            "relay_message_to_customer",
            "get_incident_context",
            "resolve_incident",
            "report_incident",
            "get_top_customers",
            "generate_weekly_report"
        }
        admin_tools = set(get_tools_for_worker("admin_worker"))
        assert expected_tools == admin_tools, f"Admin tool mismatch: {expected_tools ^ admin_tools}"
    
    def test_tool_has_required_fields(self):
        """Verify each tool has all required fields."""
        required_fields = {"worker", "purpose", "expected_output", "success_indicators", "failure_modes", "validation_rules"}
        for tool_name, info in TOOL_KNOWLEDGE.items():
            for field in required_fields:
                assert field in info, f"Tool '{tool_name}' missing field: {field}"
    
    def test_get_tool_knowledge_handles_suffix(self):
        """Verify get_tool_knowledge handles _tool suffix."""
        # These should return the same result
        result1 = get_tool_knowledge("search_products")
        result2 = get_tool_knowledge("search_products_tool")
        assert result1 == result2, "Should handle _tool suffix"
    
    def test_get_tool_knowledge_unknown_tool(self):
        """Verify get_tool_knowledge returns empty dict for unknown tool."""
        result = get_tool_knowledge("nonexistent_tool")
        assert result == {}, "Should return empty dict for unknown tool"


class TestToolValidationPrompt:
    """Tests for dynamic validation prompt generation."""
    
    def test_empty_tools_list(self):
        """Verify correct output when no tools were called."""
        result = get_tool_validation_prompt([])
        assert "NO TOOLS WERE CALLED" in result
    
    def test_single_tool_prompt(self):
        """Verify prompt generation for single tool."""
        result = get_tool_validation_prompt(["search_products"])
        assert "search_products" in result
        assert "Purpose:" in result
        assert "Expected:" in result
        assert "Success if contains:" in result
    
    def test_multiple_tools_prompt(self):
        """Verify prompt generation for multiple tools."""
        result = get_tool_validation_prompt(["search_products", "generate_payment_link"])
        assert "search_products" in result
        assert "generate_payment_link" in result
    
    def test_failure_modes_included(self):
        """Verify failure modes are included in prompt."""
        result = get_tool_validation_prompt(["search_products"])
        assert "Failure corrections:" in result
        assert "No results found" in result
    
    def test_unknown_tool_handled(self):
        """Verify unknown tools are gracefully handled."""
        result = get_tool_validation_prompt(["unknown_tool", "search_products"])
        # Should still include search_products
        assert "search_products" in result


class TestWorkerAuditRules:
    """Tests for worker-specific audit rules."""
    
    def test_all_workers_have_rules(self):
        """Verify all workers have audit rules defined."""
        workers = ["sales_worker", "payment_worker", "support_worker", "admin_worker"]
        for worker in workers:
            rules = get_worker_audit_rules(worker)
            assert rules, f"No audit rules for {worker}"
            assert len(rules) > 50, f"Audit rules too short for {worker}"
    
    def test_sales_worker_strict_mode(self):
        """Verify sales worker has strict anti-hallucination rules."""
        rules = get_worker_audit_rules("sales_worker")
        assert "STRICT" in rules
        assert "ANTI-HALLUCINATION" in rules
        assert "REJECT" in rules
    
    def test_support_worker_empathy_mode(self):
        """Verify support worker has empathy-focused rules."""
        rules = get_worker_audit_rules("support_worker")
        assert "EMPATHY" in rules
    
    def test_admin_worker_trust_mode(self):
        """Verify admin worker has trust mode rules."""
        rules = get_worker_audit_rules("admin_worker")
        assert "TRUST" in rules
    
    def test_unknown_worker_default(self):
        """Verify unknown worker gets default rules."""
        rules = get_worker_audit_rules("unknown_worker")
        assert "Standard validation" in rules


class TestReviewerAgentImport:
    """Tests for reviewer agent module."""
    
    def test_reviewer_imports_successfully(self):
        """Verify reviewer agent can be imported."""
        from app.agents.reviewer_agent import reviewer_agent_node
        assert reviewer_agent_node is not None
    
    def test_reviewer_uses_tool_knowledge(self):
        """Verify reviewer imports from tool_knowledge."""
        import inspect
        from app.agents import reviewer_agent
        source = inspect.getsource(reviewer_agent)
        assert "get_tool_validation_prompt" in source
        assert "get_worker_audit_rules" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
