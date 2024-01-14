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
