"""Parte 2, studio confermativo: motori. Ricerca SEMPRE spenta, nessun system prompt.
Riusa le classi dello studio principale (pipeline/cycle12_runner.py, pipeline/main_runner.py) senza cambiarle.
  gpt         Azure gpt-5.5 (AZURE_DEPLOYMENT_GPT), Responses API, nessuno strumento
  deepseek    Azure DeepSeek-V3.2 (AZURE_DEPLOYMENT_DEEPSEEK), stessa API, open-weight
  llama       Azure Llama-4-Maverick (AZURE_DEPLOYMENT_LLAMA), stessa API, open-weight
  perplexity  Agent API perplexity/sonar senza lo strumento web_search
  gemini_vertex  Vertex gemini-3.6-flash (solo dal Mac: servono le credenziali gcloud)
"""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline")); sys.path.insert(0, str(ROOT / "analysis"))
from thesis_env import load_env  # noqa: E402
load_env()
import cycle12_runner as c12  # noqa: E402
from cycle12_runner import with_retries, require  # noqa: E402,F401
import adapter_azure  # noqa: E402


class AzureOpen(c12.GPT):
    env = None; name = None; price = None
    def __init__(self):
        self.deployment = require(self.env)
        self.url = adapter_azure.responses_url(require("AZURE_OPENAI_ENDPOINT"))
        self.auth = {"api-key": require("AZURE_OPENAI_API_KEY")}
    def once(self, it):
        rec = super().once(it)
        rec["cost_usd_est"] = None; rec["deployment"] = self.deployment
        return rec


class DeepSeek(AzureOpen):
    env, name = "AZURE_DEPLOYMENT_DEEPSEEK", "deepseek"


class Llama(AzureOpen):
    env, name = "AZURE_DEPLOYMENT_LLAMA", "llama"


def motore(nome: str):
    if nome == "gpt":
        return c12.GPT()
    if nome == "perplexity":
        return c12.Perplexity()
    if nome == "deepseek":
        return DeepSeek()
    if nome == "llama":
        return Llama()
    if nome == "gemini_vertex":
        from main_runner import GeminiVertex
        return GeminiVertex()
    raise SystemExit(nome)


class Llama33(AzureOpen):
    env, name = "AZURE_DEPLOYMENT_LLAMA33", "llama33"
