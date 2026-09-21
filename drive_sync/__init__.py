"""Deterministic Drive <-> local sync for the daily Routine. No LLM calls.

A Routine container starts empty each morning, so `pull` downloads course
material and state into data/ before the pipeline runs, and `push` writes
the updated state back only after delivery succeeded. See docs/tasks/01.
"""
