import pytest
from app.agents.sales_consultant_agent import sales_consultant_agent_node
from langchain_core.messages import HumanMessage
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_sales_agent_flow(mocker, mock_settings):
    # Mock cache
    mocker.patch("app.agents.sales_consultant_agent.check_semantic_cache.invoke", return_value=None)
    mocker.patch("app.agents.sales_consultant_agent.update_semantic_cache.invoke")
    
    # Mock vector/db
    mocker.patch("app.agents.sales_consultant_agent.retrieve_user_memory.invoke", return_value="User likes X")
    
    # Mock LLM
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Sure, would you like to buy it?"
    mock_llm.ainvoke.return_value = mock_response
    mocker.patch("app.agents.sales_consultant_agent.ChatGroq", return_value=mock_llm)
    
    state = {
        "user_id": "u1",
        "messages": [HumanMessage(content="I want X")],
        "visual_matches": []
    }
    
    result = await sales_consultant_agent_node(state)
    
    assert "Sure" in result["messages"][0].content
    assert result["order_intent"] is True # "buy" detected in response/user input simulation logic (here mocked LLM or rule based) 
    # Wait, my implementation checks USER message for intent in the code refactor.
    # Ah, implementation checks `last_message` (User's message).
    # "I want X" doesn't strictly have "buy". 
    # Let's verify the logic in sales_consultant_agent.py: if "buy" in last_message ...
    # So I should update the input message to trigger intent if I want to test that. 
