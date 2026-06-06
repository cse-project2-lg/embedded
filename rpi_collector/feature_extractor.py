import numpy as np
from typing import List


def extract_csi_features(
    csi_window: List[np.ndarray]
) -> dict:
    """
    CSI 특징 추출

    Args:
        csi_window:
            CSIPreprocessor.process_chunk()
            결과를 Window 단위로 저장한 리스트

            각 원소 shape:
            (time_steps, num_groups)

    Returns:
        {
            "csiMaxVariance": float,
            "csiMaxAmplitude": float,
            "csiMaxDiff": float,
            "csiPacketCount": int
        }
    """

    if not csi_window:

        return {
            "csiMaxVariance": 0.0,
            "csiMaxAmplitude": 0.0,
            "csiMaxDiff": 0.0,
            "csiPacketCount": 0
        }

    merged = np.concatenate(
        csi_window,
        axis=0
    )

    max_variance = float(
        np.max(
            np.var(
                merged,
                axis=0
            )
        )
    )

    max_amplitude = float(
        np.max(
            np.abs(merged)
        )
    )

    diff_array = np.diff(
        merged,
        axis=0
    )

    max_diff = (
        float(
            np.max(
                np.abs(diff_array)
            )
        )
        if len(diff_array) > 0
        else 0.0
    )

    return {

        "csiMaxVariance":
            round(max_variance, 4),

        "csiMaxAmplitude":
            round(max_amplitude, 4),

        "csiMaxDiff":
            round(max_diff, 4),

        # 실제 CSI frame 개수
        "csiPacketCount":
            int(
                merged.shape[0]
            )
    }


def extract_tof_features(
    tof_window: List[float],
    ts_window: List[int]
) -> dict:
    """
    ToF 특징 추출

    Args:
        tof_window:
            정제된 ToF 거리값(mm)

        ts_window:
            timestamp(ns)

    Returns:
        {
            "tofMaxDrop": float,
            "tofCurrentDistance": float,
            "tofStableMs": float
        }
    """

    if not tof_window or not ts_window:

        return {
            "tofMaxDrop": 0.0,
            "tofCurrentDistance": 0.0,
            "tofStableMs": 0.0
        }

    if len(tof_window) != len(ts_window):

        raise ValueError(
            "tof_window and ts_window length mismatch"
        )

    arr = np.array(
        tof_window,
        dtype=float
    )

    # Window 내 최대 하강량
    if len(arr) >= 2:

        drops = (
            arr[:-1]
            - arr[1:]
        )

        max_drop = float(
            np.max(
                np.clip(
                    drops,
                    0.0,
                    None
                )
            )
        )

    else:

        max_drop = 0.0

    # 현재 거리
    current_distance = float(
        arr[-1]
    )

    # 현재 위치가 얼마나 유지되었는지 계산
    stable_threshold_mm = 50

    stable_start_idx = (
        len(arr) - 1
    )

    for i in range(
        len(arr) - 2,
        -1,
        -1
    ):

        if abs(
            arr[i]
            - arr[-1]
        ) > stable_threshold_mm:

            break

        stable_start_idx = i

    stable_ms = (
        ts_window[-1]
        - ts_window[stable_start_idx]
    ) / 1_000_000

    return {

        "tofMaxDrop":
            round(max_drop, 2),

        "tofCurrentDistance":
            round(current_distance, 2),

        "tofStableMs":
            round(stable_ms, 2)
    }


def extract_pir_features(
    pir_window: List[bool],
    ts_window: List[int]
) -> dict:
    """
    PIR 특징 추출

    Args:
        pir_window:
            PIR Motion 여부

        ts_window:
            timestamp(ns)

    Returns:
        {
            "pirAnyMotion": bool,
            "pirSilentDuration": float
        }
    """

    if not pir_window or not ts_window:

        return {
            "pirAnyMotion": False,
            "pirSilentDuration": 0.0
        }

    if len(pir_window) != len(ts_window):

        raise ValueError(
            "pir_window and ts_window length mismatch"
        )

    any_motion = any(
        pir_window
    )

    last_motion_idx = None

    for i in range(
        len(pir_window) - 1,
        -1,
        -1
    ):

        if pir_window[i]:

            last_motion_idx = i
            break

    if last_motion_idx is not None:

        silent_duration_ms = (
            ts_window[-1]
            - ts_window[last_motion_idx]
        ) / 1_000_000

    else:

        silent_duration_ms = (
            ts_window[-1]
            - ts_window[0]
        ) / 1_000_000

    return {

        "pirAnyMotion":
            any_motion,

        "pirSilentDuration":
            round(
                silent_duration_ms,
                2
            )
    }


def extract_window_features(
    csi_window: List[np.ndarray],
    tof_window: List[float],
    pir_window: List[bool],
    ts_window: List[int]
) -> dict:
    """
    Window 단위 통합 특징 추출

    Rule Engine 입력용 Feature Vector 생성
    """

    csi_features = extract_csi_features(
        csi_window
    )

    tof_features = extract_tof_features(
        tof_window,
        ts_window
    )

    pir_features = extract_pir_features(
        pir_window,
        ts_window
    )

    window_duration_ms = 0.0

    if len(ts_window) >= 2:

        window_duration_ms = (
            ts_window[-1]
            - ts_window[0]
        ) / 1_000_000

    return {

        "windowDurationMs":
            round(
                window_duration_ms,
                2
            ),

        **csi_features,

        **tof_features,

        **pir_features
    }