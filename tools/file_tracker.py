import os
import json
import hashlib
from typing import Dict, Set, Tuple


class FileChangeTracker:
    """
    Tracks file changes in .json and .py files under VectorRoute-Tools.
    Uses file hashes to detect modifications.
    """
    
    def __init__(self, cache_file: str = ".tool_file_cache.json"):
        """
        Initialize the file change tracker.
        
        Args:
            cache_file: Path to the cache file storing file hashes
        """
        self.cache_file = os.path.join(os.getcwd(), cache_file)
        self.cache = self._load_cache()
        
    def _load_cache(self) -> Dict[str, str]:
        """Load the cache from disk."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Could not load cache file {self.cache_file}. Starting fresh.")
                return {}
        return {}
    
    def _save_cache(self):
        """Save the cache to disk."""
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)
    
    def _compute_file_hash(self, file_path: str) -> str:
        """
        Compute SHA256 hash of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Hexadecimal hash string
        """
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            print(f"Error computing hash for {file_path}: {e}")
            return ""
    
    def check_file_changes(self, 
                          capabilities_folder: str, 
                          functions_folder: str) -> Tuple[Set[str], Dict[str, str]]:
        """
        Check for file changes in capabilities and functions folders.
        
        Args:
            capabilities_folder: Path to capabilities folder (.json files)
            functions_folder: Path to functions folder (.py files)
            
        Returns:
            Tuple of (set of changed tool names, dict of all current file hashes)
        """
        changed_tools = set()
        current_hashes = {}
        
        # Track .json files in capabilities folder
        for root, _, files in os.walk(capabilities_folder):
            for filename in files:
                if filename.endswith('.json'):
                    file_path = os.path.join(root, filename)
                    current_hash = self._compute_file_hash(file_path)
                    current_hashes[file_path] = current_hash
                    
                    # Get tool name from filename (without extension)
                    tool_name = os.path.splitext(filename)[0]
                    
                    # Check if file is new or modified
                    if file_path not in self.cache or self.cache[file_path] != current_hash:
                        changed_tools.add(tool_name)
                        print(f"Detected change in capability: {filename}")
        
        # Track .py files in functions folder
        for root, _, files in os.walk(functions_folder):
            for filename in files:
                if filename.endswith('.py') and filename != '__init__.py':
                    file_path = os.path.join(root, filename)
                    current_hash = self._compute_file_hash(file_path)
                    current_hashes[file_path] = current_hash
                    
                    # Get tool name from filename (without extension)
                    tool_name = os.path.splitext(filename)[0]
                    
                    # Check if file is new or modified
                    if file_path not in self.cache or self.cache[file_path] != current_hash:
                        changed_tools.add(tool_name)
                        print(f"Detected change in function: {filename}")
        
        # Detect deleted files
        for cached_path in self.cache.keys():
            if cached_path not in current_hashes:
                if os.path.exists(cached_path):
                    # File still exists but wasn't walked (maybe outside tracked folders)
                    continue
                filename = os.path.basename(cached_path)
                tool_name = os.path.splitext(filename)[0]
                print(f"Detected deleted file: {filename}")
                changed_tools.add(tool_name)
        
        return changed_tools, current_hashes
    
    def update_cache(self, current_hashes: Dict[str, str]):
        """
        Update the cache with current file hashes.
        
        Args:
            current_hashes: Dictionary of file paths to their current hashes
        """
        self.cache = current_hashes
        self._save_cache()
        print(f"Cache updated with {len(current_hashes)} files")
    
    def get_changed_tools(self) -> Set[str]:
        """
        Get the list of tools with changes since last cache update.
        
        Returns:
            Set of tool names with changes
        """
        capabilities_folder = os.path.join(os.getcwd(), "VectorRoute-Tools", "capabilities")
        functions_folder = os.path.join(os.getcwd(), "VectorRoute-Tools", "functions")
        
        changed_tools, _ = self.check_file_changes(capabilities_folder, functions_folder)
        return changed_tools
    
    def mark_as_processed(self):
        """
        Mark current state as processed by updating the cache.
        Call this after successfully computing embeddings.
        """
        capabilities_folder = os.path.join(os.getcwd(), "VectorRoute-Tools", "capabilities")
        functions_folder = os.path.join(os.getcwd(), "VectorRoute-Tools", "functions")
        
        _, current_hashes = self.check_file_changes(capabilities_folder, functions_folder)
        self.update_cache(current_hashes)
    
    def clear_cache(self):
        """Clear the cache file. This will cause all tools to be reprocessed."""
        self.cache = {}
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
        print("Cache cleared. All tools will be reprocessed.")
