#!/usr/bin/env bats
#R001-T01 #R005-T01 #R005-T02 #R010-T01 #R010-T02 #R015-T01 #R015-T02 #R015-T03
#R020-T01 #R020-T02 #R020-T03 #R022-T01 #R022-T02 #R022-T03 #R025-T01 #R025-T02
#R030-T01 #R030-T02 #R035-T01 #R035-T02 #R040-T01 #R040-T02 #R045-T01 #R045-T02

load "helpers/common.bash"

make_venv_python_stub() {
  local pytest_exit="${1:-0}"
  local mutmut_mode="${2:-pass}"
  local killed="${3:-42}"
  local survived="${4:-8}"
  local total="${5:-50}"
  mkdir -p "${FIXTURE_ROOT}/matchy-venv/bin" "${FIXTURE_ROOT}/tests/py" "${FIXTURE_ROOT}/mutants"
  cat > "${FIXTURE_ROOT}/tests/py/sample_test.py" <<'EOF'
def test_ok():
    assert True
EOF
  cat > "${FIXTURE_ROOT}/matchy-venv/bin/python" <<EOF
#!/usr/bin/env bash
if [ "\${1:-}" = "-m" ] && [ "\${2:-}" = "pytest" ]; then
  echo "pytest \$*" >> "${CALLS_LOG}"
  exit ${pytest_exit}
fi
if [ "\${1:-}" = "-m" ] && [ "\${2:-}" = "mutmut" ] && [ "\${3:-}" = "--version" ]; then
  echo "mutmut 3.0.0"
  exit 0
fi
if [ "\${1:-}" = "-m" ] && [ "\${2:-}" = "mutmut" ] && [ "\${3:-}" = "run" ]; then
  echo "mutmut run \$*" >> "${CALLS_LOG}"
  if [ "${mutmut_mode}" = "timeout" ]; then
    sleep 300
  fi
  if [ "${mutmut_mode}" = "fail" ]; then
    exit 2
  fi
  exit 0
fi
if [ "\${1:-}" = "-m" ] && [ "\${2:-}" = "mutmut" ] && [ "\${3:-}" = "export-cicd-stats" ]; then
  echo "mutmut export-cicd-stats \$*" >> "${CALLS_LOG}"
  if [ "${mutmut_mode}" = "no_results" ]; then
    exit 0
  fi
  mkdir -p "${FIXTURE_ROOT}/mutants"
  cat > "${FIXTURE_ROOT}/mutants/mutmut-cicd-stats.json" <<JSON
{"killed":${killed},"survived":${survived},"total":${total},"skipped":0,"timeout":0,"no_tests":0,"suspicious":0,"segfault":0,"modules":{"matchy.scoring_core":{"tests":{"tests/py/test_scoring_core.py::test_bucket":{"killed":1}}}}}
JSON
  exit 0
fi
exec /usr/bin/env python3 "\$@"
EOF
  chmod +x "${FIXTURE_ROOT}/matchy-venv/bin/python"
  : > "${CALLS_LOG}"
}

setup() {
  setup_shell_test
  create_repo_fixture
  copy_script_to_fixture "10_run_mutation_tests.sh"
  mkdir -p "${FIXTURE_ROOT}/.security-reports"
  export MUTATION_USE_SUBPROCESS=false
  make_venv_python_stub 0 pass 90 10 100
}

teardown() {
  teardown_shell_test
}

@test "runs from non-repo working directory" {
  #R001-T01: Run from a non-repo working directory and verify execution succeeds.
  mkdir -p "${TEST_TMPDIR}/elsewhere"
  run bash -c "cd '${TEST_TMPDIR}/elsewhere' && bash '${FIXTURE_ROOT}/10_run_mutation_tests.sh'"
  [ "$status" -eq 0 ]
}

@test "fails when matchy-venv python is unavailable" {
  #R005-T01: Missing venv python fails with explicit guidance.
  rm -rf "${FIXTURE_ROOT}/matchy-venv"
  run bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"matchy-venv python is required"* ]]
}

@test "fails when mutmut is unavailable in venv" {
  #R005-T02: Missing mutmut fails with explicit guidance.
  cat > "${FIXTURE_ROOT}/matchy-venv/bin/python" <<'EOF'
#!/usr/bin/env bash
if [ "${1:-}" = "-m" ] && [ "${2:-}" = "mutmut" ] && [ "${3:-}" = "--version" ]; then
  exit 1
fi
exit 0
EOF
  chmod +x "${FIXTURE_ROOT}/matchy-venv/bin/python"
  run bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"mutmut is required"* ]]
}

@test "fails when preflight pytest fails" {
  #R010-T01: Force pytest failure and verify guidance to run step-05 first.
  make_venv_python_stub 1 pass
  run env MUTATION_SKIP_PREFLIGHT=false bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"./05_run_unit_tests.sh"* ]]
}

@test "does not invoke mutmut when preflight fails" {
  #R010-T02: Verify mutmut is not invoked when preflight pytest fails.
  make_venv_python_stub 1 pass
  run env MUTATION_SKIP_PREFLIGHT=false bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  run grep -F "mutmut run" "${CALLS_LOG}"
  [ "$status" -ne 0 ]
}

