import hashlib
import logging
import re
import os

from models import Application
from services import DynamoDBOperations, JWTManager
from utilities import ErrorMessages, ResponseHandler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')
logger = logging.getLogger()

response_handler = ResponseHandler()

def lambda_handler(event, context, db_operations=None, jwt_manager=None):
    """
    Handles incoming AWS Lambda requests, routes them based on the request type and resource.
    """
    logger.info("Received event: %s", event)

    # If db_operations is not provided (mocked from testing), build it here
    if db_operations is None:
        db_operations = DynamoDBOperations()

    if jwt_manager is None:
        jwt_manager = JWTManager(secret_name=os.environ['JWT_SECRET_NAME'])
   
    try:
        if not test_dynamodb_connection(db_operations):
            logger.error("DynamoDB connection failed")
            return response_handler.response(ErrorMessages.DYNAMODB_CONNECTION_FAIL, 500)
    except Exception as e:
        logger.exception("Connection test failed")
        return response_handler.response(ErrorMessages.format_error(ErrorMessages.CONNECTION_TEST_FAILED, str(e)), 500)

    try:
        operation = event['httpMethod']
        path = event['resource']
        params = event.get('queryStringParameters', {})
        headers = event.get('headers', {})

        logger.info("Processing request: %s %s", operation, path)

        if path == "/api/create" and operation == "POST":
            app_name = params.get('app_name')
            if not app_name:
                logger.warning("Missing app name in request")
                return response_handler.response(ErrorMessages.MISSING_APP_NAME, 400)
            if not validate_app_name(app_name):
                logger.warning("Invalid app name: %s", app_name)
                return response_handler.response(ErrorMessages.INVALID_APP_NAME, 400)
            secure = params.get('secure', 'false').lower() == 'true'
            expiry_days = params.get('expiry_days', 365)  # Get the custom expiry days
            if expiry_days:
                expiry_days = int(expiry_days)  # Convert to integer if it exists
            return create_app(db_operations, app_name, jwt_manager, secure, expiry_days)

        app_name = event['pathParameters'].get('app_name')
        if not validate_app_name(app_name):
            logger.warning("Invalid app name: %s", app_name)
            return response_handler.response(ErrorMessages.INVALID_APP_NAME, 400)
        
        if check_if_secure_app(db_operations, app_name):
            token = headers.get('Authorization')
            if not token or not jwt_manager.verify_jwt(token, db_operations, app_name):
                logger.warning("Unauthorized access attempt for app: %s", app_name)
                return response_handler.response(ErrorMessages.UNAUTHORIZED, 401)

        try:
            app = Application(app_name, db_operations)
        except ValueError as e:
            logger.error("Application error: %s", str(e))
            return response_handler.response(str(e), 404)

        # rest of routing logic
        if path == "/api/{app_name}/version" and operation == "GET":
            return app.get_version()
        elif path == "/api/{app_name}/bump" and operation == "POST":
            version_type = params.get('type')
            return app.bump_version(version_type)
        elif path == "/api/{app_name}/set" and operation == "POST":
            new_version = params.get('new_version')
            if not validate_version(new_version):
                logger.warning("Invalid version type: %s", new_version)
                return response_handler.response(ErrorMessages.INVALID_VERSION_TYPE, 400)
            return app.set_version(new_version)
        else:
            logger.warning("Invalid request path: %s", path)
            return response_handler.response(ErrorMessages.INVALID_REQUEST, 400)

    except Exception as e:
        logger.exception("Internal server error")
        return response_handler.response(ErrorMessages.format_error(ErrorMessages.INTERNAL_SERVER_ERROR, str(e)), 500)

def validate_app_name(app_name):
    """ Validate the app name against a simple regex pattern. """
    if not app_name or not re.match(r'^[A-Za-z0-9_\-]+$', app_name):
        logger.warning("Validation failed for app name: %s", app_name)
        return False
    return True

def validate_version(version):
    """ Validate version format (major.minor.patch). """
    if not re.match(r'^\d+\.\d+\.\d+$', version):
        logger.warning("Invalid version format: %s", version)
        return False
    return True

def test_dynamodb_connection(db_operations):
    """
    Checks the connectivity to DynamoDB by attempting to fetch a predefined item.
    """
    try:
        db_operations.get_item({'appName': 'TestConnectionApp'})
        logger.info("DynamoDB connection successful")
        return True
    except Exception as e:
        logger.error("Failed to connect to DynamoDB: %s", str(e))
        return False
    
def create_app(db_operations, app_name, jwt_manager, secure=False, expiry_days=365):
    """
    Creates a new application entry in the database with an optional security token.
    """
    try:
        result = db_operations.get_item({'appName': app_name})
        if 'Item' in result:
            logger.warning("Application already exists: %s", app_name)
            return response_handler.response(ErrorMessages.APP_ALREADY_EXISTS, 409)
        
        app_data = {'appName': app_name, 'version': '0.1.0', 'secure': secure}
        if secure:
            token = jwt_manager.create_jwt(app_name, expiry_days)
            app_data['tokenHash'] = hashlib.sha256(token.encode()).hexdigest()  # Store a hash of the token
            app_data['tokenExpiryDays'] = expiry_days  # Store the token expiry duration
        db_operations.put_item(app_data)

        response_data = {'app_name': app_name, 'version': '0.1.0'}
        if secure:
            response_data['token'] = token

        logger.info("Created application: %s", app_name)
        return response_handler.response(response_data, 201)
    except Exception as e:
        logger.exception("Error creating application: %s", app_name)
        return response_handler.response(ErrorMessages.format_error(ErrorMessages.INTERNAL_SERVER_ERROR, str(e)), 500)

def check_if_secure_app(db_operations, app_name):
    """
    Checks if the specified app is configured for enhanced security.
    """
    if not app_name:
        return False
    result = db_operations.get_item({'appName': app_name})
    return result.get('Item', {}).get('secure', False)
