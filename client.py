import base64, hashlib, http.client, json, resource, sys, time

def peak_mb():
    # ru_maxrss 단위: macOS는 바이트, Linux는 KB
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss / 1024 / 1024 if sys.platform == "darwin" else rss / 1024

mode, port, path = sys.argv[1], int(sys.argv[2]), sys.argv[3]
CHUNK = 64 * 1024
t0 = time.perf_counter()
if mode == "json":
    raw = open(path, "rb").read()
    body = json.dumps({"sha256": hashlib.sha256(raw).hexdigest(), "filename": "f.bin",
                       "data": base64.b64encode(raw).decode()}).encode()
    del raw
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=600)
    c.request("POST", "/upload", body, {"Content-Type": "application/json"})
    r = json.loads(c.getresponse().read()); wire = len(body); server = r["server_peak_mb"]; got = r["received"]
else:
    import grpc, upload_pb2, upload_pb2_grpc
    sent = [0]
    def gen():
        with open(path, "rb") as f:
            while b := f.read(CHUNK):
                sent[0] += len(b); yield upload_pb2.Chunk(data=b)
    stub = upload_pb2_grpc.UploadStub(grpc.insecure_channel(f"127.0.0.1:{port}"))
    res, call = stub.Submit.with_call(gen())
    got = res.received; wire = sent[0]; server = dict(call.trailing_metadata())["server-peak-mb"]
print(json.dumps({"mode": mode, "payload_mb": round(wire / 1e6, 1), "received_mb": round(got / 1e6, 1),
                  "seconds": round(time.perf_counter() - t0, 2), "client_peak_mb": round(peak_mb(), 1),
                  "server_peak_mb": float(server)}))
