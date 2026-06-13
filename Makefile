SHELL := /bin/zsh

#R001: Configurable artifact and path variables consumed by every target below.
MATCHY_REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
CORE_DIR := $(MATCHY_REPO_ROOT)/src/core
CORE_BUILD_DIR ?= $(CORE_DIR)/build
CORE_BUILD_TYPE ?= RelWithDebInfo
API_BIN := $(CORE_BUILD_DIR)/matchy_api
DRIVER_BIN := $(CORE_BUILD_DIR)/matchy_driver
NCPU := $(shell sysctl -n hw.ncpu)

.DEFAULT_GOAL := help

#R008: Orchestration targets are phony so same-named files never shadow them.
.PHONY: help core test sanitize parity run driver test-all clean

#R009: Discoverable developer entrypoints.
help:
	@echo "Targets:"
	@echo "  make core     - Build the portable C++ core (cmake, $(CORE_BUILD_TYPE))"
	@echo "  make test     - Run the C++ core Catch2 unit lane (t15)"
	@echo "  make sanitize - Run the C++ core suite under ASan+UBSan (t16)"
	@echo "  make parity   - Run the Python vs C++ oracle parity lane (t17)"
	@echo "  make run      - Build the core and launch the C++ matchy API on :8790"
	@echo "  make driver   - Build the core and run the C++ matchy driver once"
	@echo "  make test-all - Run every numbered test lane in parallel"
	@echo "  make clean    - Move generated core build trees to ~/.Trash"

#R003: Build the portable C++ core deterministically through cmake.
core:
	@cmake -S "$(CORE_DIR)" -B "$(CORE_BUILD_DIR)" -DCMAKE_BUILD_TYPE=$(CORE_BUILD_TYPE) >/dev/null
	@cmake --build "$(CORE_BUILD_DIR)" -j $(NCPU)

test:
	@"$(MATCHY_REPO_ROOT)/tests/t15_run_cpp_core_unit_tests.sh"

sanitize:
	@"$(MATCHY_REPO_ROOT)/tests/t16_run_cpp_core_sanitizer_tests.sh"

parity:
	@"$(MATCHY_REPO_ROOT)/tests/t17_run_python_cpp_oracle_parity_test.sh"

run: core
	@"$(API_BIN)"

driver: core
	@"$(DRIVER_BIN)" --once

test-all:
	@"$(MATCHY_REPO_ROOT)/05_run_all_tests_parallel.sh"

#R002: Preserve build trees in ~/.Trash with a timestamp instead of deleting them.
clean:
	@timestamp=$$(date +%Y-%m-%d-%H.%M.%S); \
	trash_dir="$$HOME/.Trash/matchy_core_builds_$$timestamp"; \
	moved=0; \
	for tree in "$(CORE_DIR)/build" "$(CORE_DIR)/build-asan" "$(CORE_DIR)/build-m1"; do \
		if [ -d "$$tree" ]; then \
			mkdir -p "$$trash_dir"; \
			mv "$$tree" "$$trash_dir/"; \
			moved=1; \
		fi; \
	done; \
	if [ "$$moved" = "1" ]; then \
		echo "Moved core build trees to $$trash_dir"; \
	else \
		echo "No core build trees to clean"; \
	fi
