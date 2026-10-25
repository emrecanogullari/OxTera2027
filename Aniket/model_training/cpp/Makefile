# C++ predictor. Models come from ../4_export_cpp.py (python 4_export_cpp.py in model_training/ first).
# No -ffast-math: missing features are NaN.
CXX ?= c++
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -pedantic

# Some macOS Command Line Tools installs lack the toolchain's C++ standard headers; use the SDK's copy then.
ifeq ($(shell echo '\#include <vector>' | $(CXX) -x c++ -std=c++17 -fsyntax-only - 2>/dev/null && echo ok),)
  CXXFLAGS += -isystem $(shell xcrun --show-sdk-path 2>/dev/null)/usr/include/c++/v1
endif

.PHONY: test bench clean

oracle_predict: oracle_predict.cpp oracle_model.hpp
	$(CXX) $(CXXFLAGS) -o $@ oracle_predict.cpp

test: oracle_predict
	@for s in bullet blitz classical; do ./oracle_predict models/$$s.txt tests/$$s.csv --check || exit 1; done

bench: oracle_predict
	@for s in bullet blitz classical; do ./oracle_predict models/$$s.txt tests/$$s.csv --bench; done

clean:
	rm -f oracle_predict
