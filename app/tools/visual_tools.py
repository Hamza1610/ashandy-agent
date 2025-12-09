from langchain.tools import tool
from transformers import AutoProcessor, AutoModel
from PIL import Image
import requests
import torch
import logging
from io import BytesIO

logger = logging.getLogger(__name__)

# Initialize DINOv2 (using HuggingFace version as proxy for DINO if DINOv3 not immediately avail via standard HF AutoModel, 
# usually dinov2-base is 768 dim, compatible with architecture)
# Lazy loading to avoid startup cost
dino_processor = None
dino_model = None

def load_models():
    global dino_processor, dino_model
    if not dino_model:
        try:
            logger.info("Loading DINOv2 model via Transformers...")
            dino_processor = AutoProcessor.from_pretrained("facebook/dinov2-base")
            dino_model = AutoModel.from_pretrained("facebook/dinov2-base")
            logging.info("DINOv2 loaded.")
        except Exception as e:
            logger.error(f"Failed to load DINOv2: {e}")

@tool
async def process_image_for_search(image_url: str) -> list:
    """
    Download image and embed with DINO (768-dim).
    """
    load_models()
    
    if not dino_model or not dino_processor:
        return []
        
    try:
        # Download image
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content)).convert("RGB")
        
        # Process
        inputs = dino_processor(images=image, return_tensors="pt")
        with torch.no_grad():
            outputs = dino_model(**inputs)
        
        # Taking the [CLS] token embedding (first token for ViT-like) or pooler output
        last_hidden_states = outputs.last_hidden_state
        embedding = last_hidden_states[0][0].tolist() # Shape [1, 768] roughly
        
        return embedding
        
    except Exception as e:
        logger.error(f"Visual embedding failed: {e}")
        return []

