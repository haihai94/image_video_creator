# Hướng dẫn cấu hình Google Drive

## Bước 1: Tạo Google Cloud Project

1. Truy cập [console.cloud.google.com](https://console.cloud.google.com/)
2. Tạo Project mới (hoặc chọn project có sẵn)
3. Đặt tên, ví dụ: `image-video-creator`

## Bước 2: Bật Google Drive API

1. Vào **APIs & Services** → **Library**
2. Tìm **Google Drive API** → **Enable**
3. Tìm **Google OAuth2 API** → **Enable** (nếu chưa bật)

## Bước 3: Tạo OAuth2 Credentials

1. Vào **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Nếu chưa có OAuth consent screen:
   - Chọn **External**
   - Điền App name, User support email
   - Thêm scope: `drive.readonly`, `drive.file`, `userinfo.email`
   - Add test users (email của bạn)
4. Application type: **Web application**
5. Name: `Streamlit App`
6. Authorized redirect URIs: 
   ```
   https://imagevideocreator-63wmjyen5ujf7xp58h5vvo.streamlit.app/
   ```
   (Thay bằng URL app của bạn)
7. Click **Create** → Copy **Client ID** và **Client Secret**

## Bước 4: Cấu hình Streamlit Secrets

1. Vào Streamlit Cloud → App → **Settings** → **Secrets**
2. Thêm nội dung sau:

```toml
[google_oauth]
client_id = "YOUR_CLIENT_ID.apps.googleusercontent.com"
client_secret = "YOUR_CLIENT_SECRET"
redirect_uri = "https://imagevideocreator-63wmjyen5ujf7xp58h5vvo.streamlit.app/"
```

3. Click **Save**

## Bước 5: Test

1. Reboot app
2. Click **Đăng nhập Google** ở sidebar
3. Đăng nhập → Cho phép quyền → Kết nối thành công!

---

**Lưu ý:** Nếu app chưa được verify bởi Google, chỉ test users mới có thể đăng nhập.
