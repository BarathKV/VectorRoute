import os
import importlib.util

# TOOL_REGISTRY to store the mapping of function names to their references
# TOOL_REGISTRY = {}

# Path to the functions folder
FUNCTIONS_FOLDER = os.path.join(os.path.dirname(__file__), 'functions')

def update_tool_registry()->dict:
    TOOL_REGISTRY = {}
    # Dynamically load all Python files in the functions folder
    for filename in os.listdir(FUNCTIONS_FOLDER):
        if filename.endswith('.py'):
            module_name = filename[:-3]  # Remove the .py extension
            module_path = os.path.join(FUNCTIONS_FOLDER, filename)

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