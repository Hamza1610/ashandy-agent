import pytest
from app.agents.router_agent import router_agent_node
from langchain_core.messages import HumanMessage
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_router_agent_text_mode(mocker):
    # Mock whitelist tool
    mock_whitelist = mocker.patch("app.agents.router_agent.check_admin_whitelist")
    mock_whitelist.invoke.return_value = False
    
    state = {
        "user_id": "u1",
        "messages": [HumanMessage(content="Hello")]
    }
    
    result = await router_agent_node(state)
    assert result["is_admin"] is False
    assert result["query_type"] == "text"

@pytest.mark.asyncio
async def test_router_agent_image_mode(mocker):
    mock_whitelist = mocker.patch("app.agents.router_agent.check_admin_whitelist")
    mock_whitelist.invoke.return_value = False
    
    # Message with image kwarg (simulating webhook structure)
    msg = HumanMessage(content="Look at this")
    msg.additional_kwargs = {"image_url": "http://img.com"}
    
    state = {
        "user_id": "u1",
        "messages": [msg]
    }
    
    result = await router_agent_node(state)
    assert result["query_type"] == "image"
    assert result["image_url"] == "http://img.com"

@pytest.mark.asyncio
async def test_router_agent_admin(mocker):
    mock_whitelist = mocker.patch("app.agents.router_agent.check_admin_whitelist")
    mock_whitelist.invoke.return_value = True
    
    state = {
        "user_id": "admin1",
        "messages": [HumanMessage(content="/stock sync")]
    }
    
    result = await router_agent_node(state)
    assert result["is_admin"] is True
    assert result["query_type"] == "admin_command"
