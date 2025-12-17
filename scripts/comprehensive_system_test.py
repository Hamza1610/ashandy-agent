#!/usr/bin/env python3
"""
Comprehensive System Test Script
================================
Runs all 28 test scenarios for both User and Admin roles against the running server.

Usage:
    # Start server first:
    uvicorn app.main:app --reload --port 8000
    
    # Then run tests:
    python scripts/comprehensive_system_test.py

Author: Auto-generated from test plan
"""

import asyncio
import httpx
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_URL = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8000")
API_ENDPOINT = f"{BASE_URL}/api/test/message"
TIMEOUT = 60.0  # seconds per request

# Test image for visual search (relative to project root)
TEST_IMAGE_PATH = "uploads/WhatsApp Image 2025-12-17 at 19.13.13_9ddb2fa4.jpg"


# =============================================================================
# COLORS FOR CONSOLE OUTPUT
# =============================================================================

# Fix Windows console encoding
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")


def print_pass(test_id: str, message: str):
    print(f"{Colors.GREEN}[PASS] [{test_id}]{Colors.ENDC} - {message}")


def print_fail(test_id: str, message: str, error: str = ""):
    print(f"{Colors.RED}[FAIL] [{test_id}]{Colors.ENDC} - {message}")
    if error:
        print(f"   {Colors.YELLOW}Error: {error}{Colors.ENDC}")


def print_skip(test_id: str, message: str):
    print(f"{Colors.YELLOW}[SKIP] [{test_id}]{Colors.ENDC} - {message}")


def print_info(message: str):
    print(f"{Colors.CYAN}[INFO] {message}{Colors.ENDC}")


# =============================================================================
# DATA CLASSES
# =============================================================================

