# ... (위쪽 log_diet 함수는 그대로 유지) ...

# ==========================================
# 2. 식단 채점 함수 (디버깅 강화 버전)
# ==========================================
def batch_score(db):
    try:
        ws = db.doc.worksheet("식단")
        rows = ws.get_all_values()
        
        # 모델 설정
        generation_config = {"temperature": 0.2}
        model = genai.GenerativeModel("gemini-2.5-flash", generation_config=generation_config)
        
        updated_count = 0
        target_found = False # 채점 대상이 있는지 확인용
        
        # Streamlit 화면에 로그 출력 시작
        st.write("🕵️ 식단 데이터 분석 시작...")
        
        for i, row in enumerate(rows):
            if i == 0: continue # 헤더 스킵

            current_row_num = i + 1

            # 데이터 길이 보정
            while len(row) < 9:
                row.append("")

            # [디버깅] 현재 행의 상태 확인
            date_val = row[0]
            score_val = row[7]
            diet_txt = "".join(row[1:6]).strip()

            # 1. 이미 점수가 있으면 패스
            if score_val.strip(): 
                continue

            # 2. 내용이 없으면 패스
            if not diet_txt:
                continue

            # 여기까지 왔다면 채점 대상임
            target_found = True
            st.info(f"📍 [Row {current_row_num}] {date_val} 식단 채점 시도 중...")

            # --- 채점 로직 ---
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
                "total": "약 2100kcal (탄:200g, 단:180g, 지:60g)",
                "score": "80",
                "comment": "존댓말 피드백 한 줄."
            }}
            """

            try:
                response = model.generate_content(prompt)
                raw_text = response.text.strip()
                
                # 결과 확인용 로그 (잠시 주석 처리 가능)
                # st.code(raw_text, language='json') 

                clean_text = raw_text.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean_text)

                total_val = data.get("total", "계산 불가")
                score_val = data.get("score", "0")
                comment_val = data.get("comment", "분석 실패")

                ws.update_cell(current_row_num, 7, total_val)
                ws.update_cell(current_row_num, 8, score_val)
                ws.update_cell(current_row_num, 9, comment_val)
                
                updated_count += 1
                st.success(f"✅ [Row {current_row_num}] 채점 완료: {score_val}점")
                
                time.sleep(1.5)

            except Exception as e:
                # [핵심] 여기서 에러 내용을 화면에 뿌려줍니다.
                st.error(f"❌ [Row {current_row_num}] 실패 사유: {e}")
                st.write(f"응답 원본: {raw_text if 'raw_text' in locals() else '응답 없음'}")
                continue

        if not target_found:
            return "🤷‍♂️ 채점 대상 행(점수가 비어있는 날)을 찾지 못했습니다."
        
        if updated_count > 0:
            return f"🎉 총 {updated_count}건 채점 완료!"
        else:
            return "⚠️ 대상은 찾았으나 업데이트에 실패했습니다. 위 에러 로그를 확인하세요."

    except Exception as e:
        return f"🔥 시스템 치명적 오류: {str(e)}"
