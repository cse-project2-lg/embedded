import serial
import time
import numpy as np
from preprocessor import PIRProcessor, ToFProcessor, CSIProcessor 

PORT = '/dev/ttyUSB0'
BAUD_RATE = 115200

pir = PIRProcessor()
tof = ToFProcessor()
csi = CSIProcessor(fs=100) 

try:
    ser = serial.Serial(PORT, BAUD_RATE, timeout=1)
    print("ESP32 센서 데이터 수신 대기 중...")

    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8').rstrip()
            
            try:
                pir_str, tof_str = line.split(',')
                
                # 데이터 전처리
                if int(pir_str) == 1:
                    pir.update(motion_detected=True)
                
                clean_tof = tof.process(int(tof_str))
                
                # dummy_csi_chunk = ... 
                # filtered_csi, max_var = csi.process_chunk(dummy_csi_chunk)
                
                print(f"📡 정제된 데이터 -> PIR 상태: {pir.get_state()}, ToF 거리: {clean_tof}mm")

                # 나중에 max_var > 50.0 같은 트리거 조건이 맞으면 MQTT로 JSON을 쏘는 로직 추가

            except ValueError:
                pass

except serial.SerialException as e:
    print(f"시리얼 포트 에러: {e}")