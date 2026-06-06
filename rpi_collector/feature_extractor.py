import time
import numpy as np
from typing import List


def extract_csi_features(csi_window: List[np.ndarray]) -> dict:
    """
    window 단위 정제된 CSI 진폭 배열에서 특징 추출
    Args:
        csi_window: CSIPreprocessor.process_chunk() 결과를 window 크기만큼 쌓은 리스트
                    각 원소 shape: (time_steps, num_groups)
    Returns:
        {
            "csiMaxVariance" : float,   # 그룹별 분산의 최댓값 (움직임 격렬함)
            "csiMaxAmplitude": float,   # 최대 진폭 (튕김폭)
            "csiMaxDiff"     : float    # 인접 프레임 간 최대 변화량 (순간 꺾임)
        }
    """
    if not csi_window:
        return {"csiMaxVariance": 0.0, "csiMaxAmplitude": 0.0, "csiMaxDiff": 0.0}

    merged = np.concatenate(csi_window, axis=0)  # (total_time_steps, num_groups)

    max_variance  = float(np.max(np.var(merged, axis=0)))
    max_amplitude = float(np.max(np.abs(merged)))

    diff_array = np.diff(merged, axis=0)
    max_diff = float(np.max(np.abs(diff_array))) if len(diff_array) > 0 else 0.0

    return {
        "csiMaxVariance" : round(max_variance, 4),
        "csiMaxAmplitude": round(max_amplitude, 4),
        "csiMaxDiff"     : round(max_diff, 4)
    }


def extract_tof_features(tof_window: List[float]) -> dict:
    """
    window 단위 정제된 ToF 거리값 목록에서 특징 추출
    Args:
        tof_window: ToFPreprocessor.process() 결과를 window 크기만큼 쌓은 리스트 (mm)
    Returns:
        {
            "tofMaxDrop"     : float,   # window 내 최대 낙차 (낙상 시 급격한 하락 감지)
            "tofCurrentMedian": float   # window 내 중앙값 (현재 위치 추정)
        }
    """
    if not tof_window:
        return {"tofMaxDrop": 0.0, "tofCurrentMedian": 0.0}

    arr = np.array(tof_window)
    max_drop       = float(np.max(arr) - np.min(arr))
    current_median = float(np.median(arr))

    return {
        "tofMaxDrop"      : round(max_drop, 2),
        "tofCurrentMedian": round(current_median, 2)
    }


def extract_pir_features(pir_window: List[bool], ts_window: List[float]) -> dict:
    """
    window 단위 PIR bool값 + timestamp에서 특징 추출
    Args:
        pir_window: ESP32에서 받은 pirMotion(bool)을 window 크기만큼 쌓은 리스트
        ts_window : 각 샘플의 timestamp를 window 크기만큼 쌓은 리스트 (Unix timestamp)
    Returns:
        {
            "pirAnyMotion"     : bool,  # window 내 motion 발생 여부
            "pirSilentDuration": float  # 마지막 motion 이후 정지 지속 시간 (초)
                                        # window 내 motion이 없으면 window 전체 시간
        }
    """
    if not pir_window:
        return {"pirAnyMotion": False, "pirSilentDuration": 0.0}

    any_motion = any(pir_window)

    # 마지막 motion 발생 index 찾아서 해당 timestamp 기준으로 정지 시간 계산
    last_motion_idx = None
    for i in reversed(range(len(pir_window))):
        if pir_window[i]:
            last_motion_idx = i
            break

    if last_motion_idx is not None:
        silent_duration = round(time.time() - ts_window[last_motion_idx], 2)
    else:
        # window 내 motion 없음 → window 시작부터 지금까지
        silent_duration = round(time.time() - ts_window[0], 2) if ts_window else 0.0

    return {
        "pirAnyMotion"     : any_motion,
        "pirSilentDuration": max(silent_duration, 0.0)
    }


def extract_window_features(
    csi_window: List[np.ndarray],
    tof_window: List[float],
    pir_window: List[bool],
    ts_window : List[float]
) -> dict:
    """
    동기화된 window 데이터 전체에서 통합 특징 추출
    rule_engine.py 및 LLM 입력에 사용할 최종 sensorSummary 생성

    Args:
        csi_window: CSIPreprocessor.process_chunk() 결과 리스트
        tof_window: ToFPreprocessor.process() 결과 리스트 (mm)
        pir_window: ESP32에서 받은 pirMotion(bool) 리스트
        ts_window : 각 샘플의 timestamp 리스트

    Returns:
        {
            "csiMaxVariance" : float,
            "csiMaxAmplitude": float,
            "csiMaxDiff"     : float,
            "tofMaxDrop"     : float,
            "tofCurrentMedian": float,
            "pirAnyMotion"   : bool,
            "pirSilentDuration": float
        }
    """
    csi_features = extract_csi_features(csi_window)
    tof_features = extract_tof_features(tof_window)
    pir_features = extract_pir_features(pir_window, ts_window)

    return {**csi_features, **tof_features, **pir_features}