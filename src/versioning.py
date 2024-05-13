import hashlib
# from db_operations import DynamoDBOperations
# from jwt_operations import JWTManager
# from response_handler import ResponseHandler
import json
import jwt
import datetime
from botocore.exceptions import ClientError
import re
import logging
# from error_messages import ErrorMessages

from services.database_service import DynamoDBOperations
from services.jwt_service import JWTManager
from utilities.response_handler import ResponseHandler
from utilities.error_handling import ErrorMessages

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

response_handler = ResponseHandler()
jwt_manager = JWTManager("YourSecretKeyHere")

def lambda_handler(event, context, db_operations=None):
    """
    Handles incoming AWS Lambda requests, routes them based on the request type and resource.
    """
    if db_operations is None:
        db_operations = DynamoDBOperations()
   
    try:
        if not test_dynamodb_connection(db_operations):
            return response_handler.response(ErrorMessages.DYNAMODB_CONNECTION_FAIL, 500)
    except Exception as e:
        return response_handler.response(ErrorMessages.format_error(ErrorMessages.CONNECTION_TEST_FAILED, str(e)), 500)

    try:
        operation = event['httpMethod']
        path = event['resource']
        params = event.get('queryStringParameters', {})
        headers = event.get('headers', {})

        if path == "/create" and operation == "POST":
            app_name = params.get('app_name')
            if not app_name:
                return response_handler.response(ErrorMessages.MISSING_APP_NAME, 400)
            if not validate_app_name(app_name):
                return response_handler.response(ErrorMessages.INVALID_APP_NAME, 400)
            secure = params.get('secure', 'false').lower() == 'true'
            return create_app(db_operations, app_name, secure)

        app_name = event['pathParameters'].get('app_name')
        if not validate_app_name(app_name):
            return response_handler.response(ErrorMessages.INVALID_APP_NAME, 400)
        
        if check_if_secure_app(db_operations, app_name):
            token = headers.get('Authorization')
            if not token or not jwt_manager.verify_jwt(token, db_operations, app_name):
                return response_handler.response(ErrorMessages.UNAUTHORIZED, 401)

        # rest of routing logic
        if path == "/{app_name}/version" and operation == "GET":
            return get_version(db_operations, app_name)
        elif path == "/{app_name}/bump" and operation == "POST":
            version_type = params.get('type')
            return bump_version(db_operations, app_name, version_type)
        elif path == "/{app_name}/set" and operation == "POST":
            new_version = params.get('new_version')
            if not validate_version(new_version):
                return response_handler.response(ErrorMessages.INVALID_VERSION_TYPE, 400)
            return set_version(db_operations, app_name, new_version)
        else:
            return response_handler.response(ErrorMessages.INVALID_REQUEST, 400)

    except Exception as e:
        return response_handler.response(ErrorMessages.format_error(ErrorMessages.INTERNAL_SERVER_ERROR, str(e)), 500)

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
    """
    Checks the connectivity to DynamoDB by attempting to fetch a predefined item.
    """
    try:
        db_operations.get_item({'appName': 'TestConnectionApp'})
        return True
    except Exception as e:
        print(f"Failed to connect to DynamoDB: {str(e)}")
        return False
    
def create_app(db_operations, app_name, secure=False):
    """
    Creates a new application entry in the database with an optional security token.
    """
    # if not app_name:
    #     return response_handler.response(ErrorMessages.MISSING_APP_NAME, 400)
    
    try:
        result = db_operations.get_item({'appName': app_name})
        if 'Item' in result:
            return response_handler.response(ErrorMessages.APP_ALREADY_EXISTS, 409)
        
        app_data = {'appName': app_name, 'version': '0.1.0', 'secure': secure}
        print("secure: " + str(secure))
        if secure:
            token = jwt_manager.create_jwt(app_name)
            app_data['tokenHash'] = hashlib.sha256(token.encode()).hexdigest()  # Store a hash of the token
        db_operations.put_item(app_data)

        response_data = {'app_name': app_name, 'version': '0.1.0'}
        if secure:
            response_data['token'] = token

        return response_handler.response(response_data, 201)
    except Exception as e:
        return response_handler.response(ErrorMessages.format_error(ErrorMessages.INTERNAL_SERVER_ERROR, str(e)), 500)

def get_version(db_operations, app_name):
    """
    Retrieves the current version of the specified app from the database.
    """
    try:
        result = db_operations.get_item({'appName': app_name})
        if 'Item' not in result:
            return response_handler.response(ErrorMessages.APP_NOT_FOUND, 404)
        return response_handler.response({'version': result['Item']['version']}, 200)
    except Exception as e:
        return response_handler.response(ErrorMessages.format_error(ErrorMessages.INTERNAL_SERVER_ERROR, str(e)), 500)

def bump_version(db_operations, app_name, version_type):
    """
    Bumps the app version based on the specified type (major, minor, or patch).
    """
    if not version_type or version_type not in ['major', 'minor', 'patch']:
        return response_handler.response(ErrorMessages.INVALID_VERSION_TYPE, 400)

    try:
        result = db_operations.get_item({'appName': app_name})
        if 'Item' not in result:
            return response_handler.response(ErrorMessages.APP_NOT_FOUND, 404)
        
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
        return response_handler.response({'new_version': new_version}, 200)
    except Exception as e:
        return response_handler.response(ErrorMessages.format_error(ErrorMessages.INTERNAL_SERVER_ERROR, str(e)), 500)

def set_version(db_operations, app_name, new_version):
    """
    Sets the version of an app to a specified new value.
    """
    if not new_version:
        return response_handler.response(ErrorMessages.MISSING_NEW_VERSION, 400)

    try:
        db_operations.update_item(
            {'appName': app_name},
            'SET version = :v',
            {':v': new_version}
        )
        return response_handler.response({'new_version': new_version}, 200)
    except Exception as e:
        return response_handler.response(ErrorMessages.format_error(ErrorMessages.INTERNAL_SERVER_ERROR, str(e)), 500)

def check_if_secure_app(db_operations, app_name):
    """
    Checks if the specified app is configured for enhanced security.
    """
    if not app_name:
        return False
    result = db_operations.get_item({'appName': app_name})
    return result.get('Item', {}).get('secure', False)
