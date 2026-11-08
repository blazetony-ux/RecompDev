cmake_minimum_required(VERSION 3.17)
project(RecompDevModularConsolidation VERSION 0.4.9 LANGUAGES CXX)
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
# Independent active SMS state/runtime DLL. Its source and ABI no longer compile
# from frozen legacy or baselines directories.
add_library(rd_sms_native_runtime SHARED ../runtime_sms/src/runtime.cpp)
target_compile_definitions(rd_sms_native_runtime PRIVATE RD_SMS_NATIVE_BUILD)
target_include_directories(rd_sms_native_runtime PUBLIC ../runtime_sms/include)
target_include_directories(rd_sms_native_runtime PRIVATE ../video_sms/include)
target_link_libraries(rd_sms_native_runtime PRIVATE rd_video_sms_mode4)
set_target_properties(rd_sms_native_runtime PROPERTIES PREFIX "" OUTPUT_NAME "rd_sms_native_runtime"
 RUNTIME_OUTPUT_DIRECTORY "${OUT_DIR}" LIBRARY_OUTPUT_DIRECTORY "${OUT_DIR}")
poc_module(rd_machine_sms machine_sms.cpp)
target_include_directories(rd_machine_sms PRIVATE ../runtime_sms/include ../video_sms/include)
target_link_libraries(rd_machine_sms PRIVATE rd_sms_native_runtime rd_video_sms_mode4)
poc_module(rd_machine_synthetic machine_synthetic.cpp)
poc_module(rd_cpu_z80 cpu_z80.cpp)
target_include_directories(rd_cpu_z80 PRIVATE ../runtime_sms/templates)
poc_module(rd_game_fixture game_fixture.cpp)
poc_module(rd_game_probe game_probe.cpp)
# Generated owner code is independent of the shipped synthetic regression game.
# EXCLUDE_FROM_ALL: not compiled until the owner supplies verified export evidence.
add_library(rd_game_owner SHARED EXCLUDE_FROM_ALL owner-generated/rd_game_owner.cpp)
target_include_directories(rd_game_owner PRIVATE include ../runtime_sms/templates)
set_target_properties(rd_game_owner PROPERTIES PREFIX "" OUTPUT_NAME "rd_game_owner" RUNTIME_OUTPUT_DIRECTORY "${OUT_DIR}" LIBRARY_OUTPUT_DIRECTORY "${OUT_DIR}")
poc_module(rd_discovery_jsonl discovery_jsonl.cpp)
poc_module(rd_display_ppm display_ppm.cpp)
poc_module(rd_audio_wav audio_wav.cpp)
poc_module(rd_input_fixed input_fixed.cpp)
# The existing validated native P-code game-execution harness is now a shared
# compiled orchestration module used by both the test harness and controller.
# It still loads CPU/machine/game/audio/video/input DLLs through rd_plugin.h.
add_library(rd_native_game_runner STATIC src/runner.cpp)
target_include_directories(rd_native_game_runner PUBLIC include)
if(CMAKE_DL_LIBS)
 target_link_libraries(rd_native_game_runner PUBLIC ${CMAKE_DL_LIBS})
endif()
add_executable(RecompDevHarness src/main.cpp)
target_link_libraries(RecompDevHarness PRIVATE rd_native_game_runner)
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
target_include_directories(rd_game_recomp_v0445 PRIVATE include ../runtime_sms/templates)
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

