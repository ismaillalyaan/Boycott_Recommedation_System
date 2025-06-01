import json

def handler(event, context):
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': 'https://badylk.netlify.app'},
        'body': json.dumps({"message": "Welcome to the RecSys API.", "status": "running"})
    }