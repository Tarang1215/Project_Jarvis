import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
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
        return f"성공: {meal_type}에 '{menu}'({amount}) 저장 완료."
    return f"실패: {res}"

def tool_log_workout(target_sheet: str, exercise: str, sets: str, weight: str, reps: str):
    """운동을 기록합니다."""
    res = workout.log_workout(db, target_sheet, exercise, sets, weight, reps)
    if res == "success": 
        return f"성공: {target_sheet} 운동 '{exercise}' 저장 완료."
    return f"실패: {res}"

def tool_save_memory(fact: str):
    """기억을 저장합니다."""
    res = db.save_memory(fact)
    if res == "success": 
        return "성공: 기억 저장 완료."
    return f"실패: {res}"

tools = [tool_log_diet, tool_log_workout, tool_save_memory]

# 4. 모델 준비 (안전설정 해제 포함)
safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

try:
    memory_context = db.load_memory()
    system_instruction = config.get_system_prompt(memory_context)
    model = genai.GenerativeModel(
        "gemini-2.5-flash", 
        tools=tools, 
        system_instruction=system_instruction,
        safety_settings=safety_settings 
    )
except Exception as e:
    st.error(f"모델 로드 실패: {e}")

# 5. 화면 구성 (사이드바 메뉴 복구 완료)
st.title("Project Jarvis 👔")

with st.sidebar:
    st.header("🎛️ 업무 지시")
    # [복구됨] 식단 채점 버튼
    if st.button("🥗 식단 일괄 채점"):
        with st.spinner("채점 중..."): 
            st.info(diet.batch_score(db))
    
    # [복구됨] 운동 통계 버튼
    if st.button("🏋️ 운동 통계 업데이트"):
        with st.spinner("계산 중..."): 
            st.info(workout.batch_calculate(db))
            
    # [복구됨] 리포트 발송 버튼
    if st.button("📧 주간 리포트 발송"):
        with st.spinner("발송 중..."): 
            email = st.secrets.get("GMAIL_ID")
            pw = st.secrets.get("GMAIL_APP_PW")
            st.info(report.send_weekly_report(db, email, pw))
            
    st.divider()
    if st.button("🔄 대화 초기화"):
        st.session_state.messages = []
        st.rerun()

# 채팅창 표시
if "messages" not in st.session_state: st.session_state.messages = []

for msg in st.session_state.messages:
    if msg["role"] != "function":
        with st.chat_message(msg["role"]):
            if "image" in msg: st.image(msg["image"], width=250)
            st.markdown(msg["content"])

with st.popover("📸 사진 추가", use_container_width=True):
    uploaded_file = st.file_uploader("업로드", type=['jpg','png'])

# ==========================================
# 6. 메인 로직 (사진 분석 강화 + 도구 실행 보장)
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
        # 히스토리 구성
        history = []
        for m in st.session_state.messages:
            if m["role"] == "user":
                parts = [m["content"]]
                if "image" in m: parts.append(m["image"])
                history.append({"role":"user", "parts":parts})
            elif m["role"] == "model":
                history.append({"role":"model", "parts":[m["content"]]})
        
        # 입력 구성 (사진 들어오면 강제 명령 추가)
        curr_parts = []
        if uploaded_file and not any("image" in m for m in st.session_state.messages[-1:]):
            img_input = Image.open(uploaded_file)
            curr_parts.append(img_input)
            curr_parts.append(f"{prompt}\n(시스템 명령: 이 사진의 음식 메뉴와 양을 분석하고, 즉시 'tool_log_diet' 도구를 사용하여 기록해라. 분석 결과만 말하지 말고 반드시 도구를 실행해.)")
        else:
            curr_parts.append(prompt)

        # 챗 실행
        chat = model.start_chat(history=history[:-1])
        response = chat.send_message(curr_parts)

        # 도구 사용 루프
        executed_tools = []
        
        while response.candidates and response.parts and response.parts[0].function_call:
            fc = response.parts[0].function_call
            fname = fc.name
            fargs = dict(fc.args)

            st.toast(f"🤖 자비스가 [{fname}] 수행 중...", icon="⚙️")
            
            tool_func = locals().get(fname)
            if tool_func:
                tool_result = tool_func(**fargs)
                executed_tools.append(tool_result)
            else:
                tool_result = "Error: 도구 없음"
            
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

        # 최종 응답 출력
        final_text = ""
        try:
            if response.text:
                final_text = response.text
        except ValueError:
            if executed_tools:
                final_text = f"✅ 처리 완료되었습니다.\n\n[실행 결과]\n" + "\n".join(executed_tools)
            else:
                final_text = "시스템: 응답을 생성하지 못했습니다. (사진 분석 실패 가능성)"
        
        if not final_text and executed_tools:
             final_text = f"✅ 기록을 완료했습니다.\n" + "\n".join(executed_tools)

        st.chat_message("assistant").markdown(final_text)
        st.session_state.messages.append({"role":"model", "content":final_text})
        
        if uploaded_file: st.rerun()

    except Exception as e:
        st.error(f"오류 발생: {e}")
