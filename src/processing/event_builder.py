from __future__ import annotations

import uuid
from typing import Dict, Any


class EventBuilder:
    """
    FR-COL 전처리 결과를 분석 모듈이 바로 쓸 수 있는 이벤트 객체로 변환한다.
    간단한 룰 기반 점수로 낙상 후보 여부를 판단한다.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.thresholds = config["thresholds"]

    def build_processed(self, raw: Dict[str, Any], valid: bool, errors: list[str]) -> Dict[str, Any]:
        payload = raw.get("payload", {})
        csi = payload.get("csi", {})
        pir = payload.get("pir", {})
        tof = payload.get("tof", {})

        sensor_summary = {
            "csiChange": csi.get("change"),
            "csiVariance": csi.get("variance"),
            "rssi": csi.get("rssi"),
            "pirMotion": bool(pir.get("motion", 0)),
            "tofDistanceMm": tof.get("distanceMm"),
            "tofDeltaMm": tof.get("deltaMm"),
        }

        return {
            "messageId": str(uuid.uuid4()),
            "eventId": None,
            "timestamp": raw.get("timestamp"),
            "type": "sensor.processed",
            "source": "rpi4-edge-processor",
            "deviceId": raw.get("deviceId"),
            "roomId": raw.get("roomId"),
            "payload": {
                "sensorSummary": sensor_summary,
                "validity": {
                    "isValid": valid,
                    "errors": errors,
                },
                "mockLabel": payload.get("mockLabel"),
            },
        }

    def build_candidate_if_needed(self, processed: Dict[str, Any]) -> Dict[str, Any] | None:
        validity = processed["payload"]["validity"]
        if not validity["isValid"]:
            return None

        summary = processed["payload"]["sensorSummary"]
        score = 0
        reasons = []

        csi_change = summary.get("csiChange") or 0
        tof_delta = summary.get("tofDeltaMm") or 0
        tof_distance = summary.get("tofDistanceMm") or 99999
        pir_motion = summary.get("pirMotion")

        if csi_change >= self.thresholds["csi_change_candidate"]:
            score += 1
            reasons.append("CSI 급격한 변화")

        if tof_delta <= self.thresholds["tof_drop_delta_mm"]:
            score += 1
            reasons.append("ToF 거리 급변")

        if tof_distance <= self.thresholds["tof_low_position_mm"]:
            score += 1
            reasons.append("낮은 위치 상태")

        if pir_motion is False and tof_distance <= self.thresholds["tof_low_position_mm"]:
            score += 1
            reasons.append("낮은 위치에서 움직임 없음")

        if score < self.thresholds["abnormal_score_candidate"]:
            return None

        risk_level = "HIGH" if score >= 3 else "MEDIUM"

        return {
            "messageId": str(uuid.uuid4()),
            "eventId": str(uuid.uuid4()),
            "timestamp": processed["timestamp"],
            "type": "event.candidate",
            "source": "rpi4-edge-processor",
            "deviceId": processed.get("deviceId"),
            "roomId": processed.get("roomId"),
            "payload": {
                "behaviorState": "ABNORMAL_DETECTED",
                "responseState": "IDLE",
                "notificationState": "PENDING",
                "riskLevel": risk_level,
                "score": score,
                "reasons": reasons,
                "sensorSummary": summary,
                "summary": f"낙상 후보 이벤트 감지: {', '.join(reasons)}",
                "mockLabel": processed["payload"].get("mockLabel"),
            },
        }
