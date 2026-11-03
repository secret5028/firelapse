"""Obsolete exterior-path rollover index migration; retained as an explicit guard."""
if __name__ == "__main__":
    raise SystemExit("Superseded by tools/refresh_fgi_rollover_state.py; independent rollover indices must not be restored.")
