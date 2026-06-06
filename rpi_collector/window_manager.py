from collections import deque


# Window 설정
WINDOW_SIZE_SEC = 7
OVERLAP_SEC = 2

WINDOW_SIZE_NS = WINDOW_SIZE_SEC * 1_000_000_000
STEP_SIZE_NS = (WINDOW_SIZE_SEC - OVERLAP_SEC) * 1_000_000_000

# 최소 샘플 수
MIN_WINDOW_SAMPLES = 5

class SlidingWindowManager:
    # Timestamp 기반 Sliding Window
    # Window Size : 7초
    # Overlap     : 2초
    # Step Size   : 5초

    def __init__(self):

        self.csi_buffer = deque()
        self.tof_buffer = deque()
        self.pir_buffer = deque()
        self.ts_buffer = deque()

    def push(
        self,
        csi,
        tof,
        pir,
        ts
    ):
        """
        전처리 완료된 샘플 추가

        Args:
            csi : CSI Filtered Amplitude
            tof : ToF Distance(mm)
            pir : PIR Motion(bool)
            ts  : timestamp(ns)
        """

        self.csi_buffer.append(csi)
        self.tof_buffer.append(tof)
        self.pir_buffer.append(pir)
        self.ts_buffer.append(ts)

    def window_ready(self):
        """
        Window 생성 가능 여부 확인

        조건:
        1. 최소 샘플 수 확보
        2. Window Size(7초) 확보
        """

        if (
            len(self.ts_buffer)
            < MIN_WINDOW_SAMPLES
        ):
            return False

        start_ts = (
            self.ts_buffer[0]
        )

        current_ts = (
            self.ts_buffer[-1]
        )

        return (
            current_ts
            - start_ts
            >= WINDOW_SIZE_NS
        )


    def get_window(self):
        # Window 추출 후 다음 Window를 위해 5초 만큼 이동

        start_ts = (
            self.ts_buffer[0]
        )

        end_ts = (
            start_ts
            + WINDOW_SIZE_NS
        )

        csi_window = []

        tof_window = []

        pir_window = []

        ts_window = []

        for i, ts in enumerate(
            self.ts_buffer
        ):

            if ts <= end_ts:

                csi_window.append(
                    self.csi_buffer[i]
                )

                tof_window.append(
                    self.tof_buffer[i]
                )

                pir_window.append(
                    self.pir_buffer[i]
                )

                ts_window.append(
                    ts
                )

        next_window_start = (
            start_ts
            + STEP_SIZE_NS
        )

        while (
            self.ts_buffer
            and
            self.ts_buffer[0]
            < next_window_start
        ):

            self.csi_buffer.popleft()

            self.tof_buffer.popleft()

            self.pir_buffer.popleft()

            self.ts_buffer.popleft()

        return (
            csi_window,
            tof_window,
            pir_window,
            ts_window
        )