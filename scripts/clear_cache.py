"""
Script to clear Python bytecode cache and restart clean.
Run this when you need to force Python to reload all modules.
"""
import os
import shutil
from pathlib import Path

def clear_pycache(directory):
    """Recursively remove all __pycache__ directories."""
    count = 0
    for root, dirs, files in os.walk(directory):
        if '__pycache__' in dirs:
            pycache_path = os.path.join(root, '__pycache__')
            print(f"Removing: {pycache_path}")
            shutil.rmtree(pycache_path)
            count += 1
    return count

def clear_pyc_files(directory):
    """Remove all .pyc files."""
    count = 0
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.pyc'):
                file_path = os.path.join(root, file)
                print(f"Removing: {file_path}")
                os.remove(file_path)
                count += 1
    return count

if __name__ == "__main__":
    print("🧹 Clearing Python bytecode cache...\n")
    
    base_dir = Path(__file__).parent
    
    # Clear __pycache__ directories
    pycache_count = clear_pycache(base_dir)
    print(f"\n✅ Removed {pycache_count} __pycache__ directories")
    
    # Clear .pyc files
    pyc_count = clear_pyc_files(base_dir)
    print(f"✅ Removed {pyc_count} .pyc files")
    
    print("\n🎉 Cache cleared! Restart your server now:")
    print("   uvicorn app.main:app --reload --env-file .env")
