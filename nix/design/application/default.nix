{ buildPythonApplication
, setuptools
}:

buildPythonApplication {
  name = "application";
  format = "pyproject";

  src = ./../../../design/application;

  nativeBuildInputs = [ setuptools ];

  pythonImportsCheck = [ "application" ];
}
