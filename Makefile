# Run from inside virtualenv, or use Python2.7


pylint:
	pylint --rcfile=.pylintrc fetchphotos.py tests/unit_tests.py
