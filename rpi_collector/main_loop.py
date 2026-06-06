# main_loop.py 예시
from preprocessor import ToFPreprocessor, CSIPreprocessor
from feature_extractor import extract_window_features
 
# 전처리기 초기화
csi_pre = CSIPreprocessor()
tof_pre = ToFPreprocessor()

while True:
    # 1. MQTT 수신 (ESP32 데이터) + CSI 캡처
    raw_data = mqtt_receive()   
    raw_data["csi"] = capture_csi()  

    # 2. 전처리 (샘플 단위)
    clean_csi = csi_pre.process_chunk(raw_data["csi"])   # 필터링, baseline 제거 등
    clean_tof = tof_pre.process(raw_data["tofDistance"]) # 에러값 대체만
    pir       = raw_data["pirMotion"]                    # 전처리 없이 그대로
    ts        = raw_data["timestamp"]

    # 3. 동기화 버퍼에 적재
    sync_buffer.push(clean_csi, clean_tof, pir, ts)

    # 4. window 준비되면 특징 추출 + 1차 판정
    if sync_buffer.window_ready():
        csi_window, tof_window, pir_window, ts_window = sync_buffer.get_window()

        features = extract_window_features(csi_window, tof_window, pir_window, ts_window)
        result   = rule_engine.judge(features)

        if result.state >= FALL_ANALYZING:
            send_to_cloud(result)    # HTTP