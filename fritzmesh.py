#!/usr/bin/env python3

# MIT License
# 
# Copyright (c) 2023 Lamarqe
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import os
import http.server
import socketserver
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
import requests
from xml.etree import ElementTree
import hashlib
import threading
import time
import json
from threading import Thread, Lock
from collections import namedtuple
import re
import pickle
from urllib.parse import urlparse, parse_qsl
import sys
import configparser

fritzboxUsername = ''
fritzboxPassword = ''
fritzboxHost     = ''
fritzMeshPort    = 0

invalidSid = "0000000000000000"
entryUrls  = ("/", "/#homeNet")
cacheFilename = '/var/cache/fritzmesh/cache.pickle'
configFilename = '/etc/fritzmesh'

#see: https://stackoverflow.com/questions/34738611/how-can-i-use-python-to-change-css-attributes-of-an-html-document
bootStrapConfigs = {
  "/components/PageTabs/style.css": [(r'(.page-tabs--visible\s*{(.*?)})', r'(.*?display\s*?:\s*?)(.*?)([;}])', r'\1none\3')],
  "/css/box.css": [(r'(:root\s*{(.*?)})', r'(.*?--page-tabs-height-min-l\s*?:\s*?)(.*?)([;}])', r'\1 0\3'),
                   (r'(:root\s*{(.*?)})', r'(.*?--page-tabs-height-max-m\s*?:\s*?)(.*?)([;}])', r'\1 0\3'),
                   (r'(:root\s*{(.*?)})', r'(.*?--height-header-top\s*?:\s*?)(.*?)([;}])', r'\1 0\3'),
                   (r'(:root\s*{(.*?)})', r'(.*?--height-header-top-small\s*?:\s*?)(.*?)([;}])', r'\1 0\3'),
                   (r'(:root\s*{(.*?)})', r'(.*?--width-nav-left\s*?:\s*?)(.*?)([;}])', r'\1 0\3'),
                   (r'(:root\s*{(.*?)})', r'(.*?--height-breadcrumbs\s*?:\s*?)(.*?)([;}])', r'\1 0\3'),
                   (r'(#blueBarBox\s*{(.*?)})', r'(.*?z-index\s*?:\s*?)(.*?)([;}])', r'\1 -1\3'),
                   (r'(}\s*\.menuArea\s*{(.*?)})', r'(.*?padding\s*?:\s*?)(.*?)([;}])', r'\1 0\3')],
  "/net/mesh_overview.css": [(r'(@media only screen and \s*\((.*?)\))', r'(.*?max-width\s*?:\s*?)(.*?)([)])', r'\1 0\3')],
  "/net/mesh_overview.js": [(r'(const blocks\s*=\s*\[(.*?)\])', r'(,\s*buildIntro\(data\))', r''),
                            (r'(const blocks\s*=\s*\[(.*?)\])', r'(,\s*buildMeshablesInfo\(data\))', r''),
                            (r'(const blocks\s*=\s*\[(.*?)\])', r'(,\s*buildTable\(data\))', r''),
                            (r'(const blocks\s*=\s*\[(.*?)\])', r'(,\s*buildUpdateButton\(data\))', r'')]
} 


luaData          = None
dataLock         = Lock()
cachedData       = dict()
bootstrapSid     = invalidSid
currentSid       = invalidSid

HeaderResponsePair = namedtuple('HeaderResponsePair', ['headers', 'content'])

def fix(contentString, pattern, repl):
  return re.sub(pattern, repl, contentString.group(0), flags=re.S)

def bootstrap(path, response):
  if path not in bootStrapConfigs:
    return response.content
    
  contentString = str(response.content, encoding=response.encoding)
  for bsConfig in bootStrapConfigs[path]:
    contentString = re.sub(bsConfig[0], lambda contentString: fix(contentString, bsConfig[1], bsConfig[2]), contentString, flags=re.S)
  
  return bytes(contentString, response.encoding)

def getResponse(path):
  if path in entryUrls:
    path = "/?sid=" + bootstrapSid + "&lp=meshNet"

  if path in cachedData:
    return cachedData[path]

  response = requests.get('http://' + fritzboxHost + path)
  
  content = bootstrap(path, response)
  myPair = HeaderResponsePair(response.headers, content)

  cachedData[path] = myPair
  return myPair

class Handler(BaseHTTPRequestHandler):
  def log_request(code, size):
    pass

  def do_GET(self):    
    responseHeaders, responseContent = getResponse(self.path)

    self.send_response(HTTPStatus.OK)
    key = "Content-type"
    self.send_header(key, responseHeaders[key]);
    key = "Content-length"
    self.send_header(key, len(responseContent));
    self.end_headers()
    self.wfile.write(responseContent)
    

  def do_POST(self):    
    if (self.path == '/data.lua'):
      self.send_response(HTTPStatus.OK)
      self.send_header('Content-Type', 'application/json; charset=utf-8')
      self.end_headers()
      with dataLock:
        self.wfile.write(luaData)
    else:
      self.send_error(404, "File not found")


