import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import io
import requests
import base64
from PIL import Image, ImageDraw, ImageFont 
from streamlit_image_coordinates import streamlit_image_coordinates
import math
import streamlit.components.v1 as components 

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

# 💡 [핵심 업데이트] photo_url_2 컬럼 초기화 처리
if df.empty:
    df = pd.DataFrame(columns=['id', 'floor', 'x', 'y', 'title', 'detail', 'status', 'photo_url', 'photo_url_2'])
else:
    if 'photo_url' not in df.columns: df['photo_url'] = None
    # 시트에 photo_url_2가 없으면 빈 컬럼 생성
    if 'photo_url_2' not in df.columns: df['photo_url_2'] = None
    if 'floor' not in df.columns: df['floor'] = '지하 1층'

category_list = ["1. 설비", "2. 소방", "3. 자동제어", "4. 기타"]

# --- 팝업창 (상세 정보, 수정 및 출력) ---
@st.dialog("📋 하자 상세 정보 및 수정")
def show_defect_details(row_idx, row_data, map_image):
    try:
        current_idx = category_list.index(row_data['title'])
    except:
        current_idx = 3 
        
    edit_title = st.selectbox("하자명", category_list, index=current_idx)
    edit_detail = st.text_area("하자내용", value=row_data['detail'])
    
    # 💡 [업데이트] 상세 화면에서 사진 2장 표시
    col_img1, col_img2 = st.columns(2)
    p1_url = row_data.get('photo_url')
    p2_url = row_data.get('photo_url_2')

    with col_img1:
        if pd.notna(p1_url) and p1_url and not str(p1_url).startswith("ERROR"):
            st.image(p1_url, caption="사진 1", use_container_width=True)
    with col_img2:
        if pd.notna(p2_url) and p2_url and not str(p2_url).startswith("ERROR"):
            st.image(p2_url, caption="사진 2", use_container_width=True)
    
    st.write("---")
    
    col1, col2, col3 = st.columns(3)
    
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
            
    with col3:
        # 출력용 이미지 생성 (구름 마크 포함)
        print_img = map_image.copy()
        draw_print = ImageDraw.Draw(print_img)
        
        try:
            tx = float(row_data['x'])
            ty = float(row_data['y'])
            cloud_radius = 35  
            bump_radius = 15   
            for angle in range(0, 360, 45):
                rad = math.radians(angle)
                cx = tx + cloud_radius * math.cos(rad)
                cy = ty + cloud_radius * math.sin(rad)
                draw_print.ellipse((cx - bump_radius, cy - bump_radius, cx + bump_radius, cy + bump_radius), outline="red", width=4)
            draw_print.ellipse((tx - 20, ty - 20, tx + 20, ty + 20), outline="red", width=2)
        except: pass
            
        buffered = io.BytesIO()
        print_img.save(buffered, format="JPEG")
        map_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        # 💡 [업데이트] 보고서용 사진 HTML 생성 (사진 2장 나란히 배치)
        photo1_html = ""
        if pd.notna(p1_url) and p1_url and not str(p1_url).startswith("ERROR"):
            photo1_html = f'<img src="{p1_url}" />'
        else:
            photo1_html = '<div class="no-img">사진 1 없음</div>'

        photo2_html = ""
        if pd.notna(p2_url) and p2_url and not str(p2_url).startswith("ERROR"):
            photo2_html = f'<img src="{p2_url}" />'
        else:
            photo2_html = '<div class="no-img">사진 2 없음</div>'
            
        # 💡 [업데이트] A4 출력 레이아웃 개조 (사진 2장 좌우 배치, 그 아래 내용)
        report_html = f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
        <meta charset="utf-8">
        <title>하자 보고서 (No.{int(row_data['id'])})</title>
        <style>
            @page {{ size: A4 portrait; margin: 10mm; }}
            body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; margin: 0; padding: 0; background: #eee;}}
            .page {{ width: 190mm; height: 277mm; margin: 0 auto; display: flex; flex-direction: column; background: white; padding: 5mm; box-sizing: border-box;}}
            
            /* 상단 도면 영역 (50%) */
            .top-map {{ height: 48%; border-bottom: 2px solid #333; padding-bottom: 3mm; margin-bottom: 5mm; text-align: center; overflow: hidden; }}
            .top-map img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}
            
            /* 하단 정보 영역 (50%) */
            .bottom-info {{ height: 50%; display: flex; flex-direction: column; gap: 5mm; }}
            
            /* 하단 - 사진 2장 영역 (좌우 배치) */
            .photo-section {{ height: 60%; display: flex; gap: 5mm; }}
            .photo-box {{ width: 50%; height: 100%; text-align: center; border: 1px solid #ddd; padding: 2mm; box-sizing: border-box; display: flex; align-items: center; justify-content: center; overflow: hidden;}}
            .photo-box img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}
            .no-img {{ color: #999; font-size: 14pt; }}

            /* 하단 - 내용 영역 */
            .text-section {{ height: 38%; display: flex; flex-direction: column; gap: 3mm;}}
            .info-header {{ display: flex; gap: 5mm; align-items: center; }}
            .info-floor {{ font-size: 16pt; font-weight: bold; color: #555; }}
            .info-title {{ flex-grow: 1; font-size: 18pt; font-weight: bold; background-color: #f4f4f4; padding: 8px 15px; border-radius: 4px; border-left: 5px solid #2196F3; }}
            .info-detail-box {{ border: 1px solid #ccc; border-radius: 4px; padding: 10px; height: 100%; overflow: hidden; }}
            .info-detail-label {{ font-size: 14pt; font-weight: bold; color: #333; margin-bottom: 5px; display: block;}}
            .info-detail-content {{ font-size: 15pt; line-height: 1.5; white-space: pre-wrap; color: #444; }}
        </style>
        </head>
        <body>
            <div class="page">
                <div class="top-map">
                    <img src="data:image/jpeg;base64,{map_b64}" alt="하자 위치 도면">
                </div>
                <div class="bottom-info">
                    <div class="photo-section">
                        <div class="photo-box">{photo1_html}</div>
                        <div class="photo-box">{photo2_html}</div>
                    </div>
                    <div class="text-section">
                        <div class="info-header">
                            <div class="info-floor">[{row_data['floor']}]</div>
                            <div class="info-title">공종: {row_data['title']} (No.{int(row_data['id'])})</div>
                        </div>
                        <div class="info-detail-box">
                            <span class="info-detail-label">■ 하자내용</span>
                            <div class="info-detail-content">{row_data['detail']}</div>
                        </div>
                    </div>
                </div>
            </div>
            <script>
                window.onload = function() {{
                    setTimeout(function(){{ window.print(); }}, 500);
                }};
            </script>
        </body>
        </html>
        """
        
        b64_html = base64.b64encode(report_html.encode('utf-8')).decode('utf-8')
        js_button = f"""
        <button onclick="printReport()" style="width:100%; height: 38px; background-color:#2196F3; color:white; border:none; border-radius:5px; font-size:14px; font-weight:bold; cursor:pointer;">🖨️ A4 출력</button>
        <script>
        function printReport() {{
            var b64 = "{b64_html}";
            var html = decodeURIComponent(escape(window.atob(b64)));
            var blob = new Blob([html], {{type: 'text/html;charset=utf-8'}});
            var url = URL.createObjectURL(blob);
            window.open(url, '_blank');
        }}
        </script>
        """
        components.html(js_button, height=45)

# --- 팝업창 (신규 등록) ---
@st.dialog("📝 신규 하자 등록")
def register_defect(x, y, current_floor):
    st.info(f"{current_floor} 도면의 터치하신 위치에 등록합니다.")
    
    new_title = st.selectbox("하자명", category_list)
    new_detail = st.text_area("하자내용")

    st.write("---")
    st.subheader("🖼️ 사진 등록 (최대 2장)")
    
    # 💡 [업데이트] 사진 1 입력 영역
    st.markdown("**[사진 1]**")
    upload_type1 = st.radio("사진 1 첨부 방식", ["🖼️ 선택", "📸 촬영"], horizontal=True, key="ut1")
    img_buffer1 = None
    if upload_type1 == "🖼️ 선택":
        img_buffer1 = st.file_uploader("사진 1 선택", type=['jpg', 'jpeg', 'png'], key="fu1")
    else:
        img_buffer1 = st.camera_input("📸 사진 1 촬영", key="ci1")

    st.write("---")

    # 💡 [업데이트] 사진 2 입력 영역
    st.markdown("**[사진 2]**")
    upload_type2 = st.radio("사진 2 첨부 방식", ["🖼️ 선택", "📸 촬영"], horizontal=True, key="ut2")
    img_buffer2 = None
    if upload_type2 == "🖼️ 선택":
        img_buffer2 = st.file_uploader("사진 2 선택", type=['jpg', 'jpeg', 'png'], key="fu2")
    else:
        img_buffer2 = st.camera_input("📸 사진 2 촬영", key="ci2")
    
    if st.button("등록하기", type="primary", use_container_width=True):
        with st.spinner('안전한 이미지 서버로 데이터 전송 중...'):
            # 💡 [업데이트] 두 사진 모두 업로드 처리
            photo_link1 = ""
            if img_buffer1 is not None:
                photo_link1 = upload_image_to_imgbb(img_buffer1.getvalue())
                if photo_link1.startswith("ERROR"):
                    st.error(f"🚨 사진 1 업로드 실패 원인: {photo_link1}")
                    st.stop()

            photo_link2 = ""
            if img_buffer2 is not None:
                photo_link2 = upload_image_to_imgbb(img_buffer2.getvalue())
                if photo_link2.startswith("ERROR"):
                    st.error(f"🚨 사진 2 업로드 실패 원인: {photo_link2}")
                    st.stop()
            
            # 💡 [업데이트] 데이터프레임에 두 링크 모두 저장
            new_data = pd.DataFrame([{
                'id': len(df) + 1, 'floor': current_floor, 'x': x, 'y': y, 
                'title': new_title, 'detail': new_detail, 'status': '처리중',
                'photo_url': photo_link1, 'photo_url_2': photo_link2
            }])
            
            updated_df = pd.concat([df, new_data], ignore_index=True)
            conn.update(spreadsheet=SHEET_URL, worksheet="Sheet1", data=updated_df)
            
        st.success("등록 완료!")
        st.session_state['last_click'] = None
        st.rerun()

# --- 메인 화면 ---
st.title("🚧 다운 2지구 B2BL 지하주차장 하자 관리")
selected_floor = st.radio("📍 도면 층수 선택", ["지하 1층", "지하 2층", "지하 3층"], horizontal=True)
st.markdown("💡 **도면의 빈 곳을 터치**하면 하자가 등록되고, **마커를 터치**하면 조치 및 출력이 가능합니다.", unsafe_allow_html=True)
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
marker_radius = 8 

try:
    bold_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
except:
    try:
        bold_font = ImageFont.truetype("malgunbd.ttf", 18)
    except:
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
            elif row['title'] == '3. 자동제어': color = "#FFC000" 
            elif row['title'] == '4. 기타': color = "purple"
            else: color = "red" 
            
        draw.ellipse(
            (x - marker_radius, y - marker_radius, x + marker_radius, y + marker_radius), 
            fill=color, outline="white", width=1
        )
        
        text_num = str(int(row['id']))
        text_x = x + 12
        text_y = y - 15
        
        draw.text((text_x-1, text_y), text_num, fill="white", font=bold_font)
        draw.text((text_x+1, text_y), text_num, fill="white", font=bold_font)
        draw.text((text_x, text_y-1), text_num, fill="white", font=bold_font)
        draw.text((text_x, text_y+1), text_num, fill="white", font=bold_font)
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
            show_defect_details(clicked_marker_idx, clicked_marker_data, base_img)
        else:
            register_defect(clicked_x, clicked_y, selected_floor)