from numbers import Number

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

            if not isinstance(
                features[key],
                Number
            ):

                raise TypeError(
                    f"Feature '{key}' "
                    f"must be numeric, "
                    f"got "
                    f"{type(features[key]).__name__}"
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