import os
import psycopg2
from flask import Flask, request, render_template
from bs4 import BeautifulSoup
import requests

app = Flask(__name__)

DATABASE_HOST = os.getenv('DATABASE_HOST', 'database')
conn_string = f"dbname='postgres' user='postgres' password='postgres' host='{DATABASE_HOST}' port='5432'"

def get_vacancies(query):
    url = 'https://api.hh.ru/vacancies'
    params = {
        'text': query,
        'area': 1,
        'per_page': 50
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()['items']
    else:
        return []

def save_vacancy_to_db(vacancy):
    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor()
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
    cursor.close()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    vacancies = []
    if request.method == 'POST':
        query = request.form['query']
        vacancies = get_vacancies(query)
        for vacancy in vacancies:
            save_vacancy_to_db(vacancy)
    return render_template('index.html', vacancies=vacancies)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
