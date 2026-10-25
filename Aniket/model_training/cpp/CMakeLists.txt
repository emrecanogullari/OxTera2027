# Cross-platform build (Windows, Linux, macOS). The Makefile does the same on macOS / Linux.
#   cmake -S . -B build && cmake --build build --config Release
# Result: build/oracle_predict (or build\Release\oracle_predict.exe with Visual Studio)
cmake_minimum_required(VERSION 3.15)
project(oracle_predict CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release)
endif()

add_executable(oracle_predict oracle_predict.cpp)  # no -ffast-math: missing features are NaN

if(MSVC)
  # static runtime: the .exe runs without installing the Visual C++ redistributable
  set_property(TARGET oracle_predict PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
  target_compile_options(oracle_predict PRIVATE /W4 /EHsc)
else()
  target_compile_options(oracle_predict PRIVATE -Wall -Wextra -pedantic)
  if(MINGW)
    target_link_options(oracle_predict PRIVATE -static)  # no MinGW DLLs needed next to the .exe
  endif()
endif()

# Some macOS Command Line Tools installs lack the toolchain's C++ standard headers; use the SDK's copy then.
include(CheckIncludeFileCXX)
check_include_file_cxx(vector HAVE_STD_HEADERS)
if(APPLE AND NOT HAVE_STD_HEADERS)
  execute_process(COMMAND xcrun --show-sdk-path OUTPUT_VARIABLE SDK OUTPUT_STRIP_TRAILING_WHITESPACE)
  target_include_directories(oracle_predict SYSTEM PRIVATE "${SDK}/usr/include/c++/v1")
endif()
