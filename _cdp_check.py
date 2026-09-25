# -*- coding: utf-8 -*-
"""Minimal CDP client using stdlib to inspect computed style."""
import socket, base64, os, json, time, urllib.request, subprocess, sys

EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PORT = 9223

proc = subprocess.Popen([
    EDGE, '--headless=new', '--disable-gpu',
    '--remote-debugging-port=%d' % PORT,
    '--remote-allow-origins=*',
    '--window-size=2484,1368',
    '--user-data-dir=D:\\metrocount\\_edgeprofile',
    'about:blank',
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def http_get(path, method='GET'):
    req = urllib.request.Request('http://127.0.0.1:%d%s' % (PORT, path), method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())

time.sleep(3)
# create a new tab with our page
try:
    target = http_get('/json/new?http://127.0.0.1:8000/?cdp=1', 'PUT')
except Exception:
    target = http_get('/json/new?http://127.0.0.1:8000/?cdp=1')

wsurl = target['webSocketDebuggerUrl']
host, port = '127.0.0.1', PORT
path = wsurl.split('127.0.0.1:%d' % PORT)[1]

s = socket.create_connection((host, port), timeout=10)
key = base64.b64encode(os.urandom(16)).decode()
s.sendall((
    'GET %s HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nUpgrade: websocket\r\n'
    'Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n'
    % (path, port, key)).encode())
resp = b''
while b'\r\n\r\n' not in resp:
    resp += s.recv(4096)

def ws_send(obj):
    data = json.dumps(obj).encode()
    hdr = bytearray([0x81])
    mask = os.urandom(4)
    n = len(data)
    if n < 126:
        hdr.append(0x80 | n)
    elif n < 65536:
        hdr.append(0x80 | 126); hdr += n.to_bytes(2, 'big')
    else:
        hdr.append(0x80 | 127); hdr += n.to_bytes(8, 'big')
    hdr += mask
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    s.sendall(bytes(hdr) + masked)

def ws_recv():
    chunks = []
    s.settimeout(15)
    while True:
        h = s.recv(2)
        if not h: break
        b1, b2 = h[0], h[1]
        ln = b2 & 0x7F
        if ln == 126:
            ln = int.from_bytes(s.recv(2), 'big')
        elif ln == 127:
            ln = int.from_bytes(s.recv(8), 'big')
        d = b''
        while len(d) < ln:
            d += s.recv(ln - len(d))
        chunks.append(d)
        if b1 & 0x80:
            break
    return json.loads(b''.join(chunks).decode())

ws_send({'id': 1, 'method': 'Page.enable'})
ws_recv()
ws_send({'id': 2, 'method': 'Runtime.enable'})
ws_recv()
time.sleep(4)  # let page load + app.js render

expr = r"""(function(){
  var out=[];
  var lps=document.querySelectorAll('.line-pair');
  lps.forEach(function(lp){
    var cs=getComputedStyle(lp); var r=lp.getBoundingClientRect();
    out.push({w:Math.round(r.width), maxw:cs.maxWidth});
  });
  var rules=[];
  for (var i=0;i<document.styleSheets.length;i++){
    var ss=document.styleSheets[i];
    try {
      var cr=ss.cssRules;
      for (var j=0;j<cr.length;j++){
        var t=cr[j].selectorText||'';
        if (t.indexOf('line-pair')>=0) rules.push({sel:t, maxw:cr[j].style.maxWidth||''});
      }
    } catch(e){ rules.push({err:ss.href}); }
  }
  return JSON.stringify({rects:out, rules:rules});
})()"""
ws_send({'id': 3, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}})
deadline = time.time() + 12
while time.time() < deadline:
    m = ws_recv()
    if m.get('id') == 3:
        print(json.dumps(m, ensure_ascii=False)[:800])
        break

proc.terminate()
