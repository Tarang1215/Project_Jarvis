import datetime
import time
import json
import re
import google.generativeai as genai
import streamlit as st

# ==========================================
# 1. 식단 기록 함수 (기존 로직 유지 + 안정성 보강)
# ==========================================
def log_diet(db, menu, amount, meal_type):
    try:
        try:
            ws = db.doc.worksheet("식단")
        except:
            return "오류: '식단' 시트가 없습니다."

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # 컬럼 매핑 (A=1, B=2, ... )
        col_map = {
            "아침": 2, "점심": 3, "간식": 4, "저녁": 5, 
            "보충제": 6, "운동후보충제": 6
        }
        target_col = col_map.get(meal_type, 4) 
        input_text = f"{menu}({amount})"

        # 오늘 날짜 찾기
        try:
            cell = ws.find(today)
        except:
            cell = None

        if cell:
            row_idx = cell.row
            # 기존 값 가져오기
            curr_val = ws.cell(row_idx, target_col).value
            # 이미 값이 있으면 콤마로 연결
            new_val = f"{curr_val}, {input_text}" if curr_val else input_text
            ws.update_cell(row_idx, target_col, new_val)
            return "success"
        else:
            # 새로운 행 추가 (Total, Score, Comments 포함 9열)
            # A, B, C, D, E, F, G(Total), H(Score), I(Comments)
            new_row = [today, "", "", "", "", "", "", "", ""] 
            new_row[target_col-1] = input_text
            ws.append_row(new_row)
            return "success"

    except Exception as e:
        return f"에러 발생: {str(e)}"

# ==========================================
# 2. 식단 채점 함수 (JSON 파싱 방식으로 전면 수정)
# ==========================================
def batch_score(db):
    try:
        ws = db.doc.worksheet("식단")
        rows = ws.get_all_values()
        
        # 모델 설정 (JSON 응답 유도를 위해 온도를 낮춤)
        generation_config = {"temperature": 0.2}
        model = genai.GenerativeModel("gemini-2.5-flash", generation_config=generation_config)
        
        updated_count = 0
        
        # 헤더(rows[0]) 제외하고 데이터 확인
        # (인덱스, 데이터) 형태로 변환하여 처리
        for i, row in enumerate(rows):
            if i == 0: continue # 헤더 건너뜀

            # row 인덱스 매칭 (gspread는 1부터 시작하므로 i+1이 행 번호)
            current_row_num = i + 1

            # 데이터 길이 보정 (9개 미만이면 빈칸 채움)
            while len(row) < 9:
                row.append("")

            # [조건 1] 이미 채점된 경우(H열/Index 7) 건너뜀
            if row[7].strip(): 
                continue

            # [조건 2] 식단 데이터가 아예 없는 경우(B~F열) 건너뜀
            diet_content = "".join(row[1:6]).strip()
            if not diet_content:
                continue

            # --- 채점 로직 시작 ---
            prompt = f"""
            너는 깐깐한 헬스 트레이너 '자비스'야. 사용자의 하루 식단을 분석해서 JSON으로 응답해.
            
            [사용자 식단]
            - 날짜: {row[0]}
            - 아침: {row[1]}
            - 점심: {row[2]}
            - 간식: {row[3]}
            - 저녁: {row[4]}
            - 보충제: {row[5]}

            [사용자 프로필]
            - 목표: 체지방 감소 및 근육량 유지 (커팅)
            - 키/몸무게: 183cm / 82kg

            [필수 응답 포맷 - JSON Only]
            반드시 아래 JSON 형식으로만 출력해. 마크다운이나 잡담 금지.
            {{
                "total": "약 0000kcal (탄:00g, 단:00g, 지:00g)",
                "score": "80",
                "comment": "존댓말 피드백 한 줄. (냉정하게 평가)"
            }}
            """

            try:
                response = model.generate_content(prompt)
                raw_text = response.text.strip()

                # 마크다운 ```json ... ``` 제거 (Gemini가 자주 붙임)
                clean_text = raw_text.replace("```json", "").replace("```", "").strip()
                
                # JSON 파싱
                data = json.loads(clean_text)

                # 결과값 추출
                total_val = data.get("total", "계산 불가")
                score_val = data.get("score", "0")
                comment_val = data.get("comment", "분석 실패")

                # 시트 업데이트 (G, H, I 열 -> 인덱스 7, 8, 9)
                ws.update_cell(current_row_num, 7, total_val) # G열
                ws.update_cell(current_row_num, 8, score_val) # H열
                ws.update_cell(current_row_num, 9, comment_val) # I열
                
                updated_count += 1
                
                # API 호출 제한 방지 딜레이
                time.sleep(1.5)

            except Exception as e:
                print(f"Row {current_row_num} 분석 실패: {e}")
                continue

        if updated_count > 0:
            return f"✅ 총 {updated_count}일치 식단 분석 및 채점 완료."
        else:
            return "👌 채점할 새로운 식단 데이터가 없습니다."

    except Exception as e:
        return f"시스템 오류: {str(e)}"
