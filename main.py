import streamlit as st
import google.generativeai as genai
from PIL import Image
import time

# 우리가 만든 모듈들 불러오기
import config
import database
import diet
import workout
import report

# ==========================================
# 1. 초기화 및 설정
# ==========================================
st.set_page_config(page_title="Project Jarvis", page_icon="👔", layout="wide")
st.markdown("<style>.stToast { background-color: #333; color: white; border-radius: 10px; }</style>", unsafe_allow_html=True)

# Secrets 확인
if "GEMINI_API_KEY" not in st.secrets:
    st.error("Secrets 설정이 필요합니다."); st.stop()

# Gemini 및 DB 연결
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    db = database.DBHandler()
except Exception as e:
    st.error(f"연결 오류: {e}")
    st.stop()

# ==========================================
# 2. AI 도구 정의 (Wrapper Functions)
# ==========================================
def tool_log_diet(menu: str, amount: str, meal_type: str):
    """식단을 기록합니다."""
    res = diet.log_diet(db, menu, amount, meal_type)
    if res == "success": 
        st.toast(f"🥗 {menu}", icon="✅")
        return "성공: 식단 DB에 저장됨"
    return f"실패: {res}"

def tool_log_workout(target_sheet: str, exercise: str, sets: str, weight: str, reps: str):
    """운동 기록."""
    res = workout.log_workout(db, target_sheet, exercise, sets, weight, reps)
    if res == "success": 
        st.toast(f"💪 {exercise} -> {target_sheet}", icon="🔥")
        return "성공: 운동 DB에 저장됨"
    return f"실패: {res}"

def tool_save_memory(fact: str):
    """기억 저장."""
    res = db.save_memory(fact)
    if res == "success": 
        st.toast("🧠 기억 저장", icon="💾")
        return "성공: 기억 DB에 저장됨"
    return f"실패: {res}"

tools = [tool_log_diet, tool_log_workout, tool_save_memory]

# ==========================================
# 3. 모델 준비
# ==========================================
memory_context = db.load_memory()
system_instruction = config.get_system_prompt(memory_context)
model = genai.GenerativeModel("gemini-2.5-flash", tools=tools, system_instruction=system_instruction)

# ==========================================
# 4. UI 화면 구성
# ==========================================
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

if "messages" not in st.session_state: st.session_state.messages = []

for msg in st.session_state.messages:
    if msg["role"] != "function":
        with st.chat_message(msg["role"]):
            if "image" in msg: st.image(msg["image"], width=250)
            st.markdown(msg["content"])

with st.popover("📸 사진 추가", use_container_width=True):
    uploaded_file = st.file_uploader("업로드", type=['jpg','png'])

# ==========================================
# 5. 메인 채팅 로직 (안전장치 강화판)
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
        # History 구성
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

        # AI 호출
        chat = model.start_chat(history=history[:-1])
        res = chat.send_message(curr_parts)

        # [핵심] 도구 사용 루프
        while True:
            # 1. 함수 호출이 있는지 체크
            if not (res.candidates and res.parts and res.parts[0].function_call):
                break # 함수 호출 없으면 루프 종료 (텍스트 답변이라는 뜻)

            # 2. 함수 정보 추출
            fc = res.parts[0].function_call
            fname = fc.name
            fargs = dict(fc.args)
            
            # 3. 함수 실행
            tool_func = locals().get(fname)
            val = tool_func(**fargs) if tool_func else "Error: 함수 없음"
            
            # 4. 결과 반환 (텍스트 요구 X)
            res = chat.send_message(
                genai.protos.Content(
                    parts=[genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=fname, 
                            response={"result": val}
                        )
                    )]
                )
            )

        # [핵심] 텍스트 변환 안전장치
        # AI가 최종적으로 말을 할 때만 화면에 뿌림. 만약 여전히 함수 신호라면 무시함.
        final_text = ""
        try:
            # text 속성에 접근할 때 에러가 나면 그냥 빈 문자열로 처리
            if res.candidates and res.parts and res.parts[0].text:
                final_text = res.text
        except ValueError:
            pass # 함수 호출 신호면 무시

        if final_text:
            st.chat_message("assistant").markdown(final_text)
            st.session_state.messages.append({"role":"model", "content":final_text})
        
        if uploaded_file: st.rerun()

    except Exception as e:
        # 에러가 나도 죽지 않고 경고만 띄움
        st.warning(f"처리 중 사소한 오류가 있었으나 기록은 되었습니다: {e}")
