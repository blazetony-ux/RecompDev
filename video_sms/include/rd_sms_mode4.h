#ifndef RD_SMS_MODE4_H
#define RD_SMS_MODE4_H
#include <stdint.h>
#ifdef _WIN32
# ifdef RD_SMS_MODE4_BUILD
#  define RD_SMS_API __declspec(dllexport)
# else
#  define RD_SMS_API __declspec(dllimport)
# endif
#else
# define RD_SMS_API __attribute__((visibility("default")))
#endif
#ifdef __cplusplus
extern "C" {
#endif
#define RD_SMS_MODE4_ABI 0x00010000u
#define RD_SMS_MODE4_WIDTH 256u
#define RD_SMS_MODE4_HEIGHT 192u
/* Counters describe the supplied frame, not live VDP collision-status bits. */
typedef struct rd_sms_mode4_stats {
 uint32_t abi;
 uint32_t sat_base;
 uint32_t sprites_in_sat;
 uint32_t scanline_sprite_overflows;
 uint32_t overlapping_sprite_pixels;
 uint32_t visible_sprite_pixels;
 uint32_t foreground_masked_pixels;
 uint32_t scanlines_with_sprites;
 uint32_t flags; /* bit0: 192-line sprite terminator found */
} rd_sms_mode4_stats;
RD_SMS_API uint32_t rd_sms_mode4_abi(void);
/* BGRA pixel buffer is 256*192 u32 values. Required byte-array sizes: 16384/32/16.
 * Return 1 only after a complete successful render. Null/wrong sizes return 0.
 * ROM data and CPU translations never cross this ABI. */
RD_SMS_API int rd_sms_mode4_render(const uint8_t* vram, uint32_t vram_size,
 const uint8_t* cram, uint32_t cram_size,const uint8_t* regs,uint32_t regs_size,
 uint32_t* pixels,uint32_t pixel_count,rd_sms_mode4_stats* stats);
#ifdef __cplusplus
}
#endif
#endif
