"""Профиль C/C++ — плагин Vision03."""

from ...handlers.cpp_handler import CPP_SPEC
from .base import TSProfile

# #ifndef-guard оборачивает весь файл (preproc_ifdef/preproc_if) — прозрачная рамка.
CPP = TSProfile(CPP_SPEC, extra_frames={'preproc_ifdef', 'preproc_if'})
