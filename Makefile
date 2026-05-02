.PHONY: install dev run cli themes build clean

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
