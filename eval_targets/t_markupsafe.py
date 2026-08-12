import markupsafe
from markupsafe import Markup, escape

s = markupsafe.soft_unicode("x")
m = Markup("<b>hi</b>")
e = escape("<x>")
