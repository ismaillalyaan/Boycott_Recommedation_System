import json
import mysql.connector
from mysql.connector import Error
import requests
import os

# Database configuration
db_config = {
    "host": "boycott-mysql.mysql.database.azure.com",
    "user": "mysqladmin",
    "password": "nourrecsys1_",
    "database": "recsys",
    # Uncomment and adjust if SSL is required
    # "ssl_ca": "/tmp/cert.pem"  # Adjust path for Netlify Functions
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
    try:
        r = requests.post(url, data=payload)
        r.raise_for_status()
        return r.json().get("access_token")
    except Exception as e:
        print(f"Error getting Graph token: {e}")
        return None

def add_row_to_excel(product_name, category):
    token = get_graph_token()
    if not token:
        return {"error": "Failed to authenticate with Microsoft Graph"}
    endpoint = (
        f"https://graph.microsoft.com/v1.0/me/drive/items/{DRIVE_ITEM_ID}"
        f"/workbook/tables/{TABLE_NAME}/rows/add"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {"values": [[product_name, category]]}
    try:
        response = requests.post(endpoint, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error adding row to Excel: {e}")
        return {"error": str(e)}

def handler(event, context):
    if event['httpMethod'] == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': 'https://badylk.netlify.app'}
        }
    if event['httpMethod'] == 'POST':
        try:
            data = json.loads(event['body'])
            name = data.get('name')
            is_boycotted = data.get('is_boycotted', False)
            category = data.get('category', '')
            if not name:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': 'https://badylk.netlify.app'},
                    'body': json.dumps({"error": "Product 'name' is required"})
                }
            conn = get_db_connection()
            if not conn:
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': 'https://badylk.netlify.app'},
                    'body': json.dumps({"error": "Database connection failed"})
                }
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO products (name, is_boycotted, category) VALUES (%s, %s, %s)",
                (name, is_boycotted, category)
            )
            conn.commit()
            if category:
                excel_result = add_row_to_excel(name, category)
                if "error" in excel_result:
                    return {
                        'statusCode': 500,
                        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': 'https://badylk.netlify.app'},
                        'body': json.dumps({"error": excel_result["error"]})
                    }
            cursor.close()
            conn.close()
            return {
                'statusCode': 201,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': 'https://badylk.netlify.app'},
                'body': json.dumps({"message": "Product added successfully"})
            }
        except Error as e:
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': 'https://badylk.netlify.app'},
                'body': json.dumps({"error": str(e)})
            }
        except Exception as e:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': 'https://badylk.netlify.app'},
                'body': json.dumps({"error": f"Invalid request: {str(e)}"})
            }