import os,tempfile
from pathlib import Path

# Test credentials exist only in the isolated temporary database. The password
# is hashed at startup and is never persisted as plaintext.
os.environ["DIGITAL_TWIN_DB"]=str(Path(tempfile.mkdtemp(prefix="digital_twin_test_"))/"digital_twin_test.db")
os.environ["DIGITAL_TWIN_BOOTSTRAP_ADMIN_USERNAME"]="test_admin"
os.environ["DIGITAL_TWIN_BOOTSTRAP_ADMIN_PASSWORD"]="PrototypeTestAdmin!123"
os.environ["DIGITAL_TWIN_TOKEN_SECRET"]="test-only-secret-with-at-least-thirty-two-characters"

