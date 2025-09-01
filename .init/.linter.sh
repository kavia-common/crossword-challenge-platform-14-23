#!/bin/bash
cd /home/kavia/workspace/code-generation/crossword-challenge-platform-14-23/backend_django
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

