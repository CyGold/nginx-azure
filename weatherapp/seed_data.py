import psycopg2
import random
from faker import Faker
from datetime import datetime, timedelta

fake = Faker()

conn = psycopg2.connect(
    dbname="weatheralerts",
    user="alertuser",
    password="alertpass123",
    host="localhost"
)
cur = conn.cursor()

# Seed 500 alert configs
print("Seeding alert configs...")
cities = ['Lagos', 'Abuja', 'London', 'New York', 'Paris', 'Dubai', 'Tokyo', 'Cairo']
conditions = ['temp_above', 'temp_below', 'rain', 'wind_speed', 'humidity_above']

for _ in range(500):
    cur.execute("""
        INSERT INTO alert_configs (user_email, city, condition, threshold, active)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        fake.unique.email(),
        random.choice(cities),
        random.choice(conditions),
        round(random.uniform(10.0, 45.0), 2),
        random.choice([True, True, True, False])
    ))

conn.commit()

# Seed 50k alert logs
print("Seeding 50,000 alert logs...")
start_date = datetime.now() - timedelta(days=90)

for i in range(50000):
    triggered_at = start_date + timedelta(
        minutes=random.randint(0, 90 * 24 * 60)
    )
    cur.execute("""
        INSERT INTO alert_logs (config_id, triggered_at, weather_data, notification_sent)
        VALUES (%s, %s, %s, %s)
    """, (
        random.randint(1, 500),
        triggered_at,
        '{"temp": ' + str(round(random.uniform(15.0, 45.0), 1)) + ', "humidity": ' + str(random.randint(30, 95)) + '}',
        random.choice([True, False])
    ))

    if i % 5000 == 0:
        conn.commit()
        print(f"  {i}/50000 rows inserted...")

conn.commit()
cur.close()
conn.close()
print("Done — database seeded.")