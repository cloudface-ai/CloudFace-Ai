#!/usr/bin/env python3
"""
Blog Manager - WordPress-like Blog Posting Tool
Handles CRUD operations for blog posts
"""

import os
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for, current_app
from werkzeug.utils import secure_filename
from functools import wraps

# Create Blueprint for blog manager
blog_manager_bp = Blueprint('blog_manager', __name__)

# Storage paths
BLOG_STORAGE_DIR = 'storage/blog_posts'
BLOG_METADATA_FILE = 'storage/blog_posts_metadata.json'
BLOG_TEMPLATES_DIR = 'templates/blog_posts'
BLOG_DIR = 'templates/blog'

# Ensure directories exist
os.makedirs(BLOG_STORAGE_DIR, exist_ok=True)
os.makedirs(BLOG_TEMPLATES_DIR, exist_ok=True)
os.makedirs(BLOG_DIR, exist_ok=True)

# Simple password protection
BLOG_MANAGER_PASSWORD = os.getenv('BLOG_MANAGER_PASSWORD', '@dmiN123#')

def require_auth(f):
    """Simple password check decorator - uses URL parameter as fallback if session fails"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check password from URL parameter first (fallback), then session
        url_password = request.args.get('pwd') or request.args.get('password')
        session_password = session.get('blog_manager_password')
        provided_password = url_password or session_password
        
        print(f"🔒 Auth check for {request.path}")
        print(f"🔒 URL password: {bool(url_password)}, Session password: {bool(session_password)}")
        print(f"🔒 Session keys: {list(session.keys())}")
        
        if provided_password == BLOG_MANAGER_PASSWORD:
            # Save to session for future requests
            session['blog_manager_password'] = BLOG_MANAGER_PASSWORD
            session.permanent = True
            session.modified = True
            print(f"✅ Password verified, allowing access")
            return f(*args, **kwargs)
        
        # If JSON request, return error
        if request.is_json:
            return jsonify({'success': False, 'error': 'Password required'}), 401
        
        # Otherwise show password prompt
        print(f"❌ Password not found, showing password prompt")
        return render_template('blog_manager_password.html')
    return decorated_function

def get_blog_metadata() -> List[Dict]:
    """Load blog posts metadata"""
    try:
        if os.path.exists(BLOG_METADATA_FILE):
            with open(BLOG_METADATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Error loading blog metadata: {e}")
    return []

def save_blog_metadata(metadata: List[Dict]):
    """Save blog posts metadata"""
    try:
        with open(BLOG_METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Error saving blog metadata: {e}")
        return False

def generate_slug(title: str) -> str:
    """Generate URL-friendly slug from title"""
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug)
    slug = slug.strip('-')
    return slug

def generate_blog_template(metadata: Dict, content: str) -> str:
    """Generate HTML template for blog post matching existing blog post structure"""
    title = metadata.get('title', 'Untitled')
    description = metadata.get('meta_description', '')
    keywords = metadata.get('meta_keywords', '')
    slug = metadata.get('slug', generate_slug(title))
    og_image = metadata.get('og_image', 'https://cloudface-ai.com/static/Cloudface-ai-logo.png')
    canonical_url = f"https://cloudface-ai.com/blog/{slug}"
    published_date = metadata.get('published_date', datetime.now().strftime('%B %d, %Y'))
    read_time = metadata.get('read_time', '5')
    author = metadata.get('author', 'CloudFace AI Team')
    
    # Read the existing blog post template to extract CSS and structure
    template_file = 'templates/blog_posts/google_drive_face_search_guide.html'
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            existing_template = f.read()
        
        # Extract the CSS (from <style> tag)
        css_start = existing_template.find('<style>')
        css_end = existing_template.find('</style>')
        css_content = existing_template[css_start + 7:css_end] if css_start != -1 and css_end != -1 else ''
        
        # Extract footer HTML
        footer_start = existing_template.find('<!-- Footer -->')
        footer_end = existing_template.find('</footer>') + 9
        footer_html = existing_template[footer_start:footer_end] if footer_start != -1 and footer_end != -1 else ''
    except:
        # Fallback CSS if template file not found
        css_content = '''*{margin:0;padding:0;box-sizing:border-box}:root{--primary:#1a73e8;--primary-light:#4285f4;--primary-dark:#0d47a1;--accent:#ea4335;--success:#34a853;--warning:#fbbc04;--bg:#fafafa;--surface:#fff;--text-primary:#202124;--text-secondary:#5f6368;--text-tertiary:#9aa0a6;--border:#dadce0;--shadow:0 1px 3px rgba(0,0,0,.12),0 1px 2px rgba(0,0,0,.24);--radius:16px;--radius-sm:8px;--transition:none}body{font-family:'Google Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text-primary);font-size:16px;line-height:1.5;-webkit-font-smoothing:antialiased}.header{background:var(--surface);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100;backdrop-filter:blur(20px);background:rgba(255,255,255,.95)}.header-top{background:var(--primary);color:#fff;padding:4px 0;font-size:12px;text-align:center}.header-main{padding:1px 0}.header-content{max-width:1200px;margin:0 auto;padding:0 1rem;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem}.logo{font-size:18px;font-weight:500;color:var(--primary);text-decoration:none;display:flex;align-items:center;gap:4px}.nav-toggle{background:none;border:none;color:var(--text-primary);cursor:pointer;padding:4px;border-radius:var(--radius-sm);transition:var(--transition);display:none;align-items:center;justify-content:center}.nav-menu{display:flex;align-items:center;gap:1rem;list-style:none}.nav-menu a{color:var(--text-primary);text-decoration:none;font-weight:500;transition:var(--transition);padding:.5rem 1rem;border-radius:var(--radius-sm)}.nav-menu a:hover{color:var(--primary);background:var(--bg)}.nav-menu a.active{color:var(--primary);background:var(--bg)}.cta-button{background:var(--primary);color:#fff;padding:.75rem 1.5rem;border-radius:var(--radius);text-decoration:none;font-weight:600;transition:all .1s ease}.cta-button:hover{background:var(--primary-dark);transform:translateY(-2px);box-shadow:var(--shadow-hover)}.container{max-width:1200px;margin:0 auto;padding:2rem 1rem}.blog-header{text-align:center;margin-bottom:3rem;padding:2rem 0}.blog-header h1{font-size:2.5rem;font-weight:400;color:var(--text-primary);margin-bottom:1rem;line-height:1.2}.blog-header .meta{color:var(--text-secondary);font-size:0.9rem;margin-bottom:1rem}.blog-header .excerpt{color:var(--text-secondary);font-size:1.1rem;line-height:1.6;max-width:800px;margin:0 auto}.blog-body{line-height:1.8;color:var(--text-primary)}.blog-body h2{font-size:1.75rem;font-weight:600;margin-top:2.5rem;margin-bottom:1rem;color:var(--text-primary)}.blog-body h3{font-size:1.5rem;font-weight:600;margin-top:2rem;margin-bottom:0.75rem;color:var(--text-primary)}.blog-body h4{font-size:1.25rem;font-weight:600;margin-top:1.5rem;margin-bottom:0.5rem;color:var(--text-primary)}.blog-body p{margin-bottom:1rem;line-height:1.8}.blog-body ul,.blog-body ol{margin:1rem 0;padding-left:2rem}.blog-body li{margin-bottom:0.5rem;line-height:1.6}.blog-body a{color:var(--primary);text-decoration:none}.blog-body a:hover{text-decoration:underline}.blog-body img{max-width:100%;height:auto;border-radius:var(--radius);margin:1.5rem 0}.blog-body blockquote{border-left:4px solid var(--primary);padding-left:1.5rem;margin:1.5rem 0;color:var(--text-secondary);font-style:italic}.blog-body code{background:var(--bg);padding:0.2rem 0.4rem;border-radius:4px;font-family:'Courier New',monospace;font-size:0.9em}.blog-body pre{background:var(--bg);padding:1rem;border-radius:var(--radius);overflow-x:auto;margin:1rem 0}.highlight-box,.cta-box{background:rgba(26,115,232,.05);border:1px solid var(--primary);border-radius:var(--radius);padding:1.5rem;margin:2rem 0}.faq-section{margin:2rem 0}.faq-section h3{color:var(--primary);margin-top:1.5rem}.footer{background:var(--surface);border-top:1px solid var(--border);margin-top:4rem}.footer-content{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:2rem;margin-bottom:2rem}.footer-section h3{color:var(--text-primary);margin-bottom:1rem;font-size:18px;font-weight:600}.footer-section p{color:#2d3748;margin-bottom:0.5rem;line-height:1.6}.footer-section ul{list-style:none}.footer-section ul li{margin-bottom:0.5rem}.footer-section ul li a{color:#2d3748;text-decoration:none;transition:var(--transition)}.footer-section ul li a:hover{color:var(--primary)}.social-links{display:flex;gap:1rem;margin-top:1rem}.social-link{display:flex;align-items:center;justify-content:center;width:40px;height:40px;background:var(--bg);border-radius:50%;color:var(--text-secondary);transition:var(--transition)}.social-link:hover{background:var(--primary);color:white;transform:translateY(-2px)}.social-link svg{width:20px;height:20px;fill:currentColor}.footer-bottom{border-top:1px solid var(--border);padding:1.5rem 0}.footer-bottom-content{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem}.footer-left p{color:var(--text-tertiary);font-size:14px;margin:0 0 0.25rem 0;line-height:1.4}.footer-left p .heart{color:#e74c3c;font-weight:bold}.footer-links{display:flex;gap:1.5rem;flex-wrap:wrap}.footer-links a{color:#2d3748;text-decoration:none;font-size:14px;transition:var(--transition)}.footer-links a:hover{color:var(--primary)}@media (max-width:768px){.nav-toggle{display:flex}.nav-menu{display:none;position:absolute;top:100%;left:0;right:0;background:var(--surface);border-top:1px solid var(--border);box-shadow:var(--shadow);flex-direction:column;padding:1rem 0}.nav-menu.active{display:flex}.blog-header h1{font-size:2rem}.footer-bottom-content{flex-direction:column;text-align:center}}'''
        footer_html = '''<!-- Footer -->
    <footer class="footer">
        <div class="container">
            <div class="footer-content">
                <div class="footer-section">
                    <h3>About CloudFace AI</h3>
                    <p>We create AI-powered face recognition technology that helps you discover and organize photos across your digital life. Our focus is on privacy, performance, and beautiful user experience.</p>
                    <div class="social-links">
                         <a href="#" class="social-link" aria-label="Follow @whoisvinodkumar on Twitter">
                            <svg viewBox="0 0 24 24">
                                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                            </svg>
                        </a>
                         <a href="#" class="social-link" aria-label="Follow @whoisvinodkumar on Instagram">
                            <svg viewBox="0 0 24 24">
                                <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                            </svg>
                        </a>
                         <a href="#" class="social-link" aria-label="Subscribe to @whoisvinodkumar on YouTube">
                            <svg viewBox="0 0 24 24">
                                <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                            </svg>
                        </a>
                         <a href="#" class="social-link" aria-label="Connect with @whoisvinodkumar on LinkedIn">
                            <svg viewBox="0 0 24 24">
                                <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                            </svg>
                        </a>
                    </div>
                </div>
                
                <div class="footer-section">
                    <h3>Quick Links</h3>
                    <ul>
                        <li><a href="/">Home</a></li>
                        <li><a href="#features">Features</a></li>
                        <li><a href="/how-it-works">How It Works</a></li>
                        <li><a href="#privacy">Privacy</a></li>
                        <li><a href="/#features">Pricing</a></li>
                        <li><a href="/blog">Blog</a></li>
                        <li><a href="/app">Try App</a></li>
                        <li><a href="/contact">Contact Us</a></li>
                    </ul>
                </div>
                
                <div class="footer-section">
                     <h3>Services</h3>
                     <ul>
                         <li><a href="/#features">Face Recognition</a></li>
                         <li><a href="/#features">Photo Organization</a></li>
                         <li><a href="/#features">Google Drive Integration</a></li>
                         <li><a href="/#features">AI Processing</a></li>
                         <li><a href="/contact">Support</a></li>
                     </ul>
                 </div>
                
                <div class="footer-section">
                    <h3>Contact Info</h3>
                    <p>
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" style="display: inline; margin-right: 8px;">
                            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
                        </svg>
                        E-2/22, Block E2, <br>DLF Phase 1, Sector 26A,<br>Gurugram, Haryana<br>122003
                    </p>
                    <p>
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" style="display: inline; margin-right: 8px;">
                            <path d="M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z"/>
                        </svg>
                        +91 9718 686 723
                    </p>
                    <p>
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" style="display: inline; margin-right: 8px;">
                            <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>
                        </svg>
                        support@cloudface-ai.com
                    </p>
                    <p>
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" style="display: inline; margin-right: 8px;">
                            <path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8z"/>
                            <path d="M12.5 7H11v6l5.25 3.15.75-1.23-4.5-2.67z"/>
                        </svg>
                        Mon-Fri: 9AM-6PM
                    </p>
                </div>
            </div>
            
            <div class="footer-bottom">
                <div class="footer-bottom-content">
                    <div class="footer-left">
                        <p>&copy; 2025 cloudface-ai.com. All rights reserved.</p>
                        <p>Made with <span class="heart">❤</span> in Gurugram, India</p>
                    </div>
                    <div class="footer-links">
                        <a href="/privacy">Privacy Policy</a>
                        <a href="/terms">Terms & Conditions</a>
                        <a href="/pricing">Pricing</a>
                        <a href="/refund">Refund Policy</a>
                    </div>
                </div>
            </div>
        </div>
    </footer>'''
    
    template = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | CloudFace AI</title>
    <meta name="description" content="{description}">
    <meta name="keywords" content="{keywords}">
    
    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="article">
    <meta property="og:url" content="{canonical_url}">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{description}">
    <meta property="og:image" content="{og_image}">

    <!-- Twitter -->
    <meta property="twitter:card" content="summary_large_image">
    <meta property="twitter:url" content="{canonical_url}">
    <meta property="twitter:title" content="{title}">
    <meta property="twitter:description" content="{description}">
    <meta property="twitter:image" content="{og_image}">

    <link rel="canonical" href="{canonical_url}">
    <link rel="stylesheet" href="/static/styles.css">
    <link rel="manifest" href="/manifest.json">
    
    <style>
{css_content}
    </style>
    
    <!-- Structured Data -->
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "{title}",
        "description": "{description}",
        "image": "{og_image}",
        "author": {{
            "@type": "Organization",
            "name": "CloudFace AI"
        }},
        "publisher": {{
            "@type": "Organization",
            "name": "CloudFace AI",
            "logo": {{
                "@type": "ImageObject",
                "url": "https://cloudface-ai.com/static/Cloudface-ai-logo.png"
            }}
        }},
        "datePublished": "{published_date}",
        "dateModified": "{metadata.get('updated_at', datetime.now().isoformat())}"
    }}
    </script>
</head>
<body>
    <!-- Header -->
    <header class="header">
        <div class="header-top">
            <span>Find any photo in your cloud with AI—instantly</span>
        </div>
        <div class="header-main">
            <div class="container">
                <div class="header-content">
                    <a href="/" class="logo">
                        <img src="/static/Cloudface-ai-logo.png" alt="Cloudface AI" style="height:1.3em; width:auto; vertical-align:middle;">
                        <span style="margin-left:.4em;">Cloudface AI</span>
                    </a>
                    <button class="nav-toggle" onclick="toggleNav()" aria-label="Toggle navigation menu">
                        <svg viewBox="0 0 24 24">
                            <path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/>
                        </svg>
                    </button>
                    <nav class="nav-menu" id="navMenu">
                        <a href="/" class="active">Home</a>
                        <a href="/my-photos" id="myPhotosBtn" style="display: none;">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 6px; vertical-align: middle;">
                                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                                <circle cx="8.5" cy="8.5" r="1.5"/>
                                <polyline points="21,15 16,10 5,21"/>
                            </svg>
                            My Photos
                        </a>
                        <a href="/about">About</a>
                        <a href="/video-app">Video Search</a>
                        <a href="/blog">Blog</a>
                        <a href="/pricing">Pricing</a>
                        <a href="/how-it-works">How It Works</a>
                        <a href="/#features">Features</a>
                        <a href="/app" class="cta-button">Try App</a>
                    </nav>
                </div>
            </div>
        </div>
    </header>

    <!-- Blog Post Content -->
    <main class="container">
        <div class="blog-header">
            <div class="meta">{published_date} • {read_time} min read</div>
            <h1>{title}</h1>
            <p class="excerpt">{description}</p>
        </div>

        <div class="blog-body">
{content}
        </div>
    </main>

{footer_html}

    <script>
        function toggleNav() {{
            const navMenu = document.getElementById('navMenu');
            navMenu.classList.toggle('active');
        }}

        document.addEventListener('click', function(event) {{
            const navMenu = document.getElementById('navMenu');
            const navToggle = document.querySelector('.nav-toggle');
            
            if (!navMenu.contains(event.target) && !navToggle.contains(event.target)) {{
                navMenu.classList.remove('active');
            }}
        }});
    </script>
</body>
</html>'''
    return template


@blog_manager_bp.route('/api/blog/upload-image', methods=['POST'])
@require_auth
def upload_blog_image():
    """Upload and resize blog images"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400

        file_obj = request.files['file']
        if not file_obj or not file_obj.filename:
            return jsonify({'success': False, 'error': 'Empty file'}), 400

        filename = secure_filename(file_obj.filename)
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        allowed = {'jpg', 'jpeg', 'png', 'webp'}
        if ext not in allowed:
            return jsonify({'success': False, 'error': 'Invalid file type'}), 400

        from PIL import Image
        import time

        upload_dir = os.path.join('static', 'uploads', 'blog')
        os.makedirs(upload_dir, exist_ok=True)

        base_name = f"blog_{int(time.time())}_{filename}"
        file_path = os.path.join(upload_dir, base_name)

        image = Image.open(file_obj.stream)

        max_width = 1200
        if image.width > max_width:
            new_height = int(image.height * (max_width / image.width))
            image = image.resize((max_width, new_height), Image.LANCZOS)

        save_kwargs = {}
        if ext in {'jpg', 'jpeg'}:
            if image.mode in {'RGBA', 'P'}:
                image = image.convert('RGB')
            save_kwargs = {'format': 'JPEG', 'quality': 85, 'optimize': True}
        elif ext == 'png':
            save_kwargs = {'format': 'PNG', 'optimize': True}
        elif ext == 'webp':
            save_kwargs = {'format': 'WEBP', 'quality': 80}

        image.save(file_path, **save_kwargs)

        return jsonify({
            'success': True,
            'url': f"/static/uploads/blog/{base_name}"
        })
    except Exception as e:
        print(f"❌ Error uploading blog image: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blog_manager_bp.route('/admin/blog-manager/check-password', methods=['POST'])
def check_password():
    """Check password and redirect with URL parameter (session fallback)"""
    password = request.form.get('password', '') or (request.get_json() or {}).get('password', '')
    
    print(f"🔐 Password check: provided={bool(password)}, correct={password == BLOG_MANAGER_PASSWORD}")
    
    if password == BLOG_MANAGER_PASSWORD:
        # Try to set session
        session['blog_manager_password'] = BLOG_MANAGER_PASSWORD
        session.permanent = True
        session.modified = True
        print(f"✅ Password correct, session set: {session.get('blog_manager_password')}")
        print(f"🔐 Session keys: {list(session.keys())}")
        
        if request.is_json:
            return jsonify({'success': True, 'message': 'Access granted', 'redirect': '/admin/blog-manager?pwd=' + BLOG_MANAGER_PASSWORD})
        
        # Redirect with password in URL as fallback (in case session doesn't work)
        redirect_url = f'/admin/blog-manager?pwd={BLOG_MANAGER_PASSWORD}'
        print(f"🔗 Redirecting to {redirect_url}")
        return redirect(redirect_url)
    else:
        print(f"❌ Incorrect password")
        if request.is_json:
            return jsonify({'success': False, 'error': 'Incorrect password'}), 401
        return render_template('blog_manager_password.html', error='Incorrect password')

@blog_manager_bp.route('/admin/blog-manager')
@require_auth
def blog_manager_page():
    """Blog Manager Admin Page - Protected by password"""
    return render_template('blog_manager.html')

@blog_manager_bp.route('/api/blog/posts', methods=['GET'])
@require_auth
def get_all_posts():
    """Get all blog posts"""
    try:
        metadata = get_blog_metadata()
        # Sort by date (newest first)
        metadata.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return jsonify({'success': True, 'posts': metadata})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@blog_manager_bp.route('/api/blog/posts/<post_id>', methods=['GET'])
@require_auth
def get_post(post_id):
    """Get a specific blog post"""
    try:
        metadata = get_blog_metadata()
        post = next((p for p in metadata if p.get('id') == post_id), None)
        
        if not post:
            return jsonify({'success': False, 'error': 'Post not found'}), 404
        
        # Load content
        content_file = os.path.join(BLOG_STORAGE_DIR, f"{post_id}.html")
        content = ''
        if os.path.exists(content_file):
            with open(content_file, 'r', encoding='utf-8') as f:
                content = f.read()
        
        post['content'] = content
        return jsonify({'success': True, 'post': post})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@blog_manager_bp.route('/api/blog/posts', methods=['POST'])
@require_auth
def create_post():
    """Create a new blog post"""
    try:
        data = request.get_json()
        
        # Generate ID and slug
        post_id = f"post_{int(datetime.now().timestamp())}"
        title = data.get('title', 'Untitled')
        slug = data.get('slug') or generate_slug(title)
        
        # Check if slug already exists
        metadata = get_blog_metadata()
        existing_slug = any(p.get('slug') == slug for p in metadata)
        if existing_slug:
            slug = f"{slug}-{int(datetime.now().timestamp())}"
        
        # Create metadata
        post_metadata = {
            'id': post_id,
            'title': title,
            'slug': slug,
            'content': data.get('content', ''),
            'status': data.get('status', 'draft'),  # draft, published
            'author': data.get('author', 'CloudFace AI Team'),
            'meta_description': data.get('meta_description', ''),
            'meta_keywords': data.get('meta_keywords', ''),
            'badge': data.get('badge', '📝 BLOG'),
            'thumbnail_image': data.get('thumbnail_image', ''),
            'og_image': data.get('og_image', 'https://cloudface-ai.com/static/Cloudface-ai-logo.png'),
            'read_time': data.get('read_time', '5'),
            'published_date': data.get('published_date', datetime.now().strftime('%B %d, %Y')),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # Save content
        content_file = os.path.join(BLOG_STORAGE_DIR, f"{post_id}.html")
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write(data.get('content', ''))
        
        # If published, generate template
        if post_metadata['status'] == 'published':
            template_content = post_metadata['content']
            template_html = generate_blog_template(post_metadata, template_content)
            
            # Save to templates directory
            template_file = os.path.join(BLOG_TEMPLATES_DIR, f"{slug}.html")
            with open(template_file, 'w', encoding='utf-8') as f:
                f.write(template_html)
        
        # Add to metadata
        metadata.append(post_metadata)
        save_blog_metadata(metadata)
        
        return jsonify({'success': True, 'post': post_metadata})
    except Exception as e:
        print(f"❌ Error creating post: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@blog_manager_bp.route('/api/blog/posts/<post_id>', methods=['PUT'])
@require_auth
def update_post(post_id):
    """Update an existing blog post"""
    try:
        data = request.get_json()
        metadata = get_blog_metadata()
        
        post_index = next((i for i, p in enumerate(metadata) if p.get('id') == post_id), None)
        if post_index is None:
            return jsonify({'success': False, 'error': 'Post not found'}), 404
        
        post = metadata[post_index]
        
        # Update fields
        if 'title' in data:
            post['title'] = data['title']
            if 'slug' not in data:
                post['slug'] = generate_slug(data['title'])
        
        if 'slug' in data:
            # Check if new slug conflicts
            new_slug = data['slug']
            existing_slug = any(p.get('slug') == new_slug and p.get('id') != post_id for p in metadata)
            if not existing_slug:
                post['slug'] = new_slug
        
        if 'content' in data:
            post['content'] = data['content']
            # Save content
            content_file = os.path.join(BLOG_STORAGE_DIR, f"{post_id}.html")
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(data['content'])
        
        if 'status' in data:
            post['status'] = data['status']
        
        if 'meta_description' in data:
            post['meta_description'] = data['meta_description']
        
        if 'meta_keywords' in data:
            post['meta_keywords'] = data['meta_keywords']

        if 'badge' in data:
            post['badge'] = data['badge']

        if 'thumbnail_image' in data:
            post['thumbnail_image'] = data['thumbnail_image']
        
        if 'og_image' in data:
            post['og_image'] = data['og_image']
        
        if 'author' in data:
            post['author'] = data['author']
        
        if 'read_time' in data:
            post['read_time'] = data['read_time']
        
        if 'published_date' in data:
            post['published_date'] = data['published_date']
        
        post['updated_at'] = datetime.now().isoformat()
        
        # If published, regenerate template
        if post['status'] == 'published':
            template_content = post['content']
            template_html = generate_blog_template(post, template_content)
            
            # Save to templates directory
            template_file = os.path.join(BLOG_TEMPLATES_DIR, f"{post['slug']}.html")
            with open(template_file, 'w', encoding='utf-8') as f:
                f.write(template_html)
        else:
            # If unpublished, remove template
            template_file = os.path.join(BLOG_TEMPLATES_DIR, f"{post['slug']}.html")
            if os.path.exists(template_file):
                os.remove(template_file)
        
        # Save metadata
        save_blog_metadata(metadata)
        
        return jsonify({'success': True, 'post': post})
    except Exception as e:
        print(f"❌ Error updating post: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@blog_manager_bp.route('/api/blog/posts/<post_id>', methods=['DELETE'])
@require_auth
def delete_post(post_id):
    """Delete a blog post"""
    try:
        metadata = get_blog_metadata()
        post = next((p for p in metadata if p.get('id') == post_id), None)
        
        if not post:
            return jsonify({'success': False, 'error': 'Post not found'}), 404
        
        # Remove from metadata
        metadata = [p for p in metadata if p.get('id') != post_id]
        save_blog_metadata(metadata)
        
        # Delete content file
        content_file = os.path.join(BLOG_STORAGE_DIR, f"{post_id}.html")
        if os.path.exists(content_file):
            os.remove(content_file)
        
        # Delete template file if exists
        template_file = os.path.join(BLOG_TEMPLATES_DIR, f"{post['slug']}.html")
        if os.path.exists(template_file):
            os.remove(template_file)
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"❌ Error deleting post: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blog_manager_bp.route('/api/blog/posts/<post_id>/publish', methods=['POST'])
@require_auth
def publish_post(post_id):
    """Publish a blog post"""
    try:
        metadata = get_blog_metadata()
        post = next((p for p in metadata if p.get('id') == post_id), None)
        
        if not post:
            return jsonify({'success': False, 'error': 'Post not found'}), 404
        
        post['status'] = 'published'
        post['published_date'] = datetime.now().strftime('%B %d, %Y')
        post['updated_at'] = datetime.now().isoformat()
        
        # Generate and save template
        content_file = os.path.join(BLOG_STORAGE_DIR, f"{post_id}.html")
        content = ''
        if os.path.exists(content_file):
            with open(content_file, 'r', encoding='utf-8') as f:
                content = f.read()
        
        template_html = generate_blog_template(post, content)
        template_file = os.path.join(BLOG_TEMPLATES_DIR, f"{post['slug']}.html")
        with open(template_file, 'w', encoding='utf-8') as f:
            f.write(template_html)
        
        save_blog_metadata(metadata)
        
        return jsonify({'success': True, 'post': post})
    except Exception as e:
        print(f"❌ Error publishing post: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@blog_manager_bp.route('/api/blog/posts/<post_id>/unpublish', methods=['POST'])
@require_auth
def unpublish_post(post_id):
    """Unpublish a blog post"""
    try:
        metadata = get_blog_metadata()
        post = next((p for p in metadata if p.get('id') == post_id), None)
        
        if not post:
            return jsonify({'success': False, 'error': 'Post not found'}), 404
        
        post['status'] = 'draft'
        post['updated_at'] = datetime.now().isoformat()
        
        # Remove template file
        template_file = os.path.join(BLOG_TEMPLATES_DIR, f"{post['slug']}.html")
        if os.path.exists(template_file):
            os.remove(template_file)
        
        save_blog_metadata(metadata)
        
        return jsonify({'success': True, 'post': post})
    except Exception as e:
        print(f"❌ Error unpublishing post: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

