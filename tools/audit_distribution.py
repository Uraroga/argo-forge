#!/usr/bin/env python3
"""Audit locale in sola lettura: file Git pubblicabili e contesto Docker minimo.

Non è un parser generale .dockerignore: verifica il contratto restrittivo esatto
di questo progetto. Non invoca Docker, non estrae archivi, non legge alberi esclusi,
non crea pacchetti, non esegue staging e non stampa valori sospetti.
"""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DOCKER_RULES = ['**', '!Dockerfile', '!.dockerignore']
DOCKER_FILES = ['.dockerignore', 'Dockerfile']
SECRET_PATTERNS = {
    'token Telegram': rb'\b[0-9]{8,12}:[A-Za-z0-9_-]{30,}\b',
    'token GitHub': rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})',
    'chiave API': rb'\bsk-[A-Za-z0-9_-]{24,}',
    'chiave privata': rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'credenziali URL': rb'https?://[^\s/:@]+:[^\s/@]+@',
}


class AuditError(ValueError):
    pass


def entries(text):
    return [line.strip() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


def regular_file(root, name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name:
        raise AuditError('Percorso non ammesso nel manifest')
    parent = root
    for part in path.parts:
        parent = parent / part
        if parent.is_symlink():
            raise AuditError('Symlink non ammesso: ' + name)
    if not parent.is_file():
        raise AuditError('File richiesto assente: ' + name)
    return parent


def docker_context_files(root):
    rules = entries(regular_file(root, '.dockerignore').read_text())
    if rules != DOCKER_RULES:
        raise AuditError('Regole Docker diverse dal contesto minimo: richiedono revisione')
    override = root / 'Dockerfile.dockerignore'
    if override.exists() or override.is_symlink():
        raise AuditError('Dockerfile.dockerignore sostituirebbe le esclusioni verificate')
    dockerfile = regular_file(root, 'Dockerfile').read_text()
    logical = dockerfile.replace('\\\n', ' ')
    stages = set(re.findall(r'^FROM\s+.+?\s+AS\s+(\w+)\s*$', logical, re.I | re.M))
    for line in logical.splitlines():
        instruction = re.match(r'^\s*(COPY|ADD)\s+(.+)$', line, re.I)
        if instruction:
            source = re.match(r'--from=(\w+)\s+', instruction[2], re.I)
            if instruction[1].upper() != 'COPY' or not source or source[1] not in stages:
                raise AuditError('COPY/ADD richiede file locali o uno stage non verificato')
    return DOCKER_FILES.copy()


def git_files(root):
    env = {**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}
    result = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                            cwd=root, env=env, capture_output=True, check=True)
    return set(filter(None, result.stdout.decode().split('\0')))


def git_ignored_files(root, names):
    result = subprocess.run(['git', 'check-ignore', '--no-index', '--stdin', '-z'], cwd=root,
                            env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'},
                            input=('\0'.join(sorted(names)) + '\0').encode(), capture_output=True)
    if result.returncode not in (0, 1):
        raise subprocess.CalledProcessError(result.returncode, ['git', 'check-ignore'])
    return set(filter(None, result.stdout.decode().split('\0')))


def secret_types(data):
    return [kind for kind, pattern in SECRET_PATTERNS.items() if re.search(pattern, data)]


def check_example(text):
    for line in entries(text):
        name, separator, value = line.partition('=')
        if not separator or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name.strip()):
            raise AuditError('.env.example deve contenere soltanto assegnazioni fittizie')
        if value.strip() not in ('', 'REPLACE_ME', '"REPLACE_ME"', "'REPLACE_ME'"):
            raise AuditError('.env.example ammette solo valori vuoti o REPLACE_ME')


def audit(root):
    declared = entries(regular_file(root, 'distribution-files.txt').read_text())
    if len(declared) != len(set(declared)):
        raise AuditError('File duplicati nel manifest')
    expected = set(declared)
    optional = root / '.env.example'
    if optional.exists() or optional.is_symlink():
        expected.add('.env.example')
    actual = git_files(root)
    missing, unexpected = sorted(expected - actual), sorted(actual - expected)
    if missing or unexpected:
        raise AuditError(f'Manifest/Git divergenti: {len(missing)} mancanti, {len(unexpected)} inattesi')
    if git_ignored_files(root, actual):
        raise AuditError('Materiale escluso già tracciato o dichiarato: revisione necessaria')
    for name in sorted(expected):
        path = regular_file(root, name)
        if path.stat().st_size > 5_000_000:
            raise AuditError('File oltre il limite di revisione: ' + name)
        data = path.read_bytes()
        if b'\0' not in data[:8192] and secret_types(data):
            raise AuditError('Possibile segreto in ' + name + '; valori omessi')
        if name == '.env.example':
            check_example(data.decode('utf-8'))
    return {'public_files': sorted(expected), 'docker_context': docker_context_files(root),
            'secret_scan': 'nessun pattern ad alta confidenza; controllo euristico',
            'archives_opened': 0, 'docker_invoked': False, 'git_mutated': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='Risultato strutturato senza contenuti dei file')
    args = parser.parse_args()
    try:
        result = audit(ROOT)
    except (AuditError, OSError, subprocess.CalledProcessError) as exc:
        print('Audit fallito: ' + (str(exc) if isinstance(exc, AuditError) else type(exc).__name__), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"File pubblicabili: {len(result['public_files'])}")
        print('Contesto Docker: ' + ', '.join(result['docker_context']))
        print('Nessun pattern segreto ad alta confidenza; archivi e alberi esclusi non aperti.')
        print('Nessuna build, operazione Docker, modifica Git o pubblicazione.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
