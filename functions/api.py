from serverless_wsgi import handle_request
import sys
import os

# Add the root directory to sys.path to import app.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app

def handler(event, context):
    return handle_request(app, event, context)