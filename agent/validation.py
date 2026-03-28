import json
import inspect
from typing import Any

from pydantic import create_model, ValidationError


def _coerce_value(v: Any) -> Any:
    """Try to coerce a string into a native python type using json.loads
    and some fallbacks for numbers and booleans. Non-strings are returned as-is.
    """
    if not isinstance(v, str):
        return v

    s = v.strip()
    # try JSON first (handles lists, dicts, numbers, booleans, null)
    try:
        return json.loads(s)
    except Exception:
        pass

    # fallback: try ints and floats
    try:
        return int(s)
    except Exception:
        pass

    try:
        return float(s)
    except Exception:
        pass

    # boolean text
    lower = s.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False

    return v


def validate_and_coerce(arguments: dict, func: callable) -> dict:
    """Build a pydantic model from `func` parameter annotations and use it to
    coerce/validate `arguments`.

    - `arguments` is a mapping of name->value (often strings from user input).
    - `func` is the tool function; its signature annotations are used to
      construct the model types where available.

    Returns the dict of coerced values suitable for calling `func(**result)`.
    Raises ValueError on validation errors.
    """
    sig = inspect.signature(func)

    model_fields = {}
    for name, param in sig.parameters.items():
        # Skip *args/**kwargs
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue

        annotation = param.annotation if param.annotation is not inspect._empty else Any
        default = param.default if param.default is not inspect._empty else ...
        model_fields[name] = (annotation, default)

    Model = create_model("ToolArgsModel", **model_fields)

    coerced = {k: _coerce_value(v) for k, v in (arguments or {}).items()}

    try:
        m = Model(**coerced)
    except ValidationError as e:
        raise ValueError(e)

    return m.dict()
