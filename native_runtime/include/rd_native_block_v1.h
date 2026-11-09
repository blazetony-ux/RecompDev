#ifndef RECOMPDEV_NATIVE_BLOCK_V1_H
#define RECOMPDEV_NATIVE_BLOCK_V1_H
/* Independent, machine-neutral, C ABI for immutable, source-attested native
 * translation modules. No CPU registers, ROM addresses, C++ objects or SDL/
 * Win32 types cross the ABI. The owning machine plugin supplies opaque state.
 * step: 1 = one guest instruction committed; 0 = no matching compiled block
 * and MUST NOT mutate state; <0 = integrity/hardware failure (fail closed).
 * The host MUST retain every activated module until no execution can refer to it.
 */
#include <stdint.h>
#if defined(_WIN32)
# define RD_NATIVE_BLOCK_EXPORT __declspec(dllexport)
#else
# define RD_NATIVE_BLOCK_EXPORT __attribute__((visibility("default")))
#endif
#ifdef __cplusplus
extern "C" {
#endif
#define RD_NATIVE_BLOCK_ABI_V1 0x00010000u
#define RD_NATIVE_BLOCK_CPU_MAX 64u
#define RD_NATIVE_BLOCK_SHA_HEX 64u
typedef int (*RD_NativeBlockStepV1)(void *machine_state, uint32_t physical_offset);
typedef struct RD_NativeBlockV1 {
 uint32_t struct_size;
 uint32_t abi_version;
 const char *cpu_id;
 const char *cpu_semantics_version;
 const char *machine_id;
 const char *machine_state_abi;
 const char *target_abi;
 const char *source_sha256;
 uint64_t source_size;
 RD_NativeBlockStepV1 step;
} RD_NativeBlockV1;
typedef const RD_NativeBlockV1 *(*RD_NativeBlockGetV1)(void);
/* A module exports exactly this unmangled name. */
RD_NATIVE_BLOCK_EXPORT const RD_NativeBlockV1 *rd_native_block_get_v1(void);
#ifdef __cplusplus
}
#endif
#endif
