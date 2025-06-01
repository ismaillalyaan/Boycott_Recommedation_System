import json
import mysql.connector
from mysql.connector import Error
from ultralytics import YOLO
from PIL import Image
import io
import os

# Database configuration
db_config = {
    "host": "boycott-mysql.mysql.database.azure.com",
    "user": "mysqladmin",
    "password": "nourrecsys1_",
    "database": "recsys",
    # Uncomment and adjust if SSL is required
    # "ssl_ca": "/tmp/cert.pem"
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        if conn.is_connected():
            print("Successfully connected to Azure MySQL database")
            return conn
        else:
            print("Connection failed: Unable to establish connection")
            return None
    except Error as e:
        print(f"Error connecting to database: {e}")
        return None

# Load YOLO model (loaded per invocation in serverless environment)
model_path = "/tmp/models/best.pt"  # Adjust path for Netlify Functions
if not os.path.exists(model_path):
    raise FileNotFoundError(f"YOLO model not found at {model_path}")
model = YOLO(model_path)

def handler(event, context):
    if event['httpMethod'] == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': 'https://badylk.netlify.app'}
        }
    try:
        conn = get_db_connection()
        if not conn:
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': 'https://badylk.netlify.app'},
                'body': json.dumps({"error": "Database connection failed"})
            }
        cursor = conn.cursor(dictionary=True)

        if event['httpMethod'] == 'POST':
            # Note: File uploads are complex in Netlify Functions; this is a simplification
            if 'image' in event['headers'].get('Content-Type', '').lower():
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': 'https://badylk.netlify.app'},
                    'body': json.dumps({"error": "Image upload not fully supported; use name parameter instead"})
                }
            else:
                data = json.loads(event['body'])
                if not data or 'name' not in data:
                    return {
                        'statusCode': 400,
                        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': 'https://badylk.netlify.app'},
                        'body': json.dumps({"error": "Product name required for search"})
                    }
                class_name = data['name']

        cursor.execute(
            "SELECT product_id, name, is_boycotted, category FROM products WHERE name = %s",
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
                    WHERE s.boycott_id = %s AND p.category = %s
                    ORDER BY s.cosine_score DESC
                    LIMIT 5
                """, (product['product_id'], product['category']))
                alternatives = cursor.fetchall()
            cursor.close()
            conn.close()
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': 'https://badylk.netlify.app'},
                'body': json.dumps({
                    "detected_product": class_name,
                    "is_boycotted": product['is_boycotted'],
                    "status_message": status_message,
                    "alternatives": alternatives
                })
            }
        else:
            cursor.close()
            conn.close()
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': 'https://badylk.netlify.app'},
                'body': json.dumps({
                    "detected_product": class_name,
                    "status_message": "المنتج غير موجود في قاعدة البيانات",
                    "alternatives": []
                })
            }
    except Error as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': 'https://badylk.netlify.app'},
            'body': json.dumps({"error": f"Database query failed: {str(e)}"})
        }