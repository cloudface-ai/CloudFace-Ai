#!/usr/bin/env python3
"""
Real Progress Tracker for Facetak V2
Tracks actual progress of Google Drive processing
"""

import time
import threading
from typing import Dict, Any

class RealProgressTracker:
    def __init__(self):
        self.progress_data = {
            'overall': 0,
            'current_step': 'Initializing...',
            'folder_info': {
                'folder_path': 'Initializing...',
                'total_files': 0,
                'files_found': 0
            },
            'steps': {
                'download': {'progress': 0, 'status': 'Waiting...', 'total_files': 0, 'processed_files': 0, 'icon': '📥', 'name': 'Downloading from Google Drive'},
                'processing': {'progress': 0, 'status': 'Waiting...', 'total_files': 0, 'processed_files': 0, 'icon': '🧠', 'name': 'Processing Photos'},
                'database': {'progress': 0, 'status': 'Waiting...', 'total_files': 0, 'processed_files': 0, 'icon': '💾', 'name': 'Saving to Database'}
            },
            'estimated_time': 'Calculating...',
            'start_time': None,
            'errors': [],
            'warnings': []
        }
        self.lock = threading.Lock()
        self.start_time = None
        self.is_active = False
    
    def start_progress(self):
        """Start progress tracking"""
        with self.lock:
            self.is_active = True
            self.start_time = time.time()
            self.progress_data['overall'] = 0
            self.progress_data['current_step'] = 'Starting...'
            self.progress_data['folder_info']['folder_path'] = 'Starting...'
            self.progress_data['steps'] = {
                'download': {'progress': 0, 'status': 'Preparing...', 'total_files': 0, 'processed_files': 0, 'icon': '📥', 'name': 'Downloading from Google Drive'},
                'processing': {'progress': 0, 'status': 'Waiting...', 'total_files': 0, 'processed_files': 0, 'icon': '🧠', 'name': 'Processing Photos'},
                'database': {'progress': 0, 'status': 'Waiting...', 'total_files': 0, 'processed_files': 0, 'icon': '💾', 'name': 'Saving to Database'}
            }
            self.progress_data['errors'] = []
            self.progress_data['warnings'] = []
            self.progress_data['start_time'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    
    def stop_progress(self):
        """Stop progress tracking"""
        with self.lock:
            self.is_active = False
    
    def update_folder_info(self, folder_path: str, total_files: int = 0, files_found: int = 0):
        """Update folder information"""
        with self.lock:
            self.progress_data['folder_info']['folder_path'] = folder_path
            self.progress_data['folder_info']['total_files'] = total_files
            self.progress_data['folder_info']['files_found'] = files_found
    
    def set_total(self, total_files: int):
        """Set total number of files to process"""
        with self.lock:
            self.progress_data['folder_info']['total_files'] = total_files
            self.progress_data['steps']['download']['total_files'] = total_files
            self.progress_data['steps']['processing']['total_files'] = total_files
            self.progress_data['steps']['database']['total_files'] = total_files
    
    def increment(self, step: str = 'processing'):
        """Increment progress for a specific step"""
        with self.lock:
            if step in self.progress_data['steps']:
                self.progress_data['steps'][step]['processed_files'] += 1
                total = self.progress_data['steps'][step]['total_files']
                if total > 0:
                    progress = int((self.progress_data['steps'][step]['processed_files'] / total) * 100)
                    self.progress_data['steps'][step]['progress'] = progress
                    self.progress_data['steps'][step]['status'] = f'Processing... {progress}%'
                    
                    # Update current step
                    if progress > 0 and progress < 100:
                        self.progress_data['current_step'] = self.progress_data['steps'][step]['name']
                
                # Update overall progress
                self._update_overall_progress()
    
    def set_status(self, step: str, status: str):
        """Set status for a specific step"""
        with self.lock:
            if step in self.progress_data['steps']:
                self.progress_data['steps'][step]['status'] = status
                # Update current step if this step is active
                if 'Processing' in status or 'Downloading' in status or 'Saving' in status:
                    self.progress_data['current_step'] = self.progress_data['steps'][step]['name']
    
    def set_progress(self, step: str, progress: int):
        """Set progress percentage for a specific step"""
        with self.lock:
            if step in self.progress_data['steps']:
                self.progress_data['steps'][step]['progress'] = progress
                if progress == 100:
                    self.progress_data['steps'][step]['status'] = 'Completed'
                elif progress > 0:
                    self.progress_data['steps'][step]['status'] = f'Processing... {progress}%'
                
                # Update current step if this step is active
                if progress > 0 and progress < 100:
                    self.progress_data['current_step'] = self.progress_data['steps'][step]['name']
                
                # Update overall progress
                self._update_overall_progress()
    
    def add_error(self, error: str):
        """Add an error message"""
        with self.lock:
            self.progress_data['errors'].append(error)
    
    def add_warning(self, warning: str):
        """Add a warning message"""
        with self.lock:
            self.progress_data['warnings'].append(warning)
    
    def _update_overall_progress(self):
        """Update overall progress based on step progress (fixed for real engine)"""
        steps = self.progress_data['steps']
        
        # Simple average of all active steps (more reliable)
        active_steps = []
        for step_name, step_data in steps.items():
            if step_data['progress'] > 0 or step_data['status'] != 'Waiting...':
                active_steps.append(step_data['progress'])
        
        if active_steps:
            total_progress = sum(active_steps) / len(active_steps)
        else:
            total_progress = 0
        
        self.progress_data['overall'] = int(total_progress)
        
        # Update estimated time
        if self.start_time and self.progress_data['overall'] > 0:
            elapsed = time.time() - self.start_time
            if self.progress_data['overall'] < 100:
                remaining = (elapsed / self.progress_data['overall']) * (100 - self.progress_data['overall'])
                self.progress_data['estimated_time'] = f'About {int(remaining)} seconds remaining'
            else:
                self.progress_data['estimated_time'] = 'Processing complete!'
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress data"""
        with self.lock:
            progress_copy = self.progress_data.copy()
            progress_copy['is_active'] = self.is_active
            return progress_copy
    
    def complete_all_steps(self):
        """Mark all steps as complete with search-ready message"""
        with self.lock:
            self.progress_data['overall'] = 100
            self.progress_data['current_step'] = '✅ Processing done, now search your photos!'
            for step in self.progress_data['steps']:
                self.progress_data['steps'][step]['progress'] = 100
                self.progress_data['steps'][step]['status'] = 'Complete!'
            self.progress_data['estimated_time'] = 'Ready for search!'
            self.progress_data['completion_message'] = 'Processing complete! You can now search for faces in your photos.'
            self.progress_data['search_ready'] = True
            self.is_active = False

# Global progress tracker instance
progress_tracker = RealProgressTracker()

# Export functions for compatibility
def start_progress():
    progress_tracker.start_progress()

def stop_progress():
    progress_tracker.stop_progress()

def update_folder_info(folder_path: str, total_files: int = 0, files_found: int = 0):
    progress_tracker.update_folder_info(folder_path, total_files, files_found)

def set_total(total_files: int):
    progress_tracker.set_total(total_files)

def increment(step: str = 'processing'):
    progress_tracker.increment(step)

def set_status(step: str, status: str):
    progress_tracker.set_status(step, status)

def set_progress(step: str, progress: int):
    progress_tracker.set_progress(step, progress)

def add_error(error: str):
    progress_tracker.add_error(error)

def add_warning(warning: str):
    progress_tracker.add_warning(warning)

def get_progress():
    return progress_tracker.get_progress()

def complete_all_steps():
    progress_tracker.complete_all_steps()
