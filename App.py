from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import os
from werkzeug.utils import secure_filename
import pandas as pd
import json
import networkx as nx
from pyvis.network import Network
import threading
import time
import atexit
from pdf_processor import process_pdf
from file_handler import handle_file_upload #Import the upload logic

app = Flask(__name__)
# Allow multiple domains
allowed_origins = [
    "https://pdf-to-fraud-net-frontend.vercel.app",
    "http://localhost:5173",
]

CORS(app, origins=allowed_origins)

# Folder paths for uploaded and processed files
UPLOAD_FOLDER = 'uploads'  # Existing folder for uploaded files
PROCESSED_FOLDER = 'processed'  # Existing folder for processed files

# Ensure the folders exist (no need to create them since they already exist)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER


def cleanup_files():
    try:
        # Delete all files in the uploads folder
        for file in os.listdir(app.config['UPLOAD_FOLDER']):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file)
            if os.path.isfile(file_path):
                os.remove(file_path)

        # Delete all files in the processed folder
        for file in os.listdir(app.config['PROCESSED_FOLDER']):
            file_path = os.path.join(app.config['PROCESSED_FOLDER'], file)
            if os.path.isfile(file_path):
                os.remove(file_path)

        print("Files cleaned up successfully.")
    except Exception as e:
        print(f"Error during file cleanup: {str(e)}")

# Periodic file cleanup function
def periodic_cleanup():
    while True:
        time.sleep(3600)  # Run cleanup every hour
        cleanup_files()

# Register the cleanup function to run on server shutdown
atexit.register(cleanup_files)

# Start the cleanup thread when the app starts
cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
cleanup_thread.start()


@app.route('/')
def index():
    return '🚀 Flask server is running!'

# Register the upload route using the imported function
app.route('/upload', methods=['POST'])(handle_file_upload(app, process_pdf))

@app.route('/download-excel', methods=['GET'])
def download_excel():
    filename = request.args.get('filename')
    if not filename:
        return jsonify({'error': 'Filename not provided'}), 400

    excel_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
    if os.path.exists(excel_path):
        return send_file(excel_path, as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    return jsonify({'error': 'Excel file not found'}), 404


@app.route('/download-json', methods=['GET'])
def download_json():
    filename = request.args.get('filename')
    if not filename:
        return jsonify({'error': 'Filename not provided'}), 400

    json_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
    if os.path.exists(json_path):
        return send_file(json_path, as_attachment=True, mimetype='application/json')
    return jsonify({'error': 'JSON file not found'}), 404


@app.route('/download-graph', methods=['GET'])
def download_graph():
    filename = request.args.get('filename')
    if not filename:
        return jsonify({'error': 'Filename not provided'}), 400

    graph_html_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
    if os.path.exists(graph_html_path):
        return send_file(graph_html_path, as_attachment=False, mimetype='text/html')  # Set `as_attachment=False` to open in browser
    return jsonify({'error': 'Graph HTML file not found'}), 404

if __name__ == '__main__':
    # Create upload and processed folders if they don't exist
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    if not os.path.exists(app.config['PROCESSED_FOLDER']):
        os.makedirs(app.config['PROCESSED_FOLDER'])

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
