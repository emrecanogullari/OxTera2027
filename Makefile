# Move-choice engine. Paths are based on this file, so the same targets
# work from OxTera2027 and from the OxHack2027 folder.

OXTERA := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))

ifneq ($(wildcard /Library/Developer/CommandLineTools/.),)
  export DEVELOPER_DIR ?= /Library/Developer/CommandLineTools
endif

CXX ?= c++
CXXFLAGS = -O3 -std=c++17 -Wall -Wextra -I$(OXTERA)/Emre/src -pthread
LDFLAGS = -lcurl -pthread

SRC = $(OXTERA)/Emre/src/board.cpp $(OXTERA)/Emre/src/candidates.cpp $(OXTERA)/Emre/src/judge.cpp $(OXTERA)/Emre/src/score.cpp $(OXTERA)/Emre/src/stream.cpp $(OXTERA)/Emre/src/readout.cpp $(OXTERA)/Emre/src/demo.cpp
OBJ = $(SRC:$(OXTERA)/Emre/src/%.cpp=$(OXTERA)/Emre/build/%.o)

.PHONY: all test examples replay watch pgn fetch clean

all: $(OXTERA)/Emre/build/engine

test: $(OXTERA)/Emre/build/test_engine
	$(OXTERA)/Emre/build/test_engine

examples: $(OXTERA)/Emre/build/engine
	$(OXTERA)/Emre/build/engine examples

replay: $(OXTERA)/Emre/build/engine
	$(OXTERA)/Emre/build/engine replay

watch: $(OXTERA)/Emre/build/engine
	@test -n "$(GAME_ID)" || { echo "Usage: make watch GAME_ID=gameid"; exit 1; }
	$(OXTERA)/Emre/build/engine watch $(GAME_ID)

pgn: $(OXTERA)/Emre/build/engine
	@test -n "$(PGN)" || { echo "Usage: make pgn PGN=path/to/game.pgn"; exit 1; }
	$(OXTERA)/Emre/build/engine pgn $(PGN)

fetch: $(OXTERA)/Emre/build/engine
	@test -n "$(GAME_ID)" || { echo "Usage: make fetch GAME_ID=gameid"; exit 1; }
	$(OXTERA)/Emre/build/engine fetch $(GAME_ID)

$(OXTERA)/Emre/build/engine: $(OBJ) $(OXTERA)/Emre/build/main.o
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

$(OXTERA)/Emre/build/test_engine: $(OBJ) $(OXTERA)/Emre/build/test_engine.o
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

$(OXTERA)/Emre/build/%.o: $(OXTERA)/Emre/src/%.cpp
	@mkdir -p $(OXTERA)/Emre/build
	$(CXX) $(CXXFLAGS) -c -o $@ $<

clean:
	rm -rf $(OXTERA)/Emre/build
