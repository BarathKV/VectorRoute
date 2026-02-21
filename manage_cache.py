#!/usr/bin/env python3
"""
Utility script for managing VectorRoute caches.
"""

import os
import sys
import argparse
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tool_utils.file_tracker import FileChangeTracker

def clear_all_caches():
    """Clear all cache files."""
    tracker = FileChangeTracker()
    tracker.clear_cache()
    
    # Also clear embeddings cache
    embeddings_cache = os.path.join(os.getcwd(), ".tool_embeddings_cache.json")
    if os.path.exists(embeddings_cache):
        os.remove(embeddings_cache)
        print(f"Removed: {embeddings_cache}")
    
    print("\nAll caches cleared successfully!")

def show_cache_info():
    """Display information about current caches."""
    print("=" * 70)
    print("Cache Information")
    print("=" * 70)
    
    # File tracker cache
    file_cache = os.path.join(os.getcwd(), ".tool_file_cache.json")
    if os.path.exists(file_cache):
        with open(file_cache, 'r') as f:
            file_data = json.load(f)
        print(f"\n📁 File Change Cache: {file_cache}")
        print(f"   Tracking {len(file_data)} files")
        
        # Show file types
        json_files = sum(1 for f in file_data.keys() if f.endswith('.json'))
        py_files = sum(1 for f in file_data.keys() if f.endswith('.py'))
        print(f"   - {json_files} .json files (capabilities)")
        print(f"   - {py_files} .py files (functions)")
    else:
        print(f"\n📁 File Change Cache: Not found")
    
    # Embeddings cache
    embeddings_cache = os.path.join(os.getcwd(), ".tool_embeddings_cache.json")
    if os.path.exists(embeddings_cache):
        with open(embeddings_cache, 'r') as f:
            embeddings_data = json.load(f)
        print(f"\n🧮 Embeddings Cache: {embeddings_cache}")
        print(f"   Cached embeddings for {len(embeddings_data)} tools")
        
        # Calculate size
        file_size = os.path.getsize(embeddings_cache)
        size_mb = file_size / (1024 * 1024)
        print(f"   File size: {size_mb:.2f} MB")
    else:
        print(f"\n🧮 Embeddings Cache: Not found")
    
    print()

def show_changes():
    """Show what tools have changed."""
    tracker = FileChangeTracker()
    changed_tools = tracker.get_changed_tools()
    
    print("=" * 70)
    print("Changed Tools")
    print("=" * 70)
    
    if changed_tools:
        print(f"\nFound {len(changed_tools)} tools with changes:\n")
        for i, tool_name in enumerate(sorted(changed_tools), 1):
            print(f"  {i}. {tool_name}")
    else:
        print("\n✓ No changes detected")
    
    print()

def main():
    parser = argparse.ArgumentParser(
        description="Manage VectorRoute cache files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --info              Show cache information
  %(prog)s --changes           Show tools with changes
  %(prog)s --clear             Clear all caches
  %(prog)s --clear --info      Clear caches and show info
        """
    )
    
    parser.add_argument(
        '--info',
        action='store_true',
        help='Show information about current caches'
    )
    
    parser.add_argument(
        '--changes',
        action='store_true',
        help='Show which tools have changed'
    )
    
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear all cache files'
    )
    
    args = parser.parse_args()
    
    # If no arguments provided, show help
    if not any([args.info, args.changes, args.clear]):
        parser.print_help()
        return
    
    # Execute requested actions
    if args.clear:
        clear_all_caches()
        print()
    
    if args.changes:
        show_changes()
    
    if args.info:
        show_cache_info()

if __name__ == "__main__":
    main()
