import pandas

df = pandas.DataFrame({"a": [1]})
other = pandas.DataFrame({"a": [2]})
out = df.append(other)
csv = pandas.read_csv("x.csv")
