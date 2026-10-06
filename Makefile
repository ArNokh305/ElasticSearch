.PHONY: up down import test docs logs

up:
	docker compose up -d --build

down:
	docker compose down -v

import:
	docker compose run --rm api python -m scripts.import_csv --csv-path posts.csv

docs:
	python -m scripts.gen_docs

test:
	docker compose -f docker-compose.test.yml up -d --wait postgres-test elasticsearch-test
	docker compose -f docker-compose.test.yml run --rm --build tests; \
	status=$$?; \
	docker compose -f docker-compose.test.yml down -v; \
	exit $$status

logs:
	docker compose logs -f api
