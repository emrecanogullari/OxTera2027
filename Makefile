# Move-choice engine. Paths are based on this file, so the same targets
# work from OxTera2027 and from the OxHack2027 folder.

OXTERA := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
EMRE := $(OXTERA)/Emre

ifneq ($(wildcard /Library/Developer/CommandLineTools/.),)
  export DEVELOPER_DIR ?= /Library/Developer/CommandLineTools
endif

CXX ?= c++
CXXFLAGS = -O3 -std=c++17 -Wall -Wextra -pthread \
	-I$(EMRE)/src/board \
	-I$(EMRE)/src/candidates \
	-I$(EMRE)/src/judge \
	-I$(EMRE)/src/score \
	-I$(EMRE)/src/stream \
	-I$(EMRE)/src/readout \
	-I$(EMRE)/src/demo
LDFLAGS = -lcurl -pthread

SRC = $(EMRE)/src/board/board.cpp \
	$(EMRE)/src/candidates/candidates.cpp \
	$(EMRE)/src/judge/judge.cpp \
	$(EMRE)/src/score/score.cpp \
	$(EMRE)/src/stream/stream.cpp \
	$(EMRE)/src/readout/readout.cpp \
	$(EMRE)/src/demo/demo.cpp
OBJ = $(SRC:$(EMRE)/src/%.cpp=$(EMRE)/build/%.o)

.PHONY: all test examples replay watch pgn fetch clean

all: $(EMRE)/build/engine

test: $(EMRE)/build/test_engine
	$(EMRE)/build/test_engine

examples: $(EMRE)/build/engine
	$(EMRE)/build/engine examples

replay: $(EMRE)/build/engine
	$(EMRE)/build/engine replay

watch: $(EMRE)/build/engine
	@test -n "$(GAME_ID)" || { echo "Usage: make watch GAME_ID=gameid"; exit 1; }
	$(EMRE)/build/engine watch $(GAME_ID)

pgn: $(EMRE)/build/engine
	@test -n "$(PGN)" || { echo "Usage: make pgn PGN=path/to/game.pgn"; exit 1; }
	$(EMRE)/build/engine pgn $(PGN)

fetch: $(EMRE)/build/engine
	@test -n "$(GAME_ID)" || { echo "Usage: make fetch GAME_ID=gameid"; exit 1; }
	$(EMRE)/build/engine fetch $(GAME_ID)

$(EMRE)/build/engine: $(OBJ) $(EMRE)/build/app/main.o
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

$(EMRE)/build/test_engine: $(OBJ) $(EMRE)/build/tests/test_engine.o
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

$(EMRE)/build/%.o: $(EMRE)/src/%.cpp
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -c -o $@ $<

$(EMRE)/build/tests/test_engine.o: $(EMRE)/tests/test_engine.cpp
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -c -o $@ $<

clean:
	rm -rf $(EMRE)/build
