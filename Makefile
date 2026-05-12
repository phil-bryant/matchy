SHELL := /bin/bash

#R001: Declare user-facing orchestration targets.
.PHONY: help build test run sast av clean \
	verify-traceability install-prerequisites create-venv load-requirements \
	unit-tests security-checks av-checks

#R001: Print discoverable help for top-level targets.
help:
	@echo "Targets:"
	@echo "  make build   - Verify scripts and local structure"
	@echo "  make test    - Run shell tests under testing/"
	@echo "  make run     - Launch Matchy API server"
	@echo "  make sast    - Run static/security checks"
	@echo "  make av      - Run antivirus checks"
	@echo "  make clean   - Remove local generated artifacts"

#R005: Keep build verification deterministic and lightweight.
build:
	@test -f "pyproject.toml"
	@test -f "matchy/api.py"
	@echo "Build checks passed."

#R010: Route test lane through 04_run_unit_tests.sh.
test:
	@./04_run_unit_tests.sh

#R015: Route run lane through 07_run_matchy_api.py.
run:
	@./07_run_matchy_api.py

#R020: Route security and AV lanes through numbered scripts.
sast:
	@./05_run_security_checks.sh

av:
	@./06_run_av_checks.sh

#R025: Provide setup/maintenance alias targets for numbered scripts.
verify-traceability:
	@./00_verify_requirements_traceability.sh

install-prerequisites:
	@./01_install_prerequisites.sh

create-venv:
	@./02_create_venv.sh

load-requirements:
	@./03_load_requirements.sh

unit-tests:
	@./04_run_unit_tests.sh

security-checks:
	@./05_run_security_checks.sh

av-checks:
	@./06_run_av_checks.sh

#R030: Keep clean idempotent and safe for local artifacts.
clean:
	@mkdir -p "$$HOME/.Trash"
	@for p in .security-reports .pytest_cache __pycache__ build dist .mypy_cache; do \
		if [ -e "$$p" ]; then \
			mv "$$p" "$$HOME/.Trash/$${p}-$$(date +%s)"; \
		fi; \
	done
	@echo "Clean complete."
