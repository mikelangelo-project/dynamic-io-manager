#include <Python.h>

#include "structmember.h"
#include "kernel_mapper.h"

typedef struct {
    PyObject_HEAD
    u64 *ptr;
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
        self->ptr = NULL;
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
    self->ptr = (u64 *)address;
    return 0;
}

static PyObject *
Counter_read(Counter *self, PyObject *args)
{
    return Py_BuildValue("K", *self->ptr);
}

static PyMethodDef Counter_methods[] = {
    {"read", (PyCFunction) Counter_read, METH_NOARGS, "read counter"},
    {NULL} /* Sentinel */
};

static PyTypeObject CounterType = {
    PyObject_HEAD_INIT(NULL)
    0,                                        /*ob_size*/
    "uptime.Counter",                         /*tp_name*/
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
    0,                                        /* tp_members */
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

static PyObject *
map(PyObject *self, PyObject *args)
{
    u64 kernel_address;
    void *user_address;

    if (!PyArg_ParseTuple(args, "K", &kernel_address))
        return NULL;
    if ((user_address = kernel_remap(kernel_address)) == NULL)
        return NULL;

    return Py_BuildValue("K", (u64)user_address);
}

static PyMethodDef kernel_mapper_methods[] = {
    {"map", (PyCFunction) map, METH_VARARGS, "map a kernel address"},
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
