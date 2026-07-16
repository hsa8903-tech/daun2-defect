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
st.title("🚧 울산 다운 2지구 B2BL 지하주차장 하자 통합 관리 시스템")

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

# 좌측 사이드바: 하자 등록
with st.sidebar:
    st.header("📝 신규 하자 등록")
    new_title = st.text_input("하자명 (예: 누수, 크랙)")
    new_detail = st.text_area("상세 내용")
    new_x = st.slider("X 좌표 (가로 위치)", 0, 100, 50)
    new_y = st.slider("Y 좌표 (세로 위치)", 0, 100, 50)
    
    img_buffer = st.camera_input("📸 현장 사진 촬영")
    
    if st.button("하자 등록하기"):
        if new_title:
            with st.spinner('구글 드라이브에 사진을 올리고 저장 중입니다...'):
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

# 메인 화면
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("🗺️ 지하주차장 전체 도면")
    hide_completed = st.toggle("✅ 완료된 하자 숨기기", value=False)
    
    df_plot = df.copy()
    if hide_completed:
        df_plot = df_plot[df_plot['status'] != '완료']

    fig = go.Figure()

    # 처리중 마커
    df_pending = df_plot[df_plot['status'] == '처리중']
    fig.add_trace(go.Scatter(
        x=df_pending['x'], y=df_pending['y'],
        mode='markers+text',
        marker=dict(size=15, color='red', symbol='x'),
        text=df_pending['title'],
        textposition="top center",
        hovertext=df_pending['detail'],
        name='처리중'
    ))

    # 완료 마커
    if not hide_completed:
        df_completed = df_plot[df_plot['status'] == '완료']
        fig.add_trace(go.Scatter(
            x=df_completed['x'], y=df_completed['y'],
            mode='markers+text',
            marker=dict(size=15, color='green', symbol='circle'),
            text=df_completed['title'],
            textposition="top center",
            hovertext=df_completed['detail'],
            name='완료'
        ))

    # ==========================================
    # 도면 이미지 파일을 웹용(Base64)으로 변환해서 넣기
    # ==========================================
    try:
        # basement_map.png 파일을 읽어서 인터넷 화면에 맞게 암호화합니다.
        with open("basement_map.png", "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        bg_image = "data:image/png;base64," + encoded_string
    except:
        bg_image = "https://via.placeholder.com/800x600.png?text=Image+Not+Found"

    fig.update_layout(
        images=[dict(
            source=bg_image,
            xref="x", yref="y",
            x=0, y=100, sizex=100, sizey=100,
            sizing="stretch", opacity=0.8, layer="below"
        )],
        xaxis=dict(range=[0, 100], visible=False),
        yaxis=dict(range=[0, 100], visible=False),
        margin=dict(l=0, r=0, t=0, b=0),
        hovermode="closest"
    )
    
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("📋 하자 목록")
    for index, row in df.iterrows():
        with st.expander(f"[{row['status']}] {row['title']}"):
            st.write(f"**상세 내용:** {row['detail']}")
            if pd.notna(row.get('photo_url')) and row['photo_url'] != "":
                st.markdown(f"[📷 첨부된 현장 사진 보기]({row['photo_url']})")
            
            if row['status'] == '처리중':
                if st.button("🛠️ 처리 완료", key=f"btn_{row['id']}"):
                    df.at[index, 'status'] = '완료'
                    conn.update(worksheet="Sheet1", data=df)
                    st.rerun()