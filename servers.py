import base64, json, os, resource, sys, tempfile
from concurrent import futures
from http.server import BaseHTTPRequestHandler, HTTPServer

def peak_mb():
    # ru_maxrss 단위: macOS는 바이트, Linux는 KB
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / 1024 / 1024 if sys.platform == "darwin" else rss / 1024

def json_server(port):
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            doc = json.loads(body)
            data = base64.b64decode(doc["data"])
            with tempfile.NamedTemporaryFile() as f:
                f.write(data)
            out = json.dumps({"received": len(data), "server_peak_mb": round(peak_mb(), 1)}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(out))); self.end_headers()
            self.wfile.write(out)
        def log_message(self, *a): pass
    HTTPServer(("127.0.0.1", port), H).handle_request()

def grpc_server(port):
    import grpc, upload_pb2, upload_pb2_grpc
    class S(upload_pb2_grpc.UploadServicer):
        def Submit(self, it, ctx):
            n = 0
            with tempfile.NamedTemporaryFile() as f:
                for c in it:
                    f.write(c.data); n += len(c.data)
            ctx.set_trailing_metadata((("server-peak-mb", str(round(peak_mb(), 1))),))
            return upload_pb2.Result(received=n)
    s = grpc.server(futures.ThreadPoolExecutor(2)); upload_pb2_grpc.add_UploadServicer_to_server(S(), s)
    s.add_insecure_port(f"127.0.0.1:{port}"); s.start(); s.wait_for_termination(timeout=600)

if __name__ == "__main__":
    {"json": json_server, "grpc": grpc_server}[sys.argv[1]](int(sys.argv[2]))