# v0.4 consolidation gates. The original v0445 source tree is immutable.
# These run against the preserved source tree, not the synthetic v0.3 vendor fork.
if(Python3_Interpreter_FOUND)
 add_test(NAME migration_preservation COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/../migration/test_migration.py" TestPreservation)
 add_test(NAME migration_production_bridge COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/../migration/test_migration.py" TestProductionBridge)
 add_test(NAME migration_catalogue_safety COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/../migration/test_migration.py" TestCatalogueSafety)
 add_test(NAME migration_legacy_regressions COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/../migration/test_migration.py" TestOriginalRegressions)
endif()

# v0.4.1 genuine production-workflow gates (not a reduced interpreter).
if(Python3_Interpreter_FOUND)
 foreach(test_name IN ITEMS
    test_registry_points_to_original_services
    test_real_original_discovery_parity
    test_real_native_preparation_reports_missing_ghidra
    test_no_reuse_of_evidence_folder
    test_bad_plugin_registration_is_rejected
    test_readonly_external_catalogue_snapshotted
    test_full_source_preservation_gate)
  add_test(NAME "v041_${test_name}" COMMAND "${Python3_EXECUTABLE}"
   "${CMAKE_SOURCE_DIR}/../modular/tests/test_integration.py"
   "TestRealLegacyServices.${test_name}")
 endforeach()
endif()

# Protect CI and owner Windows build from indefinite child-process stalls.


# v0.4.2 compiled top-level controller; unlike the standalone test harness it
# owns the real ROM workflow entry point and delegates legacy services safely.
add_executable(RecompDev ../controller/main.cpp ../controller/native_execute.cpp ../controller/native_translate.cpp ../controller/native_job.cpp)
target_include_directories(RecompDev PRIVATE include ../translation_pcode/include)
target_link_libraries(RecompDev PRIVATE rd_native_game_runner)
# Resolve exactly the Python interpreter used by the tests, not an ambiguous py.exe shim.
configure_file("${CMAKE_SOURCE_DIR}/../controller/recompdev_python_config.h.in"
               "${CMAKE_CURRENT_BINARY_DIR}/recompdev_python_config.h" @ONLY)
target_include_directories(RecompDev PRIVATE "${CMAKE_CURRENT_BINARY_DIR}")
set_target_properties(RecompDev PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${OUT_DIR}")
# Build-tree executables also locate the source via an external text pointer.
# Production deployment writes its own pointer in RecompDev-Runtime.
# Multi-config Windows builds place the executable under bin/Release; Linux single-
# config executables are directly under bin. Both must resolve the same source.
if(CMAKE_CONFIGURATION_TYPES)
 file(GENERATE OUTPUT "${OUT_DIR}/$<CONFIG>/source-root.txt" CONTENT "${CMAKE_SOURCE_DIR}/..\n")
else()
 file(GENERATE OUTPUT "${OUT_DIR}/source-root.txt" CONTENT "${CMAKE_SOURCE_DIR}/..\n")
endif()
if(MSVC)
 target_compile_options(RecompDev PRIVATE /W4 /EHsc)
else()
 target_compile_options(RecompDev PRIVATE -Wall -Wextra -Wpedantic)
endif()
if(Python3_Interpreter_FOUND)
 add_test(NAME v042_compiled_controller_version COMMAND $<TARGET_FILE:RecompDev> --version)
 add_test(NAME v042_compiled_controller_registry COMMAND $<TARGET_FILE:RecompDev> --plugins)
 add_test(NAME v042_compiled_controller_e2e COMMAND "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/../modular/tests/test_native_controller.py"
  "$<TARGET_FILE:RecompDev>" "${CMAKE_SOURCE_DIR}/..")
 add_test(NAME v042_recovery_manager COMMAND "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/../modular/tests/test_recovery_manager.py")
endif()

# Automatic evidence-upload ZIP gate. Runs the direct compiled RecompDev.exe.
if(Python3_Interpreter_FOUND)
 add_test(NAME v042_evidence_bundle COMMAND "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/../modular/tests/test_evidence_bundle.py"
  "$<TARGET_FILE:RecompDev>")
endif()

# v0.4.3: real capture review and asset decoder verification; runs without ROMs.
if(Python3_Interpreter_FOUND)
 add_test(NAME v043_hardware_review COMMAND "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/../modular/tests/test_hardware_review.py")
 add_test(NAME v043_compiled_offline_review COMMAND "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/../modular/tests/test_compiled_review.py"
  "$<TARGET_FILE:RecompDev>")
endif()

# v0.4.4: protect the source checkout from Python bytecode produced by tests.
get_property(_recompdev_tests DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" PROPERTY TESTS)
foreach(_t IN LISTS _recompdev_tests)
  set_property(TEST "${_t}" APPEND PROPERTY ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1")
endforeach()
if(Python3_Interpreter_FOUND)
 add_test(NAME v044_workspace_contract COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_SOURCE_DIR}/../workspace/tests/test_workspace.py"
    "$<TARGET_FILE:RecompDev>")
 set_tests_properties(v044_workspace_contract PROPERTIES ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1")
endif()

# v0.4.8: individually buildable CPU/machine-neutral presentation host.
# Reuse the verified legacy OS adapters as source, without editing frozen files.
add_library(rd_runtime_host SHARED ../runtime_host/src/host.cpp)
target_compile_definitions(rd_runtime_host PRIVATE RD_RUNTIME_HOST_BUILD)
target_include_directories(rd_runtime_host PRIVATE ../runtime_host/include ../runtime_sms/include)
set_target_properties(rd_runtime_host PROPERTIES PREFIX "" OUTPUT_NAME "rd_runtime_host"
 RUNTIME_OUTPUT_DIRECTORY "${OUT_DIR}" LIBRARY_OUTPUT_DIRECTORY "${OUT_DIR}")
if(WIN32)
 target_link_libraries(rd_runtime_host PRIVATE user32 gdi32 winmm)
endif()
if(MSVC)
 target_compile_options(rd_runtime_host PRIVATE /W4 /EHsc)
else()
 target_compile_options(rd_runtime_host PRIVATE -Wall -Wextra -Wpedantic)
endif()
add_executable(rd_runtime_host_smoke ../runtime_host/tests/smoke.cpp)
target_include_directories(rd_runtime_host_smoke PRIVATE ../runtime_host/include)
target_link_libraries(rd_runtime_host_smoke PRIVATE rd_runtime_host)
set_target_properties(rd_runtime_host_smoke PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${OUT_DIR}")
add_test(NAME v048_runtime_host_generic_contract COMMAND $<TARGET_FILE:rd_runtime_host_smoke>)
if(Python3_Interpreter_FOUND)
 add_test(NAME v048_runtime_host_generated_native_application COMMAND "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/../runtime_host/tests/test_generated_app.py" "$<TARGET_FILE:rd_runtime_host>" "$<TARGET_FILE:rd_video_sms_mode4>")
 set_tests_properties(v048_runtime_host_generated_native_application PROPERTIES ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1")
endif()

# v0.4.9.2: independent production SMS Mode-4 *video* DLL; CPU-neutral C ABI.
# Do not edit or link original legacy hardware source; stage a thin call boundary.
add_library(rd_video_sms_mode4 SHARED ../video_sms/src/mode4.cpp)
target_compile_definitions(rd_video_sms_mode4 PRIVATE RD_SMS_MODE4_BUILD)
target_include_directories(rd_video_sms_mode4 PUBLIC ../video_sms/include)
set_target_properties(rd_video_sms_mode4 PROPERTIES PREFIX "" OUTPUT_NAME "rd_video_sms_mode4"
 RUNTIME_OUTPUT_DIRECTORY "${OUT_DIR}" LIBRARY_OUTPUT_DIRECTORY "${OUT_DIR}")
if(MSVC)
 target_compile_options(rd_video_sms_mode4 PRIVATE /W4 /EHsc)
else()
 target_compile_options(rd_video_sms_mode4 PRIVATE -Wall -Wextra -Wpedantic)
endif()
add_executable(rd_video_sms_mode4_smoke ../video_sms/tests/smoke.cpp)
target_include_directories(rd_video_sms_mode4_smoke PRIVATE ../video_sms/include ../legacy/RecompDev-v0.4.0.45)
target_link_libraries(rd_video_sms_mode4_smoke PRIVATE rd_video_sms_mode4)
set_target_properties(rd_video_sms_mode4_smoke PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${OUT_DIR}")
add_test(NAME v0492_sms_video_sprite_priority COMMAND $<TARGET_FILE:rd_video_sms_mode4_smoke>)
if(Python3_Interpreter_FOUND)
 add_test(NAME v0492_sms_video_staging COMMAND "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/../video_sms/tests/test_bridge.py")
 set_tests_properties(v0492_sms_video_staging PROPERTIES ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1")
endif()

# v0.4.9.5: controller-only monitor ABI and compiled guest event provider.
if(Python3_EXECUTABLE)
 add_test(NAME v0495_controller_monitor_protocol COMMAND "${Python3_EXECUTABLE}"
  -m unittest discover -s "${CMAKE_SOURCE_DIR}/../execution_monitor/tests" -p test_monitor.py -q)
 set_tests_properties(v0495_controller_monitor_protocol PROPERTIES WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}/.." ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1")
 add_test(NAME v0495_monitor_native_guest_event COMMAND "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/../execution_monitor/tests/test_native_events.py" $<TARGET_FILE:rd_runtime_host> $<TARGET_FILE:rd_video_sms_mode4>)
 set_tests_properties(v0495_monitor_native_guest_event PROPERTIES ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1")
endif()

# v0.4.9.7: Independent native structural discovery providers and an explicit
# compiled-controller path. ABI existing runtime plugin family remains stable.
poc_module(rd_format_sms format_sms.cpp)
poc_module(rd_format_md format_md.cpp)
poc_module(rd_format_ps1 format_ps1.cpp)
target_sources(RecompDev PRIVATE ../controller/native_discovery.cpp)
target_include_directories(RecompDev PRIVATE include ../controller)
if(CMAKE_DL_LIBS)
 target_link_libraries(RecompDev PRIVATE ${CMAKE_DL_LIBS})
endif()
if(Python3_Interpreter_FOUND)
 add_test(NAME v0497_native_discovery_contract COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_SOURCE_DIR}/tests/test_native_discovery.py" "$<TARGET_FILE:RecompDev>" "$<TARGET_FILE_DIR:RecompDev>")
 set_tests_properties(v0497_native_discovery_contract PROPERTIES ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1")
endif()

# v0.4.9.9: direct compiled controller -> preserved generated P-code game DLL,
# source-authenticated native execution, ED/indexed decode and bank-qualified flow.
if(Python3_Interpreter_FOUND)
 add_test(NAME v0499_controller_native_pcode_and_banked_source COMMAND "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/tests/test_controller_native_port.py"
  "$<TARGET_FILE:RecompDev>" "$<TARGET_FILE_DIR:RecompDev>"
  "${CMAKE_SOURCE_DIR}/examples/recomp-pcode/synthetic.sms")
 set_tests_properties(v0499_controller_native_pcode_and_banked_source PROPERTIES
  ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1")
endif()

# v0.4.9.10: real source-attested P-code lowering, executed in an independent
# native translator DLL. The original Ghidra verifier remains the oracle;
# this is not the full legacy runtime / recovery migration.
add_library(rd_translation_pcode SHARED ../translation_pcode/src/translator.cpp)
target_include_directories(rd_translation_pcode PRIVATE include ../translation_pcode/include)
set_target_properties(rd_translation_pcode PROPERTIES PREFIX "" OUTPUT_NAME "rd_translation_pcode"
 RUNTIME_OUTPUT_DIRECTORY "${OUT_DIR}" LIBRARY_OUTPUT_DIRECTORY "${OUT_DIR}")
target_include_directories(RecompDev PRIVATE ../translation_pcode/include)
if(MSVC)
 target_compile_options(rd_translation_pcode PRIVATE /W4 /EHsc)
else()
 target_compile_options(rd_translation_pcode PRIVATE -Wall -Wextra -Wpedantic)
endif()
if(Python3_Interpreter_FOUND)
 add_test(NAME v04910_native_pcode_translation_compile_execute COMMAND "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/../translation_pcode/tests/test_translation.py"
  "$<TARGET_FILE:RecompDev>" "$<TARGET_FILE_DIR:RecompDev>" "${CMAKE_SOURCE_DIR}/..")
 set_tests_properties(v04910_native_pcode_translation_compile_execute PROPERTIES ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1")
endif()

# Source-driven native C++ recovery regression: independently compiled modules,
# mapper-bank flow, loop-state bound and forged source-evidence rejection.
if(Python3_Interpreter_FOUND)
 add_test(NAME v04910_native_banked_source_recovery_compilation COMMAND "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/../translation_pcode/tests/test_source_recovery.py"
  "$<TARGET_FILE:RecompDev>" "$<TARGET_FILE_DIR:RecompDev>" "${CMAKE_SOURCE_DIR}/..")
 set_tests_properties(v04910_native_banked_source_recovery_compilation PROPERTIES ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1")
 add_test(NAME v04910_translation_partition_stability COMMAND "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/../translation_pcode/tests/test_partition_stability.py"
  "$<TARGET_FILE:RecompDev>" "$<TARGET_FILE_DIR:rd_translation_pcode>" "${CMAKE_SOURCE_DIR}/..")
 set_tests_properties(v04910_translation_partition_stability PROPERTIES ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1")
 add_test(NAME v04910_runtime_gap_native_recovery COMMAND "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/../translation_pcode/tests/test_runtime_gap_recovery.py"
  "$<TARGET_FILE:RecompDev>" "$<TARGET_FILE_DIR:rd_translation_pcode>" "${CMAKE_SOURCE_DIR}/..")
 set_tests_properties(v04910_runtime_gap_native_recovery PROPERTIES ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1")
 add_test(NAME v04910_source_lift_block_copy_repeat COMMAND "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/../translation_pcode/tests/test_z80_block_copy_repeat.py"
  "$<TARGET_FILE:RecompDev>" "$<TARGET_FILE_DIR:rd_translation_pcode>" "${CMAKE_SOURCE_DIR}/..")
 set_tests_properties(v04910_source_lift_block_copy_repeat PROPERTIES ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1")
endif()

# v0.4.9.10: compiled production DLL boundary, not the frozen implementation.
add_executable(rd_sms_native_runtime_smoke ../runtime_sms/tests/smoke.cpp)
target_include_directories(rd_sms_native_runtime_smoke PRIVATE ../runtime_sms/include ../video_sms/include ../runtime_host/include)
target_link_libraries(rd_sms_native_runtime_smoke PRIVATE rd_sms_native_runtime rd_video_sms_mode4 rd_runtime_host)
set_target_properties(rd_sms_native_runtime_smoke PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${OUT_DIR}")
add_test(NAME v04910_production_native_sms_runtime_cutover COMMAND $<TARGET_FILE:rd_sms_native_runtime_smoke>)
if(Python3_Interpreter_FOUND)
 add_test(NAME v04910_production_legacy_boundary COMMAND "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/../runtime_sms/tests/test_no_legacy_production.py"
  "${CMAKE_SOURCE_DIR}/..")
 set_tests_properties(v04910_production_legacy_boundary PROPERTIES ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1")
endif()

# v0.4.9.11: controller -> dual optional analysis providers -> reconciled
# boundaries -> compiled native discovery/translation, tested on two distinct
# synthetic ROMs; genuine Ghidra/Rizin and 2 real ROMs remain owner gates.
if(Python3_Interpreter_FOUND)
 add_test(NAME v04911_controller_analysis_recovery_integration COMMAND
  "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/../analysis_integration/tests/test_native_orchestration.py"
  "$<TARGET_FILE:RecompDev>" "$<TARGET_FILE_DIR:rd_translation_pcode>" "${CMAKE_SOURCE_DIR}/..")
 set_tests_properties(v04911_controller_analysis_recovery_integration PROPERTIES TIMEOUT 180)
endif()

# v0.4.9.12: strict independent Rizin output-normalization contract.
# These are parser tests; the preceding native-orchestrate test exercises the
# same adapter through the actual compiled controller process boundary.
if(Python3_Interpreter_FOUND)
 add_test(NAME v04912_rizin_output_compatibility COMMAND
  "${Python3_EXECUTABLE}" -B
  "${CMAKE_SOURCE_DIR}/../analysis_integration/tests/test_rizin_output_compat.py" -q)
 set_tests_properties(v04912_rizin_output_compatibility PROPERTIES
  ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1" TIMEOUT 30)
endif()

# v0.4.9.13 independently maintained external Rizin analyzer provider.
if(Python3_Interpreter_FOUND)
 add_test(NAME v04913_rizin_direct_provider COMMAND
  "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/../analysis_integration/tests/test_rizin_provider.py" -q)
 set_tests_properties(v04913_rizin_direct_provider PROPERTIES TIMEOUT 90)
endif()

# v0.4.9.14: maintained Ghidra evidence + source-bound recovery reuse.
if(Python3_Interpreter_FOUND)
 add_test(NAME v04914_ghidra_recovery_history COMMAND
  "${Python3_EXECUTABLE}" -B
  "${CMAKE_SOURCE_DIR}/../analysis_integration/tests/test_recovery_history.py" -q)
 set_tests_properties(v04914_ghidra_recovery_history PROPERTIES TIMEOUT 60)
endif()

if(Python3_Interpreter_FOUND)
 add_test(NAME v04914_compiled_recovery_history_bridge COMMAND
  "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/../analysis_integration/tests/test_recovery_compiled_bridge.py"
  "$<TARGET_FILE:RecompDev>" "$<TARGET_FILE_DIR:rd_translation_pcode>" "${CMAKE_SOURCE_DIR}/..")
 set_tests_properties(v04914_compiled_recovery_history_bridge PROPERTIES TIMEOUT 120)
endif()

# v0.4.9.15: compiled controller-owned persistent job manager and structured logger.
add_executable(rd_controller_job_contract ../controller/tests/job_manager_contract.cpp ../controller/native_job.cpp)
target_include_directories(rd_controller_job_contract PRIVATE ../controller include ../translation_pcode/include)
add_test(NAME v04915_compiled_controller_job_manager COMMAND $<TARGET_FILE:rd_controller_job_contract> "${CMAKE_SOURCE_DIR}/.." "$<TARGET_FILE:RecompDev>")
set_tests_properties(v04915_compiled_controller_job_manager PROPERTIES TIMEOUT 45)
if(Python3_Interpreter_FOUND)
 add_test(NAME v04915_compiled_job_cli_dispatch COMMAND "${Python3_EXECUTABLE}"
  "${CMAKE_SOURCE_DIR}/../controller/tests/test_job_cli_smoke.py" "$<TARGET_FILE:RecompDev>")
 set_tests_properties(v04915_compiled_job_cli_dispatch PROPERTIES TIMEOUT 35)
endif()

# v0.4.9.16: three-session cumulative evidence preservation and isolated
# release-checkpoint Git plumbing. These do not represent real-ROM parity.
if(Python3_Interpreter_FOUND)
 add_test(NAME v04916_cumulative_recovery_ledger COMMAND "${Python3_EXECUTABLE}" -B
  "${CMAKE_SOURCE_DIR}/../analysis_integration/tests/test_recovery_history.py" -q)
 set_tests_properties(v04916_cumulative_recovery_ledger PROPERTIES TIMEOUT 45)
 add_test(NAME v04916_single_package_checkpoint_contract COMMAND "${Python3_EXECUTABLE}" -B
  "${CMAKE_SOURCE_DIR}/../release/tests/test_checkpoint_contract.py" -q)
 set_tests_properties(v04916_single_package_checkpoint_contract PROPERTIES TIMEOUT 45)
endif()

# v0.4.9.17: secure diagnostic export, explicit infrastructure-only promotion
# and a migration register; 1,800-frame native gameplay qualification remains blocked.
if(Python3_Interpreter_FOUND)
 add_test(NAME v04917_controller_diagnostics_export COMMAND "${Python3_EXECUTABLE}" -B -m unittest
  discover -s "${CMAKE_SOURCE_DIR}/../workspace/tests" -p test_diagnostics_export.py -q)
 set_tests_properties(v04917_controller_diagnostics_export PROPERTIES TIMEOUT 30)
 add_test(NAME v04917_infrastructure_release_policy COMMAND "${Python3_EXECUTABLE}" -B -m unittest
  discover -s "${CMAKE_SOURCE_DIR}/../release/tests" -p test_infrastructure_promotion.py -q)
 set_tests_properties(v04917_infrastructure_release_policy PROPERTIES TIMEOUT 30)
endif()
if(Python3_Interpreter_FOUND)
 add_test(NAME v04917_migration_register_inventory COMMAND "${Python3_EXECUTABLE}" -B -m unittest
  discover -s "${CMAKE_SOURCE_DIR}/../migration/tests" -p test_v04917_inventory.py -q)
 set_tests_properties(v04917_migration_register_inventory PROPERTIES TIMEOUT 30)
endif()


# v0.4.9.18: evidence-root routing, source-attested analysis-cache reuse,
# and ROM-free coverage-diff diagnostics. Gameplay qualification remains blocked.
if(Python3_Interpreter_FOUND)
 add_test(NAME v04918_analysis_cache_identity COMMAND "${Python3_EXECUTABLE}" -B -m unittest
  discover -s "${CMAKE_SOURCE_DIR}/../analysis_integration/tests" -p test_v04918_analysis_reuse.py -q)
 set_tests_properties(v04918_analysis_cache_identity PROPERTIES TIMEOUT 30)
 add_test(NAME v04918_coverage_diagnostics COMMAND "${Python3_EXECUTABLE}" -B -m unittest
  discover -s "${CMAKE_SOURCE_DIR}/../workspace/tests" -p test_v04918_coverage.py -q)
 set_tests_properties(v04918_coverage_diagnostics PROPERTIES TIMEOUT 30)
endif()

# v0.4.9.19: current compiled job preview dispatch and actual source-attested
# instrumented native game; monitor is read-only and ZIPs exclude ROM source.
if(Python3_EXECUTABLE)
 add_test(NAME v04919_controller_preview_native COMMAND "${Python3_EXECUTABLE}"
  -m unittest discover -s "${CMAKE_SOURCE_DIR}/../execution_monitor/tests" -p test_v04919_job_preview.py -q)
 set_tests_properties(v04919_controller_preview_native PROPERTIES WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}/.." ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1")
endif()

# v0.4.9.20: source-attested preview gap handoff and cross-cycle preservation.
if(Python3_Interpreter_FOUND)
 add_test(NAME v04920_preview_handoff COMMAND "${Python3_EXECUTABLE}"
  -m unittest discover -s "${CMAKE_SOURCE_DIR}/../analysis_integration/tests" -p test_v04920_preview_frontier.py -q)
 set_tests_properties(v04920_preview_handoff PROPERTIES WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}/.." ENVIRONMENT "PYTHONDONTWRITEBYTECODE=1")
endif()

# v0.4.9.21: standalone native Windows monitor (not Python/Tk) and neutral
# reference/candidate parity-data checker. Neither links any CPU/machine DLL.
add_executable(rd_native_monitor_contract ../execution_monitor/native/monitor_contract.cpp)
target_include_directories(rd_native_monitor_contract PRIVATE ../execution_monitor/native ../translation_pcode/include)
add_test(NAME v04921_native_monitor_contract COMMAND $<TARGET_FILE:rd_native_monitor_contract>)
set_tests_properties(v04921_native_monitor_contract PROPERTIES TIMEOUT 15)
if(WIN32)
 add_executable(RecompDevMonitor WIN32 ../execution_monitor/native/viewer_win32.cpp)
 target_include_directories(RecompDevMonitor PRIVATE ../execution_monitor/native ../translation_pcode/include)
 target_link_libraries(RecompDevMonitor PRIVATE ws2_32 shell32 user32 gdi32)
 target_compile_definitions(RecompDevMonitor PRIVATE UNICODE _UNICODE)
 set_target_properties(RecompDevMonitor PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${OUT_DIR}")
 add_dependencies(RecompDev RecompDevMonitor)
endif()
add_executable(RecompDevParity ../parity_validation/parity_cli.cpp)
target_include_directories(RecompDevParity PRIVATE ../parity_validation ../translation_pcode/include)
set_target_properties(RecompDevParity PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${OUT_DIR}")
add_executable(rd_parity_contract ../parity_validation/parity_contract.cpp)
target_include_directories(rd_parity_contract PRIVATE ../parity_validation ../translation_pcode/include)
add_test(NAME v04921_parity_contract COMMAND $<TARGET_FILE:rd_parity_contract>)
set_tests_properties(v04921_parity_contract PROPERTIES TIMEOUT 15)
if(Python3_Interpreter_FOUND)
 add_test(NAME v04921_preview_and_recovery_bounds COMMAND "${Python3_EXECUTABLE}" -B -m unittest
  discover -s "${CMAKE_SOURCE_DIR}/../execution_monitor/tests" -p test_v04921_native_monitor.py -q)
 set_tests_properties(v04921_preview_and_recovery_bounds PROPERTIES TIMEOUT 30 WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}/..")
endif()

# v0.4.9.22 CPU-neutral bounded monitoring stress test: no GUI required.
add_executable(rd_native_monitor_stress ../execution_monitor/native/monitor_stress.cpp)
target_include_directories(rd_native_monitor_stress PRIVATE ../execution_monitor/native ../execution_monitor/bridge ../translation_pcode/include)
add_test(NAME v04922_native_monitor_stress COMMAND $<TARGET_FILE:rd_native_monitor_stress>)
set_tests_properties(v04922_native_monitor_stress PROPERTIES TIMEOUT 30)
if(Python3_Interpreter_FOUND)
 add_test(NAME v04922_monitor_watch_pipeline COMMAND "${Python3_EXECUTABLE}" -B -m unittest
  discover -s "${CMAKE_SOURCE_DIR}/../execution_monitor/tests" -p test_v04922_monitor_watch.py -q)
 set_tests_properties(v04922_monitor_watch_pipeline PROPERTIES TIMEOUT 45 WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}/..")
endif()
