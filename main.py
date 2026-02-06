import streamlit as st
import google.generativeai as genai
from PIL import Image

# 우리가 만든 모듈들 불러오기
import config
import database
import diet
import workout
import report

# 1. 초기화
st.set_page_config(page_title="Project Jarvis", page_icon="👔", layout="wide")
st.markdown("<style>.stToast { background-color: #333; color: white; border-radius: 10px; }</style>", unsafe_allow_html=True)

if "GEMINI_API_KEY" not in st.secrets:
    st.error("Secrets 설정이 필요합니다."); st.stop()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
db = database.DBHandler() # DB 연결

# 2. AI 도구 정의 (여기서 모듈의 함수를 호출함)
def tool_log_diet(menu: str, amount: str, meal_type: str):
    """식단 기록."""
    res = diet.log_diet(db, menu, amount, meal_type)
    if res == "success": st.toast(f"🥗 {menu}", icon="✅"); return "성공"
    return "실패"

def tool_log_workout(target_sheet: str, exercise: str, sets: str, weight: str, reps: str):
    """운동 기록. target_sheet는 [등,가슴,하체,어깨,이두,삼두,복근,유산소] 중 AI 판단."""
    res = workout.log_workout(db, target_sheet, exercise, sets, weight, reps)
    if res == "success": st.toast(f"💪 {exercise} -> {target_sheet}", icon="🔥"); return "성공"
    return "실패"

def tool_save_memory(fact: str):
    """기억 저장."""
    res = db.save_memory(fact)
    if res == "success": st.toast("🧠 기억 저장", icon="💾"); return "성공"
    return "실패"

tools = [tool_log_diet, tool_log_workout, tool_save_memory]

# 3. 모델 준비
memory_context = db.load_memory()
system_instruction = config.get_system_prompt(memory_context)
model = genai.GenerativeModel("gemini-2.5-flash", tools=tools, system_instruction=system_instruction)

# 4. 화면 구성 (UI)
st.title("Project Jarvis 👔")

with st.sidebar:
    st.header("🎛️ 업무 지시")
    if st.button("🥗 식단 일괄 채점"):
        with st.spinner("채점 중..."): st.success(diet.batch_score(db))
    if st.button("🏋️ 운동 통계 업데이트"):
        with st.spinner("계산 중..."): st.success(workout.batch_calculate(db))
    if st.button("📧 주간 리포트 발송"):
        with st.spinner("발송 중..."): 
            email = st.secrets.get("GMAIL_ID")
            pw = st.secrets.get("GMAIL_APP_PW")
            st.success(report.send_weekly_report(db, email, pw))

# 채팅창 로직
if "messages" not in st.session_state: st.session_state.messages = []

for msg in st.session_state.messages:
    if msg["role"] != "function":
        with st.chat_message(msg["role"]):
            if "image" in msg: st.image(msg["image"], width=250)
            st.markdown(msg["content"])

with st.popover("📸 사진 추가", use_container_width=True):
    uploaded_file = st.file_uploader("업로드", type=['jpg','png'])

if prompt := st.chat_input("지시를 내려주십시오."):
    with st.chat_message("user"):
        if uploaded_file:
            img = Image.open(uploaded_file)
            st.image(img, width=250)
            st.session_state.messages.append({"role":"user", "content":"[사진]", "image":img})
        st.markdown(prompt)
        st.session_state.messages.append({"role":"user", "content":prompt})

    try:
        # 히스토리 생성
        history = []
        for m in st.session_state.messages:
            if m["role"] == "user":
                parts = [m["content"]]
                if "image" in m: parts.append(m["image"])
                history.append({"role":"user", "parts":parts})
            elif m["role"] == "model":
                history.append({"role":"model", "parts":[m["content"]]})
        
        # 현재 입력
        curr_parts = [prompt]
        if uploaded_file and not any("image" in m for m in st.session_state.messages[-1:]):
            curr_parts.append(Image.open(uploaded_file))

        # AI 실행
        chat = model.start_chat(history=history[:-1])
        res = chat.send_message(curr_parts)

        # 도구 사용 루프
        while res.parts and res.parts[0].function_call:
            fc = res.parts[0].function_call
            fname = fc.name
            fargs = dict(fc.args)
            tool_func = locals().get(fname) # 현재 스코프에서 함수 찾기
            val = tool_func(**fargs) if tool_func else "Error"
            
            res = chat.send_message(genai.protos.Content(parts=[genai.protos.Part(function_response=genai.protos.FunctionResponse(name=fname, response={"result": val}))]))
        
        if res.text:
            st.chat_message("assistant").markdown(res.text)
            st.session_state.messages.append({"role":"model", "content":res.text})
        
        if uploaded_file: st.rerun()
    except Exception as e: st.error(f"Error: {e}")