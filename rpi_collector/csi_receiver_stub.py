"""Nexmon CSI receiver placeholder.

placeholder의 의미:
- CSI 수신 코드가 들어갈 파일 위치만 잡아둔 상태다.
- 현재 파일은 실제 CSI를 받거나 파싱하지 않는다.
- /sensor/raw JSON에도 CSI를 넣지 않는다.

담당 구분:
- 통신 : 이 파일 위치와 인터페이스 약속을 잡을 수 있음.
- 전처리/동기화 : UDP 5500/pcap 수신, complex numpy array 변환,
  CSI feature 계산, PIR/ToF와 시간 동기화를 구현해야 함.

나중에 전처리 구현할 예시 흐름:
    Nexmon CSI UDP 5500 수신
    -> CSI payload 파싱
    -> complex numpy array 생성
    -> CSIProcessor.process_chunk() 호출
    -> sensorSummary.csi.changeScore / packetCount 생성
    -> PIR/ToF raw와 동기화
    -> event_candidate_publisher.publish_event_candidate(candidate)
"""


def main() -> None:
    print("CSI receiver placeholder only.")
    print("실제 CSI 수신/파싱/동기화 로직은 전처리 모듈에서 구현해야 합니다.")


if __name__ == "__main__":
    main()
