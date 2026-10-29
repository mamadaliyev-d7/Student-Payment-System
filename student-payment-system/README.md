# Учёт учеников, оплат и задолженностей

Веб-приложение для администрации учебного центра: список учеников, ежемесячные оплаты и должники за любой месяц.
Бэкенд — FastAPI + SQLAlchemy + SQLite, интерфейс — HTML/CSS/JavaScript без внешних зависимостей
(работает без интернета, платных сервисов и API-ключей).

## 1. Назначение и основные функции

- **Ученики**: создание, просмотр, изменение, удаление (с подтверждением), поиск по имени и телефону, фильтр по группе.
- **Оплаты**: внесение оплаты (ученик, сумма, дата), история оплат ученика, фильтр по месяцу.
- **Должники**: список за выбранный месяц с остатком долга и итоговой суммой.
- **Дашборд**: число учеников, число должников, общая задолженность и сумма полученных платежей за месяц.
- Интерфейс адаптирован под смартфоны, планшеты и компьютеры; все тексты — на русском, суммы — в узбекских сумах (UZS) с разделителями тысяч.
- Автоматическая документация API (Swagger UI) и автотесты (pytest).

### Принятые правила (важно знать)

| Правило | Как работает |
|---|---|
| Формула долга | `долг = max(месячная стоимость − сумма оплат за месяц, 0)` |
| **Какая стоимость берётся в расчёт** | **Всегда действующая (текущая) месячная стоимость ученика.** Если стоимость изменили, отчёты за прошлые месяцы пересчитываются по новой стоимости. История стоимости не хранится. |
| К какому месяцу относится оплата | К календарному месяцу её даты (`payment_date`). Оплата от 31.10 учитывается в октябре, от 01.11 — в ноябре. |
| Должник | Ученик, у которого сумма оплат за месяц меньше стоимости (долг > 0). Переплата долга не создаёт и в следующий месяц не переносится. |
| Ученик со стоимостью 0 | Допустим (например, грант), должником не бывает. |
| Суммы | Целые числа в сумах (без тийинов) — так нет ошибок округления. Максимум — 1 000 000 000 000. |
| Удаление ученика | Вместе с учеником **удаляются все его оплаты** (в интерфейсе об этом предупреждают с указанием числа и суммы оплат). Идентификаторы удалённых учеников повторно не выдаются. |
| Дата оплаты | Формат `ГГГГ-ММ-ДД`. Если не передана — берётся текущая дата сервера. Допустимы годы 2000–2100. |
| Параметр `month` | Строго `ГГГГ-ММ` (годы 2000–2100). Для `/debtors` и `/dashboard` обязателен. |

## 2. Требования

- **Python 3.10 или новее** (проверить: `python --version`). Скачать: https://www.python.org/downloads/
  При установке в Windows отметьте «Add python.exe to PATH».
- Интернет нужен только один раз — чтобы скачать зависимости через `pip`.
- Современный браузер (Chrome, Edge, Firefox, Safari).

## 3. Запуск в Windows PowerShell (с нуля)

Откройте PowerShell, перейдите в папку проекта и выполните:

```powershell
cd путь\к\student-payment-system

# 1. Виртуальное окружение
py -m venv .venv

# 2. Активация окружения
.\.venv\Scripts\Activate.ps1

# 3. Зависимости
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Запуск сервера
uvicorn app.main:app --reload
```

Если PowerShell пишет, что выполнение скриптов запрещено, разрешите его только для текущего окна и повторите активацию:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Если команды `py` нет, используйте `python -m venv .venv`.

## 4. Запуск в macOS / Linux

```bash
cd путь/к/student-payment-system

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

uvicorn app.main:app --reload
```

## 5. Адреса после запуска

| Что | Адрес |
|---|---|
| Веб-интерфейс | http://127.0.0.1:8000/ |
| Swagger UI (интерактивная документация API) | http://127.0.0.1:8000/docs |
| ReDoc | http://127.0.0.1:8000/redoc |

Остановить сервер: `Ctrl + C`. Флаг `--reload` перезапускает сервер при изменении кода (нужен при разработке).
Чтобы открыть приложение с телефона в той же Wi-Fi сети, запустите `uvicorn app.main:app --host 0.0.0.0` и откройте
`http://<IP-компьютера>:8000/`. Встроенной авторизации нет, поэтому не выставляйте приложение в открытый интернет.

## 6. Структура проекта

