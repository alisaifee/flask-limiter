lint:
	ruff check --select I
	ruff format --check flask_limiter tests
	ruff flask_limiter tests 
	mypy flask_limiter

lint-fix:
	ruff check --select I --fix
	ruff format flask_limiter tests
	ruff --fix flask_limiter tests 
	mypy flask_limiter
