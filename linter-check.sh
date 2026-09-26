#!/usr/bin/env bash
# Run the same lint checks as the CI lint job.
# Requires ShellCheck, yamllint, and Hadolint on PATH.
# Usage: ./linter-check.sh

set -uo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")" || exit 1

required_tools=(git hadolint shellcheck yamllint)
missing_tools=()
for tool in "${required_tools[@]}"; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    missing_tools+=("$tool")
  fi
done

if [ "${#missing_tools[@]}" -ne 0 ]; then
  printf 'Missing required tools: %s\n' "${missing_tools[*]}" >&2
  exit 1
fi

# Include tracked scripts and untracked, non-ignored scripts such as this one.
shell_scripts=()
while IFS= read -r -d '' script; do
  shell_scripts+=("$script")
done < <(git ls-files -z --cached --others --exclude-standard -- '*.sh')

if [ "${#shell_scripts[@]}" -eq 0 ]; then
  printf 'No shell scripts found to check.\n' >&2
  exit 1
fi

check_names=()
check_results=()
overall_status=0

run_check() {
  local name="$1"
  shift
  printf '==> %s\n' "$name"
  if "$@"; then
    check_results+=(PASS)
  else
    check_results+=(FAIL)
    overall_status=1
  fi
  check_names+=("$name")
  printf '\n'
}

run_check 'Hadolint (MediaWiki)' hadolint --config .hadolint.yaml Dockerfile-mediawiki
run_check 'Hadolint (MemcachePHP)' hadolint --config .hadolint.yaml Dockerfile-memcachephp
run_check 'ShellCheck' shellcheck "${shell_scripts[@]}"
run_check 'yamllint' yamllint --strict --config-file .yamllint.yaml .

printf '%s\n' '================ Summary ================'
for i in "${!check_names[@]}"; do
  printf '  %-24s %s\n' "${check_names[$i]}" "${check_results[$i]}"
done
printf '%s\n' '========================================='

exit "$overall_status"
