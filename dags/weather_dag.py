from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from datetime import datetime
import requests
import psycopg2
import os
import logging
import traceback


# Setup logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
API_KEY = os.getenv("OPENWEATHER_API_KEY")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")


MOROCCO_CITIES = [
    {"name": "Casablanca", "lat": 33.5731, "lon": -7.5898},
    {"name": "Rabat", "lat": 34.0209, "lon": -6.8416},
    {"name": "Fes", "lat": 34.0331, "lon": -5.0003},
    {"name": "Marrakech", "lat": 31.6295, "lon": -7.9811},
    {"name": "Tangier", "lat": 35.7595, "lon": -5.8339},
    {"name": "Agadir", "lat": 30.4278, "lon": -9.5981},
    {"name": "Meknes", "lat": 33.8955, "lon": -5.5473},
    {"name": "Oujda", "lat": 34.6814, "lon": -1.9086},
    {"name": "Kenitra", "lat": 34.261, "lon": -6.5802},
    {"name": "Tétouan", "lat": 35.5785, "lon": -5.3684}
]


def fetch_weather(lat, lon, city_name):
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
    response = requests.get(url)

    if response.status_code != 200:
        logging.error(f"Failed to fetch weather for {city_name}: {response.text}")
        raise Exception(f"API call failed with status {response.status_code}")

    data = response.json()

    weather = {
        "city": city_name,
        "temperature": data["main"]["temp"],
        "humidity": data["main"]["humidity"],
        "description": data["weather"][0]["description"],
        "date": datetime.utcnow().date()
    }
    return weather


def store_weather_data():
    try:
        conn = psycopg2.connect(
            host="postgres",
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD
        )
        conn.autocommit = True
        cur = conn.cursor()

        for city in MOROCCO_CITIES:
            try:
                weather = fetch_weather(city["lat"], city["lon"], city["name"])
                logging.info(f"Fetched weather for {city['name']}: {weather}")

                insert_query = """
                INSERT INTO weather (city, temperature, humidity, weather_description, date)
                VALUES (%s, %s, %s, %s, %s)
                """
                cur.execute(insert_query, (
                    weather["city"],
                    weather["temperature"],
                    weather["humidity"],
                    weather["description"],
                    weather["date"]
                ))

                logging.info(f"Inserted weather for {city['name']} successfully.")

            except Exception as city_error:
                logging.error(f"Error processing city {city['name']}: {city_error}")
                logging.error(traceback.format_exc())

        cur.close()
        conn.close()

    except Exception as db_error:
        logging.error("Database connection or processing failed.")
        logging.error(traceback.format_exc())
        raise  # Important: Raise so Airflow knows the task failed


default_args = {
    'owner': 'weather_airflow',
    'depends_on_past': False,
    'retries': 1
}

with DAG(
    'morocco_weather_etl',
    default_args=default_args,
    description='Daily weather pipeline for Moroccan cities',
    schedule_interval='@daily',
    start_date=datetime(2025, 5, 6),
    catchup=False,
) as dag:

    start = EmptyOperator(task_id="start_dag")

    pipeline_work = PythonOperator(
        task_id="weather_etl",
        python_callable=store_weather_data
    )

    end = EmptyOperator(task_id="end_dag")

    start >> pipeline_work >> end
