import time
import numpy as np
from collections import deque
from scipy.signal import butter, lfilter, lfilter_zi

class PIRProcessor:
    def __init__(self, timeout=2.0):
        self.last_motion_time = 0.0
        self.timeout = timeout

    def update(self, motion_detected: bool):
        """인터럽트 발생 시 호출하여 타임스탬프 갱신"""
        if motion_detected:
            self.last_motion_time = time.time()

    def get_summary(self) -> dict:
        """동기화 큐에 던져줄 PIR 요약 데이터"""
        is_moving = (time.time() - self.last_motion_time) < self.timeout
        return {
            "pirMotion": bool(is_moving)
        }

class ToFProcessor:
    def __init__(self, window_size=5, error_value=8190):
        self.window = deque(maxlen=window_size)
        self.last_valid = 0
        self.error_value = error_value

    def process(self, distance):
        if distance is None or np.isnan(distance) or distance >= self.error_value:
            distance = self.last_valid
        else:
            self.last_valid = distance

        self.window.append(distance)
        if len(self.window) < self.window.maxlen:
            return distance
            
        return np.median(self.window)
    
    def get_summary(self) -> dict:
        """동기화 큐에 던져줄 ToF 요약 데이터"""
        if len(self.window) < 2:
            return {"tofMaxDrop": 0.0, "tofCurrentMedian": float(self.last_valid)}
            
        max_drop = max(self.window) - min(self.window)
        return {
            "tofMaxDrop": round(float(max_drop), 2),
            "tofCurrentMedian": round(float(np.median(self.window)), 2)
        }

class CSIProcessor:
    def __init__(self, num_subcarriers=64, group_size=4, fs=100, cutoff=10):
        self.num_subcarriers = num_subcarriers
        self.group_size = group_size
        self.num_groups = num_subcarriers // group_size 
        
        nyq = 0.5 * fs
        normal_cutoff = cutoff / nyq
        self.b, self.a = butter(4, normal_cutoff, btype='low', analog=False)
        self.zi = np.zeros((max(len(self.a), len(self.b)) - 1, self.num_groups))
        self.first_run = True
        
        self.baseline_amp = None
        self.alpha = 0.05 
        
        self.last_variance = 0.0
        self.last_max_amp = 0.0
        self.last_max_diff = 0.0

    def calculate_amplitude(self, csi_complex_chunk):
        return np.abs(csi_complex_chunk)

    def group_subcarriers(self, amplitude_data):
        time_steps = amplitude_data.shape[0]
        grouped = amplitude_data.reshape(time_steps, self.num_groups, self.group_size).mean(axis=2)
        return grouped

    def z_score_clipping(self, grouped_data):
        mean = np.mean(grouped_data, axis=0)
        std = np.std(grouped_data, axis=0)
        std = np.where(std == 0, 1e-6, std) 
        lower_bound = mean - 3 * std
        upper_bound = mean + 3 * std
        return np.clip(grouped_data, lower_bound, upper_bound)

    def process_chunk(self, csi_complex_chunk):
        amp = self.calculate_amplitude(csi_complex_chunk)
        grouped_amp = self.group_subcarriers(amp)
        clipped_amp = self.z_score_clipping(grouped_amp)
        
        if self.baseline_amp is None:
            self.baseline_amp = np.mean(clipped_amp, axis=0)
            
        dynamic_amp = clipped_amp - self.baseline_amp
        self.baseline_amp = (1 - self.alpha) * self.baseline_amp + self.alpha * np.mean(clipped_amp, axis=0)

        filtered_amp = np.zeros_like(dynamic_amp)
        
        if self.first_run:
            zi_base = lfilter_zi(self.b, self.a)
            for i in range(self.num_groups):
                self.zi[:, i] = zi_base * dynamic_amp[0, i] 
            self.first_run = False
            
        for i in range(self.num_groups):
            filtered_amp[:, i], self.zi[:, i] = lfilter(
                self.b, self.a, dynamic_amp[:, i], zi=self.zi[:, i]
            )
            
        # ⭐ 특징(Feature) 추출 (연산이 매우 가벼운 Numpy 내장 함수 활용)
        self.last_variance = np.max(np.var(filtered_amp, axis=0))          # 1. 격렬함(분산)
        self.last_max_amp = np.max(np.abs(filtered_amp))                   # 2. 최대 튕김폭(진폭)
        
        # np.diff는 배열 요소 간의 차이를 구해줌 -> 프레임 간 변화율(속도)
        diff_array = np.diff(filtered_amp, axis=0)
        self.last_max_diff = np.max(np.abs(diff_array)) if len(diff_array) > 0 else 0.0 # 3. 순간 최대 꺾임
        
        return filtered_amp

    def get_summary(self) -> dict:
        """동기화 큐에 던져줄 CSI 최종 요약 데이터"""
        return {
            "csiMaxVariance": round(float(self.last_variance), 4),
            "csiMaxAmplitude": round(float(self.last_max_amp), 4),
            "csiMaxDiff": round(float(self.last_max_diff), 4)
        }