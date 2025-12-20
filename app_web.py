"""
Image to Video Creator - Streamlit Web Version
Upload images + audio to create video with effects.
Supports both local upload and Google Drive.
"""
import streamlit as st
import tempfile
import os
from pathlib import Path

try:
    from video_processor import (
        create_video_from_images, 
        get_image_files, 
        get_audio_duration,
        check_ffmpeg
    )
except ImportError as e:
    st.error(f"❌ Import Error: {e}")
    st.stop()

# Import Drive service (optional)
try:
    import drive_service
    DRIVE_AVAILABLE = drive_service.is_available()
except ImportError:
    DRIVE_AVAILABLE = False

# Page config
st.set_page_config(
    page_title="Image to Video Creator",
    page_icon="🎬",
    layout="centered"
)

# Custom CSS
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    }
    .main-title {
        text-align: center;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .info-box {
        background: rgba(255,255,255,0.1);
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .success-box {
        background: rgba(0,255,100,0.1);
        border: 1px solid #00ff64;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .drive-connected {
        background: rgba(66,133,244,0.2);
        border: 1px solid #4285f4;
        border-radius: 10px;
        padding: 0.5rem 1rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'video_ready' not in st.session_state:
    st.session_state.video_ready = False
if 'video_bytes' not in st.session_state:
    st.session_state.video_bytes = None
if 'video_name' not in st.session_state:
    st.session_state.video_name = None
if 'source_mode' not in st.session_state:
    st.session_state.source_mode = 'upload'  # 'upload' or 'drive'

# ============ SIDEBAR - Google Drive Connection ============
with st.sidebar:
    st.header("🔗 Google Drive")
    
    if DRIVE_AVAILABLE:
        if drive_service.is_connected():
            st.markdown(f"""
            <div class="drive-connected">
                ✅ Đã kết nối: <strong>{drive_service.get_user_email()}</strong>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("🔌 Ngắt kết nối", use_container_width=True):
                drive_service.disconnect()
                st.rerun()
        else:
            st.info("Kết nối Drive để lấy ảnh/audio và upload video")
            
            # Check for OAuth callback
            query_params = st.query_params
            if 'code' in query_params:
                auth_code = query_params['code']
                if drive_service.handle_oauth_callback(auth_code):
                    st.query_params.clear()
                    st.success("✅ Kết nối thành công!")
                    st.rerun()
            else:
                auth_url = drive_service.get_auth_url()
                if auth_url:
                    st.link_button("🔐 Đăng nhập Google", auth_url, use_container_width=True)
                else:
                    st.warning("⚠️ Chưa cấu hình OAuth2. Xem hướng dẫn setup.")
    else:
        st.warning("📦 Thư viện Google chưa được cài đặt")
    
    st.markdown("---")
    st.caption("Made with ❤️ using Streamlit")

# ============ MAIN CONTENT ============
st.markdown('<h1 class="main-title">🎬 Image to Video Creator</h1>', unsafe_allow_html=True)
st.markdown("---")

# Check FFmpeg
if not check_ffmpeg():
    st.error("⚠️ FFmpeg chưa được cài đặt!")
    st.stop()

# ============ SOURCE SELECTION ============
if DRIVE_AVAILABLE and drive_service.is_connected():
    source_mode = st.radio(
        "📂 Nguồn file",
        options=['upload', 'drive'],
        format_func=lambda x: '💻 Upload từ máy' if x == 'upload' else '☁️ Lấy từ Google Drive',
        horizontal=True
    )
else:
    source_mode = 'upload'

# Variables to hold files
uploaded_images = []
uploaded_audio = None
drive_images_data = []
drive_audio_data = None

# ============ FILE INPUT SECTION ============
if source_mode == 'upload':
    # Standard upload UI
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📁 Upload ảnh")
        uploaded_images = st.file_uploader(
            "Chọn các ảnh (sắp xếp theo tên)",
            type=['jpg', 'jpeg', 'png', 'bmp', 'webp'],
            accept_multiple_files=True,
            key="images"
        )
        if uploaded_images:
            st.success(f"✅ Đã chọn {len(uploaded_images)} ảnh")
    
    with col2:
        st.subheader("🎵 Upload audio")
        uploaded_audio = st.file_uploader(
            "Chọn file audio",
            type=['mp3', 'wav', 'm4a', 'aac', 'ogg', 'flac'],
            key="audio"
        )
        if uploaded_audio:
            st.success(f"✅ {uploaded_audio.name}")

elif source_mode == 'drive' and DRIVE_AVAILABLE and drive_service.is_connected():
    # Google Drive file picker
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📁 Chọn folder ảnh từ Drive")
        folders = drive_service.list_folders()
        folder_options = {f['name']: f['id'] for f in folders}
        
        if folder_options:
            selected_img_folder = st.selectbox(
                "Chọn folder chứa ảnh",
                options=list(folder_options.keys()),
                key="img_folder"
            )
            
            if selected_img_folder:
                folder_id = folder_options[selected_img_folder]
                images_in_folder = drive_service.list_files_in_folder(folder_id, 'images')
                
                if images_in_folder:
                    st.success(f"✅ Tìm thấy {len(images_in_folder)} ảnh")
                    drive_images_data = images_in_folder
                else:
                    st.warning("Không tìm thấy ảnh trong folder này")
        else:
            st.warning("Không tìm thấy folder nào trên Drive")
    
    with col2:
        st.subheader("🎵 Chọn file audio từ Drive")
        
        if folder_options:
            selected_audio_folder = st.selectbox(
                "Chọn folder chứa audio",
                options=list(folder_options.keys()),
                key="audio_folder"
            )
            
            if selected_audio_folder:
                folder_id = folder_options[selected_audio_folder]
                audio_files = drive_service.list_files_in_folder(folder_id, 'audio')
                
                if audio_files:
                    audio_options = {f['name']: f for f in audio_files}
                    selected_audio = st.selectbox(
                        "Chọn file audio",
                        options=list(audio_options.keys()),
                        key="audio_file"
                    )
                    if selected_audio:
                        drive_audio_data = audio_options[selected_audio]
                        st.success(f"✅ {selected_audio}")
                else:
                    st.warning("Không tìm thấy audio trong folder này")

st.markdown("---")

# ============ OPTIONS ============
st.subheader("⚙️ Tùy chọn hiệu ứng")
col1, col2, col3 = st.columns(3)

with col1:
    enable_zoom = st.checkbox("🔍 Zoom Effect", help="Zoom từ 100% → 110%")
with col2:
    enable_blur = st.checkbox("🌫️ Blur Background", help="Nền mờ thay vì đen")
with col3:
    enable_dissolve = st.checkbox("✨ Dissolve Transition", help="Chuyển cảnh mờ 1s")

# Upload to Drive option
upload_to_drive = False
if DRIVE_AVAILABLE and drive_service.is_connected():
    upload_to_drive = st.checkbox("☁️ Upload video lên Drive sau khi xong", value=False)

st.markdown("---")

# Info
st.markdown("""
<div class="info-box">
📽️ <strong>Output:</strong> 1920x1080, 30fps, 10Mbps video, 320kbps audio
</div>
""", unsafe_allow_html=True)

# ============ GENERATE BUTTON ============
if st.button("🎬 Tạo Video", type="primary", use_container_width=True, disabled=st.session_state.processing):
    
    # Validation
    has_images = (source_mode == 'upload' and uploaded_images) or (source_mode == 'drive' and drive_images_data)
    has_audio = (source_mode == 'upload' and uploaded_audio) or (source_mode == 'drive' and drive_audio_data)
    
    if not has_images:
        st.error("❌ Vui lòng chọn ảnh!")
    elif not has_audio:
        st.error("❌ Vui lòng chọn file audio!")
    else:
        st.session_state.processing = True
        st.session_state.video_ready = False
        st.session_state.video_bytes = None
        st.session_state.video_name = None
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            images_dir = temp_path / "images"
            images_dir.mkdir()
            
            progress_bar = st.progress(0, text="Đang chuẩn bị file...")
            
            # Save images (from upload or Drive)
            if source_mode == 'upload':
                for i, img_file in enumerate(sorted(uploaded_images, key=lambda x: x.name)):
                    img_path = images_dir / img_file.name
                    with open(img_path, 'wb') as f:
                        f.write(img_file.getbuffer())
                    progress_bar.progress((i + 1) / len(uploaded_images), text=f"Đang lưu ảnh {i+1}/{len(uploaded_images)}")
                
                audio_path = temp_path / uploaded_audio.name
                with open(audio_path, 'wb') as f:
                    f.write(uploaded_audio.getbuffer())
                output_name = Path(uploaded_audio.name).stem + "_video.mp4"
            
            else:  # Drive
                for i, img_info in enumerate(sorted(drive_images_data, key=lambda x: x['name'])):
                    progress_bar.progress((i + 1) / len(drive_images_data), text=f"Đang tải ảnh từ Drive {i+1}/{len(drive_images_data)}")
                    img_bytes = drive_service.download_file(img_info['id'], img_info['name'])
                    if img_bytes:
                        img_path = images_dir / img_info['name']
                        with open(img_path, 'wb') as f:
                            f.write(img_bytes)
                
                progress_bar.progress(0, text="Đang tải audio từ Drive...")
                audio_bytes = drive_service.download_file(drive_audio_data['id'], drive_audio_data['name'])
                audio_path = temp_path / drive_audio_data['name']
                with open(audio_path, 'wb') as f:
                    f.write(audio_bytes)
                output_name = Path(drive_audio_data['name']).stem + "_video.mp4"
            
            # Get audio duration
            duration = get_audio_duration(str(audio_path))
            if duration > 0:
                st.info(f"⏱️ Thời lượng audio: {int(duration // 60)}:{int(duration % 60):02d}")
            
            output_path = temp_path / output_name
            status_text = st.empty()
            
            def update_progress(message):
                status_text.text(f"🔄 {message}")
            
            update_progress("Đang xử lý video...")
            
            success, error = create_video_from_images(
                image_folder=str(images_dir),
                audio_path=str(audio_path),
                output_path=str(output_path),
                enable_zoom=enable_zoom,
                enable_blur_bg=enable_blur,
                enable_dissolve=enable_dissolve,
                progress_callback=update_progress
            )
            
            if success:
                with open(output_path, 'rb') as f:
                    st.session_state.video_bytes = f.read()
                st.session_state.video_name = output_name
                st.session_state.video_ready = True
                
                # Upload to Drive if requested
                if upload_to_drive and DRIVE_AVAILABLE and drive_service.is_connected():
                    update_progress("Đang upload lên Drive...")
                    drive_link = drive_service.upload_bytes(
                        st.session_state.video_bytes,
                        output_name
                    )
                    if drive_link:
                        st.session_state['drive_link'] = drive_link
            else:
                st.error(f"❌ Lỗi: {error}")
        
        st.session_state.processing = False
        st.rerun()

# ============ DISPLAY RESULT ============
if st.session_state.get('video_ready') and st.session_state.get('video_bytes'):
    st.markdown("""
    <div class="success-box">
        ✅ <strong>Video đã được tạo thành công!</strong>
    </div>
    """, unsafe_allow_html=True)
    
    # Drive link if uploaded
    if st.session_state.get('drive_link'):
        st.success(f"☁️ Đã upload lên Drive: [Mở link]({st.session_state['drive_link']})")
    
    # Download button
    st.download_button(
        label="⬇️ Tải Video về máy",
        data=st.session_state.video_bytes,
        file_name=st.session_state.video_name,
        mime="video/mp4",
        type="primary",
        use_container_width=True
    )
    
    # Preview
    st.subheader("📺 Xem trước")
    st.video(st.session_state.video_bytes)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; font-size: 0.8rem;">
    Made with ❤️ using Streamlit | Powered by FFmpeg
</div>
""", unsafe_allow_html=True)
