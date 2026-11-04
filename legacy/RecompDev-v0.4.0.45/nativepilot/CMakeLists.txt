cmake_minimum_required(VERSION 3.17)
project(RecompDevNativePilot VERSION 0.4.0.45 LANGUAGES CXX)
add_executable(RecompDevNativePilot main.cpp runtime.cpp translated.cpp)
target_compile_features(RecompDevNativePilot PRIVATE cxx_std_17)
if(MSVC)
 target_compile_options(RecompDevNativePilot PRIVATE /W3 /EHsc /bigobj)
else()
 target_compile_options(RecompDevNativePilot PRIVATE -Wall -Wextra)
endif()

# Standalone interactive/headless host compiled from exactly the same
# source-attested translated.cpp as the diagnostic pilot. No emulator fallback.
add_executable(RecompDevNativeApp interactive.cpp runtime.cpp translated.cpp)
target_compile_features(RecompDevNativeApp PRIVATE cxx_std_17)
if(WIN32)
 target_link_libraries(RecompDevNativeApp PRIVATE user32 gdi32 winmm)
endif()
if(MSVC)
 target_compile_options(RecompDevNativeApp PRIVATE /W3 /EHsc /bigobj)
else()
 target_compile_options(RecompDevNativeApp PRIVATE -Wall -Wextra)
endif()

# Generated native binaries must reserve adequate *host* stack on Windows.
# Sonic SMS's source-verified native translation reproducibly crashed under
# Windows' default 1 MiB PE stack reserve (0xC00000FD); the owner-side probe
# successfully ran 12,711 translated steps after raising only this PE header
# value to 8 MiB. This is not guest Z80 stack emulation, and is not ROM-specific.
# Keep Linux/macOS defaults. Linker controls are intentional and target-scoped.
if(WIN32)
 if(MSVC)
  target_link_options(RecompDevNativePilot PRIVATE /STACK:8388608)
  target_link_options(RecompDevNativeApp PRIVATE /STACK:8388608)
 elseif(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
  target_link_options(RecompDevNativePilot PRIVATE "LINKER:--stack,8388608")
  target_link_options(RecompDevNativeApp PRIVATE "LINKER:--stack,8388608")
 endif()
endif()