class TestStatus(Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TestScenario:
    """Definition of a test scenario."""
    id: str
    name: str
    message: str
    user_id: str = "test_user_main"
    is_admin: bool = False
    expected_keywords: List[str] = field(default_factory=list)
    expected_not: List[str] = field(default_factory=list)  # Should NOT contain
    delay_before: float = 0.0  # Seconds to wait before this test
    category: str = "general"


@dataclass
class TestResult:
    """Result of a single test."""
    scenario: TestScenario
    status: TestStatus
    response: Optional[str] = None
    query_type: Optional[str] = None
    order_intent: Optional[bool] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    keywords_found: List[str] = field(default_factory=list)
    keywords_missing: List[str] = field(default_factory=list)


# =============================================================================
# TEST SCENARIOS - All 28 Tests
# =============================================================================

# Part A: USER Tests (17)
USER_TESTS = [
    # A1: Product Inquiry (existing product)
    TestScenario(
        id="A1",
        name="Product Inquiry - Existing",
        message="Do you have CeraVe Hydrating Cleanser?",
        expected_keywords=["CeraVe", "cleanser", "₦", "available"],
        category="product_search"
    ),
    
    # A2: Visual Search (image URL)
    TestScenario(
        id="A2",
        name="Visual Search",
        message=f"[Image: {TEST_IMAGE_PATH}]",  # Will be replaced with actual URL
        expected_keywords=["product", "similar", "recommend"],
        category="visual_search"
    ),
    
    # A3: Non-existent Product (alternatives)
    TestScenario(
        id="A3",
        name="Product Not Found - Alternatives",
        message="Do you have moon dust face cream?",
        expected_keywords=["sorry", "alternative", "recommend", "similar"],
        category="product_search"
    ),
    
    # A4: Out of Category
    TestScenario(
        id="A4",
        name="Category Restriction",
        message="Do you sell laptops or phones?",
        expected_keywords=["skincare", "cosmetics", "sorry", "specialize"],
        category="category_check"
    ),
    
    # A5-A11: Order Flow (uses dedicated user_id for continuity)
    TestScenario(
        id="A5",
        name="Add to Order",
        message="I'll take the CeraVe Hydrating Cleanser",
        user_id="order_flow_user",
        expected_keywords=["added", "order", "cart"],
        category="order_flow"
    ),
    TestScenario(
        id="A6",
        name="Add Multiple Items",
        message="Add Nivea Body Lotion too please",
        user_id="order_flow_user",
        expected_keywords=["added", "Nivea", "order"],
        delay_before=1.0,
        category="order_flow"
    ),
    TestScenario(
        id="A7",
        name="Complete Order - Summary",
        message="That's all I need",
        user_id="order_flow_user",
        expected_keywords=["order", "summary", "total", "₦"],
        delay_before=1.0,
        category="order_flow"
    ),
    TestScenario(
        id="A8",
        name="Confirm Order",
        message="Yes, confirm my order",
        user_id="order_flow_user",
        expected_keywords=["confirm", "address", "delivery"],
        delay_before=1.0,
        category="order_flow"
    ),
    TestScenario(
        id="A9",
        name="Provide Address",
        message="My address is 123 Bodija Road, Ibadan, Oyo State",
        user_id="order_flow_user",
        expected_keywords=["address", "delivery", "Bodija"],
        delay_before=1.0,
        category="order_flow"
    ),
    TestScenario(
        id="A10",
        name="Check Delivery Fee",
        message="What's the delivery fee?",
        user_id="order_flow_user",
        expected_keywords=["delivery", "fee", "₦"],
        delay_before=1.0,
        category="order_flow"
    ),
    TestScenario(
        id="A11",
        name="Complete Checkout",
        message="Proceed to payment",
        user_id="order_flow_user",
        expected_keywords=["payment", "pay", "link"],
        delay_before=1.0,
        category="order_flow"
    ),
    
    # A12-A13: Memory Tests
    TestScenario(
        id="A12",
        name="Memory Retrieval",
        message="Hi, I'm back! Remember my last order?",
        user_id="memory_test_user",
        expected_keywords=["welcome", "back", "previous"],
        category="memory"
    ),
    TestScenario(
        id="A13",
        name="Memory Save",
        message="I prefer products with hyaluronic acid",
        user_id="memory_test_user",
        expected_keywords=["hyaluronic", "noted", "preference"],
        delay_before=1.0,
        category="memory"
    ),
    
    # A14-A17: Feedback and Support
    TestScenario(
        id="A14",
        name="Sentiment Detection - Positive",
        message="I absolutely love your products! Best skincare ever!",
        expected_keywords=["thank", "glad", "appreciate"],
        category="feedback"
    ),
    TestScenario(
        id="A15",
        name="Complaint Handling",
        message="I have a serious complaint about my last order. The product arrived damaged.",
        expected_keywords=["sorry", "apolog", "help", "resolve"],
        category="support"
    ),
    TestScenario(
        id="A16",
        name="Escalation Request",
        message="I want to speak to a manager or human agent immediately",
        expected_keywords=["manager", "human", "escalat", "connect"],
        category="support"
    ),
    TestScenario(
        id="A17",
        name="NDPR Data Deletion",
        message="Please delete all my personal data from your system",
        expected_keywords=["data", "delet", "privacy", "request"],
        category="compliance"
    ),
]

# Part B: ADMIN Tests (6)
ADMIN_TESTS = [
    TestScenario(
        id="B1",
        name="Admin Analytics",
        message="Who bought the most products this week?",
        user_id="admin_user",
        is_admin=True,
        expected_keywords=["customer", "purchase", "week"],
        category="admin"
    ),
    TestScenario(
        id="B2",
        name="Admin Report",
        message="Give me a comprehensive sales report",
        user_id="admin_user",
        is_admin=True,
        expected_keywords=["report", "sales", "total"],
        category="admin"
    ),
    TestScenario(
        id="B3",
        name="Admin - List Approvals",
        message="List all pending order approvals",
        user_id="admin_user",
        is_admin=True,
        expected_keywords=["pending", "order", "approval"],
        category="admin"
    ),
    TestScenario(
        id="B4",
        name="Admin - Approve Order",
        message="Approve order #12345",
        user_id="admin_user",
        is_admin=True,
        expected_keywords=["order", "approv"],
        category="admin"
    ),
    TestScenario(
        id="B5",
        name="Admin - Customer Message",
        message="Tell customer with ID customer_123 that their order has shipped",
        user_id="admin_user",
        is_admin=True,
        expected_keywords=["message", "customer", "sent"],
        category="admin"
    ),
    TestScenario(
        id="B6",
        name="Admin - Log Incident",
        message="Log an incident: Customer reported receiving wrong product color",
        user_id="admin_user",
        is_admin=True,
        expected_keywords=["incident", "logged", "record"],
        category="admin"
    ),
]

# Part C: Complete Flow (1)
COMPLETE_FLOW_TESTS = [
    # This is a multi-turn test - uses dedicated user
    TestScenario(
        id="C1-1",
        name="Complete Flow: Inquiry",
        message="Hi! I'm looking for a good moisturizer for dry skin",
        user_id="complete_flow_user",
        expected_keywords=["moistur", "dry skin", "recommend"],
        category="complete_flow"
    ),
    TestScenario(
        id="C1-2",
        name="Complete Flow: Selection",
        message="I'll take the CeraVe Moisturizing Cream",
        user_id="complete_flow_user",
        expected_keywords=["CeraVe", "added", "order"],
        delay_before=1.0,
        category="complete_flow"
    ),
    TestScenario(
        id="C1-3",
        name="Complete Flow: Checkout Start",
        message="That's all, let's checkout",
        user_id="complete_flow_user",
        expected_keywords=["order", "address", "total"],
        delay_before=1.0,
        category="complete_flow"
    ),
    TestScenario(
        id="C1-4",
        name="Complete Flow: Address",
        message="Deliver to 45 Ring Road, Ibadan, Oyo State. Phone: 08012345678",
        user_id="complete_flow_user",
        expected_keywords=["delivery", "address", "confirm"],
        delay_before=1.0,
        category="complete_flow"
    ),
    TestScenario(
        id="C1-5",
        name="Complete Flow: Payment",
        message="Yes, generate payment link",
        user_id="complete_flow_user",
        expected_keywords=["payment", "link", "pay"],
        delay_before=1.0,
        category="complete_flow"
    ),
]

# Part D: Edge Cases (4)
EDGE_CASE_TESTS = [
    TestScenario(
        id="D1",
        name="High-Value Order",
        message="I want to order 50 units of La Roche-Posay Effaclar Duo for my spa",
        expected_keywords=["bulk", "quantity", "contact", "manager"],
        category="edge_case"
    ),
    TestScenario(
        id="D2",
        name="Greeting Only",
        message="Hello! How are you today?",
        expected_keywords=["hello", "hi", "help", "assist"],
        category="edge_case"
    ),
    TestScenario(
        id="D3",
        name="Off-Topic Query",
        message="What's the weather like in Lagos today?",
        expected_keywords=["skincare", "cosmetics", "help", "product"],
        category="edge_case"
    ),
    TestScenario(
        id="D4",
        name="Repeated Query (Cache Hit)",
        message="Do you have CeraVe Hydrating Cleanser?",  # Same as A1
        expected_keywords=["CeraVe", "cleanser"],
        category="edge_case"
    ),
]


# =============================================================================
# TEST RUNNER
# =============================================================================

class TestRunner:
    """Executes test scenarios and collects results."""
    
    def __init__(self):
        self.results: List[TestResult] = []
        self.client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=TIMEOUT)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def run_scenario(self, scenario: TestScenario) -> TestResult:
        """Execute a single test scenario."""
        start_time = datetime.now()
        
        # Wait if delay specified
        if scenario.delay_before > 0:
            await asyncio.sleep(scenario.delay_before)
        
        try:
            # Prepare request
            payload = {
                "message": scenario.message,
                "user_id": scenario.user_id,
                "platform": "whatsapp",
                "is_admin": scenario.is_admin
            }
            
            # Send request
            response = await self.client.post(API_ENDPOINT, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            # Extract response
            ai_response = data.get("ai_response", "") or ""
            query_type = data.get("query_type")
            order_intent = data.get("order_intent")
            error = data.get("error")
            
            if error:
                return TestResult(
                    scenario=scenario,
                    status=TestStatus.FAILED,
                    response=ai_response,
                    error=error,
                    duration_ms=duration_ms
                )
            
            # Validate response
            keywords_found = []
            keywords_missing = []
            response_lower = ai_response.lower()
            
            for keyword in scenario.expected_keywords:
                if keyword.lower() in response_lower:
                    keywords_found.append(keyword)
                else:
                    keywords_missing.append(keyword)
            
            # Check for unwanted content
            unwanted_found = []
            for unwanted in scenario.expected_not:
                if unwanted.lower() in response_lower:
                    unwanted_found.append(unwanted)
            
            # Determine pass/fail
            # Pass if at least half of keywords found and no unwanted content
            min_keywords = max(1, len(scenario.expected_keywords) // 2)
            passed = (
                len(keywords_found) >= min_keywords 
                and len(unwanted_found) == 0
                and len(ai_response) > 10  # Not empty response
            )
            
            return TestResult(
                scenario=scenario,
                status=TestStatus.PASSED if passed else TestStatus.FAILED,
                response=ai_response,
                query_type=query_type,
                order_intent=order_intent,
                duration_ms=duration_ms,
                keywords_found=keywords_found,
                keywords_missing=keywords_missing
            )
            
        except httpx.ConnectError:
            return TestResult(
                scenario=scenario,
                status=TestStatus.SKIPPED,
                error="Connection failed - is the server running?"
            )
        except Exception as e:
            return TestResult(
                scenario=scenario,
                status=TestStatus.FAILED,
                error=str(e),
                duration_ms=(datetime.now() - start_time).total_seconds() * 1000
            )
    
    async def run_all(self, scenarios: List[TestScenario]) -> List[TestResult]:
        """Run all scenarios sequentially."""
        for scenario in scenarios:
            result = await self.run_scenario(scenario)
            self.results.append(result)
            
            # Print result immediately
            if result.status == TestStatus.PASSED:
                print_pass(result.scenario.id, result.scenario.name)
                if result.response:
                    preview = result.response[:100] + "..." if len(result.response) > 100 else result.response
                    print(f"   {Colors.CYAN}Response: {preview}{Colors.ENDC}")
            elif result.status == TestStatus.FAILED:
                print_fail(result.scenario.id, result.scenario.name, result.error or "")
                if result.keywords_missing:
                    print(f"   {Colors.YELLOW}Missing keywords: {result.keywords_missing}{Colors.ENDC}")
                if result.response:
                    preview = result.response[:150] + "..." if len(result.response) > 150 else result.response
                    print(f"   {Colors.CYAN}Response: {preview}{Colors.ENDC}")
            else:
                print_skip(result.scenario.id, result.scenario.name)
                if result.error:
                    print(f"   {Colors.YELLOW}Reason: {result.error}{Colors.ENDC}")
        
        return self.results


def generate_report(results: List[TestResult]) -> Dict[str, Any]:
    """Generate a summary report."""
    passed = sum(1 for r in results if r.status == TestStatus.PASSED)
    failed = sum(1 for r in results if r.status == TestStatus.FAILED)
    skipped = sum(1 for r in results if r.status == TestStatus.SKIPPED)
    total = len(results)
    
    # Group by category
    by_category: Dict[str, Dict] = {}
    for result in results:
        cat = result.scenario.category
        if cat not in by_category:
            by_category[cat] = {"passed": 0, "failed": 0, "skipped": 0}
        if result.status == TestStatus.PASSED:
            by_category[cat]["passed"] += 1
        elif result.status == TestStatus.FAILED:
            by_category[cat]["failed"] += 1
        else:
            by_category[cat]["skipped"] += 1
    
    return {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "pass_rate": f"{(passed/total*100):.1f}%" if total > 0 else "N/A"
        },
        "by_category": by_category,
        "details": [
            {
                "id": r.scenario.id,
                "name": r.scenario.name,
                "status": r.status.value,
                "duration_ms": r.duration_ms,
                "response_preview": (r.response[:200] if r.response else None),
                "error": r.error
            }
            for r in results
        ]
    }


async def main():
    """Main entry point."""
    print_header("ASHANDY AGENT - COMPREHENSIVE SYSTEM TEST")
    print_info(f"Target: {API_ENDPOINT}")
    print_info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check server connectivity first
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(BASE_URL)
            print_info(f"Server Status: {Colors.GREEN}Connected{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.RED}ERROR: Cannot connect to server at {BASE_URL}{Colors.ENDC}")
        print(f"{Colors.YELLOW}Please start the server first:{Colors.ENDC}")
        print(f"   uvicorn app.main:app --reload --port 8000")
        sys.exit(1)
    
    all_scenarios = []
    
    # Collect all test scenarios
    async with TestRunner() as runner:
        # Part A: User Tests
        print_header("PART A: USER TESTS (17)")
        await runner.run_all(USER_TESTS)
        
        # Part B: Admin Tests
        print_header("PART B: ADMIN TESTS (6)")
        await runner.run_all(ADMIN_TESTS)
        
        # Part C: Complete Flow
        print_header("PART C: COMPLETE PURCHASE FLOW")
        await runner.run_all(COMPLETE_FLOW_TESTS)
        
        # Part D: Edge Cases
        print_header("PART D: EDGE CASES")
        await runner.run_all(EDGE_CASE_TESTS)
        
        # Generate Report
        print_header("TEST SUMMARY")
        report = generate_report(runner.results)
        
        summary = report["summary"]
        print(f"\n{Colors.BOLD}Results:{Colors.ENDC}")
        print(f"  Total:   {summary['total']}")
        print(f"  {Colors.GREEN}Passed:  {summary['passed']}{Colors.ENDC}")
        print(f"  {Colors.RED}Failed:  {summary['failed']}{Colors.ENDC}")
        print(f"  {Colors.YELLOW}Skipped: {summary['skipped']}{Colors.ENDC}")
        print(f"  Pass Rate: {Colors.BOLD}{summary['pass_rate']}{Colors.ENDC}")
        
        print(f"\n{Colors.BOLD}By Category:{Colors.ENDC}")
        for cat, stats in report["by_category"].items():
            status_str = f"{Colors.GREEN}{stats['passed']} passed{Colors.ENDC} / {Colors.RED}{stats['failed']} failed{Colors.ENDC}"
            print(f"  {cat}: {status_str}")
        
        # Save report to file
        report_path = Path(__file__).parent / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\n{Colors.CYAN}Report saved: {report_path}{Colors.ENDC}")
        
        # Exit code
        if summary["failed"] > 0:
            print(f"\n{Colors.RED}WARNING: Some tests failed!{Colors.ENDC}")
            sys.exit(1)
        else:
            print(f"\n{Colors.GREEN}SUCCESS: All tests passed!{Colors.ENDC}")
            sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
