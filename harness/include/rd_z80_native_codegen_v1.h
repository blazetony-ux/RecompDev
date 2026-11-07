#ifndef RD_Z80_NATIVE_CODEGEN_V1_H
#define RD_Z80_NATIVE_CODEGEN_V1_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Optional CPU-owned full-runtime lowering for source-verified Z80 instructions
   missing from a prior Ghidra P-code export. The translation plugin passes only
   attested opcode bytes and embeds the returned C++ into a generated case.
   No ROM identity, addresses, banking or title checks are owned by the CPU. */
#define RD_Z80_NATIVE_CODEGEN_ABI_V1 0x00010000u
typedef struct RD_Z80NativeCodeV1 {
 uint32_t abi_version, struct_size, supported, reserved;
 char cpp_body[2048];
} RD_Z80NativeCodeV1;
typedef int (*RD_Z80NativeCodeFnV1)(const uint8_t *bytes,uint32_t length,RD_Z80NativeCodeV1 *out);
#ifdef __cplusplus
}
#endif
#endif
