.PHONY: install test run-api run-ui docker

install:
	python3 -m pip install -r backend/requirements-dev.txt
	cd frontend && npm ci

test:
	PYTHONPATH=backend:serverless pytest
	ruff check backend serverless tests test_pipeline.py
	cd frontend && npm audit --audit-level=high && npm run build

run-api:
	cd backend && uvicorn main:app --reload --port 8000

run-ui:
	cd frontend && npm run dev

docker:
	docker compose up --build
