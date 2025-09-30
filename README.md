# ApplyBot 🤖

Автоматизированная система для подачи заявок на вакансии с hh.ru с использованием ИИ для генерации персонализированных сопроводительных писем.

## 🚧 Статус проекта

**⏸️ Временно приостановлен** (последнее обновление: июнь 2025)

Проект для автоматизации поиска работы на hh.ru. Базовая архитектура реализована, авторизация и поиск вакансий работают, но отправка откликов и генерация писем содержат баги. Работа приостановлена, планирую вернуться к доработке позже.

### ✅ Работает
- ✅ OAuth авторизация с hh.ru
- ✅ Поиск и фильтрация вакансий
- ✅ Интеграция с Anthropic Claude 4.0 (Opus)
- ✅ Базовая архитектура FastAPI + SQLAlchemy
- ✅ Docker окружение для разработки

### 🐛 В разработке (есть баги)
- 🔧 Генерация сопроводительных писем
- 🔧 Автоматическая отправка откликов
- 🔧 Ответы на скрининговые вопросы
- 🔧 Массовые отклики
- 🔧 История откликов в БД
- 🔧 Фоновые задачи через RQ

### 📋 Возможные улучшения (если вернусь к проекту)
- Исправление существующих багов
- Telegram бот для управления
- Веб-интерфейс для настройки
- Аналитика и статистика откликов

## 🛠️ Технологический стек

### Backend
- **FastAPI** 0.115+ - асинхронный веб-фреймворк
- **SQLAlchemy 2.0** - ORM с async поддержкой
- **PostgreSQL** - основная база данных
- **asyncpg** - асинхронный драйвер PostgreSQL
- **Alembic** - миграции БД
- **Redis** + **RQ** - очереди задач (в разработке)

### AI/ML
- **Anthropic Claude 4.0 (Opus)** - генерация текстов

### Development Tools
- **Poetry** - управление зависимостями
- **Docker** + **Docker Compose** - контейнеризация
- **Ruff** - линтинг и форматирование
- **MyPy** - статическая типизация
- **Pytest** - тестовый фреймворк

## 🚀 Быстрый старт

### Требования
- Python 3.11
- Docker и Docker Compose
- Аккаунт на hh.ru с созданным приложением
- API ключ Anthropic

### Получение учетных данных

#### 1. HeadHunter OAuth
1. Зарегистрируйте приложение на https://dev.hh.ru/
2. Получите `client_id` и `client_secret`
3. Укажите redirect URI: `http://localhost:8000/auth/callback`

#### 2. Anthropic API
1. Зарегистрируйтесь на https://console.anthropic.com/
2. Создайте API ключ в настройках аккаунта

### Установка

1. **Клонируйте репозиторий**
```bash
git clone https://github.com/FrostWillmott/ApplyBot.git
cd ApplyBot
```

2. **Создайте файл `.env`**
```env
# HeadHunter OAuth
HH_CLIENT_ID=your_hh_client_id
HH_CLIENT_SECRET=your_hh_client_secret
HH_REDIRECT_URI=http://localhost:8000/auth/callback

# Anthropic API
ANTHROPIC_API_KEY=your_anthropic_key
LLM_PROVIDER=sonnet4

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/applybot

# Redis
REDIS_URL=redis://redis:6379/0
```

3. **Запустите с Docker Compose**
```bash
# Development режим
docker-compose --profile dev up -d

# Просмотр логов
docker-compose logs -f app_dev
```

Приложение будет доступно на `http://localhost:8000`

### Локальная разработка (без Docker)

```bash
# Установка зависимостей
poetry install

# Активация виртуального окружения
poetry shell

# Запуск PostgreSQL и Redis (требуется Docker)
docker-compose up db redis -d

# Запуск миграций
alembic upgrade head

# Запуск сервера разработки
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📚 Использование

### 1. Авторизация

Перейдите на `http://localhost:8000/auth/login` для авторизации через OAuth hh.ru.

### 2. API Endpoints

#### Документация API
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

#### Поиск вакансий (✅ работает)
```bash
GET /apply/search?text=Python%20Developer&page=0&per_page=20
```

#### Одиночный отклик (🐛 в разработке)
```bash
POST /apply/single/{vacancy_id}
Content-Type: application/json

{
  "position": "Python Developer",
  "resume": "Experienced Python developer with 5+ years...",
  "skills": "Python, FastAPI, PostgreSQL, Docker",
  "experience": "5+ years in web development",
  "resume_id": "your_resume_id_from_hh"
}
```

