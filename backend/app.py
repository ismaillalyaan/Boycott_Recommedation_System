from flask import Flask, request, jsonify, send_from_directory
from ultralytics import YOLO
import mysql.connector
from mysql.connector import Error
from PIL import Image
import io
import requests
import os
from flask_cors import CORS

# Setup Flask app
app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), '..', 'static'))
CORS(app, resources={r"/*": {"origins": "*"}})

# DB connection info (hardcoded)
db_config = {
    "host": "HOST",
    "user": "USER",
    "password": "PASS",
    "database": "DB"
}

def get_db_connection():
    try:
        print("Attempting DB connection...")
        conn = mysql.connector.connect(**db_config)
        print("DB connection successful")
        return conn
    except Error as e:
        print(f"Error connecting to DB: {e}")
        raise



# Serve UI from static/
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

# API Endpoints
@app.route('/add_product', methods=['POST', 'OPTIONS'])
def add_product():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json(force=True)
        name = data.get('name')
        is_boycotted = data.get('is_boycotted', False)
        if not name:
            return jsonify({"error": "Product 'name' is required"}), 400
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO products (name, is_boycotted) VALUES (%s, %s)",
            (name, is_boycotted)
        )
        conn.commit()
        return jsonify({"message": "Product added successfully"}), 201
    except Error as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"Invalid request: {str(e)}"}), 400
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

@app.route('/search_products', methods=['GET', 'OPTIONS'])
def search_products():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        query = request.args.get('query', '')
        if not query:
            return jsonify({"products": []}), 200
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT product_id, name, is_boycotted FROM products WHERE name LIKE %s LIMIT 10",
            (f"%{query}%",)
        )
        products = cursor.fetchall()
        results = [
            {
                "product_id": p['product_id'],
                "name": p['name'],
                "is_boycotted": p['is_boycotted']
            } for p in products
        ]
        return jsonify({"products": results})
    except Error as e:
        return jsonify({"error": f"Database query failed: {str(e)}"}), 500
    finally:
        cursor.close()
        conn.close()

# Load YOLO model
try:
    model_path = os.path.join(os.getcwd(), 'models', 'best.pt')
    model = YOLO(model_path)
except Exception as e:
    print(f"Error loading YOLO model: {e}")
    exit(1)

@app.route('/process_image', methods=['POST', 'OPTIONS'])
def process_image():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if 'image' in request.files:
            file = request.files['image']
            try:
                img = Image.open(io.BytesIO(file.read())).convert('RGB')
                results = model(img)
            except Exception as e:
                return jsonify({"error": f"Image processing failed: {str(e)}"}), 500

            if not results[0].boxes:
                return jsonify({"message": "No product detected", "status_message": "غير معروف"}), 200

            pred = results[0].boxes.cls[0].item()
            class_name = model.names[int(pred)]
        else:
            data = request.get_json()
            if not data or 'name' not in data:
                return jsonify({"error": "Product name required for search"}), 400
            class_name = data['name']

        cursor.execute(
            "SELECT product_id, name, is_boycotted FROM products WHERE name = %s",
            (class_name,)
        )
        product = cursor.fetchone()
        if product:
            status_message = "هذا المنتج يخضع للمقاطعة" if product['is_boycotted'] else "هذا المنتج غير مخضوع للمقاطعة"
            alternatives = []
            if product['is_boycotted']:
                cursor.execute("""
                    SELECT p.name, s.cosine_score
                    FROM similarities s
                    JOIN products p ON s.alt_id = p.product_id
                    WHERE s.boycott_id = %s
                    ORDER BY s.cosine_score DESC
                    LIMIT 5
                """, (product['product_id'],))
                alternatives = cursor.fetchall()
            return jsonify({
                "detected_product": class_name,
                "is_boycotted": product['is_boycotted'],
                "alternatives": alternatives
            })
        else:
            return jsonify({
                "detected_product": class_name,
                "status_message": "المنتج غير موجود في قاعدة البيانات",
                "alternatives": []
            })
    except Error as e:
        return jsonify({"error": f"Database query failed: {str(e)}"}), 500
    finally:
        cursor.close()
        conn.close()

# Start the server
if __name__ == '__main__':
    #app.run(debug=True, host='0.0.0.0', port=8000)
    port = int(os.environ.get("PORT", 8000))  # Azure sets PORT env var
    app.run(host='0.0.0.0', port=port)
