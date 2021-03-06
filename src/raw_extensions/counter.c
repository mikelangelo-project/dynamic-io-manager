#include <Python.h>

#include "structmember.h"
#include "copy_to_user.h"

typedef struct {
    PyObject_HEAD
    u64 kernel_address;
    u64 value;
} Counter;

static void Counter_dealloc(Counter* self)
{
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
Counter_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    Counter *self;

    self = (Counter *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->kernel_address = 0UL;
    }
    return (PyObject *)self;
}

static int
Counter_init(Counter *self, PyObject *args, PyObject *kwds)
{
    u64 address;
    static char *kwlist[] = {"address", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "K", kwlist, &address))
        return -1;
    self->kernel_address = address;
    if (self->kernel_address != 0UL){
        copy_to_user(&self->value, self->kernel_address, sizeof(self->value));
    }
    return 0;
}

static PyObject *
Counter_read(Counter *self, PyObject *args)
{
    if (self->kernel_address != 0UL){
        copy_to_user(&self->value, self->kernel_address, sizeof(self->value));
    }
    return Py_BuildValue("K", self->value);
}

static PyMethodDef Counter_methods[] = {
    {"read", (PyCFunction) Counter_read, METH_NOARGS, "read counter"},
    {NULL} /* Sentinel */
};

static PyMemberDef Counter_members[] = {
    {"value", T_LONGLONG, offsetof(Counter, value), 0, "counter last read value"},
    {NULL} /* Sentinel */
};

static PyTypeObject CounterType = {
    PyObject_HEAD_INIT(NULL)
    0,                                        /*ob_size*/
    "kernel_mapper.Counter",                  /*tp_name*/
    sizeof(Counter),                          /*tp_basicsize*/
    0,                                        /*tp_itemsize*/
    (destructor)Counter_dealloc,              /*tp_dealloc*/
    0,                                        /*tp_print*/
    0,                                        /*tp_getattr*/
    0,                                        /*tp_setattr*/
    0,                                        /*tp_compare*/
    0,                                        /*tp_repr*/
    0,                                        /*tp_as_number*/
    0,                                        /*tp_as_sequence*/
    0,                                        /*tp_as_mapping*/
    0,                                        /*tp_hash */
    0,                                        /*tp_call*/
    0,                                        /*tp_str*/
    0,                                        /*tp_getattro*/
    0,                                        /*tp_setattro*/
    0,                                        /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /*tp_flags*/
    "Uptime counter objects",                 /* tp_doc */
    0,                                        /* tp_traverse */
    0,                                        /* tp_clear */
    0,                                        /* tp_richcompare */
    0,                                        /* tp_weaklistoffset */
    0,                                        /* tp_iter */
    0,                                        /* tp_iternext */
    Counter_methods,                          /* tp_methods */
    Counter_members,                          /* tp_members */
    0,                                        /* tp_getset */
    0,                                        /* tp_base */
    0,                                        /* tp_dict */
    0,                                        /* tp_descr_get */
    0,                                        /* tp_descr_set */
    0,                                        /* tp_dictoffset */
    (initproc)Counter_init,                   /* tp_init */
    0,                                        /* tp_alloc */
    Counter_new,                              /* tp_new */
};

static PyMethodDef kernel_mapper_methods[] = {
    {NULL}  /* Sentinel */
};

#ifndef PyMODINIT_FUNC	/* declarations for DLL import/export */
#define PyMODINIT_FUNC void
#endif
PyMODINIT_FUNC
initkernel_mapper(void)
{
    PyObject* m;

    if (PyType_Ready(&CounterType) < 0)
        return;

    m = Py_InitModule3("kernel_mapper", kernel_mapper_methods,
                       "kernel mapper module.");
    if (m == NULL)
      return;

    Py_INCREF(&CounterType);
    PyModule_AddObject(m, "Counter", (PyObject *)&CounterType);
 }
