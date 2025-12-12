# Implementation Plan: Instagram Inventory Sync

## Objective
Enable the system to automatically enrich its product inventory by analyzing the brand's Instagram posts.
1. Fetch Instagram posts (Images + Captions).
2. Analyze them using Llama 4 Vision to identify if they are products.
3. Extract Name, Price, and Description.
4. Check if the product already exists in the main PHPPOS inventory (to avoid duplicates).
5. detailed Implementation steps.

## Components

### 1. `MetaService` Update (`app/services/meta_service.py`)
Add functionality to fetch the user's media.
- `get_instagram_posts(limit=10)`: Fetches recent media objects (ID, Caption, Media URL, Permalink).

### 2. `InstagramExtractionTool` (`app/tools/instagram_tools.py`)
A new module containing the extraction logic.
- `analyze_instagram_post(image_url, caption)`:
    - Uses Llama 4 Vision.
    - Prompt: "Analyze this image and caption. Is this a product for sale? If yes, extract: Name, Price (in Naira), Description. Return JSON."
    - Returns structured data or `None`.

### 3. Ingestion Script (`scripts/ingest_instagram.py`)
The main driver script.
- Connects to Pinecone.
- connect to Vector Store.
- Loop:
    - `posts = meta_service.get_instagram_posts()`
    - For each post:
        - `data = analyze_instagram_post(post)`
        - If `data`:
            - check duplication against PHPPOS index (Pinecone Query).
            - If unique: **Upsert to Pinecone** with metadata `source='instagram'`.

### 4. `product_tools.py` Update
- Ensure `search_products` queries include items where `source='instagram'`.

## Execution Plan
1.  **Modify `MetaService`** (Add `get_instagram_posts`).
2.  **Create `app/tools/instagram_tools.py`** (The Vision Logic).
3.  **Create `scripts/ingest_instagram.py`** (The Worker).
4.  **Test** by simulating an Instagram run.
