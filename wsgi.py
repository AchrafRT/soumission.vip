import json
from pathlib import Path
from flask import Flask, jsonify, request, send_file
from app_logic import DirectoryAPI
ROOT=Path(__file__).resolve().parent
INDEX=ROOT/'frontend'/'index.html'
MANIFEST=json.loads((ROOT/'FOUNDATION_MANIFEST.json').read_text(encoding='utf-8'))
API=DirectoryAPI()
app=Flask(__name__)
app.config['MAX_CONTENT_LENGTH']=12*1024*1024
@app.get('/')
@app.get('/admin')
@app.get('/invite')
def index(): return send_file(INDEX,mimetype='text/html')
@app.get('/brand-logo.png')
def brand_logo(): return send_file(ROOT/'assets'/'soumission-vip-logo.png',mimetype='image/png')
@app.get('/health')
def health(): return jsonify(ok=True,service=MANIFEST.get('name'),version=MANIFEST.get('version'))
@app.post('/api/call')
def call():
    req=request.get_json(silent=True) or {}
    return jsonify(API.call(req.get('method',''),req.get('payload') or {},req.get('token')))
