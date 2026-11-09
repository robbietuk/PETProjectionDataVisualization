# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""STIR INTERFACE layer (anti-corruption layer). The only package that may touch ``stir``.

    stir module -> SwigStirGateway -> StirProjDataSource -> model.ProjDataset

``gateway`` and ``source`` import nothing from STIR; only ``swig_gateway`` does, lazily.
"""
from .gateway import ProjDataLayout, StirGateway, StirNotFoundError, StirProjDataHandle
from .source import StirProjDataSource, open_stir_source
from .swig_gateway import probe_stir

__all__ = ["ProjDataLayout", "StirGateway", "StirNotFoundError", "StirProjDataHandle",
           "StirProjDataSource", "open_stir_source", "probe_stir"]
