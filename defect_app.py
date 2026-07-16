import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import io
import requests
import base64
from PIL import Image, ImageDraw
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
    # 1. 스트림릿 서버에 열쇠가 잘 입력되었는지 검사합니다.
    try:
        api_key = st.secrets["IMGBB_API_KEY"]
    except:
        return "ERROR: 스트림릿 Settings(Secrets)에 IMGBB_API_KEY 열쇠가 없습니다."
        
    try:
        # 2. 이미지 용량 가볍게 압축
        img = Image.open(io.BytesIO(file_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail((1024, 1024))
        
        output_buffer = io.BytesIO()
        img.save(output_buffer, format="JPEG", quality=80)
        upload_bytes = output_buffer.getvalue()
        
        # 3. ImgBB 서버로 전송
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
    df = pd.DataFrame(columns=['id', 'x', 'y', 'title', 'detail', 'status', 'photo_url'])
elif 'photo_url' not in df.columns:
    df['photo_url'] = None

# --- 팝업창 (상세 정보) ---
@st.dialog("📋 하자 상세 정보")
def show_defect_details(row_idx, row_data):
    st.write(f"**하자명:** {row_data['title']}")
    st.write(f"**상세 내용:** {row_data['detail']}")
    
    if pd.notna(row_data.get('photo_url')) and row_data['photo_url'] != "" and not row_data['photo_url'].startswith("ERROR"):
        st.image(row_data['photo_url'], use_container_width=True)
    
    if row_data['status'] == '처리중':
        st.warning("현재 처리 대기 중인 하자입니다.")
        if st.button("✅ 처리 완료 (초록색으로 변경)", type="primary", use_container_width=True):
            df.at[row_idx, 'status'] = '완료'
            conn.update(spreadsheet=SHEET_URL, worksheet="Sheet1", data=df)
            st.session_state['last_click'] = None
            st.rerun()

# --- 팝업창 (신규 등록) ---
@st.dialog("📝 신규 하자 등록")
def register_defect(x, y):
    st.info("터치하신 위치에 새로운 하자를 등록합니다.")
    new_title = st.text_input("하자명 (예: 누수, 크랙)")
    new_detail = st.text_area("상세 내용")
    img_buffer = st.camera_input("📸 현장 사진 촬영")
    
    if st.button("등록하기", type="primary", use_container_width=True):
        if new_title:
            with st.spinner('안전한 이미지 서버로 사진을 전송 중입니다...'):
                photo_link = ""
                if img_buffer is not None:
                    photo_link = upload_image_to_imgbb(img_buffer.getvalue())
                    
                    # 💡 [핵심 수정] 업로드 실패 시 글자 저장도 멈추고 원인을 화면에 계속 띄워둡니다!
                    if photo_link.startswith("ERROR"):
                        st.error(f"🚨 사진 업로드 실패 원인:\n{photo_link}")
                        st.stop()
                
                new_data = pd.DataFrame([{
                    'id': len(df) + 1, 'x': x, 'y': y, 
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
st.markdown("💡 **스마트폰 두 손가락으로 도면을 자유롭게 확대/축소** 하세요.<br>💡 **도면의 빈 곳을 터치**하면 하자가 등록되고, **동그라미를 터치**하면 상세 내용을 볼 수 있습니다.", unsafe_allow_html=True)

hide_completed = st.toggle("✅ 완료된 하자(초록색) 숨기기", value=False)

try:
    base_img = Image.open("basement_map.jpg")
except:
    base_img = Image.new('RGB', (800, 600), color=(200, 200, 200))

draw = ImageDraw.Draw(base_img)
marker_radius = 25 

for idx, row in df.iterrows():
    if hide_completed and row['status'] == '완료':
        continue
        
    try:
        x, y = float(row['x']), float(row['y'])
        color = "red" if row['status'] == '처리중' else "green"
        draw.ellipse(
            (x - marker_radius, y - marker_radius, x + marker_radius, y + marker_radius), 
            fill=color, outline="white", width=4
        )
    except:
        pass

value = streamlit_image_coordinates(base_img, key="map")

if value is not None:
    if 'last_click' not in st.session_state or st.session_state['last_click'] != value:
        st.session_state['last_click'] = value
        
        clicked_x, clicked_y = value['x'], value['y']
        clicked_marker_idx = None
        clicked_marker_data = None
        
        for idx, row in df.iterrows():
            if hide_completed and row['status'] == '완료':
                continue
            try:
                mx, my = float(row['x']), float(row['y'])
                dist = math.sqrt((mx - clicked_x)**2 + (my - clicked_y)**2)
                if dist <= marker_radius * 1.5: 
                    clicked_marker_idx = idx
                    clicked_marker_data = row
                    break
            except:
                pass
        
        if clicked_marker_data is not None:
            show_defect_details(clicked_marker_idx, clicked_marker_data)
        else:
            register_defect(clicked_x, clicked_y)