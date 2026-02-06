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

# 1. 설정
st.set_page_config(page_title="Project Jarvis", page_icon="👔", layout="wide")
st.markdown("<style>.stToast { background-color: #333; color: white; border-radius: 10px; }</style>", unsafe_allow_html=True)

if "GEMINI_API_KEY" not in st.secrets:
    st.error("Secrets 설정 필요"); st.stop()

# 2. 연결
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    db = database.DBHandler()
except Exception as e:
    st.error(f"연결 오류: {e}"); st.stop()

# 3. 도구(Tools) 정의
def tool_log_diet(menu: str, amount: str, meal_type: str):
    """식단 기록 도구"""
    res = diet.log_diet(db, menu, amount, meal_type)
    if res == "success": 
        st.toast(f"🥗 식단 저장: {menu}", icon="✅")
        return "성공: DB에 저장됨"
    return f"실패: {res}"

def tool_log_workout(target_sheet: str, exercise: str, sets: str, weight: str, reps: str):
    """운동 기록 도구"""
    res = workout.log_workout(db, target_sheet, exercise, sets, weight, reps)
    if res == "success": 
        st.toast(f"💪 운동 저장: {exercise}", icon="🔥")
        return "성공: DB에 저장됨"
    return f"실패: {res}"

def tool_save_memory(fact: str):
    """기억 저장 도구"""
    res = db.save_memory(fact)
    if res == "success": 
        st.toast("🧠 기억 저장", icon="💾")
        return "성공: 기억 DB에 저장됨"
    return f"실패: {res}"

tools = [tool_log_diet, tool_log_workout, tool_save_memory]

# 4. 모델 준비
memory_context = db.load_memory()
system_instruction = config.get_system_prompt(memory_context)
model = genai.GenerativeModel("gemini-2.5-flash", tools=tools, system_instruction=system_instruction)

# 5. UI 구성
st.title("Project Jarvis 👔")

with st.sidebar:
    st.header("🎛️ 업무 지시")
    if st.button("🥗 식단 일괄 채점"):
        with st.spinner("채점 중..."): st.success(diet.batch_score(db))
    if st.button("🏋️ 운동 통계 업데이트"):
        with st.spinner("계산 중..."): st.success(workout.batch_calculate(db))
    if st.button("📧 주간 리포트 발송"):
        with st.spinner("발송 중..."): 
            email = st.secrets.get("GMAIL_ID"); pw = st.secrets.get("GMAIL_APP_PW")
            st.success(report.send_weekly_report(db, email, pw))

if "messages" not in st.session_state: st.session_state.messages = []

for msg in st.session_state.messages:
    if msg["role"] != "function":
        with st.chat_message(msg["role"]):
            if "image" in msg: st.image(msg["image"], width=250)
            st.markdown(msg["content"])

with st.popover("📸 사진 추가", use_container_width=True):
    uploaded_file = st.file_uploader("업로드", type=['jpg','png'])

# ==========================================
# 6. 메인 로직 (Function Calling 에러 수정)
# ==========================================
if prompt := st.chat_input("지시를 내려주십시오."):
    with st.chat_message("user"):
        if uploaded_file:
            img = Image.open(uploaded_file)
            st.image(img, width=250)
            st.session_state.messages.append({"role":"user", "content":"[사진]", "image":img})
        st.markdown(prompt)
        st.session_state.messages.append({"role":"user", "content":prompt})

    try:
        # History
        history = []
        for m in st.session_state.messages:
            if m["role"] == "user":
                parts = [m["content"]]
                if "image" in m: parts.append(m["image"])
                history.append({"role":"user", "parts":parts})
            elif m["role"] == "model":
                history.append({"role":"model", "parts":[m["content"]]})
        
        curr_parts = [prompt]
        if uploaded_file and not any("image" in m for m in st.session_state.messages[-1:]):
            curr_parts.append(Image.open(uploaded_file))

        chat = model.start_chat(history=history[:-1])
        response = chat.send_message(curr_parts)

        # [핵심 수정] 함수 호출 루프 (While Loop)
        # AI가 도구를 쓰고 싶어하는 동안 계속 실행 (텍스트 변환 시도 X)
        while response.candidates and response.parts and response.parts[0].function_call:
            
            # 1. 함수 정보 가져오기
            fc = response.parts[0].function_call
            fname = fc.name
            fargs = dict(fc.args)
            
            # 2. 함수 실행
            tool_func = locals().get(fname)
            if tool_func:
                tool_result = tool_func(**fargs)
            else:
                tool_result = "Error: 존재하지 않는 도구"
            
            # 3. 결과를 AI에게 반환 (중요: 여기서 text를 달라고 하면 안됨)
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
            # 루프가 다시 돌면서, AI가 또 다른 함수를 쓸지 아니면 텍스트를 뱉을지 결정함

        # [안전장치] 모든 함수 실행이 끝나고 AI가 텍스트를 줬을 때만 출력
        if response.text:
            st.chat_message("assistant").markdown(response.text)
            st.session_state.messages.append({"role":"model", "content":response.text})
        
        if uploaded_file: st.rerun()

    except Exception as e:
        # 치명적 오류가 아니면 무시하고 넘어감 (사용성 개선)
        if "function_call" in str(e):
            st.rerun() # 에러 시 화면 새로고침으로 넘김
        else:
            st.error(f"시스템 오류: {e}")
