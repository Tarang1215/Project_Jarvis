import streamlit as st
import google.generativeai as genai
from PIL import Image
import time

# 모듈 불러오기
import config
import database
import diet
import workout
import report

# 1. 기본 설정
st.set_page_config(page_title="Project Jarvis", page_icon="👔", layout="wide")
st.markdown("<style>.stToast { background-color: #333; color: white; border-radius: 10px; }</style>", unsafe_allow_html=True)

# 2. API 연결
try:
    if "GEMINI_API_KEY" not in st.secrets:
        st.error("Secrets에 GEMINI_API_KEY가 없습니다."); st.stop()
    
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    db = database.DBHandler()
except Exception as e:
    st.error(f"초기 연결 실패: {e}"); st.stop()

# 3. 도구(Tools) 정의
def tool_log_diet(menu: str, amount: str, meal_type: str):
    """식단을 기록합니다."""
    res = diet.log_diet(db, menu, amount, meal_type)
    if res == "success": 
        return "성공: 식단 DB에 저장됨"
    return f"실패: {res}"

def tool_log_workout(target_sheet: str, exercise: str, sets: str, weight: str, reps: str):
    """운동을 기록합니다."""
    res = workout.log_workout(db, target_sheet, exercise, sets, weight, reps)
    if res == "success": 
        return "성공: 운동 DB에 저장됨"
    return f"실패: {res}"

def tool_save_memory(fact: str):
    """기억을 저장합니다."""
    res = db.save_memory(fact)
    if res == "success": 
        return "성공: 기억 DB에 저장됨"
    return f"실패: {res}"

tools = [tool_log_diet, tool_log_workout, tool_save_memory]

# 4. 모델 준비
try:
    memory_context = db.load_memory()
    system_instruction = config.get_system_prompt(memory_context)
    model = genai.GenerativeModel("gemini-2.5-flash", tools=tools, system_instruction=system_instruction)
except Exception as e:
    st.error(f"모델 로드 실패: {e}")

# 5. 화면 구성
st.title("Project Jarvis 👔")

# 사이드바
with st.sidebar:
    st.header("🎛️ 상태창")
    if st.button("🔄 시스템 리셋"):
        st.session_state.messages = []
        st.rerun()

# 채팅 기록 표시
if "messages" not in st.session_state: st.session_state.messages = []

for msg in st.session_state.messages:
    if msg["role"] != "function": # 함수 처리 과정은 숨김
        with st.chat_message(msg["role"]):
            if "image" in msg: st.image(msg["image"], width=250)
            st.markdown(msg["content"])

# 사진 업로드
with st.popover("📸 사진 추가", use_container_width=True):
    uploaded_file = st.file_uploader("업로드", type=['jpg','png'])

# ==========================================
# 6. 메인 로직 (무응답 방지 버전)
# ==========================================
if prompt := st.chat_input("지시를 내려주십시오."):
    
    # 1. 사용자 메시지 표시
    with st.chat_message("user"):
        if uploaded_file:
            img = Image.open(uploaded_file)
            st.image(img, width=250)
            st.session_state.messages.append({"role":"user", "content":"[사진]", "image":img})
        st.markdown(prompt)
        st.session_state.messages.append({"role":"user", "content":prompt})

    # 2. AI 처리 시작
    try:
        # 히스토리 구성
        history = []
        for m in st.session_state.messages:
            if m["role"] == "user":
                parts = [m["content"]]
                if "image" in m: parts.append(m["image"])
                history.append({"role":"user", "parts":parts})
            elif m["role"] == "model":
                history.append({"role":"model", "parts":[m["content"]]})
        
        # 현재 입력 구성
        curr_parts = [prompt]
        if uploaded_file and not any("image" in m for m in st.session_state.messages[-1:]):
            curr_parts.append(Image.open(uploaded_file))

        # 챗 세션 시작
        chat = model.start_chat(history=history[:-1])
        response = chat.send_message(curr_parts)

        # 3. 도구(Function) 사용 루프
        # AI가 도구를 쓰는 동안은 계속 여기서 돕니다.
        loop_limit = 0
        while response.candidates and response.parts and response.parts[0].function_call:
            
            loop_limit += 1
            if loop_limit > 5: break # 무한루프 방지

            # 함수 정보 추출
            fc = response.parts[0].function_call
            fname = fc.name
            fargs = dict(fc.args)

            # 토스트 메시지로 진행상황 보여주기 (중요: 사용자가 멈춘 게 아니란 걸 알게 함)
            st.toast(f"🤖 자비스가 [{fname}] 기능을 수행 중...", icon="⚙️")

            # 함수 실행
            tool_func = locals().get(fname)
            if tool_func:
                tool_result = tool_func(**fargs)
            else:
                tool_result = "Error: 존재하지 않는 도구입니다."
            
            # 결과를 AI에게 반환
            response = chat.send_message(
                genai.protos.Content(
                    parts=[genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=fname,
                            response={"result": tool_result}
                        )
                    )]
                )
            )

        # 4. 최종 답변 출력 (이제 안전하게 텍스트를 꺼냅니다)
        final_text = ""
        try:
            final_text = response.text
        except ValueError:
            # 텍스트가 없으면(여전히 함수 호출이거나 등등) 강제로 내용을 확인
            final_text = "시스템: 처리 완료되었으나 텍스트 응답이 생성되지 않았습니다."
        
        if final_text:
            st.chat_message("assistant").markdown(final_text)
            st.session_state.messages.append({"role":"model", "content":final_text})
        
        if uploaded_file: st.rerun()

    except Exception as e:
        # 에러가 나면 숨기지 말고 그대로 보여줌 (그래야 원인을 앎)
        st.error(f"시스템 처리 중 오류 발생: {e}")
