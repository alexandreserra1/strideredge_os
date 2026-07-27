fn main() {
    println!("cargo:rerun-if-changed=native/mediapipe_pose_bridge.cc");
    println!("cargo:rerun-if-changed=native/mediapipe_pose_bridge.h");

    cc::Build::new()
        .cpp(true)
        .file("native/mediapipe_pose_bridge.cc")
        .flag_if_supported("-std=c++17")
        .compile("stride_mediapipe_pose_bridge");

    // `dlopen` vive em libdl no Linux e em libSystem no macOS. O runtime MediaPipe é carregado
    // por caminho configurado, para que o binário não tenha um rpath da máquina de desenvolvimento.
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("linux") {
        println!("cargo:rustc-link-lib=dl");
    }
}