```text
student-payment-system/
├── app/
│   ├── main.py            # приложение FastAPI, подключение роутеров и статики
│   ├── database.py        # движок SQLite, сессии, создание таблиц
│   ├── models.py          # ORM-модели Student, Payment
│   ├── schemas.py         # Pydantic-схемы и валидация входных данных
│   ├── crud.py            # все запросы к БД
│   ├── services.py        # бизнес-логика: должники и сводка
│   ├── utils.py           # разбор месяца, расчёт долга (чистые функции)
│   ├── deps.py            # зависимости FastAPI (параметр month)
│   ├── errors.py          # сообщения об ошибках валидации на русском
│   ├── routers/           # students.py, payments.py, debtors.py, dashboard.py
│   ├── static/            # style.css, app.js
│   └── templates/         # index.html
├── tests/                 # pytest-тесты
├── requirements.txt
├── pytest.ini
├── .gitignore
└── README.md
```

## 7. Примеры запросов API

Ниже `BASE = http://127.0.0.1:8000`. Все суммы — в сумах.

| Метод и путь | Назначение | Успех |
|---|---|---|
| `POST /students` | создать ученика | `201` |
| `GET /students` | список учеников | `200` |
| `GET /students/{id}` | один ученик | `200` / `404` |
| `PATCH /students/{id}` | изменить (любые из полей) | `200` / `404` / `422` |
| `DELETE /students/{id}` | удалить вместе с оплатами | `204` / `404` |
| `POST /payments` | добавить оплату | `201` / `404` (нет ученика) / `422` |
| `GET /payments?month=ГГГГ-ММ&student_id=N` | список оплат (оба фильтра необязательны) | `200` |
| `GET /students/{id}/payments?month=ГГГГ-ММ` | история оплат ученика | `200` / `404` |
| `GET /debtors?month=ГГГГ-ММ` | должники за месяц | `200` / `422` |
| `GET /dashboard?month=ГГГГ-ММ` | сводка для дашборда | `200` / `422` |

**macOS / Linux (curl):**

```bash
# создать ученика
curl -X POST http://127.0.0.1:8000/students \
  -H "Content-Type: application/json" \
  -d '{"name":"Ali","phone":"+998901234567","group_name":"Python Beginner","monthly_fee":500000}'

# изменить стоимость
curl -X PATCH http://127.0.0.1:8000/students/1 \
  -H "Content-Type: application/json" -d '{"monthly_fee":550000}'

# добавить оплату (дату можно не указывать — будет сегодняшняя)
curl -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -d '{"student_id":1,"amount":300000,"payment_date":"2026-10-05"}'

# история оплат ученика и должники за октябрь 2026
curl http://127.0.0.1:8000/students/1/payments
curl "http://127.0.0.1:8000/debtors?month=2026-10"

# удалить ученика
curl -X DELETE http://127.0.0.1:8000/students/1
```

**Windows PowerShell:**

```powershell
$base = "http://127.0.0.1:8000"
function Send-Json($method, $url, $obj) {
  Invoke-RestMethod -Method $method -Uri $url -ContentType "application/json; charset=utf-8" `
    -Body ([Text.Encoding]::UTF8.GetBytes(($obj | ConvertTo-Json)))
}

Send-Json Post  "$base/students" @{ name="Ali"; phone="+998901234567"; group_name="Python Beginner"; monthly_fee=500000 }
Send-Json Patch "$base/students/1" @{ monthly_fee=550000 }
Send-Json Post  "$base/payments" @{ student_id=1; amount=300000; payment_date="2026-10-05" }

