import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
import io
import base64
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# 페이지 기본 설정
st.set_page_config(page_title="다운 2지구 지하주차장 하자 관리", layout="wide")

# ==========================================
# 🚨 [수정할 부분] 과장님의 시트 주소와 폴더 ID를 다시 적어주세요! 🚨
# ==========================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1w3f9ACaJbdHB09tDFEKAT12DYB8Vun3vg_4zyJcQ7GM/edit"
FOLDER_ID = "https://drive.google.com/drive/folders/1tvGExHwTYmvuYNa9lzMJWSVDr9I3GbAf"
# ==========================================

@st.cache_resource
def get_drive_service():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["connections"]["gsheets"],
        scopes=['https://www.googleapis.com/auth/drive']
    )
    return build('drive', 'v3', credentials=creds)

def upload_image_to_drive(file_bytes, filename):
    drive_service = get_drive_service()
    file_metadata = {'name': filename, 'parents': [FOLDER_ID]}
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype='image/jpeg', resumable=True)
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
    return file.get('webViewLink')

# 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(spreadsheet=SHEET_URL, worksheet="Sheet1", ttl=0)

if df.empty:
    df = pd.DataFrame(columns=['id', 'x', 'y', 'title', 'detail', 'status', 'photo_url'])
elif 'photo_url' not in df.columns:
    df['photo_url'] = None

# ------------------------------------------
# 💡 [팝업창 기능] 상세 정보 보기 및 처리 완료
# ------------------------------------------
@st.dialog("📋 하자 상세 정보")
def show_defect_details(row_data, index_val):
    st.markdown(f"### {row_data['title']}")
    st.write(f"**상세 내용:** {row_data['detail']}")
    
    if pd.notna(row_data.get('photo_url')) and row_data['photo_url'] != "":
        st.image(row_data['photo_url'], use_container_width=True)
    
    if row_data['status'] == '처리중':
        st.warning("현재 처리 대기 중인 하자입니다.")
        if st.button("✅ 처리 완료", type="primary", use_container_width=True):
            df.at[index_val, 'status'] = '완료'
            conn.update(worksheet="Sheet1", data=df)
            st.success("완료 처리되었습니다! 화면이 새로고침됩니다.")
            st.rerun()
    else:
        st.success("조치가 완료된 하자입니다.")

st.title("🚧 울산 다운 2지구 B2BL 지하주차장 하자 관리")

# 메인 화면: 도면과 리스트
col1, col2 = st.columns([3, 1])

with col1:
    hide_completed = st.toggle("✅ 완료된 하자 숨기기", value=False)
    
    df_plot = df.copy()
    if hide_completed:
        df_plot = df_plot[df_plot['status'] != '완료']

    fig = go.Figure()

    # 처리중 마커 (빨간 동그라미)
    df_pending = df_plot[df_plot['status'] == '처리중']
    fig.add_trace(go.Scatter(
        x=df_pending['x'], y=df_pending['y'],
        mode='markers+text',
        marker=dict(size=18, color='red', symbol='circle', line=dict(color='white', width=2)),
        text=df_pending['title'],
        textposition="top center",
        hovertext=df_pending['detail'],
        name='처리중'
    ))

    # 완료 마커 (초록 동그라미)
    if not hide_completed:
        df_completed = df_plot[df_plot['status'] == '완료']
        fig.add_trace(go.Scatter(
            x=df_completed['x'], y=df_completed['y'],
            mode='markers+text',
            marker=dict(size=18, color='green', symbol='circle', line=dict(color='white', width=2)),
            text=df_completed['title'],
            textposition="top center",
            hovertext=df_completed['detail'],
            name='완료'
        ))

    # 도면 이미지 배경 처리
    try:
        with open("basement_map.jpg", "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        bg_image = "data:image/jpeg;base64," + encoded_string
    except:
        bg_image = "https://via.placeholder.com/800x600.png?text=Image+Not+Found"

    # 스마트폰 터치 및 확대/축소에 최적화된 설정
    fig.update_layout(
        dragmode="pan", # 기본 터치를 이동(Pan)으로 설정
        images=[dict(
            source=bg_image,
            xref="x", yref="y",
            x=0, y=100, sizex=100, sizey=100,
            sizing="stretch", opacity=0.8, layer="below"
        )],
        xaxis=dict(range=[0, 100], visible=False, fixedrange=False), 
        yaxis=dict(range=[0, 100], visible=False, fixedrange=False, scaleanchor="x", scaleratio=1), # 도면 비율 고정
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False
    )
    
    # 도면 그리기
    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': False})

with col2:
    st.subheader("📋 터치하여 상세 보기")
    # 도면 옆(또는 모바일에서는 아래)에 버튼 리스트 생성
    for index, row in df.iterrows():
        # 상태에 따라 버튼 아이콘 변경
        icon = "🔴" if row['status'] == "처리중" else "🟢"
        if st.button(f"{icon} {row['title']}", key=f"open_{row['id']}", use_container_width=True):
            show_defect_details(row, index)

# 좌측 사이드바: 신규 등록
with st.sidebar:
    st.header("📝 신규 하자 등록")
    st.info("X, Y 슬라이더를 움직여 도면상의 위치를 먼저 대략적으로 맞추고 내용을 입력하세요.")
    new_x = st.slider("X 좌표 (가로 위치 ↔)", 0, 100, 50)
    new_y = st.slider("Y 좌표 (세로 위치 ↕)", 0, 100, 50)
    
    new_title = st.text_input("하자명 (예: 누수, 크랙)")
    new_detail = st.text_area("상세 내용")
    img_buffer = st.camera_input("📸 현장 사진 촬영")
    
    if st.button("하자 등록하기", type="primary", use_container_width=True):
        if new_title:
            with st.spinner('사진 업로드 및 저장 중입니다...'):
                photo_link = ""
                if img_buffer is not None:
                    file_name = f"defect_{len(df)+1}.jpg"
                    photo_link = upload_image_to_drive(img_buffer.getvalue(), file_name)
                
                new_id = len(df) + 1
                new_data = pd.DataFrame([{
                    'id': new_id, 'x': new_x, 'y': new_y, 
                    'title': new_title, 'detail': new_detail, 'status': '처리중',
                    'photo_url': photo_link
                }])
                
                updated_df = pd.concat([df, new_data], ignore_index=True)
                conn.update(worksheet="Sheet1", data=updated_df)
                
            st.success("등록 완료되었습니다!")
            st.rerun()