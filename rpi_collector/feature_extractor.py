import numpy as np
from typing import List


def extract_csi_features(
    csi_window: List[np.ndarray]
) -> dict:
    """
    Window 단위 CSI 특징 추출
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

        "csiPacketCount":
            len(csi_window)
    }


def extract_tof_features(
    tof_window: List[float],
    ts_window: List[int]
) -> dict:
    """
    Window 단위 ToF 특징 추출
    """

    if not tof_window:

        return {
            "tofMaxDrop": 0.0,
            "tofCurrentDistance": 0.0,
            "tofStableMs": 0.0
        }

    arr = np.array(
        tof_window,
        dtype=float
    )

    # Window 내 최대 거리 변화량
    max_drop = float(
        np.max(arr)
        - np.min(arr)
    )

    # 현재 거리
    current_distance = float(
        arr[-1]
    )

    # 현재 위치가 얼마나 유지됐는지 계산
    stable_threshold_mm = 50

    stable_start_idx = len(arr) - 1

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
    Window 단위 PIR 특징 추출
    """

    if not pir_window:

        return {
            "pirAnyMotion": False,
            "pirSilentDuration": 0.0
        }

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