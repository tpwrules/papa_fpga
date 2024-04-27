# This file is also available under the terms of the MIT license.
# See /LICENSE.mit and /README.md for more information.
{ buildPythonApplication
, setuptools
, numpy
, cython
}:

buildPythonApplication {
  name = "application";
  format = "pyproject";

  src = ./../../../design/application;

  nativeBuildInputs = [ setuptools cython ];

  propagatedBuildInputs = [
    numpy
  ];

  pythonImportsCheck = [
    "application"
    "application.console"
    "application.wavdump"
  ];
}
