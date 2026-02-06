import datetime
import re
import time
import google.generativeai as genai

# 운동 기록 함수
def log_workout(db, target_sheet, exercise, sets, weight, reps):
    valid_sheets = ["등", "가슴", "하체", "어깨", "이두", "삼두", "복근", "유산소", "기타"]
    if target_sheet not in valid_sheets: target_sheet = "기타"
    
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    # [날짜, 종목, 세트, 무게, 횟수, 1RM, 볼륨, 비고]
    row_data = [today, exercise, sets, weight, reps, "", "", ""]
    return db.append_row(target_sheet, row_data)

# [핵심] 운동 통계(볼륨, 1RM) 일괄 계산 함수
def batch_calculate(db, model_name="gemini-2.5-flash"):
    sheet_list = ["등", "가슴", "하체", "어깨", "이두", "삼두", "복근"]
    count = 0
    model = genai.GenerativeModel(model_name)
    
    for sheet in sheet_list:
        try:
            rows = db.get_all_values(sheet)
            header = rows[0]
            idx_w = header.index("무게")
            idx_r = header.index("횟수")
            idx_vol = header.index("볼륨")
            idx_note = next(i for i, h in enumerate(header) if "비고" in h)
            
            for i, row in enumerate(rows[1:], start=2):
                if (len(row)<=idx_vol or not row[idx_vol]) and row[idx_w] and row[idx_r]:
                    try:
                        # 숫자만 추출해서 계산
                        w = float(re.findall(r"[\d\.]+", row[idx_w])[0])
                        r = float(re.findall(r"[\d\.]+", row[idx_r])[0])
                        vol = int(w * r) # (단순 계산)
                        db.update_cell(sheet, i, idx_vol+1, vol)
                        
                        # 코멘트 없으면 추가
                        if not row[idx_note]:
                            prompt = f"헬스 코치 피드백(존댓말). 종목:{row[1]}, {w}kg {r}회."
                            res = model.generate_content(prompt)
                            db.update_cell(sheet, i, idx_note+1, res.text.strip())
                        count += 1
                        time.sleep(0.5)
                    except: continue
        except: continue
    return f"✅ {count}건 운동 통계 업데이트 완료"