import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import datetime
import google.generativeai as genai

def send_weekly_report(db, email_id, email_pw, model_name="gemini-2.5-flash"):
    if not email_id: return "이메일 설정이 필요합니다."
    
    try:
        logs = db.get_all_values("통합로그")[-7:]
        diet = db.get_all_values("식단")[-7:]
        
        model = genai.GenerativeModel(model_name)
        prompt = f"""
        자비스, 주간 리포트를 작성하세요.
        [데이터]: 운동로그({logs}), 식단({diet})
        [형식]: 정중한 이메일 포맷. 성과 요약, 칭찬, 조언 포함.
        """
        res = model.generate_content(prompt)
        
        msg = MIMEMultipart()
        msg['From'] = email_id
        msg['To'] = email_id
        msg['Subject'] = f"[Jarvis] 주간 리포트 ({datetime.datetime.now().strftime('%Y-%m-%d')})"
        msg.attach(MIMEText(res.text, 'plain'))
        
        s = smtplib.SMTP('smtp.gmail.com', 587)
        s.starttls()
        s.login(email_id, email_pw)
        s.sendmail(email_id, email_id, msg.as_string())
        s.quit()
        return "📧 주간 리포트 발송 완료"
    except Exception as e: return f"발송 실패: {e}"