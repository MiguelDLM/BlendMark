#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Core package for the BlendMark add-on.

Landmarks and semilandmarks are stored as plain points on a lightweight
"landmark set" object (see landmark_data.py) and drawn as a viewport overlay
(see overlay.py) -- no mesh geometry is ever created for them.
"""

from . import landmark_data
from . import overlay
from . import landmark_ops
from . import file_io
from . import pts_io
from . import panel

_modules = (landmark_data, overlay, landmark_ops, file_io, pts_io, panel)


def register():
    for module in _modules:
        module.register()


def unregister():
    for module in reversed(_modules):
        module.unregister()
