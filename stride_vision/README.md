# stride-vision

Motor de análise de movimento esportivo **on-device** (Rust): pose estimation via ONNX
→ 17 keypoints → biomecânica feita na mão (cadência por FFT, esqueleto desenhado).

## Uso
```bash
# modelo (uma vez): exporta YOLO11n-pose para ONNX
pip install ultralytics && yolo export model=yolo11n-pose.pt format=onnx imgsz=640
mv yolo11n-pose.onnx models/

cargo run --release -- foto.jpg saida.jpg     # esqueleto na foto
cargo run --release -- corrida.mp4 saida.mp4  # esqueleto no vídeo + CADÊNCIA (spm)
```
Vídeo requer `ffmpeg` (`brew install ffmpeg`).

## Validação
Cadência estimada do vídeo é comparada com a cadência do Garmin (ground truth
no DuckDB do StriderEdge). Meta: erro < 3%.
