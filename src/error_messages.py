class ErrorMessages:
    """
    Class to encapsulate all error messages used throughout the application.
    Provides a central point of modification for the error messages.
    """
    DYNAMODB_CONNECTION_FAIL = 'Failed to connect to DynamoDB'
    CONNECTION_TEST_FAILED = 'Connection Test Failed: {}'
    INVALID_APP_NAME = 'Invalid app_name'
    UNAUTHORIZED = 'Unauthorized'
    INVALID_REQUEST = 'Invalid request'
    MISSING_APP_NAME = 'Missing app_name'
    APP_ALREADY_EXISTS = 'App already exists'
    INTERNAL_SERVER_ERROR = 'An internal server error occurred: {}'
    APP_NOT_FOUND = 'App not found'
    INVALID_VERSION_TYPE = 'Invalid or missing version type'
    MISSING_NEW_VERSION = 'Missing new_version'
    
    @staticmethod
    def format_error(message, *args):
        """
        Formats the error message with additional arguments.
        """
        return message.format(*args)