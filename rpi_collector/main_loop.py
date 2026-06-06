# main_loop.py 예시
from preprocessor import (
    ToFPreprocessor, CSIPreprocessor,
    CsiRawFileLoader, process_synced_frame,
)
from feature_extractor import extract_window_features
from datetime import date

# 전처리기 초기화
tof_pre = ToFPreprocessor()
csi_pre = CSIPreprocessor()

# CSI JSONL 로더 — 날짜가 바뀌면 재생성 필요
def make_loader() -> CsiRawFileLoader:
    today = date.today().strftime("%Y%m%d")
    return CsiRawFileLoader(
        f"/home/wisasy/workspace/embedded/data/csi_raw/csi_raw_{today}.jsonl"
    )

loader = make_loader()

while True:
    # 1. /preprocess/synced_frame 토픽 수신
    frame = mqtt_receive_synced_frame()  # synced.frame 딕셔너리

    # 날짜 자정 넘어가면 loader 교체
    today = date.today().strftime("%Y%m%d")
    if today not in str(loader._path):
        loader = make_loader()

    # 2. 전처리 (ToF + CSI 동시)
    processed = process_synced_frame(frame, loader, tof_pre, csi_pre)

    # csiFilteredAmp 가 None 이면 pingOk=False 또는 유효 패킷 없음 → 스킵
    if processed["csiFilteredAmp"] is None:
        continue

    # 3. 동기화 버퍼에 적재
    sync_buffer.push(
        csi=processed["csiFilteredAmp"],
        tof=processed["tofDistanceMm"],
        pir=processed["pirMotion"],
        ts=processed["timestamp"],
    )

    # 4. window 준비되면 특징 추출 + 1차 판정
    if sync_buffer.window_ready():
        csi_window, tof_window, pir_window, ts_window = sync_buffer.get_window()

        features = extract_window_features(csi_window, tof_window, pir_window, ts_window)
        result   = rule_engine.judge(features)

        if result.state >= FALL_ANALYZING:
            send_to_cloud(result)