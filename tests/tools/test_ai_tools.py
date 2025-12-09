import pytest
from app.tools.llama_guard_tool import check_safety
from app.tools.sentiment_tool import analyze_sentiment
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_check_safety(mocker, mock_settings):
    # Mock ChatGroq
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "safe"
    mock_llm.ainvoke.return_value = mock_response
    
    mocker.patch("app.tools.llama_guard_tool.ChatGroq", return_value=mock_llm)
    
    result = await check_safety.invoke("Hello friend")
    assert result == "safe"

@pytest.mark.asyncio
async def test_analyze_sentiment(mocker, mock_settings):
    # Mock ChatGroq
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "0.8"
    mock_llm.ainvoke.return_value = mock_response
    
    mocker.patch("app.tools.sentiment_tool.ChatGroq", return_value=mock_llm)
    
    result = await analyze_sentiment.invoke("I love this!")
    assert result == 0.8
