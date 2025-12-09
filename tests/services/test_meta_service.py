import pytest
from app.services.meta_service import meta_service
import httpx
import respx

@pytest.mark.asyncio
async def test_send_whatsapp_message(mock_settings):
    # Mock the HTTP request to Meta API
    with respx.mock(base_url="https://graph.facebook.com") as respx_mock:
        route = respx_mock.post(path__regex=r"/v18.0/.*/messages").mock(
            return_value=httpx.Response(200, json={"messaging_product": "whatsapp", "messages": [{"id": "wamid.1"}]})
        )
        
        response = await meta_service.send_whatsapp_text("1234567890", "Hello Test")
        
        assert response["messaging_product"] == "whatsapp"
        assert len(response["messages"]) == 1
        assert route.called

@pytest.mark.asyncio
async def test_send_instagram_message(mock_settings):
    # Mock IG Send
    with respx.mock(base_url="https://graph.facebook.com") as respx_mock:
        route = respx_mock.post("/v18.0/me/messages").mock(
            return_value=httpx.Response(200, json={"recipient_id": "123", "message_id": "mid.123"})
        )
        
        response = await meta_service.send_instagram_text("ig_user_1", "Hello IG")
        
        assert "message_id" in response
        assert route.called
