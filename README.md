# Argo Forge — LFM2.5 locale

<p align="center">
  <img src="assets/Mascotte_IA_LFM2_5_Intel_i3-3240.png"
       alt="Argo Forge - LFM2.5 su Intel Core i3-3240"
       width="500">
</p>

<p align="center">
  <strong>LFM2.5-24B-A2B Q4_K_M</strong><br>
  Intel Core i3-3240 @ 3.40 GHz — Ivy Bridge (2012)
</p>

Ambiente dedicato a **LFM2.5-24B-A2B Q4_K_M** su argo3, Ubuntu 24.04,
Intel Core i3-3240 (Ivy Bridge), 2 core / 4 thread, circa 30 GiB RAM.
Inferenza esclusivamente CPU: AVX/F16C, nessuna dipendenza da AVX2/FMA.

Il solo modello utilizzato è:
`/home/sergio/llama-cpp-models/LFM2.5-24B-A2B-Q4_K_M.gguf`.
Rimane esterno al repository, montato in sola lettura. Il contesto è sempre
**131072 token**, con due thread e un solo slot; non esistono selettori o fallback.

```text
localcode.py → un container llama.cpp → GGUF read-only
                         ↑
            Web UI + API su 127.0.0.1:18080
                         ↑
       OpenCode → shell compatta → repository corrente
```

## Comandi

```bash
python3 localcode.py dry-run
python3 localcode.py start
python3 localcode.py status
python3 localcode.py logs
python3 localcode.py stats
python3 localcode.py restart
python3 localcode.py stop
```

Aprire **http://127.0.0.1:18080** per la Web UI integrata. API compatibile
OpenAI: `http://127.0.0.1:18080/v1`. Il server resta attivo dopo OpenCode;
`stop` lo arresta senza eliminarlo. `restart` riusa lo stesso container.
Non vengono scaricati pesi né eliminate immagini o container.

Per usare l'agente nel proprio progetto:

```bash
cd /percorso/del/progetto
python3 /home/sergio/Progetti/argo-forge/localcode.py code --steps 24 --output 256
```

OpenCode chiede approvazione prima dei comandi shell. `--auto-approve` abilita
esplicitamente l'esecuzione senza approvazione per ogni comando; usarlo solo
in progetti fidati. La shell opera come l'utente corrente: **non è una sandbox**.
Il tool può leggere, modificare, compilare e testare tramite Bash.
`--prompt 'istruzione'` esegue un task non interattivo. OpenCode gestisce il loop;
`--steps` e `--output` sono budget indipendenti dal contesto fisso.

## Accesso LAN

Il binding resta esclusivamente localhost. Da un altro computer della LAN,
con accesso SSH già configurato tramite chiave:

```bash
ssh -N -L 18080:127.0.0.1:18080 sergio@argo3
```

Aprire `http://127.0.0.1:18080` su quel computer. Non sono necessari password
applicative o credenziali nel repository. Non configurare port forwarding sul
router né pubblicare la porta Docker su `0.0.0.0`. API e Web UI condividono lo
stesso modello e uno slot: richieste simultanee possono attendere in coda.

## Documentazione

- [Installazione](docs/INSTALLATION.md)
- [Architettura e sicurezza](docs/ARCHITECTURE.md)
- [Diagnostica](docs/TROUBLESHOOTING.md)
- [Verifica effettiva](docs/VALIDATION.md)

128K è la capacità configurata, non una garanzia di velocità o qualità su prompt
lunghi. RAM, cache e prompt processing possono limitare fortemente questo host;
nessuna riduzione automatica del contesto. Non sono stati eseguiti benchmark estesi.

Licenza [MIT](LICENSE).
