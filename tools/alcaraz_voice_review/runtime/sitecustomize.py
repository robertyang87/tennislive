import os,functools
import edge_tts
import edge_tts.communicate as communicate
from edge_tts.constants import TRUSTED_CLIENT_TOKEN
communicate.WSS_URL='wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1?Ocp-Apim-Subscription-Key='+TRUSTED_CLIENT_TOKEN
if os.environ.get('HTTPS_PROXY'):
    edge_tts.Communicate=functools.partial(edge_tts.Communicate,proxy=os.environ['HTTPS_PROXY'])
