from flask import Flask, request, jsonify
from ultralytics import YOLO
import mysql.connector
from mysql.connector import Error
from PIL import Image
import io
import requests
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/process_image": {"origins": "*"}, r"/api/add_product": {"origins": "*"}, r"/api/search_products": {"origins": "*"}})

# Database configuration (to be updated with PlanetScale)
db_config = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "122005"),
    "database": os.getenv("DB_NAME", "recsys"),
    "ssl_ca": os.getenv("DB_SSL_CA", None)
}

def get_db_connection():
    try:
        return mysql.connector.connect(**db_config)
    except Error as e:
        print(f"Error connecting to database: {e}")
        raise

# Microsoft Graph Config
TENANT_ID = os.getenv("AZ_TENANT_ID")
CLIENT_ID = os.getenv("AZ_CLIENT_ID")
CLIENT_SECRET = os.getenv("AZ_CLIENT_SECRET")
DRIVE_ITEM_ID = os.getenv("ONEDRIVE_FILE_ID")
TABLE_NAME = os.getenv("EXCEL_TABLE_NAME", "ProductsTable")

def get_graph_token():
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    payload = {
        "grant_type": "client_credentials",
        "scope": "https://graph.microsoft.com/.default",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    r = requests.post(url, data=payload)
    r.raise_for_status()
    return r.json().get("access_token")

def add_row_to_excel(product_name, category):
    token = get_graph_token()
    endpoint = (
        f"https://graph.microsoft.com/v1.0/me/drive/items/{DRIVE_ITEM_ID}"
        f"/workbook/tables/{TABLE_NAME}/rows/add"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {"values": [[product_name, category]]}
    response = requests.post(endpoint, headers=headers, json=data)
    response.raise_for_status()
    return response.json()

@app.route('/api', methods=['GET'])
def index():
    return jsonify({
        "message": "Welcome to the RecSys API. Use POST /api/process_image to analyze an image, POST /api/add_product to add a product, or GET /api/search_products for autocomplete search."
    })

@app.route('/api/add_product', methods=['POST', 'OPTIONS'])
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

@app.route('/api/search_products', methods=['GET', 'OPTIONS'])
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

try:
    model = YOLO("models/best.pt")
except Exception as e:
    print(f"Error loading YOLO model: {e}")
    exit(1)

@app.route('/api/process_image', methods=['POST', 'OPTIONS'])
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
                "status_message": status_message,
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
else:
    application = app