#ifndef RECOMPDEV_POC_PLUGIN_H
#define RECOMPDEV_POC_PLUGIN_H
/* Versioned C ABI only. No C++ stdlib, exceptions, allocator ownership or STL across a DLL. */
#include <stdint.h>
#include <stddef.h>
#if defined(_WIN32)
# define RD_EXPORT __declspec(dllexport)
#else
# define RD_EXPORT __attribute__((visibility("default")))
#endif
#ifdef __cplusplus
extern "C" {
#endif
#define RD_ABI_VERSION 0x00010000u
#define RD_PLUGIN_ENTRY "rd_get_plugin_v1"
#define RD_PIXELS 49152u
#define RD_AUDIO_SAMPLES 512u
enum { RD_MACHINE=1, RD_CPU=2, RD_GAME=3, RD_DISCOVERY=4, RD_DISPLAY=5, RD_AUDIO=6, RD_INPUT=7 };
typedef struct RD_Plugin {
    uint32_t abi_version, descriptor_size, kind, api_size;
    const char *name;
    const void *api;
} RD_Plugin;
typedef const RD_Plugin *(*RD_GetPlugin)(void);
typedef struct RD_CpuState {
    uint16_t pc, sp;
    uint8_t a,f,b,c,d,e,h,l,halted,reserved[3];
    uint64_t cycles,steps;
} RD_CpuState;
typedef struct RD_Bus {
    void *ctx;
    uint8_t (*read)(void *,uint16_t);
    void (*write)(void *,uint16_t,uint8_t);
    uint8_t (*in_port)(void *,uint16_t);
    void (*out_port)(void *,uint16_t,uint8_t);
    uint32_t (*physical)(void *,uint16_t); /* 0xffffffff = dynamic RAM/unmapped */
    void (*set_pc)(void *,uint16_t);
    void (*advance)(void *,uint32_t);
} RD_Bus;
typedef struct RD_MachineStats {
    uint64_t tstates,steps,ram_writes,bank_switches,psg_writes,vram_writes,cram_writes,hardware_hash;
    uint32_t bank2,bank3,frames;
    uint8_t c000,controller_a;
    uint8_t reserved[2];
} RD_MachineStats;
typedef struct RD_MachineApi {
    void *(*create)(const uint8_t *rom,size_t rom_size);
    void (*destroy)(void *instance);
    RD_Bus (*bus)(void *instance);
    void (*set_input)(void *instance,uint64_t buttons);
    void (*stats)(void *instance,RD_MachineStats *result);
    int (*frame_bgra)(void *instance,uint32_t *dst,size_t count,uint32_t *width,uint32_t *height);
    int (*audio_pcm)(void *instance,int16_t *dst,size_t count);
} RD_MachineApi;
typedef struct RD_CpuApi {
    /* 1=executed, 0=halted, -1=unsupported (must not advance guest state). */
    int (*interpret_one)(RD_CpuState *,const RD_Bus *,uint32_t *cycles);
} RD_CpuApi;
typedef struct RD_GameApi {
    /* 1=executed, 0=no compiled block at this physical address, -1=mismatch. */
    int (*execute_native)(uint32_t physical,RD_CpuState *,const RD_Bus *,uint32_t *cycles);
} RD_GameApi;
typedef struct RD_Event {
    uint64_t index;
    uint16_t pc;
    uint8_t opcode;
    uint8_t reserved;
    uint32_t physical,bank,cycles;
    const char *kind;
} RD_Event;
typedef struct RD_DiscoveryApi {
    void *(*open)(const char *jsonl_path);
    int (*emit)(void *ctx,const RD_Event *event);
    void (*close)(void *ctx);
} RD_DiscoveryApi;
typedef struct RD_DisplayApi {
    int (*save_ppm)(const char *path,const uint32_t *bgra,uint32_t width,uint32_t height);
} RD_DisplayApi;
typedef struct RD_AudioApi {
    int (*save_wav)(const char *path,const int16_t *samples,uint32_t count,uint32_t rate);
} RD_AudioApi;
typedef struct RD_InputApi {
    uint64_t (*buttons)(uint64_t step,uint64_t configured_buttons);
} RD_InputApi;
/* Every shared library must expose this exact symbol with C linkage. */
RD_EXPORT const RD_Plugin *rd_get_plugin_v1(void);
#ifdef __cplusplus
}
#endif
#endif
