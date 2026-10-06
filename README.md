# Document Search Service

Cервис полнотекстового поиска по документам. PostgreSQL хранит
документы целиком (`id`, `rubrics`, `text`, `created_date`), Elasticsearch
хранит поисковый индекс со строго фиксированной схемой `{id, text}`.

## Архитектура

```
клиент -> FastAPI -> Elasticsearch (поиск по text, relevance)
                   -> PostgreSQL   (все поля, сортировка по created_date)
```

Индекс ES не содержит поля даты, поэтому финальная сортировка по `created_date`
выполняется в Postgres. Алгоритм поиска:

1. Запрос `match` по полю `text` в Elasticsearch, топ `SEARCH_OVERFETCH_SIZE`
   (по умолчанию 200) документов по релевантности — возвращаются только id.
2. Из Postgres одним запросом выбираются 20 самых свежих документов среди
   этих id (`ORDER BY created_date DESC, id LIMIT 20`)

**Компромисс:** это приближение, а не точный ответ "top-20 по дате среди
всех релевантных документов". Если по запросу релевантны более 200
документов, самый свежий из них может оказаться за пределами окна в 200 и не
попасть в выдачу.

Текстовый анализ в ES использует русский стеммер (`russian_stop` +
`russian_stemmer` поверх `standard` tokenizer) — данные в `posts.csv` на
русском языке, и без стемминга запрос "конкурс" не находил бы "конкурсе",
"конкурсов" и т.п.

## Требования

- Docker + Docker Compose (рекомендуемый способ запуска)
- либо локально: Python 3.12+, PostgreSQL 16, Elasticsearch 8.x

## Быстрый старт (Docker)

```bash
cp .env.example .env   # при необходимости поправить значения
make up                # поднимает postgres, elasticsearch, api
make import             # импортирует posts.csv в Postgres и Elasticsearch
```

Сервис будет доступен на `http://localhost:8000`. Таблица и индекс
создаются при старте сервиса, поэтому до импорта поиск просто возвращает
пустой результат. Postgres и Elasticsearch
портов на хост не публикуют (во избежание конфликтов с уже запущенными
локальными сервисами на стандартных портах 5432/9200) — api обращается к ним
по внутренней docker-сети; при необходимости доступа с хоста добавьте свой
`ports:` в `docker-compose.override.yml`.

Примеры запросов:

```bash
curl 'http://localhost:8000/documents/search?q=конкурс'

curl -X DELETE 'http://localhost:8000/documents/<id>'
```

Остановить и удалить все данные: `make down`.

## Запуск без Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# локальные Postgres и Elasticsearch должны быть запущены,
# переменные окружения см. в .env.example
export DATABASE_URL=postgresql+asyncpg://docsearch:docsearch@localhost:5432/docsearch
export ELASTICSEARCH_URL=http://localhost:9200

python -m scripts.import_csv --csv-path posts.csv
uvicorn app.main:app --reload
```

## API

- `GET /documents/search?q=<текст>` — полнотекстовый поиск, возвращает до 20
  документов (все поля БД), отсортированных по `created_date` по убыванию
  (сначала новые). Пустой результат — валидный ответ `200` с `results: []`.
- `DELETE /documents/{id}` — удаляет документ из Postgres и из индекса
  Elasticsearch. `404`, если документа нет в БД. Удаление из БД фиксируется
  только после успешного удаления из индекса: если Elasticsearch недоступен,
  запрос завершается `500`, строка в БД остаётся, и запрос можно повторить.

Интерактивная документация доступна на `/docs` (Swagger UI) и `/redoc`, пока
сервис запущен. Статический снэпшот OpenAPI-схемы лежит в [`docs.json`](docs.json)
и перегенерируется командой:

```bash
make docs
```

## Импорт данных (`scripts/import_csv.py`)

- `id` в `posts.csv` отсутствует — генерируется как UUID при импорте.
- `rubrics` в CSV хранится как строка-литерал Python (`"['VK-...', ...]"`) и
  парсится через `ast.literal_eval`; если
  строка не парсится, документу присваивается `rubrics = []` и выводится
  предупреждение, импорт не прерывается.
- Данные пишутся батчами (по умолчанию 500 строк) в Postgres и индексируются
  тем же батчем через `elasticsearch.helpers.async_bulk`.
- Повторный запуск без флагов **дублирует** данные (новые id генерируются
  каждый раз). Флаг `--truncate` очищает таблицу и пересоздаёт индекс перед
  импортом:

```bash
docker compose run --rm api python -m scripts.import_csv --truncate
```

## Переменные окружения

| Переменная | Назначение | Значение по умолчанию |
|---|---|---|
| `DATABASE_URL` | строка подключения к Postgres (async) | `postgresql+asyncpg://docsearch:docsearch@localhost:5432/docsearch` |
| `ELASTICSEARCH_URL` | адрес Elasticsearch | `http://localhost:9200` |
| `ES_INDEX_NAME` | имя индекса | `documents` |
| `SEARCH_OVERFETCH_SIZE` | размер окна релевантности из ES перед сортировкой по дате | `200` |

## Тесты

Функциональные тесты поднимают отдельный тестовый стек Postgres/Elasticsearch
(`docker-compose.test.yml`) на других портах и гоняют тесты прямо по
приложению (`httpx.AsyncClient` поверх ASGI, без моков БД/ES):

```bash
make test
```