#ifndef RD_PRODUCTION_CPU_V1_H
#define RD_PRODUCTION_CPU_V1_H
/* Source-attested instruction ADMISSION contract. This is NOT native execution
   or a complete decoder/translator. It must never be reported as such. */
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define RD_Z80_SOURCE_GATE_ABI 0x00010000u
/* Return: 1=admit, known length checked; 2=admit, unverified length;
           -1=reject inconsistent known length; -2=invalid arguments. */
typedef struct RD_Z80SourceGateResultV1 {
    uint32_t struct_size;
    uint32_t abi_version;
    uint32_t opcode_family; /* 1=base, 2=CB, 3=ED, 4=DD/FD */
    uint32_t declared_length;
    uint32_t expected_length; /* 0 if this decoder does not establish it */
    uint32_t opcode;
} RD_Z80SourceGateResultV1;
/* ABI symbol looked up independently of the original rd_get_plugin_v1.
   Consumer must validate binary SHA-256 against the active component lock. */
RD_EXPORT int rd_z80_source_gate_v1(const uint8_t *bytes, uint32_t length,
                                     uint32_t physical_offset,
                                     RD_Z80SourceGateResultV1 *out);
#ifdef __cplusplus
}
#endif
#endif
