from datetime import datetime


class EventCandidateGenerator:

    def __init__(self):

        self.event_counter = 0

    def _generate_event_id(self) -> str:
        """
        EVT-YYYYMMDD-XXXX 형식 생성

        예:
        EVT-20260604-0001
        EVT-20260604-0002
        """

        self.event_counter += 1

        today = datetime.now().strftime(
            "%Y%m%d"
        )

        return (
            f"EVT-{today}-"
            f"{self.event_counter:04d}"
        )

    def build(
        self,
        features: dict,
        rule_result: dict,
        ts_window: list[int],
        device_id: str,
        room_id: str,
        csi_status: str = "AVAILABLE"
    ) -> dict:
        """
        event.candidate 생성

        Args:
            features:
                Feature Extractor 결과

            rule_result:
                Rule Engine 결과

            ts_window:
                Window timestamp(ns)

            device_id:
                Raspberry Pi Device ID

            room_id:
                설치 공간 ID

            csi_status:
                AVAILABLE
                UNAVAILABLE
                STUB

        Returns:
            /event/candidate JSON
        """

        start_ts = ts_window[0]
        end_ts = ts_window[-1]

        duration_ms = (
            end_ts - start_ts
        ) / 1_000_000

        # TODO:
        # 실험 데이터 기반 CSI 변화 점수 정규화 필요
        change_score = min(
            1.0,
            features["csiMaxDiff"] / 2.0
        )

        return {

            "type":
                "event.candidate",

            "eventId":
                self._generate_event_id(),

            "timestamp":
                datetime.now()
                .astimezone()
                .isoformat(),

            "deviceId":
                device_id,

            "roomId":
                room_id,

            "window": {

                "startMonotonicNs":
                    start_ts,

                "endMonotonicNs":
                    end_ts,

                "durationMs":
                    round(
                        duration_ms,
                        2
                    )
            },

            "sensorSummary": {

                "pirMotion":
                    features[
                        "pirAnyMotion"
                    ],

                "pirLastMotionMs":
                    features[
                        "pirSilentDuration"
                    ],

                "tofDistanceMm":
                    features[
                        "tofCurrentDistance"
                    ],

                "tofChangeMm":
                    features[
                        "tofMaxDrop"
                    ],

                "tofStableMs":
                    features[
                        "tofStableMs"
                    ],

                "csi": {

                    "status":
                        csi_status,

                    "changeScore":
                        round(
                            change_score,
                            2
                        ),

                    "packetCount":
                        features[
                            "csiPacketCount"
                        ]
                }
            },

            "localScore":
                rule_result[
                    "localScore"
                ],

            "localRiskLevel":
                rule_result[
                    "localRiskLevel"
                ],

            "candidateReason":
                rule_result[
                    "candidateReason"
                ]
        }