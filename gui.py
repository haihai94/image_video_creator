"""
Image to Video Creator - Modern GUI
Drag & drop images folder + audio to create video.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
import threading
from pathlib import Path
import sv_ttk

from video_processor import create_video_from_images, get_image_files, get_audio_duration


class ImageVideoCreatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image to Video Creator")
        self.root.geometry("700x650")
        self.root.minsize(600, 550)
        
        # Variables
        self.image_folder = tk.StringVar()
        self.audio_file = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.enable_zoom = tk.BooleanVar(value=False)
        self.enable_blur_bg = tk.BooleanVar(value=False)
        self.enable_dissolve = tk.BooleanVar(value=False)
        self.is_processing = False
        
        # Apply dark theme
        sv_ttk.set_theme("dark")
        
        self._create_ui()
    
    def _create_ui(self):
        """Create the main UI."""
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="🎬 Image to Video Creator",
            font=("Segoe UI", 18, "bold")
        )
        title_label.pack(pady=(0, 20))
        
        # Image folder drop zone
        self._create_drop_zone(
            main_frame,
            "📁 Kéo thả thư mục ảnh vào đây",
            self.image_folder,
            self._on_image_drop,
            self._browse_image_folder,
            is_folder=True
        )
        
        # Audio file drop zone
        self._create_drop_zone(
            main_frame,
            "🎵 Kéo thả file audio vào đây",
            self.audio_file,
            self._on_audio_drop,
            self._browse_audio_file,
            is_folder=False
        )
        
        # Output folder
        output_frame = ttk.LabelFrame(main_frame, text="📤 Output Folder (Bắt buộc)", padding=10)
        output_frame.pack(fill=tk.X, pady=10)
        
        output_inner = ttk.Frame(output_frame)
        output_inner.pack(fill=tk.X)
        
        self.output_entry = ttk.Entry(output_inner, textvariable=self.output_folder, state='readonly')
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        ttk.Button(output_inner, text="Browse", command=self._browse_output_folder).pack(side=tk.RIGHT)
        
        # Options
        options_frame = ttk.LabelFrame(main_frame, text="⚙️ Tùy chọn", padding=10)
        options_frame.pack(fill=tk.X, pady=10)
        
        ttk.Checkbutton(
            options_frame,
            text="🔍 Zoom Effect (100% → 120%)",
            variable=self.enable_zoom
        ).pack(anchor=tk.W, pady=2)
        
        ttk.Checkbutton(
            options_frame,
            text="🌫️ Blur Background (thay nền đen)",
            variable=self.enable_blur_bg
        ).pack(anchor=tk.W, pady=2)
        
        ttk.Checkbutton(
            options_frame,
            text="✨ Dissolve Transition (1s in/out)",
            variable=self.enable_dissolve
        ).pack(anchor=tk.W, pady=2)
        
        # Info label
        self.info_label = ttk.Label(
            main_frame,
            text="Output: 1920x1080, 25Mbps video, 320kbps audio",
            font=("Segoe UI", 9),
            foreground="gray"
        )
        self.info_label.pack(pady=5)
        
        # Progress
        self.progress_var = tk.StringVar(value="Sẵn sàng")
        self.progress_label = ttk.Label(main_frame, textvariable=self.progress_var)
        self.progress_label.pack(pady=5)
        
        self.progress_bar = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # Generate button
        self.generate_btn = ttk.Button(
            main_frame,
            text="🎬 Tạo Video",
            command=self._start_generation,
            style="Accent.TButton"
        )
        self.generate_btn.pack(pady=15, ipadx=20, ipady=10)
    
    def _create_drop_zone(self, parent, text, variable, drop_handler, browse_handler, is_folder=True):
        """Create a drag & drop zone."""
        frame = ttk.LabelFrame(parent, text=text, padding=15)
        frame.pack(fill=tk.X, pady=10)
        
        # Drop area
        drop_label = ttk.Label(
            frame,
            text="Kéo thả hoặc click Browse",
            font=("Segoe UI", 10),
            foreground="gray"
        )
        drop_label.pack()
        
        # Path display
        path_frame = ttk.Frame(frame)
        path_frame.pack(fill=tk.X, pady=(10, 0))
        
        path_entry = ttk.Entry(path_frame, textvariable=variable, state='readonly')
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        browse_btn = ttk.Button(path_frame, text="Browse", command=browse_handler)
        browse_btn.pack(side=tk.RIGHT)
        
        # Register drag & drop
        frame.drop_target_register(DND_FILES)
        frame.dnd_bind('<<Drop>>', drop_handler)
        
        return frame
    
    def _on_image_drop(self, event):
        """Handle image folder drop."""
        path = self._clean_dnd_path(event.data)
        if Path(path).is_dir():
            self.image_folder.set(path)
            self._update_image_info()
        else:
            messagebox.showwarning("Lỗi", "Vui lòng kéo thả thư mục chứa ảnh!")
    
    def _on_audio_drop(self, event):
        """Handle audio file drop."""
        path = self._clean_dnd_path(event.data)
        audio_extensions = {'.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac'}
        if Path(path).is_file() and Path(path).suffix.lower() in audio_extensions:
            self.audio_file.set(path)
            self._update_audio_info()
        else:
            messagebox.showwarning("Lỗi", "Vui lòng kéo thả file audio!")
    
    def _clean_dnd_path(self, path):
        """Clean drag & drop path."""
        # Remove curly braces from path (Windows drag & drop)
        path = path.strip()
        if path.startswith('{') and path.endswith('}'):
            path = path[1:-1]
        return path
    
    def _browse_image_folder(self):
        """Browse for image folder."""
        folder = filedialog.askdirectory(title="Chọn thư mục chứa ảnh")
        if folder:
            self.image_folder.set(folder)
            self._update_image_info()
    
    def _browse_audio_file(self):
        """Browse for audio file."""
        file = filedialog.askopenfilename(
            title="Chọn file audio",
            filetypes=[
                ("Audio files", "*.mp3 *.wav *.m4a *.aac *.ogg *.flac"),
                ("All files", "*.*")
            ]
        )
        if file:
            self.audio_file.set(file)
            self._update_audio_info()
    
    def _browse_output_folder(self):
        """Browse for output folder."""
        folder = filedialog.askdirectory(title="Chọn thư mục xuất video")
        if folder:
            self.output_folder.set(folder)
    
    def _update_image_info(self):
        """Update image count info."""
        folder = self.image_folder.get()
        if folder and Path(folder).is_dir():
            images = get_image_files(folder)
            self.progress_var.set(f"Tìm thấy {len(images)} ảnh")
    
    def _update_audio_info(self):
        """Update audio duration info."""
        audio = self.audio_file.get()
        if audio and Path(audio).is_file():
            duration = get_audio_duration(audio)
            if duration > 0:
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                self.progress_var.set(f"Thời lượng audio: {minutes}:{seconds:02d}")
    
    def _validate_inputs(self):
        """Validate all inputs before generation."""
        # Check image folder
        if not self.image_folder.get():
            messagebox.showerror("Lỗi", "Vui lòng chọn thư mục chứa ảnh!")
            return False
        
        if not Path(self.image_folder.get()).is_dir():
            messagebox.showerror("Lỗi", "Thư mục ảnh không tồn tại!")
            return False
        
        images = get_image_files(self.image_folder.get())
        if not images:
            messagebox.showerror("Lỗi", "Không tìm thấy ảnh trong thư mục!")
            return False
        
        # Check audio file
        if not self.audio_file.get():
            messagebox.showerror("Lỗi", "Vui lòng chọn file audio!")
            return False
        
        if not Path(self.audio_file.get()).is_file():
            messagebox.showerror("Lỗi", "File audio không tồn tại!")
            return False
        
        # Check output folder (REQUIRED)
        if not self.output_folder.get():
            messagebox.showerror("Lỗi", "Vui lòng chọn thư mục xuất video!")
            return False
        
        if not Path(self.output_folder.get()).is_dir():
            messagebox.showerror("Lỗi", "Thư mục xuất không tồn tại!")
            return False
        
        return True
    
    def _start_generation(self):
        """Start video generation."""
        if self.is_processing:
            return
        
        if not self._validate_inputs():
            return
        
        self.is_processing = True
        self.generate_btn.config(state='disabled')
        self.progress_bar.start()
        
        # Generate output filename
        audio_name = Path(self.audio_file.get()).stem
        output_path = Path(self.output_folder.get()) / f"{audio_name}_video.mp4"
        
        # Start generation in thread
        thread = threading.Thread(
            target=self._generate_video,
            args=(output_path,),
            daemon=True
        )
        thread.start()
    
    def _generate_video(self, output_path):
        """Generate video in background thread."""
        try:
            success, error = create_video_from_images(
                image_folder=self.image_folder.get(),
                audio_path=self.audio_file.get(),
                output_path=str(output_path),
                enable_zoom=self.enable_zoom.get(),
                enable_blur_bg=self.enable_blur_bg.get(),
                enable_dissolve=self.enable_dissolve.get(),
                progress_callback=self._update_progress
            )
            
            self.root.after(0, lambda: self._generation_complete(success, error, output_path))
        except Exception as e:
            self.root.after(0, lambda: self._generation_complete(False, str(e), output_path))
    
    def _update_progress(self, message):
        """Update progress from background thread."""
        self.root.after(0, lambda: self.progress_var.set(message))
    
    def _generation_complete(self, success, error, output_path):
        """Handle generation completion."""
        self.is_processing = False
        self.generate_btn.config(state='normal')
        self.progress_bar.stop()
        
        if success:
            self.progress_var.set("✅ Hoàn thành!")
            messagebox.showinfo(
                "Thành công",
                f"Video đã được tạo thành công!\n\n{output_path}"
            )
        else:
            self.progress_var.set("❌ Lỗi!")
            messagebox.showerror("Lỗi", f"Không thể tạo video:\n{error}")


def main():
    root = TkinterDnD.Tk()
    app = ImageVideoCreatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
