# Run from inside virtualenv, or use Python2.7

test:
	PYTHONPATH=".:" tests/unit_tests.py --verbose
	PYTHONPATH=".:" tests/functional_tests.py --verbose

# For speed
unittest:
	PYTHONPATH=".:" tests/unit_tests.py --verbose

pylint:
	pylint --rcfile=.pylintrc fetchphotos.py tests/unit_tests.py tests/functional_tests.py
