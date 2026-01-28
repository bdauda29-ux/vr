import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.migrations import run_migrations

if __name__ == "__main__":
    run_migrations()
