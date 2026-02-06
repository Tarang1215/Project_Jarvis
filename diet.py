import datetime
import time
import json
import google.generativeai as genai

# 식단 기록 함수
def log_diet(db, menu, amount, meal_type):
    try:
        col_map = {"아침": 2, "점심": 3, "간식": 4, "저녁": 5, "보충제": 6}
        target_col = col_map.get(meal_type, 4)
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        cell = db.find_cell("식단", today)
        input_txt = f"{menu}({amount})"
        
        if cell:
            curr = db.get_cell_value("식단", cell.row, target_col)
            new_val = f"{curr}, {input_txt}" if curr else input_txt
            db.update_cell("식단", cell.row, target_col, new_val)
        else:
            row = [today, "", "", "", "", "", ""]
            row[target_col-1] = input_txt
            db.append_row("식단", row)
        return "success"
    except Exception as e: return str(e)

# [핵심] 식단 일괄 채점 함수
def batch_score(db, model_name="gemini-2.5-flash"):
    rows = db.get_all_values("식단")
    # 헤더 인덱스 찾기
    try:
        idx_total = rows[0].index("Total")
        idx_score = rows[0].index("Score")
        idx_cmt = 8 
    except: return "식단 시트 헤더 오류"

    updates = []
    for i, row in enumerate(rows[1:], start=2):
        has_food = any(len(row)>j and row[j] for j in [1,2,3,4,5])
        no_score = (len(row) <= idx_score) or (not row[idx_score])
        if has_food and no_score:
            updates.append((i, f"아침:{row[1]}, 점심:{row[2]}, 저녁:{row[4]}, 간식:{row[3]}"))

    if not updates: return "채점할 데이터가 없습니다."

    count = 0
    model = genai.GenerativeModel(model_name)
    for r_idx, txt in updates:
        prompt = f"""
        영양사로서 식단 평가. User: 183cm/82kg (커팅중). 식단: {txt}
        JSON 응답: {{ "total": "C:.. P:.. F:..", "score": 85, "comment": "존댓말 평가" }}
        """
        try:
            res = model.generate_content(prompt)
            data = json.loads(res.text.strip().replace("```json","").replace("```",""))
            db.update_cell("식단", r_idx, idx_total+1, data.get("total",""))
            db.update_cell("식단", r_idx, idx_score+1, data.get("score",0))
            db.update_cell("식단", r_idx, idx_cmt+1, data.get("comment",""))
            count += 1
            time.sleep(1)
        except: continue
    return f"✅ {count}일치 식단 채점 완료"