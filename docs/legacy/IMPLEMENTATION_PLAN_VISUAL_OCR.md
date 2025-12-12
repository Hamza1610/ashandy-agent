# Implementation Plan: Visual Text Extraction & Auto-Enrichment (Pinecone Only)

## Objective
Enable the agent to find products even if the database lacks images/descriptions by reading text from user-uploaded photos ("OCR"). Also, intelligently link these high-quality user images to the product in the Vector Database to improve future searches.

## 1. Safety First
- **No Write to POS:** We will NOT write to the PHPPOS SQL database.
- **Isolated Updates:** Enriched images will be stored in **Pinecone** (Vector DB) only.
- **Sanitization:** All images will be re-processed (PIL) before any storage logic.

## 2. Component Updates

### A. `visual_tools.py` Update
- **Modify `describe_image`:**
    - Update Prompt: Request JSON output with `detected_text`, `product_type`, `visual_description`, and `confidence`.
    - Function returns a `dict` (parsed JSON) instead of just a string.

### B. `main_workflow.py` Update
- **Update `visual_processing_node`:**
    1.  **Analyze Image:** Call `describe_image` -> Get `{text, description, confidence}`.
    2.  **Visual Search:** Call `process_image_for_search` -> Query Pinecone for visual matches.
    3.  **Text Hunt (The New Feature):**
        - If `detected_text` exists: Run a **Text Search** on Pinecone (`products_text` index) using the extracted text.
    4.  **Auto-Enrichment (The Learner):**
        - **Condition:**
            - `confidence > 0.95` (AI is sure).
            - `text_search` returns a **strong match** (Score > 0.9) for a product (e.g., "Ashandy Shea Butter").
            - The matched product currently has `image_source != 'official'` (or we just want to add a variant).
        - **Action:**
            - Save the user's image temporarily (processed).
            - **Upsert to Pinecone:** Update the product's vector (or add a new "sibling" vector) pointing to this image.
            - Metadata: `source='user_enriched'`, `parent_id=...`.

## 3. Execution Flow
1. User uploads photo of "Brand X Cream".
2. System sees it has no visual config for "Brand X Cream".
3. Llama Vision reads "Brand X Cream" on the jar.
4. System searches text DB -> Finds "Brand X Cream" (Price: 5000).
5. Agent says: "Found it! That's Brand X Cream."
6. (Background) System saves this visual embedding to Pinecone so next time, it finds it *visually* too.

## 4. Deliverables
- Updated `visual_tools.py`.
- Updated `visual_processing_node` logic (in `main_workflow.py`).
