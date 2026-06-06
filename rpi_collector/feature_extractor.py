import numpy as np
from typing import List


def extract_csi_features(
    csi_window: List[np.ndarray]
) -> dict:
    """
    Window 단위 CSI 특징 추출

    Args:
        csi_window:
            CSIPreprocessor.process_chunk() 결과를
            Window 크기만큼 저장한 리스트

            각 원소 shape:
            (time_steps, num_groups)

    Returns:
        {
            "csiMaxVariance": float,
            "csiMaxAmplitude": float,
            "csiMaxDiff": float,
            "csiPacketCount": int
        }

    Description:
        csiMaxVariance
            - 그룹별 분산 중 최대값
            - 움직임 강도 추정

        csiMaxAmplitude
            - 최대 진폭
            - 신호 튕김 정도

        csiMaxDiff
            - 인접 프레임 간 최대 변화량
            - 순간적인 움직임 변화 감지

        csiPacketCount
            - Window 내 CSI Packet 수
            - CSI 신뢰도 판단용
    """

    if not csi_window:

        return {
            "csiMaxVariance": 0.0,
            "csiMaxAmplitude": 0.0,
            "csiMaxDiff": 0.0,
            "csiPacketCount": 0
        }

    # Window 내 CSI 데이터 병합
    merged = np.concatenate(
        csi_window,
        axis=0
    )

    # 그룹별 분산 계산 후 최댓값 추출
    max_variance = float(
        np.max(
            np.var(
                merged,
                axis=0
            )
        )
    )

    # 전체 CSI 진폭 중 최댓값
    max_amplitude = float(
        np.max(
            np.abs(merged)
        )
    )

    # 인접 프레임 변화량
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