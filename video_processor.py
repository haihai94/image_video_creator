"""
Image to Video Creator - Video Processing Module
Converts images + audio to video with optional effects.
"""
import subprocess
import os
import json
import tempfile
from pathlib import Path
from natsort import natsorted

# Hardware configuration - Power efficient mode
GPU_THREADS = 12
CPU_THREADS = 14  # 50% of 28 threads


def check_ffmpeg():
    """Check if FFmpeg is installed."""
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_nvenc():
    """Check if NVENC is actually available (not just compiled in)."""
    try:
        # Try to actually use nvenc - this will fail if CUDA isn't available
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-f', 'lavfi', '-i', 'nullsrc=s=64x64:d=0.1', 
             '-c:v', 'h264_nvenc', '-f', 'null', '-'],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        return result.returncode == 0
    except:
        return False


def get_audio_duration(audio_path):
    """Get audio duration in seconds."""
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        str(audio_path)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        data = json.loads(result.stdout)
        return float(data['format']['duration'])
    except:
        return 0.0


def get_image_files(folder_path):
    """Get sorted list of image files from folder."""
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff', '.gif'}
    folder = Path(folder_path)
    
    images = []
    for f in folder.iterdir():
        if f.is_file() and f.suffix.lower() in image_extensions:
            images.append(f)
    
    # Natural sort: 1, 2, 10 instead of 1, 10, 2
    return natsorted(images, key=lambda x: x.name.lower())


def run_ffmpeg_command(cmd, callback=None):
    """Run FFmpeg command with progress callback."""
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        if os.name == 'nt':
            creation_flags |= 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creation_flags
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='ignore')
            if callback:
                callback(f"FFmpeg error: {error_msg[:500]}")
            return False, error_msg
        
        return True, None
    except Exception as e:
        return False, str(e)


def create_video_from_images(
    image_folder,
    audio_path,
    output_path,
    enable_zoom=False,
    enable_blur_bg=False,
    enable_dissolve=False,
    progress_callback=None
):
    """
    Create video from images and audio.
    
    Args:
        image_folder: Path to folder containing images
        audio_path: Path to audio file
        output_path: Path for output video
        enable_zoom: Enable zoom effect (100% -> 120%)
        enable_blur_bg: Use blurred image as background instead of black
        enable_dissolve: Enable 1s dissolve transitions
        progress_callback: Function to call with progress updates
    
    Returns:
        (success, error_message)
    """
    if progress_callback:
        progress_callback("Đang kiểm tra FFmpeg...")
    
    if not check_ffmpeg():
        return False, "FFmpeg không được cài đặt!"
    
    # Get images
    images = get_image_files(image_folder)
    if not images:
        return False, "Không tìm thấy ảnh trong thư mục!"
    
    if progress_callback:
        progress_callback(f"Tìm thấy {len(images)} ảnh")
    
    # Get audio duration
    audio_duration = get_audio_duration(audio_path)
    if audio_duration <= 0:
        return False, "Không thể đọc file audio!"
    
    # Calculate duration per image
    duration_per_image = audio_duration / len(images)
    
    if progress_callback:
        progress_callback(f"Thời lượng mỗi ảnh: {duration_per_image:.2f}s")
    
    use_gpu = check_nvenc()
    if progress_callback:
        progress_callback(f"Sử dụng {'GPU (NVENC)' if use_gpu else 'CPU'} để encode")
    
    # Create temp directory for intermediate files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        if enable_dissolve:
            # Process with dissolve transitions
            return _create_video_with_dissolve(
                images, audio_path, output_path, duration_per_image,
                enable_zoom, enable_blur_bg, use_gpu, temp_path, progress_callback
            )
        else:
            # Process without transitions (simpler, faster)
            return _create_video_simple(
                images, audio_path, output_path, duration_per_image,
                enable_zoom, enable_blur_bg, use_gpu, temp_path, progress_callback
            )


