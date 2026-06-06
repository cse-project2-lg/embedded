import base64
import struct
import logging
from pathlib import Path

import numpy as np
from scipy.signal import butter, lfilter, lfilter_zi

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# nexmon_csi payload 파싱
# ---------------------------------------------------------------------------

def parse_nexmon_payload(payload_b64: str, num_subcarriers: int = 64) -> np.ndarray | None:
    """
    nexmon_csi raw payload (base64) → 복소수 배열

    nexmon 포맷:
      - 패킷 앞부분에 고정 헤더(magic 0x11111111, 타임스탬프, RSSI 등)가 붙는다.
      - 헤더 크기: 18 bytes (nexmon_csi v2.x 기준)
      - 헤더 이후부터 서브캐리어 데이터: int16 real + int16 imag 순서 (little-endian)
      - 서브캐리어 1개당 4 bytes → 64개 기준 256 bytes

    payloadLen 274 = 헤더 18 bytes + 서브캐리어 256 bytes 에 해당.

    실제 펌웨어 버전/빌드 환경에 따라 헤더 오프셋이 다를 수 있다.
    payloadPrefixHex 값으로 magic(0x11111111) 위치를 확인하고
    NEXMON_HEADER_SIZE 상수를 조정할 것.
        예) payloadPrefixHex = "c1ff04476700..." 에서 첫 바이트가 헤더 시작.

    Args:
        payload_b64: csi_raw JSONL 레코드의 payloadBase64 값
        num_subcarriers: 서브캐리어 수 (기본 64)

    Returns:
        shape (num_subcarriers,) 복소수 배열, 파싱 실패 시 None
    """
    NEXMON_HEADER_SIZE = 18  # bytes — 펌웨어 버전에 따라 조정 필요

    if not payload_b64 or payload_b64 == "...":
        return None

    try:
        raw = base64.b64decode(payload_b64)
    except Exception as e:
        logger.warning("payload base64 디코딩 실패: %s", e)
        return None

    expected_len = NEXMON_HEADER_SIZE + num_subcarriers * 4
    if len(raw) < expected_len:
        logger.warning(
            "payload 길이 부족: got %d bytes, need %d bytes", len(raw), expected_len
        )
        return None

    csi_bytes = raw[NEXMON_HEADER_SIZE: NEXMON_HEADER_SIZE + num_subcarriers * 4]
    try:
        values = struct.unpack(f"<{num_subcarriers * 2}h", csi_bytes)
    except struct.error as e:
        logger.warning("CSI 바이트 언팩 실패: %s", e)
        return None

    real = np.array(values[0::2], dtype=np.float32)
    imag = np.array(values[1::2], dtype=np.float32)
    return real + 1j * imag


# ---------------------------------------------------------------------------
# CSI JSONL 파일 로더 (seq 기반 랜덤 접근)
# ---------------------------------------------------------------------------

