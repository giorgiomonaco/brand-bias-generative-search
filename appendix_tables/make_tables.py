"""Genera le tabelle delle appendici del paper (26/10): prompt e persona di Study 1, domande e firme di Study 2,
istruzioni di riscrittura e di giudizio, elenco delle riscritture riviste. Scrive paper/sections/appendix_tables_s1.tex
e appendix_tables_s2.tex. Fonti: config/main_study_prompts.csv, config/cycle11_personas.yaml, data/part2_v4."""
import csv, json, re, yaml
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; SEC = Path(__file__).resolve().parent / "out"; SEC.mkdir(exist_ok=True); D = ROOT / "study2_experiment" / "materials"
SL = {"assicurazioni": "Insurance", "moda_beauty": "Fashion and beauty", "sport": "Sport", "viaggi": "Travel"}
def esc(s):
    s = str(s)
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"), ("_", r"\_"),
                 ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\^{}")):
        s = s.replace(a, b)
    return s.replace("’", "'")
# ---------- Study 1
P = list(csv.DictReader((ROOT / "study1_audit" / "config" / "main_study_prompts.csv").open()))
L = [r"\begingroup\scriptsize", r"\begin{longtable}{p{0.11\linewidth} p{0.47\linewidth} p{0.24\linewidth} r}",
     r"\caption{The 80 prompts of Study~1, with the keyword they were derived from and its mean monthly search volume in Italy over twelve months (DataForSEO).}\label{tab:a_prompts}\\",
     r"\toprule ID & Prompt & Keyword & Volume \\ \midrule \endfirsthead", r"\toprule ID & Prompt & Keyword & Volume \\ \midrule \endhead",
     r"\bottomrule \endlastfoot"]
for r in P:
    L.append(f"{esc(r['prompt_id'])} & \\textit{{{esc(r['prompt'])}}} & {esc(r['keyword'])} & {float(r['volume_12m']):,.0f} \\\\")
L += [r"\end{longtable}\endgroup", ""]
Pe = yaml.safe_load((ROOT / "study1_audit" / "config" / "cycle11_personas.yaml").open())["personas"]
RN = {"A": "Baseline persona (A)", "B": "Price variant (B)", "C": "Profile variant (C)"}
L += [r"\begin{table}[h]", r"\centering\scriptsize", r"\caption{The twelve buyer personas of Study~1, placed before the question in Italian; English translation below each.}\label{tab:a_personas}",
      r"\begin{tabularx}{\linewidth}{l l X}", r"\toprule Sector & Persona & Text \\ \midrule"]
for p in Pe:
    L.append(f"{SL[p['settore']]} & {RN[p['ruolo']]} & \\textit{{{esc(p['it'])}}} \\newline {esc(p['en'])} \\\\")
L += [r"\bottomrule", r"\end{tabularx}", r"\end{table}"]
(SEC / "appendix_tables_s1.tex").write_text("\n".join(L) + "\n")
# ---------- Study 2
sel = json.loads((D / "selezione.json").read_text()); sc = json.loads((D / "scelte.json").read_text())
def nome(q, k):
    v = sel[q]
    for x in v["pagine"] + v["candidati"] + [v["piu_noto"]]:
        if x["chiave"] == k: return x["nome"]
    return k
L = [r"\begingroup\scriptsize", r"\begin{longtable}{p{0.12\linewidth} p{0.33\linewidth} p{0.11\linewidth} p{0.11\linewidth} p{0.1\linewidth} p{0.08\linewidth}}",
     r"\caption{The 24 questions of Study~2 with the target page and its signatures. Better known and less known are other real brands mentioned in the Study~1 answers to the same prompt; the invented brand has no registered \texttt{.it} domain.}\label{tab:a_s2}\\",
     r"\toprule ID & Question & Target & Better known & Less known & Invented \\ \midrule \endfirsthead",
     r"\toprule ID & Question & Target & Better known & Less known & Invented \\ \midrule \endhead", r"\bottomrule \endlastfoot"]
riv = []
for q in sorted(sc):
    st = json.loads((D / "stimoli" / f"{q}.json").read_text()); c = sc[q]
    L.append(f"{esc(q)} & \\textit{{{esc(sel[q]['domanda'])}}} & {esc(nome(q, c['bersaglio']))} & {esc(nome(q, c['piu_noto']))} & {esc(nome(q, c['meno_noto']))} & {esc(st['inventato'])} \\\\")
    if st.get("riscritture_riviste"): riv.append((q, st["riscritture_riviste"]))
L += [r"\end{longtable}\endgroup", ""]
txt = (ROOT / "study2_experiment" / "code" / "part2_v3" / "riscrivi_v3.py").read_text()
ISTR = dict(re.findall(r'"(STRUTTURA|FLUENCY|AUTHORITATIVE)": ((?:"[^"]*"\s*)+)', txt))
ISTR = {k: "".join(re.findall(r'"([^"]*)"', v)) for k, v in ISTR.items()}
rs = (ROOT / "study2_experiment" / "code" / "part2_conf" / "riscrivi.py").read_text()
def blocco(name):
    m = re.search(name + r'\s*=\s*\(?((?:\s*"[^"]*"\s*)+)', rs); return "".join(re.findall(r'"([^"]*)"', m.group(1)))
COM, GIU = blocco("COMUNE"), blocco("GIUDICE")
def clean(s): return esc(s.replace("\\n", " ").replace("{{", "{").replace("}}", "}").replace("=== TESTO === {t}", "").replace("=== A === {a}  === B === {b}", "").strip())
L += [r"\paragraph{Rewriting instructions (Italian, as sent to gpt-5.5).} Each rewrite instruction is followed by a common part.",
      r"\begin{itemize}\footnotesize"]
for k, lab in (("STRUTTURA", "Structure"), ("FLUENCY", "Fluency"), ("AUTHORITATIVE", "Authoritative")):
    L.append(f"\\item \\textsc{{{lab}}}: \\textit{{{clean(ISTR[k])}}}")
L.append(f"\\item Common part: \\textit{{{clean(COM)}}}")
L += [r"\end{itemize}", r"\paragraph{Judging instruction (Italian, as sent to deepseek-v3.2).} {\footnotesize\textit{" + clean(GIU) + r"}}", ""]
auto = [q for q, r in riv if not any("mano" in x for x in r)]
L += [r"\paragraph{Revised rewrites.} When a rewrite failed the checks three times, the attempt with the fewest errors was sent back to gpt-5.5 with the original for a minimal correction of what the checks had found, and then went through the same checks and the same judge. " +
      f"This happened for the structure rewrite of {len(auto)} questions ({', '.join(esc(q) for q in auto)}). The structure rewrite of sport\\_21 was corrected by hand (final length 1.16 times the original, just above the 15\\% limit) and passed the judge again. Every step is logged with the stimuli."]
(SEC / "appendix_tables_s2.tex").write_text("\n".join(L) + "\n")
print(len(P), len(Pe), len(sc), riv)
