#!/usr/bin/env python3
"""
Quick test script to verify file change tracking and incremental embedding.
Run this script twice to see the caching in action.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tool_utils.file_tracker import FileChangeTracker

def test_file_tracker():
    """Test the file change tracker."""
    print("=" * 70)
    print("Testing File Change Tracker")
    print("=" * 70)
    
    # Initialize tracker
    tracker = FileChangeTracker()
    
    # Get changed tools
    changed_tools = tracker.get_changed_tools()
    
    print(f"\nTotal tools with changes: {len(changed_tools)}")
    
    if changed_tools:
        print("\nChanged tools:")
        for i, tool_name in enumerate(sorted(changed_tools), 1):
            print(f"  {i}. {tool_name}")
    else:
        print("\nNo changes detected.")
        print("This is expected on subsequent runs after marking as processed.")
    
    # Show cache file status
    cache_file = os.path.join(os.getcwd(), ".tool_file_cache.json")
    if os.path.exists(cache_file):
        import json
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        print(f"\nCache file exists with {len(cache_data)} entries")
    else:
        print("\nCache file does not exist (first run)")
    
    return tracker, changed_tools

def test_embedding_cache():
    """Check embedding cache status."""
    print("\n" + "=" * 70)
    print("Checking Embedding Cache")
    print("=" * 70)
    
    cache_file = os.path.join(os.getcwd(), ".tool_embeddings_cache.json")
    
    if os.path.exists(cache_file):
        import json
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            print(f"\nEmbedding cache exists with {len(cache_data)} tools")
            
            # Show first few cached tools
            if cache_data:
                print("\nSample cached tools:")
                for i, item in enumerate(cache_data[:5], 1):
                    print(f"  {i}. {item.get('name', 'unknown')}")
                if len(cache_data) > 5:
                    print(f"  ... and {len(cache_data) - 5} more")
        except json.JSONDecodeError:
            print("\nEmbedding cache file is corrupted")
    else:
        print("\nEmbedding cache does not exist")
        print("Run vr_batch.py or incremental_load_example.py to create it")

def main():
    """Main test function."""
    print("\n" + "=" * 70)
    print("VectorRoute Incremental Embedding Test")
    print("=" * 70)
    
    # Test file tracker
    tracker, changed_tools = test_file_tracker()
    
    # Test embedding cache
    test_embedding_cache()
    
    # Provide guidance
    print("\n" + "=" * 70)
    print("Next Steps")
    print("=" * 70)
    
    if changed_tools:
        print("\n1. Run the following to compute embeddings for changed tools:")
        print("   python incremental_load_example.py")
        print("\n2. Or run your batch processor:")
        print("   python vr_batch.py")
    else:
        print("\n✓ No changes detected. Your embeddings are up to date!")
        print("\nTo test the change detection:")
        print("1. Modify a .json file in VectorRoute-Tools/capabilities/")
        print("2. Or modify a .py file in VectorRoute-Tools/functions/")
        print("3. Run this test script again")
    
    print("\n" + "=" * 70)
    print("Cache Management")
    print("=" * 70)
    print("\nTo force recomputation of all embeddings:")
    print("  python -c 'from tool_utils.file_tracker import FileChangeTracker; FileChangeTracker().clear_cache()'")
    print("\nOr manually delete:")
    print("  rm .tool_file_cache.json .tool_embeddings_cache.json")
    print()

if __name__ == "__main__":
    main()
