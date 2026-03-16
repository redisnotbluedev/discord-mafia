#!/bin/bash

# run_tests.sh - Discover and run all Python unit tests in the project.

# Set PYTHONPATH to the immediate directory to ensure module imports work correctly.
here=$(dirname -- "$( readlink -f -- "$0"; )")
export PYTHONPATH=$PYTHONPATH:$here

echo "Finding and running Python unit tests..."

# Use python3's unittest discovery.
# -s . : Start discovery from the current directory.
# -p "*_test.py" : Pattern for test files.
python3 -m unittest discover -s $here

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "----------------------------------------------------------------------"
    echo "SUCCESS: All tests passed!"
else
    echo "----------------------------------------------------------------------"
    echo "FAILURE: Some tests failed (exit code: $exit_code)."
fi

exit $exit_code
