cmake_minimum_required(VERSION 3.17)
project(RecompDevModularHarnessPoC VERSION 0.1 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(OUT_DIR "${CMAKE_BINARY_DIR}/bin")
function(poc_module TARGET SOURCE)
 add_library(${TARGET} SHARED "plugins/${SOURCE}")
 target_include_directories(${TARGET} PRIVATE "${CMAKE_SOURCE_DIR}/include")
 set_target_properties(${TARGET} PROPERTIES PREFIX "" OUTPUT_NAME "${TARGET}" RUNTIME_OUTPUT_DIRECTORY "${OUT_DIR}" LIBRARY_OUTPUT_DIRECTORY "${OUT_DIR}")
 if(MSVC)
   target_compile_options(${TARGET} PRIVATE /W3 /EHsc)
 else()
   target_compile_options(${TARGET} PRIVATE -Wall -Wextra -Wpedantic)
 endif()
endfunction()
poc_module(rd_machine_sms machine_sms.cpp)
target_sources(rd_machine_sms PRIVATE vendor/RecompDev-v0445/systems/mastersystem/runtime.cpp)
target_include_directories(rd_machine_sms PRIVATE "${CMAKE_SOURCE_DIR}/vendor/RecompDev-v0445")
poc_module(rd_machine_synthetic machine_synthetic.cpp)
poc_module(rd_cpu_z80 cpu_z80.cpp)
poc_module(rd_game_fixture game_fixture.cpp)
poc_module(rd_game_probe game_probe.cpp)
# Generated owner code is independent of the shipped synthetic regression game.
# EXCLUDE_FROM_ALL: not compiled until the owner supplies verified export evidence.
add_library(rd_game_owner SHARED EXCLUDE_FROM_ALL owner-generated/rd_game_owner.cpp)
target_include_directories(rd_game_owner PRIVATE include vendor/RecompDev-v0445)
set_target_properties(rd_game_owner PROPERTIES PREFIX "" OUTPUT_NAME "rd_game_owner" RUNTIME_OUTPUT_DIRECTORY "${OUT_DIR}" LIBRARY_OUTPUT_DIRECTORY "${OUT_DIR}")
poc_module(rd_discovery_jsonl discovery_jsonl.cpp)
poc_module(rd_display_ppm display_ppm.cpp)
poc_module(rd_audio_wav audio_wav.cpp)
poc_module(rd_input_fixed input_fixed.cpp)
add_executable(RecompDevHarness src/main.cpp)
target_include_directories(RecompDevHarness PRIVATE include)
set_target_properties(RecompDevHarness PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${OUT_DIR}")
if(CMAKE_DL_LIBS)
 target_link_libraries(RecompDevHarness PRIVATE ${CMAKE_DL_LIBS})
endif()
if(MSVC)
 target_compile_options(RecompDevHarness PRIVATE /W3 /EHsc)
else()
 target_compile_options(RecompDevHarness PRIVATE -Wall -Wextra -Wpedantic)
endif()
# Cross-platform headless tests; on Windows these run with actual DLLs.
enable_testing()
file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/reports")
add_test(NAME modules_load COMMAND $<TARGET_FILE:RecompDevHarness> --list --plugin-dir $<TARGET_FILE_DIR:RecompDevHarness>)
add_test(NAME hybrid_main_parity COMMAND $<TARGET_FILE:RecompDevHarness> --validate --plugin-dir $<TARGET_FILE_DIR:RecompDevHarness> --out "${CMAKE_BINARY_DIR}/reports/main")
add_test(NAME hybrid_bank2_parity COMMAND $<TARGET_FILE:RecompDevHarness> --validate --case bank2 --plugin-dir $<TARGET_FILE_DIR:RecompDevHarness> --out "${CMAKE_BINARY_DIR}/reports/bank2")
add_test(NAME hybrid_input_parity COMMAND $<TARGET_FILE:RecompDevHarness> --validate --buttons 0 --plugin-dir $<TARGET_FILE_DIR:RecompDevHarness> --out "${CMAKE_BINARY_DIR}/reports/input")
add_test(NAME alternate_machine_parity COMMAND $<TARGET_FILE:RecompDevHarness> --machine rd_machine_synthetic --validate --plugin-dir $<TARGET_FILE_DIR:RecompDevHarness> --out "${CMAKE_BINARY_DIR}/reports/alternate")
add_test(NAME wrong_plugin_kind_rejected COMMAND $<TARGET_FILE:RecompDevHarness> --cpu rd_game_fixture --plugin-dir $<TARGET_FILE_DIR:RecompDevHarness> --out "${CMAKE_BINARY_DIR}/reports/invalid")
set_tests_properties(wrong_plugin_kind_rejected PROPERTIES WILL_FAIL TRUE)
add_test(NAME native_only_single_block COMMAND $<TARGET_FILE:RecompDevHarness> --no-fallback --steps 1 --plugin-dir $<TARGET_FILE_DIR:RecompDevHarness> --out "${CMAKE_BINARY_DIR}/reports/native_only")
add_test(NAME native_only_unresolved_rejected COMMAND $<TARGET_FILE:RecompDevHarness> --no-fallback --plugin-dir $<TARGET_FILE_DIR:RecompDevHarness> --out "${CMAKE_BINARY_DIR}/reports/rejected")
set_tests_properties(native_only_unresolved_rejected PROPERTIES WILL_FAIL TRUE)
add_test(NAME compiled_byte_mismatch_rejected COMMAND $<TARGET_FILE:RecompDevHarness> --corrupt-fixture --plugin-dir $<TARGET_FILE_DIR:RecompDevHarness> --out "${CMAKE_BINARY_DIR}/reports/corrupt")
set_tests_properties(compiled_byte_mismatch_rejected PROPERTIES WILL_FAIL TRUE)
add_test(NAME unsupported_opcode_rejected COMMAND $<TARGET_FILE:RecompDevHarness> --unsupported --plugin-dir $<TARGET_FILE_DIR:RecompDevHarness> --out "${CMAKE_BINARY_DIR}/reports/unsupported")
set_tests_properties(unsupported_opcode_rejected PROPERTIES WILL_FAIL TRUE)
find_package(Python3 COMPONENTS Interpreter QUIET)
if(Python3_Interpreter_FOUND)
 add_test(NAME inspect_generated_reports COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/tests/inspect.py" "${CMAKE_BINARY_DIR}/reports")
 set_tests_properties(inspect_generated_reports PROPERTIES DEPENDS "hybrid_main_parity;hybrid_bank2_parity;hybrid_input_parity;native_only_single_block;alternate_machine_parity")
 add_test(NAME export_discovery_sidecar COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/tests/test_sidecar.py" "${CMAKE_SOURCE_DIR}" "${CMAKE_BINARY_DIR}/reports")
 set_tests_properties(export_discovery_sidecar PROPERTIES DEPENDS "hybrid_main_parity")
endif()

# v0.2: real RecompDev v0.4.0.45 P-code verified/lowered game DLL.
# This is source-created synthetic acceptance evidence. Real owner exports are
# substituted through tools/build_pcode_plugin.py, then rebuilding this DLL.
add_library(rd_game_recomp_v0445 SHARED generated/rd_game_recomp_v0445.cpp)
target_include_directories(rd_game_recomp_v0445 PRIVATE include vendor/RecompDev-v0445)
set_target_properties(rd_game_recomp_v0445 PROPERTIES PREFIX "" OUTPUT_NAME "rd_game_recomp_v0445"
  RUNTIME_OUTPUT_DIRECTORY "${OUT_DIR}" LIBRARY_OUTPUT_DIRECTORY "${OUT_DIR}")
if(MSVC)
 target_compile_options(rd_game_recomp_v0445 PRIVATE /W3 /EHsc)
else()
 target_compile_options(rd_game_recomp_v0445 PRIVATE -Wall -Wextra -Wpedantic)
endif()

# Cross-platform proof of real production P-code generator -> shared library ->
# bank-aware harness -> interpreter fallback -> native resume.
add_test(NAME production_pcode_hybrid_parity COMMAND $<TARGET_FILE:RecompDevHarness>
  --plugin-dir $<TARGET_FILE_DIR:RecompDevHarness> --game rd_game_recomp_v0445
  --case rom --rom "${CMAKE_SOURCE_DIR}/examples/recomp-pcode/synthetic.sms"
  --validate --out "${CMAKE_BINARY_DIR}/reports/production_pcode")
add_test(NAME production_pcode_native_one COMMAND $<TARGET_FILE:RecompDevHarness>
  --plugin-dir $<TARGET_FILE_DIR:RecompDevHarness> --game rd_game_recomp_v0445
  --case rom --rom "${CMAKE_SOURCE_DIR}/examples/recomp-pcode/synthetic.sms"
  --no-fallback --steps 1 --out "${CMAKE_BINARY_DIR}/reports/production_native_one")
add_test(NAME production_pcode_native_only_rejects_untranslated COMMAND $<TARGET_FILE:RecompDevHarness>
  --plugin-dir $<TARGET_FILE_DIR:RecompDevHarness> --game rd_game_recomp_v0445
  --case rom --rom "${CMAKE_SOURCE_DIR}/examples/recomp-pcode/synthetic.sms"
  --no-fallback --out "${CMAKE_BINARY_DIR}/reports/production_missing")
set_tests_properties(production_pcode_native_only_rejects_untranslated PROPERTIES WILL_FAIL TRUE)
if(Python3_Interpreter_FOUND)
 add_test(NAME production_pcode_generated_evidence COMMAND "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/tests/test_generated_pcode.py" "${CMAKE_SOURCE_DIR}"
  "${CMAKE_BINARY_DIR}/reports" "$<TARGET_FILE:RecompDevHarness>" "$<TARGET_FILE_DIR:RecompDevHarness>")
 set_tests_properties(production_pcode_generated_evidence PROPERTIES DEPENDS production_pcode_hybrid_parity)
endif()
add_executable(poc_sha256_vectors tests/sha256_vectors.cpp)
target_include_directories(poc_sha256_vectors PRIVATE include)
add_test(NAME source_sha256_vectors COMMAND $<TARGET_FILE:poc_sha256_vectors>)
add_test(NAME production_pcode_alternate_machine COMMAND $<TARGET_FILE:RecompDevHarness>
 --plugin-dir $<TARGET_FILE_DIR:RecompDevHarness> --game rd_game_recomp_v0445
 --machine rd_machine_synthetic --case rom
 --rom "${CMAKE_SOURCE_DIR}/examples/recomp-pcode/synthetic.sms"
 --validate --out "${CMAKE_BINARY_DIR}/reports/production_alternate")
if(Python3_Interpreter_FOUND)
 set_tests_properties(production_pcode_generated_evidence PROPERTIES DEPENDS "production_pcode_hybrid_parity;production_pcode_alternate_machine")
endif()

# v0.3: source-bound real ROM probe, safe incomplete-stop reporting and new catalogue bridge.
if(Python3_Interpreter_FOUND)
 add_test(NAME real_rom_probe_sidecar COMMAND "${Python3_EXECUTABLE}"
   "${CMAKE_SOURCE_DIR}/tests/test_real_rom_bridge.py" "${CMAKE_SOURCE_DIR}"
   "$<TARGET_FILE:RecompDevHarness>" "$<TARGET_FILE_DIR:RecompDevHarness>")
 set_tests_properties(real_rom_probe_sidecar PROPERTIES DEPENDS production_pcode_hybrid_parity)
endif()
