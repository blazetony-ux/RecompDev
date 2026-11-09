#ifndef RD_RUNTIME_HOST_V1_H
#define RD_RUNTIME_HOST_V1_H
/* RecompDev generic host ABI v1: presentation only, never a CPU or machine API.
 * No C++/STL ownership crosses this binary boundary. All sizes are bounded.
 * Buttons: Up Down Left Right A B C Start Select = bits 0..8.
 * PCM input may be interleaved with 1..8 channels; Windows speaker currently
 * downmixes to mono while preserving source-stream fingerprints in headless mode.
 */
#include <stdint.h>
#include <stddef.h>
#if defined(_WIN32)
# if defined(RD_RUNTIME_HOST_BUILD)
#  define RD_HOST_EXPORT __declspec(dllexport)
# else
#  define RD_HOST_EXPORT __declspec(dllimport)
# endif
#else
# define RD_HOST_EXPORT __attribute__((visibility("default")))
#endif
#ifdef __cplusplus
extern "C" {
#endif
#define RD_HOST_ABI_VERSION 0x00010000u
#define RD_HOST_MODE_HEADLESS 0u
#define RD_HOST_MODE_WINDOW 1u
#define RD_HOST_MODE_SPEAKER 2u
#define RD_HOST_PIXELS_BGRA8888 1u
typedef struct RD_Host RD_Host;
typedef struct RD_HostStats {
 uint32_t struct_size, abi_version, running, width, height;
 uint64_t frames, audio_samples, frame_fingerprint, audio_fingerprint, buttons;
} RD_HostStats;
RD_HOST_EXPORT uint32_t rd_host_abi_version(void);
RD_HOST_EXPORT int rd_host_create(uint32_t mode, const char *title, uint32_t sample_rate, RD_Host **out);
RD_HOST_EXPORT void rd_host_destroy(RD_Host *host);
RD_HOST_EXPORT int rd_host_present(RD_Host *host, const uint32_t *bgra, uint32_t width, uint32_t height, uint32_t format);
RD_HOST_EXPORT int rd_host_pcm(RD_Host *host, const int16_t *samples, size_t sample_count, uint32_t sample_rate, uint32_t channels);
RD_HOST_EXPORT int rd_host_pump(RD_Host *host);
RD_HOST_EXPORT uint64_t rd_host_buttons(RD_Host *host);
/* Press edges since last take, including events pumped while guest execution
   is suspended for native compilation; not an artificial guest instruction. */
RD_HOST_EXPORT uint64_t rd_host_take_pressed(RD_Host *host);
RD_HOST_EXPORT int rd_host_title(RD_Host *host, const char *title);
RD_HOST_EXPORT int rd_host_stats(RD_Host *host, RD_HostStats *result);
#ifdef __cplusplus
}
#endif
#endif
