def calculate_bmi(weight_kg: float, height_cm: float):
    """
    Calculate Body Mass Index (BMI).
    BMI = weight (kg) / (height (m))^2
    """
    height_m = height_cm / 100

    if height_m <= 0:
        raise ValueError("Height must be greater than zero")

    bmi = weight_kg / (height_m ** 2)

    if bmi < 18.5:
        category = "Underweight"
    elif bmi < 25:
        category = "Normal weight"
    elif bmi < 30:
        category = "Overweight"
    else:
        category = "Obese"

    return {
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "bmi": round(bmi, 2),
        "category": category
    }
