#!/bin/bash
# Catch bare \uXXXX escape sequences in JSX text content.
# JSX text does NOT process JS unicode escapes.
# Valid:   {"\u2014"} or "\u2014" (inside JS strings)
# Invalid: <div>\u2014</div> (bare JSX text)

ROOT="$(git rev-parse --show-toplevel)/frontend/src"
ISSUES=0

while IFS= read -r match; do
  file=$(echo "$match" | cut -d: -f1)
  line_num=$(echo "$match" | cut -d: -f2)
  content=$(echo "$match" | cut -d: -f3-)

  # Remove all double-quoted strings from the line
  stripped=$(echo "$content" | sed "s/\"[^\"]*\"//g")

  # If \uXXXX still appears after removing quoted strings, it is bare
  if echo "$stripped" | grep -qE u[0-9a-fA-F]{4}; then
    echo "  $file:$line_num: $content"
    ISSUES=$((ISSUES + 1))
  fi
done < <(grep -rn u[0-9a-fA-F]{4} "$ROOT" --include="*.jsx" | grep -v node_modules)

if [ $ISSUES -gt 0 ]; then
  echo ""
  echo "ERROR: Found $ISSUES bare Unicode escape(s) in JSX text."
  echo "Fix: use literal chars or JS string: {\"\u2014\"}"
  exit 1
fi
exit 0
