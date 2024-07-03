import os
import psycopg2
from bs4 import BeautifulSoup
import requests

DATABASE_HOST = os.getenv('DATABASE_HOST', 'database')
conn_string = f"dbname='postgres' user='postgres' password='postgres' host='{DATABASE_HOST}' port='5432'"

conn = psycopg2.connect(conn_string)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS vacancies (
        id SERIAL PRIMARY KEY,
        title VARCHAR(255),
        salary VARCHAR(255),
        requirements TEXT
    )
""")
conn.commit()

url = 'https://api.hh.ru/vacancies'
params = {
    'text': 'Python',
    'area': 1,
    'per_page': 50
}

response = requests.get(url, params=params)

if response.status_code == 200:
    vacancies = response.json()
    for vacancy in vacancies['items']:
        title = vacancy['name']
        salary = vacancy.get('salary', {'from': None, 'to': None})
        snippet = vacancy.get('snippet', {})
        requirements = snippet.get('requirement', 'Требования не указаны')
        if requirements:
            requirements = BeautifulSoup(requirements, "html.parser").text
        else:
            requirements = 'Требования не указаны'
        salary_text = 'Не указана' if not salary else f"от {salary['from']} до {salary['to']}"

        cursor.execute(
            "INSERT INTO vacancies (title, salary, requirements) VALUES (%s, %s, %s)",
            (title, salary_text, requirements)
        )
    conn.commit()
else:
    print(f"Ошибка при запросе: {response.status_code} - {response.text}")

cursor.close()
conn.close()
