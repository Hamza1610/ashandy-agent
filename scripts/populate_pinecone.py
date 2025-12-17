"""
Script to populate Pinecone with skincare products from Excel file.

Usage:
    python scripts/populate_pinecone.py

Requirements:
    - pandas, openpyxl (for Excel reading)
    - pinecone, sentence-transformers (for Pinecone)
    - PINECONE_API_KEY in .env
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
EXCEL_FILE = project_root / "docs" / "items_export.xlsx"
INDEX_NAME = os.getenv("PINECONE_INDEX_PRODUCTS_TEXT", "ashandy-products-text")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # 384 dimensions


def load_and_clean_data(filepath: Path) -> pd.DataFrame:
    """Load Excel file and clean data."""
    logger.info(f"Loading data from {filepath}")
    
    df = pd.read_excel(filepath)
    logger.info(f"Loaded {len(df)} raw items")
    
    # Clean: Remove items with 0 or null selling price
    df = df[df['Selling Price'].notna() & (df['Selling Price'] > 0)]
    logger.info(f"After removing 0/null price items: {len(df)} items")
    
    # Clean: Remove inactive items if column exists
    if 'Inactive' in df.columns:
        # Keep items where Inactive is not 'y' or is NaN
        df = df[(df['Inactive'] != 'y') | (df['Inactive'].isna())]
        logger.info(f"After removing inactive items: {len(df)} items")
    
    # Select and rename relevant columns
    df = df[['Item Id', 'Item Name', 'Selling Price', 'Category', 'Description', 'Quantity']].copy()
    df.columns = ['id', 'name', 'price', 'category', 'description', 'quantity']
    
    # Fill NaN descriptions with empty string
    df['description'] = df['description'].fillna('')
    df['quantity'] = df['quantity'].fillna(0).astype(int)
    
    # Create searchable text for embedding
    df['search_text'] = df.apply(
        lambda row: f"{row['name']} {row['description']} {row['category']}".strip(),
        axis=1
    )
    
    return df


def create_pinecone_index(pc: Pinecone, index_name: str, dimension: int = 384):
    """Create Pinecone index if it doesn't exist."""
    existing_indexes = [idx.name for idx in pc.list_indexes()]
    
    if index_name in existing_indexes:
        logger.info(f"Index '{index_name}' already exists")
        # Delete and recreate to ensure clean state
        logger.info(f"Deleting existing index to refresh data...")
        pc.delete_index(index_name)
        time.sleep(2)
    
    logger.info(f"Creating index '{index_name}'...")
    pc.create_index(
        name=index_name,
        dimension=dimension,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )
    
    # Wait for index to be ready
    while not pc.describe_index(index_name).status['ready']:
        logger.info("Waiting for index to be ready...")
        time.sleep(2)
    
    logger.info(f"Index '{index_name}' is ready!")


def populate_pinecone(df: pd.DataFrame, pc: Pinecone, index_name: str, model: SentenceTransformer):
    """Embed products and upsert to Pinecone."""
    index = pc.Index(index_name)
    
    # Process in batches
    batch_size = 100
    total_upserted = 0
    
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i+batch_size]
        
        # Generate embeddings
        texts = batch['search_text'].tolist()
        embeddings = model.encode(texts).tolist()
        
        # Prepare vectors for upsert
        vectors = []
        for idx, (_, row) in enumerate(batch.iterrows()):
            vectors.append({
                'id': str(row['id']),
                'values': embeddings[idx],
                'metadata': {
                    'name': row['name'],
                    'price': float(row['price']),
                    'category': row['category'],
                    'description': row['description'],
                    'quantity': int(row['quantity']),
                    'source': 'phppos_export'
                }
            })
        
        # Upsert to Pinecone
        index.upsert(vectors=vectors)
        total_upserted += len(vectors)
        logger.info(f"Upserted batch {i//batch_size + 1}: {total_upserted}/{len(df)} items")
    
    return total_upserted


def main():
    """Main function to populate Pinecone."""
    # Check API key
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        logger.error("PINECONE_API_KEY not found in environment. Please set it in .env")
        sys.exit(1)
    
    # Check Excel file
    if not EXCEL_FILE.exists():
        logger.error(f"Excel file not found: {EXCEL_FILE}")
        sys.exit(1)
    
    # Initialize components
    logger.info("Initializing Pinecone client...")
    pc = Pinecone(api_key=api_key)
    
    logger.info(f"Loading embedding model: {EMBEDDING_MODEL}...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    dimension = model.get_sentence_embedding_dimension()
    logger.info(f"Model loaded. Embedding dimension: {dimension}")
    
    # Load and clean data
    df = load_and_clean_data(EXCEL_FILE)
    
    if len(df) == 0:
        logger.error("No valid products found after cleaning!")
        sys.exit(1)
    
    # Show sample data
    logger.info("\n=== Sample Data ===")
    for _, row in df.head(5).iterrows():
        logger.info(f"  - {row['name']}: ₦{row['price']:,.0f}")
    
    # Confirm before proceeding
    logger.info(f"\n📦 Ready to populate Pinecone with {len(df)} products")
    logger.info(f"   Index: {INDEX_NAME}")
    logger.info(f"   Dimension: {dimension}")
    
    # Create/refresh index
    create_pinecone_index(pc, INDEX_NAME, dimension)
    
    # Populate
    logger.info("\n🚀 Starting Pinecone population...")
    total = populate_pinecone(df, pc, INDEX_NAME, model)
    
    logger.info(f"\n✅ SUCCESS! Populated {total} products into Pinecone index '{INDEX_NAME}'")
    logger.info("You can now use semantic search for product queries!")


if __name__ == "__main__":
    main()
