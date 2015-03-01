#!/bin/sh
cd ..
PYTHONPATH=".:" tests/functional_tests.py --verbose "$@"

#end
