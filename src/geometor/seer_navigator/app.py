"""
run the main app
"""
from .seer_navigator import Seer_navigator


def run() -> None:
    reply = Seer_navigator().run()
    print(reply)
