from distutils.core import setup
from Cython.Build import cythonize
import numpy
setup(ext_modules = cythonize("samplerbox_audio.pyx"), include_dirs=[numpy.get_include()])
# Additional part for dotstar handling
from distutils.core import setup, Extension
setup(name='dotstar', version='0.1', ext_modules=[Extension('dotstar', ['dotstar.c'])])
