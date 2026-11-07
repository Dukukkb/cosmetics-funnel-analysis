from pathlib import Path
from zipfile import ZipFile
import hashlib
import shutil

root = Path(__file__).resolve().parents[1]
checksums = {
    '2019-Oct': 'd87b1124a003151592e722996c6295aba2d286626c5db624c49d749877478c23',
    '2019-Nov': '25b03eea9020a64f97659a4cbce9d801ca81872910ce72348bfa607817539755',
}
for month, expected in checksums.items():
    target = root / 'data' / f'{month}.csv'
    if not target.exists():
        archive_path = root / 'data' / f'{month}.zip'
        if not archive_path.exists():
            raise SystemExit(f'Нет {target.name} или {archive_path.name}. Скачайте данные по инструкции в README.')
        with ZipFile(archive_path) as archive:
            with archive.open(f'{month}.csv') as source, target.open('wb') as output:
                shutil.copyfileobj(source, output)
    with target.open('rb') as source:
        actual = hashlib.file_digest(source, 'sha256').hexdigest()
    if actual != expected:
        raise ValueError(f'Контрольная сумма не совпадает: {target}')
    print(f'{month}: CSV подготовлен и проверен')
