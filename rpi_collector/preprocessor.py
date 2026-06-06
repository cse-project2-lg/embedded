import numpy as np
from scipy.signal import butter, lfilter, lfilter_zi


class ToFPreprocessor:
    """
    ToF 센서 raw 거리값 처리
    - 에러값(8190 등) → 직전 유효값으로 대체 (샘플 단위)
    """

    def __init__(self, error_value: int = 8190):
        """
        Args:
            error_value: ToF 센서 에러 코드값 (이 값 이상은 무효)
        """
        self.last_valid: float = 0.0
        self.error_value = error_value

    def process(self, distance) -> float:
        """
        단일 거리값 정제 (에러값 대체만 수행)
        Args:
            distance: ToF 센서 raw 거리값 (mm)
        Returns:
            유효한 거리값 (mm). 에러값이면 직전 유효값 반환.
        """
        if distance is None or np.isnan(distance) or distance >= self.error_value:
            return self.last_valid

        self.last_valid = float(distance)
        return self.last_valid


class CSIPreprocessor:
    """
    CSI raw 복소수 데이터 처리
    - 진폭 계산
    - 서브캐리어 그룹핑
    - Z-score 클리핑
    - Baseline(동적 평균) 제거
    - 저역통과 필터 (Butterworth, 상태 유지)
    """

    def __init__(
        self,
        num_subcarriers: int = 64,
        group_size: int = 4,
        fs: float = 100.0,
        cutoff: float = 10.0,
        alpha: float = 0.05
    ):
        """
        Args:
            num_subcarriers: CSI 서브캐리어 수
            group_size: 그룹핑 단위 (서브캐리어 평균)
            fs: 샘플링 주파수 (Hz)
            cutoff: 저역통과 필터 컷오프 주파수 (Hz)
            alpha: baseline 지수 이동 평균 계수 (작을수록 천천히 갱신)
        """
        self.num_subcarriers = num_subcarriers
        self.group_size = group_size
        self.num_groups = num_subcarriers // group_size

        # Butterworth 저역통과 필터 계수
        nyq = 0.5 * fs
        normal_cutoff = cutoff / nyq
        self.b, self.a = butter(4, normal_cutoff, btype='low', analog=False)

        # 필터 초기 상태 (그룹 수만큼)
        self.zi = np.zeros((max(len(self.a), len(self.b)) - 1, self.num_groups))
        self.first_run = True

        # 동적 baseline (지수 이동 평균)
        self.baseline_amp = None
        self.alpha = alpha

    def process_chunk(self, csi_complex_chunk: np.ndarray) -> np.ndarray:
        """
        CSI 청크 전처리 (스트리밍, 필터 상태 유지)
        Args:
            csi_complex_chunk: shape (time_steps, num_subcarriers), 복소수 배열
        Returns:
            filtered_amp: shape (time_steps, num_groups), 정제된 진폭 배열
        """
        # 1. 진폭 계산
        amp = np.abs(csi_complex_chunk)

        # 2. 서브캐리어 그룹핑 (평균)
        time_steps = amp.shape[0]
        grouped_amp = amp.reshape(time_steps, self.num_groups, self.group_size).mean(axis=2)

        # 3. Z-score 클리핑 (±3σ)
        mean = np.mean(grouped_amp, axis=0)
        std = np.std(grouped_amp, axis=0)
        std = np.where(std == 0, 1e-6, std)
        clipped_amp = np.clip(grouped_amp, mean - 3 * std, mean + 3 * std)

        # 4. 동적 baseline 제거
        if self.baseline_amp is None:
            self.baseline_amp = np.mean(clipped_amp, axis=0)
        dynamic_amp = clipped_amp - self.baseline_amp
        self.baseline_amp = (1 - self.alpha) * self.baseline_amp + self.alpha * np.mean(clipped_amp, axis=0)

        # 5. Butterworth 저역통과 필터 (상태 유지)
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

        return filtered_amp