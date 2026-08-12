import flask
from flask import Flask, jsonify

app = Flask(__name__)
p = flask.safe_join("static", "a.txt")
s = flask.json.htmlsafe_dumps({"a": 1})
r = jsonify({"ok": True})
