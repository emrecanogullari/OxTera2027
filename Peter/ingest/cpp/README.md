# C++ PGN ingest

Same job as `ingest/ingest.py`: read Lichess PGN on stdin, keep rated blitz
`180+0` / `300+0`, Elo 1000–2200, `Normal` games with `[%clk]` and `[%eval]`,
write `games.csv` and `moves.csv`.

## Files

| File | What to look at |
|---|---|
| `src/pgn.hpp` | Types + function declarations (`#pragma once`) |
| `src/pgn.cpp` | Parser: tags, filters, SAN + clock + eval |
| `src/main.cpp` | CLI, CSV writers, `std::cin` |

Python `ingest.py` stays as a readable spec and as unit tests. The live dump path uses this binary.

## Build (Windows, VS 2017+)

From `Peter/ingest/cpp`:

```powershell
powershell -File compile.ps1
```

That produces `build/ingest.exe`.

On macOS/Linux:

```bash
make
```

## Run

Create the output folder first (`ofstream` will not create parent directories).

```powershell
New-Item -ItemType Directory -Force data
Get-Content ..\tests\fixtures\sample.pgn | .\build\ingest.exe --out-dir data --max-games 10
```

Monthly dump (zstd on PATH):

```powershell
zstd -dc path\to\lichess_db_standard_rated_2026-09.pgn.zst | .\build\ingest.exe --out-dir data --max-games 1000
```

Or from `Peter/`:

```powershell
python ingest/stream_lichess.py --out-dir data --max-games 1000
```

`stream_lichess.py` decompresses the dump and pipes PGN into this executable.

## C++ notes for this parser

- `std::string` owns text; compare with `==` / `.find()`.
- `std::unordered_map` / `unordered_set` are hash tables (Python `dict` / `set`).
- `std::optional` is unused here: a `bool keep_headers(..., GameRow* out)` writes through a pointer, which is the C-style pattern you will see a lot.
- `std::function` in `ingest_stream` is a callback. The lambda in `main.cpp` writes each kept game immediately so we do not store 1000 games in RAM first.
- `std::isspace(c)` needs `static_cast<unsigned char>(c)` so high-bit UTF-8 bytes do not crash.
- MSVC 2017 is C++17: no `std::filesystem` in this tool, no ranges.
