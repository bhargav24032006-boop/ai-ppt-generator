import sys
from pathlib import Path

# Add backend directory to sys.path so 'app' and 'main' can be imported easily
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
