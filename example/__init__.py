from flask import Flask, jsonify
from flask.ext.restplus import Api, Resource
import os

from apy_blueprint.apib import Schema

CWD = os.path.dirname(__file__)

application = Flask(__name__)
api = Api(application)

class API:
  schema = Schema(api, os.path.join(CWD, 'spec.apib'))
  @schema.at('/wave')
  class Wave:
    def get(self):
      return {
        'channels': [],
        'formats': []
      }

    def post(self):
      pass

  @schema.at('/wave/channel/{channel_id}')
  class ChannelDetail:
    def get(self, channel_id):
      return { 'url': 'xyz' }


for rule in application.url_map.iter_rules():
  print(rule)
