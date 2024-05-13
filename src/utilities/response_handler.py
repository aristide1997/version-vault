import json

class ResponseHandler:
    def __init__(self):
        pass

    def response(self, message, status_code):
        return {
            'statusCode': status_code,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(message) if isinstance(message, dict) else message
        }
