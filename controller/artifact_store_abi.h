#ifndef RECOMPDEV_ARTIFACT_STORE_ABI_H
#define RECOMPDEV_ARTIFACT_STORE_ABI_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define RD_ARTIFACT_STORE_ABI_V1 1u
typedef struct RD_ArtifactStoreAPIv1 {
    uint32_t abi_version;
    uint32_t struct_size;
    /* 1=success, 0=invalid/refused; digest buffer must be >=65 bytes. */
    int (*put)(const char* root, const char* kind, const char* producer,
               const char* target, const char* abi, const uint8_t* data,
               uint64_t length, char* digest_out, uint32_t digest_capacity);
    /* 1=success, 0=missing/invalid, -1=buffer too small, sets length. */
    int (*get)(const char* root, const char* kind, const char* producer,
               const char* target, const char* abi, const char* digest,
               uint8_t* output, uint64_t* inout_capacity);
} RD_ArtifactStoreAPIv1;
#if defined(_WIN32)
  #if defined(RD_ARTIFACT_STORE_BUILD)
    #define RD_STORE_EXPORT __declspec(dllexport)
  #else
    #define RD_STORE_EXPORT __declspec(dllimport)
  #endif
#else
  #define RD_STORE_EXPORT __attribute__((visibility("default")))
#endif
RD_STORE_EXPORT const RD_ArtifactStoreAPIv1* rd_artifact_store_api_v1(void);
#ifdef __cplusplus
}
#endif
#endif
