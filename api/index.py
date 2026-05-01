"""
Vercel Serverless Function Entry Point
This file is required for Vercel to properly route requests to the Flask app.
"""

import sys
import os

# Add parent directory to path so we can import app.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the Flask application
from app import app

# Vercel expects this WSGI application
# The function name 'handler' or the app itself can be used
export = app
