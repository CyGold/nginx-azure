from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional

# Import our weather service module
from weather_service import get_current_weather, WeatherServiceError

app = FastAPI(
    title="Weather Alert API",
    description="An API to fetch current weather data and set up basic weather alerts.",
    version="1.0.0",
    contact={
        "name": "API Support",
        "url": "http://example.com/contact",
        "email": "support@example.com",
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
)

# Pydantic models for request and response validation

class WeatherData(BaseModel):
    city: str
    temperature: float
    description: str
    humidity: int
    wind_speed: float
    timestamp: int

class AlertConfig(BaseModel):
    city: str
    threshold_temp_high: Optional[float] = None
    threshold_temp_low: Optional[float] = None
    threshold_humidity_high: Optional[int] = None
    threshold_humidity_low: Optional[int] = None
    alert_message_high_temp: str = "High temperature alert!"
    alert_message_low_temp: str = "Low temperature alert!"
    alert_message_high_humidity: str = "High humidity alert!"
    alert_message_low_humidity: str = "Low humidity alert!"

class CurrentAlertStatus(BaseModel):
    city: str
    triggered_alerts: List[str] = []
    current_weather: WeatherData

# In-memory storage for alert configurations. For a real-world app, use a database.
alert_configurations = {}

@app.get("/")
def read_root():
    """
    Root endpoint for API health check.
    """
    return {"message": "Welcome to the Weather Alert API!"}

@app.get("/weather/{city}", response_model=WeatherData)
def get_weather_by_city(city: str):
    """
    Retrieves current weather data for a specified city.

    - **city**: The name of the city for which to fetch weather data.
    """
    try:
        weather_data = get_current_weather(city)
        if weather_data:
            # Pydantic model validation happens automatically here upon return
            return weather_data
        else:
            raise HTTPException(status_code=404, detail=f"Weather data not found for city: {city}")
    except WeatherServiceError as e:
        # Catching our custom service error and returning an appropriate HTTP error
        raise HTTPException(status_code=503, detail=f"Weather service unavailable or error: {e}")
    except Exception as e:
        # Catch any other unexpected errors
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")

@app.post("/alerts/config", response_model=AlertConfig)
def configure_alert(alert_config: AlertConfig):
    """
    Configures weather alerts for a specific city.

    You can set thresholds for high/low temperature and high/low humidity.
    When the current weather exceeds these thresholds, alerts will be triggered.
    """
    city = alert_config.city
    alert_configurations[city] = alert_config
    print(f"Alert configured for {city}: {alert_config.dict()}")
    return alert_config

@app.get("/alerts/status/{city}", response_model=CurrentAlertStatus)
def get_alert_status_for_city(city: str):
    """
    Checks the current alert status for a given city based on configured thresholds.
    """
    if city not in alert_configurations:
        raise HTTPException(status_code=404, detail=f"No alert configuration found for city: {city}")

    alert_config = alert_configurations[city]

    try:
        current_weather = get_current_weather(city)
        if not current_weather:
            raise HTTPException(status_code=404, detail=f"Could not retrieve current weather for {city} to check alerts.")

        # Convert timestamp to datetime object for potential future use (e.g., logging)
        # current_weather_obj = WeatherData(**current_weather) # Validate weather data
        # current_weather_obj.timestamp = datetime.fromtimestamp(current_weather_obj.timestamp)


        triggered_alerts = []
        weather_data_dict = current_weather # Using the dictionary directly

        # Check Temperature Alerts
        if alert_config.threshold_temp_high is not None and weather_data_dict["temperature"] > alert_config.threshold_temp_high:
            triggered_alerts.append(f"{alert_config.alert_message_high_temp} (Temp: {weather_data_dict['temperature']}°C)")
        if alert_config.threshold_temp_low is not None and weather_data_dict["temperature"] < alert_config.threshold_temp_low:
            triggered_alerts.append(f"{alert_config.alert_message_low_temp} (Temp: {weather_data_dict['temperature']}°C)")

        # Check Humidity Alerts
        if alert_config.threshold_humidity_high is not None and weather_data_dict["humidity"] > alert_config.threshold_humidity_high:
            triggered_alerts.append(f"{alert_config.alert_message_high_humidity} (Humidity: {weather_data_dict['humidity']}%)")
        if alert_config.threshold_humidity_low is not None and weather_data_dict["humidity"] < alert_config.threshold_humidity_low:
            triggered_alerts.append(f"{alert_config.alert_message_low_humidity} (Humidity: {weather_data_dict['humidity']}%)")

        return CurrentAlertStatus(
            city=city,
            triggered_alerts=triggered_alerts,
            current_weather=WeatherData(**current_weather) # Ensure response conforms to WeatherData model
        )

    except WeatherServiceError as e:
        raise HTTPException(status_code=503, detail=f"Weather service unavailable or error while checking alerts for {city}: {e}")
    except HTTPException as e:
        # Re-raise HTTPExceptions from get_current_weather or other parts
        raise e
    except Exception as e:
        print(f"Unexpected error checking alert status for {city}: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred while checking alerts for {city}.")

@app.delete("/alerts/config/{city}")
def delete_alert_config(city: str):
    """
    Deletes the alert configuration for a specific city.
    """
    if city in alert_configurations:
        del alert_configurations[city]
        return {"message": f"Alert configuration for {city} deleted successfully."}
    else:
        raise HTTPException(status_code=404, detail=f"No alert configuration found for city: {city}")


# Helper function to run the server (optional, for direct execution)
# To run from terminal: uvicorn main:app --reload
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)