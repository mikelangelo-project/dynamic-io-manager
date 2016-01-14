#include <Python.h>
#include <stdio.h>
#include <time.h>

#include "structmember.h"

static inline long long unsigned time_ns(struct timespec* const ts);

typedef struct {
    PyObject_HEAD
    struct timespec ts;
    unsigned long long up_time;
    unsigned long long up_time_diff;
} UpTimeCounterRaw;

static void UpTimeCounterRaw_dealloc(UpTimeCounterRaw* self)
{
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
UpTimeCounterRaw_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    UpTimeCounterRaw *self;

    self = (UpTimeCounterRaw *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->up_time = 0ULL;
        self->up_time_diff = 0ULL;
    }
    return (PyObject *)self;
}

static int
UpTimeCounterRaw_init(UpTimeCounterRaw *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "", kwlist))
        return -1;
    self->up_time = time_ns(&self->ts);
    self->up_time_diff = 0ULL;
    return 0;
}

static PyObject *
UpTimeCounterRaw_update(UpTimeCounterRaw *self)
{
    unsigned long long old = self->up_time;
    self->up_time = time_ns(&self->ts);
    self->up_time_diff = self->up_time - old;
    return (PyObject *)self;
}

static PyMethodDef UpTimeCounterRaw_methods[] = {
    {"update", (PyCFunction) UpTimeCounterRaw_update, METH_NOARGS,
     "update the uptime counter"},
    {NULL} /* Sentinel */
};

static PyMemberDef UpTimeCounterRaw_members[] = {
    {"up_time", T_ULONGLONG, offsetof(UpTimeCounterRaw, up_time), 0, "up time"},
    {"up_time_diff", T_ULONGLONG, offsetof(UpTimeCounterRaw, up_time_diff), 0,
        "up time difference"},
    {NULL}  /* Sentinel */
};

static PyTypeObject UpTimeCounterRawType = {
    PyObject_HEAD_INIT(NULL)
    0,                                        /*ob_size*/
    "uptime.UpTimeCounterRaw",                   /*tp_name*/
    sizeof(UpTimeCounterRaw),                    /*tp_basicsize*/
    0,                                        /*tp_itemsize*/
    (destructor)UpTimeCounterRaw_dealloc,        /*tp_dealloc*/
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
    UpTimeCounterRaw_methods,                    /* tp_methods */
    UpTimeCounterRaw_members,                    /* tp_members */
    0,                                        /* tp_getset */
    0,                                        /* tp_base */
    0,                                        /* tp_dict */
    0,                                        /* tp_descr_get */
    0,                                        /* tp_descr_set */
    0,                                        /* tp_dictoffset */
    (initproc)UpTimeCounterRaw_init,             /* tp_init */
    0,                                        /* tp_alloc */
    UpTimeCounterRaw_new,                        /* tp_new */
};

static PyMethodDef uptime_methods[] = {
    {NULL}  /* Sentinel */
};

#ifndef PyMODINIT_FUNC	/* declarations for DLL import/export */
#define PyMODINIT_FUNC void
#endif
PyMODINIT_FUNC
inituptime(void)
{
    PyObject* m;

    if (PyType_Ready(&UpTimeCounterRawType) < 0)
        return;

    m = Py_InitModule3("uptime", uptime_methods, "uptime counter module.");

    if (m == NULL)
      return;

    Py_INCREF(&UpTimeCounterRawType);
    PyModule_AddObject(m, "UpTimeCounterRaw", (PyObject *)&UpTimeCounterRawType);
}

static inline long long unsigned time_ns(struct timespec* const ts) {

    if (clock_gettime(CLOCK_REALTIME, ts)) {
        exit(1);
    }
    return ((long long unsigned) ts->tv_sec) * 1000000000LLU +
        (long long unsigned) ts->tv_nsec;
}
