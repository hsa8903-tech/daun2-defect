import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import io
import requests
import base64
from PIL import Image, ImageDraw, ImageFont  # 💡 글꼴(Font) 조절 도구 추가
from streamlit_image_coordinates import streamlit_image_coordinates
import math

# 페이지 기본 설정
st.set_page_config(page_title="다운 2지구 지하주차장 하자 관리", layout="wide")

# ==========================================
# 🚨 [수정할 부분] 시트 주소만 다시 적어주세요! 
# ==========================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1w3f9ACaJbdHB09tDFEKAT12DYB8Vun3vg_4zyJcQ7GM/edit"
# ==========================================

def upload_image_to_imgbb(file_bytes):
    try:
        api_key = st.secrets["IMGBB_API_KEY"]
    except:
        return "ERROR: 스트림릿 Settings(Secrets)에 IMGBB_API_KEY 열쇠가 없습니다."
        
    try:
        img = Image.open(io.BytesIO(file_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((1024, 1024))
        
        output_buffer = io.BytesIO()
        img.save(output_buffer, format="JPEG", quality=80)
        upload_bytes = output_buffer.getvalue()
        
        url = "https://api.imgbb.com/1/upload"
        payload = {
            "key": api_key,
            "image": base64.b64encode(upload_bytes).decode('utf-8')
        }
        response = requests.post(url, data=payload)
        
        if response.status_code == 200:
            return response.json()['data']['url']
        else:
            return f"ERROR: 서버 거절 사유 ({response.text})"
    except Exception as e:
        return f"ERROR: 코드 실행 오류 ({str(e)})"

# 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(spreadsheet=SHEET_URL, worksheet="Sheet1", ttl=0)

if df.empty:
    df = pd.DataFrame(columns=['id', 'floor', 'x', 'y', 'title', 'detail', 'status', 'photo_url'])
else:
    if 'photo_url' not in df.columns:
        df['photo_url'] = None
    if 'floor' not in df.columns:
        df['floor'] = '지하 1층'

category_list = ["1. 설비", "2. 소방", "3. 자동제어", "4. 기타"]

# --- 팝업창 (상세 정보 및 수정) ---
@st.dialog("📋 하자 상세 정보 및 수정")
def show_defect_details(row_idx, row_data):
    try:
        current_idx = category_list.index(row_data['title'])
    except:
        current_idx = 3 
        
    edit_title = st.selectbox("하자명", category_list, index=current_idx)
    edit_detail = st.text_area("하자내용", value=row_data['detail'])
    
    if pd.notna(row_data.get('photo_url')) and row_data['photo_url'] != "" and not row_data['photo_url'].startswith("ERROR"):
        st.image(row_data['photo_url'], use_container_width=True)
    
    st.write("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 내용 수정", use_container_width=True):
            df.at[row_idx, 'title'] = edit_title
            df.at[row_idx, 'detail'] = edit_detail
            conn.update(spreadsheet=SHEET_URL, worksheet="Sheet1", data=df)
            st.session_state['last_click'] = None
            st.rerun()
            
    with col2:
        if row_data['status'] == '처리중':
            if st.button("✅ 처리 완료", type="primary", use_container_width=True):
                df.at[row_idx, 'status'] = '완료'
                conn.update(spreadsheet=SHEET_URL, worksheet="Sheet1", data=df)
                st.session_state['last_click'] = None
                st.rerun()
        else:
            st.success("조치 완료됨")

# --- 팝업창 (신규 등록) ---
@st.dialog("📝 신규 하자 등록")
def register_defect(x, y, current_floor):
    st.info(f"{current_floor} 도면의 터치하신 위치에 등록합니다.")
    
    new_title = st.selectbox("하자명", category_list)
    new_detail = st.text_area("하자내용")
    
    upload_type = st.radio("사진 첨부 방식", ["🖼️ 사진첩에서 선택", "📸 카메라로 바로 촬영"], horizontal=True)
    
    img_buffer = None
    if upload_type == "🖼️ 사진첩에서 선택":
        img_buffer = st.file_uploader("사진을 선택해주세요.", type=['jpg', 'jpeg', 'png'])
    else:
        img_buffer = st.camera_input("📸 현장 사진 촬영")
    
    if st.button("등록하기", type="primary", use_container_width=True):
        with st.spinner('안전한 이미지 서버로 데이터 전송 중...'):
            photo_link = ""
            if img_buffer is not None:
                photo_link = upload_image_to_imgbb(img_buffer.getvalue())
                if photo_link.startswith("ERROR"):
                    st.error(f"🚨 사진 업로드 실패 원인:\n{photo_link}")
                    st.stop()
            
            new_data = pd.DataFrame([{
                'id': len(df) + 1, 'floor': current_floor, 'x': x, 'y': y, 
                'title': new_title, 'detail': new_detail, 'status': '처리중',
                'photo_url': photo_link
            }])
            
            updated_df = pd.concat([df, new_data], ignore_index=True)
            conn.update(spreadsheet=SHEET_URL, worksheet="Sheet1", data=updated_df)
            
        st.success("등록 완료!")
        st.session_state['last_click'] = None
        st.rerun()

# --- 메인 화면 ---
st.title("🚧 다운 2지구 B2BL 지하주차장 하자 관리")
selected_floor = st.radio("📍 도면 층수 선택", ["지하 1층", "지하 2층", "지하 3층"], horizontal=True)
st.markdown("💡 **도면의 빈 곳을 터치**하면 하자가 등록되고, **마커를 터치**하면 수정 및 완료 처리가 가능합니다.", unsafe_allow_html=True)
hide_completed = st.toggle("✅ 완료된 하자(초록색) 숨기기", value=False)

floor_img_map = {
    "지하 1층": "basement_map_b1.jpg",
    "지하 2층": "basement_map_b2.jpg",
    "지하 3층": "basement_map_b3.jpg"
}

try:
    base_img = Image.open(floor_img_map[selected_floor])
except:
    base_img = Image.new('RGB', (800, 600), color=(200, 200, 200))

draw = ImageDraw.Draw(base_img)

# 💡 피드백 반영: 마커 크기 8px로 조절
marker_radius = 8 

# 💡 피드백 반영: 글자 크기를 키우고 굵게(Bold) 설정하는 코드
try:
    # 스트림릿 서버에 있는 기본 굵은 글꼴 (크기 15)
    bold_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 15)
except:
    try:
        # PC 환경을 위한 맑은 고딕 굵게
        bold_font = ImageFont.truetype("malgunbd.ttf", 15)
    except:
        # 폰트를 못 찾으면 기본 폰트 사용
        bold_font = ImageFont.load_default()

current_floor_df = df[df['floor'] == selected_floor]

for idx, row in current_floor_df.iterrows():
    if hide_completed and row['status'] == '완료':
        continue
        
    try:
        x, y = float(row['x']), float(row['y'])
        
        if row['status'] == '완료':
            color = "green"
        else:
            if row['title'] == '1. 설비': color = "blue"
            elif row['title'] == '2. 소방': color = "red"
            elif row['title'] == '3. 자동제어': color = "yellow"
            elif row['title'] == '4. 기타': color = "purple"
            else: color = "red" 
            
        draw.ellipse(
            (x - marker_radius, y - marker_radius, x + marker_radius, y + marker_radius), 
            fill=color, outline="white", width=1
        )
        
        # 💡 피드백 반영: 소수점(1.0)을 무조건 정수(1)로 변환
        text_num = str(int(row['id']))
        
        # 글씨가 커진 만큼 위치를 우측으로 조금 더 이동시킵니다.
        text_x = x + 10
        text_y = y - 12
        
        # 가독성을 위한 하얀색 테두리 효과
        draw.text((text_x-1, text_y), text_num, fill="white", font=bold_font)
        draw.text((text_x+1, text_y), text_num, fill="white", font=bold_font)
        draw.text((text_x, text_y-1), text_num, fill="white", font=bold_font)
        draw.text((text_x, text_y+1), text_num, fill="white", font=bold_font)
        
        # 실제 숫자 검은색 굵은 글씨로 출력
        draw.text((text_x, text_y), text_num, fill="black", font=bold_font)
        
    except:
        pass

value = streamlit_image_coordinates(base_img, key=f"map_{selected_floor}")

if value is not None:
    if 'last_click' not in st.session_state or st.session_state['last_click'] != value:
        st.session_state['last_click'] = value
        
        clicked_x, clicked_y = value['x'], value['y']
        clicked_marker_idx = None
        clicked_marker_data = None
        
        for idx, row in current_floor_df.iterrows():
            if hide_completed and row['status'] == '완료':
                continue
            try:
                mx, my = float(row['x']), float(row['y'])
                dist = math.sqrt((mx - clicked_x)**2 + (my - clicked_y)**2)
                if dist <= 20.0: 
                    clicked_marker_idx = idx
                    clicked_marker_data = row
                    break
            except:
                pass
        
        if clicked_marker_data is not None:
            show_defect_details(clicked_marker_idx, clicked_marker_data)
        else:
            register_defect(clicked_x, clicked_y, selected_floor)