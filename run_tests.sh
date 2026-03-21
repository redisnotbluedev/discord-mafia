#!/bin/bash

# run_tests.sh - Discover and run all Python unit tests in the project.

# Set PYTHONPATH to the immediate directory to ensure module imports work correctly.
here=$(dirname -- "$( readlink -f -- "$0"; )")
export PYTHONPATH=$PYTHONPATH:$here

echo "Finding and running Python unit tests..."

# Use pytest for test discovery and execution with coverage reporting.
pytest "$here/tests" --cov=classes --cov=cogs --cov=data --cov=logging_utils --cov-report=term-missing "$@"

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "----------------------------------------------------------------------"
    echo "SUCCESS: All tests passed!"
else
    echo "----------------------------------------------------------------------"
    echo "FAILURE: Some tests failed (exit code: $exit_code)."
fi

exit $exit_code
