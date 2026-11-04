# Ciclo 11 — unione di persona e prompt (Studio 1 e Studio 0)

Messaggio utente = `{persona} {prompt}`

- `{persona}`: la frase italiana della persona, da `config/cycle11_personas.yaml` (campo `it`), così com'è,
  con il punto finale.
- uno spazio (U+0020), uno solo;
- `{prompt}`: il prompt del settore, così com'è nei file congelati del ciclo 10.
- Tutto nel messaggio utente. System prompt vuoto (nessuna istruzione di sistema).
- Condizione senza persona: messaggio utente = `{prompt}`.

Esempio (assicurazioni, persona A, prompt 1):
`Sono genitore con una famiglia a carico. È la prima volta che stipulo una polizza. Cerco di spendere il meno possibile. Quale assicurazione RC moto scegliere?`