# Fritzbox login using PBKDF2 as described here:
# https://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/AVM_Technical_Note_-_Session_ID_deutsch_2021-05-03.pdf
def updateLogin():
  global currentSid
  
  response = requests.get('http://' + fritzboxHost + '/login_sid.lua?version=2&sid=' + currentSid)
  if response.status_code == HTTPStatus.OK:
    root = ElementTree.fromstring(response.content)
    currentSid = root.find("SID").text

    if currentSid != invalidSid:
      return currentSid
    else:
      challenge = root.find("Challenge").text
      _, iterations_1, salt_1, iterations_2, salt_2 = challenge.split('$')

      static_hash = hashlib.pbkdf2_hmac(
          "sha256",
          fritzboxPassword.encode(),
          bytes.fromhex(salt_1),
          int(iterations_1)
      )
      dynamic_hash = hashlib.pbkdf2_hmac(
          "sha256",
          static_hash,
          bytes.fromhex(salt_2),
          int(iterations_2)
      )
      challenge_hash = f"{salt_2}${dynamic_hash.hex()}"

      with requests.post(
          'http://' + fritzboxHost + '/login_sid.lua?version=2',
          data={'username': fritzboxUsername, 'response': challenge_hash},
          headers={"Content-Type": "application/x-www-form-urlencoded"}
      ) as sidResponse:
        root = ElementTree.fromstring(sidResponse.text)
        currentSid = root.find("SID").text
        return currentSid
  else:
    currentSid = invalidSid
    return currentSid


def updateLuaData():
  global currentSid
  global luaData
  with requests.post(
      'http://' + fritzboxHost + '/data.lua',
      data={'xhr': '1', 'sid': currentSid, 'lang': 'de', 'page': 'homeNet',
            'xhrId': 'refresh', 'updating': '', 'fwcheckstarted': '',
            'useajax': '1', 'no_sidrenew': ''},
      headers={"Content-Type": "application/x-www-form-urlencoded"}
  ) as luaResponse:
    luaJson = json.loads(luaResponse.text)
    if (luaJson['sid'] == invalidSid):
      return False
    else:
      luaJson['sid'] = bootstrapSid
      with dataLock:
        luaData = json.dumps(luaJson).encode('utf-8')
      return True


def luaThreadMain():
  while True:
    time.sleep(5.0)
    if not updateLuaData():
      updateLogin()


def main():
  global bootstrapSid
  global configFilename, cacheFilename, cachedData
  global fritzboxUsername, fritzboxPassword, fritzboxHost

  # load config
  try:
    with open(configFilename, 'r') as f:
      configString = "[DummyTop]\n" + f.read()
      config = configparser.ConfigParser()
      config.read_string(configString)
      config = config['DummyTop']
      fritzboxUsername = config['fritzboxUsername']
      fritzboxPassword = config['fritzboxPassword']
      fritzboxHost     = config['fritzboxHost']
      fritzMeshPort    = config.getint('fritzMeshPort')
  except (IOError, KeyError):
    print("Could not read config file '" + configFilename + "'. Exiting.", file=sys.stderr)
    return

  # load previously cached data
  try:
    with open(cacheFilename, 'rb') as f:
      cachedData = pickle.load(f)
      for key in cachedData:
        if key.startswith('/?sid='):
          query = dict(parse_qsl(urlparse(key).query))
          bootstrapSid = query['sid']
  except IOError:
    pass

  # get a valid login and sid from Fritzbox
  mySid = updateLogin()
  if (mySid == invalidSid):
    print("Could not access Fritzbox. Exiting.", file=sys.stderr)
    return
    
  if (bootstrapSid == invalidSid):
    # we got a valid sid for the first time. 
    bootstrapSid = mySid

  # fill initial mesh data and start polling
  updateLuaData()
  threading.Thread(target=luaThreadMain, daemon=True).start()

  # start the webserver
  httpd = http.server.HTTPServer(('', fritzMeshPort), Handler)
  try:
    httpd.serve_forever()
  except KeyboardInterrupt:
    pass
  finally:
    httpd.shutdown()
    
  # store the cache data
  with open(cacheFilename, 'wb') as f:
    # Pickle the 'data' dictionary using the highest protocol available.
    pickle.dump(cachedData, f, pickle.HIGHEST_PROTOCOL)

if __name__ == '__main__':
  main()