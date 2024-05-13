import hashlib
from db_operations import DynamoDBOperations
import json
import jwt
import datetime
from botocore.exceptions import ClientError
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')


SECRET_KEY = "YourSecretKeyHere"  # Securely manage this key, perhaps using AWS Secrets Manager

def lambda_handler(event, context, db_operations=None):
    if db_operations is None:
        db_operations = DynamoDBOperations()
   
    try:
        if not test_dynamodb_connection(db_operations):
            return response('Failed to connect to DynamoDB', 500)
    except Exception as e:
        return response(f"Connection Test Failed: {str(e)}", 500)

    try:
        operation = event['httpMethod']
        path = event['resource']
        params = event.get('queryStringParameters', {})
        headers = event.get('headers', {})

        if path == "/create" and operation == "POST":
            app_name = params.get('app_name')
            secure = params.get('secure', 'false').lower() == 'true'
            return create_app(db_operations, app_name, secure)

        app_name = event['pathParameters'].get('app_name')
        if check_if_secure_app(db_operations, app_name):
            token = headers.get('Authorization')
            if not token or not verify_jwt(token, db_operations, app_name):
                return response('Unauthorized', 401)

        # Existing routing logic
        if path == "/{app_name}/version" and operation == "GET":
            return get_version(db_operations, app_name)
        elif path == "/{app_name}/bump" and operation == "POST":
            version_type = params.get('type')
            return bump_version(db_operations, app_name, version_type)
        elif path == "/{app_name}/set" and operation == "POST":
            new_version = params.get('new_version')
            return set_version(db_operations, app_name, new_version)
        else:
            return response('Invalid request', 400)

    except Exception as e:
        return response(str(e), 500)

def validate_app_name(app_name):
    """ Validate the app name against a simple regex pattern. """
    if not app_name or not re.match(r'^[A-Za-z0-9_\-]+$', app_name):
        logging.warning(f"Validation failed for app_name: {app_name}")
        return False
    return True

def validate_version(version):
    """ Validate version format (major.minor.patch). """
    if not re.match(r'^\d+\.\d+\.\d+$', version):
        logging.warning(f"Invalid version format: {version}")
        return False
    return True

def test_dynamodb_connection(db_operations):
    # This just attempts to fetch a predefined item to check the connection
    try:
        db_operations.get_item({'appName': 'TestConnectionApp'})
        return True
    except Exception as e:
        print(f"Failed to connect to DynamoDB: {str(e)}")
        return False
    
def create_app(db_operations, app_name, secure=False):
    if not app_name:
        return response('Missing app_name', 400)
    
    try:
        result = db_operations.get_item({'appName': app_name})
        if 'Item' in result:
            return response('App already exists', 409)
        
        app_data = {'appName': app_name, 'version': '0.1.0', 'secure': secure}
        print("secure: " + str(secure))
        if secure:
            token = create_jwt(app_name)
            app_data['tokenHash'] = hashlib.sha256(token.encode()).hexdigest()  # Store a hash of the token
        db_operations.put_item(app_data)

        response_data = {'app_name': app_name, 'version': '0.1.0'}
        if secure:
            response_data['token'] = token

        return response(response_data, 201)
    except Exception as e:
        return response(str(e), 500)

def get_version(db_operations, app_name):
    try:
        result = db_operations.get_item({'appName': app_name})
        if 'Item' not in result:
            return response('App not found', 404)
        return response({'version': result['Item']['version']}, 200)
    except Exception as e:
        return response(str(e), 500)

def bump_version(db_operations, app_name, version_type):
    if not version_type or version_type not in ['major', 'minor', 'patch']:
        return response('Invalid or missing version type', 400)

    try:
        result = db_operations.get_item({'appName': app_name})
        if 'Item' not in result:
            return response('App not found', 404)
        
        current_version = result['Item']['version']
        major, minor, patch = [int(part) for part in current_version.split('.')]
        new_version = ''
        if version_type == 'major':
            new_version = f"{major + 1}.0.0"
        elif version_type == 'minor':
            new_version = f"{major}.{minor + 1}.0"
        else:  # patch
            new_version = f"{major}.{minor}.{patch + 1}"

        db_operations.update_item(
            {'appName': app_name},
            'SET version = :v',
            {':v': new_version}
        )
        return response({'new_version': new_version}, 200)
    except Exception as e:
        return response(str(e), 500)

def set_version(db_operations, app_name, new_version):
    if not new_version:
        return response('Missing new_version', 400)

    try:
        db_operations.update_item(
            {'appName': app_name},
            'SET version = :v',
            {':v': new_version}
        )
        return response({'new_version': new_version}, 200)
    except Exception as e:
        return response(str(e), 500)


def verify_jwt(token, db_operations, app_name):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        # Check if the app_name in the token matches the app_name being accessed
        if payload.get('app_name') == app_name:
            # Fetch the stored token hash from the database
            result = db_operations.get_item({'appName': app_name})
            if 'tokenHash' in result['Item']:
                token_hash = result['Item']['tokenHash']
                # Validate the token hash
                return hashlib.sha256(token.encode()).hexdigest() == token_hash
        return False
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return False

def create_jwt(app_name):
    payload = {
        'app_name': app_name,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=365)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def check_if_secure_app(db_operations, app_name):
    if not app_name:
        return False
    result = db_operations.get_item({'appName': app_name})
    return result.get('Item', {}).get('secure', False)

def response(message, status_code):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(message) if isinstance(message, dict) else message
    }
