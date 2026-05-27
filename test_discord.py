import os
import time
import requests
from dotenv import load_dotenv

# 1. .env 파일로부터 안전하게 디스코드 비밀 주소 로드
load_dotenv()
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def send_discord_notification(event_id, situation_summary):
    """
    라즈베리파이 메인 코드에서 낙상 감지 시 호출할 독립 알림 함수
    """
    if not WEBHOOK_URL:
        print("❌ 에러: .env 파일에 DISCORD_WEBHOOK_URL이 설정되지 않았습니다.")
        return

    # 2. 디스코드에서 지원하는 Embed(정형화된 박스) 포맷 데이터 구성
    payload = {
        "username": "RPi4_Fall_Detector",  # 디스코드에 표시될 봇 이름
        "avatar_url": "https://i.imgur.com/4M34gA0.png",  # 봇 프로필 이미지 (retro 픽셀 스타일)
        "embeds": [
            {
                "title": "🚨 [🚨 응급 상황] 피보호자 안전 이상 감지",
                "color": 15158332,  # 경고를 의미하는 진한 빨간색 코드
                "fields": [
                    {"name": "📌 사건 식별 ID", "value": event_id, "inline": True},
                    {"name": "⏰ 발생 시각", "value": time.strftime('%Y-%m-%d %H:%M:%S'), "inline": True},
                    {"name": "📊 현재 시스템 상태", "value": "FALL_CONFIRMED (낙상 확정)", "inline": False},
                    {"name": "📝 복합 상황 요약", "value": situation_summary, "inline": False}
                ],
                "footer": {
                    "text": "경북대학교 종합설계프로젝트 7팀 와사시"
                }
            }
        ]
    }

    print("디스코드 외부 알림 채널(REST API) 호출 중...")
    try:
        # 실시간성 보장을 위해 타임아웃 3초 제한 설정
        response = requests.post(WEBHOOK_URL, json=payload, timeout=3.0)
        
        # 디스코드 웹훅의 전송 성공 HTTP 상태 코드는 204(No Content)입니다.
        if response.status_code == 204:
            print("✅ 디스코드 보호자 관제 채널로 비상 알림 전송 성공!")
        else:
            print(f"❌ 전송 실패 (HTTP 상태 코드: {response.status_code})")
            print(response.text)
            
    except Exception as e:
        print(f"🔥 네트워크 단절 또는 요청 에러 발생: {e}")

if __name__ == "__main__":
    # 통합 전 단독 작동 여부를 확인하기 위한 모의 가상 데이터 유입
    print("=== 디스코드 알림 인터페이스 단독 기능 테스트 ===")
    mock_event_id = "EVT-20260527-01"
    mock_summary = "CSI 무선 신호 위상 반전 및 振幅 감쇠 발생. TTS 음성으로 상태 확인을 시도했으나 사용자가 10초간 아무런 움직임 및 응답을 보이지 않아 최종 낙상 상황으로 판정함."
    
    send_discord_notification(mock_event_id, mock_summary)