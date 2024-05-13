import os
import json
import pytest
import boto3
from moto import mock_dynamodb2
from src.versioning import lambda_handler
# from src.db_operations import DynamoDBOperations
# from src.error_messages import ErrorMessages

from src.services.database_service import DynamoDBOperations
from src.utilities.error_handling import ErrorMessages

@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['TABLE_NAME'] = 'VersioningTable'

@pytest.fixture(scope="function")
def dynamodb_resource(aws_credentials):
    with mock_dynamodb2():
        dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
        table = dynamodb.create_table(
            TableName="VersioningTable",
            KeySchema=[{'AttributeName': 'appName', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'appName', 'AttributeType': 'S'}],
            ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
        )
        table.meta.client.get_waiter('table_exists').wait(TableName="VersioningTable")
        yield dynamodb

@pytest.fixture(scope="function")
def db_operations(dynamodb_resource):
    return DynamoDBOperations(client=dynamodb_resource)

@pytest.fixture
def api_event():
    """Generates API Gateway events to simulate different API calls."""
    return {
        "POST": {
            "httpMethod": "POST",
            "resource": "/create",
            "queryStringParameters": {"app_name": "TestApp"}
        },
        "GET": {
            "httpMethod": "GET",
            "resource": "/{app_name}/version",
            "pathParameters": {"app_name": "TestApp"}
        },
        "POST_BUMP": {
            "httpMethod": "POST",
            "resource": "/{app_name}/bump",
            "pathParameters": {"app_name": "TestApp"},
            "queryStringParameters": {"type": "minor"}
        },
        "POST_SET": {
            "httpMethod": "POST",
            "resource": "/{app_name}/set",
            "pathParameters": {"app_name": "TestApp"},
            "queryStringParameters": {"new_version": "2.0.0"}
        },
        "POST_SECURE": {
            "httpMethod": "POST",
            "resource": "/create",
            "queryStringParameters": {"app_name": "SecureTestApp", "secure": "true"}
        },
        "GET_SECURE": {
            "httpMethod": "GET",
            "resource": "/{app_name}/version",
            "pathParameters": {"app_name": "SecureTestApp"},
            "headers": {"Authorization": None}  # Update this with token later
        },
        "POST_BUMP_SECURE": {
            "httpMethod": "POST",
            "resource": "/{app_name}/bump",
            "pathParameters": {"app_name": "SecureTestApp"},
            "headers": {"Authorization": None},  # Update this with token later
            "queryStringParameters": {"type": "minor"}
        }
    }

def test_write_and_read_item(db_operations):
    """Test writing to and reading from the DynamoDB table."""
    # Assuming 'appName' is the primary key and 'data' is an additional attribute
    test_item = {
        'appName': '123',  # Use 'appName' as per your table's key schema
        'data': 'example data'
    }

    # Write item to DynamoDB
    db_operations.put_item(test_item)

    # Read item from DynamoDB
    result = db_operations.get_item({'appName': '123'})

    # Assert that the retrieved item matches the written item
    assert 'Item' in result, "The item should have been found in the table."
    assert result['Item']['appName'] == '123', "The item appName should match the test item appName."
    assert result['Item']['data'] == 'example data', "The item data should match the test item data."


def test_lambda_handler_create_app(db_operations, api_event):
    """Test the creation of a new app entry."""
    response = lambda_handler(event=api_event["POST"], context=None, db_operations=db_operations)
    assert response['statusCode'] == 201, "Status code should be 201 for successful creation"
    # assert 'App created with version 0.1.0' in response['body'], "Response body should confirm creation"

def test_lambda_handler_get_version(db_operations, api_event):
    """Test getting the version of an app after its creation."""
    # First create the app
    lambda_handler(event=api_event["POST"], context=None, db_operations=db_operations)
    # Now get the version
    response = lambda_handler(event=api_event["GET"], context=None, db_operations=db_operations)
    assert response['statusCode'] == 200, "Status code should be 200 for successful fetch"
    assert json.loads(response['body'])['version'] == '0.1.0', "The version should be 0.1.0 in the response body"

def test_lambda_handler_bump_version(db_operations, api_event):
    """Test bumping the version of an existing app."""
    lambda_handler(event=api_event["POST"], context=None, db_operations=db_operations)  # Create the app first
    response = lambda_handler(event=api_event["POST_BUMP"], context=None, db_operations=db_operations)
    assert response['statusCode'] == 200, "Status code should be 200 for successful version bump"
    assert json.loads(response['body'])['new_version'] == '0.2.0', "Version should be bumped to 0.2.0"

def test_lambda_handler_set_version(db_operations, api_event):
    """Test setting a specific version for an existing app."""
    lambda_handler(event=api_event["POST"], context=None, db_operations=db_operations)  # Create the app first
    response = lambda_handler(event=api_event["POST_SET"], context=None, db_operations=db_operations)
    assert response['statusCode'] == 200, "Status code should be 200 for successful version set"
    assert json.loads(response['body'])['new_version'] == '2.0.0', "Version should be set to 2.0.0"

def test_lambda_handler_create_app_missing_app_name(db_operations, api_event):
    """Test the case where app name is missing during creation."""
    # Change the app name to None
    api_event["POST"]["queryStringParameters"]["app_name"] = None
    response = lambda_handler(event=api_event["POST"], context=None, db_operations=db_operations)
    assert response['statusCode'] == 400, "Status code should be 400 for app name missing"
    assert ErrorMessages.MISSING_APP_NAME in response['body'], "Response body should mention missing app name"

