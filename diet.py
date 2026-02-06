import datetime
import time
import json
import google.generativeai as genai
import streamlit as st

# ==========================================
# 1. 식단 기록 함수 (기존 유지)
# ==========================================
def log_diet(db, menu, amount, meal_type):
    try:
        try:
            ws = db.doc.worksheet("식단")
        except:
            return "오류: '식단' 시트가 없습니다."

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        col_map = {
            "아침": 2, "점심": 3, "간식": 4, "저녁": 5, 
            "보충제": 6, "운동후보충제": 6
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
            new_row = [today, "", "", "", "", "", "", "", ""] 
            new_row[target_col-1] = input_text
            ws.append_row(new_row)
            return "success"

    except Exception as e:
        return f"에러 발생: {str(e)}"

# ==========================================
# 2. 식단 채점 함수 (수정됨: 간헐적 단식, 당일 제외, 말투 교정)
# ==========================================
def batch_score(db):
    try:
        ws = db.doc.worksheet("식단")
        rows = ws.get_all_values()
        
        # 모델 설정 (창의성을 낮추고 사실 기반 분석 강화)
        generation_config = {"temperature": 0.1}
        model = genai.GenerativeModel("gemini-2.5-flash", generation_config=generation_config)
        
        updated_count = 0
        target_found = False
        
        # 오늘 날짜 확인 (오늘 자 데이터는 채점하지 않음)
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")

        st.write("🕵️ 식단 데이터 분석 시작...")
        
        for i, row in enumerate(rows):
            if i == 0: continue # 헤더 스킵

            current_row_num = i + 1

            # 데이터 길이 보정
            while len(row) < 9:
                row.append("")

            date_val = row[0]
            score_val = row[7]
            diet_txt = "".join(row[1:6]).strip()

            # [수정 1] 오늘 날짜면 채점 스킵 (하루가 안 끝남)
            if date_val == today_str:
                continue

            # 1. 이미 점수가 있으면 패스
            if score_val.strip(): 
                continue

            # 2. 내용이 없으면 패스
            if not diet_txt:
                continue

            target_found = True
            st.info(f"📍 [Row {current_row_num}] {date_val} 식단 분석 중...")

            # --- 프롬프트 대폭 수정 ---
            prompt = f"""
            당신은 사용자의 전담 영양사입니다. 
            아래 제공된 식단 데이터를 기반으로 영양 성분을 분석하여 JSON으로 반환하십시오.

            [사용자 프로필]
            - 키/체중: 183cm / 82kg
            - 골격근 : 40kg
            - 목표: 빠른 체지방 커팅 (근손실 최소화)
            - **특이사항: 간헐적 단식 진행 중 (아침 식사 건너뛰는 것은 계획된 행동임. 절대 감점 사유 아님)**

            [분석할 식단 데이터]
            - 날짜: {row[0]}
            - 아침: {row[1]} (공란일 경우 단식 중임)
            - 점심: {row[2]}
            - 간식: {row[3]}
            - 저녁: {row[4]}
            - 보충제: {row[5]}

            [지시사항]
            1. **계산**: 오직 '입력된 텍스트'에 기반하여 칼로리와 탄단지를 보수적으로 추산하십시오. (추측하여 부풀리지 말 것)
               - 잡곡밥 1공기는 약 300kcal (탄수화물 약 65g) 수준입니다. 200g 탄수화물 같은 터무니없는 수치 금지.
               - 사용자의 기초대사량과 운동량을 감안하여 채점하십시오.
            2. **평가**: 아침을 안 먹은 것에 대해 지적하지 마십시오. 단백질 섭취량이 체중 대비(약 160g 이상) 충분한지 집중 확인하십시오.
            3. **말투**: "어디로 증발하셨습니까?" 같은 비꼬는 말투 절대 금지. **매우 정중하고 분석적인 비서의 어조(존댓말)**를 사용하십시오.

            [필수 응답 포맷 - JSON Only]
            반드시 아래 JSON 형식으로만 출력하십시오.
            {{
                "total": "약 1800kcal (탄:150g, 단:160g, 지:50g)",
                "score": "85",
                "comment": "점심의 탄수화물 비중이 적절하며, 저녁 단백질 보충도 훌륭합니다."
            }}
            """

            try:
                response = model.generate_content(prompt)
                raw_text = response.text.strip()
                
                clean_text = raw_text.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean_text)

                total_val = data.get("total", "계산 불가")
                score_val = data.get("score", "0")
                comment_val = data.get("comment", "분석 실패")

                ws.update_cell(current_row_num, 7, total_val)
                ws.update_cell(current_row_num, 8, score_val)
                ws.update_cell(current_row_num, 9, comment_val)
                
                updated_count += 1
                st.success(f"✅ [{date_val}] 분석 완료: {score_val}점")
                
                time.sleep(1.5)

            except Exception as e:
                st.error(f"❌ 분석 실패 ({date_val}): {e}")
                continue

        if not target_found:
            return "⏳ 채점할 과거 데이터가 없습니다. (오늘 데이터는 내일 채점합니다)"
        
        if updated_count > 0:
            return f"🎉 총 {updated_count}건 리포트 작성 완료"
        else:
            return "⚠️ 대상 확인되었으나 업데이트 실패."

    except Exception as e:
        return f"🔥 시스템 오류: {str(e)}"


