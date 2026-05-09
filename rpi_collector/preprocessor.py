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

    def get_state(self) -> int:
        """현재 상태 반환 (1: 움직임 유지 중, 0: 대기 상태)"""
        if time.time() - self.last_motion_time < self.timeout:
            return 1
        return 0

class ToFProcessor:
    def __init__(self, window_size=5, error_value=8190):
        # 0.5초(10Hz 기준 5개) 치의 데이터만 보관
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
    
class CSIProcessor:
    def __init__(self, num_subcarriers=64, group_size=4, fs=100, cutoff=10):
        self.num_subcarriers = num_subcarriers
        self.group_size = group_size
        self.num_groups = num_subcarriers // group_size  # 64 -> 16으로 축소
        
        nyq = 0.5 * fs
        normal_cutoff = cutoff / nyq
        self.b, self.a = butter(4, normal_cutoff, btype='low', analog=False)
        
        self.zi = np.zeros((max(len(self.a), len(self.b)) - 1, self.num_groups))
        self.first_run = True

    def calculate_amplitude(self, csi_complex_chunk):
        """복소수 배열에서 진폭만 추출"""
        return np.abs(csi_complex_chunk)

    def group_subcarriers(self, amplitude_data):
        """64개 서브캐리어를 4개씩 묶어 평균 -> 16개로 차원 축소 (PCA 대체)"""
        time_steps = amplitude_data.shape[0]
        grouped = amplitude_data.reshape(time_steps, self.num_groups, self.group_size).mean(axis=2)
        return grouped

    def z_score_clipping(self, grouped_data):
        """무거운 필터 대신 평균 ± 3표준편차로 이상치 잘라내기"""
        mean = np.mean(grouped_data, axis=0)
        std = np.std(grouped_data, axis=0)
        
        std = np.where(std == 0, 1e-6, std) 
        
        lower_bound = mean - 3 * std
        upper_bound = mean + 3 * std
        return np.clip(grouped_data, lower_bound, upper_bound)

    def process_chunk(self, csi_complex_chunk):
        """2초 윈도우(예: 200 패킷) 단위로 들어오는 CSI 청크 처리"""
        amp = self.calculate_amplitude(csi_complex_chunk)
        grouped_amp = self.group_subcarriers(amp)
        clipped_amp = self.z_score_clipping(grouped_amp)
        filtered_amp = np.zeros_like(clipped_amp)
        
        if self.first_run:
            zi_base = lfilter_zi(self.b, self.a)
            for i in range(self.num_groups):
                self.zi[:, i] = zi_base * clipped_amp[0, i]
            self.first_run = False
            
        for i in range(self.num_groups):
            filtered_amp[:, i], self.zi[:, i] = lfilter(
                self.b, self.a, clipped_amp[:, i], zi=self.zi[:, i]
            )
            
        max_variance = np.max(np.var(filtered_amp, axis=0))
        
        return filtered_amp, max_variance