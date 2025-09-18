lint:
	uv run ruff check flask_limiter tests examples --select I
	uv run ruff format --check flask_limiter tests examples
	uv run ruff check flask_limiter tests examples 
	uv run mypy flask_limiter

lint-fix:
	uv run ruff check flask_limiter tests examples --select I --fix
	uv run ruff format flask_limiter tests examples
	uv run ruff check --fix flask_limiter tests examples 
	uv run mypy flask_limiter
