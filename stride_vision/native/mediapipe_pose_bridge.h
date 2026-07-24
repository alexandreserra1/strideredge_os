// ABI mínima StriderEdge <-> MediaPipe Tasks C. Não expõe structs internas do MediaPipe ao Rust.
#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct SePoseBridge SePoseBridge;

// Abre o runtime MediaPipe e cria um PoseLandmarker em modo VIDEO, para uma única pessoa.
// Retorna nullptr e escreve um motivo curto em `error` se não conseguir inicializar.
SePoseBridge* se_pose_bridge_create(const char* runtime_path, const char* model_path,
                                    char* error, size_t error_size);

// Lê um frame RGB intercalado. `out_landmarks` recebe 33 grupos de:
// [x_normalizado, y_normalizado, visibility, presence]. `out_world` (se != nullptr) recebe 33 grupos
// de [x, y, z] em METROS (pose_world_landmarks, origem no quadril) — o 3D que só o BlazePose entrega.
// `found` é 0 quando não há pessoa. Retorna 0 em sucesso; nos outros casos escreve o motivo em `error`.
int se_pose_bridge_infer(SePoseBridge* bridge, const uint8_t* rgb, uint32_t width, uint32_t height,
                         int64_t timestamp_ms, float* out_landmarks, float* out_world, int* found,
                         char* error, size_t error_size);

void se_pose_bridge_close(SePoseBridge* bridge);

#ifdef __cplusplus
}
#endif
