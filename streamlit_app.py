STREAMLIT_APPS = [
    "https://nexusiq-ai.streamlit.app",
]


if __name__ == "__main__":
    # Local compatibility wrapper: `streamlit run streamlit_app.py` should
    # render the real app, while wake_up_streamlit.py can still import
    # STREAMLIT_APPS without booting the UI.
    import main  # noqa: F401
