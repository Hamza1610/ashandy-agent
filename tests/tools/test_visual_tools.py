import pytest
from app.tools.visual_tools import process_image_for_search
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_process_image_for_search(mocker):
    # Mock request
    mocker.patch("requests.get", return_value=MagicMock(content=b"fake_image_bytes", status_code=200))
    # Mock Image open
    mock_image = mocker.patch("PIL.Image.open")
    mock_image.return_value.convert.return_value = MagicMock()
    
    # Mock Models
    mocker.patch("app.tools.visual_tools.load_models") # Prevent real load
    mocker.patch("app.tools.visual_tools.dino_processor", MagicMock())
    
    mock_model_output = MagicMock()
    mock_model_output.last_hidden_state = [[ [0.5]*768 ]] # Simulated embedding
    
    mock_dino_model = MagicMock()
    mock_dino_model.return_value = mock_model_output
    mocker.patch("app.tools.visual_tools.dino_model", mock_dino_model)
    
    result = await process_image_for_search.invoke("http://example.com/image.jpg")
    
    assert isinstance(result, list)
    assert len(result) == 768
    assert result[0] == 0.5
