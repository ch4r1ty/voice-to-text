"""
Simple file upload server for iPhone -> Windows transfer.
Python 3.13 compatible (no cgi module needed).
Run, then open http://<your-ip>:8000 on iPhone Safari.
"""

import os
import re
from http.server import HTTPServer, BaseHTTPRequestHandler

UPLOAD_DIR = os.path.dirname(os.path.abspath(__file__))


class UploadHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        page = b"""<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Upload to PC</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, sans-serif; max-width: 500px; margin: 40px auto; padding: 20px; background: #f5f5f7; }
  h2 { color: #1a1a1a; }
  .drop-zone { border: 2px dashed #ccc; border-radius: 12px; padding: 40px 20px; text-align: center; background: white; margin: 20px 0; cursor: pointer; transition: all 0.2s; }
  .drop-zone:active { border-color: #007aff; background: #e3f0ff; }
  input[type=file] { display: none; }
  .btn { display: block; width: 100%; background: #007aff; color: white; padding: 14px; border-radius: 10px; font-size: 17px; border: none; cursor: pointer; }
  .btn:active { background: #005ecb; }
  .btn:disabled { background: #ccc; }
  #status { margin-top: 15px; font-size: 15px; color: #555; text-align: center; }
  .success { color: #34c759 !important; font-weight: bold; }
  .error { color: #ff3b30 !important; }
  .filename { font-size: 13px; color: #999; margin-top: 8px; }
</style>
</head>
<body>
  <h2>\xf0\x9f\x93\xb1 Upload to PC</h2>
  <p>Select an audio file from your iPhone:</p>
  <div class="drop-zone" id="dropZone" onclick="document.getElementById('fileInput').click()">
    <p>\xf0\x9f\x93\x82 Tap here to choose a file</p>
    <p style="font-size:13px;color:#999">WAV, MP3, M4A, etc.</p>
    <p class="filename" id="fileName"></p>
  </div>
  <input type="file" id="fileInput">
  <button class="btn" id="uploadBtn" onclick="uploadFile()" disabled>Upload</button>
  <div id="status"></div>
  <script>
    const fileInput = document.getElementById('fileInput');
    const status = document.getElementById('status');
    const uploadBtn = document.getElementById('uploadBtn');
    const fileName = document.getElementById('fileName');

    fileInput.addEventListener('change', () => {
      if (fileInput.files.length > 0) {
        fileName.textContent = fileInput.files[0].name + ' (' + (fileInput.files[0].size/1024/1024).toFixed(1) + ' MB)';
        uploadBtn.disabled = false;
      }
    });

    async function uploadFile() {
      if (!fileInput.files.length) return;
      const file = fileInput.files[0];
      const formData = new FormData();
      formData.append('file', file);

      uploadBtn.disabled = true;
      uploadBtn.textContent = 'Uploading...';
      status.className = '';
      status.textContent = 'Uploading ' + file.name + '...';

      try {
        const resp = await fetch('/', { method: 'POST', body: formData });
        const text = await resp.text();
        if (resp.ok) {
          status.className = 'success';
          status.textContent = text;
          uploadBtn.textContent = 'Upload Another';
          uploadBtn.disabled = false;
          fileInput.value = '';
          fileName.textContent = '';
        } else {
          status.className = 'error';
          status.textContent = 'Failed: ' + text;
          uploadBtn.textContent = 'Retry';
          uploadBtn.disabled = false;
        }
      } catch (e) {
        status.className = 'error';
        status.textContent = 'Error: ' + e.message;
        uploadBtn.textContent = 'Retry';
        uploadBtn.disabled = false;
      }
    }
  </script>
</body>
</html>"""
        self.wfile.write(page)

    def do_POST(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send_text(400, "Expected multipart form data")
            return

        # Extract boundary
        m = re.search(r'boundary=(.+)', content_type)
        if not m:
            self._send_text(400, "No boundary found")
            return

        boundary = m.group(1).strip().encode()
        content_length = int(self.headers.get("Content-Length", 0))

        # Read full body
        body = self.rfile.read(content_length)

        # Split by boundary and find the file part
        parts = body.split(b"--" + boundary)
        filename = None
        file_data = None

        for part in parts:
            if b"filename=" not in part:
                continue

            # Find headers section (before \r\n\r\n)
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue

            header_str = part[:header_end].decode("utf-8", errors="ignore")

            # Extract filename
            fn_match = re.search(r'filename="(.+?)"', header_str)
            if fn_match:
                filename = fn_match.group(1)

            # File data is after headers, strip trailing \r\n
            file_data = part[header_end + 4:]
            if file_data.endswith(b"\r\n"):
                file_data = file_data[:-2]
            break

        if not filename or file_data is None:
            self._send_text(400, "No file found in upload")
            return

        # Sanitize and save
        safe_name = os.path.basename(filename)
        dest = os.path.join(UPLOAD_DIR, safe_name)

        with open(dest, "wb") as f:
            f.write(file_data)

        size_mb = len(file_data) / 1024 / 1024
        msg = f"\xe2\x9c\x85 Saved: {safe_name} ({size_mb:.1f} MB)".encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(msg)

        print(f"[UPLOAD] {safe_name} ({size_mb:.1f} MB) -> {dest}")

    def _send_text(self, code, msg):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(msg.encode("utf-8"))

    def log_message(self, format, *args):
        print(f"[{self.client_address[0]}] {format % args}")


if __name__ == "__main__":
    PORT = 8000
    server = HTTPServer(("0.0.0.0", PORT), UploadHandler)
    print(f"Upload server running on port {PORT}")
    print(f"iPhone Safari: http://172.20.10.2:8000")
    print(f"Or try:        http://10.103.132.164:8000")
    print(f"Files save to: {UPLOAD_DIR}")
    print("Press Ctrl+C to stop.\n")
    server.serve_forever()
