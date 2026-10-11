

#pragma once

#include "Module.h"

class PyDataBlock: protected Module {
public:
  PyDataBlock() : Module() {}
  void include(py::module_ &m);
};

extern PyDataBlock py_data_block;

