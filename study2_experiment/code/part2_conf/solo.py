import sys, taratura
from comune import esegui
m = sys.argv[1]; w = int(sys.argv[2]); b = float(sys.argv[3])
esegui([i for i in taratura.piano() if i["motore"] == m], taratura.OUT, budget_s=b, workers={m: w})
