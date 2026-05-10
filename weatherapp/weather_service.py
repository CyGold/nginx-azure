import requests
import os
from dotenv import load_dotenv
from typing import Dict, Any, Optional

# Load environment variables from .env file
load_dotenv()

OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")
BASE_URL = "http://api.openweathermap.org/data/2.5/weather"

class WeatherServiceError(Exception):
    """Custom exception for weather service errors."""
    pass

def get_current_weather(city: str) -> Optional[Dict[str, Any]]:
    """
    Fetches current weather data for a given city from OpenWeatherMap.

    Args:
        city: The name of the city.

    Returns:
        A dictionary containing weather data if successful, None otherwise.
        Raises WeatherServiceError on API request failure or invalid response.
    """
    if not OPENWEATHERMAP_API_KEY:
        raise WeatherServiceError("OpenWeatherMap API key not found. Please set OPENWEATHERMAP_API_KEY in your .env file.")

    params = {
        "q": city,
        "appid": OPENWEATHERMAP_API_KEY,
        "units": "metric"  # Use metric units (Celsius)
    }

    try:
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        data = response.json()

        # Basic validation of the response structure
        if "weather" in data and data["weather"]:
            return {
                "city": data.get("name"),
                "temperature": data["main"].get("temp"),
                "description": data["weather"][0].get("description"),
                "humidity": data["main"].get("humidity"),
                "wind_speed": data["wind"].get("speed"),
                "timestamp": data.get("dt") # Unix timestamp
            }
        else:
            print(f"Warning: Unexpected response structure from OpenWeatherMap for {city}: {data}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather for {city}: {e}")
        # Optionally log the detailed error response if available
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status code: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        raise WeatherServiceError(f"Failed to fetch weather data for {city}.") from e
    except Exception as e:
        print(f"An unexpected error occurred while processing weather data for {city}: {e}")
        raise WeatherServiceError(f"An unexpected error occurred processing weather data for {city}.") from e

# Example usage (optional, for testing)
if __name__ == "__main__":
    try:
        weather_data = get_current_weather("London")
        if weather_data:
            print("Current Weather for London:")
            for key, value in weather_data.items():
                print(f"- {key.capitalize()}: {value}")
        else:
            print("Could not retrieve weather data for London.")
        # Example of an error case (invalid city)
        # weather_data_invalid = get_current_weather("InvalidCityName123")
        # if weather_data_invalid:
        #     print("Current Weather for InvalidCityName123:")
        #     for key, value in weather_data_invalid.items():
        #         print(f"- {key.capitalize()}: {value}")
        # else:
        #     print("Could not retrieve weather data for InvalidCityName123 (as expected).")

    except WeatherServiceError as e:
        print(f"Error: {e}")