import os
import json
import pytest
import boto3
from moto import mock_dynamodb2
from src.versioning import lambda_handler
from src.db_operations import DynamoDBOperations

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
            "resource": "/create-app",
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
    assert 'App created with version 0.1.0' in response['body'], "Response body should confirm creation"

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
