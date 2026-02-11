#!/usr/bin/env python3
"""
Facetak Web Server
Connects HTML frontend to existing Python backend with OAuth integration
"""

from flask import Flask, render_template, request, jsonify, send_from_directory, send_file, session, redirect, url_for
from service_account_drive import get_service_account_access_token
import os
import tempfile
import uuid
import time
import requests
import hashlib
import json
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from urllib.parse import urlencode, parse_qs, urlparse

# Import your existing modules (if they exist)
try:
    from flow_controller import process_drive_folder_and_store
except ImportError:
    # Use real drive processor instead
    from real_drive_processor import process_drive_folder_and_store

try:
    from progress_endpoint import create_progress_endpoint
except ImportError:
    create_progress_endpoint = None

try:
    from local_cache import get_cache_stats
except ImportError:
    get_cache_stats = None

# Import real face recognition engine (Phase 1)
from real_face_recognition_engine import get_real_engine

# Import Firebase store for database integration
from firebase_store import save_face_embedding, fetch_embeddings_for_user

# Import analytics tracker
from analytics_tracker import analytics

# Import blog manager
try:
    from blog_manager import blog_manager_bp
    BLOG_MANAGER_AVAILABLE = True
except ImportError:
    print("⚠️ Blog manager not available")
    BLOG_MANAGER_AVAILABLE = False

try:
    from image_tools import image_tools_bp
    IMAGE_TOOLS_AVAILABLE = True
except ImportError:
    print("⚠️ Image tools not available")
    IMAGE_TOOLS_AVAILABLE = False

# Super user/Admin list
SUPER_USERS = ['spvinodmandan@gmail.com']

def is_super_user(user_id):
    """Check if user is a super user/admin"""
    return user_id in SUPER_USERS

def require_super_user(func):
    """Decorator to require super user authentication"""
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        if not is_super_user(session['user_id']):
            return jsonify({'error': 'Access denied. Super user only.'}), 403
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

def record_user_feedback(user_id: str, photo_reference: str, is_correct: bool, 
                        selfie_path: str = None, similarity_score: float = None) -> bool:
    """
    Record user feedback for active learning system
    
    Args:
        user_id: User identifier
        photo_reference: Path or ID of the photo being rated
        is_correct: Whether the match was correct (True) or incorrect (False)
        selfie_path: Path to the selfie used for search
        similarity_score: Similarity score of the match
    
    Returns:
        bool: True if feedback was recorded successfully
    """
    try:
        import json
        from datetime import datetime
        
        # Create feedback data structure
        feedback_data = {
            'user_id': user_id,
            'photo_reference': photo_reference,
            'is_correct': is_correct,
            'selfie_path': selfie_path,
            'similarity_score': similarity_score,
            'timestamp': datetime.now().isoformat(),
            'feedback_type': 'explicit'  # vs 'implicit' for downloads
        }
        
        # Store feedback in JSON file (simple storage for now)
        feedback_dir = 'storage/feedback'
        os.makedirs(feedback_dir, exist_ok=True)
        
        feedback_file = os.path.join(feedback_dir, f"{user_id}_feedback.json")
        
        # Load existing feedback or create new list
        if os.path.exists(feedback_file):
            with open(feedback_file, 'r') as f:
                all_feedback = json.load(f)
        else:
            all_feedback = []
        
        # Add new feedback
        all_feedback.append(feedback_data)
        
        # Save updated feedback
        with open(feedback_file, 'w') as f:
            json.dump(all_feedback, f, indent=2)
        
        print(f"📝 Feedback recorded: {user_id} -> {photo_reference} -> {'✅ CORRECT' if is_correct else '❌ INCORRECT'}")
        
        # Trigger learning system update
        update_user_learning_profile(user_id, feedback_data)
        
        return True
        
    except Exception as e:
        print(f"❌ Error recording feedback: {e}")
        return False

def update_user_learning_profile(user_id: str, feedback_data: dict) -> None:
    """
    Update user's learning profile based on new feedback
    
    Args:
        user_id: User identifier
        feedback_data: Feedback data to process
    """
    try:
        import json
        from datetime import datetime
        
        # Load user's learning profile
        profile_dir = 'storage/learning_profiles'
        os.makedirs(profile_dir, exist_ok=True)
        
        profile_file = os.path.join(profile_dir, f"{user_id}_profile.json")
        
        if os.path.exists(profile_file):
            with open(profile_file, 'r') as f:
                profile = json.load(f)
        else:
            profile = {
                'user_id': user_id,
                'total_feedback': 0,
                'correct_matches': 0,
                'incorrect_matches': 0,
                'similarity_threshold': 0.7,  # Default threshold
                'learning_data': [],
                'last_updated': datetime.now().isoformat()
            }
        
        # Update profile with new feedback
        profile['total_feedback'] += 1
        
        if feedback_data['is_correct']:
            profile['correct_matches'] += 1
        else:
            profile['incorrect_matches'] += 1
        
        # Store learning data
        profile['learning_data'].append({
            'similarity_score': feedback_data.get('similarity_score'),
            'is_correct': feedback_data['is_correct'],
            'timestamp': feedback_data['timestamp']
        })
        
        # Keep only last 100 learning data points
        if len(profile['learning_data']) > 100:
            profile['learning_data'] = profile['learning_data'][-100:]
        
        # Calculate new similarity threshold based on feedback
        profile['similarity_threshold'] = calculate_optimal_threshold(profile['learning_data'])
        
        profile['last_updated'] = datetime.now().isoformat()
        
        # Save updated profile
        with open(profile_file, 'w') as f:
            json.dump(profile, f, indent=2)
        
        print(f"🧠 Updated learning profile for {user_id}: threshold={profile['similarity_threshold']:.3f}")
        
    except Exception as e:
        print(f"❌ Error updating learning profile: {e}")

def calculate_optimal_threshold(learning_data: list) -> float:
    """
    Calculate optimal similarity threshold based on user feedback
    
    Args:
        learning_data: List of feedback data points
    
    Returns:
        float: Optimal similarity threshold (0.0 to 1.0)
    """
    try:
        if not learning_data:
            return 0.7  # Default threshold
        
        # Separate correct and incorrect matches by similarity score
        correct_scores = [d['similarity_score'] for d in learning_data 
                         if d['is_correct'] and d['similarity_score'] is not None]
        incorrect_scores = [d['similarity_score'] for d in learning_data 
                           if not d['is_correct'] and d['similarity_score'] is not None]
        
        if not correct_scores and not incorrect_scores:
            return 0.7
        
        # Calculate optimal threshold
        if correct_scores and incorrect_scores:
            # Find threshold that maximizes correct matches while minimizing incorrect ones
            min_correct = min(correct_scores)
            max_incorrect = max(incorrect_scores)
            
            # Use midpoint between highest incorrect and lowest correct
            optimal_threshold = (min_correct + max_incorrect) / 2
        elif correct_scores:
            # Only correct matches - use minimum correct score
            optimal_threshold = min(correct_scores) - 0.05  # Slightly lower for safety
        else:
            # Only incorrect matches - use maximum incorrect score + buffer
            optimal_threshold = max(incorrect_scores) + 0.05
        
        # Clamp threshold to reasonable range
        optimal_threshold = max(0.5, min(0.95, optimal_threshold))
        
        return optimal_threshold
        
    except Exception as e:
        print(f"❌ Error calculating optimal threshold: {e}")
        return 0.7

def record_download_feedback(user_id: str, photo_reference: str, similarity_score: float = None) -> bool:
    """
    Record download as positive feedback for learning system
    
    Args:
        user_id: User identifier
        photo_reference: Path or ID of the downloaded photo
        similarity_score: Similarity score of the match
    
    Returns:
        bool: True if feedback was recorded successfully
    """
    try:
        import json
        from datetime import datetime
        
        # Create download feedback data
        download_data = {
            'user_id': user_id,
            'photo_reference': photo_reference,
            'is_correct': True,  # Download = positive feedback
            'similarity_score': similarity_score,
            'timestamp': datetime.now().isoformat(),
            'feedback_type': 'implicit',  # Implicit feedback from download
            'action': 'download'
        }
        
        # Store in same feedback system
        feedback_dir = 'storage/feedback'
        os.makedirs(feedback_dir, exist_ok=True)
        
        feedback_file = os.path.join(feedback_dir, f"{user_id}_feedback.json")
        
        if os.path.exists(feedback_file):
            with open(feedback_file, 'r') as f:
                all_feedback = json.load(f)
        else:
            all_feedback = []
        
        all_feedback.append(download_data)
        
        with open(feedback_file, 'w') as f:
            json.dump(all_feedback, f, indent=2)
        
        print(f"📥 Download feedback recorded: {user_id} -> {photo_reference} -> ✅ POSITIVE")
        
        # Update learning profile
        update_user_learning_profile(user_id, download_data)
        
        return True
        
    except Exception as e:
        print(f"❌ Error recording download feedback: {e}")
        return False

def get_user_learning_stats(user_id: str) -> dict:
    """
    Get user's learning statistics and current threshold
    
    Args:
        user_id: User identifier
    
    Returns:
        dict: Learning statistics
    """
    try:
        import json
        
        profile_file = os.path.join('storage/learning_profiles', f"{user_id}_profile.json")
        
        if os.path.exists(profile_file):
            with open(profile_file, 'r') as f:
                profile = json.load(f)
            
            # Calculate accuracy
            total = profile['total_feedback']
            correct = profile['correct_matches']
            accuracy = (correct / total * 100) if total > 0 else 0
            
            return {
                'total_feedback': total,
                'correct_matches': correct,
                'incorrect_matches': profile['incorrect_matches'],
                'accuracy_percentage': round(accuracy, 1),
                'current_threshold': profile['similarity_threshold'],
                'learning_active': total >= 5,  # Active after 5 feedback points
                'last_updated': profile['last_updated']
            }
        else:
            return {
                'total_feedback': 0,
                'correct_matches': 0,
                'incorrect_matches': 0,
                'accuracy_percentage': 0,
                'current_threshold': 0.7,
                'learning_active': False,
                'last_updated': None
            }
            
    except Exception as e:
        print(f"❌ Error getting learning stats: {e}")
        return {
            'total_feedback': 0,
            'correct_matches': 0,
            'incorrect_matches': 0,
            'accuracy_percentage': 0,
            'current_threshold': 0.7,
            'learning_active': False,
            'last_updated': None
        }

app = Flask(__name__)

# Register blog manager blueprint
if BLOG_MANAGER_AVAILABLE:
    app.register_blueprint(blog_manager_bp)
if IMAGE_TOOLS_AVAILABLE:
    app.register_blueprint(image_tools_bp)
    print("✅ Blog Manager registered")
# Load secret key from environment variable (more secure)
# Use a fixed secret key to prevent session invalidation on server restart
app.secret_key = os.environ.get('SECRET_KEY', 'cloudface-ai-secret-key-2024-stable-session-persistence')

# Configure session to be more persistent
from datetime import timedelta
app.permanent_session_lifetime = timedelta(hours=24)  # Sessions last 24 hours

# Session configuration for persistent login
from datetime import timedelta
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
# Only use secure cookies in production (HTTPS), allow HTTP in development
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production' or os.environ.get('HTTPS_ENABLED', 'false').lower() == 'true'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Add progress tracking endpoints (if available)
if create_progress_endpoint:
    create_progress_endpoint(app)
else:
    # Real progress stream endpoint using real progress tracker
    @app.route('/progress/stream')
    def real_progress_stream():
        """Real progress stream using real progress tracker - FIXED VERSION"""
        from flask import Response
        import json
        import time
        from real_progress_tracker import get_progress
        
        def generate():
            last_progress = None
            connection_count = 0
            max_connections = 3600  # 60 minutes at 1 second intervals (for large folders)
            error_count = 0
            max_errors = 5
            
            try:
                while connection_count < max_connections and error_count < max_errors:
                    try:
                        progress_data = get_progress()
                        
                        # Validate progress data
                        if not isinstance(progress_data, dict):
                            raise ValueError("Invalid progress data format")
                        
                        # Always send initial data
                        if last_progress is None:
                            safe_data = {
                                'overall': progress_data.get('overall', 0),
                                'current_step': progress_data.get('current_step', 'Starting...'),
                                'folder_info': progress_data.get('folder_info', {}),
                                'steps': progress_data.get('steps', {}),
                                'is_active': progress_data.get('is_active', False),
                                'search_ready': progress_data.get('search_ready', False),
                                'completion_message': progress_data.get('completion_message', ''),
                                'errors': progress_data.get('errors', [])[-5:],  # Last 5 errors only
                                'timestamp': time.time()
                            }
                            yield f"data: {json.dumps(safe_data)}\n\n"
                            last_progress = safe_data.copy()
                            connection_count += 1
                            time.sleep(1)
                            continue
                        
                        # Only send if progress has changed significantly
                        current_overall = progress_data.get('overall', 0)
                        last_overall = last_progress.get('overall', 0)
                        
                        if (current_overall != last_overall or 
                            progress_data.get('current_step') != last_progress.get('current_step') or
                            connection_count % 10 == 0):  # Send heartbeat every 10 seconds
                            
                            safe_data = {
                                'overall': current_overall,
                                'current_step': progress_data.get('current_step', 'Processing...'),
                                'folder_info': progress_data.get('folder_info', {}),
                                'steps': progress_data.get('steps', {}),
                                'is_active': progress_data.get('is_active', False),
                                'search_ready': progress_data.get('search_ready', False),
                                'completion_message': progress_data.get('completion_message', ''),
                                'errors': progress_data.get('errors', [])[-5:],  # Last 5 errors only
                                'timestamp': time.time()
                            }
                            yield f"data: {json.dumps(safe_data)}\n\n"
                            last_progress = safe_data.copy()
                        
                        # Check if processing is complete (search_ready flag)
                        if progress_data.get('search_ready', False):
                            # Send final completion message with all data
                            final_data = safe_data.copy()
                            final_data['complete'] = True
                            yield f"data: {json.dumps(final_data)}\n\n"
                            return
                        
                        # Check if processing is active
                        if progress_data.get('is_active', False):
                            time.sleep(0.5)  # Update every 500ms when active
                        else:
                            time.sleep(1)  # Update every 1 second when idle
                        
                        connection_count += 1
                        error_count = 0  # Reset error count on successful iteration
                        
                    except Exception as e:
                        error_count += 1
                        print(f"❌ Progress stream error (attempt {error_count}): {e}")
                        
                        # Send error to client
                        error_data = {
                            'error': str(e),
                            'error_count': error_count,
                            'timestamp': time.time()
                        }
                        yield f"data: {json.dumps(error_data)}\n\n"
                        
                        if error_count >= max_errors:
                            print(f"❌ Too many errors, closing stream")
                            break
                        
                        time.sleep(2)  # Wait before retry
                
                # Do not send a second close; stream ends naturally
                
            except Exception as e:
                print(f"❌ Fatal progress stream error: {e}")
                yield f"data: {json.dumps({'error': f'Fatal error: {str(e)}'})}\n\n"
        
        response = Response(generate(), mimetype='text/event-stream')
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Connection'] = 'keep-alive'
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Cache-Control'
        response.headers['X-Accel-Buffering'] = 'no'  # Disable nginx buffering
        return response

