// Ponte fina para a C API do MediaPipe Pose Landmarker. O runtime é aberto por dlopen para não
// acoplar o binário a um caminho local; empacotamento escolhe o dylib/so oficial por plataforma.
#include "mediapipe_pose_bridge.h"

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <limits>
#include <new>

#include <dlfcn.h>

namespace {
constexpr int kRgb = 1;
constexpr int kVideo = 2;
constexpr int kOnePose = 1;
constexpr int kLandmarkCount = 33;
constexpr int kFieldsPerLandmark = 4;

struct MpBaseOptions {
  const char* model_asset_buffer;
  uint32_t model_asset_buffer_count;
  const char* model_asset_path;
  int delegate;
  int host_environment;
  int host_system;
  const char* host_version;
  const char* ca_bundle_path;
};

struct MpPoseOptions {
  MpBaseOptions base_options;
  int running_mode;
  int num_poses;
  float min_pose_detection_confidence;
  float min_pose_presence_confidence;
  float min_tracking_confidence;
  bool output_segmentation_masks;
  void* result_callback;
};

struct MpNormalizedLandmark {
  float x;
  float y;
  float z;
  bool has_visibility;
  float visibility;
  bool has_presence;
  float presence;
  const char* name;
};

struct MpNormalizedLandmarks {
  MpNormalizedLandmark* landmarks;
  uint32_t landmarks_count;
};

struct MpPoseResult {
  void** segmentation_masks;
  uint32_t segmentation_masks_count;
  MpNormalizedLandmarks* pose_landmarks;
  uint32_t pose_landmarks_count;
  // world landmarks têm a MESMA layout de struct dos normalized (x,y,z,visibility,presence), só que
  // x/y/z em METROS com origem no quadril. Reusamos MpNormalizedLandmarks pra ler os 33 pontos 3D.
  MpNormalizedLandmarks* pose_world_landmarks;
  uint32_t pose_world_landmarks_count;
};

using Error = char*;
using PoseCreate = int (*)(const MpPoseOptions*, void**, Error*);
using PoseDetectVideo = int (*)(void*, void*, const void*, int64_t, MpPoseResult*, Error*);
using PoseCloseResult = void (*)(MpPoseResult*);
using PoseClose = int (*)(void*, Error*);
using ImageCreateRgb = int (*)(int, int, int, const uint8_t*, int, void**, Error*);
using ImageFree = void (*)(void*);
using ErrorFree = void (*)(void*);

struct Api {
  PoseCreate pose_create = nullptr;
  PoseDetectVideo pose_detect_video = nullptr;
  PoseCloseResult pose_close_result = nullptr;
  PoseClose pose_close = nullptr;
  ImageCreateRgb image_create_rgb = nullptr;
  ImageFree image_free = nullptr;
  ErrorFree error_free = nullptr;
};

void write_error(char* destination, size_t size, const char* message) {
  if (!destination || size == 0) return;
  std::snprintf(destination, size, "%s", message ? message : "erro nativo desconhecido");
}

void write_status_error(const Api& api, Error error, char* destination, size_t size,
                        const char* action, int status) {
  char combined[512];
  std::snprintf(combined, sizeof(combined), "%s (status %d): %s", action, status,
                error ? error : "sem detalhe do runtime");
  write_error(destination, size, combined);
  if (error && api.error_free) api.error_free(error);
}

template <typename T>
bool symbol(void* library, const char* name, T* output, char* error, size_t error_size) {
  *output = reinterpret_cast<T>(dlsym(library, name));
  if (*output) return true;
  const char* loader_error = dlerror();
  char combined[256];
  std::snprintf(combined, sizeof(combined), "runtime MediaPipe sem símbolo %s: %s", name,
                loader_error ? loader_error : "desconhecido");
  write_error(error, error_size, combined);
  return false;
}

bool load_api(void* library, Api* api, char* error, size_t error_size) {
  return symbol(library, "MpPoseLandmarkerCreate", &api->pose_create, error, error_size) &&
         symbol(library, "MpPoseLandmarkerDetectForVideo", &api->pose_detect_video, error, error_size) &&
         symbol(library, "MpPoseLandmarkerCloseResult", &api->pose_close_result, error, error_size) &&
         symbol(library, "MpPoseLandmarkerClose", &api->pose_close, error, error_size) &&
         symbol(library, "MpImageCreateFromUint8Data", &api->image_create_rgb, error, error_size) &&
         symbol(library, "MpImageFree", &api->image_free, error, error_size) &&
         symbol(library, "MpErrorFree", &api->error_free, error, error_size);
}
}  // namespace

struct SePoseBridge {
  void* library = nullptr;
  void* landmarker = nullptr;
  Api api;
};