class CsiRawFileLoader:
    """
    /csi/raw JSONL 파일에서 seq 번호로 CSI raw 레코드를 조회한다.

    synced.frame 의 csiRawRefs 는 payload 없이 seq 만 참조하므로,
    실제 payload 는 이 클래스를 통해 JSONL 파일에서 읽어온다.

    사용 예:
        loader = CsiRawFileLoader("/home/wisasy/workspace/embedded/data/csi_raw/csi_raw_20260606.jsonl")
        record = loader.get_by_seq(1200)
        payload_b64 = record["payloadBase64"]
    """

    def __init__(self, jsonl_path: str | Path):
        """
        Args:
            jsonl_path: csi_raw_YYYYMMDD.jsonl 파일 경로
        """
        import json
        self._path = Path(jsonl_path)
        self._index: dict[int, dict] = {}  # seq → record
        self._loaded = False
        self._json = json

    def _load(self) -> None:
        """JSONL 전체를 seq 기준으로 인덱싱 (최초 호출 시 1회만 실행)"""
        if self._loaded:
            return
        if not self._path.exists():
            raise FileNotFoundError(f"CSI JSONL 파일 없음: {self._path}")

        with self._path.open("r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = self._json.loads(line)
                    seq = record.get("seq")
                    if seq is not None:
                        self._index[int(seq)] = record
                except self._json.JSONDecodeError as e:
                    logger.warning("JSONL 파싱 실패 (line %d): %s", lineno, e)

        logger.debug("CsiRawFileLoader: %d 레코드 로드 완료 (%s)", len(self._index), self._path.name)
        self._loaded = True

    def get_by_seq(self, seq: int) -> dict | None:
        """
        seq 번호로 CSI raw 레코드 조회

        Args:
            seq: csiRawRefs[i].seq 값

        Returns:
            CSI raw 레코드 딕셔너리, 없으면 None
        """
        self._load()
        record = self._index.get(seq)
        if record is None:
            logger.warning("seq=%d 레코드 없음", seq)
        return record


# ---------------------------------------------------------------------------
# loader 캐시 (rawLogFile 기반)
# ---------------------------------------------------------------------------

_loader_cache: dict[str, CsiRawFileLoader] = {}
CSI_RAW_BASE_DIR = "/home/wisasy/workspace/embedded/data/csi_raw"


def get_loader(raw_log_file: str) -> CsiRawFileLoader:
    """
    rawLogFile 파일명으로 CsiRawFileLoader 를 반환한다.
    동일 파일명이면 캐시된 인스턴스를 재사용한다.

    Args:
        raw_log_file: csi_raw JSONL 레코드의 rawLogFile 값
                      (예: "csi_raw_20260606.jsonl")

    Returns:
        CsiRawFileLoader 인스턴스
    """
    if raw_log_file not in _loader_cache:
        path = f"{CSI_RAW_BASE_DIR}/{raw_log_file}"
        _loader_cache[raw_log_file] = CsiRawFileLoader(path)
        logger.debug("CsiRawFileLoader 생성: %s", raw_log_file)
    return _loader_cache[raw_log_file]


def build_chunk_from_refs(
    csi_raw_refs: list[dict],
    num_subcarriers: int = 64,
) -> np.ndarray | None:
    """
    synced.frame 의 csiRawRefs 목록
    → rawLogFile 기반 loader 자동 결정
    → (time_steps, num_subcarriers) 복소수 배열

    csiRawRefs 각 항목의 rawLogFile 로 loader 를 결정하고,
    seq 로 JSONL 에서 실제 payloadBase64 를 조회한다.

    Args:
        csi_raw_refs: synced.frame["raw"]["csiRawRefs"]
        num_subcarriers: 서브캐리어 수

    Returns:
        shape (time_steps, num_subcarriers) 또는 None
    """
    rows = []
    for ref in csi_raw_refs:
        seq = ref.get("seq")
        packet_id = ref.get("packetId")  # 로그용
        raw_log_file = ref.get("rawLogFile")

        if seq is None or not raw_log_file:
            logger.warning(
                "csiRawRefs 항목 누락 (seq=%s, rawLogFile=%s, packetId=%s)",
                seq, raw_log_file, packet_id,
            )
            continue

        loader = get_loader(raw_log_file)
        record = loader.get_by_seq(int(seq))
        if record is None:
            logger.warning(
                "seq=%d 레코드 없음 (packetId=%s, rawLogFile=%s)",
                seq, packet_id, raw_log_file,
            )
            continue

        payload_b64 = record.get("payloadBase64", "")
        parsed = parse_nexmon_payload(payload_b64, num_subcarriers)
        if parsed is not None:
            rows.append(parsed)

    if not rows:
        logger.warning(
            "build_chunk_from_refs: 유효한 CSI 패킷 없음 (refs=%d)", len(csi_raw_refs)
        )
        return None

    return np.stack(rows, axis=0)  # (time_steps, num_subcarriers)


# ---------------------------------------------------------------------------
# ToF 전처리
# ---------------------------------------------------------------------------

class ToFPreprocessor:
    """
    ToF 센서 raw 거리값 처리

    - tofValid / tofError / tofTimeout 플래그 기반 무효값 처리
    - 에러값(error_value 이상) → 직전 유효값으로 대체
    """

    def __init__(self, error_value: int = 8190):
        """
        Args:
            error_value: ToF 에러 코드값. 이 값 이상이면 무효로 처리.
        """
        self.last_valid: float = 0.0
        self.error_value = error_value

    def process(self, distance) -> float:
        """
        단일 거리값 정제 (숫자값만 전달받는 경우)

        Args:
            distance: ToF 센서 raw 거리값 (mm)

        Returns:
            유효한 거리값 (mm). 무효면 직전 유효값 반환.
        """
        if distance is None:
            return self.last_valid
        try:
            d = float(distance)
        except (TypeError, ValueError):
            return self.last_valid

        if np.isnan(d) or d >= self.error_value:
            return self.last_valid

        self.last_valid = d
        return self.last_valid

    def process_from_frame(self, sensors: dict) -> float:
        """
        synced.frame 의 sensors 딕셔너리에서 ToF 처리

        tofValid / tofError / tofTimeout 플래그를 우선 확인한 후
        tofDistanceMm 값을 process() 로 넘긴다.

        Args:
            sensors: synced.frame["raw"]["sensorRaw"]["sensors"]

        Returns:
            유효한 거리값 (mm). 무효면 직전 유효값 반환.
        """
        if not sensors.get("tofValid", False):
            logger.debug("ToF invalid (tofValid=False)")
            return self.last_valid

        if sensors.get("tofError") is not None:
            logger.debug("ToF error: %s", sensors["tofError"])
            return self.last_valid

        if sensors.get("tofTimeout", False):
            logger.debug("ToF timeout")
            return self.last_valid

        return self.process(sensors.get("tofDistanceMm"))


# ---------------------------------------------------------------------------
# CSI 전처리
# ---------------------------------------------------------------------------

class CSIPreprocessor:
    """
    CSI raw 복소수 데이터 처리

    처리 순서:
      1. 진폭 계산
      2. 서브캐리어 그룹핑 (평균)
      3. Z-score 클리핑 (±3σ)
      4. Baseline 제거 (지수 이동 평균)
      5. Butterworth 저역통과 필터 (상태 유지)
    """

    def __init__(
        self,
        num_subcarriers: int = 64,
        group_size: int = 4,
        fs: float = 100.0,
        cutoff: float = 10.0,
        alpha: float = 0.05,
    ):
        """
        Args:
            num_subcarriers: CSI 서브캐리어 수
            group_size: 그룹핑 단위 (서브캐리어 평균)
            fs: 샘플링 주파수 (Hz)
            cutoff: 저역통과 필터 컷오프 주파수 (Hz)
            alpha: baseline 지수 이동 평균 계수 (작을수록 천천히 갱신)
        """
        self.num_subcarriers = num_subcarriers
        self.group_size = group_size
        self.num_groups = num_subcarriers // group_size

        nyq = 0.5 * fs
        normal_cutoff = cutoff / nyq
        self.b, self.a = butter(4, normal_cutoff, btype="low", analog=False)

        self.zi = np.zeros((max(len(self.a), len(self.b)) - 1, self.num_groups))
        self.first_run = True

        self.baseline_amp: np.ndarray | None = None
        self.alpha = alpha

    def process_chunk(self, csi_complex_chunk: np.ndarray) -> np.ndarray:
        """
        CSI 청크 전처리 (스트리밍, 필터 상태 유지)

        Args:
            csi_complex_chunk: shape (time_steps, num_subcarriers), 복소수 배열

        Returns:
            filtered_amp: shape (time_steps, num_groups), 정제된 진폭 배열
        """
        # 1. 진폭 계산
        amp = np.abs(csi_complex_chunk)

        # 2. 서브캐리어 그룹핑 (평균)
        time_steps = amp.shape[0]
        grouped_amp = amp.reshape(time_steps, self.num_groups, self.group_size).mean(axis=2)

        # 3. Z-score 클리핑 (±3σ)
        mean = np.mean(grouped_amp, axis=0)
        std = np.std(grouped_amp, axis=0)
        std = np.where(std == 0, 1e-6, std)
        clipped_amp = np.clip(grouped_amp, mean - 3 * std, mean + 3 * std)

        # 4. 동적 baseline 제거
        if self.baseline_amp is None:
            self.baseline_amp = np.mean(clipped_amp, axis=0)
        dynamic_amp = clipped_amp - self.baseline_amp
        self.baseline_amp = (
            (1 - self.alpha) * self.baseline_amp
            + self.alpha * np.mean(clipped_amp, axis=0)
        )

        # 5. Butterworth 저역통과 필터 (상태 유지)
        filtered_amp = np.zeros_like(dynamic_amp)
        if self.first_run:
            zi_base = lfilter_zi(self.b, self.a)
            for i in range(self.num_groups):
                self.zi[:, i] = zi_base * dynamic_amp[0, i]
            self.first_run = False

        for i in range(self.num_groups):
            filtered_amp[:, i], self.zi[:, i] = lfilter(
                self.b, self.a, dynamic_amp[:, i], zi=self.zi[:, i]
            )

        return filtered_amp

    def process_from_frame(self, frame: dict) -> np.ndarray | None:
        """
        synced.frame 에서 CSI 청크를 추출·전처리

        - transport.pingOk 가 False 이면 CSI 신뢰도 없음 → None 반환
        - csiRawRefs → build_chunk_from_refs() → process_chunk()
        - loader 는 csiRawRefs[].rawLogFile 기반으로 자동 결정

        Args:
            frame: synced.frame 딕셔너리

        Returns:
            filtered_amp: shape (time_steps, num_groups), 또는 None
        """
        sensor_raw = frame.get("raw", {}).get("sensorRaw", {})
        transport = sensor_raw.get("transport", {})

        if not transport.get("pingOk", True):
            logger.warning(
                "pingOk=False — ESP32↔AP 트래픽 단절, CSI 처리 스킵 (frameId=%s)",
                frame.get("frameId"),
            )
            return None

        refs = frame.get("raw", {}).get("csiRawRefs", [])
        chunk = build_chunk_from_refs(refs, self.num_subcarriers)
        if chunk is None:
            return None

        return self.process_chunk(chunk)


# ---------------------------------------------------------------------------
# 통합 프레임 처리 헬퍼
# ---------------------------------------------------------------------------

def process_synced_frame(
    frame: dict,
    tof_preprocessor: ToFPreprocessor,
    csi_preprocessor: CSIPreprocessor,
) -> dict:
    """
    synced.frame 하나를 받아 ToF + CSI 전처리 결과를 반환

    loader 는 csiRawRefs[].rawLogFile 을 보고 내부에서 자동 결정되므로
    호출부에서 별도로 관리할 필요 없다.

    Args:
        frame: synced.frame 딕셔너리 (/preprocess/synced_frame MQTT 메시지)
        tof_preprocessor: ToFPreprocessor 인스턴스
        csi_preprocessor: CSIPreprocessor 인스턴스

    Returns:
        {
            "frameId":        str,
            "timestamp":      str,
            "tofDistanceMm":  float,             # 정제된 ToF 거리값
            "pirMotion":      bool,
            "csiFilteredAmp": np.ndarray | None, # shape (time_steps, num_groups)
            "csiPacketCount": int,
            "pingOk":         bool,
        }
    """
    sensor_raw = frame.get("raw", {}).get("sensorRaw", {})
    sensors = sensor_raw.get("sensors", {})
    transport = sensor_raw.get("transport", {})
    summary = frame.get("summary", {})

    tof_distance = tof_preprocessor.process_from_frame(sensors)
    csi_filtered = csi_preprocessor.process_from_frame(frame)

    return {
        "frameId":        frame.get("frameId"),
        "timestamp":      frame.get("timestamp"),
        "tofDistanceMm":  tof_distance,
        "pirMotion":      sensors.get("pirMotion", False),
        "csiFilteredAmp": csi_filtered,
        "csiPacketCount": summary.get("csiPacketCount", 0),
        "pingOk":         transport.get("pingOk", False),
    }