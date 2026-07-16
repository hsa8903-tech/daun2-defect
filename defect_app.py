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

# 💡 [업그레이드] 층수(floor) 컬럼 자동 추가 기능
if df.empty:
    df = pd.DataFrame(columns=['id', 'floor', 'x', 'y', 'title', 'detail', 'status', 'photo_url'])
else:
    if 'photo_url' not in df.columns:
        df['photo_url'] = None
    if 'floor' not in df.columns:
        df['floor'] = '지하 1층'  # 예전 데이터는 기본 지하 1층으로 처리

# --- 팝업창 (상세 정보 및 수정) ---
@st.dialog("📋 하자 상세 정보 및 수정")
def show_defect_details(row_idx, row_data):
    # 💡 [업그레이드] 텍스트 입력창에 기존 내용을 띄워두고 바로 수정할 수 있게 만듭니다.
    edit_title = st.text_input("하자명", value=row_data['title'])
    edit_detail = st.text_area("상세 내용", value=row_data['detail'])
    
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
    new_title = st.text_input("하자명 (예: 누수, 크랙)")
    new_detail = st.text_area("상세 내용")
    
    upload_type = st.radio("사진 첨부 방식", ["🖼️ 사진첩에서 선택", "📸 카메라로 바로 촬영"], horizontal=True)
    
    img_buffer = None
    if upload_type == "🖼️ 사진첩에서 선택":
        img_buffer = st.file_uploader("사진을 선택해주세요.", type=['jpg', 'jpeg', 'png'])
    else:
        img_buffer = st.camera_input("📸 현장 사진 촬영")
    
    if st.button("등록하기", type="primary", use_container_width=True):
        if new_title:
            with st.spinner('안전한 이미지 서버로 사진을 전송 중입니다...'):
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

# 💡 [업그레이드] 층수 선택 메뉴 추가
selected_floor = st.radio("📍 도면 층수 선택", ["지하 1층", "지하 2층", "지하 3층"], horizontal=True)

st.markdown("💡 **스마트폰 두 손가락으로 도면을 자유롭게 확대/축소** 하세요.<br>💡 **도면의 빈 곳을 터치**하면 하자가 등록되고, **동그라미를 터치**하면 수정 및 완료 처리가 가능합니다.", unsafe_allow_html=True)

hide_completed = st.toggle("✅ 완료된 하자(초록색) 숨기기", value=False)

# 선택한 층수에 맞게 도면 파일 연결
floor_img_map = {
    "지하 1층": "basement_map_b1.jpg",
    "지하 2층": "basement_map_b2.jpg",
    "지하 3층": "basement_map_b3.jpg"
}

try:
    base_img = Image.open(floor_img_map[selected_floor])
except:
    # 이미지가 없을 경우 빈 회색 도면을 띄워줍니다.
    base_img = Image.new('RGB', (800, 600), color=(200, 200, 200))

draw = ImageDraw.Draw(base_img)
# 💡 [업그레이드] 마커 크기를 25에서 절반인 12로 줄였습니다.
marker_radius = 12 

# 선택한 층수의 하자만 필터링해서 그리기
current_floor_df = df[df['floor'] == selected_floor]

for idx, row in current_floor_df.iterrows():
    if hide_completed and row['status'] == '완료':
        continue
        
    try:
        x, y = float(row['x']), float(row['y'])
        color = "red" if row['status'] == '처리중' else "green"
        draw.ellipse(
            (x - marker_radius, y - marker_radius, x + marker_radius, y + marker_radius), 
            fill=color, outline="white", width=2
        )
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
                if dist <= marker_radius * 2.0:  # 크기가 줄었으니 터치 범위는 조금 넉넉히 잡습니다
                    clicked_marker_idx = idx
                    clicked_marker_data = row
                    break
            except:
                pass
        
        if clicked_marker_data is not None:
            show_defect_details(clicked_marker_idx, clicked_marker_data)
        else:
            register_defect(clicked_x, clicked_y, selected_floor)