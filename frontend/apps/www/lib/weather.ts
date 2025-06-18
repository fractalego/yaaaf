// Map weather code to description
const weatherCodes: Record<number, string> = {
  0: "Clear sky",
  1: "Mainly clear",
  2: "Partly cloudy",
  3: "Overcast",
  45: "Foggy",
  48: "Depositing rime fog",
  51: "Light drizzle",
  53: "Moderate drizzle",
  55: "Dense drizzle",
  61: "Slight rain",
  63: "Moderate rain",
  65: "Heavy rain",
  71: "Slight snow",
  73: "Moderate snow",
  75: "Heavy snow",
  77: "Snow grains",
  80: "Slight rain showers",
  81: "Moderate rain showers",
  82: "Violent rain showers",
  85: "Slight snow showers",
  86: "Heavy snow showers",
  95: "Thunderstorm",
  96: "Thunderstorm with slight hail",
  99: "Thunderstorm with heavy hail",
}

interface Coordinates {
  lat: number
  lon: number
  name: string
  country: string
}

interface WeatherData {
  location: string
  temperature: string
  feelsLike: string
  humidity: string
  windSpeed: string
  precipitation: string
  conditions: string
}

export async function getCoordinates(location: string): Promise<Coordinates> {
  const response = await fetch(
    `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(
      location
    )}&count=1&language=en&format=json`
  )
  const data = await response.json()
  if (!data.results?.[0]) {
    throw new Error(`Location not found: ${location}`)
  }
  return {
    lat: data.results[0].latitude,
    lon: data.results[0].longitude,
    name: data.results[0].name,
    country: data.results[0].country,
  }
}

export async function getWeather(location: string): Promise<WeatherData> {
  // Get coordinates for the location
  const coords = await getCoordinates(location)

  // Fetch weather data
  const weatherResponse = await fetch(
    `https://api.open-meteo.com/v1/forecast?latitude=${coords.lat}&longitude=${coords.lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&timezone=auto`
  )
  const weatherData = await weatherResponse.json()

  const current = weatherData.current
  return {
    location: `${coords.name}, ${coords.country}`,
    temperature: `${current.temperature_2m}°C`,
    feelsLike: `${current.apparent_temperature}°C`,
    humidity: `${current.relative_humidity_2m}%`,
    windSpeed: `${current.wind_speed_10m} km/h`,
    precipitation: `${current.precipitation} mm`,
    conditions: weatherCodes[current.weather_code] || "Unknown",
  }
}
