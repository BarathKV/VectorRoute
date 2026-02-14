import random

def get_weather(city: str) -> str:
    temperature = random.randint(22, 30)
    return f"The weather in {city} is sunny and {temperature}°C."