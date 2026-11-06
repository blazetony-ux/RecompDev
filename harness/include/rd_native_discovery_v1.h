#ifndef RD_NATIVE_DISCOVERY_V1_H
#define RD_NATIVE_DISCOVERY_V1_H
#include "rd_plugin.h"
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Independent v1 C ABI for native source discovery; do not conflate with
   RD_DiscoveryApi (JSONL runtime-event recorder). No allocations cross DLLs. */
#define RD_NATIVE_DISCOVERY_ABI 0x00010000u
#define RD_FORMAT_KIND 8u
#define RD_NATIVE_SOURCE_UNMAPPED 0xffffffffffffffffull
enum { RD_INSPECT_NO_MATCH=0,RD_INSPECT_MATCH=1,RD_INSPECT_BLOCKED=2 };
enum { RD_PLATFORM_UNKNOWN=0,RD_PLATFORM_SMS=1,RD_PLATFORM_MD=2,RD_PLATFORM_PS1=3 };
enum { RD_CPU_UNKNOWN=0,RD_CPU_Z80_FAMILY=1,RD_CPU_M68000=2,RD_CPU_MIPS_R3000A=3 };
typedef struct RD_SourceV1 {
 uint32_t abi_version,struct_size;
 void *ctx;
 uint64_t byte_size;
 /* Returns 1 exactly when count bytes are read, 0 for out-of-range or I/O. */
 int (*read)(void *ctx,uint64_t offset,uint8_t *bytes,uint32_t count);
} RD_SourceV1;
typedef struct RD_FormatResultV1 {
 uint32_t abi_version,struct_size;
 uint32_t status,platform,cpu;
 uint64_t entry,executable_offset,executable_size;
 uint32_t sector_size,file_count;
 char evidence[160];
} RD_FormatResultV1;
typedef struct RD_FormatApiV1 {
 uint32_t abi_version,struct_size;
 int (*inspect)(const RD_SourceV1*,RD_FormatResultV1*);
} RD_FormatApiV1;
/* New optional Z80 discovery extension; independent of subset interpreter ABI. */
enum { RD_FLOW_FALL=0,RD_FLOW_JUMP=1,RD_FLOW_COND=2,RD_FLOW_CALL=3,
       RD_FLOW_RETURN=4,RD_FLOW_INDIRECT=5,RD_FLOW_STOP=6 };
typedef struct RD_Z80DecodeV1 {
 uint32_t abi_version,struct_size;
 uint32_t status,length,flow;
 uint16_t pc,target;
 uint8_t opcode,conditional;
 uint8_t reserved[2];
} RD_Z80DecodeV1;
typedef int (*RD_Z80DecodeFnV1)(const RD_SourceV1*,uint64_t physical,uint16_t pc,RD_Z80DecodeV1*);
/* 1=unambiguously mapped, 0=bank context required, -1=outside ROM/RAM. */
typedef int (*RD_SmsResolveFnV1)(uint16_t guest,uint64_t source_size,uint64_t *physical);
/* Optional source-exact mapping snapshot: bank numbers and the control
   register are modelled by the SMS plugin, not the controller. Unknown
   registers MUST remain unknown across a path join or unverified call. */
typedef struct RD_SmsSourceMapV1 {
 uint32_t abi_version,struct_size;
 uint8_t mapper[4],known_mask;
 uint8_t reserved[3];
} RD_SmsSourceMapV1;
typedef int (*RD_SmsMapInitialFnV1)(RD_SmsSourceMapV1*);
typedef int (*RD_SmsMapResolveFnV1)(const RD_SmsSourceMapV1*,uint16_t guest,uint64_t source_size,uint64_t*physical);
typedef int (*RD_SmsMapWriteFnV1)(RD_SmsSourceMapV1*,uint16_t dest,uint8_t value,int value_known);
/* Abstract constant propagation is CPU owned; this is not a CPU emulator. */
typedef struct RD_Z80AbstractV1 {
 uint32_t abi_version,struct_size;
 uint8_t known_a,a,known_sp,reserved;
 uint16_t sp;
 uint8_t reserved2[2];
} RD_Z80AbstractV1;
enum { RD_Z80_EFFECT_NO_WRITE=0,RD_Z80_EFFECT_ABSOLUTE=1,RD_Z80_EFFECT_UNRESOLVED=2 };
typedef struct RD_Z80EffectV1 {
 uint32_t abi_version,struct_size;
 uint32_t write_kind;
 uint16_t absolute;
 uint8_t value_known,value;
 uint8_t reserved[2];
} RD_Z80EffectV1;
typedef int (*RD_Z80AbstractFnV1)(const uint8_t*,uint32_t,RD_Z80AbstractV1*,RD_Z80EffectV1*);

#ifdef __cplusplus
}
#endif
#endif
