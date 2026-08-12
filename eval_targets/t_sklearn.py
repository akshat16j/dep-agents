import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score

clf = LogisticRegression()
score = accuracy_score([0], [0])
