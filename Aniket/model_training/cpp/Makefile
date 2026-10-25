# C++ predictor. Models come from ../4_export_cpp.py (python 4_export_cpp.py in model_training/ first).
# No -ffast-math: missing features are NaN.
CXX ?= c++
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -pedantic

# Some macOS Command Line Tools installs lack the toolchain's C++ standard headers; use the SDK's copy then.
# Skip on Windows / when xcrun is absent (Chocolatey make still runs this shell probe).
UNAME_S := $(shell uname -s 2>/dev/null)
ifeq ($(UNAME_S),Darwin)
  ifeq ($(shell echo '\#include <vector>' | $(CXX) -x c++ -std=c++17 -fsyntax-only - 2>/dev/null && echo ok),)
    CXXFLAGS += -isystem $(shell xcrun --show-sdk-path 2>/dev/null)/usr/include/c++/v1
  endif
endif

# Windows MinGW produces oracle_predict.exe; keep a stable target name for make.
ifeq ($(OS),Windows_NT)
  ORACLE_BIN := oracle_predict.exe
else
  ORACLE_BIN := oracle_predict
endif

.PHONY: test bench clean

$(ORACLE_BIN): oracle_predict.cpp oracle_model.hpp
	$(CXX) $(CXXFLAGS) -o $@ oracle_predict.cpp

oracle_predict: $(ORACLE_BIN)

test: oracle_predict
	@for s in bullet blitz classical; do ./oracle_predict models/$$s.txt tests/$$s.csv --check || exit 1; done

bench: oracle_predict
	@for s in bullet blitz classical; do ./oracle_predict models/$$s.txt tests/$$s.csv --bench; done

clean:
	rm -f oracle_predict