def _build_image_filter(enable_zoom, enable_blur_bg, duration_frames, fps=30):
    """Build FFmpeg filter for a single image."""
    
    if enable_blur_bg and enable_zoom:
        # Blur background (STATIC) + Foreground zoom 100% → 110% from center
        # 1. Split into bg and fg
        # 2. Create static blur background at 1920x1080
        # 3. Apply zoompan ONLY to foreground (before overlay)
        # 4. Overlay zoomed foreground on static background
        filter_str = (
            "split[bg][fg];"
            "[bg]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=80:10[blur];"
            f"[fg]scale=-1:1080:force_original_aspect_ratio=decrease,"
            f"zoompan=z='1+0.1*on/{duration_frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={duration_frames}:s=1920x1080:fps={fps}[zoomed];"
            "[blur][zoomed]overlay=(W-w)/2:(H-h)/2:shortest=1"
        )
        return filter_str
    
    elif enable_blur_bg:
        # Blur background + centered image (no zoom)
        return (
            "split[bg][fg];"
            "[bg]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=80:10[blur];"
            "[fg]scale='min(1920,iw)':'min(1080,ih)':force_original_aspect_ratio=decrease[img];"
            "[blur][img]overlay=(W-w)/2:(H-h)/2"
        )
    
    elif enable_zoom:
        # Black background with zoom 100% → 110%
        return (
            f"scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,"
            f"zoompan=z='1+0.1*on/{duration_frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={duration_frames}:s=1920x1080:fps={fps}"
        )
    
    else:
        # Black background with centered image (no zoom)
        return (
            "scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black"
        )


def _create_video_simple(
    images, audio_path, output_path, duration_per_image,
    enable_zoom, enable_blur_bg, use_gpu, temp_path, progress_callback
):
    """Create video without dissolve transitions."""
    fps = 30
    duration_frames = int(duration_per_image * fps)
    
    # Create concat file
    concat_file = temp_path / "concat.txt"
    clip_files = []
    
    for i, img_path in enumerate(images):
        if progress_callback:
            progress_callback(f"Xử lý ảnh {i+1}/{len(images)}: {img_path.name}")
        
        clip_path = temp_path / f"clip_{i:04d}.mp4"
        clip_files.append(clip_path)
        
        # Build filter
        vf = _build_image_filter(enable_zoom, enable_blur_bg, duration_frames, fps)
        
        # Build command
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-i', str(img_path),
            '-t', str(duration_per_image),
            '-vf', vf,
            '-r', str(fps),
        ]
        
        if use_gpu:
            cmd.extend([
                '-c:v', 'h264_nvenc',
                '-preset', 'p4',
                '-cq', '18',
                '-gpu', '0',
            ])
        else:
            cmd.extend([
                '-threads', str(CPU_THREADS),
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '18',
            ])
        
        cmd.extend(['-an', str(clip_path)])
        
        success, error = run_ffmpeg_command(cmd)
        if not success:
            return False, f"Lỗi xử lý ảnh {img_path.name}: {error}"
    
    # Create concat file
    if progress_callback:
        progress_callback("Đang ghép video...")
    
    with open(concat_file, 'w', encoding='utf-8') as f:
        for clip in clip_files:
            escaped_path = str(clip).replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{escaped_path}'\n")
    
    # Concat clips
    concat_output = temp_path / "concat_output.mp4"
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', str(concat_file),
        '-c', 'copy',
        str(concat_output)
    ]
    
    success, error = run_ffmpeg_command(cmd)
    if not success:
        return False, f"Lỗi ghép video: {error}"
    
    # Add audio and final encode
    if progress_callback:
        progress_callback("Đang thêm audio và xuất file cuối cùng...")
    
    return _final_encode(concat_output, audio_path, output_path, use_gpu, progress_callback)


