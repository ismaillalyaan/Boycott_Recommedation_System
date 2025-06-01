import json
import mysql.connector
from mysql.connector import Error

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

def handler(event, context):
    if event['httpMethod'] == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': 'https://badylk.netlify.app'}
        }
    if event['httpMethod'] == 'GET':
        try:
            query = event['queryStringParameters'].get('query', '') if event['queryStringParameters'] else ''
            if not query:
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': 'https://badylk.netlify.app'},
                    'body': json.dumps({"products": []})
                }
            conn = get_db_connection()
            if not conn:
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': 'https://badylk.netlify.app'},
                    'body': json.dumps({"error": "Database connection failed"})
                }
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
            cursor.close()
            conn.close()
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': 'https://badylk.netlify.app'},
                'body': json.dumps({"products": results})
            }
        except Error as e:
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': 'https://badylk.netlify.app'},
                'body': json.dumps({"error": f"Database query failed: {str(e)}"})
            }