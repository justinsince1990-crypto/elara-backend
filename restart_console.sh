#!/bin/bash
pkill -f streamlit
nohup /root/elara/venv/bin/streamlit run /root/elara/ui_console.py --server.port 8502 --server.address 0.0.0.0 --server.enableCORS false --server.enableXsrfProtection false > /root/elara/streamlit_new.log 2>&1 &
echo "Done!"
