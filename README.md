# 🤖 Insurance Law Bot

Telegram бот для консультаций по страховому законодательству РК с веб-панелью управления.

---

## 🎯 Как это работает

### Общая схема
```

Пользователь в Telegram → Bot получает вопрос → Redis сохраняет историю
↓
Core ищет ответ в документах → Gemini генерирует ответ → Bot отправляет результат
```
### Основные компоненты

**📱 Bot** (`bot.py`) — Слушает Telegram, получает вопросы, отправляет ответы. Команды: `/start`, `/help`, `/status`, `/clear`

**🌐 Web API** (`api.py`) — REST API на порту 8000. Загрузка документов, просмотр статуса, перестроение индексов.

**🧠 Core Intelligence** (`core.py`) — Главный мозг. Работает в 4 этапа:

1️⃣ **Загрузка документов** — Извлекает текст из DOCX файлов в папке `insurance_laws/`

2️⃣ **Разбиение на куски** — Нарезает документы на куски по 1000 символов. Нужно для быстрого поиска нужного куска вместо всего документа.

3️⃣ **Векторизация** — Преобразует текст в векторы чисел через Google API. Похожие тексты = похожие векторы.

```
"Что такое ОСАГО?" → [0.2, -0.5, 0.8, ... 768 чисел ...]
```

4️⃣ **Поиск** — Когда приходит вопрос, он преобразуется в вектор и ищутся 10 самых похожих кусков документов. Эти куски отправляются в Gemini.

**📚 Manager** (`manager.py`) — Отслеживает документы, сохраняет метаданные, управляет словарём терминов.

**💾 Redis** — Кэш истории чатов и сессии пользователей.

---

## 🔄 Как отвечает на вопрос
```
Пользователь: "Какие виды ОСАГО существуют?"
      ↓
Bot получает → нормализует текст → отправляет в Core
      ↓
Core преобразует в вектор → ищет похожие куски в БД
      ↓
Находит 10 релевантных кусков из разных документов
      ↓
Отправляет куски + вопрос в Gemini
      ↓
Gemini генерирует ответ на основе найденного
      ↓
Bot отправляет ответ в Telegram + сохраняет в историю (Redis)
```
---

## 🚀 Быстрый старт

### Подготовка
```bash
cd nomadbot
```

### Создаём .env
```bash
cat > .env << EOF
TELEGRAM_BOT_TOKEN=your_token_here
GOOGLE_API_KEY=your_key_here
EOF
```

### Запуск с Docker
```shell script
docker-compose up -d          # Поднимаем всё
docker-compose ps             # Проверяем статус
docker-compose logs -f bot    # Смотрим логи
```


### Проверка
```shell script
# Telegram — откройте бота и пишите /start

# Web API
curl http://localhost:8000/api/status
curl http://localhost:8000/api/documents
```


---

## 📡 API (веб-панель)

| Метод | Путь | Описание |
|-------|------|---------|
| GET | `/api/status` | Статус базы знаний |
| GET | `/api/documents` | Список документов |
| POST | `/api/documents/upload` | Загрузить документ |
| GET | `/api/terminology` | Словарь терминов |
| POST | `/api/rebuild` | Пересчитать индексы |

**Примеры:**
```shell script
curl http://localhost:8000/api/status | json_pp
curl -F "file=@закон.docx" http://localhost:8000/api/documents/upload
curl -X POST http://localhost:8000/api/rebuild
```


---

## 📁 Структура
```
nomadbot/
├── bot.py              ← Telegram интерфейс
├── api.py              ← Веб-сервер
├── core.py             ← AI мозг (RAG)
├── manager.py          ← Управление документами
├── requirements.txt    ← Зависимости
├── docker-compose.yml  ← Docker конфиг
├── insurance_laws/     ← Ваши DOCX документы
├── knowledge_base/     ← Индексы (не трогать)
└── insurance_law_db/   ← БД векторов (не трогать)
```


---

## 🛠️ Команды Docker

```shell script
docker-compose up -d              # Запуск
docker-compose down               # Остановка
docker-compose build --no-cache   # Пересборка
docker-compose logs -f bot        # Логи бота
docker-compose logs -f web        # Логи веб-сервера
docker-compose exec bot bash      # Вход в контейнер
docker-compose down -v            # Удалить всё (вместе с БД)
```


---

## 💬 Telegram команды

| Команда | Что делает |
|---------|-----------|
| `/start` | Приветствие и справка |
| `/help` | Справка по использованию |
| `/status` | Статус базы знаний |
| `/clear` | Очистить историю |
| `/feedback` | Отправить отзыв |

**Примеры вопросов:**
- "Что такое ОСАГО?"
- "Какие виды страхования?"
- "Какие требования к страховщику?"
- "Расскажи подробнее про..."

Бот помнит контекст и отвечает на уточняющие вопросы.

---

## ⚙️ Технологии

Python 3.13 • Telegram Bot API • Flask • Google Gemini • Google Embeddings • Redis • Docker

---

## 🔐 Получение ключей

**Telegram Bot Token** → [@BotFather](https://t.me/botfather) → `/newbot`

**Google API Key** → [Google AI Console](https://aistudio.google.com/apikey)

---

## 🐛 Проблемы

**Бот не отвечает:**
```shell script
docker-compose logs bot
# Проверьте TELEGRAM_BOT_TOKEN и GOOGLE_API_KEY
```


**Redis ошибка:**
```shell script
docker-compose restart redis
```


**Медленные ответы:**
```shell script
# Может быть много документов. Пересчитайте:
curl -X POST http://localhost:8000/api/rebuild
```


---

**Версия:** 1.0 | **Статус:** ✅ Готово к работе
```
Готово! Теперь всё в одном сообщении и не сливается с встроенной панелью. 👍
```
