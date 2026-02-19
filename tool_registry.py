import os
import importlib.util

# TOOL_REGISTRY to store the mapping of function names to their references
# TOOL_REGISTRY = {}

# Path to the functions folder
FUNCTIONS_FOLDER = os.path.join(os.path.dirname(__file__), 'VectorRoute-Tools', 'functions')

def update_tool_registry() -> dict:
    TOOL_REGISTRY = {}
    
    # Walk through the functions folder recursively
    for root, _, files in os.walk(FUNCTIONS_FOLDER):
        for filename in files:
            if filename.endswith('.py'):
                module_name = os.path.splitext(os.path.relpath(os.path.join(root, filename), FUNCTIONS_FOLDER))[0]
                module_name = module_name.replace(os.sep, '.')  # Convert path to module name
                module_path = os.path.join(root, filename)

                # Dynamically import the module
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Add all functions in the module to TOOL_REGISTRY
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if callable(attr):  # Check if the attribute is a function
                        TOOL_REGISTRY[attr_name] = attr

    print(f"Loaded tools: {list(TOOL_REGISTRY.keys())}")
    return TOOL_REGISTRY

# # Example: Print the TOOL_REGISTRY to verify
# if __name__ == "__main__":
#     print("TOOL_REGISTRY:", TOOL_REGISTRY)