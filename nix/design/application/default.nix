# This file is also available under the terms of the MIT license.
# See /LICENSE.mit and /README.md for more information.
{ buildPythonApplication
, setuptools
, numpy
, cython_3
}:

buildPythonApplication {
  name = "application";
  format = "pyproject";

  src = ./../../../design/application;

  nativeBuildInputs = [ setuptools cython_3 ];

  propagatedBuildInputs = [
    numpy
  ];

  pythonImportsCheck = [
    "application"
    "application.console"
    "application.wavdump"
  ];
}
