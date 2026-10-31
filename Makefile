.PHONY: setup run-backend run-frontend seed test docker-up docker-down

PYTHON ?= python
PIP ?= pip
NPM ?= npm

setup:
	cd backend && $(PYTHON) -m venv .venv && \
	( .venv/Scripts/pip install -r requirements.txt || .venv/bin/pip install -r requirements.txt )
	cd frontend && $(NPM) install

run-backend:
	cd backend && ( .venv/Scripts/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 || .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 )

run-frontend:
	cd frontend && $(NPM) run dev

seed:
	cd backend && ( .venv/Scripts/python -m app.seed || .venv/bin/python -m app.seed )

test:
	$(PYTHON) scripts/smoke_test.py

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

