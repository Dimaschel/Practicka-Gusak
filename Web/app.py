import os
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from flask import Flask, request, render_template
from bs4 import BeautifulSoup
import requests
import threading
import time
import schedule

app = Flask(__name__)

# Настройки базы данных
DATABASE_HOST = os.getenv('DATABASE_HOST', 'database')
CONN_STRING = f"dbname='postgres' user='postgres' password='postgres' host='{DATABASE_HOST}' port='5432'"

# Создаем пул соединений (5-20 соединений в пуле)
pool = SimpleConnectionPool(5, 20, CONN_STRING)

# Класс для работы с базой данных
class VacancyRepository:
    @staticmethod
    def save_vacancy(title, salary_text, requirements):
        conn = pool.getconn()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO vacancies (title, salary, requirements) VALUES (%s, %s, %s)",
                (title, salary_text, requirements)
            )
            conn.commit()
        finally:
            cursor.close()
            pool.putconn(conn)

    @staticmethod
    def clear_database():
        conn = pool.getconn()
        cursor = conn.cursor()
        try:
            cursor.execute("TRUNCATE TABLE vacancies")
            conn.commit()
        finally:
            cursor.close()
            pool.putconn(conn)
        print("База данных очищена")

    @staticmethod
    def get_vacancies(keyword=None, sort_order=None):
        conn = pool.getconn()
        cursor = conn.cursor()
        query = "SELECT * FROM vacancies"
        params = ()

        if keyword:
            query += " WHERE title ILIKE %s"
            params = ('%' + keyword + '%',)

        if sort_order == 'asc':
            query += " ORDER BY salary ASC NULLS LAST"
        elif sort_order == 'desc':
            query += " ORDER BY salary DESC NULLS LAST"

        cursor.execute(query, params)
        vacancies = cursor.fetchall()
        
        cursor.close()
        pool.putconn(conn)
        return vacancies

# Класс для работы с API hh.ru
class HHApiClient:
    BASE_URL = "https://api.hh.ru/vacancies"

    @staticmethod
    def fetch_vacancies(query, city=None, num_vacancies=50):
        params = {
            'text': query,
            'area': city if city else 1,
            'per_page': num_vacancies
        }
        response = requests.get(HHApiClient.BASE_URL, params=params)
        return response.json()['items'] if response.status_code == 200 else []

# Функция обработки данных вакансии
def extract_vacancy_data(vacancy):
    title = vacancy['name']
    salary = vacancy.get('salary', {'from': None, 'to': None})
    snippet = vacancy.get('snippet', {})
    requirements = snippet.get('requirement', 'Требования не указаны')
    requirements = BeautifulSoup(requirements, "html.parser").text if requirements else 'Требования не указаны'
    salary_text = 'Не указана' if not salary else f"от {salary['from']} до {salary['to']}"
    return title, salary_text, requirements

# Функция запуска очистки БД по расписанию
def run_scheduler():
    schedule.every(3).hours.do(VacancyRepository.clear_database)
    while True:
        schedule.run_pending()
        time.sleep(1)

# Роут главной страницы
@app.route('/', methods=['GET', 'POST'])
def index():
    vacancies = []
    if request.method == 'POST':
        query = request.form['query']
        city = request.form['city']
        num_vacancies = request.form.get('num_vacancies', default=50, type=int)

        vacancies = HHApiClient.fetch_vacancies(query, city, num_vacancies)

        for vacancy in vacancies:
            title, salary_text, requirements = extract_vacancy_data(vacancy)
            VacancyRepository.save_vacancy(title, salary_text, requirements)

    return render_template('index.html', vacancies=vacancies)

@app.route('/database', methods=['GET'])
def database():
    keyword = request.args.get('keyword')
    sort_order = request.args.get('sort')
    vacancies = VacancyRepository.get_vacancies(keyword, sort_order)
    return render_template('database.html', vacancies=vacancies)

if __name__ == '__main__':
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    app.run(host='0.0.0.0', port=5000)
