from numbers import Real
import math

class RuleEngine:
    """
    Rule-Based Fall Candidate Detector

    입력:
        Feature Extractor 결과

    출력:
        {
            "localScore": float,
            "localRiskLevel": str,
            "candidateReason": list
        }
    """

    # Threshold
    # TODO:
    # 실제 실험 데이터를 기반으로 튜닝 필요

    REQUIRED_FEATURE_KEYS = (
        "csiMaxDiff",
        "tofMaxDrop",
        "pirSilentDuration"
    )

    CSI_DIFF_THRESHOLD = 1.0

    TOF_DROP_THRESHOLD = 500

    PIR_SILENT_THRESHOLD_MS = 2000

    # MAIN
    def judge(
        self,
        features: dict
    ) -> dict:
        
        missing = [
            key
            for key in self.REQUIRED_FEATURE_KEYS
            if key not in features
        ]

        if missing:

            raise ValueError(
                f"Missing required features: "
                f"{missing}"
            )

        for key in self.REQUIRED_FEATURE_KEYS:

            value = features[key]

            # bool 차단
            if isinstance(
                value,
                bool
            ):

                raise TypeError(
                    f"Feature '{key}' "
                    f"must not be bool"
                )

            # 실수/정수만 허용
            if not isinstance(
                value,
                Real
            ):

                raise TypeError(
                    f"Feature '{key}' "
                    f"must be real number, "
                    f"got "
                    f"{type(value).__name__}"
                )

            # NaN, inf 차단
            if not math.isfinite(
                value
            ):

                raise ValueError(
                    f"Feature '{key}' "
                    f"must be finite, "
                    f"got {value}"
                )

        score = 0.0

        reasons = []

        # CSI Rule

        # CSI 급격 변화 발생 여부
        if (
            features["csiMaxDiff"]
            >= self.CSI_DIFF_THRESHOLD
        ):

            score += 0.3

            reasons.append(
                "CSI 급격 변화"
            )

        # ToF Rule

        # 거리 급변 여부
        if (
            features["tofMaxDrop"]
            >= self.TOF_DROP_THRESHOLD
        ):

            score += 0.4

            reasons.append(
                "ToF 거리 급변"
            )

        # PIR Rule

        # 일정 시간 이상 움직임 없음
        if (
            features["pirSilentDuration"]
            >= self.PIR_SILENT_THRESHOLD_MS
        ):

            score += 0.3

            reasons.append(
                "움직임 정지 지속"
            )

        # Risk Level
        if score >= 0.8:

            risk_level = "HIGH"

        elif score >= 0.5:

            risk_level = "MEDIUM"

        else:

            risk_level = "LOW"

        # Result
        return {

            "localScore":
                round(score, 2),

            "localRiskLevel":
                risk_level,

            "candidateReason":
                reasons
        }