Invoke-RestMethod "$base/students/1/payments"
Invoke-RestMethod "$base/debtors?month=2026-10" | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Delete "$base/students/1"
```

**Пример ответа `GET /debtors?month=2026-10`:**

```json
{
  "month": "2026-10",
  "total_debtors": 2,
  "total_debt": 600000,
  "debtors": [
    {"student_id": 1, "name": "Ali", "phone": "+998901234567", "group_name": "Python Beginner",
     "monthly_fee": 500000, "paid_amount": 300000, "debt_amount": 200000},
    {"student_id": 2, "name": "Madina", "phone": "+998931234567", "group_name": "Frontend",
     "monthly_fee": 400000, "paid_amount": 0, "debt_amount": 400000}
  ]
}
```

Поле `total_debt` — дополнение к примеру из задания (сумма задолженности по всем должникам).
Должники отдаются в порядке `student_id`; в интерфейсе они сортируются по убыванию долга.

**Формат ошибок.** Некорректные данные → `422` с понятным текстом:

```json
{
  "detail": "Стоимость обучения: Значение должно быть не меньше 0",
  "errors": [{"field": "monthly_fee", "message": "Значение должно быть не меньше 0"}]
}
```

Отсутствующий ученик → `404`: `{"detail": "Ученик с ID 999 не найден"}`.

## 8. Примеры данных для тестирования

Рабочая база при первом запуске **пустая** — тестовые данные автоматически не создаются.
Чтобы быстро наполнить её вручную, выполните (сервер должен быть запущен).

| Ученик | Телефон | Группа | В месяц |
|---|---|---|---|
| Ali | +998901234567 | Python Beginner | 500 000 |
| Madina | +998931234567 | Frontend | 400 000 |
| Dilnoza | +998971234567 | Design | 300 000 |

| Оплата | Сумма | Дата |
|---|---|---|
| Ali | 300 000 | 2026-10-05 |
| Dilnoza | 300 000 | 2026-10-10 |

Для октября 2026 должниками будут Ali (долг 200 000) и Madina (долг 400 000); Dilnoza оплатила полностью.
В интерфейсе выберите месяц `2026-10` переключателем в правом верхнем углу.

**macOS / Linux:**

```bash
B=http://127.0.0.1:8000; H="Content-Type: application/json"
curl -s -X POST $B/students -H "$H" -d '{"name":"Ali","phone":"+998901234567","group_name":"Python Beginner","monthly_fee":500000}'
curl -s -X POST $B/students -H "$H" -d '{"name":"Madina","phone":"+998931234567","group_name":"Frontend","monthly_fee":400000}'
curl -s -X POST $B/students -H "$H" -d '{"name":"Dilnoza","phone":"+998971234567","group_name":"Design","monthly_fee":300000}'
curl -s -X POST $B/payments -H "$H" -d '{"student_id":1,"amount":300000,"payment_date":"2026-10-05"}'
curl -s -X POST $B/payments -H "$H" -d '{"student_id":3,"amount":300000,"payment_date":"2026-10-10"}'
```

**Windows PowerShell** (после определения `$base` и `Send-Json` из раздела 7):

```powershell
Send-Json Post "$base/students" @{ name="Ali";     phone="+998901234567"; group_name="Python Beginner"; monthly_fee=500000 }
Send-Json Post "$base/students" @{ name="Madina";  phone="+998931234567"; group_name="Frontend";        monthly_fee=400000 }
Send-Json Post "$base/students" @{ name="Dilnoza"; phone="+998971234567"; group_name="Design";          monthly_fee=300000 }
Send-Json Post "$base/payments" @{ student_id=1; amount=300000; payment_date="2026-10-05" }
Send-Json Post "$base/payments" @{ student_id=3; amount=300000; payment_date="2026-10-10" }
```

(Идентификаторы 1, 2, 3 выдаются по порядку создания, если база была пустой.)

## 9. База данных

- Файл: **`data/students.db`** (SQLite) внутри папки проекта. Папка и таблицы создаются автоматически при первом запуске.
- Данные сохраняются между перезапусками. Файл содержит персональные данные учеников, поэтому он добавлен в `.gitignore`.
- Резервная копия: остановите сервер и скопируйте `data/students.db`.
- Другая база: переменная окружения `DATABASE_URL`, например
  - PowerShell: `$env:DATABASE_URL = "sqlite:///demo.db"; uvicorn app.main:app --reload`
  - macOS/Linux: `DATABASE_URL=sqlite:///demo.db uvicorn app.main:app --reload`

## 10. Тесты

С активированным виртуальным окружением, из корня проекта:

```bash
pytest
```

(или `python -m pytest`; подробный вывод — `pytest -v`.)

Тесты используют **отдельную временную базу** (для каждого теста создаётся свой пустой файл во временной папке),
поэтому рабочий файл `data/students.db` они не читают и не меняют. Покрыто: создание, просмотр, изменение и удаление ученика;
валидация; платежи и их история; сохранность платежей после «перезапуска»; должники — несколько оплат за месяц,
полная и частичная оплата, отсутствие оплат, переплата, разные месяцы и границы месяцев (в т. ч. декабрь и 29 февраля),
смена стоимости, неверный формат месяца, несуществующий ученик, пустая база; сводка дашборда.

## 11. Как сбросить базу

- **Рабочая база** (удалит всех учеников и оплаты безвозвратно): остановите сервер (`Ctrl + C`) и удалите файл —
  PowerShell: `Remove-Item data\students.db`; macOS/Linux: `rm data/students.db`.
  При следующем запуске создастся новая пустая база.
- **Тестовая база**: сбрасывать ничего не нужно — она создаётся заново при каждом запуске `pytest` и не затрагивает рабочие данные.
- Отдельная «песочница» для экспериментов: запустите сервер с `DATABASE_URL` (см. раздел 9) и удалите файл `demo.db`, когда он станет не нужен.

## 12. Безопасность и ограничения

- Все запросы к БД выполняются через SQLAlchemy с параметрами — SQL-инъекции исключены. Данные из API в интерфейсе вставляются как текст, а не как HTML.
- В коде нет паролей, ключей и внешних сервисов.
- **Авторизации нет**: приложение рассчитано на локальное использование в сети центра. Если нужен доступ из интернета, поставьте его за обратный прокси с авторизацией.
- Постраничной выдачи нет (список учеников и оплат отдаётся целиком) — для одного учебного центра этого достаточно.
