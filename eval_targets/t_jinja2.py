import jinja2
from jinja2 import Environment, Template

env = Environment()
tpl = Template("hi")
f = jinja2.contextfunction(lambda c: c)
u = jinja2.unicode_urlencode("a b")
