CXX ?= c++
CXXFLAGS ?= -O2 -std=c++17 -Wall -Wextra
SRC := src/pgn.cpp src/main.cpp
OUT := build/ingest

.PHONY: all clean

all: $(OUT)

$(OUT): $(SRC) src/pgn.hpp
	mkdir -p build
	$(CXX) $(CXXFLAGS) -o $@ $(SRC)

clean:
	rm -rf build
