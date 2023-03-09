lint:
	black --check tests flask_limiter
	mypy flask_limiter
	flake8 flask_limiter tests

lint-fix:
	black tests flask_limiter
	mypy flask_limiter
	isort -r --profile=black tests flask_limiter
	autoflake8 -i -r tests flask_limiter