def test_lambda_handler_get_version_non_existent_app(db_operations, api_event):
    """Test getting the version of a non-existent app."""
    api_event["GET"]["pathParameters"]["app_name"] = "RandomApp"  # Non-existent app name
    response = lambda_handler(event=api_event["GET"], context=None, db_operations=db_operations)
    assert response['statusCode'] == 404, "Status code should be 404 for non-existent app"
    assert ErrorMessages.APP_NOT_FOUND in response['body'], "Response body should confirm app not found"

def test_lambda_handler_bump_version_invalid_version_type(db_operations, api_event):
    """Test the case where invalid version type is supplied for version bump."""
    lambda_handler(event=api_event["POST"], context=None, db_operations=db_operations)  # Create the app first
    api_event["POST_BUMP"]["queryStringParameters"]["type"] = "invalid"  # Invalid version type
    response = lambda_handler(event=api_event["POST_BUMP"], context=None, db_operations=db_operations)
    assert response['statusCode'] == 400, "Status code should be 400 for invalid version type"
    assert ErrorMessages.INVALID_VERSION_TYPE in response['body'], "Response body should mention invalid version type"

def test_lambda_handler_set_version_missing_new_version(db_operations, api_event):
    """Test the case where new version is missing while setting a version."""
    lambda_handler(event=api_event["POST"], context=None, db_operations=db_operations)  # Create the app first
    api_event["POST_SET"]["queryStringParameters"]["new_version"] = ""  # Missing new version
    response = lambda_handler(event=api_event["POST_SET"], context=None, db_operations=db_operations)
    assert response['statusCode'] == 400, "Status code should be 400 for missing new version"
    assert ErrorMessages.INVALID_VERSION_TYPE in response['body'], "Response body should mention missing new version"

def test_lambda_handler_secure_create_app(db_operations, api_event):
    """Test creating a new app entry with secure 'true'. This should create a JWT as well."""
    response = lambda_handler(event=api_event["POST_SECURE"], context=None, db_operations=db_operations)
    assert response['statusCode'] == 201, "Status code should be 201 for successful creation"
    assert 'token' in response['body'], "Response body should contain a JWT token"

def test_lambda_handler_secure_get_version(db_operations, api_event):
    """Test getting the version of an app after its creation. This requires a valid JWT."""
    # Create the app and get the JWT
    response = lambda_handler(event=api_event["POST_SECURE"], context=None, db_operations=db_operations)
    token = json.loads(response['body'])['token']
    # Update the GET_SECURE event with the JWT
    api_event["GET_SECURE"]["headers"]["Authorization"] = token
    # Now get the version
    response = lambda_handler(event=api_event["GET_SECURE"], context=None, db_operations=db_operations)
    assert response['statusCode'] == 200, "Status code should be 200 for successful fetch"
    assert json.loads(response['body'])['version'] == '0.1.0', "The version should be 0.1.0 in the response body"

def test_lambda_handler_secure_bump_version(db_operations, api_event):
    """Test bumping the version of an existing app. This requires a valid JWT."""
    # Create the app and get the JWT
    response = lambda_handler(event=api_event["POST_SECURE"], context=None, db_operations=db_operations)
    token = json.loads(response['body'])['token']
    # Update the POST_BUMP_SECURE event with the JWT
    api_event["POST_BUMP_SECURE"]["headers"]["Authorization"] = token
    # Now bump the version
    response = lambda_handler(event=api_event["POST_BUMP_SECURE"], context=None, db_operations=db_operations)
    assert response['statusCode'] == 200, "Status code should be 200 for successful version bump"
    assert json.loads(response['body'])['new_version'] == '0.2.0', "Version should be bumped to 0.2.0"

def test_invalid_jwt(db_operations, api_event):
    """Test accessing secure endpoints with an invalid JWT."""
    # First create a secure app
    response_create = lambda_handler(api_event["POST_SECURE"], context=None, db_operations=db_operations)
    token = json.loads(response_create['body'])['token'] + "tampered"

    # Use the tampered token to fetch version
    api_event["GET_SECURE"]["headers"]["Authorization"] = token
    response = lambda_handler(api_event["GET_SECURE"], context=None, db_operations=db_operations)
    assert response['statusCode'] == 401, "Status code should be 401 for invalid JWT"
    assert ErrorMessages.UNAUTHORIZED in response['body'], "Response body should indicate unauthorized access"

@pytest.mark.parametrize("invalid_name", ["test app", "test@app", "test*app"])
def test_create_app_with_invalid_app_name(db_operations, api_event, invalid_name):
    """Test app creation with invalid app names."""
    api_event["POST"]["queryStringParameters"]["app_name"] = invalid_name
    response = lambda_handler(api_event["POST"], context=None, db_operations=db_operations)
    assert response['statusCode'] == 400, "Should return 400 for invalid app names"
    assert ErrorMessages.INVALID_APP_NAME in response['body'], "Response body should indicate invalid app name"

def test_set_invalid_version_format(db_operations, api_event):
    """Test setting a version with an invalid format."""
    # First create the app
    lambda_handler(api_event["POST"], context=None, db_operations=db_operations)
    api_event["POST_SET"]["queryStringParameters"]["new_version"] = "1..0"
    response = lambda_handler(api_event["POST_SET"], context=None, db_operations=db_operations)
    assert response['statusCode'] == 400, "Status code should be 400 for invalid version format"
    assert ErrorMessages.INVALID_VERSION_TYPE in response['body'], "Response body should indicate invalid version format"

def test_unsupported_http_method(db_operations, api_event):
    """Test lambda handler with an unsupported HTTP method."""
    api_event["GET"]["httpMethod"] = "PUT"  # Unsupported method
    response = lambda_handler(api_event["GET"], context=None, db_operations=db_operations)
    assert response['statusCode'] == 400, "Status code should be 400 for unsupported HTTP method"
    assert ErrorMessages.INVALID_REQUEST in response['body'], "Response body should indicate invalid request"