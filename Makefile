.PHONY: install dev run cli themes build clean gate

install:
	pip install .

dev:
	pip install -r requirements-dev.txt

run:
	python -m fluxtuner

cli:
	python -m fluxtuner --cli

themes:
	python -m fluxtuner --list-themes

build:
	python -m build

clean:
	rm -rf build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +


gate:
	ruff format --check .
	ruff check .
	python -m compileall fluxtuner tests
	python -m pytest
	mypy --follow-imports=skip fluxtuner/
	node --check fluxtuner/web/static/app.js
	pip-audit --local
	bandit -r fluxtuner -c pyproject.toml
