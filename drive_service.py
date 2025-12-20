"""
Google Drive Service Module
Handles OAuth2 authentication and Drive API operations.
All tokens are stored in st.session_state for user isolation.
"""
import streamlit as st
import os
import io
import json
from pathlib import Path

# Check if running on Streamlit Cloud
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

# OAuth2 scopes - Full drive access to read all folders
SCOPES = [
    'https://www.googleapis.com/auth/drive',           # Full Drive access
    'https://www.googleapis.com/auth/userinfo.email',  # Get user email
]

# Image and audio extensions
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.gif'}
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac'}


def is_available():
    """Check if Google libraries are available."""
    return GOOGLE_LIBS_AVAILABLE


def get_credentials_from_secrets():
    """Get OAuth2 client credentials from Streamlit secrets."""
    try:
        if hasattr(st, 'secrets') and 'google_oauth' in st.secrets:
            return {
                "web": {
                    "client_id": st.secrets["google_oauth"]["client_id"],
                    "client_secret": st.secrets["google_oauth"]["client_secret"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [st.secrets["google_oauth"].get("redirect_uri", "https://localhost:8501")]
                }
            }
    except Exception:
        pass
    return None


def is_connected():
    """Check if user is connected to Google Drive."""
    return st.session_state.get('google_token') is not None


def get_user_email():
    """Get connected user's email."""
    return st.session_state.get('google_email', '')


def disconnect():
    """Disconnect from Google Drive."""
    if 'google_token' in st.session_state:
        del st.session_state['google_token']
    if 'google_email' in st.session_state:
        del st.session_state['google_email']


def get_auth_url():
    """Get OAuth2 authorization URL."""
    client_config = get_credentials_from_secrets()
    if not client_config:
        return None
    
    try:
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=client_config['web']['redirect_uris'][0]
        )
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        st.session_state['oauth_flow'] = flow
        return auth_url
    except Exception as e:
        st.error(f"Lỗi tạo auth URL: {e}")
        return None


def handle_oauth_callback(auth_code):
    """Handle OAuth2 callback with authorization code."""
    try:
        flow = st.session_state.get('oauth_flow')
        if not flow:
            return False
        
        flow.fetch_token(code=auth_code)
        credentials = flow.credentials
        
        # Store token in session state (safe, per-user)
        st.session_state['google_token'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': list(credentials.scopes)
        }
        
        # Get user email
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        st.session_state['google_email'] = user_info.get('email', 'Unknown')
        
        return True
    except Exception as e:
        st.error(f"Lỗi xác thực: {e}")
        return False


def _get_credentials():
    """Get credentials from session state."""
    token_data = st.session_state.get('google_token')
    if not token_data:
        return None
    
    return Credentials(
        token=token_data['token'],
        refresh_token=token_data.get('refresh_token'),
        token_uri=token_data['token_uri'],
        client_id=token_data['client_id'],
        client_secret=token_data['client_secret'],
        scopes=token_data['scopes']
    )


def _get_drive_service():
    """Get Google Drive service."""
    credentials = _get_credentials()
    if not credentials:
        return None
    return build('drive', 'v3', credentials=credentials)


def list_folders():
    """List all folders in user's Drive."""
    service = _get_drive_service()
    if not service:
        return []
    
    try:
        results = service.files().list(
            q="mimeType='application/vnd.google-apps.folder' and trashed=false",
            spaces='drive',
            fields='files(id, name)',
            orderBy='name',
            pageSize=100
        ).execute()
        
        return results.get('files', [])
    except Exception as e:
        st.error(f"Lỗi liệt kê folder: {e}")
        return []


def list_files_in_folder(folder_id, file_type='all'):
    """List files in a specific folder."""
    service = _get_drive_service()
    if not service:
        return []
    
    try:
        # Build query based on file type
        query = f"'{folder_id}' in parents and trashed=false"
        
        results = service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, mimeType, size)',
            orderBy='name',
            pageSize=200
        ).execute()
        
        files = results.get('files', [])
        
        # Filter by type
        if file_type == 'images':
            files = [f for f in files if any(f['name'].lower().endswith(ext) for ext in IMAGE_EXTENSIONS)]
        elif file_type == 'audio':
            files = [f for f in files if any(f['name'].lower().endswith(ext) for ext in AUDIO_EXTENSIONS)]
        
        return files
    except Exception as e:
        st.error(f"Lỗi liệt kê file: {e}")
        return []


def download_file(file_id, file_name):
    """Download file from Drive to bytes."""
    service = _get_drive_service()
    if not service:
        return None
    
    try:
        request = service.files().get_media(fileId=file_id)
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        file_buffer.seek(0)
        return file_buffer.read()
    except Exception as e:
        st.error(f"Lỗi download {file_name}: {e}")
        return None


def upload_file(file_path, file_name, folder_id=None):
    """Upload file to Drive."""
    service = _get_drive_service()
    if not service:
        return None
    
    try:
        file_metadata = {'name': file_name}
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        media = MediaFileUpload(file_path, resumable=True)
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        return file.get('webViewLink')
    except Exception as e:
        st.error(f"Lỗi upload: {e}")
        return None


def upload_bytes(file_bytes, file_name, mime_type='video/mp4', folder_id=None):
    """Upload bytes to Drive."""
    service = _get_drive_service()
    if not service:
        return None
    
    try:
        file_metadata = {'name': file_name}
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        # Create temp file
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        
        media = MediaFileUpload(tmp_path, mimetype=mime_type, resumable=True)
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        # Clean up
        os.unlink(tmp_path)
        
        return file.get('webViewLink')
    except Exception as e:
        st.error(f"Lỗi upload: {e}")
        return None
