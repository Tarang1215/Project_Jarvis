import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime

class DBHandler:
    def __init__(self):
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
            client = gspread.authorize(creds)
            self.doc = client.open("운동일지_DB") # 시트 이름 확인 필수
        except Exception as e:
            st.error(f"DB 연결 실패: {e}")

    def append_row(self, sheet_name, data):
        try:
            self.doc.worksheet(sheet_name).append_row(data)
            return "success"
        except: return "fail"

    def update_cell(self, sheet_name, row, col, val):
        self.doc.worksheet(sheet_name).update_cell(row, col, val)

    def get_all_values(self, sheet_name):
        return self.doc.worksheet(sheet_name).get_all_values()

    def find_cell(self, sheet_name, query):
        try: return self.doc.worksheet(sheet_name).find(query)
        except: return None
        
    def get_cell_value(self, sheet_name, row, col):
        return self.doc.worksheet(sheet_name).cell(row, col).value

    # 기억 저장용 (시트 없으면 생성)
    def save_memory(self, fact):
        try:
            try: ws = self.doc.worksheet("기억_DB")
            except: ws = self.doc.add_worksheet("기억_DB", 100, 2); ws.append_row(["날짜", "내용"])
            ws.append_row([datetime.datetime.now().strftime("%Y-%m-%d"), fact])
            return "success"
        except Exception as e: return f"Error: {e}"

    def load_memory(self):
        try: return "\n".join([f"- {r[1]}" for r in self.doc.worksheet("기억_DB").get_all_values()[1:][-15:]])
        except: return "기억 없음"