# Configuration
UPLOAD_FOLDER = 'storage/temp/selfies'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'heic'}

# URL Shortener Configuration
SHORT_LINKS_FILE = 'storage/short_links.json'

def load_short_links():
    """Load short links from file"""
    try:
        if os.path.exists(SHORT_LINKS_FILE):
            with open(SHORT_LINKS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading short links: {e}")
    return {}

def save_short_links(links):
    """Save short links to file"""
    try:
        os.makedirs(os.path.dirname(SHORT_LINKS_FILE), exist_ok=True)
        with open(SHORT_LINKS_FILE, 'w') as f:
            json.dump(links, f, indent=2)
    except Exception as e:
        print(f"Error saving short links: {e}")

def generate_short_code(url, event_name=None):
    """Generate a short code for the URL"""
    # Create hash from URL + timestamp for uniqueness
    hash_input = f"{url}{time.time()}"
    hash_obj = hashlib.md5(hash_input.encode())
    short_code = hash_obj.hexdigest()[:8]  # 8 character code
    
    # If event name provided, try to create a readable code
    if event_name:
        # Clean event name and create readable code
        clean_name = ''.join(c.lower() for c in event_name if c.isalnum())[:10]
        if clean_name:
            short_code = f"{clean_name}-{short_code[:4]}"
    
    return short_code

def create_short_link(full_url, event_name=None, expires_days=30):
    """Create a short link for the given URL"""
    links = load_short_links()
    
    # Check if URL already has a short link
    for code, data in links.items():
        if data['full_url'] == full_url:
            return f"https://cloudface-ai.com/s/{code}"
    
    # Generate new short code
    short_code = generate_short_code(full_url, event_name)
    
    # Ensure uniqueness
    counter = 1
    original_code = short_code
    while short_code in links:
        short_code = f"{original_code}{counter}"
        counter += 1
    
    # Store the mapping
    links[short_code] = {
        'full_url': full_url,
        'event_name': event_name,
        'created_at': datetime.now().isoformat(),
        'expires_at': (datetime.now() + timedelta(days=expires_days)).isoformat(),
        'click_count': 0
    }
    
    save_short_links(links)
    return f"https://cloudface-ai.com/s/{short_code}"

# Google OAuth Configuration
from dotenv import load_dotenv
load_dotenv('.env', override=True)

GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:8550/auth/callback')
GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v2/userinfo'
GOOGLE_SCOPES = [
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email'
]

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize Facial Recognition Pipeline V2
print("🚀 Initializing Facial Recognition Pipeline V2...")
try:
    real_engine = get_real_engine()
    print("✅ Real Face Recognition Engine initialized successfully")
    print(f"📊 Engine stats: {real_engine.get_stats()}")
except Exception as e:
    print(f"❌ Failed to initialize Real Face Recognition Engine: {e}")
    real_engine = None

def add_to_database(image_path: str, user_id: str, photo_reference: str) -> dict:
    """
    Add a face to the database using the V2 pipeline and Supabase.
    This function bridges the V2 pipeline with the existing database system.
    """
    try:
        import cv2
        import numpy as np
        
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            return {'success': False, 'error': 'Could not load image'}
        
        # Process with real face recognition to get embeddings
        faces = real_engine.detect_and_embed_faces(image)
        if not faces:
            return {'success': False, 'error': 'No face detected'}
        result = {'success': True, 'embeddings': [{'embedding': faces[0]['embedding']}]}
        
        if not result.get('success', False):
            return {'success': False, 'error': 'Face processing failed'}
        
        # Get the first embedding (assuming single face per image)
        embeddings = result.get('embeddings', [])
        if not embeddings:
            return {'success': False, 'error': 'No face embeddings generated'}
        
        # Use the first embedding
        embedding = embeddings[0]['embedding']
        
        # Convert to numpy array if it's a list
        if isinstance(embedding, list):
            embedding = np.array(embedding)
        
        # Save to Firebase using existing Firebase store
        success = save_face_embedding(user_id, photo_reference, embedding)
        
        if success:
            return {'success': True, 'message': f'Successfully added {photo_reference}'}
        else:
            return {'success': False, 'error': 'Failed to save to database'}
            
    except Exception as e:
        return {'success': False, 'error': f'Database error: {str(e)}'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _find_photo_by_file_id(user_id, file_id):
    """Find photo filename by Google Drive file ID in cache folders"""
    try:
        print(f"🔧 DEBUG: _find_photo_by_file_id called with user_id: {user_id}, file_id: {file_id}")
        
        # Get current folder_id from session to know which cache folder to search
        current_folder_id = session.get('current_folder_id')
        if not current_folder_id:
            print(f"❌ DEBUG: No current_folder_id in session")
            return None
        
        # Look in the cache folder for this specific Drive folder
        cache_folder = os.path.join('storage', 'downloads', f"{user_id}_{current_folder_id}")
        print(f"🔧 DEBUG: Searching in cache folder: {cache_folder}")
        
        if not os.path.exists(cache_folder):
            print(f"❌ DEBUG: Cache folder does not exist: {cache_folder}")
            return None
        
        # First, try to use the mapping file
        mapping_file = os.path.join(cache_folder, 'file_id_mapping.json')
        if os.path.exists(mapping_file):
            try:
                import json
                with open(mapping_file, 'r') as f:
                    file_mapping = json.load(f)
                if file_id in file_mapping:
                    filename = file_mapping[file_id]
                    file_path = os.path.join(cache_folder, filename)
                    if os.path.exists(file_path):
                        print(f"✅ Found photo by mapping file lookup: {filename}")
                        return filename
            except Exception as e:
                print(f"⚠️  Could not read mapping file: {e}")
        
        # Fallback: scan cache folder directly
        print(f"🔍 Scanning cache folder directly: {cache_folder}")
        for filename in os.listdir(cache_folder):
            if filename.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')):
                # Check if the file_id is in the filename
                if file_id in filename or f"{user_id}_{file_id}" in filename:
                    print(f"✅ Found photo by direct scan: {filename}")
                    return filename
        
        print(f"❌ DEBUG: Photo not found for file_id: {file_id} in cache folder: {cache_folder}")
        return None
    except Exception as e:
        print(f"❌ DEBUG: Error finding photo by file ID: {e}")
        import traceback
        traceback.print_exc()
        return None

def refresh_access_token():
    """Refresh the access token using the refresh token"""
    try:
        if 'refresh_token' not in session:
            return False
        
        token_data = {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'refresh_token': session['refresh_token'],
            'grant_type': 'refresh_token'
        }
        
        response = requests.post(GOOGLE_TOKEN_URL, data=token_data)
        if response.status_code == 200:
            tokens = response.json()
            session['access_token'] = tokens['access_token']
            print(f"✅ Access token refreshed successfully")
            return True
        else:
            print(f"❌ Token refresh failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error refreshing token: {e}")
        return False

def is_authenticated():
    """Check if user is authenticated and has valid tokens"""
    return 'access_token' in session and 'user_info' in session

def get_valid_access_token():
    """Get a valid access token, refreshing if necessary"""
    if not is_authenticated():
        return None
    
    # Try to use current token first
    access_token = session['access_token']
    
    # Test the token with a simple API call
    try:
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get('https://www.googleapis.com/oauth2/v1/userinfo', headers=headers)
        if response.status_code == 200:
            return access_token
    except:
        pass
    
    # If token is invalid, try to refresh it
    if refresh_access_token():
        return session['access_token']
    
    return None

def get_google_auth_url():
    """Generate Google OAuth URL"""
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'scope': ' '.join(GOOGLE_SCOPES),
        'response_type': 'code',
        'access_type': 'offline',
        'prompt': 'consent'
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

@app.route('/')
def landing():
    """Show the landing/marketing page"""
    return render_template('landing.html')

@app.route('/app')
def index():
    """Show the main app interface"""
    # Track page view
    user_id = session.get('user_id', 'anonymous')
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')
    referrer = request.headers.get('Referer', '')
    
    # Start or update session
    session_id = session.get('analytics_session_id')
    if not session_id:
        session_id = analytics.start_session(user_id, ip_address, user_agent, referrer, '/app')
        session['analytics_session_id'] = session_id
    else:
        analytics.track_page_view(session_id, user_id, '/app', 'CloudFace AI - Homepage', referrer)
    
    return render_template('index.html')

@app.route('/contact')
def contact():
    """Show the contact page"""
    return render_template('contact.html')

@app.route('/about')
def about():
    """Show the about page"""
    return render_template('about.html')

@app.route('/blog')
def blog():
    """Show the blog page with all articles"""
    # Load dynamic blog posts from metadata
    dynamic_posts = []
    try:
        metadata_file = 'storage/blog_posts_metadata.json'
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r', encoding='utf-8') as f:
                all_posts = json.load(f)
                # Filter only published posts
                dynamic_posts = [p for p in all_posts if p.get('status') == 'published']
                # Sort by created_at (newest first)
                dynamic_posts.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    except Exception as e:
        print(f"⚠️ Error loading dynamic blog posts: {e}")
    
    return render_template('blog.html', dynamic_posts=dynamic_posts)

@app.route('/blog/fortune-500-photo-software')
def blog_fortune_500():
    """Fortune 500 Photo Software Guide"""
    return render_template('blog/fortune-500-photo-software.html')

@app.route('/blog/coca-cola-photo-management')
def blog_coca_cola():
    """Coca-Cola Photo Management Case Study"""
    return render_template('blog/coca-cola-photo-management.html')

@app.route('/blog/nike-photo-organization')
def blog_nike():
    """Nike Photo Organization Secrets"""
    return render_template('blog/nike-photo-organization.html')

@app.route('/blog/red-bull-formula1-photography')
def blog_red_bull():
    """Red Bull Formula 1 Photography Technology"""
    return render_template('blog/red-bull-formula1-photography.html')

@app.route('/blog/spotify-music-events')
def blog_spotify():
    """Spotify Music Event Photo Organization"""
    return render_template('blog/spotify-music-events.html')

@app.route('/blog/professional-photographers-cloudface-ai')
def blog_professional_photographers():
    """Professional Wedding & Travel Photographers Guide"""
    return render_template('blog/professional-photographers-cloudface-ai.html')

@app.route('/blog/government-transportation-live-tracking')
def blog_government_transportation():
    """Government Transportation Live Tracking Systems"""
    return render_template('blog/government-transportation-live-tracking.html')

@app.route('/blog/worlds-first-privacy-face-recognition')
def blog_privacy_protection():
    """World's First Privacy-Protecting Face Recognition"""
    return render_template('blog/worlds-first-privacy-face-recognition.html')

@app.route('/blog/gdpr-face-recognition-privacy-compliance')
def blog_gdpr_compliance():
    """GDPR Compliant Face Recognition Privacy"""
    return render_template('blog/gdpr-face-recognition-privacy-compliance.html')

@app.route('/blog/privacy-destruction-major-apps-facebook-instagram')
def blog_privacy_destruction():
    """How Major Apps Destroy Privacy - Facebook Instagram Expose"""
    return render_template('blog/privacy-destruction-major-apps-facebook-instagram.html')

@app.route('/blog/india-privacy-laws-international-human-rights')
def blog_india_privacy_laws():
    """India Privacy Laws and International Human Rights Guide"""
    return render_template('blog/india-privacy-laws-international-human-rights.html')

@app.route('/blog/privacy-experts-expose-big-tech-surveillance')
def blog_privacy_experts():
    """Privacy Experts Expose Big Tech Surveillance - Expert Quotes"""
    return render_template('blog/privacy-experts-expose-big-tech-surveillance.html')

@app.route('/blog/best-face-search-apps-2025')
def best_face_search_apps_2025():
    """Show the best face search apps 2025 comparison blog post"""
    return render_template('blog_posts/best_face_search_apps_2025.html')

@app.route('/blog/cloudface-ai-privacy-secure')
def cloudface_ai_privacy_secure():
    """Show the CloudFace AI privacy secure blog post"""
    return render_template('blog_posts/cloudface_ai_privacy_secure.html')

@app.route('/blog/google-drive-face-search-guide')
def google_drive_face_search_guide():
    """Show the Google Drive face search guide blog post"""
    return render_template('blog_posts/google_drive_face_search_guide.html')

@app.route('/blog/face-recognition-dark-blurry-photos')
def face_recognition_dark_blurry_photos():
    """Show the face recognition dark blurry photos blog post"""
    return render_template('blog_posts/face_recognition_dark_blurry_photos.html')

@app.route('/blog/step-by-step-photo-processing-guide')
def step_by_step_photo_processing_guide():
    """Show the step-by-step photo processing guide blog post"""
    return render_template('blog_posts/step_by_step_photo_processing_guide.html')

@app.route('/blog/ai-powered-photo-management-corporate-events-2025')
def ai_powered_photo_management_corporate_events_2025():
    """Show the AI-powered photo management for corporate events blog post"""
    return render_template('blog/ai-powered-photo-management-corporate-events-2025.html')

@app.route('/blog/privacy-first-face-recognition-trends-2025')
def privacy_first_face_recognition_trends_2025():
    """Show the privacy-first face recognition trends blog post"""
    return render_template('blog/privacy-first-face-recognition-trends-2025.html')

@app.route('/blog/hybrid-events-photo-organization-ai-2025')
def hybrid_events_photo_organization_ai_2025():
    """Show the hybrid events photo organization with AI blog post"""
    return render_template('blog/hybrid-events-photo-organization-ai-2025.html')

# Dynamic blog post route handler (catches all /blog/* routes)
@app.route('/blog/<slug>')
def dynamic_blog_post(slug):
    """Dynamic route handler for blog posts created via blog manager"""
    try:
        print(f"🔍 Looking for blog post with slug: {slug}")
        # Check if it's a static route first (existing hardcoded posts)
        # If not found, try dynamic route
        metadata_file = 'storage/blog_posts_metadata.json'
        print(f"🔍 Metadata file exists: {os.path.exists(metadata_file)}")
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r', encoding='utf-8') as f:
                posts = json.load(f)
            
            print(f"🔍 Loaded {len(posts)} posts from metadata")
            # Find post by slug
            post = next((p for p in posts if p.get('slug') == slug and p.get('status') == 'published'), None)
            print(f"🔍 Post found: {post is not None}")
            if post:
                print(f"✅ Found post: {post.get('title', 'Untitled')}")
                # Try to load from template file first
                template_path = f"blog_posts/{slug}.html"
                if os.path.exists(os.path.join('templates', template_path)):
                    return render_template(template_path)
                
                # If template doesn't exist, generate it on-the-fly
                try:
                    from blog_manager import generate_blog_template
                    # Load content from storage
                    content_file = os.path.join('storage/blog_posts', f"{post['id']}.html")
                    content = ''
                    if os.path.exists(content_file):
                        with open(content_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                    
                    # Generate the full HTML with header/footer
                    full_html = generate_blog_template(post, content)
                    
                    # Save it for future requests
                    template_file = os.path.join('templates', template_path)
                    os.makedirs(os.path.dirname(template_file), exist_ok=True)
                    with open(template_file, 'w', encoding='utf-8') as f:
                        f.write(full_html)
                    
                    return full_html
                except Exception as e:
                    print(f"⚠️ Error generating template for {slug}: {e}")
                    import traceback
                    traceback.print_exc()
                    return f"Error generating blog post: {str(e)}", 500
            else:
                print(f"❌ Post not found or not published. Slug: {slug}")
                # Debug: show all slugs
                all_slugs = [p.get('slug') for p in posts]
                print(f"🔍 Available slugs: {all_slugs[:5]}...")
        
        # If not found in dynamic posts, return 404
        print(f"❌ Returning 404 for slug: {slug}")
        return "Blog post not found", 404
    except Exception as e:
        print(f"⚠️ Error loading dynamic blog post: {e}")
        import traceback
        traceback.print_exc()
        return "Error loading blog post", 500

# Register static blog routes on startup (for existing hardcoded posts)
def register_static_blog_routes():
    """Register static routes for existing hardcoded blog posts"""
    # This is handled by the @app.route decorators above
    pass

@app.route('/privacy')
def privacy():
    """Show the privacy policy page"""
    return render_template('privacy.html')

@app.route('/refund')
def refund():
    """Show the refund policy page"""
    return render_template('refund.html')

@app.route('/terms')
def terms():
    """Show the terms and conditions page"""
    return render_template('terms.html')


@app.route('/pricing')
def pricing():
    """Show the pricing page with dynamic plans"""
    try:
        from pricing_manager import pricing_manager
        
        # Get currency from URL parameter or detect from location
        currency = request.args.get('currency', '').lower()
        if currency not in ['inr', 'usd']:
            # Detect user location for currency (default to INR)
            user_location = request.headers.get('CF-IPCountry', 'IN')  # Cloudflare header
            currency = 'inr' if user_location == 'IN' else 'usd'
        
        # Get all plans
        plans = pricing_manager.get_all_plans(currency)
        
        # Get user's current plan if authenticated
        current_plan = None
        if 'user_id' in session:
            user_id = session['user_id']
            # Check if super user
            if is_super_user(user_id):
                current_plan = 'enterprise'
            else:
                user_plan_data = pricing_manager.get_user_plan(user_id)
                current_plan = user_plan_data.get('plan_type', 'free')
        
        return render_template('pricing.html', 
                             plans=plans,
                             currency=currency,
                             current_plan=current_plan)
        
    except Exception as e:
        print(f"❌ Error loading pricing: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to static pricing page with default values
        return render_template('pricing.html', 
                             plans={}, 
                             currency='inr', 
                             current_plan='free')

@app.route('/how-it-works-alt')
def how_it_works_alt():
    """Alternate How It Works page"""
    return render_template('how-it-works-alt.html')

@app.route('/how-it-works-pro')
def how_it_works_pro():
    """Pro How It Works page (new design)"""
    return render_template('how-it-works-pro.html')

@app.route('/how-it-works')
def how_it_works():
    """Show the How It Works page"""
    return render_template('how-it-works.html')

@app.route('/my-photos')
def my_photos():
    """Show My Photos dashboard with folder-wise organization"""
    try:
        # Check authentication
        if 'user_id' not in session:
            return redirect('/auth/login')
        
        user_id = session['user_id']
        
        # Get cache statistics from search cache manager
        from search_cache_manager import cache_manager
        cache_stats = cache_manager.get_cache_stats(user_id)
        
        # My Photos should only show search results, not all processed photos
        # The cache_stats already contains the search results from search_cache_manager
        cache_stats['processed_photos'] = 0  # Don't show processed photos count
        cache_stats['has_processed_photos'] = False  # Don't show processed photos state
        
        # Get user info for display
        user_info = {
            'name': session.get('user_name', 'User'),
            'email': session.get('user_email', user_id),
            'profile_pic': session.get('user_profile_pic', '')
        }
        
        return render_template('my-photos.html', 
                             cache_stats=cache_stats,
                             user_info=user_info)
        
    except Exception as e:
        print(f"❌ Error loading My Photos: {e}")
        import traceback
        traceback.print_exc()
        return render_template('my-photos.html', 
                             cache_stats={'error': str(e)},
                             user_info={'name': 'User', 'email': 'unknown', 'profile_pic': ''})

@app.route('/my-photos/folder/<folder_id>')
def view_folder_photos(folder_id):
    """View all photos from a specific folder"""
    try:
        # Check authentication
        if 'user_id' not in session:
            return redirect('/auth/login')
        
        user_id = session['user_id']
        
        # Get cached results for this folder
        from search_cache_manager import cache_manager
        cached_results = cache_manager.get_cached_results(user_id, folder_id)
        
        if not cached_results:
            return render_template('folder-photos.html', 
                                 error="No cached results found for this folder",
                                 folder_id=folder_id)
        
        # Extract matches from cached results
        matches = cached_results.get('search_results', {}).get('matches', [])
        
        # Get folder info
        folder_info = {
            'id': folder_id,
            'match_count': len(matches),
            'cached_at': cached_results.get('cached_at', 'Unknown'),
            'name': f"Folder {folder_id[:8]}..."  # Shortened folder ID
        }
        
        return render_template('folder-photos.html',
                             matches=matches,
                             folder_info=folder_info)
        
    except Exception as e:
        print(f"❌ Error loading folder photos: {e}")
        return render_template('folder-photos.html',
                             error=str(e),
                             folder_id=folder_id)

@app.route('/api/clear-cache/<folder_id>', methods=['POST'])
def clear_folder_cache(folder_id):
    """Clear cache for a specific folder"""
    try:
        # Check authentication
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Not authenticated'})
        
        user_id = session['user_id']
        
        # Clear the cache
        from search_cache_manager import cache_manager
        success = cache_manager.clear_cache(user_id, folder_id)
        
        if success:
            return jsonify({'success': True, 'message': f'Cache cleared for folder {folder_id}'})
        else:
            return jsonify({'success': False, 'error': 'Failed to clear cache'})
            
    except Exception as e:
        print(f"❌ Error clearing cache: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/payment/checkout')
def payment_checkout():
    """Payment checkout page"""
    try:
        # Check authentication
        if 'user_id' not in session:
            return redirect('/auth/login')
        
        plan_id = request.args.get('plan', 'standard')
        currency = request.args.get('currency', 'inr')
        
        from pricing_manager import pricing_manager
        from payment_gateway import payment_gateway
        
        # Get plan details
        plans = pricing_manager.get_all_plans(currency)
        selected_plan = plans.get(plan_id)
        
        if not selected_plan:
            return redirect('/pricing')
        
        # Get payment methods
        payment_methods = payment_gateway.get_payment_methods('IN' if currency == 'inr' else 'US')
        
        return render_template('checkout.html',
                             plan=selected_plan,
                             plan_id=plan_id,
                             currency=currency,
                             payment_methods=payment_methods,
                             user_id=session['user_id'])
        
    except Exception as e:
        print(f"❌ Error loading checkout: {e}")
        return redirect('/pricing')

@app.route('/api/usage-stats')
def get_usage_stats():
    """Get user's current usage statistics"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        
        from pricing_manager import pricing_manager
        stats = pricing_manager.get_usage_stats(session['user_id'])
        
        return jsonify({'success': True, 'stats': stats})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/make-pro')
def admin_make_pro():
    """Admin endpoint to make current user Pro (for testing)"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user_id = session['user_id']
        
        from pricing_manager import pricing_manager
        success = pricing_manager.make_user_pro(user_id)
        
        if success:
            return jsonify({
                'success': True, 
                'message': f'✅ User {user_id} upgraded to Pro plan!',
                'plan': 'Pro',
                'image_limit': 50000,
                'expires': '1 year from now'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to upgrade user'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/create-payment', methods=['POST'])
def create_payment():
    """Create payment order"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        plan_id = data.get('plan_id')
        currency = data.get('currency', 'inr')
        
        from pricing_manager import pricing_manager
        from payment_gateway import payment_gateway
        
        # Get plan details
        plans = pricing_manager.get_all_plans(currency)
        plan = plans.get(plan_id)
        
        if not plan:
            return jsonify({'success': False, 'error': 'Invalid plan'})
        
        # Create payment order
        if currency == 'inr':
            # Try to use Razorpay subscription first
            razorpay_plan_id = payment_gateway.get_razorpay_plan_id(plan_id)
            if razorpay_plan_id:
                result = payment_gateway.create_razorpay_subscription(
                    razorpay_plan_id, session['user_id']
                )
                print(f"💳 Razorpay subscription result: {result}")
            else:
                # Fallback to one-time payment
                result = payment_gateway.create_razorpay_order(
                    plan['price'], plan['name'], session['user_id']
                )
                print(f"💳 Razorpay order result: {result}")
        else:
            result = payment_gateway.create_paypal_order(
                plan['price'], plan['name'], session['user_id']
            )
        
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Payment creation exception: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/verify-payment', methods=['POST'])
def verify_payment():
    """Verify and process successful payment"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        payment_method = data.get('method', 'razorpay')
        
        from pricing_manager import pricing_manager
        from payment_gateway import payment_gateway
        
        # Verify payment
        if payment_method == 'razorpay':
            verification = payment_gateway.verify_razorpay_payment(data)
        else:
            verification = payment_gateway.verify_paypal_payment(data)
        
        if verification['success']:
            # Upgrade user plan
            plan_id = data.get('plan_id')
            payment_info = {
                'amount': data.get('amount', 0),
                'currency': data.get('currency', 'INR'),
                'payment_id': verification['payment_id'],
                'method': payment_method
            }
            
            upgrade_success = pricing_manager.upgrade_user_plan(
                session['user_id'], plan_id, payment_info
            )
            
            if upgrade_success:
                return jsonify({
                    'success': True,
                    'message': 'Payment successful! Your plan has been upgraded.',
                    'redirect': '/app'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Payment verified but plan upgrade failed. Please contact support.'
                })
        else:
            return jsonify({
                'success': False,
                'error': verification.get('error', 'Payment verification failed')
            })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Serve root logo asset for headers
@app.route('/Cloudface-ai-logo.png')
def serve_root_logo():
    try:
        return send_from_directory('.', 'Cloudface-ai-logo.png')
    except Exception as e:
        return jsonify({'error': str(e)}), 404

# Also support the "/root/Cloudface-ai-logo.png" path used in templates
@app.route('/root/Cloudface-ai-logo.png')
def serve_root_logo_with_prefix():
    try:
        return send_from_directory('.', 'Cloudface-ai-logo.png')
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/auth/login')
def google_login():
    """Redirect to Google OAuth"""
    auth_url = get_google_auth_url()
    return redirect(auth_url)

@app.route('/auth/callback')
def google_callback():
    """Handle Google OAuth callback"""
    try:
        # Get authorization code from callback
        code = request.args.get('code')
        if not code:
            return jsonify({'success': False, 'error': 'No authorization code received'})
        
        # Exchange code for tokens
        token_data = {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': GOOGLE_REDIRECT_URI
        }
        
        response = requests.post(GOOGLE_TOKEN_URL, data=token_data)
        if response.status_code != 200:
            return jsonify({'success': False, 'error': f'Token exchange failed: {response.text}'})
        
        tokens = response.json()
        
        # Get user info
        headers = {'Authorization': f"Bearer {tokens['access_token']}"}
        user_response = requests.get(GOOGLE_USERINFO_URL, headers=headers)
        if user_response.status_code != 200:
            return jsonify({'success': False, 'error': f'Failed to get user info: {user_response.text}'})
        
        user_info = user_response.json()
        
        # Store in session with debugging
        session.permanent = True  # Make session last 30 days
        session['access_token'] = tokens['access_token']
        session['refresh_token'] = tokens.get('refresh_token')
        session['user_info'] = user_info
        session['user_id'] = user_info['email']
        
        print(f"SUCCESS: User authenticated: {user_info['email']}")
        print(f"SUCCESS: Access token stored: {tokens['access_token'][:20]}...")
        print(f"SUCCESS: Session keys after login: {list(session.keys())}")
        print(f"SUCCESS: Session permanent: {session.permanent}")
        
        # Make session permanent to prevent expiration
        session.permanent = True
        
        # Check for return URL in session (from auto-process flow)
        return_url = session.pop('return_after_auth', '/app')
        
        # Redirect back
        return redirect(return_url)
        
    except Exception as e:
        print(f"❌ OAuth callback error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/auth/logout')
def logout():
    """Clear user session"""
    session.clear()
    return redirect('/')

@app.route('/auth/status')
def auth_status():
    """Check authentication status"""
    if is_authenticated():
        return jsonify({
            'authenticated': True,
            'user': session['user_info'],
            'session_keys': list(session.keys()),
            'user_id': session.get('user_id'),
            'user_email': session.get('user_id')  # user_id is the email
        })
    else:
        return jsonify({
            'authenticated': False,
            'login_url': '/auth/login',
            'session_keys': list(session.keys()),
            'debug_info': {
                'access_token_present': 'access_token' in session,
                'user_info_present': 'user_info' in session,
                'user_id_present': 'user_id' in session
            }
        })

@app.route('/auth/refresh')
def refresh_token():
    """Manually refresh access token"""
    try:
        if refresh_access_token():
            return jsonify({
                'success': True,
                'message': 'Token refreshed successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to refresh token. Please sign in again.'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/process_local', methods=['POST'])
def process_local():
    """Process uploaded files - handles local file uploads"""
    try:
        print(f"🔍 /process_local route called")
        print(f"📋 Request method: {request.method}")
        print(f"📋 Request content type: {request.content_type}")
        print(f"📋 Request files: {list(request.files.keys())}")
        print(f"📋 Request form: {dict(request.form)}")
        
        # Check authentication
        if not is_authenticated():
            print("❌ Not authenticated")
            return jsonify({'error': 'Not authenticated'}), 401
        
        user_id = session.get('user_id')
        print(f"👤 User ID: {user_id}")
        
        # Get uploaded files
        uploaded_files = request.files.getlist('files')
        force_reprocess = request.form.get('force_reprocess', 'false').lower() == 'true'
        
        print(f"📁 Received {len(uploaded_files)} uploaded files")
        for i, file_obj in enumerate(uploaded_files[:3]):  # Log first 3 files
            print(f"  📄 File {i+1}: {file_obj.filename} ({file_obj.content_length} bytes)")
        
        if not uploaded_files or len(uploaded_files) == 0:
            return jsonify({'success': False, 'error': 'No files uploaded'})
        
        print(f"📁 Received {len(uploaded_files)} uploaded files")
        
        # Check user plan limits before processing
        try:
            from pricing_manager import pricing_manager
            
            # Estimate number of images (quick count)
            from local_folder_processor import LocalFolderProcessor
            temp_processor = LocalFolderProcessor()
            image_files = temp_processor._filter_uploaded_image_files(uploaded_files)
            estimated_images = len(image_files)
            
            if not pricing_manager.can_process_images(user_id, estimated_images):
                user_plan = pricing_manager.get_user_plan(user_id)
                return jsonify({
                    'success': False, 
                    'error': f'Plan limit exceeded. Found {estimated_images} images, but your {user_plan["plan_name"]} plan allows {user_plan["limits"]["images"]} images.',
                    'upgrade_needed': True,
                    'current_plan': user_plan["plan_name"],
                    'estimated_images': estimated_images
                })
        except ImportError:
            print("⚠️  Pricing manager not available, proceeding without limits")
        
        # Import and use local folder processor
        from local_folder_processor import process_uploaded_files_and_store
        
        print(f"🔍 Processing {len(uploaded_files)} uploaded files")
        print(f"👤 User: {user_id}")
        print(f"🔄 Force reprocess: {force_reprocess}")
        
        # Process the uploaded files
        result = process_uploaded_files_and_store(
            user_id=user_id,
            uploaded_files=uploaded_files,
            force_reprocess=force_reprocess
        )
        
        # Track usage if processing was successful
        if result.get('success') and result.get('processed_count', 0) > 0:
            try:
                from pricing_manager import pricing_manager
                pricing_manager.track_image_usage(user_id, result['processed_count'])
                print(f"📊 Tracked {result['processed_count']} images for user {user_id}")
            except Exception as e:
                print(f"⚠️ Usage tracking failed: {e}")
        
        print(f"✅ Upload processing result: {result}")
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Error in process_local: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/process_drive', methods=['POST'])
def process_drive():
    """Process Google Drive folder - connects to your existing code"""
    try:
        # Debug: Log session state
        print(f"INFO: Process Drive Request - Session keys: {list(session.keys())}")
        print(f"INFO: User ID in session: {session.get('user_id', 'NOT_FOUND')}")
        print(f"INFO: Access token present: {'access_token' in session}")
        print(f"INFO: User info present: {'user_info' in session}")
        
        # Check authentication with detailed logging
        auth_check = is_authenticated()
        print(f"INFO: Authentication check result: {auth_check}")
        
        if not auth_check:
            # Try to get a valid token
            valid_token = get_valid_access_token()
            print(f"INFO: Valid token check: {valid_token is not None}")
            
            if not valid_token:
                return jsonify({'success': False, 'error': 'Not authenticated. Please sign in with Google first.'})
        
        data = request.get_json()
        drive_url = data.get('drive_url')
        force_reprocess = data.get('force_reprocess', False)
        max_depth = data.get('max_depth', 10)  # Default to 10 levels deep
        
        if not drive_url:
            return jsonify({'success': False, 'error': 'No drive URL provided'})
        
        # Validate max_depth
        if not isinstance(max_depth, int) or max_depth < 1 or max_depth > 20:
            max_depth = 10  # Default to 10 if invalid
        
        # Get valid access token (refresh if necessary)
        user_id = session['user_id']
        access_token = get_valid_access_token()
        
        if not access_token:
            return jsonify({'success': False, 'error': 'Authentication failed. Please sign in again.'})
        
        # Extract folder_id from drive URL for folder isolation
        from google_drive_handler import extract_file_id_from_url
        folder_id = extract_file_id_from_url(drive_url)
        if not folder_id:
            return jsonify({'success': False, 'error': 'Could not extract folder ID from URL'})
        
        # Check user's plan limits before processing
        from pricing_manager import pricing_manager
        
        # Get estimated file count (quick check)
        try:
            from real_drive_processor import RealDriveProcessor
            temp_processor = RealDriveProcessor()
            all_files = temp_processor._get_folder_contents_recursive(folder_id, access_token, max_depth)
            image_files = temp_processor._filter_image_files(all_files) if all_files else []
            estimated_images = len(image_files)
            
            # Check if user can process this many images (skip for super users)
            if is_super_user(user_id):
                print(f"🔑 Super user detected, bypassing pricing limits")
            else:
                usage_check = pricing_manager.can_process_images(user_id, estimated_images)
                
                if not usage_check['allowed']:
                    return jsonify({
                        'success': False,
                        'error': 'plan_limit_exceeded',
                        'message': f'Your plan allows {usage_check["limit"]} images. This folder has {estimated_images} images.',
                        'usage_info': usage_check,
                        'upgrade_required': True
                    })
                
                print(f"✅ Plan check passed: {estimated_images} images, {usage_check['remaining']} remaining")
            
        except Exception as e:
            print(f"⚠️ Plan check failed, proceeding anyway: {e}")
        
        # Store current folder_id in session for search isolation
        session['current_folder_id'] = folder_id
        print(f"📁 Set current folder_id in session: {folder_id}")
        
        print(f"🔍 Starting background processing for user: {user_id}")
        print(f"🔑 Using access token: {access_token[:20]}...")
        
        # Start processing in background thread to avoid Railway timeout
        import threading
        try:
            from progress_tracker import start_progress, stop_progress, set_status, set_total, increment, update_folder_info
        except ImportError:
            # Use real progress tracker instead
            from real_progress_tracker import start_progress, stop_progress, set_status, set_total, increment, update_folder_info
        
        def background_process():
            try:
                # Start progress tracking
                start_progress()
                
                # Update folder info with the drive URL
                update_folder_info(folder_path=f"Processing: {drive_url}")
                
                # Use real drive processing with recursive support
                result = process_drive_folder_and_store(
                    user_id=user_id,
                    url=drive_url,
                    access_token=access_token,
                    force_reprocess=force_reprocess,
                    max_depth=max_depth
                )
                
                # Track usage if processing was successful
                if result.get('success') and result.get('processed_count', 0) > 0:
                    try:
                        from pricing_manager import pricing_manager
                        pricing_manager.track_image_usage(user_id, result['processed_count'])
                        print(f"📊 Tracked {result['processed_count']} images for user {user_id}")
                    except Exception as e:
                        print(f"⚠️ Usage tracking failed: {e}")
                
                # Finalize note: completion is handled inside the processor at the real end
                try:
                    update_folder_info(folder_path="Processing Done — Return to main screen")
                except Exception:
                    pass
                print(f"✅ Background processing completed for user {user_id}")
            except Exception as e:
                stop_progress()
                print(f"❌ Background processing failed for user {user_id}: {e}")
        
        # Start background thread
        thread = threading.Thread(target=background_process, daemon=True)
        thread.start()
        
        # Return immediately to avoid timeout
        return jsonify({
            'success': True,
            'message': 'Processing your request...',
            'status': 'processing'
        })
        
    except Exception as e:
        print(f"Error starting drive processing: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/progress', methods=['GET'])
def get_progress():
    """Get current progress status"""
    try:
        try:
            from progress_tracker import get_progress
        except ImportError:
            from real_progress_tracker import get_progress
        
        progress_data = get_progress()
        return jsonify({
            'success': True,
            'progress_data': progress_data,
            'is_active': progress_data.get('is_active', False)
        })
    except Exception as e:
        print(f"❌ Error getting progress: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'progress_data': {
                'overall': 0,
                'current_step': 'Error',
                'folder_info': {'folder_path': 'Error occurred', 'total_files': 0, 'files_found': 0},
                'steps': {},
                'is_active': False
            }
        })

@app.route('/debug_progress', methods=['GET'])
def debug_progress():
    """Debug endpoint to check current progress state"""
    try:
        from progress_tracker import get_progress
    except ImportError:
        from real_progress_tracker import get_progress
    progress_data = get_progress()
    return jsonify({
        'success': True,
        'progress_data': progress_data,
        'is_active': progress_data.get('overall', 0) > 0
    })

@app.route('/stop_processing', methods=['POST'])
def stop_processing():
    """Stop the current processing operation"""
    try:
        try:
            from progress_tracker import stop_tracking, update_folder_info
        except ImportError:
            def stop_tracking(*args, **kwargs): pass
            def update_folder_info(*args, **kwargs): pass
        
        print("🛑 Stop processing requested by user")
        
        # Stop the progress tracking
        stop_tracking()
        
        # Update progress to show stopped state
        update_folder_info(folder_path="Processing stopped by user")
        
        return jsonify({
            'success': True,
            'message': 'Processing stopped successfully'
        })
    except Exception as e:
        print(f"❌ Error stopping processing: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/test_progress', methods=['GET'])
def test_progress():
    """Test endpoint to verify progress bar is working"""
    try:
        from progress_tracker import start_progress, update_folder_info, set_status, set_total, increment, stop_progress
    except ImportError:
        def start_progress(*args, **kwargs): pass
        def update_folder_info(*args, **kwargs): pass
        def set_status(*args, **kwargs): pass
        def set_total(*args, **kwargs): pass
        def increment(*args, **kwargs): pass
        def stop_progress(*args, **kwargs): pass
    import threading
    import time
    
@app.route('/process_drive_shared', methods=['POST'])
def process_drive_shared():
    """Process a Google Drive folder shared with the service account (bot).

    Expected JSON body:
      - drive_url: Google Drive folder URL (the folder must be shared with the bot email)
      - force_reprocess: optional bool
      - max_depth: optional int (1-20)
      - user_id: optional override (falls back to session user_id or 'shared_bot')
    """
    try:
        data = request.get_json() or {}
        drive_url = data.get('drive_url')
        force_reprocess = data.get('force_reprocess', False)
        max_depth = data.get('max_depth', 10)
        user_id = data.get('user_id') or session.get('user_id') or 'shared_bot'

        if not drive_url:
            return jsonify({'success': False, 'error': 'No drive URL provided'}), 400

        try:
            max_depth = int(max_depth)
            if max_depth < 1 or max_depth > 20:
                max_depth = 10
        except Exception:
            max_depth = 10

        # Extract folder ID for session storage
        from google_drive_handler import extract_file_id_from_url
        folder_id = extract_file_id_from_url(drive_url)
        if not folder_id:
            return jsonify({'success': False, 'error': 'Could not extract folder ID from URL'}), 400

        # Mint a service account access token
        access_token = get_service_account_access_token()
        
        # Check user's plan limits before processing
        try:
            from pricing_manager import pricing_manager
            
            # Get estimated file count (quick check)
            from real_drive_processor import RealDriveProcessor
            temp_processor = RealDriveProcessor()
            all_files = temp_processor._get_folder_contents_recursive(folder_id, access_token, max_depth)
            image_files = temp_processor._filter_image_files(all_files) if all_files else []
            estimated_images = len(image_files)
            
            # Check if user can process this many images (skip for super users)
            if is_super_user(user_id):
                print(f"🔑 Super user detected, bypassing pricing limits")
            else:
                usage_check = pricing_manager.can_process_images(user_id, estimated_images)
                
                if not usage_check['allowed']:
                    return jsonify({
                        'success': False,
                        'error': 'plan_limit_exceeded',
                        'message': f'Your {usage_check.get("plan_name", "plan")} allows {usage_check["limit"]} images. This folder has {estimated_images} images. You have already used {usage_check["current_usage"]} images.',
                        'usage_info': usage_check,
                        'upgrade_required': True
                    })
                
                print(f"✅ Plan check passed: {estimated_images} images, {usage_check['remaining']} remaining")
            
        except Exception as e:
            print(f"⚠️ Plan check failed, proceeding anyway: {e}")
            import traceback
            traceback.print_exc()

        # Store current folder_id in session for search isolation
        session['current_folder_id'] = folder_id
        print(f"📁 Set current folder_id in session for bot processing: {folder_id}")

        # Import progress tracking and threading
        import threading
        try:
            from progress_tracker import start_progress, stop_progress, set_status, set_total, increment, update_folder_info
        except ImportError:
            from real_progress_tracker import start_progress, stop_progress, set_status, set_total, increment, update_folder_info
        
        # Background processing to avoid timeout
        def background_process():
            try:
                # Start progress tracking
                start_progress()
                
                # Update folder info with the drive URL
                update_folder_info(folder_path=f"Processing: {drive_url}")
                
                # Use real drive processing with recursive support
                from real_drive_processor import process_drive_folder_and_store
                result = process_drive_folder_and_store(
                    user_id=user_id,
                    url=drive_url,
                    access_token=access_token,
                    force_reprocess=force_reprocess,
                    max_depth=max_depth
                )
                
                # Track photo processing analytics
                if result.get('success') and result.get('processed_count', 0) > 0:
                    try:
                        session_id = session.get('analytics_session_id')
                        if session_id:
                            analytics.track_action(
                                session_id, 
                                user_id, 
                                'photo_processed', 
                                {
                                    'processed_count': result.get('processed_count', 0),
                                    'total_files': result.get('total_files', 0),
                                    'folder_url': drive_url
                                },
                                '/app'
                            )
                    except Exception as e:
                        print(f"⚠️ Analytics tracking failed: {e}")
                
                # Finalize
                try:
                    update_folder_info(folder_path="Processing Done — Return to main screen")
                except Exception:
                    pass
                print(f"✅ Background processing completed for user {user_id}")
            except Exception as e:
                stop_progress()
                print(f"❌ Background processing failed for user {user_id}: {e}")
        
        # Start background thread
        thread = threading.Thread(target=background_process, daemon=True)
        thread.start()
        
        # Return immediately to avoid timeout
        return jsonify({
            'success': True,
            'message': 'Processing your request...',
            'status': 'processing'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

    def test_background():
        try:
            start_progress()
            update_folder_info(folder_path="Test Folder: /test/photos", total_files=5, files_found=5)
            
            # Simulate processing steps
            set_status('download', 'Downloading test files...')
            set_total('download', 5)
            for i in range(5):
                increment('download')
                time.sleep(0.5)
            
            set_status('processing', 'Processing test photos...')
            set_total('processing', 5)
            for i in range(5):
                increment('processing')
                time.sleep(0.5)
            
            set_status('face_detection', 'Detecting faces...')
            set_total('face_detection', 5)
            for i in range(5):
                increment('face_detection')
                time.sleep(0.5)
            
            set_status('embedding', 'Creating embeddings...')
            set_total('embedding', 5)
            for i in range(5):
                increment('embedding')
                time.sleep(0.5)
            
            set_status('storage', 'Saving to database...')
            set_total('storage', 5)
            for i in range(5):
                increment('storage')
                time.sleep(0.5)
            
            stop_progress()
            print("✅ Test progress completed")
        except Exception as e:
            stop_progress()
            print(f"❌ Test progress failed: {e}")
    
    # Start test in background
    thread = threading.Thread(target=test_background, daemon=True)
    thread.start()
    
    return jsonify({'success': True, 'message': 'Test progress started'})

@app.route('/search', methods=['POST'])
def search():
    """Search for person using uploaded selfie - V2 PIPELINE"""
    try:
        # Check if file was uploaded
        if 'selfie' not in request.files:
            return jsonify({'success': False, 'error': 'No selfie file uploaded'})
        
        file = request.files['selfie']
        threshold = float(request.form.get('threshold', 0.50))  # Balanced default
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Invalid file type'})
        
        # Save uploaded file to temp storage
        filename = secure_filename(file.filename)
        unique_filename = f"selfie_{uuid.uuid4().hex}{os.path.splitext(filename)[1]}"
        
        # Ensure upload directory exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file_path = os.path.normpath(os.path.join(UPLOAD_FOLDER, unique_filename))
        
        file.save(file_path)
        
        # Get user ID from session - must be authenticated
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Not authenticated. Please sign in first.'})
        
        user_id = session['user_id']
        
        # Check for shared session - use admin's data if available
        shared_user_id = session.get('shared_user_id')
        shared_folder_id = session.get('shared_folder_id')
        
        # Use shared session data if available for searching
        search_user_id = shared_user_id if shared_user_id else user_id
        
        print(f"🔍 Searching for person with selfie: {file_path}")
        print(f"👤 Logged-in User ID: {user_id}")
        print(f"🔗 Shared User ID: {shared_user_id}")
        print(f"📸 Search User ID (using): {search_user_id}")
        print(f"🎯 Using V2 pipeline for consistent 1024D embeddings")
        print(f"🔧 DEBUG: Starting search process...")
        
        # Use new V2 pipeline
        if real_engine is None:
            return jsonify({'success': False, 'error': 'Facial recognition pipeline not available'})
        
        try:
            # Load image
            import cv2
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity
            
            # Normalize path to handle Windows path separators
            normalized_path = os.path.normpath(file_path)
            print(f"🔧 DEBUG: Normalized file path: {normalized_path}")
            
            image = cv2.imread(normalized_path)
            if image is None:
                print(f"❌ DEBUG: cv2.imread failed for path: {normalized_path}")
                print(f"❌ DEBUG: File exists: {os.path.exists(normalized_path)}")
                return jsonify({'success': False, 'error': 'Could not load image'})
            
            # Process selfie with real face recognition engine (Phase 1)
            print(f"🔧 DEBUG: Processing selfie with universal search...")
            from real_face_recognition_engine import search_with_real_recognition_universal
            
            # Use universal search across admin's photos if shared session, otherwise user's photos
            # If shared session, search only in the specific shared folder
            shared_folder_id = session.get('shared_folder_id')
            search_result = search_with_real_recognition_universal(normalized_path, search_user_id, threshold, shared_folder_id)
            print(f"🔧 DEBUG: Universal search result: {search_result.get('total_matches', 0)} matches found")
            
            # Cache the search results so they appear in /my-photos
            if search_result.get('total_matches', 0) > 0:
                try:
                    from search_cache_manager import cache_manager
                    
                    # Create a folder ID for this search session
                    import time
                    search_session_id = f"search_{int(time.time())}"
                    
                    # Save search results to cache
                    cache_manager.save_search_results(
                        user_id=user_id,
                        folder_id=search_session_id,
                        search_results=search_result,
                        folder_files=[],  # Empty since this is a universal search
                        selfie_embedding=None  # We don't need to store the selfie embedding
                    )
                    print(f"💾 Cached search results for session: {search_session_id}")
                    
                except Exception as e:
                    print(f"⚠️ Failed to cache search results: {e}")
            
            # Clean up temp file
            try:
                os.remove(normalized_path)
            except:
                pass
            
            return jsonify(search_result)
            
            if not result.get('success', False):
                print(f"❌ DEBUG: Face processing failed - result: {result}")
                return jsonify({'success': False, 'error': 'Face processing failed - no face detected in selfie'})
            
            # Get the first embedding (ensure 1024D consistency)
            embeddings = result.get('embeddings', [])
            print(f"🔧 DEBUG: Found {len(embeddings)} embeddings in selfie")
            if not embeddings:
                print(f"❌ DEBUG: No embeddings found in result: {result}")
                return jsonify({'success': False, 'error': 'No face detected in selfie'})
            
            selfie_embedding = embeddings[0]['embedding']
            if isinstance(selfie_embedding, list):
                selfie_embedding = np.array(selfie_embedding)
            print(f"🔧 DEBUG: Selfie embedding shape: {selfie_embedding.shape}, type: {type(selfie_embedding)}")
            
            # Note: Embedding dimension may vary by model config; handle at compare time
            
            # Get faces for this user from Firebase, filtered by current folder for isolation
            current_folder_id = session.get('current_folder_id')
            print(f"🔧 DEBUG: Fetching faces from Firebase for user: {user_id}")
            print(f"📁 DEBUG: Current folder_id from session: {current_folder_id}")
            user_faces = fetch_embeddings_for_user(user_id, current_folder_id)
            filter_msg = f" (folder: {current_folder_id})" if current_folder_id else " (all folders)"
            print(f"🔍 Fetched {len(user_faces)} faces from database for user {user_id}{filter_msg}")
            
            if not user_faces:
                print(f"❌ DEBUG: No faces found in database for user {user_id}")
                print(f"🔧 DEBUG: Checking Firebase connection...")
                try:
                    from firebase_store import get_firebase_stats
                    stats = get_firebase_stats()
                    print(f"🔧 DEBUG: Firebase stats: {stats}")
                except Exception as e:
                    print(f"❌ DEBUG: Firebase stats error: {e}")
                return jsonify({'success': True, 'matches': [], 'message': 'No photos found for this user'})
            
            print(f"🔧 DEBUG: Sample face data: {user_faces[0] if user_faces else 'None'}")
            
            # Calculate similarities using the same method as database processing
            matches = []
            print(f"🔍 Comparing selfie embedding (1024D) with {len(user_faces)} database faces")
            
            for i, face in enumerate(user_faces):
                try:
                    print(f"🔧 DEBUG: Processing face {i+1}/{len(user_faces)}: {face.get('photo_reference', 'unknown')}")
                    
                    # Get embedding from database
                    db_embedding = np.array(face['face_embedding'])
                    print(f"🔧 DEBUG: DB embedding shape: {db_embedding.shape}, type: {type(db_embedding)}")
                    
                    # Align to common dimension and normalize for cosine
                    common_dim = min(len(selfie_embedding), len(db_embedding))
                    se = selfie_embedding[:common_dim]
                    de = db_embedding[:common_dim]
                    print(f"🔧 DEBUG: Common dimension: {common_dim}, selfie: {len(selfie_embedding)}, db: {len(db_embedding)}")
                    
                    # Normalize to unit vectors to compute cosine via dot
                    se_norm = se / (np.linalg.norm(se) + 1e-8)
                    de_norm = de / (np.linalg.norm(de) + 1e-8)
                    similarity = float(np.dot(se_norm, de_norm))
                    
                    print(f"📊 Similarity with {face['photo_reference']}: {similarity:.3f}")
                    
                    if similarity >= threshold:
                        print(f"✅ DEBUG: Match found! Similarity {similarity:.3f} >= threshold {threshold}")
                        
                        # Extract file_id from photo_reference (format: user_id_file_id)
                        photo_reference = face['photo_reference']
                        if '_' in photo_reference:
                            file_id = photo_reference.split('_', 1)[1]
                        else:
                            file_id = photo_reference
                        print(f"🔧 DEBUG: Extracted file_id: {file_id} from photo_reference: {photo_reference}")
                        
                        # Find photo file using the file_id
                        print(f"🔧 DEBUG: Searching for photo with file_id: {file_id}")
                        photo_name = _find_photo_by_file_id(user_id, file_id)
                        print(f"🔧 DEBUG: Photo search result: {photo_name}")
                        
                        if photo_name:
                            matches.append({
                                'person_id': photo_reference,
                                'photo_name': photo_name,
                                'photo_path': photo_name,  # Frontend will construct /photo/{filename}
                                'similarity': float(similarity),
                                'confidence': f"{similarity:.2%}"
                            })
                        print(f"✅ DEBUG: Added match: {photo_name}")
                    else:
                        print(f"❌ DEBUG: No match - similarity {similarity:.3f} < threshold {threshold}")
                        
                except Exception as e:
                    print(f"❌ DEBUG: Error processing face {i+1}: {e}")
                    print(f"❌ DEBUG: Face data: {face}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            # Sort by similarity (highest first)
            matches.sort(key=lambda x: x['similarity'], reverse=True)
            print(f"🔧 DEBUG: Found {len(matches)} total matches above threshold {threshold}")
            
            # Clean up temp file
            try:
                os.remove(normalized_path)
            except:
                pass
            
            # Track search analytics
            session_id = session.get('analytics_session_id')
            if session_id:
                analytics.track_action(
                    session_id, 
                    session.get('user_id', 'anonymous'), 
                    'search_performed', 
                    {
                        'matches_found': len(matches),
                        'threshold_used': threshold,
                        'faces_detected': 1 if matches else 0
                    },
                    '/app'
                )
            
            # Return results directly (no double processing)
            return jsonify({
                'success': True,
                'matches': matches,  # All matches - no artificial limits
                'faces_detected': 1 if matches else 0,  # 1 if we found matches, 0 if no face
                'total_matches': len(matches),
                'threshold_used': threshold,
                'feedback_session_id': '',
                'message': f'Found {len(matches)} matches'
            })
            
        except Exception as e:
            print(f"❌ Error in V2 pipeline search: {e}")
            return jsonify({'success': False, 'error': f'Search failed: {str(e)}'})
        
    except Exception as e:
        print(f"Error in search: {e}")
        return jsonify({'success': False, 'error': str(e)})

def track_downloader_info(admin_user_id, downloader_user_id, filename, source):
    """Track who downloaded photos from shared links"""
    try:
        # Find which session this download is from (shared_session_id is the session ID from the shared link)
        shared_session_id = session.get('shared_session_id') or session.get('shared_folder_id')
        
        if not shared_session_id:
            print(f"⚠️ No shared session found for download tracking")
            return
        
        # Get session manager to find the link
        from shared_session_manager import get_session_manager
        manager = get_session_manager()
        session_data = manager.get_session(shared_session_id) if shared_session_id else None
        
        # Find the admin link for this session
        links_file = 'storage/admin_links.json'
        try:
            with open(links_file, 'r') as f:
                links = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return
        
        # Get folder_id from current session
        folder_id = session.get('shared_folder_id') or session.get('current_folder_id')
        
        # Find link matching this admin and session/folder
        print(f"🔍 Tracking downloader - Admin: {admin_user_id}, Downloader: {downloader_user_id}, Session: {shared_session_id}, Folder: {folder_id}")
        print(f"🔍 Checking {len(links)} links...")
        
        for link in links:
            print(f"🔍 Link: admin={link.get('admin_user_id')}, session_id={link.get('session_id')}, metadata={link.get('metadata', {})}")
            # Try to match by session_id first, then by folder_id from metadata
            link_folder_id = link.get('metadata', {}).get('folder_id') or link.get('metadata', {}).get('drive_url', '').split('/folders/')[-1].split('/')[0] if link.get('metadata', {}).get('drive_url') else None
            
            if (link.get('admin_user_id') == admin_user_id and 
                (link.get('session_id') == shared_session_id or link_folder_id == folder_id)):
                
                print(f"✅ Found matching link!")
                # Add downloader info
                if 'downloaders' not in link:
                    link['downloaders'] = []
                
                # Check if this user already downloaded (to avoid duplicates)
                existing = next((d for d in link['downloaders'] if d['user_id'] == downloader_user_id), None)
                if existing:
                    existing['download_count'] = existing.get('download_count', 0) + 1
                    existing['last_download'] = datetime.now().isoformat()
                else:
                    link['downloaders'].append({
                        'user_id': downloader_user_id,
                        'download_count': 1,
                        'first_download': datetime.now().isoformat(),
                        'last_download': datetime.now().isoformat()
                    })
                
                # Save updated links
                with open(links_file, 'w') as f:
                    json.dump(links, f, indent=2)
                
                print(f"✅ Tracked downloader: {downloader_user_id} for admin: {admin_user_id}")
                break
        else:
            print(f"⚠️ No matching link found for session {shared_session_id}")
        
    except Exception as e:
        print(f"⚠️ Failed to track downloader info: {e}")
        import traceback
        traceback.print_exc()


def _get_shared_watermark_settings():
    shared_session_id = session.get('shared_session_id') or session.get('shared_folder_id')
    if not shared_session_id:
        return None
    try:
        from shared_session_manager import get_session_manager
        manager = get_session_manager()
        session_data = manager.get_session(shared_session_id)
        if not session_data:
            return None
        metadata = session_data.get('metadata', {})
        if not metadata.get('watermark_enabled'):
            return None
        return metadata
    except Exception as e:
        print(f"⚠️ Failed to load watermark settings: {e}")
        return None


def _is_image_file(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in {'.jpg', '.jpeg', '.png', '.webp'}


def _apply_watermark_to_image(image_path, settings):
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    text = (settings.get('watermark_text') or '').strip()
    logo_filename = settings.get('watermark_logo_filename') or ''
    opacity = float(settings.get('watermark_opacity', 70))
    size_pct = float(settings.get('watermark_size', 15))
    margin = int(settings.get('watermark_margin', 12))
    position = settings.get('watermark_position', 'bottom-right')
    offset_x = float(settings.get('watermark_offset_x', 0) or 0)
    offset_y = float(settings.get('watermark_offset_y', 0) or 0)

    if not text and not logo_filename:
        return None, None

    with Image.open(image_path) as base_image:
        image_format = base_image.format or 'JPEG'
        base_image = ImageOps.exif_transpose(base_image)
        image = base_image.convert('RGBA')

    logo = None
    if logo_filename:
        logo_path = os.path.join('static', 'logos', logo_filename)
        if os.path.exists(logo_path):
            logo = Image.open(logo_path).convert('RGBA')
            target_width = max(40, int(image.width * size_pct / 100))
            target_height = int(logo.height * (target_width / logo.width))
            logo = logo.resize((target_width, target_height), Image.LANCZOS)

    font_size = max(14, int(image.width * (size_pct / 100) * 0.25))
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    text_image = None
    if text:
        dummy_draw = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
        bbox = dummy_draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_image = Image.new('RGBA', (text_width + 2, text_height + 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_image)
        draw.text((1, 1), text, font=font, fill=(0, 0, 0, 255))
        draw.text((0, 0), text, font=font, fill=(255, 255, 255, 255))

    gap = max(6, int(image.width * 0.01))
    if logo and text_image:
        watermark_width = max(logo.width, text_image.width)
        watermark_height = logo.height + gap + text_image.height
        watermark = Image.new('RGBA', (watermark_width, watermark_height), (0, 0, 0, 0))
        watermark.paste(logo, ((watermark_width - logo.width) // 2, 0), logo)
        watermark.paste(text_image, ((watermark_width - text_image.width) // 2, logo.height + gap), text_image)
    elif logo:
        watermark = logo
    else:
        watermark = text_image

    if watermark is None:
        return None, None

    if opacity < 100:
        alpha = watermark.split()[3]
        alpha = alpha.point(lambda p: int(p * opacity / 100))
        watermark.putalpha(alpha)

    max_x = max(0, image.width - watermark.width)
    max_y = max(0, image.height - watermark.height)

    if position == 'custom':
        x = int(max_x * (offset_x / 100)) if max_x else 0
        y = int(max_y * (offset_y / 100)) if max_y else 0
    else:
        if position.endswith('left'):
            x = margin
        elif position.endswith('right'):
            x = image.width - watermark.width - margin
        else:
            x = (image.width - watermark.width) // 2

        if position.startswith('top'):
            y = margin
        else:
            y = image.height - watermark.height - margin

    x = max(0, min(x, max_x))
    y = max(0, min(y, max_y))

    image.alpha_composite(watermark, (x, y))

    output = BytesIO()
    ext = os.path.splitext(image_path)[1].lower()
    output_format = 'PNG' if ext == '.png' else 'JPEG'
    mimetype = 'image/png' if output_format == 'PNG' else 'image/jpeg'
    if output_format == 'JPEG':
        image = image.convert('RGB')
    image.save(output, format=output_format, quality=90)
    output.seek(0)
    return output, mimetype


def _send_photo_with_optional_watermark(file_path, filename, base_dir, watermark_settings):
    if not watermark_settings or not _is_image_file(filename):
        return send_from_directory(base_dir, filename)
    try:
        watermarked_file, mimetype = _apply_watermark_to_image(file_path, watermark_settings)
        if watermarked_file is None:
            return send_from_directory(base_dir, filename)
        return send_file(watermarked_file, mimetype=mimetype, download_name=os.path.basename(filename))
    except Exception as e:
        print(f"⚠️ Watermark failed, serving original: {e}")
        return send_from_directory(base_dir, filename)

@app.route('/photo/<path:filename>')
def serve_photo(filename):
    """Serve photos from user's cache folder"""
    try:
        print(f"🔍 Serving photo: {filename}")
        
        # Get user ID from session - must be authenticated
        if 'user_id' not in session:
            print(f"   ❌ Not authenticated")
            return jsonify({'error': 'Not authenticated'}), 401
        
        user_id = session['user_id']
        current_folder_id = session.get('current_folder_id')
        
        # Debug session state
        print(f"   🔧 DEBUG: Full session keys: {list(session.keys())}")
        print(f"   🔧 DEBUG: Session current_folder_id: {current_folder_id}")
        
        # Check for shared session - use admin's data if available
        shared_user_id = session.get('shared_user_id')
        shared_folder_id = session.get('shared_folder_id')
        watermark_settings = _get_shared_watermark_settings()
        
        # Use shared session data if available, otherwise use logged-in user's data
        photo_user_id = shared_user_id if shared_user_id else user_id
        photo_folder_id = shared_folder_id if shared_folder_id else current_folder_id
        
        print(f"   👤 Logged-in User ID: {user_id}")
        print(f"   🔗 Shared User ID: {shared_user_id}")
        print(f"   📸 Photo User ID (using): {photo_user_id}")
        print(f"   📁 Current folder ID: {current_folder_id}")
        print(f"   🔗 Shared folder ID: {shared_folder_id}")
        print(f"   📸 Photo Folder ID (using): {photo_folder_id}")
        
        # First, try uploaded files folder (universal search includes uploaded files)
        upload_folder = os.path.join('storage', 'uploads', photo_user_id)
        upload_file_path = os.path.join(upload_folder, filename)
        print(f"   📁 Checking uploads: {upload_file_path}")
        print(f"   📁 Upload folder exists: {os.path.exists(upload_folder)}")
        print(f"   📁 Upload file exists: {os.path.exists(upload_file_path)}")
        
        if os.path.exists(upload_file_path):
            print(f"   ✅ Found uploaded file: {upload_file_path}")
            # Track download
            try:
                from analytics_tracker import analytics
                session_id = session.get('analytics_session_id', 'default_session')
                analytics.track_action(session_id, photo_user_id, 'photo_downloaded', {
                    'filename': filename,
                    'source': 'upload'
                })
                
                # Track downloader info if from shared link
                if shared_user_id:
                    track_downloader_info(shared_user_id, user_id, filename, 'upload')
            except Exception as e:
                print(f"⚠️ Failed to track download: {e}")
            # For nested paths like "1111/ABN10404.jpg", we need to serve from the base upload folder
            return _send_photo_with_optional_watermark(upload_file_path, filename, upload_folder, watermark_settings)
        
        # Second, try Google Drive cache folder (if folder session exists)
        if photo_folder_id:
            cache_folder = os.path.join('storage', 'downloads', f"{photo_user_id}_{photo_folder_id}")
            cache_file_path = os.path.join(cache_folder, filename)
            print(f"   📁 Checking cache: {cache_file_path}")
            
            if os.path.exists(cache_file_path):
                print(f"   ✅ Found cached file: {cache_file_path}")
                
                # Check if file was modified (to avoid counting cache hits as downloads)
                from flask import request
                response = _send_photo_with_optional_watermark(cache_file_path, filename, cache_folder, watermark_settings)
                
                # Track download only if it's not a 304 (cached response)
                if response.status_code == 200:
                    try:
                        from analytics_tracker import analytics
                        session_id = session.get('analytics_session_id', 'default_session')
                        analytics.track_action(session_id, photo_user_id, 'photo_downloaded', {
                            'filename': filename,
                            'source': 'cache',
                            'folder_id': photo_folder_id
                        })
                        
                        # Track downloader info if from shared link
                        if shared_user_id:
                            track_downloader_info(shared_user_id, user_id, filename, 'cache')
                    except Exception as e:
                        print(f"⚠️ Failed to track download: {e}")
                
                return response
        
        # Fallback: Try to find the file in any cache folder for this user
        if photo_folder_id:
            print(f"   🔍 Has folder session, trying to find file in any cache folder...")
            downloads_dir = os.path.join('storage', 'downloads')
            print(f"   📁 Downloads directory exists: {os.path.exists(downloads_dir)}")
            if os.path.exists(downloads_dir):
                print(f"   📁 Contents of downloads directory: {os.listdir(downloads_dir)}")
                for folder_name in os.listdir(downloads_dir):
                    print(f"   📁 Checking folder: {folder_name}")
                    if folder_name.startswith(f"{photo_user_id}_"):
                        cache_folder = os.path.join(downloads_dir, folder_name)
                        cache_file_path = os.path.join(cache_folder, filename)
                        print(f"   📁 Checking fallback cache: {cache_file_path}")
                        print(f"   📁 File exists: {os.path.exists(cache_file_path)}")
                        if os.path.exists(cache_file_path):
                            print(f"   ✅ Found cached file in fallback: {cache_file_path}")
                            # Track download
                            try:
                                from analytics_tracker import analytics
                                session_id = session.get('analytics_session_id', 'default_session')
                                analytics.track_action(session_id, photo_user_id, 'photo_downloaded', {
                                    'filename': filename,
                                    'source': 'fallback_cache',
                                    'folder_id': folder_name
                                })
                                
                                # Track downloader info if from shared link
                                if shared_user_id:
                                    track_downloader_info(shared_user_id, user_id, filename, 'fallback_cache')
                            except Exception as e:
                                print(f"⚠️ Failed to track download: {e}")
                            return _send_photo_with_optional_watermark(cache_file_path, filename, cache_folder, watermark_settings)
                        else:
                            # List files in the cache folder to see what's available
                            if os.path.exists(cache_folder):
                                files_in_cache = os.listdir(cache_folder)
                                print(f"   📁 Files in cache folder: {files_in_cache[:5]}...")  # Show first 5 files
        else:
            print(f"   ⚠️  No folder session, skipping cache check")
        
        print(f"   ❌ Photo not found in uploads or cache: {filename}")
        print(f"   📁 Files in upload folder:")
        if os.path.exists(upload_folder):
            for root, dirs, files in os.walk(upload_folder):
                for file in files:
                    print(f"       {os.path.relpath(os.path.join(root, file), upload_folder)}")
        
        return jsonify({'error': 'Photo not found'}), 404
        
    except Exception as e:
        print(f"Error serving photo: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/cache_stats')
def cache_stats():
    """Get cache statistics"""
    try:
        # Get user ID from session - must be authenticated
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated. Please sign in first.'}), 401
        
        user_id = session['user_id']
        if get_cache_stats:
            stats = get_cache_stats(user_id)
        else:
            stats = {'message': 'Cache stats not available'}
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/debug_storage')
def debug_storage():
    """Debug route to see what's in storage"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user_id = session['user_id']
        user_storage_path = os.path.join('storage', 'data', user_id)
        
        if not os.path.exists(user_storage_path):
            return jsonify({'error': f'User storage path does not exist: {user_storage_path}'})
        
        storage_info = {
            'user_id': user_id,
            'storage_path': user_storage_path,
            'exists': os.path.exists(user_storage_path),
            'directories': [],
            'total_files': 0
        }
        
        for root, dirs, files in os.walk(user_storage_path):
            rel_path = os.path.relpath(root, user_storage_path)
            if rel_path == '.':
                rel_path = 'root'
            
            storage_info['directories'].append({
                'path': rel_path,
                'file_count': len(files),
                'sample_files': files[:5]  # First 5 files
            })
            storage_info['total_files'] += len(files)
        
        return jsonify(storage_info)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route('/find_file/<filename>')
def find_file(filename):
    """Find a specific file in storage"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user_id = session['user_id']
        user_storage_path = os.path.join('storage', 'data', user_id)
        
        if not os.path.exists(user_storage_path):
            return jsonify({'error': f'User storage path does not exist: {user_storage_path}'})
        
        found_locations = []
        
        for root, dirs, files in os.walk(user_storage_path):
            if filename in files:
                rel_path = os.path.relpath(root, user_storage_path)
                if rel_path == '.':
                    rel_path = 'root'
                found_locations.append({
                    'directory': rel_path,
                    'full_path': os.path.join(root, filename)
                })
        
        return jsonify({
            'filename': filename,
            'user_id': user_id,
            'found': len(found_locations) > 0,
            'locations': found_locations
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# User Feedback Endpoint for Active Learning
@app.route('/feedback', methods=['POST'])
def record_feedback():
    """Record user feedback about search results for active learning"""
    try:
        data = request.get_json()
        
        # Check if user is authenticated
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Not authenticated'})
        
        user_id = session['user_id']
        photo_reference = data.get('photo_reference')
        is_correct = data.get('is_correct', False)
        selfie_path = data.get('selfie_path')
        similarity_score = data.get('similarity_score')
        
        if not photo_reference:
            return jsonify({'success': False, 'error': 'Photo reference required'})
        
        print(f"📝 Recording feedback: {photo_reference} -> {'✅ CORRECT' if is_correct else '❌ INCORRECT'}")
        
        # Record feedback using the active learning system
        success = record_user_feedback(
            user_id=user_id,
            photo_reference=photo_reference,
            is_correct=is_correct,
            selfie_path=selfie_path,
            similarity_score=similarity_score
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Feedback recorded successfully',
                'learning_active': True
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to record feedback'
            })
            
    except Exception as e:
        print(f"❌ Error recording feedback: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Learning Statistics Endpoint
@app.route('/download-feedback', methods=['POST'])
def record_download():
    """Record download as positive feedback for learning"""
    try:
        data = request.get_json()
        
        # Check if user is authenticated
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Not authenticated'})
        
        user_id = session['user_id']
        photo_reference = data.get('photo_reference')
        similarity_score = data.get('similarity_score')
        
        if not photo_reference:
            return jsonify({'success': False, 'error': 'Photo reference required'})
        
        print(f"📥 Recording download feedback: {photo_reference}")
        
        # Record download as positive feedback
        success = record_download_feedback(
            user_id=user_id,
            photo_reference=photo_reference,
            similarity_score=similarity_score
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Download feedback recorded - system is learning!',
                'learning_active': True
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to record download feedback'
            })
            
    except Exception as e:
        print(f"❌ Error recording download feedback: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/learning-stats', methods=['GET'])
def get_learning_stats():
    """Get active learning statistics"""
    try:
        # Check if user is authenticated
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Not authenticated'})
        
        user_id = session['user_id']
        
        # Get learning statistics using the new function
        stats = get_user_learning_stats(user_id)
        
        return jsonify({
            'success': True,
            'stats': stats,
            'user_id': user_id
        })
        
    except Exception as e:
        print(f"❌ Error getting learning stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Folder browsing functionality temporarily disabled to fix Google Drive processing

@app.route('/process_local_legacy', methods=['POST'])
def process_local_photos():
    """Process local photos and generate embeddings"""
    try:
        import tempfile
        import os
        
        # Get files from request
        files = request.files.getlist('photos')
        folder_path = request.form.get('folder_path', 'local_folder')
        
        if not files:
            return jsonify({'success': False, 'message': 'No photos provided'})
        
        processed_count = 0
        errors = []
        
        for file in files:
            if file and allowed_file(file.filename):
                try:
                    # Save file temporarily
                    filename = secure_filename(file.filename)
                    temp_path = os.path.join(tempfile.gettempdir(), filename)
                    file.save(temp_path)
                    
                    # Process with new robust engine V2
                    result = add_to_database(
                        image_path=temp_path,
                        user_id='local_user',
                        photo_reference=filename
                    )
                    
                    if result.get('success', False):
                        processed_count += 1
                        print(f"✅ Processed: {filename}")
                    else:
                        errors.append(f"Failed to process {filename}: {result.get('error', 'Unknown error')}")
                    
                    # Clean up temp file
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                        
                except Exception as e:
                    errors.append(f"Error processing {file.filename}: {str(e)}")
                    print(f"❌ Error processing {file.filename}: {str(e)}")
        
        return jsonify({
            'success': True,
            'processed_count': processed_count,
            'total_files': len(files),
            'errors': errors[:5]  # Limit error messages
        })
        
    except Exception as e:
        print(f"❌ Local processing error: {str(e)}")
        return jsonify({'success': False, 'message': f'Processing error: {str(e)}'})

@app.route('/add_person_v2', methods=['POST'])
def add_person_v2():
    """Add a person to the database using V2 pipeline"""
    try:
        if 'images' not in request.files:
            return jsonify({'success': False, 'error': 'No image files uploaded'})
        
        files = request.files.getlist('images')
        person_id = request.form.get('person_id', '')
        
        if not person_id:
            return jsonify({'success': False, 'error': 'Person ID required'})
        
        if not files or files[0].filename == '':
            return jsonify({'success': False, 'error': 'No files selected'})
        
        user_id = session.get('user_id', 'anonymous')
        
        if real_engine is None:
            return jsonify({'success': False, 'error': 'Facial recognition pipeline not available'})
        
        # Process images
        images = []
        for file in files:
            if file.filename and allowed_file(file.filename):
                # Save temp file
                filename = secure_filename(file.filename)
                unique_filename = f"temp_{uuid.uuid4().hex}{os.path.splitext(filename)[1]}"
                file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                file.save(file_path)
                
                # Load image
                import cv2
                image = cv2.imread(file_path)
                if image is not None:
                    # Resize if too large
                    height, width = image.shape[:2]
                    if width > 1000 or height > 1000:
                        scale = min(1000/width, 1000/height)
                        new_width = int(width * scale)
                        new_height = int(height * scale)
                        image = cv2.resize(image, (new_width, new_height))
                    
                    images.append(image)
                
                # Clean up temp file
                try:
                    os.remove(file_path)
                except:
                    pass
        
        if not images:
            return jsonify({'success': False, 'error': 'No valid images could be processed'})
        
        # Add to database
        result = real_engine.add_person(person_id, images)
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in add_person_v2: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/submit_feedback_v2', methods=['POST'])
def submit_feedback_v2():
    """Submit user feedback for search results"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        result_id = data.get('result_id')
        is_correct = data.get('is_correct', False)
        confidence = data.get('confidence', 3)
        
        if not session_id or result_id is None:
            return jsonify({'success': False, 'error': 'Missing required parameters'})
        
        if real_engine is None:
            return jsonify({'success': False, 'error': 'Facial recognition pipeline not available'})
        
        success = real_engine.submit_feedback(session_id, result_id, is_correct, confidence)
        
        return jsonify({'success': success})
        
    except Exception as e:
        print(f"Error in submit_feedback_v2: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/pipeline_stats_v2', methods=['GET'])
def pipeline_stats_v2():
    """Get pipeline statistics"""
    try:
        if real_engine is None:
            return jsonify({'success': False, 'error': 'Facial recognition pipeline not available'})
        
        stats = real_engine.get_pipeline_statistics()
        return jsonify({'success': True, 'stats': stats})
        
    except Exception as e:
        print(f"Error in pipeline_stats_v2: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ===== VIDEO PROCESSING ROUTES =====
from video_processor import video_processor

@app.route('/video-app')
def video_app():
    """Video upload and processing interface"""
    try:
        return render_template('video-app.html')
    except Exception as e:
        print(f"❌ Error loading video app: {e}")
        return render_template('video-app.html')

@app.route('/my-videos')
def my_videos():
    """List user's processed videos"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect('/')
        
        # Load user's video database
        video_processor.load_video_database(user_id)
        
        # Get user's videos
        videos = video_processor.get_user_videos(user_id)
        
        return render_template('my-videos.html', videos=videos, user_id=user_id)
        
    except Exception as e:
        print(f"❌ Error loading my videos: {e}")
        return render_template('my-videos.html', videos=[], user_id=session.get('user_id', ''))

@app.route('/video-search/<video_id>')
def video_search(video_id):
    """Search within a specific video"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect('/')
        
        # Load user's video database
        video_processor.load_video_database(user_id)
        
        # Get video info
        video_info = video_processor.get_video_info(user_id, video_id)
        
        if not video_info.get('success'):
            return render_template('video-search.html', 
                                 video_info={'error': video_info.get('error')},
                                 user_id=user_id)
        
        return render_template('video-search.html', 
                             video_info=video_info, 
                             user_id=user_id)
        
    except Exception as e:
        print(f"❌ Error loading video search: {e}")
        return render_template('video-search.html', 
                             video_info={'error': str(e)}, 
                             user_id=session.get('user_id', ''))

@app.route('/upload-video', methods=['POST'])
def upload_video():
    """Handle video upload and processing"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'User not authenticated'})
        
        # Check if video file was uploaded
        if 'video' not in request.files:
            return jsonify({'success': False, 'error': 'No video file provided'})
        
        video_file = request.files['video']
        if video_file.filename == '':
            return jsonify({'success': False, 'error': 'No video file selected'})
        
        # Check file extension
        if not any(video_file.filename.lower().endswith(ext) for ext in ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv']):
            return jsonify({'success': False, 'error': 'Unsupported video format. Supported: MP4, AVI, MOV, MKV, WMV, FLV'})
        
        # Create user video directory
        user_video_dir = os.path.join('storage', 'videos', user_id)
        os.makedirs(user_video_dir, exist_ok=True)
        
        # Generate unique video ID
        video_id = f"video_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        video_filename = f"{video_id}_{secure_filename(video_file.filename)}"
        video_path = os.path.join(user_video_dir, video_filename)
        
        # Save video file
        video_file.save(video_path)
        
        # Load user's video database
        video_processor.load_video_database(user_id)
        
        # Process video in background (for now, process immediately)
        result = video_processor.process_video(video_path, user_id, video_id)
        
        if result.get('success'):
            # Save video database
            video_processor.save_video_database(user_id)
            
            return jsonify({
                'success': True,
                'video_id': video_id,
                'video_name': result['video_name'],
                'faces_found': result['faces_found'],
                'processing_time': result['processing_time']
            })
        else:
            return jsonify({'success': False, 'error': result.get('error')})
        
    except Exception as e:
        print(f"❌ Error uploading video: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/search-video', methods=['POST'])
def search_video():
    """Search for faces within a specific video"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'User not authenticated'})
        
        # Get form data
        video_id = request.form.get('video_id')
        if not video_id:
            return jsonify({'success': False, 'error': 'Video ID required'})
        
        # Check if selfie was uploaded
        if 'selfie' not in request.files:
            return jsonify({'success': False, 'error': 'No selfie image provided'})
        
        selfie_file = request.files['selfie']
        if selfie_file.filename == '':
            return jsonify({'success': False, 'error': 'No selfie image selected'})
        
        # Save selfie temporarily
        selfie_filename = f"temp_selfie_{uuid.uuid4().hex[:8]}.jpg"
        selfie_path = os.path.join('storage', 'temp', selfie_filename)
        os.makedirs(os.path.dirname(selfie_path), exist_ok=True)
        selfie_file.save(selfie_path)
        
        # Load user's video database
        video_processor.load_video_database(user_id)
        
        # Search for faces in the specific video
        matches = video_processor.search_video_faces(selfie_path, user_id, video_id)
        
        # Clean up temp file
        try:
            os.remove(selfie_path)
        except:
            pass
        
        return jsonify({
            'success': True,
            'matches': matches,
            'total_matches': len(matches),
            'video_id': video_id
        })
        
    except Exception as e:
        print(f"❌ Error searching video: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/video-progress')
def video_progress():
    """Get video processing progress"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'User not authenticated'})
        
        # Get progress from video processor
        progress = video_processor.progress_tracker.get_status()
        
        return jsonify({'success': True, 'progress': progress})
        
    except Exception as e:
        print(f"❌ Error getting video progress: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/download-video-segment', methods=['POST'])
def download_video_segment():
    """Download a video segment at specific timestamp"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': 'User not authenticated'})
        
        # Get form data
        video_id = request.form.get('video_id')
        timestamp = float(request.form.get('timestamp', 0))
        
        if not video_id:
            return jsonify({'success': False, 'error': 'Video ID required'})
        
        # Find the video file
        user_video_dir = os.path.join('storage', 'videos', user_id)
        video_files = [f for f in os.listdir(user_video_dir) if f.startswith(video_id)]
        
        if not video_files:
            return jsonify({'success': False, 'error': 'Video file not found'})
        
        video_file = video_files[0]
        video_path = os.path.join(user_video_dir, video_file)
        
        # For now, return the full video file
        # In a real implementation, you would extract a segment using ffmpeg
        return send_from_directory(user_video_dir, video_file, as_attachment=True, 
                                 download_name=f"video_segment_{timestamp:.1f}s.mp4")
        
    except Exception as e:
        print(f"❌ Error downloading video segment: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/sitemap.xml')
def sitemap_xml():
    """Serve sitemap.xml file"""
    return send_file('sitemap.xml', mimetype='application/xml')

@app.route('/sitemap-index.xml')
def sitemap_index_xml():
    """Serve sitemap-index.xml file"""
    return send_file('sitemap-index.xml', mimetype='application/xml')

@app.route('/blog-sitemap.xml')
def blog_sitemap_xml():
    """Serve blog-sitemap.xml file"""
    return send_file('blog-sitemap.xml', mimetype='application/xml')

@app.route('/image-sitemap.xml')
def image_sitemap_xml():
    """Serve image-sitemap.xml file"""
    return send_file('image-sitemap.xml', mimetype='application/xml')

@app.route('/s/<short_code>')
def redirect_short_link(short_code):
    """Redirect short links to full URLs"""
    try:
        links = load_short_links()
        
        if short_code not in links:
            return render_template('404.html'), 404
        
        link_data = links[short_code]
        
        # Check if link has expired
        expires_at = datetime.fromisoformat(link_data['expires_at'])
        if datetime.now() > expires_at:
            return render_template('404.html'), 404
        
        # Increment click count
        link_data['click_count'] += 1
        save_short_links(links)
        
        # Also track click in admin links if it exists (direct call, no HTTP request)
        try:
            track_link_click_direct(short_code)
        except Exception as e:
            print(f"⚠️ Failed to track admin link click: {e}")
        
        # Redirect to full URL
        return redirect(link_data['full_url'])
        
    except Exception as e:
        print(f"Error redirecting short link: {e}")
        return render_template('404.html'), 404

@app.route('/robots.txt')
def robots_txt():
    """Serve robots.txt file"""
    return send_from_directory('.', 'robots.txt', mimetype='text/plain')

@app.route('/favicon.ico')
def favicon():
    """Serve favicon"""
    return send_from_directory('.', 'favicon.ico', mimetype='image/x-icon')

@app.route('/api/create-short-link', methods=['POST'])
def create_short_link_api():
    """API endpoint to create short links"""
    try:
        data = request.get_json()
        full_url = data.get('url')
        event_name = data.get('event_name', '')
        expires_days = data.get('expires_days', 30)
        
        if not full_url:
            return jsonify({'success': False, 'error': 'URL is required'}), 400
        
        short_url = create_short_link(full_url, event_name, expires_days)
        
        return jsonify({
            'success': True,
            'short_url': short_url,
            'full_url': full_url,
            'event_name': event_name
        })
        
    except Exception as e:
        print(f"Error creating short link: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/manifest.json')
def manifest():
    """Serve manifest.json file"""
    return send_from_directory('.', 'manifest.json', mimetype='application/json')

@app.route('/sw.js')
def service_worker():
    """Serve service worker file"""
    return send_from_directory('.', 'sw.js', mimetype='application/javascript')

@app.route('/favicon.ico')
def favicon_ico():
    """Serve favicon.ico"""
    return send_from_directory('.', 'favicon.ico', mimetype='image/x-icon')

@app.route('/apple-touch-icon.png')
def apple_touch_icon():
    """Serve Apple touch icon"""
    return send_from_directory('.', 'apple-touch-icon.png', mimetype='image/png')

@app.route('/favicon-32x32.png')
def favicon_32():
    """Serve 32x32 favicon"""
    return send_from_directory('.', 'favicon-32x32.png', mimetype='image/png')

@app.route('/favicon-16x16.png')
def favicon_16():
    """Serve 16x16 favicon"""
    return send_from_directory('.', 'favicon-16x16.png', mimetype='image/png')

@app.route('/test-logo-qr')
def test_logo_qr():
    """Test page for logo upload and QR code generation"""
    return send_from_directory('.', 'test_logo_qr.html', mimetype='text/html')

@app.route('/auto-process')
def auto_process():
    """Auto-process route with beautiful welcome page"""
    drive_url = request.args.get('drive', '')
    event_name = request.args.get('event', '')
    event_date = request.args.get('date', '')
    session_id = request.args.get('session', '')
    company_name = ''
    logo_filename = ''
    
    # If session_id provided, load metadata from Firebase
    if session_id:
        try:
            from shared_session_manager import get_session_manager
            manager = get_session_manager()
            session_data = manager.get_session(session_id)
            
            if session_data:
                metadata = session_data.get('metadata', {})
                event_name = metadata.get('event_name', event_name)
                event_date = metadata.get('event_date', event_date)
                company_name = metadata.get('company_name', '')
                logo_filename = metadata.get('logo_filename', '')
                drive_url = metadata.get('drive_url', drive_url)
                
                # Set shared session variables for search
                session['shared_user_id'] = session_data.get('admin_user_id')
                session['shared_folder_id'] = session_data.get('folder_id')
                session['shared_session_id'] = session_id
                
                print(f"📋 Loaded metadata for session {session_id}:")
                print(f"   Event: {event_name}")
                print(f"   Date: {event_date}")
                print(f"   Company: {company_name}")
                print(f"   Logo: {logo_filename}")
                print(f"   Admin User ID: {session_data.get('admin_user_id')}")
                print(f"   Folder ID: {session_data.get('folder_id')}")
        except Exception as e:
            print(f"❌ Error loading session metadata: {e}")
    
    # Show welcome page with event info
    return render_template('auto_process_welcome.html', 
                          drive_url=drive_url,
                          event_name=event_name,
                          event_date=event_date,
                          session_id=session_id,
                          company_name=company_name,
                          logo_filename=logo_filename)

@app.route('/admin/link-generator')
def admin_link_generator():
    """Admin page to generate shareable auto-process links"""
    # Track page view
    user_id = session.get('user_id', 'anonymous')
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')
    referrer = request.headers.get('Referer', '')
    
    # Start or update session
    session_id = session.get('analytics_session_id')
    if not session_id:
        session_id = analytics.start_session(user_id, ip_address, user_agent, referrer, '/admin/link-generator')
        session['analytics_session_id'] = session_id
    else:
        analytics.track_page_view(session_id, user_id, '/admin/link-generator', 'Admin Link Generator', referrer)
    
    return render_template('admin_link_generator.html')

@app.route('/admin/blog-manager')
@app.route('/blog-manager')
def blog_manager_direct():
    """Direct route to blog manager (no authentication required for testing)"""
    return render_template('blog_manager.html')

@app.route('/api/create-share-session', methods=['POST'])
def create_share_session():
    """Create a shareable session after admin processes photos"""
    try:
        from shared_session_manager import get_session_manager
        
        data = request.get_json()
        print(f"🔍 Create share session data: {data}")
        
        admin_user_id = data.get('admin_user_id')
        folder_id = data.get('folder_id')
        metadata = data.get('metadata', {})
        
        # If no admin_user_id provided, use a default or generate one
        if not admin_user_id:
            import time
            admin_user_id = f"admin_{int(time.time())}"
            print(f"🔍 Generated admin user ID: {admin_user_id}")
        
        print(f"🔍 Admin user ID: {admin_user_id}")
        print(f"🔍 Folder ID: {folder_id}")
        print(f"🔍 Metadata: {metadata}")
        
        manager = get_session_manager()
        print(f"🔍 Manager created: {manager}")
        
        session_id = manager.create_session(admin_user_id, folder_id, metadata)
        print(f"🔍 Session ID result: {session_id}")
        
        if session_id:
            print(f"✅ Session created successfully: {session_id}")
            # Track link creation analytics (optional, don't require auth)
            try:
                analytics_session_id = session.get('analytics_session_id')
                if analytics_session_id:
                    analytics.track_action(
                        analytics_session_id, 
                        admin_user_id, 
                        'link_created', 
                        {
                            'session_id': session_id,
                            'folder_id': folder_id,
                            'metadata': metadata
                        },
                        '/admin_link_generator'
                    )
            except Exception as e:
                print(f"⚠️ Analytics tracking failed: {e}")
            
            return jsonify({'success': True, 'session_id': session_id})
        else:
            print("❌ Session creation returned None - this is the problem!")
            return jsonify({'success': False, 'error': 'Session creation returned None - check server logs'})
    except Exception as e:
        print(f"❌ Error creating share session: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/load-share-session/<session_id>')
def load_share_session_api(session_id):
    """Load shared session data and store in Flask session"""
    try:
        from shared_session_manager import get_session_manager
        
        manager = get_session_manager()
        session_data = manager.get_session(session_id)
        
        if session_data:
            session['shared_folder_id'] = session_data.get('folder_id')
            session['shared_user_id'] = session_data.get('admin_user_id')
            
            print(f"✅ Loaded and stored shared session: {session_id}")
            print(f"   Folder ID: {session_data.get('folder_id')}")
            print(f"   Admin User: {session_data.get('admin_user_id')}")
            
            return jsonify({
                'success': True,
                'folder_id': session_data.get('folder_id'),
                'admin_user_id': session_data.get('admin_user_id'),
                'metadata': session_data.get('metadata', {})
            })
        else:
            return jsonify({'success': False, 'error': 'Session not found'})
    except Exception as e:
        print(f"❌ Error loading share session: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/save-admin-link', methods=['POST'])
def save_admin_link():
    """Save admin generated link for future use"""
    try:
        data = request.get_json()
        admin_user_id = data.get('admin_user_id', 'unknown')
        session_id = data.get('session_id')
        short_code = data.get('short_code')
        full_url = data.get('full_url')
        metadata = data.get('metadata', {})
        
        if not all([session_id, short_code, full_url]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        # Load existing links
        links_file = 'storage/admin_links.json'
        try:
            with open(links_file, 'r') as f:
                links = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            links = []
        
        # Add new link
        link_data = {
            'id': len(links) + 1,
            'admin_user_id': admin_user_id,
            'session_id': session_id,
            'short_code': short_code,
            'full_url': full_url,
            'short_url': f"https://cloudface-ai.com/s/{short_code}",
            'metadata': metadata,
            'created_at': datetime.now().isoformat(),
            'click_count': 0,
            'last_used': None
        }
        
        links.append(link_data)
        
        # Save back to file
        os.makedirs(os.path.dirname(links_file), exist_ok=True)
        with open(links_file, 'w') as f:
            json.dump(links, f, indent=2)
        
        print(f"✅ Saved admin link: {link_data['short_url']}")
        return jsonify({'success': True, 'link_id': link_data['id']})
        
    except Exception as e:
        print(f"❌ Error saving admin link: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get-admin-links')
def get_admin_links():
    """Get all admin generated links for the logged-in user"""
    try:
        # Get logged-in user ID
        user_id = session.get('user_id')
        
        if not user_id:
            # Not logged in - return empty
            return jsonify({'success': True, 'links': []})
        
        links_file = 'storage/admin_links.json'
        try:
            with open(links_file, 'r') as f:
                all_links = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            all_links = []
        
        # Filter links by user_id
        user_links = [link for link in all_links if link.get('admin_user_id') == user_id]
        
        # Sort by creation date (newest first)
        user_links.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return jsonify({'success': True, 'links': user_links})
        
    except Exception as e:
        print(f"❌ Error getting admin links: {e}")
        return jsonify({'success': False, 'error': str(e)})

def track_link_click_direct(short_code):
    """Track link click directly (used internally)"""
    try:
        if not short_code:
            return
        
        # Load existing links
        links_file = 'storage/admin_links.json'
        try:
            with open(links_file, 'r') as f:
                links = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return
        
        # Find and update the link
        for link in links:
            if link.get('short_code') == short_code:
                link['click_count'] = link.get('click_count', 0) + 1
                link['last_used'] = datetime.now().isoformat()
                break
        
        # Save back to file
        with open(links_file, 'w') as f:
            json.dump(links, f, indent=2)
        print(f"✅ Tracked click for link: {short_code}")
        
    except Exception as e:
        print(f"⚠️ Failed to track link click: {e}")

@app.route('/api/track-link-click', methods=['POST'])
def track_link_click():
    """Track when a short link is clicked"""
    try:
        data = request.get_json()
        short_code = data.get('short_code')
        
        if not short_code:
            return jsonify({'success': False, 'error': 'Missing short_code'})
        
        track_link_click_direct(short_code)
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"❌ Error tracking link click: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/store-return-url', methods=['POST'])
def store_return_url():
    """Store return URL in session for after authentication"""
    try:
        data = request.get_json()
        return_url = data.get('return_url', '/app')
        session['return_after_auth'] = return_url
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/upload-logo', methods=['POST'])
def upload_logo():
    """Upload company logo and return filename"""
    try:
        if 'logo' not in request.files:
            return jsonify({'success': False, 'error': 'No logo file provided'})
        
        logo_file = request.files['logo']
        if logo_file.filename == '':
            return jsonify({'success': False, 'error': 'No logo file selected'})
        
        # Validate file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
        if not ('.' in logo_file.filename and 
                logo_file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            return jsonify({'success': False, 'error': 'Invalid file type. Only PNG, JPG, JPEG, and GIF are allowed.'})
        
        # Create logos directory if it doesn't exist
        logos_dir = os.path.join('static', 'logos')
        os.makedirs(logos_dir, exist_ok=True)
        
        # Generate unique filename
        import uuid
        file_extension = logo_file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{file_extension}"
        filepath = os.path.join(logos_dir, filename)
        
        # Save file
        logo_file.save(filepath)
        
        return jsonify({'success': True, 'filename': filename})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Analytics API Endpoints
@app.route('/api/analytics/overall')
def get_overall_analytics():
    """Get overall analytics data"""
    try:
        days = int(request.args.get('days', 30))
        data = analytics.get_overall_analytics(days)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/analytics/user/<user_id>')
def get_user_analytics(user_id):
    """Get analytics for a specific user"""
    try:
        days = int(request.args.get('days', 30))
        data = analytics.get_user_analytics(user_id, days)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/analytics/users')
def get_all_users_analytics():
    """Get analytics for all users (admin view)"""
    try:
        days = int(request.args.get('days', 30))
        
        # Get all unique users from sessions
        sessions = analytics._load_data(analytics.sessions_file)
        cutoff_date = datetime.now() - timedelta(days=days)
        
        recent_sessions = [s for s in sessions if 
                          datetime.fromisoformat(s['start_time']) >= cutoff_date]
        
        unique_users = list(set(s['user_id'] for s in recent_sessions))
        
        # Get analytics for each user
        users_data = []
        for user_id in unique_users[:50]:  # Limit to 50 users for performance
            user_data = analytics.get_user_analytics(user_id, days)
            users_data.append(user_data)
        
        return jsonify({'success': True, 'data': users_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/analytics/realtime')
def get_realtime_analytics():
    """Get real-time analytics data"""
    try:
        data = analytics.get_realtime_stats()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/analytics')
def admin_analytics():
    """Show analytics dashboard"""
    return render_template('admin_analytics.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    """Show the admin dashboard for sharing metrics"""
    return render_template('admin_dashboard.html')

@app.route('/api/admin/dashboard')
def admin_dashboard_data():
    """Get admin dashboard data"""
    try:
        from analytics_tracker import analytics
        from pricing_manager import pricing_manager
        
        # Get user profile and plan info
        user_id = session.get('user_id', 'guest')
        user_plan = pricing_manager.get_user_plan(user_id)
        
        # Check if user is super user and override plan
        if is_super_user(user_id):
            profile = {
                'user_id': user_id,
                'plan_name': 'Enterprise',
                'plan_type': 'enterprise',
                'images_used': user_plan.get('usage', {}).get('images_processed', 0),
                'images_limit': 9999999,  # Unlimited
                'images_percentage': 0,
                'images_remaining': 9999999,
                'videos_used': user_plan.get('usage', {}).get('videos_processed', 0),
                'videos_limit': 9999999,  # Unlimited
                'videos_percentage': 0,
                'videos_remaining': 9999999,
            }
        else:
            # Calculate usage percentages for regular users
            images_used = user_plan.get('usage', {}).get('images_processed', 0)
            images_limit = user_plan.get('limits', {}).get('images', 0)
            images_percentage = int((images_used / images_limit * 100)) if images_limit > 0 else 0
            
            videos_used = user_plan.get('usage', {}).get('videos_processed', 0)
            videos_limit = user_plan.get('limits', {}).get('videos', 0)
            videos_percentage = int((videos_used / videos_limit * 100)) if videos_limit > 0 else 0
            
            profile = {
                'user_id': user_id,
                'plan_name': user_plan.get('plan_name', 'Starter'),
                'plan_type': user_plan.get('plan_type', 'free'),
                'images_used': images_used,
                'images_limit': images_limit,
                'images_percentage': min(images_percentage, 100),
                'images_remaining': max(images_limit - images_used, 0),
                'videos_used': videos_used,
                'videos_limit': videos_limit,
                'videos_percentage': min(videos_percentage, 100),
                'videos_remaining': max(videos_limit - videos_used, 0),
            }
        
        # Add common fields to profile
        profile['expires_at'] = user_plan.get('expires_at')
        profile['features'] = user_plan.get('limits', {}).get('features', []) if not is_super_user(user_id) else ['Unlimited Processing']
        
        # Get user-specific analytics (filtered by user_id)
        user_analytics = analytics.get_user_analytics(user_id)
        
        # Calculate sharing metrics (use profile data for accurate photo count)
        stats = {
            'photos_shared': profile.get('images_used', 0),  # Use actual usage from profile, not analytics
            'links_created': user_analytics.get('links_created', 0),
            'total_downloads': user_analytics.get('photos_downloaded', 0),
            'total_views': user_analytics.get('total_page_views', 0),
            'photos_this_week': user_analytics.get('photos_this_week', 0),
            'links_this_week': user_analytics.get('links_this_week', 0),
            'downloads_this_week': user_analytics.get('downloads_this_week', 0),
            'views_this_week': user_analytics.get('views_this_week', 0)
        }
        
        # Get real chart data
        chart_data = analytics.get_chart_data(30, user_id=user_id)
        charts = {
            'activity_labels': chart_data['labels'],
            'photos_data': chart_data['photos_data'],
            'links_data': chart_data['links_data'],
            'sources_labels': chart_data['sources_labels'],
            'sources_data': chart_data['sources_data']
        }
        
        # Get real recent activity
        recent_activity = analytics.get_recent_activity(10)
        
        return jsonify({
            'success': True,
            'profile': profile,
            'stats': stats,
            'charts': charts,
            'recent_activity': recent_activity
        })
        
    except Exception as e:
        print(f"Error getting admin dashboard data: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'profile': {
                'plan_name': 'Starter',
                'plan_type': 'free',
                'images_used': 0,
                'images_limit': 500,
                'images_percentage': 0,
                'images_remaining': 500,
                'videos_used': 0,
                'videos_limit': 0,
                'videos_percentage': 0,
                'videos_remaining': 0
            },
            'stats': {
                'photos_shared': 0,
                'links_created': 0,
                'total_downloads': 0,
                'total_views': 0,
                'photos_this_week': 0,
                'links_this_week': 0,
                'downloads_this_week': 0,
                'views_this_week': 0
            },
            'charts': {
                'activity_labels': [],
                'photos_data': [],
                'links_data': [],
                'sources_labels': [],
                'sources_data': []
            },
            'recent_activity': []
        })

@app.route('/api/analytics/track-share', methods=['POST'])
def track_share():
    """Track share events"""
    try:
        data = request.get_json()
        share_type = data.get('share_type')
        share_data = data.get('share_data', {})
        
        session_id = session.get('analytics_session_id')
        if session_id:
            analytics.track_share(
                session_id,
                session.get('user_id', 'anonymous'),
                share_type,
                share_data,
                recipient_count=1
            )
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    # Get port from environment variable (for Railway) or use default
    port = int(os.environ.get('PORT', 8550))
    
    print("🚀 Starting Facetak Web Server with OAuth...")
    print(f"🔑 OAuth Client ID: {GOOGLE_CLIENT_ID[:20]}...")
    print(f"🌐 Redirect URI: {GOOGLE_REDIRECT_URI}")
    print(f"📱 Open http://localhost:{port} in your browser")
    print("⚠️  Auto-reload disabled to prevent connection issues during processing")
    app.run(debug=False, host='0.0.0.0', port=port)
 