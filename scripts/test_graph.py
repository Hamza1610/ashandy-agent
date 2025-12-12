"""
Simple test script to verify the new LangGraph implementation works.
Run this to test the graph without sending actual WhatsApp messages.
"""
import asyncio
from app.graphs.main_graph import app
from app.state.agent_state import AgentState
from langchain_core.messages import HumanMessage
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_text_query():
    """Test a simple text query flow."""
    print("\n" + "="*60)
    print("TEST 1: Text Query Flow")
    print("="*60)
    
    input_state = {
        "messages": [HumanMessage(content="Hi, do you have lipstick?")],
        "user_id": "test_user_123",
        "session_id": "test_session_123",
        "platform": "whatsapp",
        "is_admin": False,
        "blocked": False,
        "order_intent": False,
        "requires_handoff": False
    }
    
    try:
        print("\n📤 Input: 'Hi, do you have lipstick?'")
        print("🔄 Invoking graph...")
        
        result = await app.ainvoke(
            input_state,
            config={"configurable": {"thread_id": "test_123"}}
        )
        
        print(f"\n✅ Graph execution completed!")
        print(f"📊 Final state keys: {list(result.keys())}")
        print(f"💬 Messages exchanged: {len(result.get('messages', []))}")
        
        if result.get('messages'):
            last_msg = result['messages'][-1]
            print(f"\n🤖 AI Response:")
            print(f"   {last_msg.content[:200]}...")
        
        print(f"\n📈 State snapshot:")
        print(f"   - Query Type: {result.get('query_type')}")
        print(f"   - Order Intent: {result.get('order_intent')}")
        print(f"   - Cached: {'Yes' if result.get('cached_response') else 'No'}")
        print(f"   - Sentiment Score: {result.get('sentiment_score')}")
        
        return True
    except Exception as e:
        print(f"\n❌ Test failed with error:")
        print(f"   {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_admin_route():
    """Test admin routing."""
    print("\n" + "="*60)
    print("TEST 2: Admin Route")
    print("="*60)
    
    input_state = {
        "messages": [HumanMessage(content="/stock")],
        "user_id": "admin_user",
        "session_id": "admin_session",
        "platform": "whatsapp",
        "is_admin": True,
        "blocked": False,
        "order_intent": False,
        "requires_handoff": False
    }
    
    try:
        print("\n📤 Input: '/stock' (admin command)")
        print("🔄 Invoking graph...")
        
        result = await app.ainvoke(
            input_state,
            config={"configurable": {"thread_id": "admin_123"}}
        )
        
        print(f"\n✅ Admin route completed!")
        print(f"📊 Query routed as: {result.get('query_type')}")
        
        return True
    except Exception as e:
        print(f"\n❌ Admin test failed:")
        print(f"   {type(e).__name__}: {str(e)}")
        return False


async def test_graph_structure():
    """Verify graph structure."""
    print("\n" + "="*60)
    print("TEST 3: Graph Structure Verification")
    print("="*60)
    
    try:
        graph = app.get_graph()
        nodes = list(graph.nodes.keys())
        edges = list(graph.edges)
        
        print(f"\n✅ Graph compiled successfully!")
        print(f"📊 Nodes: {len(nodes)}")
        print(f"🔗 Edges: {len(edges)}")
        
        print(f"\n📋 Node list:")
        for i, node in enumerate(sorted(nodes), 1):
            print(f"   {i:2d}. {node}")
        
        # Check critical nodes exist
        critical_nodes = [
            "router", "safety", "sales", 
            "cache_check", "response", "admin"
        ]
        
        print(f"\n🔍 Critical nodes check:")
        for node in critical_nodes:
            status = "✅" if node in nodes else "❌"
            print(f"   {status} {node}")
        
        return all(node in nodes for node in critical_nodes)
        
    except Exception as e:
        print(f"\n❌ Structure test failed:")
        print(f"   {type(e).__name__}: {str(e)}")
        return False


async def main():
    """Run all tests."""
    print("\n" + "🧪 " + "="*58)
    print("🧪  AWELEWA LANGGRAPH - INTEGRATION TESTS")
    print("🧪 " + "="*58)
    
    tests = [
        ("Graph Structure", test_graph_structure),
        ("Text Query Flow", test_text_query),
        ("Admin Route", test_admin_route),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status} - {test_name}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print(f"\n📈 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready for production.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review above.")


if __name__ == "__main__":
    asyncio.run(main())
