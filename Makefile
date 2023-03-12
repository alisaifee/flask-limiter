lint:
	black --check tests flask_limiter
	mypy flask_limiter
	ruff flask_limiter tests 

lint-fix:
	black tests flask_limiter
	mypy flask_limiter
	isort -r --profile=black tests flask_limiter
	ruff --fix flask_limiter tests 
