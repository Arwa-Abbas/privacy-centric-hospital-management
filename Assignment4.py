"""Assignment 4 entry point. Run: streamlit run Assignment4.py.

The Streamlit layout lives in app.py; database and privacy steps are documented
in README.md and docs/IMPLEMENTATION_PLAN.md.
"""
import runpy

runpy.run_module("src.app", run_name="__main__")
