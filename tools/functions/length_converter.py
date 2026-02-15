def length_converter(value:float, from_unit:str, to_unit:str) -> float:
    # Define conversion factors
    conversion_factors = {
        'm': 1.0,
        'km': 1000.0,
        'cm': 0.01,
        'mm': 0.001,
        'in': 0.0254,
        'ft': 0.3048,
        'yd': 0.9144,
    }
    
    # Check if the units are valid
    if from_unit not in conversion_factors or to_unit not in conversion_factors:
        raise ValueError("Invalid units provided.")
    
    # Convert the value to meters
    value_in_meters = value * conversion_factors[from_unit]
    
    # Convert the value from meters to the target unit
    converted_value = value_in_meters / conversion_factors[to_unit]
    
    return converted_value