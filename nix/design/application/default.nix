{ buildPythonApplication
, setuptools
, numpy-old
}:

buildPythonApplication {
  name = "application";
  format = "pyproject";

  src = ./../../../design/application;

  nativeBuildInputs = [ setuptools ];

  propagatedBuildInputs = [
    numpy-old
  ];

  pythonImportsCheck = [
    "application"
    "application.console"
    "application.wavdump"
  ];
}
