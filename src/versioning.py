from db_operations import DynamoDBOperations

import json
from botocore.exceptions import ClientError

def lambda_handler(event, context, db_operations=None):

    if db_operations is None:
        db_operations = DynamoDBOperations()
        
    # db_operations = DynamoDBOperations()  # Initialize DynamoDB operations
    
    # Test DynamoDB connection
    try:
        if not test_dynamodb_connection(db_operations):
            return response('Failed to connect to DynamoDB', 500)
    except Exception as e:
        return response(f"Connection Test Failed: {str(e)}", 500)
    
    try:
        operation = event['httpMethod']
        path = event['resource']
        params = event.get('queryStringParameters', {})

        # Route the request
        if path == "/create-app" and operation == "POST":
            app_name = params.get('app_name')
            return create_app(db_operations, app_name)
        elif path == "/{app_name}/version" and operation == "GET":
            app_name = event['pathParameters']['app_name']
            return get_version(db_operations, app_name)
        elif path == "/{app_name}/bump" and operation == "POST":
            app_name = event['pathParameters']['app_name']
            version_type = params.get('type')
            return bump_version(db_operations, app_name, version_type)
        elif path == "/{app_name}/set" and operation == "POST":
            app_name = event['pathParameters']['app_name']
            new_version = params.get('new_version')
            return set_version(db_operations, app_name, new_version)
        else:
            return response('Invalid request', 400)
    except Exception as e:
        return response(str(e), 500)

def test_dynamodb_connection(db_operations):
    # This just attempts to fetch a predefined item to check the connection
    try:
        db_operations.get_item({'appName': 'TestConnectionApp'})
        return True
    except Exception as e:
        print(f"Failed to connect to DynamoDB: {str(e)}")
        return False

def create_app(db_operations, app_name):
    if not app_name:
        return response('Missing app_name', 400)
    
    try:
        result = db_operations.get_item({'appName': app_name})
        if 'Item' in result:
            return response('App already exists', 409)
        
        db_operations.put_item({'appName': app_name, 'version': '0.1.0'})
        return response('App created with version 0.1.0', 201)
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
            initial_versions = {
                'major': '1.0.0',
                'minor': '0.1.0',
                'patch': '0.0.1'
            }
            initial_version = initial_versions[version_type]
            db_operations.put_item({'appName': app_name, 'version': initial_version})
            return response(f"App created with version {initial_version}", 201)
        else:
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

def response(message, status_code):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'  # CORS configuration if necessary
        },
        'body': json.dumps(message) if isinstance(message, dict) else message
    }

