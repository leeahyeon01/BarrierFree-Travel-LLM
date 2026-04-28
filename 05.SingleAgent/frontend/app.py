import streamlit as st
import requests
import os
import sys

st.set_page_config(page_title="배리어프리 Agent", page_icon="♿", layout="wide")
st.title("♿ 무장애 여행 기획 에이전트")

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "안녕하세요! 원하시는 여행 목적지와 조건(예: 휠체어 사용, 단차 없는 곳 등)을 말씀해주세요."}
    ]

# 기존 대화 렌더링
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("예: 제주도 1박 2일 여행갈래. 휠체어 이용할거야.")

if user_input:
    # 사용자 메시지 표시
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 에이전트 답변 생성
    with st.chat_message("assistant"):
        with st.spinner("에이전트가 최적의 코스를 찾고 검증하는 중입니다... (최대 1~2분 소요)"):
            
            # Docker 컨테이너 등 API 서버가 떠있을 경우의 호출 주소
            API_URL = os.getenv("API_URL", "http://localhost:8000/chat")
            
            try:
                resp = requests.post(API_URL, json={"message": user_input}, timeout=120)
                if resp.status_code == 200:
                    reply = resp.json().get("reply", "응답 오류가 발생했습니다.")
                else:
                    reply = f"API 서버 에러: {resp.status_code}"
            except requests.exceptions.ConnectionError:
                # 로컬에서 API 서버를 띄우지 않고 Streamlit만 단독 실행했을 때를 위한 Fallback
                st.warning("⚠️ API 서버에 연결할 수 없어 로컬 모듈을 직접 호출합니다.")
                sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
                from backend.agent import run_agent
                reply = run_agent(user_input)
                
        st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})
