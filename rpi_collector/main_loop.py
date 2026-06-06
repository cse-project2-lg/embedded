# main_loop.py
from preprocessor import ToFPreprocessor, CSIPreprocessor, process_synced_frame
from feature_extractor import extract_window_features

# 전처리기 초기화
tof_pre = ToFPreprocessor()
csi_pre = CSIPreprocessor()

while True:
    # 1. /preprocess/synced_frame 토픽 수신
    frame = mqtt_receive_synced_frame()

    # 2. 전처리 (ToF + CSI 동시, loader는 rawLogFile 기반으로 내부 자동 결정)
    processed = process_synced_frame(frame, tof_pre, csi_pre)

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