def _create_video_with_dissolve(
    images, audio_path, output_path, duration_per_image,
    enable_zoom, enable_blur_bg, use_gpu, temp_path, progress_callback
):
    """Create video with 1s dissolve transitions."""
    fps = 30
    dissolve_duration = 1.0  # 1 second dissolve
    
    # Adjust duration to account for overlapping transitions
    # Each image needs extra time for the transition overlap
    effective_duration = duration_per_image
    duration_frames = int(effective_duration * fps)
    
    clip_files = []
    
    # Create individual clips
    for i, img_path in enumerate(images):
        if progress_callback:
            progress_callback(f"Xử lý ảnh {i+1}/{len(images)}: {img_path.name}")
        
        clip_path = temp_path / f"clip_{i:04d}.mp4"
        clip_files.append(clip_path)
        
        vf = _build_image_filter(enable_zoom, enable_blur_bg, duration_frames, fps)
        
        cmd = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-i', str(img_path),
            '-t', str(effective_duration),
            '-vf', vf,
            '-r', str(fps),
        ]
        
        if use_gpu:
            cmd.extend([
                '-c:v', 'h264_nvenc',
                '-preset', 'p4',
                '-cq', '18',
                '-gpu', '0',
            ])
        else:
            cmd.extend([
                '-threads', str(CPU_THREADS),
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '18',
            ])
        
        cmd.extend(['-an', str(clip_path)])
        
        success, error = run_ffmpeg_command(cmd)
        if not success:
            return False, f"Lỗi xử lý ảnh {img_path.name}: {error}"
    
    # Apply xfade transitions between clips
    if progress_callback:
        progress_callback("Đang áp dụng chuyển cảnh dissolve...")
    
    if len(clip_files) == 1:
        # Only one clip, no transitions needed
        concat_output = clip_files[0]
    else:
        # Build xfade filter chain
        concat_output = temp_path / "dissolve_output.mp4"
        
        # Build inputs
        inputs = []
        for clip in clip_files:
            inputs.extend(['-i', str(clip)])
        
        # Build xfade filter chain
        filter_parts = []
        offset = effective_duration - dissolve_duration
        
        for i in range(len(clip_files) - 1):
            if i == 0:
                input_label = "[0:v]"
            else:
                input_label = f"[v{i}]"
            
            next_input = f"[{i+1}:v]"
            
            if i == len(clip_files) - 2:
                output_label = ""  # Last output
            else:
                output_label = f"[v{i+1}]"
            
            current_offset = offset + i * (effective_duration - dissolve_duration)
            filter_parts.append(
                f"{input_label}{next_input}xfade=transition=fade:duration={dissolve_duration}:offset={current_offset}{output_label}"
            )
        
        filter_complex = ";".join(filter_parts)
        
        cmd = [
            'ffmpeg', '-y',
            *inputs,
            '-filter_complex', filter_complex,
        ]
        
        if use_gpu:
            cmd.extend([
                '-c:v', 'h264_nvenc',
                '-preset', 'p4',
                '-cq', '18',
                '-gpu', '0',
            ])
        else:
            cmd.extend([
                '-threads', str(CPU_THREADS),
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '18',
            ])
        
        cmd.extend(['-an', str(concat_output)])
        
        success, error = run_ffmpeg_command(cmd)
        if not success:
            return False, f"Lỗi tạo chuyển cảnh: {error}"
    
    # Add audio and final encode
    if progress_callback:
        progress_callback("Đang thêm audio và xuất file cuối cùng...")
    
    return _final_encode(concat_output, audio_path, output_path, use_gpu, progress_callback)


def _final_encode(video_path, audio_path, output_path, use_gpu, progress_callback):
    """Final encode with target specifications."""
    if use_gpu:
        cmd = [
            'ffmpeg', '-y',
            '-i', str(video_path),
            '-i', str(audio_path),
            '-c:v', 'h264_nvenc',
            '-preset', 'p4',
            '-tune', 'hq',
            '-rc', 'cbr',
            '-b:v', '10000k',
            '-maxrate', '10000k',
            '-bufsize', '20000k',
            '-spatial_aq', '1',
            '-temporal_aq', '1',
            '-r', '30',
            '-s', '1920x1080',
            '-c:a', 'aac',
            '-b:a', '320k',
            '-ar', '48000',
            '-map', '0:v:0',
            '-map', '1:a:0',
            '-shortest',
            '-gpu', '0',
            str(output_path)
        ]
    else:
        cmd = [
            'ffmpeg', '-y',
            '-threads', str(CPU_THREADS),
            '-i', str(video_path),
            '-i', str(audio_path),
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-b:v', '10000k',
            '-maxrate', '10000k',
            '-bufsize', '20000k',
            '-r', '30',
            '-s', '1920x1080',
            '-c:a', 'aac',
            '-b:a', '320k',
            '-ar', '48000',
            '-map', '0:v:0',
            '-map', '1:a:0',
            '-shortest',
            str(output_path)
        ]
    
    success, error = run_ffmpeg_command(cmd)
    if success:
        if progress_callback:
            progress_callback("Hoàn thành!")
        return True, None
    else:
        return False, f"Lỗi xuất video: {error}"
