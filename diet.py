import datetime
import gspread
import google.generativeai as genai
import streamlit as st

# ==========================================
# 1. 식단 기록 함수 (아까 잘 되던 그 코드)
# ==========================================
def log_diet(db, menu, amount, meal_type):
    """
    사용자 시트 구조: 
    날짜(A) | 아침(B) | 점심(C) | 간식(D) | 저녁(E) | 운동후보충제(F) | Total Input(G) | Score(H) | Comments(I)
    """
    try:
        try:
            ws = db.doc.worksheet("식단")
        except:
            return "오류: '식단' 시트를 찾을 수 없습니다."

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # 컬럼 매핑 (1부터 시작)
        col_map = {
            "아침": 2,          # B열
            "점심": 3,          # C열
            "간식": 4,          # D열
            "저녁": 5,          # E열
            "보충제": 6,        # F열
            "운동후보충제": 6
        }
        target_col = col_map.get(meal_type, 4) 
        input_text = f"{menu}({amount})"

        try:
            cell = ws.find(today)
        except:
            cell = None

        if cell:
            row_idx = cell.row
            curr_val = ws.cell(row_idx, target_col).value
            new_val = f"{curr_val}, {input_text}" if curr_val else input_text
            ws.update_cell(row_idx, target_col, new_val)
            return "success"
        else:
            # 9칸 확보 (Total, Score, Comments 포함)
            new_row = [today, "", "", "", "", "", "", "", ""] 
            new_row[target_col-1] = input_text
            ws.append_row(new_row)
            return "success"

    except Exception as e:
        return f"에러 발생: {str(e)}"

# ==========================================
# 2. 식단 채점 함수 (복구됨!)
# ==========================================
def batch_score(db):
    """
    최근 5일치 기록 중, Score(H열)가 비어있는 날을 찾아 채점합니다.
    """
    try:
        ws = db.doc.worksheet("식단")
        # 전체 데이터를 가져옴 (헤더 제외)
        rows = ws.get_all_values()
        
        # Gemini 모델 준비
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        updated_count = 0
        
        # 최근 5개 행만 검사 (속도 최적화)
        # rows[1:]는 헤더 제외, [-5:]는 뒤에서 5개
        target_rows = list(enumerate(rows))[1:][-5:]
        
        for idx, row in target_rows:
            # row 인덱스 주의: 0부터 시작. 
            # 시트 구조: 날짜(0), 아침(1), 점심(2), 간식(3), 저녁(4), 보충제(5), Total(6), Score(7), Comments(8)
            
            # 데이터가 9개보다 적으면 빈 문자열로 채움 (에러 방지)
            while len(row) < 9:
                row.append("")

            # 이미 점수(7번 인덱스)가 있으면 패스
            if row[7].strip() != "":
                continue
                
            # 먹은 게 아무것도 없으면 패스 (아침~보충제까지 다 비었는지 체크)
            if "".join(row[1:6]).strip() == "":
                continue

            # --- AI 채점 시작 ---
            diet_summary = f"""
            날짜: {row[0]}
            아침: {row[1]}
            점심: {row[2]}
            간식: {row[3]}
            저녁: {row[4]}
            보충제: {row[5]}
            """
            
            prompt = f"""
            너는 엄격한 헬스 트레이너야. 아래 식단을 보고 3가지 항목을 채워줘.
            
            [식단 정보]
            {diet_summary}
            
            [필수 답변 형식]
            반드시 아래 형식 그대로, 파이프(|)로 구분해서 한 줄로 대답해. 다른 말 금지.
            총 칼로리/단백질 추정 | 10점 만점 점수 | 피드백 한 줄
            
            예시:
            2100kcal, 단백질 140g | 8 | 단백질은 충분하나 점심에 지방이 과했습니다. 클린하게 드세요.
            """
            
            response = model.generate_content(prompt)
            result_text = response.text.strip()
            
            # 결과 파싱 ( | 로 나눔)
            parts = result_text.split('|')
            if len(parts) == 3:
                total_input = parts[0].strip()
                score = parts[1].strip()
                comment = parts[2].strip()
                
                # 시트에 업데이트 (행 번호는 idx + 1)
                # G열(7), H열(8), I열(9)
                ws.update_cell(idx + 1, 7, total_input) # Total Input
                ws.update_cell(idx + 1, 8, score)       # Score
                ws.update_cell(idx + 1, 9, comment)     # Comments
                
                updated_count += 1
                
        if updated_count > 0:
            return f"✅ {updated_count}일치 식단을 채점하고 피드백을 남겼습니다."
        else:
            return "👌 채점할 새로운 식단이 없습니다."

    except Exception as e:
        return f"채점 중 오류 발생: {str(e)}"
