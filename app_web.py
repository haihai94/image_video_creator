"""
Image to Video Creator - Streamlit Web Version
Upload images + audio to create video with effects.
"""
import streamlit as st
import tempfile
import os
from pathlib import Path
import zipfile
import shutil

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

# Page config
st.set_page_config(
    page_title="Image to Video Creator",
    page_icon="🎬",
    layout="centered"
)

# Custom CSS for dark theme
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
</style>
""", unsafe_allow_html=True)

# Title
st.markdown('<h1 class="main-title">🎬 Image to Video Creator</h1>', unsafe_allow_html=True)
st.markdown("---")

# Check FFmpeg
if not check_ffmpeg():
    st.error("⚠️ FFmpeg chưa được cài đặt! Vui lòng cài đặt FFmpeg trước khi sử dụng.")
    st.stop()

# Initialize session state
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'video_ready' not in st.session_state:
    st.session_state.video_ready = False
if 'output_path' not in st.session_state:
    st.session_state.output_path = None

# Upload sections
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

st.markdown("---")

# Options
st.subheader("⚙️ Tùy chọn hiệu ứng")
col1, col2, col3 = st.columns(3)

with col1:
    enable_zoom = st.checkbox("🔍 Zoom Effect", help="Zoom từ 100% → 120%")
with col2:
    enable_blur = st.checkbox("🌫️ Blur Background", help="Nền mờ thay vì đen")
with col3:
    enable_dissolve = st.checkbox("✨ Dissolve Transition", help="Chuyển cảnh mờ 1s")

st.markdown("---")

# Info
st.markdown("""
<div class="info-box">
📽️ <strong>Output:</strong> 1920x1080, 30fps, 25Mbps video, 320kbps audio
</div>
""", unsafe_allow_html=True)

# Generate button
if st.button("🎬 Tạo Video", type="primary", use_container_width=True, disabled=st.session_state.processing):
    
    # Validation
    if not uploaded_images:
        st.error("❌ Vui lòng upload ảnh!")
    elif not uploaded_audio:
        st.error("❌ Vui lòng upload file audio!")
    else:
        st.session_state.processing = True
        st.session_state.video_ready = False
        st.session_state.video_bytes = None
        st.session_state.video_name = None
        
        # Create temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Save uploaded images
            images_dir = temp_path / "images"
            images_dir.mkdir()
            
            progress_bar = st.progress(0, text="Đang lưu ảnh...")
            
            for i, img_file in enumerate(sorted(uploaded_images, key=lambda x: x.name)):
                img_path = images_dir / img_file.name
                with open(img_path, 'wb') as f:
                    f.write(img_file.getbuffer())
                progress_bar.progress((i + 1) / len(uploaded_images), text=f"Đang lưu ảnh {i+1}/{len(uploaded_images)}")
            
            # Save uploaded audio
            progress_bar.progress(0, text="Đang lưu audio...")
            audio_path = temp_path / uploaded_audio.name
            with open(audio_path, 'wb') as f:
                f.write(uploaded_audio.getbuffer())
            
            # Get audio duration
            duration = get_audio_duration(str(audio_path))
            if duration > 0:
                st.info(f"⏱️ Thời lượng audio: {int(duration // 60)}:{int(duration % 60):02d}")
            
            # Output path
            output_name = Path(uploaded_audio.name).stem + "_video.mp4"
            output_path = temp_path / output_name
            
            # Progress display
            status_text = st.empty()
            
            def update_progress(message):
                status_text.text(f"🔄 {message}")
            
            # Create video
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
                # Read video file and store in session state BEFORE temp dir is deleted
                with open(output_path, 'rb') as f:
                    st.session_state.video_bytes = f.read()
                st.session_state.video_name = output_name
                st.session_state.video_ready = True
            else:
                st.error(f"❌ Lỗi: {error}")
        
        st.session_state.processing = False
        st.rerun()  # Rerun to display download button

# Display download section if video is ready
if st.session_state.get('video_ready') and st.session_state.get('video_bytes'):
    st.markdown("""
    <div class="success-box">
        ✅ <strong>Video đã được tạo thành công!</strong>
    </div>
    """, unsafe_allow_html=True)
    
    # Download button
    st.download_button(
        label="⬇️ Tải Video về máy",
        data=st.session_state.video_bytes,
        file_name=st.session_state.video_name,
        mime="video/mp4",
        type="primary",
        use_container_width=True
    )
    
    # Preview video
    st.subheader("📺 Xem trước")
    st.video(st.session_state.video_bytes)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; font-size: 0.8rem;">
    Made with ❤️ using Streamlit | Powered by FFmpeg
</div>
""", unsafe_allow_html=True)
