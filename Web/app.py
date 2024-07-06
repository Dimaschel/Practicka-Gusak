import os
import psycopg2
from flask import Flask, request, render_template
from bs4 import BeautifulSoup
import requests
import threading
import time
import schedule


app = Flask(__name__)

DATABASE_HOST = os.getenv('DATABASE_HOST', 'database')
conn_string = f"dbname='postgres' user='postgres' password='postgres' host='{DATABASE_HOST}' port='5432'"

def get_vacancies(query, city=None, num_vacancies=50):
    url = 'https://api.hh.ru/vacancies'
    params = {
        'text': query,
        'area': 1, 
        'per_page': num_vacancies,
        'area': city if city else 1  
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

def clear_database():
    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE vacancies")
    conn.commit()
    cursor.close()
    conn.close()
    print("бд очищена")

def run_scheduler():
    schedule.every(3).hours.do(clear_database)
    while True:
        schedule.run_pending()
        time.sleep(1)

@app.route('/', methods=['GET', 'POST'])
def index():
    vacancies = []
    if request.method == 'POST':
        query = request.form['query']
        city = request.form['city']
        num_vacancies = request.form.get('num_vacancies', default=50, type=int)
        vacancies = get_vacancies(query, city, num_vacancies)
        for vacancy in vacancies:
            save_vacancy_to_db(vacancy)
    return render_template('index.html', vacancies=vacancies)

@app.route('/database', methods=['GET'])
def database():
    keyword = request.args.get('keyword')
    sort_order = request.args.get('sort')

    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor()

    query = "SELECT * FROM vacancies"

    if keyword:
        query += " WHERE title ILIKE %s"
        params = ('%' + keyword + '%',)
    else:
        params = ()

    if sort_order == 'asc':
        query += " ORDER BY salary ASC NULLS LAST"
    elif sort_order == 'desc':
        query += " ORDER BY salary DESC NULLS LAST"

    cursor.execute(query, params)
    vacancies = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('database.html', vacancies=vacancies)


if __name__ == '__main__':
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    app.run(host='0.0.0.0', port=5000)