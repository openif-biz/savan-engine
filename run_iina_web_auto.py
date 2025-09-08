#!/usr/bin/env python3
from savan_iina_auto import generate_iina, run_command
poc_file = generate_iina()
run_command(f"streamlit run {poc_file}")
