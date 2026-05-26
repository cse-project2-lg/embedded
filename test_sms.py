import os
import time
import requests
import hmac
import hashlib
import uuid
from dotenv import load_workbook, load_dotenv

# .env 파일에 적힌 비밀 정보들을 메모리로 로드합니다.
load_dotenv()

# 1. 가상 데이터 정의 (요구사항서 스펙 기반)
mock_event_id = "EVT-20260523"
mock_situation = "사용자 TTS 확인 질문에 무응답 (낙상 확정 위험 고조)"

# 2. 발급받은 API 정보 기입 (테스트용)
API_KEY = os.environ.get("SOLAPI_API_KEY")
API_SECRET = os.environ.get("SOLAPI_API_SECRET")
SENDER = os.environ.get("SENDER_NUMBER")
RECEIVER = os.environ.get("RECEIVER_NUMBER")

def send_test_sms():
    url = "https://api.solapi.com/messages/v4/send-many"
    
    # 2. 솔라피 v4 표준 인증 헤더 생성 로직 (InvalidToken 해결의 핵심)
    date = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    salt = str(uuid.uuid1().hex)
    combined = date + salt
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        combined.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # 솔라피가 요구하는 정확한 토큰 생성 규칙 적용
    authorization_header = f"HMAC-SHA256 apiKey={API_KEY}, date={date}, salt={salt}, signature={signature}"

    text_content = f"[낙상위험] ID:{mock_event_id} 발생시각:{time.strftime('%H:%M:%S')} 무응답. 확인바람."
    ###(
    ###    f"[🚨 비상 알림]\n"
    ###    f"사건ID: EVT-20260523\n"
    ###    f"발생시각: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    ###    f"상황: 사용자 TTS 확인 질문 무응답\n"
    ###    f"즉시 확인 바랍니다."
    ###)
    
    payload = {
        "messages": [
            {
                "to": RECEIVER,
                "from": SENDER,
                "text": text_content
            }
        ]
    }
    
    # 수정된 헤더 구조 적용
    headers = {
        "Authorization": authorization_header,
        "Content-Type": "application/json"
    }

    print("보호자 알림 REST API 요청 전송 중...")
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=3.0)
        if response.status_code == 200:
            print("✅ 구글 클라우드 환경에서 보호자 문자 발송 성공!")
            print(response.json())
        else:
            print(f"❌ 전송 실패 (오류 코드: {response.status_code})")
            print(response.text)
    except Exception as e:
        print(f"🔥 통신 에러: {e}")

if __name__ == "__main__":
    send_test_sms()