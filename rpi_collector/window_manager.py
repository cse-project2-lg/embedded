from dataclasses import dataclass
from collections import deque


# Window 설정
# - 7초 길이의 Window 생성
# - 이전 Window와 2초 중첩
WINDOW_SIZE_SEC = 7
OVERLAP_SEC = 2

WINDOW_SIZE_NS = WINDOW_SIZE_SEC * 1_000_000_000
STEP_SIZE_NS = (WINDOW_SIZE_SEC - OVERLAP_SEC) * 1_000_000_000


@dataclass
class DataWindow:
    # Feature Extraction 단계로 전달되는 하나의 분석 구간(Window)

    startTimestampNs: int
    endTimestampNs: int

    durationSec: float

    sampleCount: int

    samples: list


class SlidingWindowManager:
    # Timestamp 기반 Sliding Window 생성기
    # Window Size : 7초
    # Overlap     : 2초
    # Step Size   : 5초

    def __init__(self):

        # 최근 수신 데이터 저장 버퍼
        self.buffer = deque()

    def add_sample(self, sample):
        """
        전처리된 샘플 추가

        Args:
            sample:
            {
                "timestampNs": ...,
                ...
            }

        Returns:
            DataWindow 또는 None
        """

        self.buffer.append(sample)

        # 최소 2개 이상 있어야 시간 계산 가능
        if len(self.buffer) < 2:
            return None

        start_ts = self.buffer[0]["timestampNs"]
        current_ts = self.buffer[-1]["timestampNs"]

        # 아직 7초가 채워지지 않았으면 대기
        if current_ts - start_ts < WINDOW_SIZE_NS:
            return None

        return self._create_window()

    def _create_window(self):
        # 현재 버퍼 기준으로 Window 생성

        start_ts = self.buffer[0]["timestampNs"]
        end_ts = start_ts + WINDOW_SIZE_NS

        samples = []

        # Window 범위 내 데이터만 수집
        for sample in self.buffer:

            if sample["timestampNs"] <= end_ts:
                samples.append(sample)

        window = DataWindow(
            startTimestampNs=start_ts,
            endTimestampNs=end_ts,
            durationSec=WINDOW_SIZE_SEC,
            sampleCount=len(samples),
            samples=samples
        )

        # 다음 Window 시작 위치 계산
        # (7초 Window, 2초 중첩 → 5초 이동)
        next_window_start = start_ts + STEP_SIZE_NS

        # 다음 Window에 필요 없는 과거 데이터 제거
        while (
            self.buffer and
            self.buffer[0]["timestampNs"] < next_window_start
        ):
            self.buffer.popleft()

        return window