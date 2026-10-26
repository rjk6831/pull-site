"""Builds get/index.html from tools/get.template.html, inlining a static QR SVG."""
import pathlib, qr
root = pathlib.Path(__file__).resolve().parent.parent
url = "https://rjk6831.github.io/pull-site/get/"
html = (root / "tools/get.template.html").read_text().replace("@@QR@@", qr.svg(url))
(root / "get/index.html").write_text(html)
print(len(html.encode()), "bytes")
