lint:
	ruff check flask_limiter tests examples --select I
	ruff format --check flask_limiter tests examples
	ruff check flask_limiter tests examples 
	mypy flask_limiter

lint-fix:
	ruff check flask_limiter tests examples --select I --fix
	ruff format flask_limiter tests examples
	ruff check --fix flask_limiter tests examples 
	mypy flask_limiter
