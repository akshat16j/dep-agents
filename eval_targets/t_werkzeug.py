import werkzeug
from werkzeug import Response

it = werkzeug.wsgi.make_line_iter(None)
p = werkzeug.utils.safe_join("static", "a.txt")
resp = Response("ok")
