"""Prepare pinned Tesseract language files for source runs and Windows builds."""
import hashlib
import os
from pathlib import Path
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent / 'tessdata'
BASE = 'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/87416418657359cb625c412a48b6e1d6d41c29bd/'
FILES = {
    'rus.traineddata': 'e16e5e036cce1d9ec2b00063cf8b54472625b9e14d893a169e2b0dedeb4df225',
    'eng.traineddata': '7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2',
    'LICENSE': 'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30',
}


def prepare():
    ROOT.mkdir(exist_ok=True)
    for name, digest in FILES.items():
        target = ROOT / name
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
            continue
        with urllib.request.urlopen(BASE + name, timeout=30) as response:
            content = response.read(5_000_001)
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError(f'Неверная контрольная сумма {name}')
        with tempfile.NamedTemporaryFile(dir=ROOT, delete=False) as tmp:
            tmp.write(content)
        os.replace(tmp.name, target)


if __name__ == '__main__':
    prepare()
