"""Standalone LAN UDP diagnostic. Stores summaries only, never raw packets/tokens."""
import argparse
import json
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'blender'))
from spatial_pointer.core import PacketError, parse_packet


class Monitor:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = dict(received=0, valid=0, invalid=0, source=None,
                          last_received=None, packet=None, last_error=None)

    def record(self, raw, peer):
        try:
            packet = parse_packet(raw)  # Format only; deliberately no pairing check.
            summary = dict(seq=packet.seq, tracking=packet.tracking,
                           follow=packet.follow, grab=packet.grab, space=packet.space,
                           position_blender=packet.pose.position,
                           rotation_wxyz_blender=packet.pose.rotation)
            error = None
        except PacketError as exc:
            summary, error = None, str(exc)
        with self.lock:
            self.state['received'] += 1
            self.state['valid' if error is None else 'invalid'] += 1
            self.state.update(source=f'{peer[0]}:{peer[1]}', last_received=time.time(),
                              last_error=error)
            if summary is not None:
                self.state['packet'] = summary

    def snapshot(self):
        with self.lock:
            return dict(self.state)


def open_udp(host, port):
    connection = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if os.name == 'nt':
            connection.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        connection.bind((host, port))
        connection.settimeout(0.1)
        return connection
    except OSError:
        connection.close()
        raise


PAGE = '''<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Spatial Pointer — UDP受信テスト</title>
<style>
body{font:16px/1.7 system-ui,sans-serif;background:#f4f5f7;color:#19212c;margin:0}
main{max-width:850px;margin:40px auto;padding:0 24px}h1{font-size:28px;line-height:1.4}
.cards{display:flex;gap:12px;flex-wrap:wrap}.card,section{background:white;border:1px solid #dfe4ea;border-radius:14px;padding:20px;margin:12px 0}.card{flex:1;min-width:140px}
.number{display:block;font-size:38px;font-weight:650;font-variant-numeric:tabular-nums}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 monospace}
button{background:#1e5fe0;color:white;border:0;border-radius:8px;padding:10px 20px;font:inherit;cursor:pointer}.muted{color:#596577}
</style><main><h1>Blenderを使わないUDP受信テスト</h1>
<p id="status" role="status">受信ツールへ接続中…</p>
<section><strong>iPhoneアプリの設定</strong><div id="addresses"></div>
<div>トークン：<code>udp-test-1234</code>（このテストでは照合しません）</div>
<div class="muted">設定後「送信開始」を押し、アプリを開いたままにしてください。</div></section>
<div class="cards"><div class="card">受信総数<span class="number" id="received">0</span></div>
<div class="card">形式OK<span class="number" id="valid">0</span></div>
<div class="card">形式NG<span class="number" id="invalid">0</span></div></div>
<section><strong>最後の受信</strong><div id="source">まだ受信していません</div>
<pre id="packet">位置・回転・ボタン状態がここに表示されます。</pre><div id="error"></div></section>
<p class="muted">形式OKはBlenderと同じパーサーで検証します。トークン照合・セッション判定・物体操作は行いません。生データとトークンは表示・保存しません。</p>
<p class="muted">30分で自動終了します。終了ボタンで受信を止め、一時的なファイアウォール許可を削除します。ブラウザーを閉じるだけでは受信は止まりません。</p>
<button id="stop">受信テストを終了</button>
<script>
const el=id=>document.getElementById(id);let timer;
async function refresh(){try{const r=await fetch('/status',{cache:'no-store'});if(!r.ok)throw Error();const s=await r.json();
 for(const k of ['received','valid','invalid'])el(k).textContent=s[k];
 el('addresses').textContent='送信先PCのIP：'+s.addresses.join(' / ')+'　UDPポート：'+s.port;
 const age=s.last_received===null?null:Math.max(0,(Date.now()/1000-s.last_received));
 el('status').textContent=age===null?'受信待ちです。iPhoneから送信してください。':age<3?'受信できています。':`受信が止まっています（最後の受信 ${Math.floor(age)}秒前）`;
 el('source').textContent=s.source?'送信元：'+s.source:'まだ受信していません';
 if(s.packet)el('packet').textContent=JSON.stringify(s.packet,null,2);
 el('error').textContent=s.last_error?'最後のパケットの形式エラー：'+s.last_error:'';
 }catch{el('status').textContent='受信ツールが停止したか、接続できません。';}}
el('stop').onclick=async()=>{try{const r=await fetch('/stop',{method:'POST',headers:{'X-Monitor-Stop':'1'}});if(!r.ok)throw Error();clearInterval(timer);el('status').textContent='受信テストを終了しました。';el('stop').disabled=true;}catch{el('status').textContent='終了要求に失敗しました。';}};
refresh();timer=setInterval(refresh,1000);
</script></main></html>'''


def run(args):
    monitor = Monitor()
    stop = threading.Event()
    started = time.monotonic()
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    metadata = dict(port=args.port, http_port=args.http_port, addresses=args.pc_ip,
                    pid=os.getpid(), status='starting')

    def snapshot():
        return {**monitor.snapshot(), **metadata}

    def save_report():
        temporary = report.with_suffix('.tmp')
        temporary.write_text(json.dumps(snapshot(), ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(report)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/status':
                self.respond(json.dumps(snapshot()).encode(), 'application/json')
            elif self.path == '/':
                self.respond(PAGE.encode('utf-8'), 'text/html; charset=utf-8')
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path != '/stop' or self.headers.get('X-Monitor-Stop') != '1':
                self.send_error(403)
                return
            self.respond(b'{}', 'application/json')
            stop.set()

        def respond(self, body, content_type):
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *unused):
            pass

    receiver = None
    server = None
    try:
        receiver = open_udp(args.bind, args.port)
        server = ThreadingHTTPServer(('127.0.0.1', args.http_port), Handler)
        server.daemon_threads = True
        metadata.update(status='running', port=receiver.getsockname()[1],
                        http_port=server.server_address[1])
        save_report()
        threading.Thread(target=server.serve_forever, daemon=True).start()
        last_save = time.monotonic()
        while not stop.is_set() and time.monotonic() - started < args.duration:
            try:
                raw, peer = receiver.recvfrom(65535)
                monitor.record(raw, peer)
            except socket.timeout:
                pass
            if time.monotonic() - last_save >= 1:
                save_report()
                last_save = time.monotonic()
    except OSError as exc:
        metadata.update(status='error', error=f'Cannot open receiver: {exc}')
        return 1
    finally:
        if receiver:
            receiver.close()
        if server:
            server.shutdown()
            server.server_close()
        if metadata['status'] != 'error':
            metadata['status'] = 'stopped'
        save_report()
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5005)
    parser.add_argument('--http-port', type=int, default=8766)
    parser.add_argument('--duration', type=int, default=1800)
    parser.add_argument('--pc-ip', action='append', default=[])
    parser.add_argument('--report', default=str(Path(__file__).resolve().parents[1] / 'dist/udp-monitor-status.json'))
    sys.exit(run(parser.parse_args()))
