 import json
import os
import boto3
import requests

DB_FILE_NAME = os.environ.get('db_file_name')

def postRequest(token, method, data):
    return requests.post("https://api.telegram.org/bot" + token + method, json=data)

def aws_key_id():
    return os.environ.get('aws_access_key_id')

def aws_secret_key():
    return os.environ.get('aws_secret_access_key')

def bucket_id():
    return os.environ.get('bucket_id')

def bot_token():
    return os.environ.get('bot_token')

def chat_id():
    return os.environ.get('chat_id')

def handler(event, context):
    session = boto3.session.Session()
    s3 = session.client(
        service_name='s3',
        endpoint_url='https://storage.yandexcloud.net',
        aws_access_key_id=aws_key_id(),
        aws_secret_access_key=aws_secret_key()
    )

    is_message_from_queue = True
    try:
        event['messages'][0]['event_metadata']['event_type']

    except KeyError:
        is_message_from_queue = False

    if is_message_from_queue:
        message_body_json = event['messages'][0]['details']['message']['message_attributes']['string']['string_value']
        faces = message_body_json.strip('[').strip(']').replace("'", '').split(", ")

        parent_obj_origin = event['messages'][0]['details']['message']['body']
        parent_object = "".join(parent_obj_origin.split(" ")[2::])

        
        for face in faces:
            face_image_response = s3.get_object(Bucket=bucket_id(), Key=face)
            face_image_content = face_image_response['Body'].read()
            params = {'chat_id': chat_id(), 'caption': parent_object}
            files = {'photo': face_image_content}
            postRequest(bot_token(), '/sendMessage', data={'chat_id': chat_id(), 'text': 'Who is it?'})
            requests.post('https://api.telegram.org/bot{0}/sendPhoto'.format(bot_token()), data=params, files=files)

    else:
        try:
            body = event['body']
            body_json = json.loads(body)
            message = body_json['message']
            message_id = message['message_id']
        except KeyError:
            message = body_json['edited_message']
            message_id = message['message_id']

        is_valid_reply = False
        photo_id = ""
        photo_name = ""
        try:
            photo_id = message['reply_to_message']['caption']
            if message['reply_to_message']['from']['is_bot'] == True:
                is_valid_reply = True
                photo_name = message['text']

        except KeyError:
            is_valid_reply = False

        if is_valid_reply:
            db_file = {}
            try:
                get_db_file_response = s3.get_object(Bucket=bucket_id(), Key=DB_FILE_NAME)
                db_file = json.loads(get_db_file_response['Body'].read())
            except Exception as e:
                db_file = {}

            current_images_for_name = []
            try:
                current_images_for_name = db_file[photo_name]
            except KeyError:
                current_images_for_name = []

            is_append_file = True
            for image in current_images_for_name:
                if image == photo_id:
                    is_append_file = False
            if is_append_file:
                current_images_for_name.append(photo_id)
                db_file[photo_name] = current_images_for_name
                s3.put_object(Body=json.dumps(db_file), Bucket=bucket_id(), Key=DB_FILE_NAME)

        else:
            try:
                message_text = message['text']
            except Exception as e:
                postRequest(bot_token(), '/sendMessage', data={'chat_id': chat_id(), 'text': 'Invalid Command!',
                                                                      'reply_to_message_id': message_id})
                return {
                    'statusCode': 200,
                    'body': 'Invalid Command!',
                }
            command_parts = message_text.split(' ')
            is_command_find = False
            for part in command_parts:
                if part == '/find':
                    is_command_find = True
            if len(command_parts) == 2 and is_command_find:
                name_to_find = command_parts[1]
                try:
                    get_db_file_response = s3.get_object(Bucket=bucket_id(), Key=DB_FILE_NAME)
                    db_file = json.loads(get_db_file_response['Body'].read())
                except Exception as e:
                    postRequest(bot_token(), '/sendMessage', data={'chat_id': chat_id(),
                                                                          'text': 'No photos',
                                                                          'reply_to_message_id': message_id})
                    return {
                        'statusCode': 200,
                        'body': 'No photos',
                    }
                try:
                    images = db_file[name_to_find]
                except KeyError:
                    postRequest(
                        bot_token(),
                        '/sendMessage',
                        data={'chat_id': chat_id(),
                                       'text': 'No photos',
                                       'reply_to_message_id': message_id})
                    return {
                        'statusCode': 200,
                        'body': 'No photos!',
                    }
                postRequest(
                    bot_token(),
                    '/sendMessage',
                    data={'chat_id': chat_id(),
                                   'text': f'Photos of the user {name_to_find}:'})

                for image in images:
                    image_response = s3.get_object(Bucket=bucket_id(), Key=image)
                    image_response_content = image_response['Body'].read()
                    params = {'chat_id': chat_id()}
                    files = {'photo': image_response_content}
                    requests.post('https://api.telegram.org/bot{0}/sendPhoto'.format(bot_token()), data=params,
                                  files=files)
            else:
                return {
                    'statusCode': 200,
                    'body': 'Invalid Command!',
                }

    return {
        'statusCode': 200,
        'body': 'Ok',
    }