#### Массовые отклики (🐛 в разработке)
```bash
POST /apply/bulk?max_applications=20
Content-Type: application/json

{
  "position": "Python Developer",
  "resume": "Experienced Python developer...",
  "skills": "Python, FastAPI, PostgreSQL",
  "experience": "5+ years",
  "resume_id": "your_resume_id",
  "exclude_companies": ["CompanyToExclude"],
  "salary_min": 100000,
  "remote_only": true,
  "required_skills": ["Python", "FastAPI"]
}
```

### 3. Веб-интерфейс

Базовый веб-интерфейс доступен на `http://localhost:8000`

## 🧪 Тестирование

```bash
# Запуск всех тестов
poetry run pytest

# С покрытием кода
poetry run pytest --cov=app --cov-report=html

# Только unit тесты
poetry run pytest tests/unit/

# Только integration тесты
poetry run pytest tests/integration/

# Запуск тестов в Docker
docker-compose --profile dev run --rm tests
```

## 📁 Структура проекта

```
ApplyBot/
├── app/
│   ├── core/              # Конфигурация и базовые утилиты
│   │   ├── config.py      # Настройки приложения
│   │   ├── storage.py     # База данных
│   │   └── exceptions.py  # Кастомные исключения
│   ├── models/            # SQLAlchemy модели
│   │   ├── token.py       # Токены OAuth
│   │   ├── application.py # История откликов
│   │   └── user.py        # Пользователи
│   ├── routers/           # FastAPI endpoints
│   │   ├── auth.py        # Авторизация ✅
│   │   ├── apply.py       # Отклики 🐛
│   │   └── hh_apply.py    # Legacy endpoints
│   ├── schemas/           # Pydantic модели
│   │   └── apply.py       # Схемы для откликов
│   ├── services/          # Бизнес-логика
│   │   ├── application_service.py  # Основной сервис 🐛
│   │   ├── hh_client.py            # HH API клиент ✅
│   │   └── llm/                    # LLM провайдеры 🐛
│   │       ├── base.py
│   │       ├── providers.py
│   │       └── factory.py
│   ├── utils/             # Утилиты
│   │   ├── filters.py     # Фильтры вакансий
│   │   └── validators.py  # Валидаторы
│   ├── static/            # Веб-интерфейс
│   │   ├── index.html
│   │   ├── script.js
│   │   └── styles.css
│   ├── tasks.py           # RQ фоновые задачи 🐛
│   └── main.py            # Точка входа
├── tests/                 # Тесты
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── conftest.py
├── alembic/               # Миграции БД
│   ├── versions/
│   └── env.py
├── .github/
│   └── workflows/         # CI/CD (планируется)
├── docker-compose.yml     # Docker конфигурация
├── Dockerfile             # Multi-stage build
├── pyproject.toml         # Poetry зависимости
├── ruff.toml              # Ruff конфигурация
├── pytest.ini             # Pytest настройки
└── README.md              # Этот файл
```

## 🔧 Разработка

### Миграции БД

```bash
# Создание новой миграции
alembic revision --autogenerate -m "Description"

# Применение миграций
alembic upgrade head

# Откат миграции
alembic downgrade -1
```

### Линтинг и форматирование

```bash
# Проверка кода
poetry run ruff check app tests

# Автоисправление
poetry run ruff check --fix app tests

# Форматирование
poetry run ruff format app tests

# Проверка типов
poetry run mypy app
```

### Pre-commit hooks

```bash
# Установка
poetry run pre-commit install

# Запуск вручную
poetry run pre-commit run --all-files
```

## ⚠️ Известные проблемы

Проект содержит нерешенные баги в ключевых функциях:
- Генерация сопроводительных писем требует отладки
- Отправка откликов не работает стабильно  
- Фоновые задачи через RQ не настроены
- История откликов не всегда сохраняется корректно

Авторизация и поиск вакансий работают стабильно.

## 🙏 Благодарности

- [HeadHunter API](https://dev.hh.ru/) - за предоставление API
- [Anthropic](https://www.anthropic.com/) - за Claude API
- [FastAPI](https://fastapi.tiangolo.com/) - за отличный фреймворк

---

<sub>⚠️ **Дисклеймер:** Проект в стадии разработки, основные функции содержат баги. Работает только поиск вакансий и авторизация. Используйте на свой риск.</sub>
