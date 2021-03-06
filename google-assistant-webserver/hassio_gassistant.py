"""Hass.IO Google Assistant."""
import json
import sys
from pathlib import Path

import google.oauth2.credentials

from google.assistant.library import Assistant
from google.assistant.library.event import EventType

import google.auth.transport.grpc
import google.auth.transport.requests

from google.assistant.embedded.v1alpha2 import (
    embedded_assistant_pb2,
    embedded_assistant_pb2_grpc
)

from flask import Flask, request, jsonify
from flask_restful import Resource, Api

app = Flask(__name__)
api = Api(app)

ASSISTANT_API_ENDPOINT = 'embeddedassistant.googleapis.com'
DEFAULT_GRPC_DEADLINE = 60 * 3 + 5

class BroadcastMessage(Resource):
    def get(self):
        message = request.args.get('message', default = 'This is a test!')
        text_query = 'broadcast "'+message+'"'
        display_text = assistant.assist(text_query=text_query)
        return {'status': 'OK'}

class StandardMessage(Resource):
    def get(self):
        message = request.args.get('message', default = 'This is a test!')
        text_query = message
        display_text = assistant.assist(text_query=text_query)
        return {'status': 'OK'}
    
api.add_resource(BroadcastMessage, '/broadcast_message')
api.add_resource(StandardMessage, '/standard_message')

class GoogleTextAssistant(object):
    """Assistant that supports text based conversations.

    Args:
      language_code: language for the conversation.
      device_model_id: identifier of the device model.
      device_id: identifier of the registered device instance.
      channel: authorized gRPC channel for connection to the
        Google Assistant API.
      deadline_sec: gRPC deadline in seconds for Google Assistant API call.
    """

    def __init__(self, language_code, device_model_id, device_id,
                 channel, deadline_sec):
        self.language_code = language_code
        self.device_model_id = device_model_id
        self.device_id = device_id
        self.conversation_state = None
        self.assistant = embedded_assistant_pb2_grpc.EmbeddedAssistantStub(
            channel
        )
        self.deadline = deadline_sec

    def __enter__(self):
        return self

    def __exit__(self, etype, e, traceback):
        if e:
            return False

    def assist(self, text_query):
        """Send a text request to the Assistant and playback the response.
        """
        def iter_assist_requests():
            dialog_state_in = embedded_assistant_pb2.DialogStateIn(
                language_code=self.language_code,
                conversation_state=b''
            )
            if self.conversation_state:
                dialog_state_in.conversation_state = self.conversation_state
            config = embedded_assistant_pb2.AssistConfig(
                audio_out_config=embedded_assistant_pb2.AudioOutConfig(
                    encoding='LINEAR16',
                    sample_rate_hertz=16000,
                    volume_percentage=0,
                ),
                dialog_state_in=dialog_state_in,
                device_config=embedded_assistant_pb2.DeviceConfig(
                    device_id=self.device_id,
                    device_model_id=self.device_model_id,
                ),
                text_query=text_query,
            )
            req = embedded_assistant_pb2.AssistRequest(config=config)
            yield req

        display_text = None
        for resp in self.assistant.Assist(iter_assist_requests(),
                                          self.deadline):
            if resp.dialog_state_out.conversation_state:
                conversation_state = resp.dialog_state_out.conversation_state
                self.conversation_state = conversation_state
            if resp.dialog_state_out.supplemental_display_text:
                display_text = resp.dialog_state_out.supplemental_display_text
        return display_text

if __name__ == '__main__':
    global assistant

    cred_json = Path(sys.argv[1])

    # open credentials
    with cred_json.open('r') as data:
        credentials = google.oauth2.credentials.Credentials(token=None, **json.load(data))
        http_request = google.auth.transport.requests.Request()
        credentials.refresh(http_request)

    # Create an authorized gRPC channel.
    grpc_channel = google.auth.transport.grpc.secure_authorized_channel(
        credentials, http_request, ASSISTANT_API_ENDPOINT)

    # Create the text assistant
    assistant = GoogleTextAssistant('en-US', 'HA_GA', 'HA_GA_TEXT_SERVER',
                             grpc_channel, DEFAULT_GRPC_DEADLINE)
    app.run(host='0.0.0.0')