@test "skips pytest preflight by default" {
  #R010-T03: Run with default settings and verify pytest is not invoked.
  run bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  [ "$status" -eq 0 ]
  run grep -F "pytest" "${CALLS_LOG}"
  [ "$status" -ne 0 ]
  grep -F "mutmut run" "${CALLS_LOG}"
}

@test "invokes mutmut run after preflight passes" {
  #R015-T01: Verify mutmut run is invoked from repository root after preflight passes.
  run env MUTATION_SKIP_PREFLIGHT=false bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  [ "$status" -eq 0 ]
  grep -F "mutmut run" "${CALLS_LOG}"
}

@test "writes mutation summary report" {
  #R015-T02: Verify CI/CD stats and mutation-summary.json are written.
  #R030-T01: Verify mutation-summary.json is written after a successful run.
  run bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  [ "$status" -eq 0 ]
  [ -f "${FIXTURE_ROOT}/.security-reports/mutmut-cicd-stats.json" ]
  [ -f "${FIXTURE_ROOT}/.security-reports/mutation-summary.json" ]
}

@test "fails when mutmut produces no stats json" {
  #R015-T03: Simulate export without stats JSON and verify failure.
  make_venv_python_stub 0 no_results
  run bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"no results"* ]]
}

@test "fails when mutation score is below threshold" {
  #R020-T01: Simulate stats with score below threshold and verify failure.
  make_venv_python_stub 0 pass 80 20 100
  run bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"Mutation score"* ]]
}

@test "passes when mutation score meets threshold" {
  #R020-T02: Simulate stats with score at or above threshold and verify pass.
  make_venv_python_stub 0 pass 90 10 100
  run bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"✅ PASS:"* ]]
}

@test "fails when mutator coverage is below threshold" {
  #R022-T01: Simulate low coverage with high score and verify coverage failure.
  make_venv_python_stub 0 pass 80 20 200
  run env MUTATOR_COVERAGE_THRESHOLD=90 bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"Mutator coverage"* ]]
}

@test "passes when mutator coverage meets threshold" {
  #R022-T02: Simulate coverage at or above threshold and verify pass.
  make_venv_python_stub 0 pass 90 10 100
  run bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  [ "$status" -eq 0 ]
}

@test "honors custom mutation score threshold" {
  #R020-T03: Verify custom MUTATION_SCORE_THRESHOLD is applied.
  make_venv_python_stub 0 pass 60 40 100
  run env MUTATION_SCORE_THRESHOLD=50 bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  [ "$status" -eq 0 ]
  run env MUTATION_SCORE_THRESHOLD=70 bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  [ "$status" -ne 0 ]
}

@test "records excluded files in summary" {
  #R025-T01: Set MUTATION_EXCLUDE_FILES and verify summary JSON contains them.
  make_venv_python_stub 0 pass 90 10 100
  run env MUTATION_EXCLUDE_FILES="matchy/api.py,matchy/settings.py" MUTATION_SCORE_THRESHOLD=90 bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  [ "$status" -eq 0 ]
  run python3 -c "
import json
from pathlib import Path
data = json.loads(Path('${FIXTURE_ROOT}/.security-reports/mutation-summary.json').read_text())
assert data['excluded_files'] == ['matchy/api.py', 'matchy/settings.py']
"
}

@test "records empty excluded files by default" {
  #R025-T02: Verify default exclusion list is empty in summary JSON.
  run bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  run python3 -c "
import json
from pathlib import Path
data = json.loads(Path('${FIXTURE_ROOT}/.security-reports/mutation-summary.json').read_text())
assert data['excluded_files'] == []
"
}

@test "mutation summary contains required fields" {
  #R030-T02: Verify JSON contains required fields.
  run bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  run python3 -c "
import json
from pathlib import Path
data = json.loads(Path('${FIXTURE_ROOT}/.security-reports/mutation-summary.json').read_text())
for key in ('total','killed','survived','score','mutator_coverage','threshold','coverage_threshold','gate_failed','by_module'):
    assert key in data
"
}

@test "fails with timeout message when mutmut exceeds timeout" {
  #R040-T01: Simulate mutmut exceeding timeout and verify timeout failure message.
  make_venv_python_stub 0 timeout
  run env MUTATION_TIMEOUT_SECONDS=1 bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"timed out"* ]]
}

@test "includes scoring_core contract tests in mutmut pytest scope" {
  #R045-T01: Verify pyproject lists tests/py/test_scoring_core.py in mutmut.tests_dir.
  run grep -F 'tests/py/test_scoring_core.py' "$(repo_root)/pyproject.toml"
  [ "$status" -eq 0 ]
}

@test "maps scoring_core mutants to scoring_core tests in mutmut stats" {
  #R045-T02: Verify exported mutmut stats reference scoring_core tests.
  make_venv_python_stub 0 pass 90 10 100
  run bash "${FIXTURE_ROOT}/10_run_mutation_tests.sh"
  [ "$status" -eq 0 ]
  run python3 -c "
import json
from pathlib import Path
stats = json.loads(Path('${FIXTURE_ROOT}/.security-reports/mutmut-cicd-stats.json').read_text())
modules = stats.get('modules', {})
scoring = modules.get('matchy.scoring_core', {})
tests = scoring.get('tests', {})
assert any('test_scoring_core.py' in name for name in tests)
"
  [ "$status" -eq 0 ]
}
