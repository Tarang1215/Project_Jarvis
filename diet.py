import datetime
import gspread

def log_diet(db, menu, amount, meal_type):
    """
    사용자 시트 구조에 맞춘 식단 기록 함수
    순서: 날짜(A) | 아침(B) | 점심(C) | 간식(D) | 저녁(E) | 운동후보충제(F) | Total Input(G) | Score(H) | Comments(I)
    """
    try:
        # 1. 시트 연결
        try:
            ws = db.doc.worksheet("식단")
        except:
            return "오류: '식단' 시트를 찾을 수 없습니다."

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # 2. 식사 유형별 컬럼 번호 매핑 (알려주신 순서 적용)
        col_map = {
            "아침": 2,          # B열
            "점심": 3,          # C열
            "간식": 4,          # D열
            "저녁": 5,          # E열
            "보충제": 6,        # F열 (운동후보충제)
            "운동후보충제": 6   # 혹시 몰라 둘 다 매핑
        }
        
        # AI가 '보충제'라고 하든 '운동후보충제'라고 하든 6번 칸으로 보냄
        # 매핑 안 된 단어가 오면 기본값 '간식(4)' 처리
        target_col = col_map.get(meal_type, 4) 
        
        input_text = f"{menu}({amount})"

        # 3. 오늘 날짜 행 찾기
        try:
            cell = ws.find(today)
        except:
            cell = None

        if cell:
            # [수정] 이미 오늘 기록이 있으면 -> 해당 칸에 덧붙이기
            row_idx = cell.row
            curr_val = ws.cell(row_idx, target_col).value
            
            if curr_val:
                new_val = f"{curr_val}, {input_text}"
            else:
                new_val = input_text
                
            ws.update_cell(row_idx, target_col, new_val)
            return "success"
        else:
            # [수정] 오늘 첫 기록이면 -> 새 줄 만들기 (총 9칸 확보)
            # A(날짜) ~ I(Comments) 까지 빈 칸 생성
            new_row = [today, "", "", "", "", "", "", "", ""] 
            
            # 목표 칸에 내용 넣기
            new_row[target_col-1] = input_text
            
            ws.append_row(new_row)
            return "success"

    except Exception as e:
        return f"에러 발생: {str(e)}"

def batch_score(db):
    """
    식단 채점 기능 (추후 구현)
    """
    return "현재 자동 채점 기능은 준비 중입니다."
