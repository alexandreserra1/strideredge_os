//! onnx.rs — carregamento de sessão ONNX Runtime (`ort`) + adaptador de erro.
//!
//! Isola o acoplamento ao `ort` (runtime + execution provider) num só lugar; os backends de pose
//! só pedem uma `Session` pronta. No macOS liga CoreML (ANE/GPU) com fallback pra CPU.

use anyhow::{anyhow, Result};
use ort::session::{builder::GraphOptimizationLevel, Session};
#[cfg(target_os = "macos")]
use ort::ep::CoreML;

/// erros do `ort` (não-Send) -> anyhow
pub(crate) fn o<T, E: std::fmt::Display>(r: std::result::Result<T, E>) -> Result<T> {
    r.map_err(|e| anyhow!("ort: {e}"))
}

/// Uma sessão por modelo. No macOS pede CoreML/ANE/GPU; se o runtime não trouxer esse provider,
/// `ort` registra o aviso e preserva CPU como fallback. Outros sistemas nunca dependem de CoreML.
pub(crate) fn load_session(model_path: &str) -> Result<Session> {
    let mut builder = o(o(o(Session::builder())?
        .with_optimization_level(GraphOptimizationLevel::Level3))?
        .with_intra_threads(4))?;
    #[cfg(target_os = "macos")]
    {
        let provider = CoreML::default()
            .with_compute_units(ort::ep::coreml::ComputeUnits::All)
            .with_static_input_shapes(true)
            .with_specialization_strategy(ort::ep::coreml::SpecializationStrategy::FastPrediction)
            .build();
        builder = o(builder.with_execution_providers([provider]))?;
    }
    o(builder.commit_from_file(model_path))
}
