{ buildPythonApplication
, setuptools
, numpy
}:

buildPythonApplication {
  name = "application";
  format = "pyproject";

  src = ./../../../design/application;

  nativeBuildInputs = [ setuptools ];

  propagatedBuildInputs = [
    numpy
  ];

  pythonImportsCheck = [ "application" ];
}
