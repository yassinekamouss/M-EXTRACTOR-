import io
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from extractor import parse_metadata

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/extract', methods=['POST'])
def extract():
    """Extract metadata using in-memory byte streams (io.BytesIO)"""
    if 'image' not in request.files:
        return jsonify({"status": "error", "message": "No image file provided."}), 400
    
    file = request.files['image']
    
    if file.filename == '':
        return jsonify({"status": "error", "message": "Empty file uploaded."}), 400

    # Ensure secure filename - though we do not save to disk per rules
    secure_filename(file.filename)

    try:
        # Load entirely into memory based on constraints
        file_bytes = file.read()
        if not file_bytes:
            return jsonify({"status": "error", "message": "Uploaded file is empty."}), 400

        metadata = parse_metadata(file_bytes)
        
        return jsonify({
            "status": "success",
            "message": "Metadata extracted successfully.",
            "data": metadata
        }), 200

    except ValueError as ve:
        return jsonify({"status": "error", "message": str(ve)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Internal processing error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)