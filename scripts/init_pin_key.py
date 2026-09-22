"""Initialize the local PIN encryption secret without replacing an existing key."""
import os
from pathlib import Path
import secrets

root = Path(__file__).resolve().parent.parent / '.runtime'
root.mkdir(exist_ok=True)
path = root / 'employee-pin.env'
try:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    print('Existing PIN key retained')
else:
    with os.fdopen(descriptor, 'w') as target:
        target.write('EMPLOYEE_PIN_KEY=' + secrets.token_hex(32) + '\n')
    print('PIN encryption key initialized')
