#pragma once
#include <stdint.h>
#include "rd_plugin.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Versioned pure native source-attested Ghidra P-code -> game DLL source ABI.
   Returns 1 only when at least one instruction lowered. 0 = no admitted source;
   -1 = invalid export or source, -2 = unsupported/host error.
   Paths are UTF-8, output location must be new and outside the project tree.
   Caller owns every allocation; no exceptions cross this C ABI. */
#define RD_TRANSLATION_ABI_V1 0x00010000u
#define RD_TRANSLATOR_KIND 9u
typedef struct RD_TranslationRequestV1 {
 uint32_t abi_version, struct_size;
 const char* rom_path;
 const char* base_export;
 const char* const* bank_exports;
 uint32_t bank_count;
 const char* output_directory;
 uint32_t require_ghidra;
 /* 1=full preserved nativepilot runtime project, 0=limited game DLL. */
 uint32_t full_runtime_project;
 const char* source_root;
} RD_TranslationRequestV1;
typedef struct RD_TranslationResultV1 {
 uint32_t abi_version, struct_size;
 uint32_t attested, emitted, rejected;
 char source_sha256[65];
 char status[96];
} RD_TranslationResultV1;
typedef struct RD_TranslationApiV1 {
 uint32_t abi_version, struct_size;
 int (*translate)(const RD_TranslationRequestV1*,RD_TranslationResultV1*);
} RD_TranslationApiV1;
/* Optional source-discovery integration. Preserves the v1 request and plugin
   descriptor so older clients and independent translator plugins still work. */
typedef struct RD_TranslationRecoveryRequestV1 {
 uint32_t abi_version,struct_size;
 RD_TranslationRequestV1 base;
 const char* source_discovery_json;
 const char* cpu_plugin_path;
} RD_TranslationRecoveryRequestV1;
typedef int (*RD_TranslationRecoveryFnV1)(const RD_TranslationRecoveryRequestV1*,
                                          RD_TranslationResultV1*);

#ifdef __cplusplus
}
#endif
