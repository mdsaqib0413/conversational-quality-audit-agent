Set-Location $PSScriptRoot
python -m streamlit run app/streamlit_app.py --server.fileWatcherType none --server.runOnSave false --browser.gatherUsageStats false