extern "C" SePoseBridge* se_pose_bridge_create(const char* runtime_path, const char* model_path,
                                                  char* error, size_t error_size) {
  if (!runtime_path || !*runtime_path || !model_path || !*model_path) {
    write_error(error, error_size, "STRIDE_MEDIAPIPE_LIB e STRIDE_BLAZEPOSE_MODEL são obrigatórios");
    return nullptr;
  }
  auto* bridge = new (std::nothrow) SePoseBridge();
  if (!bridge) {
    write_error(error, error_size, "memória insuficiente ao criar ponte MediaPipe");
    return nullptr;
  }
  bridge->library = dlopen(runtime_path, RTLD_NOW | RTLD_LOCAL);
  if (!bridge->library) {
    write_error(error, error_size, dlerror());
    delete bridge;
    return nullptr;
  }
  if (!load_api(bridge->library, &bridge->api, error, error_size)) {
    dlclose(bridge->library);
    delete bridge;
    return nullptr;
  }
  MpPoseOptions options{};
  options.base_options.model_asset_path = model_path;
  options.running_mode = kVideo;
  options.num_poses = kOnePose;
  options.min_pose_detection_confidence = 0.5f;
  options.min_pose_presence_confidence = 0.5f;
  options.min_tracking_confidence = 0.5f;
  Error native_error = nullptr;
  const int status = bridge->api.pose_create(&options, &bridge->landmarker, &native_error);
  if (status != 0 || !bridge->landmarker) {
    write_status_error(bridge->api, native_error, error, error_size, "criando Pose Landmarker", status);
    dlclose(bridge->library);
    delete bridge;
    return nullptr;
  }
  return bridge;
}

extern "C" int se_pose_bridge_infer(SePoseBridge* bridge, const uint8_t* rgb, uint32_t width,
                                      uint32_t height, int64_t timestamp_ms, float* out_landmarks,
                                      float* out_world, int* found, char* error, size_t error_size) {
  if (!bridge || !rgb || !out_landmarks || !found || width == 0 || height == 0) {
    write_error(error, error_size, "entrada inválida para inferência MediaPipe");
    return 1;
  }
  const uint64_t bytes = static_cast<uint64_t>(width) * height * 3;
  if (bytes > static_cast<uint64_t>(std::numeric_limits<int>::max())) {
    write_error(error, error_size, "frame RGB grande demais para a ABI MediaPipe");
    return 1;
  }
  void* image = nullptr;
  Error native_error = nullptr;
  int status = bridge->api.image_create_rgb(kRgb, static_cast<int>(width), static_cast<int>(height), rgb,
                                            static_cast<int>(bytes), &image, &native_error);
  if (status != 0) {
    write_status_error(bridge->api, native_error, error, error_size, "criando imagem MediaPipe", status);
    return status;
  }
  MpPoseResult result{};
  native_error = nullptr;
  status = bridge->api.pose_detect_video(bridge->landmarker, image, nullptr, timestamp_ms,
                                          &result, &native_error);
  bridge->api.image_free(image);
  if (status != 0) {
    write_status_error(bridge->api, native_error, error, error_size, "inferindo Pose Landmarker", status);
    return status;
  }
  *found = 0;
  if (result.pose_landmarks_count > 0 && result.pose_landmarks) {
    const MpNormalizedLandmarks& pose = result.pose_landmarks[0];
    if (pose.landmarks_count != kLandmarkCount || !pose.landmarks) {
      bridge->api.pose_close_result(&result);
      write_error(error, error_size, "Pose Landmarker devolveu quantidade inesperada de landmarks");
      return 1;
    }
    for (int index = 0; index < kLandmarkCount; ++index) {
      const MpNormalizedLandmark& point = pose.landmarks[index];
      const int offset = index * kFieldsPerLandmark;
      out_landmarks[offset] = point.x;
      out_landmarks[offset + 1] = point.y;
      out_landmarks[offset + 2] = point.has_visibility ? point.visibility : 0.0f;
      out_landmarks[offset + 3] = point.has_presence ? point.presence : 0.0f;
    }
    // 3D métrico (world landmarks): x,y,z em metros por keypoint. É o que permite o ângulo REAL do
    // BlazePose, imune à projeção 2D. Zera se o runtime não trouxer (backend segue com o 2D).
    if (out_world) {
      const bool has_world = result.pose_world_landmarks_count > 0 && result.pose_world_landmarks &&
                             result.pose_world_landmarks[0].landmarks_count == kLandmarkCount &&
                             result.pose_world_landmarks[0].landmarks;
      for (int index = 0; index < kLandmarkCount; ++index) {
        const int w = index * 3;
        if (has_world) {
          const MpNormalizedLandmark& p = result.pose_world_landmarks[0].landmarks[index];
          out_world[w] = p.x;
          out_world[w + 1] = p.y;
          out_world[w + 2] = p.z;
        } else {
          out_world[w] = out_world[w + 1] = out_world[w + 2] = 0.0f;
        }
      }
    }
    *found = 1;
  }
  bridge->api.pose_close_result(&result);
  return 0;
}

extern "C" void se_pose_bridge_close(SePoseBridge* bridge) {
  if (!bridge) return;
  if (bridge->landmarker) {
    Error native_error = nullptr;
    bridge->api.pose_close(bridge->landmarker, &native_error);
    if (native_error && bridge->api.error_free) bridge->api.error_free(native_error);
  }
  if (bridge->library) dlclose(bridge->library);
  delete bridge;
}
